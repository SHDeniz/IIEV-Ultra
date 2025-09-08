"""
IIEV-Ultra Hauptanwendung
FastAPI Application mit allen Routen und Middleware
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import time
from contextlib import asynccontextmanager

from .core.config import settings
from .core.azure_clients import azure_clients
from .db.session import health_check_databases
from .api import upload, status, health


# Logging konfigurieren
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application Lifecycle Management
    Startup und Shutdown Events
    """
    # Startup
    logger.info(f"🚀 IIEV-Ultra {settings.app_version} startet...")
    logger.info(f"Umgebung: {settings.environment}")
    
    # Gesundheitsprüfung der Services
    try:
        # Azure Services prüfen
        azure_health = azure_clients.health_check()
        logger.info(f"Azure Services Status: {azure_health}")
        
        # Datenbanken prüfen
        db_health = health_check_databases()
        logger.info(f"Datenbank Status: {db_health}")
        
        if not all(azure_health.values()) or not all(db_health.values()):
            logger.warning("⚠️  Einige Services sind nicht verfügbar, aber Anwendung startet trotzdem")
        else:
            logger.info("✅ Alle Services sind betriebsbereit")
            
    except Exception as e:
        logger.error(f"❌ Fehler beim Service Health Check: {e}")
    
    yield
    
    # Shutdown
    logger.info("🛑 IIEV-Ultra wird heruntergefahren...")


# FastAPI App erstellen
app = FastAPI(
    title="IIEV-Ultra",
    description="Invoice Ingestion and Validation Engine - Ultra Edition",
    version=settings.app_version,
    docs_url="/docs" if settings.debug else None,
    redoc_url="/redoc" if settings.debug else None,
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.debug else ["https://yourdomain.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request Logging Middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log alle eingehenden Requests mit Timing"""
    start_time = time.time()
    
    # Request loggen
    logger.info(f"📨 {request.method} {request.url.path} - Client: {request.client.host if request.client else 'unknown'}")
    
    try:
        response = await call_next(request)
        
        # Response loggen
        process_time = time.time() - start_time
        logger.info(f"📤 {request.method} {request.url.path} - Status: {response.status_code} - Time: {process_time:.3f}s")
        
        # Performance Header hinzufügen
        response.headers["X-Process-Time"] = str(process_time)
        
        return response
        
    except Exception as e:
        process_time = time.time() - start_time
        logger.error(f"❌ {request.method} {request.url.path} - Error: {str(e)} - Time: {process_time:.3f}s")
        
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal Server Error",
                "message": "Ein unerwarteter Fehler ist aufgetreten",
                "timestamp": time.time()
            }
        )


# Exception Handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Globaler Exception Handler"""
    logger.error(f"🔥 Unbehandelte Exception: {type(exc).__name__}: {str(exc)}")
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": "Ein unerwarteter Fehler ist aufgetreten",
            "timestamp": time.time(),
            "path": str(request.url.path) if request else None
        }
    )


# API Routen einbinden
app.include_router(health.router, tags=["Health"])
app.include_router(upload.router, prefix=settings.api_v1_prefix, tags=["Upload"])
app.include_router(status.router, prefix=settings.api_v1_prefix, tags=["Status"])


# Root Endpoint
@app.get("/")
async def root():
    """Root Endpoint mit Basis-Informationen"""
    return {
        "service": "IIEV-Ultra",
        "version": settings.app_version,
        "description": "Invoice Ingestion and Validation Engine - Ultra Edition",
        "environment": settings.environment,
        "status": "running",
        "docs": "/docs" if settings.debug else "disabled",
        "api_version": "v1",
        "api_prefix": settings.api_v1_prefix
    }


# Entwicklungs-Endpoints (nur in Debug-Modus)
if settings.debug:
    @app.get("/debug/config")
    async def debug_config():
        """Debug-Endpoint für Konfiguration (nur Development)"""
        return {
            "environment": settings.environment,
            "debug": settings.debug,
            "database_url": settings.database_url.split("@")[-1] if "@" in settings.database_url else "***",
            "blob_containers": {
                "raw": settings.blob_container_raw,
                "processed": settings.blob_container_processed
            },
            "kosit_config": {
                "jar_path": settings.kosit_validator_jar_path,
                "timeout": settings.kosit_timeout_seconds
            },
            "validation": {
                "tolerance_euro": settings.calculation_tolerance_euro,
                "max_file_size_mb": settings.max_file_size_mb
            }
        }


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "src.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.debug,
        log_level=settings.log_level.lower()
    )
