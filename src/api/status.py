"""
Status API Endpoints
Überwachung von Rechnungsverarbeitungs-Status
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_, func
from typing import Optional, List
import logging
from datetime import datetime, timedelta
from uuid import UUID

from ..db.session import get_metadata_session_dependency
from ..db.models import InvoiceTransaction, TransactionStatus, ProcessingLog
from ..schemas.validation_report import ValidationReport

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/status/{transaction_id}")
async def get_transaction_status(
    transaction_id: str,
    db: Session = Depends(get_metadata_session_dependency)
) -> dict:
    """
    Status einer spezifischen Transaction abfragen
    """
    
    try:
        # UUID Validierung
        uuid_obj = UUID(transaction_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Ungültige Transaction ID")
    
    # Transaction suchen
    transaction = db.query(InvoiceTransaction).filter(
        InvoiceTransaction.id == uuid_obj
    ).first()
    
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction nicht gefunden")
    
    # Verarbeitungslog laden (letzte 10 Einträge)
    processing_logs = db.query(ProcessingLog).filter(
        ProcessingLog.transaction_id == uuid_obj
    ).order_by(desc(ProcessingLog.created_at)).limit(10).all()
    
    # Response zusammenstellen
    response = transaction.to_dict()
    
    # Processing Log hinzufügen
    response["processing_log"] = [
        {
            "step_name": log.step_name,
            "step_status": log.step_status,
            "message": log.message,
            "duration_seconds": float(log.duration_seconds) if log.duration_seconds else None,
            "created_at": log.created_at.isoformat() if log.created_at else None
        }
        for log in processing_logs
    ]
    
    # Validation Report parsen falls vorhanden
    if transaction.validation_report:
        try:
            # ValidationReport aus JSON rekonstruieren
            response["validation_summary"] = {
                "is_valid": transaction.validation_report.get("summary", {}).get("is_valid", False),
                "total_errors": transaction.validation_report.get("summary", {}).get("total_errors", 0),
                "total_warnings": transaction.validation_report.get("summary", {}).get("total_warnings", 0),
                "highest_level_reached": transaction.validation_report.get("summary", {}).get("highest_level_reached", "NONE")
            }
        except Exception as e:
            logger.warning(f"Fehler beim Parsen des Validation Reports: {e}")
    
    return response


@router.get("/status")
async def list_transactions(
    status: Optional[TransactionStatus] = Query(None, description="Filter nach Status"),
    limit: int = Query(50, ge=1, le=1000, description="Anzahl Ergebnisse (max 1000)"),
    offset: int = Query(0, ge=0, description="Offset für Paginierung"),
    since_hours: Optional[int] = Query(None, ge=1, le=168, description="Nur Transaktionen der letzten X Stunden"),
    db: Session = Depends(get_metadata_session_dependency)
) -> dict:
    """
    Liste aller Transaktionen mit Filteroptionen
    """
    
    # Query zusammenbauen
    query = db.query(InvoiceTransaction)
    
    # Filter anwenden
    if status:
        query = query.filter(InvoiceTransaction.status == status)
    
    if since_hours:
        cutoff_time = datetime.now() - timedelta(hours=since_hours)
        query = query.filter(InvoiceTransaction.created_at >= cutoff_time)
    
    # Gesamtanzahl für Paginierung
    total_count = query.count()
    
    # Sortierung und Paginierung
    transactions = query.order_by(desc(InvoiceTransaction.created_at)).offset(offset).limit(limit).all()
    
    # Response zusammenstellen
    return {
        "transactions": [transaction.to_dict() for transaction in transactions],
        "pagination": {
            "total_count": total_count,
            "limit": limit,
            "offset": offset,
            "has_more": offset + limit < total_count
        },
        "filters": {
            "status": status.value if status else None,
            "since_hours": since_hours
        },
        "timestamp": datetime.now().isoformat()
    }


@router.get("/status/{transaction_id}/validation-report")
async def get_validation_report(
    transaction_id: str,
    db: Session = Depends(get_metadata_session_dependency)
) -> dict:
    """
    Vollständigen Validierungsbericht für eine Transaction abrufen
    """
    
    try:
        uuid_obj = UUID(transaction_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Ungültige Transaction ID")
    
    transaction = db.query(InvoiceTransaction).filter(
        InvoiceTransaction.id == uuid_obj
    ).first()
    
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction nicht gefunden")
    
    if not transaction.validation_report:
        raise HTTPException(
            status_code=404, 
            detail="Validierungsbericht noch nicht verfügbar"
        )
    
    return transaction.validation_report


@router.get("/statistics")
async def get_statistics(
    hours: int = Query(24, ge=1, le=168, description="Zeitraum in Stunden"),
    db: Session = Depends(get_metadata_session_dependency)
) -> dict:
    """
    Statistiken über Rechnungsverarbeitung
    """
    
    cutoff_time = datetime.now() - timedelta(hours=hours)
    
    # Basis-Query für den Zeitraum
    base_query = db.query(InvoiceTransaction).filter(
        InvoiceTransaction.created_at >= cutoff_time
    )
    
    # Statistiken sammeln
    total_transactions = base_query.count()
    
    # Status-Verteilung
    status_counts = {}
    for status_enum in TransactionStatus:
        count = base_query.filter(InvoiceTransaction.status == status_enum).count()
        status_counts[status_enum.value] = count
    
    # Format-Verteilung
    format_stats = db.query(
        InvoiceTransaction.format_detected,
        func.count(InvoiceTransaction.id).label('count')
    ).filter(
        InvoiceTransaction.created_at >= cutoff_time,
        InvoiceTransaction.format_detected.isnot(None)
    ).group_by(InvoiceTransaction.format_detected).all()
    
    format_counts = {
        format_type.value if format_type else "UNKNOWN": count 
        for format_type, count in format_stats
    }
    
    # Durchschnittliche Verarbeitungszeit
    avg_processing_time = db.query(
        func.avg(InvoiceTransaction.processing_time_seconds)
    ).filter(
        InvoiceTransaction.created_at >= cutoff_time,
        InvoiceTransaction.processing_time_seconds.isnot(None)
    ).scalar()
    
    # Fehlerrate berechnen
    error_count = base_query.filter(
        InvoiceTransaction.status.in_([TransactionStatus.ERROR, TransactionStatus.INVALID])
    ).count()
    
    error_rate = (error_count / total_transactions * 100) if total_transactions > 0 else 0
    
    # Success Rate
    success_count = base_query.filter(InvoiceTransaction.status == TransactionStatus.VALID).count()
    success_rate = (success_count / total_transactions * 100) if total_transactions > 0 else 0
    
    return {
        "period": {
            "hours": hours,
            "from": cutoff_time.isoformat(),
            "to": datetime.now().isoformat()
        },
        "overview": {
            "total_transactions": total_transactions,
            "success_rate_percent": round(success_rate, 2),
            "error_rate_percent": round(error_rate, 2),
            "avg_processing_time_seconds": round(float(avg_processing_time), 3) if avg_processing_time else None
        },
        "status_distribution": status_counts,
        "format_distribution": format_counts,
        "generated_at": datetime.now().isoformat()
    }


@router.post("/status/{transaction_id}/retry")
async def retry_transaction(
    transaction_id: str,
    db: Session = Depends(get_metadata_session_dependency)
) -> dict:
    """
    Fehlgeschlagene Transaction erneut verarbeiten
    """
    
    try:
        uuid_obj = UUID(transaction_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Ungültige Transaction ID")
    
    transaction = db.query(InvoiceTransaction).filter(
        InvoiceTransaction.id == uuid_obj
    ).first()
    
    if not transaction:
        raise HTTPException(status_code=404, detail="Transaction nicht gefunden")
    
    # Nur fehlgeschlagene Transaktionen können wiederholt werden
    if transaction.status not in [TransactionStatus.ERROR, TransactionStatus.INVALID]:
        raise HTTPException(
            status_code=400,
            detail=f"Transaction im Status '{transaction.status.value}' kann nicht wiederholt werden"
        )
    
    # Retry-Limit prüfen (max 3 Versuche)
    if transaction.retry_count >= 3:
        raise HTTPException(
            status_code=400,
            detail="Maximale Anzahl Wiederholungsversuche erreicht"
        )
    
    # Status zurücksetzen und Retry-Counter erhöhen
    transaction.status = TransactionStatus.RECEIVED
    transaction.retry_count += 1
    transaction.error_message = None
    transaction.error_details = None
    transaction.updated_at = datetime.now()
    
    db.commit()
    
    logger.info(f"🔄 Transaction {transaction_id} für Wiederholung markiert (Versuch #{transaction.retry_count})")
    
    # TODO: Celery Task erneut starten (wird in Sprint 1 implementiert)
    # from ..tasks.processor import process_invoice_task
    # process_invoice_task.delay(str(transaction_id))
    
    return {
        "transaction_id": transaction_id,
        "status": "retry_scheduled",
        "retry_count": transaction.retry_count,
        "message": "Transaction wurde für Wiederholung eingereicht",
        "updated_at": transaction.updated_at.isoformat()
    }
