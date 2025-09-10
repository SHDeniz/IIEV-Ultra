"""
IIEV-Ultra Konfiguration
Pydantic Settings Management für alle Umgebungsvariablen
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    """Hauptkonfiguration für IIEV-Ultra"""

    # Pydantic V2 Konfiguration für Settings
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding='utf-8',
        # Standardmäßig False (case-insensitive), was bedeutet, dass 'environment' sowohl 'environment' als auch 'ENVIRONMENT' findet.
        case_sensitive=False, 
    )
    
    # Allgemeine Einstellungen
    app_name: str = "IIEV-Ultra"
    app_version: str = "0.1.0"
    environment: str = Field(default="development")
    debug: bool = Field(default=True)
    
    # API Einstellungen
    api_v1_prefix: str = "/api/v1"
    
    # Datenbank Konfiguration (Metadaten)
    database_url: str = Field(...)
    
    # ERP Datenbank Konfiguration (Read-Only)
    erp_database_url: str = Field(...)
    
    # Azure Storage
    azure_storage_connection_string: str = Field(...)
    blob_container_raw: str = Field(default="invoices-raw")
    blob_container_processed: str = Field(default="invoices-processed")
    
    # Azure Service Bus (für Produktion)
    azure_servicebus_connection_string: Optional[str] = Field(default=None)
    servicebus_queue_name: str = Field(default="invoice-processing")
    
    # Celery Konfiguration
    celery_broker_url: str = Field(...)
    celery_result_backend: str = Field(...)
    
    # KoSIT Validator Konfiguration
    kosit_validator_jar_path: str = Field(default="/app/assets/validator.jar")
    kosit_scenario_config_path: str = Field(default="/app/assets/scenarios.xml")
    kosit_timeout_seconds: int = Field(default=30)
    
    # XSD Schema Pfade
    xsd_ubl_path: str = Field(default="/app/assets/xsd/ubl")
    xsd_cii_path: str = Field(default="/app/assets/xsd/cii")
    
    # Validierung Einstellungen
    calculation_tolerance_euro: float = Field(default=0.02)
    max_file_size_mb: int = Field(default=10)
    
    # Security
    secret_key: str = Field(default="dev-secret-key-change-in-production")
    
    # Logging
    log_level: str = Field(default="INFO")
    
    # Azure Key Vault (für Produktion)
    azure_key_vault_url: Optional[str] = Field(default=None)
    
    # E-Mail Ingestion (IMAP)
    EMAIL_INGESTION_ENABLED: bool = Field(default=False)
    IMAP_HOST: Optional[str] = Field(default=None)
    IMAP_PORT: int = Field(default=993)
    IMAP_USERNAME: Optional[str] = Field(default=None)
    IMAP_PASSWORD: Optional[str] = Field(default=None)
    IMAP_FOLDER_INBOX: str = Field(default="INBOX")
    # Ordner zum Verschieben nach Verarbeitung
    IMAP_FOLDER_ARCHIVE: str = Field(default="INBOX/Archive")
    IMAP_FOLDER_ERROR: str = Field(default="INBOX/Error")


# Globale Settings Instanz
settings = Settings()
