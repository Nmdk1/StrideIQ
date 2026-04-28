"""
Email Service Tests

Covers:
- send with valid config (mocked SMTP)
- disabled flag short-circuits before SMTP
- SMTP failure returns False without raising
- missing credentials returns False without raising
"""

import pytest
from unittest.mock import MagicMock, patch

from services.email_service import EmailService


def _service(enabled=True, username="test@strideiq.run", password="apppassword"):
    """Build an EmailService with controlled settings."""
    svc = EmailService.__new__(EmailService)
    svc.smtp_server = "smtp.gmail.com"
    svc.smtp_port = 587
    svc.smtp_username = username
    svc.smtp_password = password
    svc.smtp_timeout_seconds = 15
    svc.from_email = "noreply@strideiq.run"
    svc.from_name = "StrideIQ"
    svc.enabled = enabled
    return svc


class TestEmailServiceSend:
    def test_sends_with_valid_config(self):
        """Mock SMTP — verifies From header, subject, and body reach the server."""
        svc = _service()
        mock_smtp = MagicMock()

        with patch("smtplib.SMTP", return_value=mock_smtp) as smtp_cls:
            mock_smtp.__enter__ = lambda s: mock_smtp
            mock_smtp.__exit__ = MagicMock(return_value=False)

            result = svc.send_email(
                to_email="athlete@example.com",
                subject="Password Reset",
                html_content="<p>Reset link here</p>",
                text_content="Reset link here",
            )

        assert result is True
        smtp_cls.assert_called_once_with("smtp.gmail.com", 587, timeout=15)
        mock_smtp.starttls.assert_called_once()
        mock_smtp.login.assert_called_once_with("test@strideiq.run", "apppassword")
        sent_msg = mock_smtp.send_message.call_args[0][0]
        assert sent_msg["Subject"] == "Password Reset"
        assert "StrideIQ" in sent_msg["From"]
        assert "noreply@strideiq.run" in sent_msg["From"]

    def test_disabled_does_not_send(self):
        """EMAIL_ENABLED=False must short-circuit before any SMTP contact."""
        svc = _service(enabled=False)

        with patch("smtplib.SMTP") as smtp_cls:
            result = svc.send_email(
                to_email="athlete@example.com",
                subject="Should not send",
                html_content="<p>nope</p>",
            )

        assert result is False
        smtp_cls.assert_not_called()

    def test_handles_smtp_failure(self):
        """SMTP exception must return False, not raise."""
        svc = _service()

        with patch("smtplib.SMTP", side_effect=Exception("Connection refused")):
            result = svc.send_email(
                to_email="athlete@example.com",
                subject="Will fail",
                html_content="<p>fail</p>",
            )

        assert result is False

    def test_missing_credentials_returns_false(self):
        """EMAIL_ENABLED=True but no credentials — must return False, not silently succeed."""
        svc = _service(username=None, password=None)

        with patch("smtplib.SMTP") as smtp_cls:
            result = svc.send_email(
                to_email="athlete@example.com",
                subject="No creds",
                html_content="<p>no creds</p>",
            )

        assert result is False
        smtp_cls.assert_not_called()

    def test_from_domain_is_strideiq(self):
        """Sender domain must be strideiq.run, not legacy brand."""
        svc = _service()
        mock_smtp = MagicMock()

        with patch("smtplib.SMTP", return_value=mock_smtp):
            mock_smtp.__enter__ = lambda s: mock_smtp
            mock_smtp.__exit__ = MagicMock(return_value=False)
            svc.send_email("x@example.com", "Test", "<p>test</p>")

        sent_msg = mock_smtp.send_message.call_args[0][0]
        assert "performancefocused.com" not in sent_msg["From"]
        assert "strideiq.run" in sent_msg["From"]


class TestWeeklyDigestEmail:
    def test_invalid_llm_scratchpad_uses_safe_fallback(self):
        """Internal filtering notes must never be sent as the digest body."""
        svc = _service()
        scratchpad = (
            "Here are the findings that survive the filters:\n"
            "Actionable & non-obvious:**\n"
            "1. **Running cadence** (r=+0.52, n=47) — actionable\n"
            "Surviving findings:** cadence\n"
            "Keep going."
        )
        correlations = [
            {
                "input_name": "avg_cadence",
                "output_metric": "efficiency",
                "category": "what_works",
                "correlation_coefficient": 0.52,
                "sample_size": 47,
                "times_confirmed": 4,
            },
            {
                "input_name": "pre_run_carbs_g",
                "output_metric": "efficiency",
                "category": "pattern",
                "correlation_coefficient": 0.42,
                "sample_size": 22,
                "times_confirmed": 3,
            },
        ]

        svc.send_email = MagicMock(return_value=True)
        with patch("core.llm_client.resolve_briefing_model", return_value="test-model"), \
             patch("core.llm_client.call_llm", return_value={"text": scratchpad}):
            assert svc.send_coached_digest(
                to_email="athlete@example.com",
                athlete_name="Michael",
                findings_context="- cadence",
                analysis_period_days=90,
                total_correlations=len(correlations),
                all_correlations=correlations,
            )

        send_args = svc.send_email.call_args.args
        html_body = send_args[2]
        text_body = send_args[3]
        assert "Actionable" not in html_body
        assert "Surviving findings" not in html_body
        assert "r=+0.52" not in text_body
        assert "Running cadence" in html_body

    def test_valid_llm_digest_is_escaped_before_send(self):
        svc = _service()
        valid_body = (
            "• Cadence is one of your more repeatable performance signals across 47 runs.\n"
            "• Pre-run fueling is worth watching because it keeps recurring in your data."
        )

        svc.send_email = MagicMock(return_value=True)
        with patch("core.llm_client.resolve_briefing_model", return_value="test-model"), \
             patch("core.llm_client.call_llm", return_value={"text": valid_body}):
            assert svc.send_coached_digest(
                to_email="athlete@example.com",
                athlete_name="<Michael>",
                findings_context="- cadence",
                analysis_period_days=90,
                total_correlations=2,
                all_correlations=[],
            )

        html_body = svc.send_email.call_args.args[2]
        assert "Hey &lt;Michael&gt;" in html_body
        assert "<Michael>" not in html_body
        assert "<li>Cadence is one of your more repeatable performance signals across 47 runs.</li>" in html_body
