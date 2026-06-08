"""
Email notifier for alert digests.
"""
import html
import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Dict, List

from utils.db import record_notification

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
SMTP_FROM = os.getenv("SMTP_FROM")
SMTP_HOST = "smtp.gmail.com"
SMTP_PORT = 465

_email_queue: Dict[str, List[dict]] = {}


def queue_email_digest(email: str, jobs: List[dict]) -> None:
    """Queue jobs for a daily email digest."""
    if not email or not jobs:
        return

    if email not in _email_queue:
        _email_queue[email] = []
    _email_queue[email].extend(jobs)


def _format_plain_text_body(jobs: List[dict]) -> str:
    """Build the plain-text fallback body."""
    lines = [
        f"{job.get('title', '').strip()} at {job.get('company', '').strip()} ({job.get('location', '').strip()}) -> {job.get('apply_url', '').strip()}"
        for job in jobs
    ]
    return "\n".join(lines)


def build_html_body(jobs: List[dict]) -> str:
    """Return a full responsive HTML email body for the job digest."""
    job_count = len(jobs)
    cards = []

    for job in jobs:
        title = html.escape((job.get("title") or "").strip())
        company = html.escape((job.get("company") or "").strip())
        location = html.escape((job.get("location") or "").strip())
        apply_url = html.escape((job.get("apply_url") or "").strip(), quote=True)

        cards.append(
            f"""
            <tr>
              <td style="padding: 0 0 18px 0;">
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="border: 1px solid #e5e7eb; border-radius: 14px; overflow: hidden; background: #ffffff;">
                  <tr>
                    <td style="padding: 20px 20px 16px 20px;">
                      <div style="font-family: Arial, sans-serif; font-size: 18px; line-height: 1.4; font-weight: 700; color: #111827; margin: 0 0 8px 0;">
                        {title or 'Untitled Role'}
                      </div>
                      <div style="font-family: Arial, sans-serif; font-size: 14px; line-height: 1.5; color: #374151; margin: 0 0 6px 0;">
                        <strong style="color: #111827;">Company:</strong> {company or 'Unknown'}
                      </div>
                      <div style="font-family: Arial, sans-serif; font-size: 14px; line-height: 1.5; color: #374151; margin: 0 0 16px 0;">
                        <span style="font-size: 15px;">📍</span> {location or 'Location not listed'}
                      </div>
                      <a href="{apply_url}" target="_blank" rel="noopener noreferrer" style="display: inline-block; background: #4f46e5; color: #ffffff; text-decoration: none; font-family: Arial, sans-serif; font-size: 14px; font-weight: 700; line-height: 1; padding: 12px 18px; border-radius: 10px;">
                        Apply Now
                      </a>
                    </td>
                  </tr>
                </table>
              </td>
            </tr>
            """
        )

    cards_html = "".join(cards) if cards else """
        <tr>
          <td style="padding: 0 0 18px 0;">
            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="border: 1px solid #e5e7eb; border-radius: 14px; background: #ffffff;">
              <tr>
                <td style="padding: 20px; font-family: Arial, sans-serif; font-size: 14px; line-height: 1.5; color: #374151;">
                  No new jobs were found for this alert cycle.
                </td>
              </tr>
            </table>
          </td>
        </tr>
    """

    return f"""
    <!doctype html>
    <html lang="en">
      <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Your Daily Job Alert</title>
      </head>
      <body style="margin: 0; padding: 0; background: #f4f6fb;">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background: #f4f6fb; margin: 0; padding: 0;">
          <tr>
            <td align="center" style="padding: 24px 12px;">
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="max-width: 600px; width: 100%; background: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 8px 24px rgba(15, 23, 42, 0.08);">
                <tr>
                  <td style="background: #1a1a2e; padding: 28px 24px; text-align: center;">
                    <div style="font-family: Arial, sans-serif; font-size: 24px; line-height: 1.2; font-weight: 700; color: #ffffff; margin: 0 0 10px 0;">
                      Your Daily Job Alert
                    </div>
                    <div style="display: inline-block; font-family: Arial, sans-serif; font-size: 13px; font-weight: 700; color: #ffffff; background: #4f46e5; padding: 7px 12px; border-radius: 999px;">
                      {job_count} new job{'' if job_count == 1 else 's'}
                    </div>
                  </td>
                </tr>
                <tr>
                  <td style="padding: 24px;">
                    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                      {cards_html}
                    </table>
                    <div style="font-family: Arial, sans-serif; font-size: 12px; line-height: 1.6; color: #6b7280; padding-top: 8px; border-top: 1px solid #e5e7eb;">
                      You&apos;re receiving this because you uploaded your resume to Job Agent.
                    </div>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
        </table>
      </body>
    </html>
    """


def _send_digest(email: str, user_id: int, jobs: List[dict]) -> None:
    """Send a multipart email digest for collected jobs."""
    if not SMTP_USER or not SMTP_PASSWORD or not SMTP_FROM:
        logger.warning("SMTP configuration is incomplete; cannot send email digest.")
        for job in jobs:
            alert_job_id = job.get("alert_job_id")
            if alert_job_id is not None:
                try:
                    record_notification(
                        user_id=user_id,
                        alert_job_id=alert_job_id,
                        channel="email",
                        status="failed",
                        error_msg="SMTP configuration is incomplete",
                    )
                except Exception:
                    logger.exception("Failed to record email configuration failure for job %s.", alert_job_id)
        return

    if not email or not isinstance(user_id, int) or not jobs:
        return

    subject = f"Your Daily Job Alert - {len(jobs)} new jobs found"
    plain_text_body = _format_plain_text_body(jobs)
    html_body = build_html_body(jobs)

    message = MIMEMultipart("alternative")
    message["Subject"] = subject
    message["From"] = SMTP_FROM
    message["To"] = email
    message.attach(MIMEText(plain_text_body, "plain", "utf-8"))
    message.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT, timeout=10) as smtp:
            smtp.login(SMTP_USER, SMTP_PASSWORD)
            smtp.send_message(message)

        for job in jobs:
            alert_job_id = job.get("alert_job_id")
            try:
                if alert_job_id is not None:
                    record_notification(
                        user_id=user_id,
                        alert_job_id=alert_job_id,
                        channel="email",
                        status="sent",
                    )
            except Exception:
                logger.exception("Failed to record email notification success for job %s.", alert_job_id)
    except Exception as exc:
        error_msg = str(exc)
        logger.error("Failed to send email digest to %s: %s", email, error_msg)
        for job in jobs:
            alert_job_id = job.get("alert_job_id")
            try:
                if alert_job_id is not None:
                    record_notification(
                        user_id=user_id,
                        alert_job_id=alert_job_id,
                        channel="email",
                        status="failed",
                        error_msg=error_msg,
                    )
            except Exception:
                logger.exception("Failed to record email notification failure for job %s.", alert_job_id)


def flush_email_digests(user_lookup: Dict[str, int]) -> None:
    """Send all queued email digests and clear the queue."""
    if not _email_queue:
        return

    for email, jobs in list(_email_queue.items()):
        user_id = user_lookup.get(email)
        if user_id is None:
            logger.warning("No user_id found for email %s when flushing digests.", email)
            continue
        try:
            _send_digest(email, user_id, jobs)
        except Exception:
            logger.exception("Unexpected error flushing email digest for %s.", email)

    _email_queue.clear()
