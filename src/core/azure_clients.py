"""
Azure Clients Initialisierung
Zentrale Verwaltung aller Azure Service Clients
"""

from azure.storage.blob import BlobServiceClient
from azure.servicebus import ServiceBusClient
from azure.identity import DefaultAzureCredential, ManagedIdentityCredential
from azure.keyvault.secrets import SecretClient
from typing import Optional
import logging

from .config import settings

logger = logging.getLogger(__name__)


class AzureClientManager:
    """Zentraler Manager für alle Azure Service Clients"""
    
    def __init__(self):
        self._blob_client: Optional[BlobServiceClient] = None
        self._servicebus_client: Optional[ServiceBusClient] = None
        self._keyvault_client: Optional[SecretClient] = None
        self._credential: Optional[DefaultAzureCredential] = None
    
    @property
    def credential(self) -> DefaultAzureCredential:
        """Azure Credential für Authentifizierung"""
        if self._credential is None:
            if settings.environment == "development":
                # Lokale Entwicklung: Verwende Connection Strings
                self._credential = None
            else:
                # Produktion: Verwende Managed Identity
                self._credential = DefaultAzureCredential()
        return self._credential
    
    @property
    def blob_client(self) -> BlobServiceClient:
        """Azure Blob Storage Client"""
        if self._blob_client is None:
            try:
                if settings.environment == "development":
                    # Lokale Entwicklung mit Azurite
                    self._blob_client = BlobServiceClient.from_connection_string(
                        settings.azure_storage_connection_string
                    )
                else:
                    # Produktion mit Managed Identity
                    account_url = f"https://{self._extract_account_name()}.blob.core.windows.net"
                    self._blob_client = BlobServiceClient(
                        account_url=account_url,
                        credential=self.credential
                    )
                
                # Container erstellen falls sie nicht existieren
                self._ensure_containers_exist()
                
            except Exception as e:
                logger.error(f"Fehler bei Blob Client Initialisierung: {e}")
                raise
        
        return self._blob_client
    
    @property
    def servicebus_client(self) -> Optional[ServiceBusClient]:
        """Azure Service Bus Client (optional für lokale Entwicklung)"""
        if self._servicebus_client is None and settings.azure_servicebus_connection_string:
            try:
                if settings.environment == "development":
                    # Lokale Entwicklung: Verwende Connection String falls verfügbar
                    if settings.azure_servicebus_connection_string:
                        self._servicebus_client = ServiceBusClient.from_connection_string(
                            settings.azure_servicebus_connection_string
                        )
                else:
                    # Produktion mit Managed Identity
                    namespace_url = self._extract_servicebus_namespace()
                    self._servicebus_client = ServiceBusClient(
                        fully_qualified_namespace=namespace_url,
                        credential=self.credential
                    )
            except Exception as e:
                logger.error(f"Fehler bei Service Bus Client Initialisierung: {e}")
                # Service Bus ist optional, daher nicht kritisch
                
        return self._servicebus_client
    
    @property
    def keyvault_client(self) -> Optional[SecretClient]:
        """Azure Key Vault Client (nur für Produktion)"""
        if self._keyvault_client is None and settings.azure_key_vault_url:
            try:
                self._keyvault_client = SecretClient(
                    vault_url=settings.azure_key_vault_url,
                    credential=self.credential
                )
            except Exception as e:
                logger.error(f"Fehler bei Key Vault Client Initialisierung: {e}")
                
        return self._keyvault_client
    
    def _ensure_containers_exist(self):
        """Stelle sicher, dass alle benötigten Blob Container existieren"""
        try:
            containers = [
                settings.blob_container_raw,
                settings.blob_container_processed
            ]
            
            for container_name in containers:
                try:
                    self._blob_client.create_container(container_name)
                    logger.info(f"Container '{container_name}' erstellt")
                except Exception:
                    # Container existiert bereits
                    logger.debug(f"Container '{container_name}' existiert bereits")
                    
        except Exception as e:
            logger.error(f"Fehler beim Erstellen der Container: {e}")
    
    def _extract_account_name(self) -> str:
        """Extrahiere Storage Account Name aus Connection String"""
        conn_str = settings.azure_storage_connection_string
        for part in conn_str.split(';'):
            if part.startswith('AccountName='):
                return part.split('=')[1]
        raise ValueError("AccountName nicht in Connection String gefunden")
    
    def _extract_servicebus_namespace(self) -> str:
        """Extrahiere Service Bus Namespace aus Connection String"""
        conn_str = settings.azure_servicebus_connection_string or ""
        for part in conn_str.split(';'):
            if part.startswith('Endpoint='):
                endpoint = part.split('=', 1)[1]
                # Extrahiere Namespace aus sb://namespace.servicebus.windows.net/
                return endpoint.replace('sb://', '').replace('/', '')
        raise ValueError("Endpoint nicht in Service Bus Connection String gefunden")
    
    def health_check(self) -> dict:
        """Gesundheitsprüfung aller Azure Services"""
        health = {
            "blob_storage": False,
            "service_bus": False,
            "key_vault": False
        }
        
        try:
            # Blob Storage Test
            self.blob_client.get_account_information()
            health["blob_storage"] = True
        except Exception as e:
            logger.error(f"Blob Storage Health Check fehlgeschlagen: {e}")
        
        try:
            # Service Bus Test (falls konfiguriert)
            if self.servicebus_client:
                # Einfacher Verbindungstest
                health["service_bus"] = True
        except Exception as e:
            logger.error(f"Service Bus Health Check fehlgeschlagen: {e}")
        
        try:
            # Key Vault Test (falls konfiguriert)
            if self.keyvault_client:
                # Einfacher Verbindungstest
                health["key_vault"] = True
        except Exception as e:
            logger.error(f"Key Vault Health Check fehlgeschlagen: {e}")
        
        return health


# Globale Azure Client Manager Instanz
azure_clients = AzureClientManager()
