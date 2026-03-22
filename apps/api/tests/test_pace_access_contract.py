from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import MagicMock

from core.pace_access import can_access_plan_paces


def test_admin_always_has_pace_access():
    athlete = SimpleNamespace(role="admin", has_active_subscription=False, subscription_tier="free")
    assert can_access_plan_paces(athlete, uuid4(), MagicMock()) is True


def test_active_subscription_has_pace_access():
    athlete = SimpleNamespace(role="athlete", has_active_subscription=True, subscription_tier="free")
    assert can_access_plan_paces(athlete, uuid4(), MagicMock()) is True


def test_guided_tier_has_pace_access():
    athlete = SimpleNamespace(role="athlete", has_active_subscription=False, subscription_tier="guided")
    assert can_access_plan_paces(athlete, uuid4(), MagicMock()) is True


def test_subscriber_tier_has_pace_access():
    athlete = SimpleNamespace(role="athlete", has_active_subscription=False, subscription_tier="subscriber")
    assert can_access_plan_paces(athlete, uuid4(), MagicMock()) is True


def test_free_tier_without_subscription_has_no_pace_access():
    athlete = SimpleNamespace(role="athlete", has_active_subscription=False, subscription_tier="free")
    db = MagicMock()
    db.query.side_effect = AssertionError("legacy purchase lookup should not run")
    assert can_access_plan_paces(athlete, uuid4(), db) is False
