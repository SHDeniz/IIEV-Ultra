# src/services/storage_service_sync.py

import logging
from azure.storage.blob import BlobServiceClient, BlobClient
from azure.core.exceptions import ResourceNotFoundError, AzureError
import hashlib
from datetime import datetime
import uuid
from typing import Optional

# Importiere die Settings aus Ihrer config.py
from ..core.config import settings

logger = logging.getLogger(__name__)

class SyncStorageService:
    """
    Synchroner Service für Azure Blob Storage Operationen.
    Speziell für die Verwendung in synchronen Celery Tasks.
    """
    
    def __init__(self):
        # Initialisierung basierend auf Ihrer Konfiguration (Connection String)
        if not settings.azure_storage_connection_string:
             raise ConnectionError("AZURE_STORAGE_CONNECTION_STRING ist nicht gesetzt.")
             
        self.blob_service_client = BlobServiceClient.from_connection_string(
            settings.azure_storage_connection_string
        )
        # Nutze die Namen aus Ihrer config.py
        self.raw_container_name = settings.blob_container_raw
        self.processed_container_name = settings.blob_container_processed

    def _get_blob_client_from_uri(self, uri: str) -> BlobClient:
        """Helper, um einen Client aus einem URI zu erstellen."""
        # Erstellt einen Client aus der URL unter Verwendung des Connection Strings für die Authentifizierung.
        return BlobClient.from_connection_string(
            conn_str=settings.azure_storage_connection_string,
            container_name=self._get_container_name_from_uri(uri),
            blob_name=self._get_blob_name_from_uri(uri)
        )

    def download_blob_by_uri(self, uri: str) -> bytes:
        """Lädt Daten anhand eines Blob Storage URI synchron herunter."""
        logger.debug(f"Lade Blob synchron herunter von: {uri}")

        try:
            blob_client = self._get_blob_client_from_uri(uri)
            # Synchroner Download
            stream = blob_client.download_blob()
            return stream.readall()
        except ResourceNotFoundError:
            logger.error(f"Blob nicht gefunden: {uri}")
            raise FileNotFoundError(f"Blob nicht gefunden: {uri}")
        except AzureError as e:
            logger.error(f"Azure Fehler beim synchronen Download: {e}")
            # Werfe IOError, damit Celery Retry greift
            raise IOError(f"Download fehlgeschlagen: {e}")

    def upload_processed_xml(
        self, 
        transaction_id: str | uuid.UUID,
        xml_content: bytes, 
        format_type: str
    ) -> str:
        """Lädt extrahiertes XML synchron hoch."""
        
        str_transaction_id = str(transaction_id)
        # Blob-Name gemäß der Konvention in Ihrem async Service: transaction_id/processed.xml
        blob_name = f"{str_transaction_id}/processed.xml"

        try:
            # Metadaten analog zu Ihrem async Service
            metadata = {
                "transaction_id": str_transaction_id,
                "format_type": format_type,
                "processing_timestamp": datetime.now().isoformat(),
                "content_hash": hashlib.sha256(xml_content).hexdigest(),
            }
            
            blob_client = self.blob_service_client.get_blob_client(
                container=self.processed_container_name, 
                blob=blob_name
            )
            # Synchroner Upload
            blob_client.upload_blob(xml_content, overwrite=True, content_type="application/xml", metadata=metadata)
            return blob_client.url
        except AzureError as e:
            logger.error(f"Azure Fehler beim synchronen Upload: {e}")
            raise IOError(f"Upload fehlgeschlagen: {e}")

    # Hilfsfunktionen zur Extraktion von Container/Blob Name aus URI
    def _get_container_name_from_uri(self, uri: str) -> str:
        # Simples Parsing der URL: https://account.blob.core.windows.net/container/blob...
        parts = uri.split('/')
        if len(parts) > 3:
            return parts[3]
        raise ValueError(f"Ungültiger Blob URI (Container): {uri}")

    def _get_blob_name_from_uri(self, uri: str) -> str:
        parts = uri.split('/')
        if len(parts) > 4:
            return '/'.join(parts[4:])
        raise ValueError(f"Ungültiger Blob URI (Blob): {uri}")

# Singleton Instanz für die Celery Worker
try:
    sync_storage_service = SyncStorageService()
except Exception as e:
    logger.warning(f"SyncStorageService konnte nicht initialisiert werden (z.B. während Build/Tests): {e}")
    sync_storage_service = None