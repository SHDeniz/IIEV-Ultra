"""
Upload API Endpoints
Rechnungs-Upload und Verarbeitungsstart
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
import logging
import uuid
from datetime import datetime
from typing import Optional

from ..db.session import get_metadata_session_dependency
from ..db.models import InvoiceTransaction, TransactionStatus
from ..services.storage_service import StorageService
from ..core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/upload")
async def upload_invoice(
    file: UploadFile = File(...),
    db: Session = Depends(get_metadata_session_dependency)
) -> dict:
    """
    Rechnung hochladen und Verarbeitung starten
    
    - Akzeptiert PDF (ZUGFeRD/Factur-X) oder XML (XRechnung) Dateien
    - Speichert Datei in Azure Blob Storage
    - Erstellt Transaction Record in Datenbank
    - Startet asynchrone Verarbeitung via Celery
    """
    
    # Validierung der Datei
    if not file.filename:
        raise HTTPException(status_code=400, detail="Dateiname ist erforderlich")
    
    # Dateigröße prüfen
    file_content = await file.read()
    file_size = len(file_content)
    
    max_size = settings.max_file_size_mb * 1024 * 1024  # MB zu Bytes
    if file_size > max_size:
        raise HTTPException(
            status_code=413, 
            detail=f"Datei zu groß. Maximum: {settings.max_file_size_mb} MB"
        )
    
    # Dateityp validieren
    allowed_types = [
        "application/pdf",
        "application/xml", 
        "text/xml",
        "application/octet-stream"  # Für unbekannte PDF/XML
    ]
    
    content_type = file.content_type or "application/octet-stream"
    
    # Zusätzliche Validierung basierend auf Dateiendung
    filename_lower = file.filename.lower()
    if not (content_type in allowed_types or 
            filename_lower.endswith(('.pdf', '.xml', '.p7m'))):
        raise HTTPException(
            status_code=415,
            detail="Nicht unterstützter Dateityp. Erlaubt: PDF, XML"
        )
    
    try:
        # Eindeutige Transaction ID generieren
        transaction_id = uuid.uuid4()
        
        logger.info(f"📤 Upload gestartet: {file.filename} ({file_size} bytes) - ID: {transaction_id}")
        
        # Datei in Azure Blob Storage speichern
        storage_service = StorageService()
        blob_uri = await storage_service.upload_raw_file(
            transaction_id=str(transaction_id),
            filename=file.filename,
            content=file_content,
            content_type=content_type
        )
        
        logger.info(f"💾 Datei gespeichert: {blob_uri}")
        
        # Transaction Record in Datenbank erstellen
        transaction = InvoiceTransaction(
            id=transaction_id,
            status=TransactionStatus.RECEIVED,
            original_filename=file.filename,
            file_size_bytes=file_size,
            content_type=content_type,
            storage_uri_raw=blob_uri
        )
        
        db.add(transaction)
        db.commit()
        db.refresh(transaction)
        
        logger.info(f"📝 Transaction erstellt: {transaction_id}")
        
        # TODO: Celery Task starten (wird in Sprint 1 implementiert)
        # from ..tasks.processor import process_invoice_task
        # process_invoice_task.delay(str(transaction_id))
        
        # Response
        return {
            "transaction_id": str(transaction_id),
            "status": "received",
            "message": "Rechnung erfolgreich hochgeladen und zur Verarbeitung eingereicht",
            "filename": file.filename,
            "file_size_bytes": file_size,
            "content_type": content_type,
            "blob_uri": blob_uri,
            "created_at": transaction.created_at.isoformat() if transaction.created_at else None
        }
        
    except Exception as e:
        logger.error(f"❌ Upload-Fehler für {file.filename}: {str(e)}")
        
        # Rollback falls Transaction erstellt wurde
        db.rollback()
        
        # Detaillierte Fehlerbehandlung
        if "storage" in str(e).lower():
            raise HTTPException(
                status_code=503,
                detail="Speicher-Service temporär nicht verfügbar"
            )
        elif "database" in str(e).lower():
            raise HTTPException(
                status_code=503,
                detail="Datenbank temporär nicht verfügbar"
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Interner Server-Fehler: {str(e)}"
            )


@router.post("/upload/batch")
async def upload_batch(
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_metadata_session_dependency)
) -> dict:
    """
    Batch-Upload mehrerer Rechnungen
    Maximal 10 Dateien pro Batch
    """
    
    if len(files) > 10:
        raise HTTPException(
            status_code=400,
            detail="Maximal 10 Dateien pro Batch erlaubt"
        )
    
    if len(files) == 0:
        raise HTTPException(
            status_code=400,
            detail="Mindestens eine Datei erforderlich"
        )
    
    results = []
    successful_uploads = 0
    failed_uploads = 0
    
    logger.info(f"📦 Batch-Upload gestartet: {len(files)} Dateien")
    
    for file in files:
        try:
            # Einzelne Datei verarbeiten (Code-Wiederverwendung)
            result = await upload_invoice(file, db)
            results.append({
                "filename": file.filename,
                "status": "success",
                "transaction_id": result["transaction_id"],
                "message": "Erfolgreich hochgeladen"
            })
            successful_uploads += 1
            
        except HTTPException as e:
            results.append({
                "filename": file.filename or "unknown",
                "status": "failed",
                "error_code": e.status_code,
                "error_message": e.detail
            })
            failed_uploads += 1
            
        except Exception as e:
            results.append({
                "filename": file.filename or "unknown", 
                "status": "failed",
                "error_message": str(e)
            })
            failed_uploads += 1
    
    logger.info(f"📦 Batch-Upload abgeschlossen: {successful_uploads} erfolgreich, {failed_uploads} fehlgeschlagen")
    
    return {
        "batch_summary": {
            "total_files": len(files),
            "successful_uploads": successful_uploads,
            "failed_uploads": failed_uploads
        },
        "results": results,
        "timestamp": datetime.now().isoformat()
    }
