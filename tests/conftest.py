# tests/conftest.py
import pytest
from pypdf import PdfWriter
import io
import os
from decimal import Decimal
from unittest.mock import MagicMock

# Setze Umgebungsvariablen für Tests, um externe Abhängigkeiten zu simulieren
os.environ['ENVIRONMENT'] = 'testing'
os.environ['DATABASE_URL'] = 'sqlite:///:memory:'
os.environ['ERP_DATABASE_URL'] = 'sqlite:///:memory:'
os.environ['AZURE_STORAGE_CONNECTION_STRING'] = 'DefaultEndpointsProtocol=http;AccountName=test;AccountKey=testkey;'
os.environ['CELERY_BROKER_URL'] = 'memory://'
os.environ['CELERY_RESULT_BACKEND'] = 'cache+memory://'
os.environ["EMAIL_INGESTION_ENABLED"] = "False"

# ------------------------------------------------------------------------
# Mock XML Daten und Erwartete Werte
# ------------------------------------------------------------------------

EXPECTED_INVOICE_NUMBER = "R-TEST-2025-001"
EXPECTED_ISSUE_DATE_STR = "2025-09-10"
EXPECTED_SELLER_NAME = "Test Seller GmbH"
EXPECTED_BUYER_NAME = "Test Buyer AG"
EXPECTED_PAYABLE_AMOUNT = Decimal("119.00")
EXPECTED_TAX_AMOUNT = Decimal("19.00")
EXPECTED_NET_AMOUNT = Decimal("100.00")
EXPECTED_IBAN = "DE987654321012345678"

MINIMAL_UBL_XML = f"""<?xml version="1.0" encoding="UTF-8"?>
<Invoice xmlns="urn:oasis:names:specification:ubl:schema:xsd:Invoice-2"
         xmlns:cac="urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2"
         xmlns:cbc="urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2">
    <cbc:ID>{EXPECTED_INVOICE_NUMBER}</cbc:ID>
    <cbc:IssueDate>{EXPECTED_ISSUE_DATE_STR}</cbc:IssueDate>
    <cbc:InvoiceTypeCode>380</cbc:InvoiceTypeCode>
    <cbc:DocumentCurrencyCode>EUR</cbc:DocumentCurrencyCode>
    <cac:AccountingSupplierParty>
        <cac:Party>
            <cac:PartyName><cbc:Name>{EXPECTED_SELLER_NAME}</cbc:Name></cac:PartyName>
            <cac:PostalAddress>
                <cbc:CityName>Berlin</cbc:CityName><cbc:PostalZone>10115</cbc:PostalZone>
                <cac:Country><cbc:IdentificationCode>DE</cbc:IdentificationCode></cac:Country>
            </cac:PostalAddress>
            <cac:PartyTaxScheme>
                <cbc:CompanyID>DE123456789</cbc:CompanyID>
                <cac:TaxScheme><cbc:ID>VAT</cbc:ID></cac:TaxScheme>
            </cac:PartyTaxScheme>
        </cac:Party>
    </cac:AccountingSupplierParty>
    <cac:AccountingCustomerParty>
        <cac:Party>
            <cac:PartyName><cbc:Name>{EXPECTED_BUYER_NAME}</cbc:Name></cac:PartyName>
            <cac:PostalAddress>
                <cbc:CityName>Munich</cbc:CityName><cbc:PostalZone>80331</cbc:PostalZone>
                <cac:Country><cbc:IdentificationCode>DE</cbc:IdentificationCode></cac:Country>
            </cac:PostalAddress>
        </cac:Party>
    </cac:AccountingCustomerParty>
    <cac:PaymentMeans>
        <cbc:PaymentMeansCode>30</cbc:PaymentMeansCode>
        <cac:PayeeFinancialAccount><cbc:ID>{EXPECTED_IBAN}</cbc:ID></cac:PayeeFinancialAccount>
    </cac:PaymentMeans>
    <cac:TaxTotal>
        <cbc:TaxAmount currencyID="EUR">19.00</cbc:TaxAmount>
        <cac:TaxSubtotal>
            <cbc:TaxableAmount currencyID="EUR">100.00</cbc:TaxableAmount>
            <cbc:TaxAmount currencyID="EUR">19.00</cbc:TaxAmount>
            <cac:TaxCategory>
                <cbc:ID>S</cbc:ID><cbc:Percent>19.00</cbc:Percent>
                <cac:TaxScheme><cbc:ID>VAT</cbc:ID></cac:TaxScheme>
            </cac:TaxCategory>
        </cac:TaxSubtotal>
    </cac:TaxTotal>
    <cac:LegalMonetaryTotal>
        <cbc:LineExtensionAmount currencyID="EUR">100.00</cbc:LineExtensionAmount>
        <cbc:TaxExclusiveAmount currencyID="EUR">100.00</cbc:TaxExclusiveAmount>
        <cbc:TaxInclusiveAmount currencyID="EUR">119.00</cbc:TaxInclusiveAmount>
        <cbc:PayableAmount currencyID="EUR">119.00</cbc:PayableAmount>
    </cac:LegalMonetaryTotal>
    <cac:InvoiceLine>
        <cbc:ID>1</cbc:ID>
        <cbc:InvoicedQuantity unitCode="C62">1.00</cbc:InvoicedQuantity>
        <cbc:LineExtensionAmount currencyID="EUR">100.00</cbc:LineExtensionAmount>
        <cac:Item>
            <cbc:Name>Test Product</cbc:Name>
            <cac:ClassifiedTaxCategory>
                <cbc:ID>S</cbc:ID><cbc:Percent>19.00</cbc:Percent>
                <cac:TaxScheme><cbc:ID>VAT</cbc:ID></cac:TaxScheme>
            </cac:ClassifiedTaxCategory>
        </cac:Item>
        <cac:Price><cbc:PriceAmount currencyID="EUR">100.00</cbc:PriceAmount><cbc:BaseQuantity>1.00</cbc:BaseQuantity></cac:Price>
    </cac:InvoiceLine>
</Invoice>
"""

MINIMAL_CII_XML = f"""<?xml version="1.0" encoding="UTF-8"?>
<rsm:CrossIndustryInvoice xmlns:rsm="urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100"
                          xmlns:ram="urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100"
                          xmlns:udt="urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100">
    <rsm:ExchangedDocument>
        <ram:ID>{EXPECTED_INVOICE_NUMBER}</ram:ID>
        <ram:TypeCode>380</ram:TypeCode>
        <ram:IssueDateTime><udt:DateTimeString format="102">20250910</udt:DateTimeString></ram:IssueDateTime>
    </rsm:ExchangedDocument>
    <rsm:SupplyChainTradeTransaction>
        <ram:IncludedSupplyChainTradeLineItem>
            <ram:AssociatedDocumentLineDocument><ram:LineID>1</ram:LineID></ram:AssociatedDocumentLineDocument>
            <ram:SpecifiedTradeProduct><ram:Name>Test Product CII</ram:Name></ram:SpecifiedTradeProduct>
            <ram:SpecifiedLineTradeAgreement>
                <ram:NetPriceProductTradePrice><ram:ChargeAmount>100.00</ram:ChargeAmount><ram:BasisQuantity>1.00</ram:BasisQuantity></ram:NetPriceProductTradePrice>
            </ram:SpecifiedLineTradeAgreement>
            <ram:SpecifiedLineTradeDelivery><ram:BilledQuantity unitCode="C62">1.00</ram:BilledQuantity></ram:SpecifiedLineTradeDelivery>
            <ram:SpecifiedLineTradeSettlement>
                <ram:ApplicableTradeTax><ram:TypeCode>VAT</ram:TypeCode><ram:CategoryCode>S</ram:CategoryCode><ram:RateApplicablePercent>19.00</ram:RateApplicablePercent></ram:ApplicableTradeTax>
                <ram:SpecifiedTradeSettlementLineMonetarySummation><ram:LineTotalAmount>100.00</ram:LineTotalAmount></ram:SpecifiedTradeSettlementLineMonetarySummation>
            </ram:SpecifiedLineTradeSettlement>
        </ram:IncludedSupplyChainTradeLineItem>
        <ram:ApplicableHeaderTradeAgreement>
            <ram:SellerTradeParty>
                <ram:Name>{EXPECTED_SELLER_NAME}</ram:Name>
                <ram:PostalTradeAddress><ram:PostcodeCode>10115</ram:PostcodeCode><ram:CityName>Berlin</ram:CityName><ram:CountryID>DE</ram:CountryID></ram:PostalTradeAddress>
                <ram:SpecifiedTaxRegistration><ram:ID schemeID="VA">DE123456789</ram:ID></ram:SpecifiedTaxRegistration>
            </ram:SellerTradeParty>
            <ram:BuyerTradeParty>
                <ram:Name>{EXPECTED_BUYER_NAME}</ram:Name>
                <ram:PostalTradeAddress><ram:PostcodeCode>80331</ram:PostcodeCode><ram:CityName>Munich</ram:CityName><ram:CountryID>DE</ram:CountryID></ram:PostalTradeAddress>
            </ram:BuyerTradeParty>
        </ram:ApplicableHeaderTradeAgreement>
        <ram:ApplicableHeaderTradeSettlement>
            <ram:InvoiceCurrencyCode>EUR</ram:InvoiceCurrencyCode>
            <ram:SpecifiedTradeSettlementPaymentMeans>
                <ram:TypeCode>30</ram:TypeCode>
                <ram:PayeePartyCreditorFinancialAccount><ram:IBANID>{EXPECTED_IBAN}</ram:IBANID></ram:PayeePartyCreditorFinancialAccount>
            </ram:SpecifiedTradeSettlementPaymentMeans>
            <ram:ApplicableTradeTax>
                <ram:CalculatedAmount>19.00</ram:CalculatedAmount><ram:TypeCode>VAT</ram:TypeCode>
                <ram:BasisAmount>100.00</ram:BasisAmount><ram:CategoryCode>S</ram:CategoryCode><ram:RateApplicablePercent>19.00</ram:RateApplicablePercent>
            </ram:ApplicableTradeTax>
            <ram:SpecifiedTradeSettlementHeaderMonetarySummation>
                <ram:LineTotalAmount>100.00</ram:LineTotalAmount><ram:TaxBasisTotalAmount>100.00</ram:TaxBasisTotalAmount>
                <ram:GrandTotalAmount>119.00</ram:GrandTotalAmount><ram:DuePayableAmount>119.00</ram:DuePayableAmount>
            </ram:SpecifiedTradeSettlementHeaderMonetarySummation>
        </ram:ApplicableHeaderTradeSettlement>
    </rsm:SupplyChainTradeTransaction>
</rsm:CrossIndustryInvoice>
"""

@pytest.fixture
def minimal_cii_bytes():
    return MINIMAL_CII_XML.encode('utf-8')

@pytest.fixture
def minimal_ubl_bytes():
    return MINIMAL_UBL_XML.encode('utf-8')

# ------------------------------------------------------------------------
# Mock PDF Generierung (ReportLab)
# ------------------------------------------------------------------------

def create_dummy_pdf() -> bytes:
    """Erstellt ein einfaches, valides PDF ohne Anhang."""
    buffer = io.BytesIO()
    writer = PdfWriter()
    # Ein PDF benötigt mindestens eine Seite
    writer.add_blank_page(width=595, height=842) # A4 Größe
    writer.write(buffer)
    return buffer.getvalue()

def create_mock_zugferd_pdf(xml_content: bytes, filename: str = "factur-x.xml") -> bytes:
    """
    Erstellt ein Mock ZUGFeRD/Factur-X PDF mit eingebettetem XML mittels pypdf.
    """
    buffer = io.BytesIO()
    writer = PdfWriter()
    writer.add_blank_page(width=595, height=842)
    
    # XML-Datei einbetten mit pypdf (High-Level API)
    # Dies ersetzt die fehlerhafte reportlab Methode.
    writer.add_attachment(filename, xml_content)
    
    # Hinweis: Für vollständige PDF/A-3 Konformität wären mehr Metadaten nötig, 
    # aber für den Extraktions-Test reicht dies aus.

    writer.write(buffer)
    return buffer.getvalue()

# Die Fixtures, die diese Funktionen nutzen, bleiben unverändert:
@pytest.fixture
def dummy_pdf_bytes():
    return create_dummy_pdf()

@pytest.fixture
def valid_zugferd_bytes(minimal_cii_bytes):
    # ZUGFeRD verwendet CII XML
    return create_mock_zugferd_pdf(minimal_cii_bytes, "factur-x.xml")

# ------------------------------------------------------------------------
# Mocks für Integrationstests
# ------------------------------------------------------------------------

@pytest.fixture
def mock_db_session(mocker):
    """Mockt die Datenbank-Session."""
    # Erstellt Mocks für die Session und Query Objekte
    session = MagicMock()
    query = MagicMock()
    session.query.return_value = query
    
    # Mockt den Aufruf von get_metadata_session in processor.py
    # Stellt sicher, dass der Context Manager funktioniert
    mocker.patch('src.tasks.processor.get_metadata_session', return_value=session)
    session.__enter__.return_value = session
    return session, query

@pytest.fixture
def mock_sync_storage_service(mocker):
    """Mockt den SyncStorageService in processor.py."""
    mock_service = MagicMock()
    mocker.patch('src.tasks.processor.sync_storage_service', mock_service)
    return mock_service

# ------------------------------------------------------------------------
# Basisverzeichnis für Testdaten
# ------------------------------------------------------------------------

from pathlib import Path
from typing import List

# Definiere das Basisverzeichnis für Testdaten relativ zur conftest.py
TEST_DATA_DIR = Path(__file__).parent / "test_data" / "corpus"

def get_corpus_files(subdir: str) -> List[pytest.param]:
    """
    Hilfsfunktion zum Auflisten von Dateien in einem Corpus-Unterverzeichnis.
    Gibt eine Liste von pytest.param zurück, die für die Parametrisierung genutzt wird.
    """
    path = TEST_DATA_DIR / subdir
    if not path.exists():
        # Wenn das Verzeichnis nicht existiert (z.B. weil die Daten noch nicht heruntergeladen wurden)
        return []
    
    test_files = []
    # Liste von Pfaden zurückgeben und relative Pfade als IDs verwenden (für bessere Testberichte)
    for f in path.iterdir():
        if f.is_file() and f.suffix.lower() in ['.xml', '.pdf']:
            relative_path = f.relative_to(TEST_DATA_DIR)
            # pytest.param erlaubt es, eine ID für den Testfall festzulegen
            test_files.append(pytest.param(f, id=str(relative_path)))
            
    return test_files

# WICHTIG: Wir definieren die Listen direkt hier auf Modulebene, 
# damit Pytest sie während der Test-Discovery finden und parametrisieren kann.
UBL_CORPUS_FILES = get_corpus_files("ubl")
CII_CORPUS_FILES = get_corpus_files("cii")
ZUGFERD_CORPUS_FILES = get_corpus_files("zugferd")