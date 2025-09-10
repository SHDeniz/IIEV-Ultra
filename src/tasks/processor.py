# src/tasks/processor.py (Aktualisiert und Kompatibel)

"""
Haupt-Verarbeitungs-Tasks
Orchestriert den kompletten Rechnungsverarbeitungs-Workflow
"""

from celery import Task
from sqlalchemy.orm import Session
from sqlalchemy.exc import DatabaseError # Import für Celery Retries
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import traceback
import time
import os
import uuid
import hashlib
from imap_tools import MailBox, AND, MailMessage

from .worker import celery_app
# Annahme: get_metadata_session existiert in db/session.py
from ..db.session import get_metadata_session 
from ..db.models import InvoiceTransaction, TransactionStatus, ProcessingLog, ValidationLevel, InvoiceFormat

# WICHTIG: Importiere den neuen synchronen Storage Service
from ..services.storage_service_sync import sync_storage_service

# Importiere die User-Version von ValidationReport
from ..schemas.validation_report import ValidationReport, ValidationStep, ValidationError, ValidationCategory, ValidationSeverity
from ..schemas.canonical_model import CanonicalInvoice
from ..core.config import settings

# Importiere die neuen Services
from ..services.extraction.extractor import extract_invoice_data
from ..services.mapping.mapper import map_xml_to_canonical
from ..services.mapping.xpath_util import MappingError


logger = logging.getLogger(__name__)


class CallbackTask(Task):
    """
    Custom Task-Klasse mit automatischem Status-Update bei endgültigem Fehler.
    """
    
    def on_success(self, retval, task_id, args, kwargs):
        logger.info(f"✅ Task {task_id} erfolgreich abgeschlossen")
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Task fehlgeschlagen (nachdem alle Retries erschöpft sind)"""
        logger.error(f"❌ Task {task_id} endgültig fehlgeschlagen: {exc}")
        
        # MappingErrors sind Geschäftslogik-Fehler und sollten bereits im Task behandelt worden sein (Status INVALID).
        if isinstance(exc, MappingError):
            return

        # Behandle Systemfehler (Status ERROR).
        if args and len(args) > 0:
            transaction_id = args[0]
            try:
                with get_metadata_session() as db:
                    transaction = db.query(InvoiceTransaction).filter(
                        InvoiceTransaction.id == transaction_id
                    ).first()
                    
                    # Nur aktualisieren, wenn der Status nicht bereits durch Geschäftslogik gesetzt wurde
                    if transaction and transaction.status not in [TransactionStatus.INVALID, TransactionStatus.MANUAL_REVIEW, TransactionStatus.VALID]:
                        transaction.status = TransactionStatus.ERROR
                        transaction.error_message = f"Systemfehler (nach Retries): {str(exc)}"
                        transaction.error_details = {"traceback": str(einfo)}
                        transaction.updated_at = datetime.now()
                        db.commit()
                        
                        _log_processing_step(db, transaction_id, "task_failure", "failed", str(exc), details={"traceback": str(einfo)})
                        
            except Exception as e:
                logger.error(f"Kritischer Fehler beim Update des Transaction Status nach Task Failure: {e}")


# Konfiguration für automatische Wiederholungen bei transienten Fehlern (DB/Netzwerk/Storage)
@celery_app.task(bind=True, base=CallbackTask, name="process_invoice_task",
                 autoretry_for=(DatabaseError, ConnectionError, IOError), 
                 retry_backoff=True, max_retries=5)
def process_invoice_task(self, transaction_id: str) -> Dict[str, Any]:
    """
    Haupt-Task für die Rechnungsverarbeitung.
    """
    
    start_time = time.time()
    logger.info(f"🚀 Starte Rechnungsverarbeitung für Transaction: {transaction_id}")
    
    # Prüfe Verfügbarkeit des synchronen Storage Service
    if sync_storage_service is None:
        raise RuntimeError("SyncStorageService ist nicht verfügbar.")

    # Initialisiere Variablen (Kompatibel mit User-Schema)
    validation_report = ValidationReport(transaction_id=transaction_id)
    canonical_invoice: Optional[CanonicalInvoice] = None
    
    try:
        with get_metadata_session() as db:
            # Transaction laden
            transaction = db.query(InvoiceTransaction).filter(
                InvoiceTransaction.id == transaction_id
            ).first()
            
            if not transaction:
                raise Exception(f"Transaction {transaction_id} nicht gefunden")

            # Idempotenz-Check
            if transaction.status not in [TransactionStatus.RECEIVED, TransactionStatus.ERROR]:
                logger.warning(f"Transaktion {transaction_id} bereits im Status {transaction.status.value}. Überspringe.")
                return {"status": "skipped", "reason": "already_processed_or_in_progress"}
            
            # Status auf PROCESSING setzen
            transaction.status = TransactionStatus.PROCESSING
            transaction.updated_at = datetime.now()
            db.commit()
            
            _log_processing_step(db, transaction_id, "processing_started", "started", "Verarbeitung gestartet")
            
            # --------------------------------------------------------------------
            # SCHRITT 1: Laden, Format-Erkennung und Extraktion (Integration Sprint 1 & 2)
            # --------------------------------------------------------------------
            logger.info(f"📋 Schritt 1: Laden und Extraktion für {transaction_id}")
            step1_start = time.time()
            # Initialisierung kompatibel mit User-Schema (Status als String)
            format_step = ValidationStep(
                step_name="format_detection_extraction",
                step_description="Laden, Format-Erkennung und XML-Extraktion",
                status="FAILED" # Default auf FAILED
            )

            # 1.1 Rohdaten laden (Synchron)
            if not transaction.storage_uri_raw:
                raise IOError("storage_uri_raw ist nicht gesetzt.")
            
            # Dies kann IOError auslösen, welcher von Celery Retry behandelt wird.
            raw_bytes = sync_storage_service.download_blob_by_uri(transaction.storage_uri_raw)

            # 1.2 Extraktion aufrufen
            detected_format, xml_bytes = extract_invoice_data(raw_bytes)
            
            transaction.format_detected = detected_format
            validation_report.detected_format = detected_format.value
            db.commit()

            # 1.3 Ergebnis prüfen und Workflow steuern
            format_step.duration_seconds = time.time() - step1_start

            if detected_format in [InvoiceFormat.OTHER_PDF, InvoiceFormat.UNKNOWN] or xml_bytes is None:
                # Nicht-strukturierte Daten -> Manuelle Prüfung
                logger.info(f"🛑 Format {detected_format.value} erkannt. Weiterleitung zur manuellen Prüfung.")
                
                # Kompatibel mit User-Schema: Füge Warnung hinzu, Status auf SUCCESS setzen, da Schritt technisch erfolgreich war.
                format_step.status = "SUCCESS"
                format_step.warnings.append(ValidationError(
                    message=f"Keine strukturierten Daten gefunden. Format: {detected_format.value}. Manuelle Bearbeitung erforderlich.",
                    category=ValidationCategory.TECHNICAL,
                    severity=ValidationSeverity.INFO
                ))
                validation_report.add_step(format_step)
                
                # Workflow hier beenden
                return _finalize_processing(db, transaction, TransactionStatus.MANUAL_REVIEW, validation_report, start_time)

            # 1.4 XML Speichern (Synchron, falls extrahiert, z.B. bei ZUGFeRD)
            if detected_format in [InvoiceFormat.ZUGFERD_CII, InvoiceFormat.FACTURX_CII]:
                # Nutze den synchronen Service für den Upload
                xml_uri = sync_storage_service.upload_processed_xml(
                    transaction_id=transaction.id, 
                    xml_content=xml_bytes, 
                    format_type=detected_format.value
                )
                transaction.storage_uri_xml = xml_uri
                db.commit()
            else:
                # Bei XRechnung sind Raw Data = XML Data
                transaction.storage_uri_xml = transaction.storage_uri_raw
                db.commit()

            format_step.status = "SUCCESS"
            format_step.metadata = {"format": detected_format.value, "xml_size_bytes": len(xml_bytes)}
            validation_report.add_step(format_step)
            _log_processing_step(db, transaction_id, "format_detection", "completed", f"Format {detected_format.value} erkannt.", duration=format_step.duration_seconds)


            # --------------------------------------------------------------------
            # SCHRITT 2: XML Mapping (Integration Sprint 2)
            # --------------------------------------------------------------------
            logger.info(f"🗺️ Schritt 2: XML Mapping für {transaction_id}")
            step2_start = time.time()
            # Initialisierung kompatibel mit User-Schema
            mapping_step = ValidationStep(
                step_name="xml_mapping",
                step_description="Transformation in das Canonical Model",
                status="FAILED"
            )

            try:
                canonical_invoice = map_xml_to_canonical(xml_bytes, detected_format)
                
                mapping_step.duration_seconds = time.time() - step2_start
                mapping_step.status = "SUCCESS"
                mapping_step.metadata = {"invoice_number": canonical_invoice.invoice_number, "total_amount": str(canonical_invoice.payable_amount)}
                validation_report.add_step(mapping_step)
                
                _log_processing_step(db, transaction_id, "xml_mapping", "completed", "Mapping zum Canonical Model erfolgreich.", duration=mapping_step.duration_seconds)
                
                # Wichtige Daten in die Transaction Tabelle übertragen
                _update_transaction_with_canonical_data(db, transaction, canonical_invoice)
                validation_report.invoice_number = canonical_invoice.invoice_number

            except MappingError as e:
                # Mapping fehlgeschlagen (Geschäftslogik-Fehler) -> Status INVALID, kein Retry.
                logger.error(f"🛑 Mapping Error für {transaction_id}: {e}")
                
                mapping_step.duration_seconds = time.time() - step2_start
                # Kompatibel mit User-Schema: Fehler direkt hinzufügen
                mapping_step.errors.append(ValidationError(
                    message=str(e),
                    # Verwende STRUCTURE, da dies im User-Enum vorhanden ist.
                    category=ValidationCategory.STRUCTURE, 
                    severity=ValidationSeverity.FATAL,
                    code="MAPPING_FAILED"
                ))
                validation_report.add_step(mapping_step)
                _log_processing_step(db, transaction_id, "xml_mapping", "failed", str(e), duration=mapping_step.duration_seconds)
                
                # Workflow hier beenden und Status auf INVALID setzen
                return _finalize_processing(db, transaction, TransactionStatus.INVALID, validation_report, start_time)


            # --------------------------------------------------------------------
            # SCHRITT 3, 4, 5: Validierung (Placeholder für Sprints 3-5)
            # --------------------------------------------------------------------
            # Diese Schritte arbeiten nun mit dem `canonical_invoice` Objekt.

            logger.info(f"🔍 Schritte 3-5: Validierung (Platzhalter)")
            # Placeholder Logik kompatibel mit User-Schema
            validation_report.add_step(ValidationStep(step_name="structure_validation", status="SKIPPED"))
            validation_report.add_step(ValidationStep(step_name="semantic_validation", status="SKIPPED"))
            validation_report.add_step(ValidationStep(step_name="business_validation", status="SKIPPED"))


            # VORLÄUFIGER STATUS: Wenn Mapping erfolgreich war, aber Validierung noch fehlt.
            final_status = TransactionStatus.MANUAL_REVIEW # Sicherer Default
            transaction.validation_level_reached = ValidationLevel.STRUCTURE # Mapping erfolgreich

            return _finalize_processing(db, transaction, final_status, validation_report, start_time)
            
    except Exception as e:
        # Generelle Fehlerbehandlung für Systemfehler (Retry durch Celery)
        logger.error(f"❌ Unerwarteter Systemfehler bei Rechnungsverarbeitung {transaction_id}: {str(e)}", exc_info=True)
        # Inkrementiere Retry Count in der DB
        try:
            with get_metadata_session() as db:
                 db.query(InvoiceTransaction).filter(InvoiceTransaction.id == transaction_id).update({"retry_count": InvoiceTransaction.retry_count + 1})
                 db.commit()
        except Exception:
             pass
        raise


# --- Hilfsfunktionen ---

def _finalize_processing(db: Session, transaction: InvoiceTransaction, status: TransactionStatus, report: ValidationReport, start_time: float) -> Dict[str, Any]:
    """
    Schließt die Verarbeitung ab, aktualisiert den Status und speichert das Ergebnis.
    """
    processing_time = time.time() - start_time
    
    transaction.status = status
    
    # Aktualisiere den Summary Report (wichtig in der User-Struktur)
    report._update_summary()
    report.total_duration_seconds = processing_time

    # Pydantic V2 Kompatibilität: Verwende model_dump() falls verfügbar, sonst dict()
    try:
        # Versuche V2 model_dump für JSON-kompatible Ausgabe
        transaction.validation_report = report.model_dump(mode='json')
    except AttributeError:
        # Fallback für Pydantic V1
        transaction.validation_report = report.dict()

    transaction.processing_time_seconds = processing_time
    transaction.processed_at = datetime.now()
    transaction.updated_at = datetime.now()
    
    db.commit()
    
    _log_processing_step(
        db, str(transaction.id), "processing_completed", "completed", 
        f"Verarbeitung abgeschlossen. Status: {status.value}. Dauer: {processing_time:.3f}s"
    )
    
    logger.info(f"🏁 Rechnungsverarbeitung für {transaction.id} abgeschlossen. Status: {status.value}. Dauer: {processing_time:.3f}s")
    
    return {
        "transaction_id": str(transaction.id),
        "status": status.value,
        "processing_time_seconds": processing_time,
        # Nutze die Methode aus dem User-Modell
        "validation_summary": report.to_json_summary(),
    }

def _update_transaction_with_canonical_data(db: Session, transaction: InvoiceTransaction, invoice: CanonicalInvoice):
    """
    Extrahiert Schlüsseldaten aus dem Canonical Model und speichert sie in der Transaction Tabelle.
    """
    try:
        transaction.invoice_number = invoice.invoice_number
        # Konvertiere date zu datetime für das DB-Modell
        if invoice.issue_date:
            transaction.issue_date = datetime.combine(invoice.issue_date, datetime.min.time())
        
        transaction.total_amount = invoice.payable_amount
        transaction.currency_code = invoice.currency_code.value
        
        transaction.seller_name = invoice.seller.name
        transaction.seller_vat_id = invoice.seller.vat_id
        transaction.buyer_name = invoice.buyer.name
        transaction.buyer_vat_id = invoice.buyer.vat_id
        
        if invoice.purchase_order_reference:
            transaction.purchase_order_id = invoice.purchase_order_reference.document_id
            
        db.commit()
        logger.debug(f"Transaction {transaction.id} mit extrahierten Daten aktualisiert.")
        
    except Exception as e:
        logger.error(f"Fehler beim Aktualisieren der Transaction mit Canonical Daten: {e}", exc_info=True)
        db.rollback()

def _log_processing_step(
    db: Session, 
    transaction_id: str, 
    step_name: str, 
    step_status: str, 
    message: str,
    details: Optional[Dict[str, Any]] = None,
    duration: Optional[float] = None
):
    """
    Hilfsfunktion zum Loggen von Verarbeitungsschritten.
    """
    try:
        # Konvertiere transaction_id zu UUID für MSSQL UNIQUEIDENTIFIER
        try:
            if isinstance(transaction_id, uuid.UUID):
                tx_uuid = transaction_id
            else:
                tx_uuid = uuid.UUID(str(transaction_id))
        except ValueError:
            logger.error(f"Ungültige transaction_id für Logging (keine UUID): {transaction_id}")
            return

        log_entry = ProcessingLog(
            transaction_id=tx_uuid,
            step_name=step_name,
            step_status=step_status,
            message=message,
            details=details,
            duration_seconds=duration
        )
        
        db.add(log_entry)
        db.commit()
        
        logger.debug(f"📝 Processing Log: {step_name} - {step_status} - {message}")
        
    except Exception as e:
        logger.error(f"Fehler beim Erstellen des Processing Logs: {e}")
        db.rollback() 


# --- Andere Tasks (E-Mail Monitoring etc.) ---

@celery_app.task(name="email_monitoring_task")
def email_monitoring_task() -> Dict[str, Any]:
    """
    Periodischer Task zur Überwachung des E-Mail-Postfachs.
    """
    if not settings.EMAIL_INGESTION_ENABLED:
        logger.info("📧 E-Mail Monitoring ist deaktiviert.")
        return {"status": "disabled"}

    if not all([settings.IMAP_HOST, settings.IMAP_USERNAME, settings.IMAP_PASSWORD]):
        logger.error("❌ E-Mail Monitoring Konfiguration unvollständig.")
        return {"status": "configuration_error"}

    logger.info(f"📧 Starte E-Mail Monitoring für {settings.IMAP_USERNAME}@{settings.IMAP_HOST}...")
    
    processed_count = 0
    error_count = 0

    try:
        # Verbinde zum IMAP Server (SSL/TLS wird standardmäßig verwendet)
        with MailBox(settings.IMAP_HOST, settings.IMAP_PORT).login(settings.IMAP_USERNAME, settings.IMAP_PASSWORD, settings.IMAP_FOLDER_INBOX) as mailbox:
            
            # Suche nach ungelesenen E-Mails
            uids = mailbox.uids(AND(seen=False))
            logger.info(f"📬 {len(uids)} neue E-Mails gefunden.")

            for uid in uids:
                msg = None
                try:
                    # Hole E-Mail (mark_seen=False, um Datenverlust bei Absturz zu verhindern)
                    msg = mailbox.fetch(uid, mark_seen=False)
                    
                    # Verarbeite Anhänge
                    attachments_processed = _process_email_attachments(msg)
                    
                    if attachments_processed > 0:
                        # Wenn erfolgreich verarbeitet: Verschiebe in Archiv und markiere als gelesen
                        mailbox.move(uid, settings.IMAP_FOLDER_ARCHIVE)
                        mailbox.seen(uid, True)
                        processed_count += attachments_processed
                    else:
                        # Keine relevanten Anhänge: Markiere als gelesen
                        logger.info(f"Keine relevanten Anhänge in E-Mail UID {uid}. Markiere als gelesen.")
                        mailbox.seen(uid, True)

                except Exception as e:
                    # Fehler bei der Verarbeitung dieser E-Mail
                    logger.error(f"❌ Fehler bei der Verarbeitung von E-Mail UID {uid} (Subject: {msg.subject if msg else 'N/A'}): {e}", exc_info=True)
                    error_count += 1
                    # Versuche in Error-Ordner zu verschieben
                    try:
                        mailbox.move(uid, settings.IMAP_FOLDER_ERROR)
                        mailbox.seen(uid, True)
                    except Exception as move_error:
                        logger.error(f"Fehler beim Verschieben in Error-Ordner: {move_error}")

    except Exception as e:
        # Fehler bei der Verbindung zum IMAP Server
        logger.error(f"❌ Kritischer Fehler beim E-Mail Monitoring (Verbindung/Login): {e}")
        return {"status": "failed", "error": str(e)}

    logger.info(f"✅ E-Mail Monitoring abgeschlossen. Verarbeitet: {processed_count}, Fehler: {error_count}.")
    return {
        "status": "completed",
        "processed_attachments": processed_count,
        "errors": error_count,
    }


def _process_email_attachments(msg: MailMessage) -> int:
    """
    Extrahiert Anhänge, speichert sie GoBD-konform und startet den Verarbeitungsprozess.
    """
    processed_count = 0
    logger.info(f"📄 Verarbeite Anhänge von E-Mail: {msg.subject} (Von: {msg.from_})")

    if sync_storage_service is None:
        raise RuntimeError("SyncStorageService ist nicht verfügbar für E-Mail-Verarbeitung.")

    for att in msg.attachments:
        # Filter für relevante Dateitypen (PDF, XML)
        if att.content_type not in ['application/pdf', 'application/xml', 'text/xml']:
            logger.info(f"Skipping Anhang {att.filename} (Typ: {att.content_type})")
            continue

        logger.info(f"Processing Anhang: {att.filename} ({len(att.payload)} bytes)")
        
        # Initialisiere DB Session
        db = None
        storage_uri = None
        try:
            # Wir müssen hier eine Session öffnen, da wir außerhalb des Contexts von process_invoice_task sind.
            # Verwenden Sie die Funktion, die in db/session.py definiert ist.
            db = get_metadata_session() 
            with db: # Nutze Session als Context Manager
                # 1. Erstelle neue Transaction in der Datenbank
                transaction = InvoiceTransaction(
                    status=TransactionStatus.RECEIVED,
                    original_filename=att.filename,
                    file_size_bytes=len(att.payload),
                    content_type=att.content_type,
                    # Metadaten zur Quelle
                    error_details={"source": "EMAIL", "email_subject": msg.subject, "email_from": msg.from_}
                )
                db.add(transaction)
                db.commit()
                transaction_id = str(transaction.id) 
                
                # 2. Speichere Anhang im Raw Storage (GoBD-konform)
                # Blob Name Konvention (transaction_id/filename)
                blob_name = f"{transaction_id}/{att.filename}"
                
                # Direkter Upload mit dem synchronen Service Client
                blob_client = sync_storage_service.blob_service_client.get_blob_client(
                    container=sync_storage_service.raw_container_name,
                    blob=blob_name
                )
                
                metadata = {
                   "transaction_id": transaction_id,
                   "source": "EMAIL",
                   "content_hash": hashlib.sha256(att.payload).hexdigest(),
                }
                
                # Synchroner Upload
                blob_client.upload_blob(att.payload, overwrite=True, metadata=metadata)
                storage_uri = blob_client.url

                # 3. Aktualisiere Transaction mit Storage URI
                transaction.storage_uri_raw = storage_uri
                db.commit()

                # 4. Starte asynchronen Verarbeitungsprozess
                process_invoice_task.delay(transaction_id)
                logger.info(f"🚀 Verarbeitung gestartet für Anhang {att.filename} (Transaction ID: {transaction_id})")
                processed_count += 1

        except Exception as e:
            logger.error(f"❌ Fehler bei der Verarbeitung des Anhangs {att.filename}: {e}", exc_info=True)
            if db:
                try:
                    db.rollback()
                except:
                    pass
            if storage_uri:
                 logger.critical(f"Inkonsistenz! Datei hochgeladen ({storage_uri}), aber DB-Transaktion fehlgeschlagen.")
            raise # Werfe Fehler weiter, damit die E-Mail als fehlerhaft markiert wird

    return processed_count


@celery_app.task(name="cleanup_old_results_task")
def cleanup_old_results_task() -> Dict[str, Any]:
     logger.info("🧹 Cleanup Task (Platzhalter)")
     return {"status": "skipped", "note": "Implementierung folgt"}