from celery import Celery
from kombu import Queue

from app.core.config import settings

# Initialize Celery Application
celery_app = Celery(
    "socialos_workers",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=["app.workers.tasks.test_task"],
)

# Queue Definitions for SocialOS
# Queues: publish_queue, analytics_queue, maintenance_queue, dead_letter_queue
celery_app.conf.task_queues = (
    Queue("default", routing_key="task.default"),
    Queue("publish_queue", routing_key="task.publish"),
    Queue("analytics_queue", routing_key="task.analytics"),
    Queue("maintenance_queue", routing_key="task.maintenance"),
    Queue("dead_letter_queue", routing_key="task.dlq"),
)

celery_app.conf.task_default_queue = "default"
celery_app.conf.task_default_exchange = "tasks"
celery_app.conf.task_default_routing_key = "task.default"

# Celery Serialization and Timezone Settings
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,
    worker_prefetch_multiplier=1,
)

# Celery Beat Scheduled Tasks (Skeleton configuration - harmless heartbeat task)
celery_app.conf.beat_schedule = {
    "system-heartbeat-every-minute": {
        "task": "app.workers.tasks.test_task.heartbeat_task",
        "schedule": 60.0,
        "options": {"queue": "maintenance_queue"},
    },
}
