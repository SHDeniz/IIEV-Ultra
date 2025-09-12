# tests/unit/validation/test_xsd_validator.py (Vollständig aktualisiert)

import pytest
from src.services.validation.xsd_validator import validate_xsd
from src.db.models import InvoiceFormat
# Stelle sicher, dass ValidationCategory importiert ist
from src.schemas.validation_report import ValidationSeverity, ValidationCategory

def check_fatal_system_errors(errors):
    """
    Helper, um den Test sofort fehlschlagen zu lassen, wenn fatale Systemfehler auftreten.
    """
    # Filtere nach FATAL Fehlern, die NICHT erwartete Syntaxfehler sind.
    system_fatal_errors = [
        e for e in errors 
        if e.severity == ValidationSeverity.FATAL and e.code != "XML_SYNTAX_ERROR"
    ]

    if system_fatal_errors:
        error = system_fatal_errors[0]
        # Dies bricht den Test sofort ab und meldet die Ursache klar.
        pytest.fail(f"Test execution aborted due to FATAL system error (Assets missing?): {error.code} - {error.message}")

def test_xsd_validation_valid_ubl(minimal_ubl_bytes):
    """Testet eine valide UBL Datei."""
    errors = validate_xsd(minimal_ubl_bytes, InvoiceFormat.XRECHNUNG_UBL)
    check_fatal_system_errors(errors)
    assert len(errors) == 0

def test_xsd_validation_invalid_structure(invalid_xsd_ubl_bytes):
    """Testet eine strukturell invalide UBL Datei."""
    errors = validate_xsd(invalid_xsd_ubl_bytes, InvoiceFormat.XRECHNUNG_UBL)
    check_fatal_system_errors(errors)
    
    # Filtere nach tatsächlichen XSD Violations
    validation_errors = [e for e in errors if e.code == "XSD_VIOLATION"]
    assert len(validation_errors) > 0
    
    error = validation_errors[0]
    assert error.severity == ValidationSeverity.ERROR
    assert error.category == ValidationCategory.STRUCTURE

def test_xsd_validation_syntax_error():
    """Testet die Behandlung von nicht wohlgeformtem XML."""
    malformed_xml = b"<Invoice><ID>123</ID>" # Fehlendes schließendes Tag
    errors = validate_xsd(malformed_xml, InvoiceFormat.XRECHNUNG_UBL)
    
    # Prüfe auf Systemfehler (z.B. fehlendes Schema), bevor wir den Syntaxfehler prüfen
    check_fatal_system_errors(errors)

    assert len(errors) > 0
    # Der Syntaxfehler selbst ist FATAL für die Verarbeitung
    assert errors[0].severity == ValidationSeverity.FATAL
    assert errors[0].code == "XML_SYNTAX_ERROR"