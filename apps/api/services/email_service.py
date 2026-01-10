"""
Email Service

Handles sending emails for scheduled digests and notifications.
Uses SMTP for now, can be swapped for SendGrid/Mailgun later.
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional
from core.config import settings
import logging

logger = logging.getLogger(__name__)


class EmailService:
    """Service for sending emails"""
    
    def __init__(self):
        self.smtp_server = getattr(settings, 'SMTP_SERVER', 'localhost')
        self.smtp_port = getattr(settings, 'SMTP_PORT', 587)
        self.smtp_username = getattr(settings, 'SMTP_USERNAME', None)
        self.smtp_password = getattr(settings, 'SMTP_PASSWORD', None)
        self.from_email = getattr(settings, 'FROM_EMAIL', 'noreply@performancefocused.com')
        self.from_name = getattr(settings, 'FROM_NAME', 'Performance Focused')
        self.enabled = getattr(settings, 'EMAIL_ENABLED', False)
    
    def send_email(
        self,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None
    ) -> bool:
        """
        Send an email.
        
        Returns True if sent successfully, False otherwise.
        """
        if not self.enabled:
            logger.info(f"Email disabled, would send to {to_email}: {subject}")
            return False
        
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = f"{self.from_name} <{self.from_email}>"
            msg['To'] = to_email
            
            # Add text and HTML parts
            if text_content:
                text_part = MIMEText(text_content, 'plain')
                msg.attach(text_part)
            
            html_part = MIMEText(html_content, 'html')
            msg.attach(html_part)
            
            # Send email
            if self.smtp_username and self.smtp_password:
                server = smtplib.SMTP(self.smtp_server, self.smtp_port)
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)
                server.quit()
            else:
                # Local development - just log
                logger.info(f"Would send email to {to_email}: {subject}")
                logger.debug(f"Content: {html_content[:200]}...")
            
            return True
            
        except Exception as e:
            logger.error(f"Error sending email to {to_email}: {str(e)}")
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
        html_parts.append("<p>— Performance Focused</p>")
        
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
        
        text_parts.append("\nKeep going.\n— Performance Focused")
        text_content = "\n".join(text_parts)
        
        return self.send_email(to_email, subject, html_content, text_content)


# Singleton instance
email_service = EmailService()


