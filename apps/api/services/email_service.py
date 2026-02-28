"""
Email Service

Handles sending transactional emails (password reset, email change verification).
Transport: Google Workspace SMTP via smtp.gmail.com:587 (STARTTLS).
Configured via settings: SMTP_SERVER, SMTP_PORT, SMTP_USERNAME, SMTP_PASSWORD,
FROM_EMAIL, FROM_NAME, EMAIL_ENABLED.
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional
from core.config import settings
import logging

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending transactional emails."""

    def __init__(self):
        self.smtp_server = settings.SMTP_SERVER
        self.smtp_port = settings.SMTP_PORT
        self.smtp_username = settings.SMTP_USERNAME
        self.smtp_password = settings.SMTP_PASSWORD
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

            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.ehlo()
                server.starttls()
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
            "<p>Here's what the data says about your performance over the last {analysis_period_days} days.</p>",
        ]
        
        if what_works:
            html_parts.append("<h3>What's Working</h3>")
            html_parts.append("<ul>")
            for correlation in what_works[:5]:  # Top 5
                input_name = correlation['input_name'].replace('_', ' ').title()
                percent = int(abs(correlation['correlation_coefficient']) * 100)
                html_parts.append(
                    f"<li><strong>{input_name}</strong> explains {percent}% of your efficiency gains. "
                    f"Pattern holds over {correlation['sample_size']} runs.</li>"
                )
            html_parts.append("</ul>")
        else:
            html_parts.append("<p>Not enough data yet. Keep running.</p>")
        
        if what_doesnt_work:
            html_parts.append("<h3>What Doesn't Work</h3>")
            html_parts.append("<ul>")
            for correlation in what_doesnt_work[:3]:  # Top 3
                input_name = correlation['input_name'].replace('_', ' ').title()
                percent = int(abs(correlation['correlation_coefficient']) * 100)
                html_parts.append(
                    f"<li><strong>{input_name}</strong> correlates with {percent}% worse efficiency. "
                    f"Statistically significant.</li>"
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
                input_name = correlation['input_name'].replace('_', ' ').title()
                percent = int(abs(correlation['correlation_coefficient']) * 100)
                text_parts.append(
                    f"- {input_name} explains {percent}% of your efficiency gains. "
                    f"Pattern holds over {correlation['sample_size']} runs."
                )
        else:
            text_parts.append("Not enough data yet. Keep running.")
        
        if what_doesnt_work:
            text_parts.append("\nWHAT DOESN'T WORK:")
            for correlation in what_doesnt_work[:3]:
                input_name = correlation['input_name'].replace('_', ' ').title()
                percent = int(abs(correlation['correlation_coefficient']) * 100)
                text_parts.append(
                    f"- {input_name} correlates with {percent}% worse efficiency. "
                    f"Statistically significant."
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

