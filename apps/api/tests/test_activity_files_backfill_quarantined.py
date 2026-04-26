"""
Quarantine contract for Garmin activityFiles backfill.

Background: Garmin's `/wellness-api/rest/backfill/activityFiles` endpoint
returns 404 against our scopes regardless of window or token freshness.
Multiple agents have tried over multiple sessions; it is not fixable from
our side. Continued attempts waste Garmin rate-limit headroom and produce
log noise that looks like a real bug.

These tests lock in the quarantine so the next agent who sees the call
site cannot accidentally re-enable it.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


def test_request_activity_files_backfill_raises_unavailable():
    """The function itself must raise immediately — no network call."""
    from services.sync.garmin_backfill import (
        ActivityFilesBackfillUnavailable,
        request_activity_files_backfill,
    )

    athlete = MagicMock()
    athlete.id = "test-athlete-id"
    db = MagicMock()

    with pytest.raises(ActivityFilesBackfillUnavailable) as excinfo:
        request_activity_files_backfill(athlete, db, days=30)

    msg = str(excinfo.value)
    assert "test-athlete-id" in msg
    assert "live activity-files webhook" in msg


def test_celery_task_returns_unavailable_envelope_without_raising():
    """The celery task wraps the call and must NOT propagate the raise.

    A scheduled invocation should yield a stable structured result so it
    surfaces in monitoring as "unavailable" rather than as a retried
    exception that hammers the broker.
    """
    from tasks.garmin_webhook_tasks import (
        request_garmin_activity_files_backfill_task,
    )

    # For a `bind=True` Celery task, calling `.run(...)` (or the task
    # directly) auto-binds `self` for us, so we pass only the user args.
    result = request_garmin_activity_files_backfill_task.run("abc-123", 30)

    assert result["status"] == "unavailable"
    assert result["reason"] == "garmin_activity_files_backfill_not_supported"
    assert result["athlete_id"] == "abc-123"
    assert result["days"] == 30


def test_garmin_webhook_tasks_does_not_import_quarantined_function():
    """If the import sneaks back in, this fails immediately.

    Static contract: nothing in tasks/garmin_webhook_tasks.py should pull in
    request_activity_files_backfill, because the only valid use of it is to
    not call it.
    """
    import inspect

    from tasks import garmin_webhook_tasks

    source = inspect.getsource(garmin_webhook_tasks)
    # The string can appear in docstrings/comments referring to the
    # quarantine, but it must NOT appear as an `import` line.
    for line in source.splitlines():
        stripped = line.strip()
        if stripped.startswith(("import ", "from ")) and "request_activity_files_backfill" in stripped:
            pytest.fail(
                f"garmin_webhook_tasks.py is importing the quarantined function: {stripped!r}"
            )
