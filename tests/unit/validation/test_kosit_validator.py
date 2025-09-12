# tests/integration/validation/test_kosit_validator.py
import pytest
import subprocess
import uuid
from src.services.validation.kosit_validator import validate_kosit_schematron
from src.services.validation.asset_service import asset_service
from src.schemas.validation_report import ValidationSeverity, ValidationCategory

# Prüfe Voraussetzungen: Java (JRE) und KoSIT Assets müssen vorhanden sein.
def is_java_available():
    try:
        # Prüft, ob der 'java' Befehl im System verfügbar ist.
        subprocess.check_call(['java', '-version'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

# Definiere eine Markierung, um diese Tests nur auszuführen, wenn Voraussetzungen erfüllt sind.
kosit_test = pytest.mark.skipif(
    not is_java_available() or not asset_service.kosit_jar_path or not asset_service.kosit_scenarios_path,
    reason="Skipping KoSIT tests: Java JRE oder KoSIT Assets nicht verfügbar."
)

@kosit_test
def test_kosit_validation_valid_ubl(minimal_ubl_bytes):
    """Testet eine valide UBL Datei mit dem KoSIT Validator."""
    transaction_id = str(uuid.uuid4())
    errors = validate_kosit_schematron(minimal_ubl_bytes, transaction_id)
    
    # Filtere nach echten Fehlern (ignoriere Warnungen/Infos)
    actual_errors = [e for e in errors if e.severity in [ValidationSeverity.ERROR, ValidationSeverity.FATAL]]
    
    assert len(actual_errors) == 0

@kosit_test
def test_kosit_validation_invalid_semantic(invalid_semantic_ubl_bytes):
    """Testet eine semantisch invalide UBL Datei (ungültiger Ländercode XX)."""
    transaction_id = str(uuid.uuid4())
    errors = validate_kosit_schematron(invalid_semantic_ubl_bytes, transaction_id)
    
    actual_errors = [e for e in errors if e.severity in [ValidationSeverity.ERROR, ValidationSeverity.FATAL]]
    assert len(actual_errors) > 0
    
    # Prüfe spezifisch auf Fehler bezüglich Ländercodes
    assert any(e.category == ValidationCategory.SEMANTIC for e in actual_errors)
    assert any("Country/IdentificationCode" in e.message or "Ländercode" in e.message for e in actual_errors)