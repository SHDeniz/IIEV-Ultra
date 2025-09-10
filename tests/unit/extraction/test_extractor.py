# tests/unit/extraction/test_extractor.py
import pytest
from src.services.extraction.extractor import extract_invoice_data
from src.db.models import InvoiceFormat

def test_extractor_ubl(minimal_ubl_bytes):
    """Testet, ob UBL korrekt als XML erkannt wird."""
    format, xml_bytes = extract_invoice_data(minimal_ubl_bytes)
    assert format == InvoiceFormat.XRECHNUNG_UBL
    assert xml_bytes == minimal_ubl_bytes

def test_extractor_cii(minimal_cii_bytes):
    """Testet, ob CII korrekt als XML erkannt wird."""
    format, xml_bytes = extract_invoice_data(minimal_cii_bytes)
    assert format == InvoiceFormat.XRECHNUNG_CII
    assert xml_bytes == minimal_cii_bytes

def test_extractor_zugferd(valid_zugferd_bytes):
    """Testet, ob ZUGFeRD/Factur-X korrekt aus PDF extrahiert wird."""
    format, xml_bytes = extract_invoice_data(valid_zugferd_bytes)
    
    # Muss FACTURX_CII sein, da wir "factur-x.xml" in der Fixture verwenden
    assert format == InvoiceFormat.FACTURX_CII
    assert xml_bytes is not None
    
    # Der Inhalt sollte das extrahierte XML sein
    assert b"CrossIndustryInvoice" in xml_bytes
    assert b"%PDF" not in xml_bytes

def test_extractor_simple_pdf(dummy_pdf_bytes):
    """Testet, ob einfache PDFs korrekt klassifiziert werden."""
    format, xml_bytes = extract_invoice_data(dummy_pdf_bytes)
    assert format == InvoiceFormat.OTHER_PDF
    assert xml_bytes is None
