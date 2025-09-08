"""
Celery Worker Konfiguration
Asynchrone Verarbeitung von Rechnungen
"""

from celery import Celery
import logging
from typing import Dict, Any

from ..core.config import settings

# Logging konfigurieren
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Celery App erstellen
celery_app = Celery(
    "iiev-ultra",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["src.tasks.processor"]  # Module mit Tasks
)

# Celery Konfiguration
celery_app.conf.update(
    # Task Routing
    task_routes={
        "src.tasks.processor.process_invoice_task": {"queue": "invoice_processing"},
        "src.tasks.processor.email_monitoring_task": {"queue": "email_monitoring"}
    },
    
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    
    # Timezone
    timezone="Europe/Berlin",
    enable_utc=True,
    
    # Task Execution
    task_always_eager=False,  # Für Tests auf True setzen
    task_eager_propagates=True,
    
    # Worker Configuration
    worker_prefetch_multiplier=1,  # Ein Task pro Worker
    worker_max_tasks_per_child=1000,
    worker_disable_rate_limits=False,
    
    # Task Timeouts
    task_soft_time_limit=300,  # 5 Minuten Soft Limit
    task_time_limit=600,       # 10 Minuten Hard Limit
    
    # Result Backend
    result_expires=3600,  # Ergebnisse 1 Stunde aufbewahren
    result_persistent=True,
    
    # Retry Configuration
    task_reject_on_worker_lost=True,
    task_acks_late=True,
    
    # Monitoring
    worker_send_task_events=True,
    task_send_sent_event=True,
    
    # Beat Schedule (für periodische Tasks)
    beat_schedule={
        "email-monitoring": {
            "task": "src.tasks.processor.email_monitoring_task",
            "schedule": 60.0,  # Alle 60 Sekunden
            "options": {"queue": "email_monitoring"}
        },
        "cleanup-old-results": {
            "task": "src.tasks.processor.cleanup_old_results_task",
            "schedule": 3600.0,  # Stündlich
            "options": {"queue": "maintenance"}
        }
    },
    beat_schedule_filename="celerybeat-schedule"
)

# Task Error Handler
@celery_app.task(bind=True)
def error_handler(self, uuid, err, traceback):
    """Globaler Error Handler für Tasks"""
    logger.error(f"Task {uuid} failed: {err}")
    logger.error(f"Traceback: {traceback}")
    
    # Hier könnte Monitoring/Alerting integriert werden
    # z.B. Azure Application Insights, Sentry, etc.


# Health Check Task
@celery_app.task(name="health_check")
def health_check_task() -> Dict[str, Any]:
    """
    Health Check Task für Celery Worker
    """
    import datetime
    
    return {
        "status": "healthy",
        "worker_id": health_check_task.request.id,
        "timestamp": datetime.datetime.now().isoformat(),
        "celery_version": celery_app.version,
        "broker_url": settings.celery_broker_url.split("@")[-1] if "@" in settings.celery_broker_url else settings.celery_broker_url
    }


# Startup Event
@celery_app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    """Setup für periodische Tasks"""
    logger.info("🔄 Celery Worker konfiguriert mit periodischen Tasks")


# Worker Ready Event
@celery_app.on_after_finalize.connect
def setup_worker(sender, **kwargs):
    """Worker Setup nach Initialisierung"""
    logger.info(f"🚀 Celery Worker bereit - Environment: {settings.environment}")
    
    # In Development: Eager Mode für schnellere Tests
    if settings.environment == "development":
        logger.info("⚡ Development Mode: Task Eager Execution aktiviert")
        celery_app.conf.task_always_eager = True


if __name__ == "__main__":
    # Worker direkt starten
    celery_app.start()
