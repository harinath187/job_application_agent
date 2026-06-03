"""
Email notifier for alert digests.
"""
import logging
import os
import smtplib
from email.message import EmailMessage
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


def _send_digest(email: str, user_id: int, jobs: List[dict]) -> None:
    """Send a plain-text email digest for collected jobs."""
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

    subject = f"Your Daily Job Alert — {len(jobs)} new jobs found"
    lines = [
        f"{job.get('title', '').strip()} at {job.get('company', '').strip()} ({job.get('location', '').strip()}) → {job.get('apply_url', '').strip()}"
        for job in jobs
    ]
    body = "\n".join(lines)

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = SMTP_FROM
    message["To"] = email
    message.set_content(body)

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
