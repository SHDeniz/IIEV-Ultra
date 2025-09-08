"""
Azure Blob Storage Service
Abstraktion für alle Storage-Operationen
"""

from azure.storage.blob import BlobServiceClient, BlobClient
from azure.core.exceptions import AzureError
import logging
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
import hashlib

from ..core.azure_clients import azure_clients
from ..core.config import settings

logger = logging.getLogger(__name__)


class StorageService:
    """Service für Azure Blob Storage Operationen"""
    
    def __init__(self):
        self.blob_client = azure_clients.blob_client
    
    async def upload_raw_file(
        self, 
        transaction_id: str, 
        filename: str, 
        content: bytes, 
        content_type: str
    ) -> str:
        """
        Lade Rohdatei in den Raw-Container hoch
        
        Args:
            transaction_id: Eindeutige Transaction ID
            filename: Originaler Dateiname
            content: Dateiinhalt als Bytes
            content_type: MIME-Type der Datei
            
        Returns:
            Blob URI der hochgeladenen Datei
        """
        
        try:
            # Blob-Name generieren: transaction_id/original_filename
            blob_name = f"{transaction_id}/{filename}"
            
            # Content Hash für Integrität
            content_hash = hashlib.sha256(content).hexdigest()
            
            # Metadaten setzen
            metadata = {
                "transaction_id": transaction_id,
                "original_filename": filename,
                "upload_timestamp": datetime.now().isoformat(),
                "content_hash": content_hash,
                "file_size_bytes": str(len(content))
            }
            
            # Blob hochladen
            blob_client = self.blob_client.get_blob_client(
                container=settings.blob_container_raw,
                blob=blob_name
            )
            
            blob_client.upload_blob(
                data=content,
                content_type=content_type,
                metadata=metadata,
                overwrite=True  # Überschreiben falls bereits vorhanden
            )
            
            blob_uri = blob_client.url
            
            logger.info(f"📁 Raw-Datei hochgeladen: {blob_name} ({len(content)} bytes)")
            
            return blob_uri
            
        except AzureError as e:
            logger.error(f"❌ Azure Storage Fehler beim Upload von {filename}: {e}")
            raise Exception(f"Storage Upload fehlgeschlagen: {str(e)}")
        except Exception as e:
            logger.error(f"❌ Unerwarteter Fehler beim Upload von {filename}: {e}")
            raise
    
    async def upload_processed_xml(
        self, 
        transaction_id: str, 
        xml_content: bytes, 
        format_type: str
    ) -> str:
        """
        Lade extrahierte/verarbeitete XML-Datei hoch
        
        Args:
            transaction_id: Transaction ID
            xml_content: XML Inhalt als Bytes
            format_type: Erkanntes Format (z.B. "XRECHNUNG_UBL")
            
        Returns:
            Blob URI der XML-Datei
        """
        
        try:
            # Blob-Name: transaction_id/processed.xml
            blob_name = f"{transaction_id}/processed.xml"
            
            # Metadaten
            metadata = {
                "transaction_id": transaction_id,
                "format_type": format_type,
                "processing_timestamp": datetime.now().isoformat(),
                "content_hash": hashlib.sha256(xml_content).hexdigest(),
                "file_size_bytes": str(len(xml_content))
            }
            
            # Upload
            blob_client = self.blob_client.get_blob_client(
                container=settings.blob_container_processed,
                blob=blob_name
            )
            
            blob_client.upload_blob(
                data=xml_content,
                content_type="application/xml",
                metadata=metadata,
                overwrite=True
            )
            
            blob_uri = blob_client.url
            
            logger.info(f"📁 Verarbeitete XML hochgeladen: {blob_name} ({len(xml_content)} bytes)")
            
            return blob_uri
            
        except Exception as e:
            logger.error(f"❌ Fehler beim XML Upload für {transaction_id}: {e}")
            raise
    
    async def download_raw_file(self, transaction_id: str, filename: str) -> bytes:
        """
        Lade Rohdatei aus Storage herunter
        
        Args:
            transaction_id: Transaction ID
            filename: Originaler Dateiname
            
        Returns:
            Dateiinhalt als Bytes
        """
        
        try:
            blob_name = f"{transaction_id}/{filename}"
            
            blob_client = self.blob_client.get_blob_client(
                container=settings.blob_container_raw,
                blob=blob_name
            )
            
            download_stream = blob_client.download_blob()
            content = download_stream.readall()
            
            logger.info(f"📥 Raw-Datei heruntergeladen: {blob_name} ({len(content)} bytes)")
            
            return content
            
        except Exception as e:
            logger.error(f"❌ Fehler beim Download von {blob_name}: {e}")
            raise
    
    async def download_processed_xml(self, transaction_id: str) -> bytes:
        """
        Lade verarbeitete XML-Datei herunter
        """
        
        try:
            blob_name = f"{transaction_id}/processed.xml"
            
            blob_client = self.blob_client.get_blob_client(
                container=settings.blob_container_processed,
                blob=blob_name
            )
            
            download_stream = blob_client.download_blob()
            content = download_stream.readall()
            
            logger.info(f"📥 Verarbeitete XML heruntergeladen: {blob_name}")
            
            return content
            
        except Exception as e:
            logger.error(f"❌ Fehler beim XML Download für {transaction_id}: {e}")
            raise
    
    async def get_file_metadata(self, container: str, blob_name: str) -> Dict[str, Any]:
        """
        Hole Metadaten einer Datei
        """
        
        try:
            blob_client = self.blob_client.get_blob_client(
                container=container,
                blob=blob_name
            )
            
            properties = blob_client.get_blob_properties()
            
            return {
                "size_bytes": properties.size,
                "content_type": properties.content_settings.content_type,
                "last_modified": properties.last_modified.isoformat() if properties.last_modified else None,
                "etag": properties.etag,
                "metadata": properties.metadata or {}
            }
            
        except Exception as e:
            logger.error(f"❌ Fehler beim Abrufen der Metadaten für {blob_name}: {e}")
            raise
    
    async def delete_transaction_files(self, transaction_id: str) -> bool:
        """
        Lösche alle Dateien einer Transaction (Raw + Processed)
        ACHTUNG: Nur für Development/Testing verwenden!
        """
        
        try:
            deleted_count = 0
            
            # Raw Container durchsuchen
            raw_blobs = self.blob_client.get_container_client(
                settings.blob_container_raw
            ).list_blobs(name_starts_with=f"{transaction_id}/")
            
            for blob in raw_blobs:
                blob_client = self.blob_client.get_blob_client(
                    container=settings.blob_container_raw,
                    blob=blob.name
                )
                blob_client.delete_blob()
                deleted_count += 1
                logger.info(f"🗑️ Gelöscht: {blob.name}")
            
            # Processed Container durchsuchen
            processed_blobs = self.blob_client.get_container_client(
                settings.blob_container_processed
            ).list_blobs(name_starts_with=f"{transaction_id}/")
            
            for blob in processed_blobs:
                blob_client = self.blob_client.get_blob_client(
                    container=settings.blob_container_processed,
                    blob=blob.name
                )
                blob_client.delete_blob()
                deleted_count += 1
                logger.info(f"🗑️ Gelöscht: {blob.name}")
            
            logger.info(f"🗑️ {deleted_count} Dateien für Transaction {transaction_id} gelöscht")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Fehler beim Löschen der Dateien für {transaction_id}: {e}")
            return False
    
    async def generate_download_url(
        self, 
        container: str, 
        blob_name: str, 
        expiry_hours: int = 24
    ) -> str:
        """
        Generiere temporäre Download-URL mit SAS Token
        
        Args:
            container: Container Name
            blob_name: Blob Name
            expiry_hours: Gültigkeit in Stunden
            
        Returns:
            Temporäre Download-URL
        """
        
        try:
            from azure.storage.blob import generate_blob_sas, BlobSasPermissions
            from datetime import datetime, timedelta
            
            blob_client = self.blob_client.get_blob_client(
                container=container,
                blob=blob_name
            )
            
            # Entwicklung: Connection String basierte SAS
            if settings.environment == "development":
                # Account Key aus Connection String extrahieren
                account_key = self._extract_account_key_from_connection_string()
                if account_key:
                    sas_token = generate_blob_sas(
                        account_name=self.blob_client.account_name,
                        container_name=container,
                        blob_name=blob_name,
                        account_key=account_key,
                        permission=BlobSasPermissions(read=True),
                        expiry=datetime.utcnow() + timedelta(hours=expiry_hours)
                    )
                    
                    download_url = f"{blob_client.url}?{sas_token}"
                    logger.info(f"🔗 Development SAS URL generiert für {blob_name}")
                    return download_url
            
            # Produktion: User Delegation SAS (für Managed Identity)
            else:
                # User Delegation Key holen (erfordert Managed Identity mit entsprechenden Rechten)
                delegation_key = self.blob_client.get_user_delegation_key(
                    key_start_time=datetime.utcnow(),
                    key_expiry_time=datetime.utcnow() + timedelta(hours=expiry_hours)
                )
                
                sas_token = generate_blob_sas(
                    account_name=self.blob_client.account_name,
                    container_name=container,
                    blob_name=blob_name,
                    user_delegation_key=delegation_key,
                    permission=BlobSasPermissions(read=True),
                    expiry=datetime.utcnow() + timedelta(hours=expiry_hours)
                )
                
                download_url = f"{blob_client.url}?{sas_token}"
                logger.info(f"🔗 Production SAS URL generiert für {blob_name}")
                return download_url
            
            # Fallback: Direkte URL ohne SAS (nur für Development)
            logger.warning(f"⚠️ SAS-Generierung fehlgeschlagen, verwende direkte URL für {blob_name}")
            return blob_client.url
            
        except Exception as e:
            logger.error(f"❌ Fehler beim Generieren der Download-URL für {blob_name}: {e}")
            # Fallback: Direkte URL
            blob_client = self.blob_client.get_blob_client(container=container, blob=blob_name)
            return blob_client.url
    
    def _extract_account_key_from_connection_string(self) -> Optional[str]:
        """Extrahiere Account Key aus Azure Storage Connection String"""
        try:
            conn_str = settings.azure_storage_connection_string
            for part in conn_str.split(';'):
                if part.startswith('AccountKey='):
                    return part.split('=', 1)[1]
            return None
        except Exception as e:
            logger.error(f"Fehler beim Extrahieren des Account Keys: {e}")
            return None
    
    def health_check(self) -> Dict[str, Any]:
        """
        Storage Service Gesundheitsprüfung
        """
        
        health = {
            "blob_service": False,
            "containers": {
                "raw": False,
                "processed": False
            }
        }
        
        try:
            # Blob Service Test
            self.blob_client.get_account_information()
            health["blob_service"] = True
            
            # Container Tests
            for container_name in [settings.blob_container_raw, settings.blob_container_processed]:
                try:
                    container_client = self.blob_client.get_container_client(container_name)
                    container_client.get_container_properties()
                    health["containers"][container_name.replace("invoices-", "")] = True
                except Exception:
                    logger.warning(f"Container {container_name} nicht verfügbar")
            
        except Exception as e:
            logger.error(f"Storage Health Check fehlgeschlagen: {e}")
        
        return health
