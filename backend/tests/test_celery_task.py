from app.workers.tasks.test_task import ping_task, heartbeat_task


def test_celery_ping_task():
    """Verify that the test ping task executes and returns valid dictionary."""
    result = ping_task("test_hello")
    assert result["status"] == "success"
    assert result["task"] == "ping_task"
    assert result["payload"] == "test_hello"
    assert "executed_at" in result


def test_celery_heartbeat_task():
    """Verify that the beat heartbeat task executes and returns valid dictionary."""
    result = heartbeat_task()
    assert result["status"] == "alive"
    assert result["service"] == "socialos_celery_beat"
    assert "timestamp" in result
