"""
Health Check API Endpoints
Überwachung der System-Gesundheit
"""

from fastapi import APIRouter
from typing import Dict, Any
import logging
from datetime import datetime

from ..core.azure_clients import azure_clients
from ..db.session import health_check_databases
from ..core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """
    Basis Health Check Endpoint
    Schnelle Überprüfung ob Service läuft
    """
    return {
        "status": "healthy",
        "service": "IIEV-Ultra",
        "version": settings.app_version,
        "environment": settings.environment,
        "timestamp": datetime.now().isoformat()
    }


@router.get("/health/detailed")
async def detailed_health_check() -> Dict[str, Any]:
    """
    Detaillierter Health Check
    Prüft alle abhängigen Services
    """
    health_status = {
        "status": "healthy",
        "service": "IIEV-Ultra",
        "version": settings.app_version,
        "environment": settings.environment,
        "timestamp": datetime.now().isoformat(),
        "checks": {}
    }
    
    overall_healthy = True
    
    try:
        # Azure Services prüfen
        logger.info("Prüfe Azure Services...")
        azure_health = azure_clients.health_check()
        health_status["checks"]["azure"] = azure_health
        
        if not all(azure_health.values()):
            overall_healthy = False
            logger.warning("Azure Services nicht vollständig verfügbar")
        
    except Exception as e:
        logger.error(f"Azure Health Check fehlgeschlagen: {e}")
        health_status["checks"]["azure"] = {"error": str(e)}
        overall_healthy = False
    
    try:
        # Datenbanken prüfen
        logger.info("Prüfe Datenbank-Verbindungen...")
        db_health = health_check_databases()
        health_status["checks"]["databases"] = db_health
        
        if not all(db_health.values()):
            overall_healthy = False
            logger.warning("Datenbank-Verbindungen nicht vollständig verfügbar")
            
    except Exception as e:
        logger.error(f"Datenbank Health Check fehlgeschlagen: {e}")
        health_status["checks"]["databases"] = {"error": str(e)}
        overall_healthy = False
    
    # Celery Worker Status (TODO: Implementierung wenn Celery läuft)
    health_status["checks"]["celery"] = {"status": "not_implemented"}
    
    # KoSIT Validator verfügbarkeit prüfen
    try:
        import os
        kosit_available = os.path.exists(settings.kosit_validator_jar_path)
        health_status["checks"]["kosit_validator"] = {
            "jar_available": kosit_available,
            "jar_path": settings.kosit_validator_jar_path
        }
        if not kosit_available:
            logger.warning(f"KoSIT Validator JAR nicht gefunden: {settings.kosit_validator_jar_path}")
            
    except Exception as e:
        logger.error(f"KoSIT Health Check fehlgeschlagen: {e}")
        health_status["checks"]["kosit_validator"] = {"error": str(e)}
    
    # Gesamtstatus setzen
    health_status["status"] = "healthy" if overall_healthy else "degraded"
    
    return health_status


@router.get("/health/ready")
async def readiness_check() -> Dict[str, Any]:
    """
    Kubernetes Readiness Probe
    Service ist bereit Traffic zu empfangen
    """
    try:
        # Minimale Checks für Readiness
        db_health = health_check_databases()
        
        if db_health.get("metadata_db", False):
            return {
                "status": "ready",
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {
                "status": "not_ready",
                "reason": "metadata_database_unavailable",
                "timestamp": datetime.now().isoformat()
            }
            
    except Exception as e:
        logger.error(f"Readiness Check fehlgeschlagen: {e}")
        return {
            "status": "not_ready",
            "reason": str(e),
            "timestamp": datetime.now().isoformat()
        }


@router.get("/health/live")
async def liveness_check() -> Dict[str, Any]:
    """
    Kubernetes Liveness Probe
    Service ist am Leben (nicht deadlocked)
    """
    return {
        "status": "alive",
        "timestamp": datetime.now().isoformat()
    }
