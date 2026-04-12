"""Public tool funnel telemetry — no auth required."""

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_tool_event_requires_tools_path_for_tool_page_view():
    r = client.post(
        "/v1/telemetry/tool-event",
        json={"event_type": "tool_page_view", "path": "/wrong/tools"},
    )
    assert r.status_code == 400


def test_tool_event_accepts_tools_page_view():
    r = client.post(
        "/v1/telemetry/tool-event",
        json={"event_type": "tool_page_view", "path": "/tools/training-pace-calculator"},
    )
    assert r.status_code == 204


def test_signup_cta_accepts_non_tools_path():
    r = client.post(
        "/v1/telemetry/tool-event",
        json={"event_type": "signup_cta_click", "path": "/", "metadata": {"cta": "hero_primary"}},
    )
    assert r.status_code == 204


def test_finding_share_requires_manual_path():
    r = client.post(
        "/v1/telemetry/tool-event",
        json={
            "event_type": "finding_share_initiated",
            "path": "/tools/x",
            "metadata": {"finding_type": "highlighted_finding"},
        },
    )
    assert r.status_code == 400


def test_finding_share_accepts_manual_path():
    r = client.post(
        "/v1/telemetry/tool-event",
        json={
            "event_type": "finding_share_completed",
            "path": "/manual",
            "metadata": {"finding_type": "cascade_story", "finding_ref": "abc"},
        },
    )
    assert r.status_code == 204
