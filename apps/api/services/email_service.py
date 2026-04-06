"""
Email Service

Handles sending transactional emails (password reset, email change verification,
weekly coached digest).
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


_DIGEST_COACHING_SYSTEM = """\
You are writing a brief weekly email from StrideIQ to a runner.  You receive
their statistically confirmed correlation findings from the last 90 days.

Your job is NOT to relay every finding.  Your job is to be a good coach: pick
only the findings that are genuinely useful and write 3-5 short bullet points
in plain coaching language.

FILTERING RULES — exclude findings that fail ANY of these:
1. ACTIONABLE — can the athlete change this?  Environmental factors they
   cannot control (dew point, temperature, humidity) are NOT actionable.
   The system already adjusts for weather internally; do not tell the athlete
   "run when it's cooler."
2. NON-OBVIOUS — "fresh legs = better running" is common sense, not insight.
   Skip tautologies.
3. RELIABLE DATA — daily step count from a wrist device is noisy and often
   includes activity steps.  Treat it with low confidence.
4. NON-CONTRADICTORY — if two findings appear to conflict (e.g. "more
   consecutive days is good" but "more active time is bad"), either explain
   the nuance in one bullet or pick the one that matters more.  Never show
   both without reconciliation.

WRITING RULES:
- Use plain athlete language.  "Your efficiency improves with…" not
  "r=-0.72 p<0.01".
- Each bullet should answer: WHAT is the finding, WHICH DIRECTION helps,
  and HOW STRONG is the evidence (use the sample size).
- Do NOT use internal metric names.  The friendly name is provided.
- If a finding is about something the athlete does (training, sleep, recovery),
  frame it as something they can keep doing or adjust.
- Keep the total body under 120 words.  Sparse and direct.
- Do NOT add greetings, sign-offs, or preamble — just the bullet points.
  The email wrapper handles salutation and closing.
- Output plain text, one bullet per line, each starting with "• ".
- If fewer than 2 findings survive the filter, say:
  "Your data is still accumulating.  Check back next week."\
"""


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
    
    # ------------------------------------------------------------------
    # Coached digest (LLM-powered, with template fallback)
    # ------------------------------------------------------------------

    def send_coached_digest(
        self,
        to_email: str,
        athlete_name: str,
        findings_context: str,
        analysis_period_days: int,
        total_correlations: int,
        all_correlations: List[dict],
    ) -> bool:
        """
        Send weekly digest using an LLM coaching filter.

        The LLM receives the raw findings and returns 3-5 coached bullets.
        On LLM failure, falls back to the deterministic template.
        """
        coached_body = self._generate_coached_body(findings_context)

        if coached_body:
            return self._send_coached_email(
                to_email, athlete_name, coached_body, analysis_period_days
            )

        logger.warning("LLM digest generation failed — using template fallback for %s", to_email)
        return self._send_template_fallback(
            to_email, athlete_name, all_correlations, analysis_period_days
        )

    def _generate_coached_body(self, findings_context: str) -> Optional[str]:
        """Call the LLM to produce coached digest bullets. Returns None on failure."""
        try:
            from core.llm_client import call_llm, resolve_briefing_model

            model = resolve_briefing_model()
            result = call_llm(
                model=model,
                system=_DIGEST_COACHING_SYSTEM,
                messages=[{
                    "role": "user",
                    "content": (
                        "Here are this athlete's confirmed correlation findings "
                        "from the last 90 days.  Write the coached digest bullets.\n\n"
                        f"{findings_context}"
                    ),
                }],
                max_tokens=400,
                temperature=0.3,
                timeout_s=30,
                disable_thinking=True,
            )
            body = (result.get("content") or "").strip()
            if not body or len(body) < 20:
                logger.warning("LLM returned empty or too-short digest body")
                return None
            return body
        except Exception as exc:
            logger.error("LLM digest call failed: %s", exc)
            return None

    def _send_coached_email(
        self,
        to_email: str,
        athlete_name: str,
        coached_body: str,
        analysis_period_days: int,
    ) -> bool:
        subject = "Your Weekly Performance Insights"
        name = athlete_name or "there"

        bullets_html = ""
        for line in coached_body.split("\n"):
            line = line.strip()
            if not line:
                continue
            clean = line.lstrip("•-* ").strip()
            if clean:
                bullets_html += f"<li>{clean}</li>\n"

        html_content = (
            f"<h2>Hey {name},</h2>\n"
            f"<p>Here's what your data revealed over the last {analysis_period_days} days.</p>\n"
            f"<ul>\n{bullets_html}</ul>\n"
            f"<p>Keep going.</p>\n"
            f"<p>— StrideIQ</p>"
        )
        text_content = (
            f"Hey {name},\n\n"
            f"Here's what your data revealed over the last {analysis_period_days} days.\n\n"
            f"{coached_body}\n\n"
            f"Keep going.\n— StrideIQ"
        )
        return self.send_email(to_email, subject, html_content, text_content)

    # ------------------------------------------------------------------
    # Deterministic template fallback (degraded path)
    # ------------------------------------------------------------------

    def _send_template_fallback(
        self,
        to_email: str,
        athlete_name: str,
        all_correlations: List[dict],
        analysis_period_days: int,
    ) -> bool:
        """Old for-loop template — used only when the LLM call fails."""
        subject = "Your Weekly Performance Insights"

        what_works = sorted(
            [c for c in all_correlations if c.get("direction") == "negative"],
            key=lambda x: abs(x.get("correlation_coefficient", 0)),
            reverse=True,
        )
        what_doesnt_work = sorted(
            [c for c in all_correlations if c.get("direction") == "positive"],
            key=lambda x: abs(x.get("correlation_coefficient", 0)),
            reverse=True,
        )

        html_parts = [
            f"<h2>Hey {athlete_name or 'there'},</h2>",
            f"<p>Here's what the data says about your performance over the last {analysis_period_days} days.</p>",
        ]

        if what_works:
            html_parts.append("<h3>What's Working</h3><ul>")
            for c in what_works[:5]:
                raw_key = c["input_name"]
                name = friendly_signal_name(raw_key)
                sample = c["sample_size"]
                dw = _direction_phrase(raw_key, positive_is_good=True)
                label = f"{dw}{name}" if dw else name.capitalize()
                html_parts.append(
                    f"<li><strong>{label}</strong> is one of your strongest "
                    f"efficiency drivers — confirmed over {sample} runs.</li>"
                )
            html_parts.append("</ul>")

        if what_doesnt_work:
            html_parts.append("<h3>What Doesn't Work</h3><ul>")
            for c in what_doesnt_work[:3]:
                raw_key = c["input_name"]
                name = friendly_signal_name(raw_key)
                sample = c["sample_size"]
                dw = _direction_phrase(raw_key, positive_is_good=False)
                label = f"{dw}{name}" if dw else name.capitalize()
                html_parts.append(
                    f"<li><strong>{label}</strong> is dragging your efficiency "
                    f"down — confirmed across {sample} runs.</li>"
                )
            html_parts.append("</ul>")

        html_parts.append("<p>Keep going.</p><p>— StrideIQ</p>")
        html_content = "\n".join(html_parts)

        text_content = (
            f"Hey {athlete_name or 'there'},\n\n"
            f"Here's what the data says about your performance over the last {analysis_period_days} days.\n\n"
            f"Keep going.\n— StrideIQ"
        )
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

