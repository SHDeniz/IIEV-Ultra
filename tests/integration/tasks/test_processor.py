# tests/integration/tasks/test_processor.py
import pytest
import uuid
from decimal import Decimal
from src.tasks.processor import process_invoice_task
from src.db.models import InvoiceTransaction, TransactionStatus, InvoiceFormat
from src.services.mapping.xpath_util import MappingError
from unittest.mock import MagicMock

# Wir nutzen die Mocks (mock_db_session, mock_sync_storage_service) aus conftest.py

class TestProcessorWorkflow:

    def test_process_happy_path_ubl(self, mock_db_session, mock_sync_storage_service, minimal_ubl_bytes, mocker):
        """Testet den erfolgreichen Workflow für eine UBL Rechnung."""
        
        transaction_id = str(uuid.uuid4())
        session, query = mock_db_session
        
        # 1. Setup DB Mock: Simuliere eine eingehende Transaktion
        mock_transaction = InvoiceTransaction(
            id=transaction_id, 
            status=TransactionStatus.RECEIVED,
            storage_uri_raw="azure://raw/test.xml"
        )
        query.filter.return_value.first.return_value = mock_transaction

        # 2. Setup Storage Mock: Liefere das UBL XML zurück
        mock_sync_storage_service.download_blob_by_uri.return_value = minimal_ubl_bytes
        
        # 3. Setup Mapper Mock (Optional, aber schneller)
        # Wir können das Mapping auch laufen lassen, da das XML valide ist. Hier mocken wir es für Isolation.
        mock_canonical = MagicMock()
        mock_canonical.invoice_number = "R98765"
        mock_canonical.payable_amount = Decimal("100.00")
        # Patche den Aufruf im processor Modul
        mocker.patch('src.tasks.processor.map_xml_to_canonical', return_value=mock_canonical)

        # 4. Führe den Task aus
        result = process_invoice_task(transaction_id)

        # 5. Prüfe Ergebnisse
        # Der Status ist MANUAL_REVIEW, da die Validierung (Sprints 3-5) noch fehlt.
        assert result['status'] == TransactionStatus.MANUAL_REVIEW.value
        assert mock_transaction.status == TransactionStatus.MANUAL_REVIEW
        assert mock_transaction.format_detected == InvoiceFormat.XRECHNUNG_UBL
        
        # Prüfe Aufrufe
        mock_sync_storage_service.download_blob_by_uri.assert_called_with("azure://raw/test.xml")
        session.commit.assert_called()

    def test_process_mapping_error(self, mock_db_session, mock_sync_storage_service, minimal_ubl_bytes, mocker):
        """Testet den Workflow, wenn das Mapping fehlschlägt."""
        
        transaction_id = str(uuid.uuid4())
        session, query = mock_db_session
        mock_transaction = InvoiceTransaction(id=transaction_id, status=TransactionStatus.RECEIVED, storage_uri_raw="azure://raw/data.xml")
        query.filter.return_value.first.return_value = mock_transaction
        mock_sync_storage_service.download_blob_by_uri.return_value = minimal_ubl_bytes

        # Erzwinge einen Fehler im Mapper
        mocker.patch('src.tasks.processor.map_xml_to_canonical', side_effect=MappingError("Pflichtfeld fehlt"))

        # Führe den Task aus
        result = process_invoice_task(transaction_id)

        # Prüfe Ergebnisse
        assert result['status'] == TransactionStatus.INVALID.value
        assert mock_transaction.status == TransactionStatus.INVALID
        # Prüfe, ob der Fehler im Report enthalten ist (basierend auf dem Code in processor.py)
        assert "MAPPING_FAILED" in str(mock_transaction.validation_report)

    def test_process_unstructured_pdf(self, mock_db_session, mock_sync_storage_service, dummy_pdf_bytes):
        """Testet den Workflow für ein PDF ohne strukturierte Daten."""
        
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
