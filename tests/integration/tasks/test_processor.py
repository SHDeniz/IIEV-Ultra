# tests/integration/tasks/test_processor.py (Vollständig aktualisiert)
import pytest
import uuid
from decimal import Decimal
from datetime import date
from src.tasks.processor import process_invoice_task
from src.db.models import InvoiceTransaction, TransactionStatus, InvoiceFormat
from src.services.mapping.xpath_util import MappingError
from unittest.mock import MagicMock

# Importiere ValidationError, um Fehler simulieren zu können
from src.schemas.validation_report import ValidationError, ValidationCategory, ValidationSeverity

# Wir nutzen die Mocks (mock_db_session, mock_sync_storage_service) aus conftest.py

class TestProcessorWorkflow:

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Mockt alle Validierungsfunktionen und das Mapping für Workflow-Tests."""
        # Mocke XSD, KoSIT und Calculation, um JRE/Asset Abhängigkeiten zu entfernen.
        self.mock_xsd = mocker.patch('src.tasks.processor.validate_xsd', return_value=[])
        self.mock_kosit = mocker.patch('src.tasks.processor.validate_kosit_schematron', return_value=[])
        self.mock_calc = mocker.patch('src.tasks.processor.validate_calculations', return_value=[])
        # Mocke auch das Mapping.
        self.mock_mapper = mocker.patch('src.tasks.processor.map_xml_to_canonical')

    def test_process_happy_path_ubl(self, mock_db_session, mock_sync_storage_service, minimal_ubl_bytes):
        """Testet den erfolgreichen Workflow (VALID) wenn keine Fehler von Mocks gemeldet werden."""
        
        transaction_id = str(uuid.uuid4())
        session, query = mock_db_session
        
        # 1. Setup DB Mock
        mock_transaction = InvoiceTransaction(
            id=transaction_id, 
            status=TransactionStatus.RECEIVED,
            storage_uri_raw="azure://raw/test.xml"
        )
        query.filter.return_value.first.return_value = mock_transaction

        # 2. Setup Storage Mock
        mock_sync_storage_service.download_blob_by_uri.return_value = minimal_ubl_bytes
        
        # 3. Setup Mapper Mock (Stelle sicher, dass alle notwendigen Attribute vorhanden sind)
        mock_canonical = MagicMock()
        mock_canonical.invoice_number = "R98765"
        mock_canonical.payable_amount = Decimal("100.00")
        mock_canonical.currency_code = MagicMock(value="EUR") # Mock Enum access
        mock_canonical.issue_date = date(2025, 9, 11)
        mock_canonical.seller = MagicMock(name="Seller", vat_id="DE123")
        mock_canonical.buyer = MagicMock(name="Buyer", vat_id="DE456")
        mock_canonical.purchase_order_reference = None
        
        self.mock_mapper.return_value = mock_canonical

        # 4. Führe den Task aus
        result = process_invoice_task(transaction_id)

        # 5. Prüfe Ergebnisse
        # Da alle Validierungen gemockt sind und keine Fehler zurückgeben, sollte der Status VALID sein.
        assert result['status'] == TransactionStatus.VALID.value
        assert mock_transaction.status == TransactionStatus.VALID
        
        # Prüfe, ob alle Schritte aufgerufen wurden
        self.mock_xsd.assert_called()
        self.mock_kosit.assert_called()
        self.mock_mapper.assert_called()
        self.mock_calc.assert_called()

    def test_process_validation_error_flow(self, mock_db_session, mock_sync_storage_service, minimal_ubl_bytes):
        """Testet den Workflow (INVALID), wenn eine Validierung einen Fehler meldet."""
        
        transaction_id = str(uuid.uuid4())
        session, query = mock_db_session
        mock_transaction = InvoiceTransaction(id=transaction_id, status=TransactionStatus.RECEIVED, storage_uri_raw="azure://raw/test.xml")
        query.filter.return_value.first.return_value = mock_transaction
        mock_sync_storage_service.download_blob_by_uri.return_value = minimal_ubl_bytes

        # Simuliere einen Fehler bei der KoSIT Validierung
        self.mock_kosit.return_value = [
            ValidationError(category=ValidationCategory.SEMANTIC, severity=ValidationSeverity.ERROR, message="Test Error", code="TEST-1")
        ]

        # Führe den Task aus
        result = process_invoice_task(transaction_id)

        # Prüfe Ergebnisse
        assert result['status'] == TransactionStatus.INVALID.value
        
        # Prüfe, dass das Mapping NICHT aufgerufen wurde, da KoSIT vorher fehlschlug
        self.mock_mapper.assert_not_called()

    def test_process_mapping_error(self, mock_db_session, mock_sync_storage_service, minimal_ubl_bytes):
        """Testet den Workflow (INVALID), wenn das Mapping fehlschlägt."""
        
        transaction_id = str(uuid.uuid4())
        session, query = mock_db_session
        mock_transaction = InvoiceTransaction(id=transaction_id, status=TransactionStatus.RECEIVED, storage_uri_raw="azure://raw/data.xml")
        query.filter.return_value.first.return_value = mock_transaction
        mock_sync_storage_service.download_blob_by_uri.return_value = minimal_ubl_bytes

        # Erzwinge einen Fehler im Mapper
        # (XSD und KoSIT sind bereits durch das setup_mocks Fixture als erfolgreich gemockt)
        self.mock_mapper.side_effect = MappingError("Pflichtfeld fehlt")

        # Führe den Task aus
        result = process_invoice_task(transaction_id)

        # Prüfe Ergebnisse
        assert result['status'] == TransactionStatus.INVALID.value
        assert "MAPPING_FAILED" in str(mock_transaction.validation_report)
        
        # Prüfe, dass Calculation NICHT aufgerufen wurde, da Mapping fehlschlug
        self.mock_calc.assert_not_called()

    def test_process_unstructured_pdf(self, mock_db_session, mock_sync_storage_service, dummy_pdf_bytes):
        """Testet den Workflow (MANUAL_REVIEW) für ein PDF ohne strukturierte Daten."""
        
        transaction_id = str(uuid.uuid4())
        session, query = mock_db_session
        mock_transaction = InvoiceTransaction(id=transaction_id, status=TransactionStatus.RECEIVED, storage_uri_raw="azure://raw/simple.pdf")
        query.filter.return_value.first.return_value = mock_transaction
        mock_sync_storage_service.download_blob_by_uri.return_value = dummy_pdf_bytes

        # Führe den Task aus
        result = process_invoice_task(transaction_id)

        # Prüfe Ergebnisse
        assert result['status'] == TransactionStatus.MANUAL_REVIEW.value
        assert mock_transaction.format_detected == InvoiceFormat.OTHER_PDF
        
        # Prüfe, dass keine Validierung oder Mapping versucht wurde
        self.mock_xsd.assert_not_called()
        self.mock_mapper.assert_not_called()

    def test_process_idempotency(self, mock_db_session, mock_sync_storage_service):
        """Testet, ob der Task übersprungen wird, wenn er bereits läuft."""
        transaction_id = str(uuid.uuid4())
        session, query = mock_db_session
        
        # Simuliere Status PROCESSING
        mock_transaction = InvoiceTransaction(id=transaction_id, status=TransactionStatus.PROCESSING)
        query.filter.return_value.first.return_value = mock_transaction

        result = process_invoice_task(transaction_id)

        assert result['status'] == "skipped"
        mock_sync_storage_service.download_blob_by_uri.assert_not_called()