# src/services/validation/xsd_validator.py
import logging
from lxml import etree
from io import BytesIO
from functools import lru_cache
from pathlib import Path
from typing import Optional

from ...db.models import InvoiceFormat
from ...schemas.validation_report import ValidationError, ValidationCategory, ValidationSeverity
from .asset_service import asset_service

logger = logging.getLogger(__name__)

@lru_cache(maxsize=10)
def _load_schema(xsd_path: Path) -> Optional[etree.XMLSchema]:
    """Lädt und cached das XSD Schema für Performance."""
    logger.info(f"Lade und kompiliere XSD Schema (Caching): {xsd_path.name}")
    try:
        # Sicherheit: resolve_entities=False (Schutz vor XXE)
        parser = etree.XMLParser(resolve_entities=False)
        # lxml benötigt einen String-Pfad für das Parsen, um relative Imports im XSD korrekt aufzulösen.
        schema_doc = etree.parse(str(xsd_path), parser=parser)
        return etree.XMLSchema(schema_doc)
    except etree.XMLSchemaError as e:
        logger.error(f"Fehler beim Kompilieren des XSD Schemas {xsd_path}: {e}")
        return None

def validate_xsd(xml_bytes: bytes, format: InvoiceFormat) -> list[ValidationError]:
    """
    Validiert XML-Daten gegen das entsprechende EN 16931 XSD-Schema.
    """
    logger.info(f"Starte XSD Validierung für Format {format.value}...")
    errors = []

    # 1. Lade das XSD Schema
    # Wir übergeben xml_bytes, damit der AssetService den UBL Typ (Invoice/CreditNote) bestimmen kann.
    xsd_path = asset_service.get_xsd_path(format, xml_bytes)
    
    if not xsd_path:
        errors.append(ValidationError(
            category=ValidationCategory.TECHNICAL, severity=ValidationSeverity.FATAL,
            message=f"Kein XSD Schema für Format {format.value} gefunden oder konfiguriert.", code="XSD_SCHEMA_MISSING"
        ))
        return errors

    xmlschema = _load_schema(xsd_path)
    if not xmlschema:
        errors.append(ValidationError(
            category=ValidationCategory.TECHNICAL, severity=ValidationSeverity.FATAL,
            message=f"XSD Schema konnte nicht kompiliert werden: {xsd_path.name}", code="XSD_SCHEMA_INVALID"
        ))
        return errors

    # 2. Parse das Input XML
    try:
        parser = etree.XMLParser(resolve_entities=False)
        doc = etree.parse(BytesIO(xml_bytes), parser=parser)
    except etree.XMLSyntaxError as e:
        # Fehlerbehandlung für nicht wohlgeformtes XML
        errors.append(ValidationError(
            category=ValidationCategory.STRUCTURE, severity=ValidationSeverity.FATAL,
            message=f"XML Syntaxfehler (nicht wohlgeformt): {e.msg}", code="XML_SYNTAX_ERROR",
            location=f"Line {e.lineno}, Column {e.offset}"
        ))
        return errors

    # 3. Validierung durchführen
    is_valid = xmlschema.validate(doc)

    if is_valid:
        logger.info("✅ XSD Validierung erfolgreich.")
        return []

    # 4. Fehler extrahieren
    logger.warning(f"❌ XSD Validierung fehlgeschlagen. {len(xmlschema.error_log)} Fehler gefunden.")
    
    for error in xmlschema.error_log:
        # Bereinige die Fehlermeldung von Namespace-Informationen für bessere Lesbarkeit
        clean_message = error.message.replace('{http://www.w3.org/2001/XMLSchema}', '')
        errors.append(ValidationError(
            category=ValidationCategory.STRUCTURE,
            severity=ValidationSeverity.ERROR,
            message=clean_message,
            location=f"Line {error.line}, Path: {error.path}",
            code="XSD_VIOLATION"
        ))

    return errors