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
        smtp_cls.assert_called_once_with("smtp.gmail.com", 587)
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
