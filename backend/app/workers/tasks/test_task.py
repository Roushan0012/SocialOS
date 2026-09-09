import logging
from datetime import datetime, timezone
from typing import Any, Dict

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="app.workers.tasks.test_task.ping_task", queue="default")
def ping_task(payload: str = "pong") -> Dict[str, Any]:
    """Harmless test task for verifying Celery worker execution locally."""
    timestamp = datetime.now(timezone.utc).isoformat()
    logger.info(f"Executing ping_task with payload: {payload} at {timestamp}")
    return {
        "status": "success",
        "task": "ping_task",
        "payload": payload,
        "executed_at": timestamp,
    }


@celery_app.task(name="app.workers.tasks.test_task.heartbeat_task", queue="maintenance_queue")
def heartbeat_task() -> Dict[str, Any]:
    """Periodic heartbeat task executed via Celery Beat scheduler."""
    timestamp = datetime.now(timezone.utc).isoformat()
    logger.info(f"SocialOS Beat Heartbeat pulse at {timestamp}")
    return {
        "status": "alive",
        "service": "socialos_celery_beat",
        "timestamp": timestamp,
    }
