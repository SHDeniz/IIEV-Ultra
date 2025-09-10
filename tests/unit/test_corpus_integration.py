# tests/unit/test_corpus_integration.py

import pytest
import logging
# Importiere die Dateilisten aus conftest
from tests.conftest import UBL_CORPUS_FILES, CII_CORPUS_FILES, ZUGFERD_CORPUS_FILES
from src.services.extraction.extractor import extract_invoice_data
from src.services.mapping.mapper import map_xml_to_canonical
from src.services.mapping.xpath_util import MappingError
from src.db.models import InvoiceFormat

logger = logging.getLogger(__name__)

# --- Hilfsfunktion zur Ausführung der Tests ---

def run_corpus_test(file_path, expected_formats):
    """
    Führt Extraktion und Mapping für eine Corpus-Datei durch und prüft auf grundlegende Korrektheit.
    """
    logger.info(f"Testing corpus file: {file_path.name}")
    
    # Lade Dateiinhalt
    try:
        with open(file_path, 'rb') as f:
            raw_bytes = f.read()
    except IOError as e:
        pytest.fail(f"Konnte Testdatei nicht lesen: {e}")

    # 1. Test Extraktion
    detected_format, xml_bytes = extract_invoice_data(raw_bytes)
    
    assert detected_format in expected_formats, f"Format mismatch für {file_path.name}. Erwartet: {expected_formats}, Erhalten: {detected_format}"
    assert xml_bytes is not None, f"XML extraction failed für {file_path.name}"

    # 2. Test Mapping
    try:
        canonical_invoice = map_xml_to_canonical(xml_bytes, detected_format)
        
        # Grundlegende Plausibilitätsprüfungen (Sanity Checks)
        assert canonical_invoice.invoice_number is not None
        assert canonical_invoice.seller is not None
        assert canonical_invoice.buyer is not None
        # Wir können nicht > 0 prüfen, da Gutschriften (Credit Notes) negativ sein können.
        assert canonical_invoice.payable_amount is not None
        # Eine Rechnung/Gutschrift sollte Positionen haben
        assert len(canonical_invoice.lines) > 0
        
    except MappingError as e:
        # Wenn ein MappingError auftritt (z.B. fehlendes Pflichtfeld), lassen wir den Test fehlschlagen.
        pytest.fail(f"Mapping failed für Corpus-Datei {file_path.name}: {e}")
    except Exception as e:
        # Fange unerwartete Fehler (z.B. Pydantic Validation Errors) ab
        pytest.fail(f"Unerwarteter Fehler beim Mapping für {file_path.name}: {type(e).__name__}: {e}")

# --- Parametrisierte Tests ---

# Nutze pytest.mark.skipif, falls keine Dateien gefunden wurden.

@pytest.mark.skipif(not UBL_CORPUS_FILES, reason="UBL corpus files nicht gefunden.")
@pytest.mark.parametrize("file_path", UBL_CORPUS_FILES)
def test_corpus_ubl(file_path):
    """Testet UBL Dateien aus dem Corpus."""
    run_corpus_test(file_path, [InvoiceFormat.XRECHNUNG_UBL])

@pytest.mark.skipif(not CII_CORPUS_FILES, reason="CII corpus files nicht gefunden.")
@pytest.mark.parametrize("file_path", CII_CORPUS_FILES)
def test_corpus_cii(file_path):
    """Testet CII Dateien aus dem Corpus."""
    run_corpus_test(file_path, [InvoiceFormat.XRECHNUNG_CII])

@pytest.mark.skipif(not ZUGFERD_CORPUS_FILES, reason="ZUGFeRD corpus files nicht gefunden.")
@pytest.mark.parametrize("file_path", ZUGFERD_CORPUS_FILES)
def test_corpus_zugferd(file_path):
    """Testet ZUGFeRD/Factur-X PDF Dateien aus dem Corpus."""
    # ZUGFeRD und Factur-X verwenden intern CII
    run_corpus_test(file_path, [InvoiceFormat.ZUGFERD_CII, InvoiceFormat.FACTURX_CII])