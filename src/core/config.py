"""
IIEV-Ultra Konfiguration
Pydantic Settings Management für alle Umgebungsvariablen
"""

from pydantic import Field
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Hauptkonfiguration für IIEV-Ultra"""
    
    # Allgemeine Einstellungen
    app_name: str = "IIEV-Ultra"
    app_version: str = "0.1.0"
    environment: str = Field(default="development", env="ENVIRONMENT")
    debug: bool = Field(default=True, env="DEBUG")
    
    # API Einstellungen
    api_v1_prefix: str = "/api/v1"
    
    # Datenbank Konfiguration (Metadaten)
    database_url: str = Field(..., env="DATABASE_URL")
    
    # ERP Datenbank Konfiguration (Read-Only)
    erp_database_url: str = Field(..., env="ERP_DATABASE_URL")
    
    # Azure Storage
    azure_storage_connection_string: str = Field(..., env="AZURE_STORAGE_CONNECTION_STRING")
    blob_container_raw: str = Field(default="invoices-raw", env="BLOB_CONTAINER_RAW")
    blob_container_processed: str = Field(default="invoices-processed", env="BLOB_CONTAINER_PROCESSED")
    
    # Azure Service Bus (für Produktion)
    azure_servicebus_connection_string: Optional[str] = Field(default=None, env="AZURE_SERVICEBUS_CONNECTION_STRING")
    servicebus_queue_name: str = Field(default="invoice-processing", env="SERVICEBUS_QUEUE_NAME")
    
    # Celery Konfiguration
    celery_broker_url: str = Field(..., env="CELERY_BROKER_URL")
    celery_result_backend: str = Field(..., env="CELERY_RESULT_BACKEND")
    
    # KoSIT Validator Konfiguration
    kosit_validator_jar_path: str = Field(default="/app/assets/validator.jar", env="KOSIT_VALIDATOR_JAR_PATH")
    kosit_scenario_config_path: str = Field(default="/app/assets/scenarios.xml", env="KOSIT_SCENARIO_CONFIG_PATH")
    kosit_timeout_seconds: int = Field(default=30, env="KOSIT_TIMEOUT_SECONDS")
    
    # XSD Schema Pfade
    xsd_ubl_path: str = Field(default="/app/assets/xsd/ubl", env="XSD_UBL_PATH")
    xsd_cii_path: str = Field(default="/app/assets/xsd/cii", env="XSD_CII_PATH")
    
    # Validierung Einstellungen
    calculation_tolerance_euro: float = Field(default=0.02, env="CALCULATION_TOLERANCE_EURO")
    max_file_size_mb: int = Field(default=10, env="MAX_FILE_SIZE_MB")
    
    # Security
    secret_key: str = Field(default="dev-secret-key-change-in-production", env="SECRET_KEY")
    
    # Logging
    log_level: str = Field(default="INFO", env="LOG_LEVEL")
    
    # Azure Key Vault (für Produktion)
    azure_key_vault_url: Optional[str] = Field(default=None, env="AZURE_KEY_VAULT_URL")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Globale Settings Instanz
settings = Settings()
