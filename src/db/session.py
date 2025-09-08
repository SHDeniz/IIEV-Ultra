"""
Datenbank Session Management
Getrennte Sessions für Metadaten-DB und ERP-DB
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool
from contextlib import contextmanager
from typing import Generator
import logging

from ..core.config import settings

logger = logging.getLogger(__name__)

# Metadaten-Datenbank Engine (PostgreSQL/Azure SQL)
metadata_engine = create_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,
    pool_recycle=3600,
)

# ERP-Datenbank Engine (MSSQL - Read Only)
erp_engine = create_engine(
    settings.erp_database_url,
    echo=settings.debug,
    pool_pre_ping=True,
    pool_recycle=3600,
    poolclass=NullPool,  # Keine Connection Pooling für ERP DB
)

# Session Factories
MetadataSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=metadata_engine)
ERPSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=erp_engine)


@contextmanager
def get_metadata_session() -> Generator[Session, None, None]:
    """
    Context Manager für Metadaten-Datenbank Sessions
    Automatisches Rollback bei Fehlern
    """
    session = MetadataSessionLocal()
    try:
        yield session
        session.commit()
    except Exception as e:
        logger.error(f"Datenbank-Fehler in Metadaten-Session: {e}")
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def get_erp_session() -> Generator[Session, None, None]:
    """
    Context Manager für ERP-Datenbank Sessions (Read-Only)
    """
    session = ERPSessionLocal()
    try:
        yield session
        # Keine Commits für Read-Only ERP Session
    except Exception as e:
        logger.error(f"Datenbank-Fehler in ERP-Session: {e}")
        session.rollback()
        raise
    finally:
        session.close()


def get_metadata_session_dependency() -> Generator[Session, None, None]:
    """
    Dependency für FastAPI Dependency Injection
    """
    with get_metadata_session() as session:
        yield session


def get_erp_session_dependency() -> Generator[Session, None, None]:
    """
    Dependency für FastAPI Dependency Injection (ERP)
    """
    with get_erp_session() as session:
        yield session


def health_check_databases() -> dict:
    """
    Gesundheitsprüfung beider Datenbanken
    """
    health = {
        "metadata_db": False,
        "erp_db": False
    }
    
    # Test Metadaten-DB
    try:
        with get_metadata_session() as session:
            session.execute("SELECT 1")
            health["metadata_db"] = True
            logger.info("Metadaten-DB Verbindung erfolgreich")
    except Exception as e:
        logger.error(f"Metadaten-DB Verbindungsfehler: {e}")
    
    # Test ERP-DB
    try:
        with get_erp_session() as session:
            session.execute("SELECT 1")
            health["erp_db"] = True
            logger.info("ERP-DB Verbindung erfolgreich")
    except Exception as e:
        logger.error(f"ERP-DB Verbindungsfehler: {e}")
    
    return health
