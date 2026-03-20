from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from routers.admin import DeepBackfillRequest, enqueue_garmin_deep_backfill


def _mock_db_with_target(target):
    db = MagicMock()
    q = MagicMock()
    q.filter.return_value = q
    q.first.return_value = target
    db.query.return_value = q
    return db


def test_admin_deep_backfill_success():
    user_id = uuid4()
    actor = SimpleNamespace(id=uuid4())
    target = SimpleNamespace(id=user_id, garmin_connected=True)
    db = _mock_db_with_target(target)
    task = SimpleNamespace(id="task-123")
    http_request = MagicMock()

    with patch("tasks.garmin_webhook_tasks.request_deep_garmin_backfill_task.apply_async", return_value=task), \
         patch("services.admin_audit.record_admin_audit_event") as mock_audit:
        result = enqueue_garmin_deep_backfill(
            user_id=user_id,
            request=DeepBackfillRequest(reason="support"),
            http_request=http_request,
            _=None,
            current_user=actor,
            db=db,
        )

    assert result == {"success": True, "queued": True, "task_id": "task-123"}
    assert db.commit.called
    mock_audit.assert_called_once()


def test_admin_deep_backfill_user_not_found():
    actor = SimpleNamespace(id=uuid4())
    db = _mock_db_with_target(None)
    with pytest.raises(HTTPException) as exc:
        enqueue_garmin_deep_backfill(
            user_id=uuid4(),
            request=DeepBackfillRequest(reason="support"),
            http_request=MagicMock(),
            _=None,
            current_user=actor,
            db=db,
        )
    assert exc.value.status_code == 404


def test_admin_deep_backfill_requires_garmin_connected():
    user_id = uuid4()
    actor = SimpleNamespace(id=uuid4())
    target = SimpleNamespace(id=user_id, garmin_connected=False)
    db = _mock_db_with_target(target)
    with pytest.raises(HTTPException) as exc:
        enqueue_garmin_deep_backfill(
            user_id=user_id,
            request=DeepBackfillRequest(reason="support"),
            http_request=MagicMock(),
            _=None,
            current_user=actor,
            db=db,
        )
    assert exc.value.status_code == 400
