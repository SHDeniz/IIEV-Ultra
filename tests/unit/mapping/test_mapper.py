# tests/unit/mapping/test_mapper.py
import pytest
from decimal import Decimal
from src.services.mapping.mapper import map_xml_to_canonical
from src.services.mapping.xpath_util import MappingError
from src.db.models import InvoiceFormat
from src.schemas.canonical_model import CurrencyCode, CountryCode, TaxCategory

# Importiere die erwarteten Werte aus conftest.py
from tests.conftest import (
    EXPECTED_INVOICE_NUMBER, EXPECTED_ISSUE_DATE_STR, EXPECTED_SELLER_NAME, 
    EXPECTED_PAYABLE_AMOUNT, EXPECTED_IBAN
)

# --- UBL Mapping Tests ---

def test_map_ubl_success(minimal_ubl_bytes):
    """Testet das erfolgreiche Mapping eines minimalen UBL Beispiels."""
    invoice = map_xml_to_canonical(minimal_ubl_bytes, InvoiceFormat.XRECHNUNG_UBL)

    # Prüfe Schlüsselwerte
    assert invoice.invoice_number == EXPECTED_INVOICE_NUMBER
    assert invoice.issue_date.isoformat() == EXPECTED_ISSUE_DATE_STR
    assert invoice.payable_amount == EXPECTED_PAYABLE_AMOUNT
    assert invoice.seller.name == EXPECTED_SELLER_NAME
    assert invoice.payment_details[0].iban == EXPECTED_IBAN
    assert len(invoice.lines) == 1

def test_map_ubl_missing_mandatory_field(minimal_ubl_bytes):
    """Testet MappingError, wenn ein Pflichtfeld fehlt."""
    # Manipuliere XML, um die Rechnungsnummer zu entfernen
    xml_str = minimal_ubl_bytes.decode('utf-8')
    xml_str = xml_str.replace(f'<cbc:ID>{EXPECTED_INVOICE_NUMBER}</cbc:ID>', '')
    manipulated_bytes = xml_str.encode('utf-8')

    with pytest.raises(MappingError) as excinfo:
        map_xml_to_canonical(manipulated_bytes, InvoiceFormat.XRECHNUNG_UBL)
    
    # Prüfe, ob die Fehlermeldung den XPath (cbc:ID) enthält
    assert "cbc:ID" in str(excinfo.value)


# --- CII Mapping Tests ---

def test_map_cii_success(minimal_cii_bytes):
    """Testet das erfolgreiche Mapping eines minimalen CII Beispiels."""
    invoice = map_xml_to_canonical(minimal_cii_bytes, InvoiceFormat.XRECHNUNG_CII)

    # Prüfe Schlüsselwerte
    assert invoice.invoice_number == EXPECTED_INVOICE_NUMBER
    assert invoice.payable_amount == EXPECTED_PAYABLE_AMOUNT
    assert invoice.seller.name == EXPECTED_SELLER_NAME
    assert invoice.payment_details[0].iban == EXPECTED_IBAN

def test_map_cii_invalid_date_format(minimal_cii_bytes):
    """Testet Fehlerbehandlung bei ungültigem Datumsformat (CII erwartet YYYYMMDD für Format 102)."""
    xml_str = minimal_cii_bytes.decode('utf-8')
    # Ändere Datum von 20250910 zu 2025-09-10
    xml_str = xml_str.replace('20250910', '2025-09-10')
    manipulated_bytes = xml_str.encode('utf-8')

    with pytest.raises(MappingError) as excinfo:
        map_xml_to_canonical(manipulated_bytes, InvoiceFormat.XRECHNUNG_CII)
    
    assert "Ungültiges Datumsformat" in str(excinfo.value)
