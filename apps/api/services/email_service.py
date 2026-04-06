"""
Email Service

Handles sending transactional emails (password reset, email change verification).
Transport: Google Workspace SMTP via smtp.gmail.com:587 (STARTTLS).
Configured via settings: SMTP_SERVER, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD,
FROM_EMAIL, FROM_NAME, EMAIL_ENABLED.
"""

import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional, Set
from core.config import settings
from services.n1_insight_generator import friendly_signal_name
import logging

logger = logging.getLogger(__name__)

_HIGHER_IS_BETTER: Set[str] = {
    "garmin_sleep_score", "garmin_sleep_deep_s", "garmin_hrv_5min_high",
    "sleep_hours", "sleep_h", "sleep_quality_1_5", "feedback_leg_feel",
    "feedback_energy_pre", "garmin_body_battery_end", "garmin_body_battery_start",
    "activity_intensity_score", "garmin_hrv_weekly_avg", "garmin_hrv_status",
}
_LOWER_IS_BETTER: Set[str] = {
    "dew_point_f", "temperature_f", "garmin_avg_stress", "garmin_max_stress",
    "garmin_sleep_awake_s", "stress_1_5", "soreness_1_5",
}


def _direction_phrase(raw_key: str, positive_is_good: bool) -> str:
    """Return 'More ', 'Less ', 'Higher ', 'Lower ', or '' for known metrics."""
    if raw_key in _HIGHER_IS_BETTER:
        return "More " if positive_is_good else "Too much "
    if raw_key in _LOWER_IS_BETTER:
        return "Lower " if positive_is_good else "Higher "
    return ""


class EmailService:
    """Service for sending transactional emails."""

    def __init__(self):
        self.smtp_server = settings.SMTP_SERVER
        self.smtp_port = settings.SMTP_PORT
        self.smtp_username = settings.SMTP_USERNAME
        self.smtp_password = settings.SMTP_PASSWORD
        self.smtp_timeout_seconds = settings.SMTP_TIMEOUT_SECONDS
        self.from_email = settings.FROM_EMAIL
        self.from_name = settings.FROM_NAME
        self.enabled = settings.EMAIL_ENABLED

    def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None,
    ) -> bool:
        """
        Send an email via SMTP (STARTTLS).

        Returns True if sent successfully, False otherwise.
        Logs and returns False on any failure without raising.
        """
        if not self.enabled:
            logger.info("Email disabled — skipping send to %s: %s", to_email, subject)
            return False

        if not self.smtp_username or not self.smtp_password:
            logger.warning(
                "EMAIL_ENABLED=True but SMTP credentials not configured — "
                "cannot send to %s: %s",
                to_email,
                subject,
            )
            return False

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{self.from_name} <{self.from_email}>"
            msg["To"] = to_email

            if text_content:
                msg.attach(MIMEText(text_content, "plain"))
            msg.attach(MIMEText(html_content, "html"))

            with smtplib.SMTP(
                self.smtp_server,
                self.smtp_port,
                timeout=self.smtp_timeout_seconds,
            ) as server:
                server.ehlo()
                server.starttls(context=ssl.create_default_context())
                server.ehlo()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)

            logger.info("Email sent to %s: %s", to_email, subject)
            return True

        except Exception as exc:
            logger.error("Failed to send email to %s (%s): %s", to_email, subject, exc)
            return False
    
    def send_digest(
        self,
        to_email: str,
        athlete_name: str,
        what_works: List[dict],
        what_doesnt_work: List[dict],
        analysis_period_days: int
    ) -> bool:
        """
        Send weekly digest email with correlation insights.
        
        Tone: Sparse, direct, irreverent when earned.
        """
        subject = "Your Weekly Performance Insights"
        
        # Build HTML content
        html_parts = [
            f"<h2>Hey {athlete_name or 'there'},</h2>",
            f"<p>Here's what the data says about your performance over the last {analysis_period_days} days.</p>",
        ]
        
        if what_works:
            html_parts.append("<h3>What's Working</h3>")
            html_parts.append("<ul>")
            for correlation in what_works[:5]:
                raw_key = correlation['input_name']
                name = friendly_signal_name(raw_key)
                sample = correlation['sample_size']
                direction_word = _direction_phrase(raw_key, positive_is_good=True)
                label = f"{direction_word}{name}" if direction_word else name.capitalize()
                html_parts.append(
                    f"<li><strong>{label}</strong> is one of your strongest "
                    f"efficiency drivers — confirmed over {sample} runs.</li>"
                )
            html_parts.append("</ul>")
        else:
            html_parts.append("<p>Not enough data yet. Keep running.</p>")
        
        if what_doesnt_work:
            html_parts.append("<h3>What Doesn't Work</h3>")
            html_parts.append("<ul>")
            for correlation in what_doesnt_work[:3]:
                raw_key = correlation['input_name']
                name = friendly_signal_name(raw_key)
                sample = correlation['sample_size']
                direction_word = _direction_phrase(raw_key, positive_is_good=False)
                label = f"{direction_word}{name}" if direction_word else name.capitalize()
                html_parts.append(
                    f"<li><strong>{label}</strong> is dragging your efficiency "
                    f"down — confirmed across {sample} runs.</li>"
                )
            html_parts.append("</ul>")
        
        html_parts.append("<p>Keep going.</p>")
        html_parts.append("<p>— StrideIQ</p>")
        
        html_content = "\n".join(html_parts)
        
        # Build text content
        text_parts = [
            f"Hey {athlete_name or 'there'},",
            f"\nHere's what the data says about your performance over the last {analysis_period_days} days.\n",
        ]
        
        if what_works:
            text_parts.append("WHAT'S WORKING:")
            for correlation in what_works[:5]:
                raw_key = correlation['input_name']
                name = friendly_signal_name(raw_key)
                sample = correlation['sample_size']
                direction_word = _direction_phrase(raw_key, positive_is_good=True)
                label = f"{direction_word}{name}" if direction_word else name.capitalize()
                text_parts.append(
                    f"- {label} is one of your strongest "
                    f"efficiency drivers — confirmed over {sample} runs."
                )
        else:
            text_parts.append("Not enough data yet. Keep running.")
        
        if what_doesnt_work:
            text_parts.append("\nWHAT DOESN'T WORK:")
            for correlation in what_doesnt_work[:3]:
                raw_key = correlation['input_name']
                name = friendly_signal_name(raw_key)
                sample = correlation['sample_size']
                direction_word = _direction_phrase(raw_key, positive_is_good=False)
                label = f"{direction_word}{name}" if direction_word else name.capitalize()
                text_parts.append(
                    f"- {label} is dragging your efficiency "
                    f"down — confirmed across {sample} runs."
                )
        
        text_parts.append("\nKeep going.\n— StrideIQ")
        text_content = "\n".join(text_parts)
        
        return self.send_email(to_email, subject, html_content, text_content)


# Singleton instance
email_service = EmailService()


def send_email(
    to_email: str,
    subject: str,
    html_content: str,
    text_content: Optional[str] = None
) -> bool:
    """
    Module-level convenience function for sending emails.
    Delegates to the singleton EmailService instance.
    
    Args:
        to_email: Recipient email address
        subject: Email subject line
        html_content: HTML body of the email
        text_content: Optional plain text version
        
    Returns:
        True if sent successfully, False otherwise
    """
    return email_service.send_email(
        to_email=to_email,
        subject=subject,
        html_content=html_content,
        text_content=text_content
    )

