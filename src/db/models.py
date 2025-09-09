"""
SQLAlchemy Datenmodelle für Metadaten-Tracking
Verfolgt den Status jeder eingehenden Rechnung
"""

import enum
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Enum, JSON, DateTime, func, Text, Integer, Numeric, Boolean, ForeignKey
from sqlalchemy.dialects.mssql import UNIQUEIDENTIFIER
from sqlalchemy.orm import declarative_base

Base = declarative_base()


class TransactionStatus(str, enum.Enum):
    """Status der Rechnungsverarbeitung"""
    RECEIVED = "RECEIVED"
    PROCESSING = "PROCESSING"
    VALID = "VALID"
    INVALID = "INVALID"
    MANUAL_REVIEW = "MANUAL_REVIEW"  # Für nicht-strukturierte Daten
    ERROR = "ERROR"  # Systemfehler


class InvoiceFormat(str, enum.Enum):
    """Erkannte Rechnungsformate"""
    XRECHNUNG_UBL = "XRECHNUNG_UBL"
    XRECHNUNG_CII = "XRECHNUNG_CII"
    ZUGFERD_CII = "ZUGFERD_CII"
    FACTURX_CII = "FACTURX_CII"
    OTHER_PDF = "OTHER_PDF"
    PLAIN_XML = "PLAIN_XML"
    UNKNOWN = "UNKNOWN"


class ValidationLevel(str, enum.Enum):
    """Validierungsstufen"""
    STRUCTURE = "STRUCTURE"  # XSD Validierung
    SEMANTIC = "SEMANTIC"    # Schematron/KoSIT
    CALCULATION = "CALCULATION"  # Mathematische Prüfung
    BUSINESS = "BUSINESS"    # ERP Business Rules
    COMPLIANCE = "COMPLIANCE"  # §14 UStG etc.


class InvoiceTransaction(Base):
    """Haupttabelle für Rechnungsverarbeitungs-Tracking"""
    __tablename__ = 'invoice_transactions'

    # Primärschlüssel
    id = Column(UNIQUEIDENTIFIER, primary_key=True, default=uuid.uuid4)
    
    # Status und Format (mit Index für Performance)
    status = Column(Enum(TransactionStatus), nullable=False, default=TransactionStatus.RECEIVED, index=True)
    format_detected = Column(Enum(InvoiceFormat), nullable=True)
    
    # Datei-Informationen
    original_filename = Column(String(255), nullable=True)
    file_size_bytes = Column(Integer, nullable=True)
    content_type = Column(String(100), nullable=True)
    
    # Azure Blob Storage URIs
    storage_uri_raw = Column(String(1024), nullable=True)
    storage_uri_xml = Column(String(1024), nullable=True)
    
    # Validierungsergebnisse
    validation_report = Column(JSON, nullable=True)
    validation_level_reached = Column(Enum(ValidationLevel), nullable=True)
    
    # Extrahierte Schlüsseldaten (für schnellen Zugriff)
    invoice_number = Column(String(100), nullable=True, index=True)  # Index für Duplikatscheck
    issue_date = Column(DateTime, nullable=True)
    total_amount = Column(Numeric(precision=18, scale=2), nullable=True)  # Erhöhte Präzision für B2B
    currency_code = Column(String(3), nullable=True)  # ISO 4217
    
    # Parteien-Informationen
    seller_name = Column(String(255), nullable=True)
    seller_vat_id = Column(String(50), nullable=True, index=True)  # Index für ERP Lookup
    buyer_name = Column(String(255), nullable=True)
    buyer_vat_id = Column(String(50), nullable=True)
    
    # ERP Integration
    erp_vendor_id = Column(String(50), nullable=True)
    purchase_order_id = Column(String(100), nullable=True)
    is_duplicate = Column(Boolean, nullable=True, default=False)  # Boolean statt String
    
    # Fehler-Tracking
    error_message = Column(Text, nullable=True)
    error_details = Column(JSON, nullable=True)
    retry_count = Column(Integer, default=0)
    
    # Zeitstempel (mit Index für Performance bei Zeitbereichsabfragen)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    processed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Verarbeitungszeiten (für Performance-Monitoring)
    processing_time_seconds = Column(Numeric(precision=8, scale=3), nullable=True)
    
    def __repr__(self):
        return f"<InvoiceTransaction(id={self.id}, status={self.status}, invoice_number={self.invoice_number})>"
    
    def to_dict(self) -> dict:
        """Konvertiere zu Dictionary für API-Responses"""
        return {
            'id': str(self.id),
            'status': self.status.value,
            'format_detected': self.format_detected.value if self.format_detected else None,
            'original_filename': self.original_filename,
            'file_size_bytes': self.file_size_bytes,
            'invoice_number': self.invoice_number,
            'issue_date': self.issue_date.isoformat() if self.issue_date else None,
            'total_amount': float(self.total_amount) if self.total_amount else None,
            'currency_code': self.currency_code,
            'seller_name': self.seller_name,
            'seller_vat_id': self.seller_vat_id,
            'buyer_name': self.buyer_name,
            'buyer_vat_id': self.buyer_vat_id,
            'erp_vendor_id': self.erp_vendor_id,
            'purchase_order_id': self.purchase_order_id,
            'is_duplicate': self.is_duplicate,
            'validation_report': self.validation_report,
            'validation_level_reached': self.validation_level_reached.value if self.validation_level_reached else None,
            'error_message': self.error_message,
            'retry_count': self.retry_count,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'processed_at': self.processed_at.isoformat() if self.processed_at else None,
            'processing_time_seconds': float(self.processing_time_seconds) if self.processing_time_seconds else None
        }


class ProcessingLog(Base):
    """Detailliertes Log für jeden Verarbeitungsschritt"""
    __tablename__ = 'processing_logs'
    
    id = Column(UNIQUEIDENTIFIER, primary_key=True, default=uuid.uuid4)
    transaction_id = Column(UNIQUEIDENTIFIER, ForeignKey('invoice_transactions.id'), nullable=False, index=True)
    
    step_name = Column(String(100), nullable=False)  # z.B. "format_detection", "xsd_validation"
    step_status = Column(String(20), nullable=False)  # "started", "completed", "failed"
    
    message = Column(Text, nullable=True)
    details = Column(JSON, nullable=True)
    duration_seconds = Column(Numeric(precision=8, scale=3), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    def __repr__(self):
        return f"<ProcessingLog(transaction_id={self.transaction_id}, step={self.step_name}, status={self.step_status})>"
