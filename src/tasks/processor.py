"""
Haupt-Verarbeitungs-Tasks
Orchestriert den kompletten Rechnungsverarbeitungs-Workflow
"""

from celery import Task
from sqlalchemy.orm import Session
from sqlalchemy.exc import DatabaseError, IntegrityError
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import traceback
import time
import os

from .worker import celery_app
from ..db.session import get_metadata_session, get_erp_session
from ..db.models import InvoiceTransaction, TransactionStatus, ProcessingLog, ValidationLevel
from ..services.storage_service import StorageService
from ..schemas.validation_report import ValidationReport, ValidationStep, ValidationError, ValidationCategory, ValidationSeverity
from ..core.config import settings

logger = logging.getLogger(__name__)


class CallbackTask(Task):
    """
    Custom Task-Klasse mit automatischem Status-Update
    """
    
    def on_success(self, retval, task_id, args, kwargs):
        """Task erfolgreich abgeschlossen"""
        logger.info(f"✅ Task {task_id} erfolgreich abgeschlossen")
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Task fehlgeschlagen"""
        logger.error(f"❌ Task {task_id} fehlgeschlagen: {exc}")
        
        # Transaction Status auf ERROR setzen
        if args and len(args) > 0:
            transaction_id = args[0]
            try:
                with get_metadata_session() as db:
                    transaction = db.query(InvoiceTransaction).filter(
                        InvoiceTransaction.id == transaction_id
                    ).first()
                    
                    if transaction:
                        transaction.status = TransactionStatus.ERROR
                        transaction.error_message = str(exc)
                        transaction.error_details = {"traceback": str(einfo)}
                        transaction.updated_at = datetime.now()
                        db.commit()
                        
                        # Processing Log erstellen
                        log_entry = ProcessingLog(
                            transaction_id=transaction_id,
                            step_name="task_failure",
                            step_status="failed",
                            message=str(exc),
                            details={"traceback": str(einfo)}
                        )
                        db.add(log_entry)
                        db.commit()
                        
            except Exception as e:
                logger.error(f"Fehler beim Update des Transaction Status: {e}")


@celery_app.task(
    bind=True, 
    base=CallbackTask, 
    name="process_invoice_task",
    autoretry_for=(DatabaseError, ConnectionError, OSError),  # Retry bei transienten Fehlern
    retry_backoff=True,  # Exponential backoff
    retry_backoff_max=600,  # Max 10 Minuten
    retry_jitter=True,  # Zufälliger Jitter
    max_retries=5,  # Maximum 5 Versuche
    default_retry_delay=60  # 1 Minute Basis-Delay
)
def process_invoice_task(self, transaction_id: str) -> Dict[str, Any]:
    """
    Haupt-Task für die Rechnungsverarbeitung
    Orchestriert den kompletten Workflow von Format-Erkennung bis ERP-Integration
    
    Args:
        transaction_id: UUID der zu verarbeitenden Transaction
        
    Returns:
        Dictionary mit Verarbeitungsergebnis
    """
    
    start_time = time.time()
    logger.info(f"🚀 Starte Rechnungsverarbeitung für Transaction: {transaction_id} (Versuch {self.request.retries + 1})")
    
    try:
        with get_metadata_session() as db:
            # Transaction laden
            transaction = db.query(InvoiceTransaction).filter(
                InvoiceTransaction.id == transaction_id
            ).first()
            
            if not transaction:
                raise Exception(f"Transaction {transaction_id} nicht gefunden")
            
            # IDEMPOTENZ CHECK: Prüfe aktuellen Status
            if transaction.status == TransactionStatus.PROCESSING:
                logger.warning(f"Transaction {transaction_id} bereits in Verarbeitung. Race Condition erkannt.")
                return {
                    "transaction_id": transaction_id,
                    "status": "already_processing",
                    "message": "Transaction wird bereits verarbeitet (Race Condition vermieden)"
                }
            
            if transaction.status not in [TransactionStatus.RECEIVED, TransactionStatus.ERROR]:
                logger.info(f"Transaction {transaction_id} bereits verarbeitet (Status: {transaction.status.value})")
                return {
                    "transaction_id": transaction_id,
                    "status": "already_processed",
                    "current_status": transaction.status.value,
                    "message": "Transaction bereits erfolgreich verarbeitet"
                }
            
            # Status auf PROCESSING setzen (mit optimistischem Locking)
            transaction.status = TransactionStatus.PROCESSING
            transaction.updated_at = datetime.now()
            
            try:
                db.commit()
            except IntegrityError as e:
                # Race Condition beim Status-Update
                logger.warning(f"Race Condition beim Status-Update für {transaction_id}: {e}")
                db.rollback()
                return {
                    "transaction_id": transaction_id,
                    "status": "race_condition",
                    "message": "Andere Worker-Instanz verarbeitet bereits diese Transaction"
                }
            
            # Processing Log starten
            _log_processing_step(db, transaction_id, "processing_started", "started", "Verarbeitung gestartet")
            
            # Validation Report initialisieren
            validation_report = ValidationReport(
                transaction_id=transaction_id,
                invoice_number=transaction.invoice_number
            )
            
            # SCHRITT 1: Format-Erkennung und Extraktion (wird in Sprint 2 implementiert)
            logger.info(f"📋 Schritt 1: Format-Erkennung für {transaction_id}")
            format_step = ValidationStep(
                step_name="format_detection",
                step_description="Erkennung des Rechnungsformats und XML-Extraktion",
                status="SKIPPED",  # Placeholder - wird in Sprint 2 implementiert
                metadata={"reason": "Implementation in Sprint 2 geplant"}
            )
            validation_report.add_step(format_step)
            _log_processing_step(db, transaction_id, "format_detection", "skipped", "Format-Erkennung noch nicht implementiert")
            
            # SCHRITT 2: Strukturvalidierung (wird in Sprint 3 implementiert)
            logger.info(f"🔍 Schritt 2: XSD Validierung für {transaction_id}")
            structure_step = ValidationStep(
                step_name="structure_validation",
                step_description="XSD Schema Validierung",
                status="SKIPPED",
                metadata={"reason": "Implementation in Sprint 3 geplant"}
            )
            validation_report.add_step(structure_step)
            _log_processing_step(db, transaction_id, "structure_validation", "skipped", "XSD Validierung noch nicht implementiert")
            
            # SCHRITT 3: Semantische Validierung (wird in Sprint 3 implementiert)
            logger.info(f"🧠 Schritt 3: KoSIT Validierung für {transaction_id}")
            semantic_step = ValidationStep(
                step_name="semantic_validation",
                step_description="KoSIT Schematron Validierung",
                status="SKIPPED",
                metadata={"reason": "Implementation in Sprint 3 geplant"}
            )
            validation_report.add_step(semantic_step)
            _log_processing_step(db, transaction_id, "semantic_validation", "skipped", "KoSIT Validierung noch nicht implementiert")
            
            # SCHRITT 4: Mathematische Validierung (wird in Sprint 4 implementiert)
            logger.info(f"🧮 Schritt 4: Calculation Validation für {transaction_id}")
            calculation_step = ValidationStep(
                step_name="calculation_validation",
                step_description="Mathematische Prüfung von Summen und Steuern",
                status="SKIPPED",
                metadata={"reason": "Implementation in Sprint 4 geplant"}
            )
            validation_report.add_step(calculation_step)
            _log_processing_step(db, transaction_id, "calculation_validation", "skipped", "Berechnung Validierung noch nicht implementiert")
            
            # SCHRITT 5: Business Validierung (wird in Sprint 5 implementiert)
            logger.info(f"🏢 Schritt 5: ERP Business Validation für {transaction_id}")
            business_step = ValidationStep(
                step_name="business_validation",
                step_description="ERP Integration und Business Rules",
                status="SKIPPED",
                metadata={"reason": "Implementation in Sprint 5 geplant"}
            )
            validation_report.add_step(business_step)
            _log_processing_step(db, transaction_id, "business_validation", "skipped", "ERP Validierung noch nicht implementiert")
            
            # VORLÄUFIGER STATUS: Da alle Validierungsschritte noch nicht implementiert sind
            # setzen wir den Status auf MANUAL_REVIEW für Sprint 0
            transaction.status = TransactionStatus.MANUAL_REVIEW
            transaction.validation_report = validation_report.dict()
            transaction.validation_level_reached = ValidationLevel.STRUCTURE  # Placeholder
            
            # Verarbeitungszeit berechnen
            processing_time = time.time() - start_time
            transaction.processing_time_seconds = processing_time
            transaction.processed_at = datetime.now()
            transaction.updated_at = datetime.now()
            
            db.commit()
            
            # Abschluss-Log
            _log_processing_step(
                db, transaction_id, "processing_completed", "completed", 
                f"Verarbeitung abgeschlossen in {processing_time:.3f}s (Sprint 0 - Placeholder)"
            )
            
            logger.info(f"✅ Rechnungsverarbeitung für {transaction_id} abgeschlossen in {processing_time:.3f}s")
            
            return {
                "transaction_id": transaction_id,
                "status": transaction.status.value,
                "processing_time_seconds": processing_time,
                "validation_summary": validation_report.to_json_summary(),
                "message": "Verarbeitung abgeschlossen (Sprint 0 - Alle Validierungsschritte noch nicht implementiert)"
            }
            
    except Exception as e:
        # Fehlerbehandlung mit Retry-Logik
        processing_time = time.time() - start_time
        
        # Prüfe, ob es sich um einen retriable Fehler handelt
        is_retriable = isinstance(e, (DatabaseError, ConnectionError, OSError))
        
        if is_retriable and self.request.retries < self.max_retries:
            logger.warning(f"⚠️ Transienter Fehler bei {transaction_id} (Versuch {self.request.retries + 1}): {str(e)}")
            
            # Für retriable Fehler: Status nicht auf ERROR setzen
            try:
                with get_metadata_session() as db:
                    transaction = db.query(InvoiceTransaction).filter(
                        InvoiceTransaction.id == transaction_id
                    ).first()
                    
                    if transaction and transaction.status == TransactionStatus.PROCESSING:
                        # Status zurück auf RECEIVED für Retry
                        transaction.status = TransactionStatus.RECEIVED
                        transaction.updated_at = datetime.now()
                        db.commit()
                        
                        _log_processing_step(db, transaction_id, "processing_retry", "retry", 
                                           f"Retry {self.request.retries + 1} nach transienten Fehler: {str(e)}")
                        
            except Exception as db_error:
                logger.error(f"Fehler beim Retry-Status Update: {db_error}")
            
            # Celery Retry auslösen
            raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))
        
        else:
            # Permanenter Fehler oder Max Retries erreicht
            logger.error(f"❌ Permanenter Fehler bei Rechnungsverarbeitung {transaction_id}: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            
            try:
                with get_metadata_session() as db:
                    transaction = db.query(InvoiceTransaction).filter(
                        InvoiceTransaction.id == transaction_id
                    ).first()
                    
                    if transaction:
                        transaction.status = TransactionStatus.ERROR
                        transaction.error_message = str(e)
                        transaction.error_details = {
                            "traceback": traceback.format_exc(),
                            "retries_attempted": self.request.retries,
                            "is_retriable_error": is_retriable
                        }
                        transaction.processing_time_seconds = processing_time
                        transaction.updated_at = datetime.now()
                        db.commit()
                        
                        _log_processing_step(db, transaction_id, "processing_failed", "failed", 
                                           f"Permanenter Fehler nach {self.request.retries} Versuchen: {str(e)}")
                        
            except Exception as db_error:
                logger.error(f"Fehler beim Speichern des Fehler-Status: {db_error}")
            
            # Nicht re-raisen für permanente Fehler - Task als "completed with error" markieren
            return {
                "transaction_id": transaction_id,
                "status": "failed",
                "error": str(e),
                "retries_attempted": self.request.retries,
                "processing_time_seconds": processing_time
            }


@celery_app.task(name="email_monitoring_task")
def email_monitoring_task() -> Dict[str, Any]:
    """
    Periodischer Task zur Überwachung des E-Mail-Postfachs
    Simulation für Sprint 0 - echte E-Mail-Integration in Sprint 1
    """
    
    logger.info("📧 E-Mail Monitoring Task gestartet (Simulation)")
    
    # Überwache lokales Verzeichnis als Mock für E-Mail-Postfach
    mock_email_dir = "/tmp/iiev_email_mock"
    
    if not os.path.exists(mock_email_dir):
        os.makedirs(mock_email_dir, exist_ok=True)
        logger.info(f"📁 Mock E-Mail Verzeichnis erstellt: {mock_email_dir}")
    
    # Prüfe auf neue Dateien
    try:
        files = os.listdir(mock_email_dir)
        new_files = [f for f in files if f.endswith(('.pdf', '.xml'))]
        
        if new_files:
            logger.info(f"📧 {len(new_files)} neue E-Mail-Anhänge gefunden: {new_files}")
            
            # TODO: In Sprint 1 implementieren
            # - Dateien verarbeiten
            # - Transaction erstellen
            # - process_invoice_task starten
            # - Dateien nach Verarbeitung archivieren
            
        return {
            "status": "completed",
            "files_found": len(new_files),
            "files": new_files,
            "timestamp": datetime.now().isoformat(),
            "note": "Mock-Implementation für Sprint 0"
        }
        
    except Exception as e:
        logger.error(f"❌ E-Mail Monitoring Fehler: {e}")
        return {
            "status": "failed",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


@celery_app.task(name="cleanup_old_results_task")
def cleanup_old_results_task() -> Dict[str, Any]:
    """
    Wartungs-Task zum Aufräumen alter Celery Results und Logs
    """
    
    logger.info("🧹 Cleanup Task gestartet")
    
    try:
        cutoff_time = datetime.now() - timedelta(days=7)  # 7 Tage alte Daten löschen
        
        with get_metadata_session() as db:
            # Alte Processing Logs löschen
            old_logs = db.query(ProcessingLog).filter(
                ProcessingLog.created_at < cutoff_time
            ).count()
            
            db.query(ProcessingLog).filter(
                ProcessingLog.created_at < cutoff_time
            ).delete()
            
            db.commit()
            
            logger.info(f"🧹 {old_logs} alte Processing Logs gelöscht")
            
            return {
                "status": "completed",
                "deleted_logs": old_logs,
                "cutoff_date": cutoff_time.isoformat(),
                "timestamp": datetime.now().isoformat()
            }
            
    except Exception as e:
        logger.error(f"❌ Cleanup Task Fehler: {e}")
        return {
            "status": "failed",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


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
    Hilfsfunktion zum Loggen von Verarbeitungsschritten
    """
    
    try:
        log_entry = ProcessingLog(
            transaction_id=transaction_id,
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


# Entwicklungs-Helper Task
@celery_app.task(name="test_task")
def test_task(message: str = "Hello from IIEV-Ultra Celery!") -> Dict[str, Any]:
    """
    Test-Task für Entwicklung und Debugging
    """
    
    logger.info(f"🧪 Test Task ausgeführt: {message}")
    
    return {
        "message": message,
        "timestamp": datetime.now().isoformat(),
        "worker_id": test_task.request.id,
        "status": "success"
    }
