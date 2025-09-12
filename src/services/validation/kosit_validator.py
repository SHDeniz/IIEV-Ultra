# src/services/validation/kosit_validator.py
import logging
import subprocess
import tempfile
from pathlib import Path
from lxml import etree
from typing import List

from ...schemas.validation_report import ValidationError, ValidationCategory, ValidationSeverity
from .asset_service import asset_service

logger = logging.getLogger(__name__)

# Namespace für SVRL (Schematron Validation Reporting Language)
NS_SVRL = {"svrl": "http://purl.oclc.org/dsdl/svrl"}

def validate_kosit_schematron(xml_bytes: bytes, transaction_id: str) -> List[ValidationError]:
    """
    Führt die semantische Validierung mittels des externen KoSIT Prüftools (Java) durch.
    """
    logger.info(f"Starte KoSIT/Schematron Validierung für Transaktion {transaction_id}...")
    
    # Prüfe Verfügbarkeit der Assets
    if not asset_service.kosit_jar_path or not asset_service.kosit_scenarios_path.exists():
        return [_create_system_error("KOSIT_ASSETS_MISSING", "KoSIT Validator Assets (JAR oder Konfiguration) nicht gefunden.")]

    # Das Java-Tool benötigt Dateien auf dem Dateisystem.
    with tempfile.TemporaryDirectory(prefix="iiev_kosit_") as temp_dir:
        temp_dir_path = Path(temp_dir)
        
        # 1. Schreibe Input XML
        input_xml_path = temp_dir_path / f"{transaction_id}.xml"
        try:
            input_xml_path.write_bytes(xml_bytes)
        except IOError as e:
            logger.error(f"Fehler beim Schreiben der temporären XML-Datei: {e}")
            return [_create_system_error("KOSIT_IO_ERROR", str(e))]

        # 2. Konstruiere den Befehl
        # java -jar validator.jar -s scenarios.xml -r output_dir input.xml
        cmd = [
            "java", "-Dfile.encoding=UTF-8", "-jar", str(asset_service.kosit_jar_path),
            "-s", str(asset_service.kosit_scenarios_path), # Szenario Konfiguration
            "-r", str(temp_dir_path), # Output Directory für den Report
            str(input_xml_path)       # Input XML Datei
        ]

        # 3. Führe den Validator aus
        try:
            # check=False, da Exit Code != 0 bei Validierungsfehlern erwartet werden kann.
            result = subprocess.run(
                cmd, capture_output=True, text=True, check=False, timeout=60, encoding='utf-8'
            )
            
            # 4. Ergebnis auswerten
            # Das Tool generiert Reports im Output-Verzeichnis mit dem Suffix "-report.xml"
            report_path = temp_dir_path / f"{transaction_id}.xml-report.xml"

            # Prüfe auf Systemfehler (Exit Code != 0 UND kein Report vorhanden)
            if result.returncode != 0 and not report_path.exists():
                logger.error(f"KoSIT Validator Systemfehler (Exit Code {result.returncode}): STDERR: {result.stderr}")
                return [_create_system_error("KOSIT_EXECUTION_FAILED", result.stderr)]
            
            # 5. Parse den Report (SVRL)
            if report_path.exists():
                return _parse_svrl_report(report_path)
            
            # Wenn Exit Code 0 und kein Report (sollte selten vorkommen, aber möglich)
            if result.returncode == 0:
                logger.info("✅ KoSIT/Schematron Validierung erfolgreich (Keine Issues gefunden).")
                return []
            else:
                logger.error(f"KoSIT Report wurde nicht generiert, aber Exit Code war {result.returncode}. Stdout: {result.stdout}")
                return [_create_system_error("KOSIT_REPORT_MISSING", "Report wurde nicht erstellt.")]

        except subprocess.TimeoutExpired:
            return [_create_system_error("KOSIT_TIMEOUT", "Timeout (60s) überschritten.")]
        except FileNotFoundError:
             logger.error("Java Runtime Environment (JRE) nicht gefunden. Ist JRE im Docker Container installiert?")
             return [_create_system_error("KOSIT_JRE_MISSING", "Java Runtime Environment nicht gefunden.")]
        except Exception as e:
            logger.error(f"Unerwarteter Fehler bei der Ausführung des KoSIT Validators: {e}", exc_info=True)
            return [_create_system_error("KOSIT_UNKNOWN_ERROR", str(e))]

def _parse_svrl_report(report_path: Path) -> List[ValidationError]:
    """Parst den SVRL Report und extrahiert Fehler und Warnungen."""
    errors = []
    try:
        tree = etree.parse(str(report_path))
    except etree.XMLSyntaxError as e:
        return [_create_system_error("KOSIT_REPORT_INVALID", str(e))]
        
    # Finde alle fehlgeschlagenen Assertions (Fehler) und erfolgreiche Reports (Warnungen/Infos)
    failed_asserts = tree.xpath("//svrl:failed-assert", namespaces=NS_SVRL)
    successful_reports = tree.xpath("//svrl:successful-report", namespaces=NS_SVRL)

    for assertion in failed_asserts:
        errors.append(_extract_svrl_item(assertion, ValidationSeverity.ERROR))

    for report in successful_reports:
        # Bestimme Severity basierend auf dem 'role' Attribut (z.B. WARNING, INFO)
        role = report.get("role", "").upper()
        if role == "WARNING":
            severity = ValidationSeverity.WARNING
        elif role == "INFO":
            severity = ValidationSeverity.INFO
        else:
            # Ignoriere successful reports ohne spezifische Rolle
            continue
        errors.append(_extract_svrl_item(report, severity))
    
    return errors

def _extract_svrl_item(item: etree._Element, severity: ValidationSeverity) -> ValidationError:
    """Extrahiert Details aus einem SVRL Element."""
    rule_id = item.get("id")
    location = item.get("location")
    test_condition = item.get("test")
    
    message_list = item.xpath("svrl:text/text()", namespaces=NS_SVRL)
    message = message_list[0].strip() if message_list else "Keine Nachricht verfügbar."

    return ValidationError(
        category=ValidationCategory.SEMANTIC,
        severity=severity,
        code=rule_id,
        message=message,
        location=location,
        description=f"Test Condition: {test_condition}"
    )

def _create_system_error(code: str, message: str) -> ValidationError:
    return ValidationError(
        category=ValidationCategory.TECHNICAL,
        severity=ValidationSeverity.FATAL,
        code=code,
        message=message
    )