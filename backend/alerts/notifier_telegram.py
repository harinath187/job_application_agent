"""
Telegram notifier for alert jobs.
"""
import logging
import os
from typing import Any, Dict, List

import httpx

from utils.db import record_notification

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_API_URL = "https://api.telegram.org"


def _escape_markdown(text: str) -> str:
    """Escape Markdown special characters in text."""
    if text is None:
        return ""
    replacements = {
        "_": "\\_",
        "*": "\\*",
        "[": "\\[",
        "]": "\\]",
        "(`": "\\(`",
        ")": "\\)",
        "~": "\\~",
        "`": "\\`",
        ">": "\\>",
        "#": "\\#",
        "+": "\\+",
        "-": "\\-",
        "=": "\\=",
        "|": "\\|",
        "{": "\\{",
        "}": "\\}",
    }
    escaped = text
    for char, replacement in replacements.items():
        escaped = escaped.replace(char, replacement)
    return escaped


async def send_telegram(telegram_chat_id: str, jobs: List[Dict[str, Any]]) -> int:
    """Send Telegram messages for each new job alert."""
    if not TELEGRAM_BOT_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN not configured; Telegram notifications are disabled.")
        return 0

    if not telegram_chat_id:
        logger.warning("Telegram chat ID is missing; skipping Telegram notifications.")
        return 0

    if not jobs:
        return 0

    messages_sent = 0
    url = f"{TELEGRAM_API_URL}/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    async with httpx.AsyncClient(timeout=10.0) as client:
        for job in jobs:
            title = _escape_markdown(str(job.get("title", "")).strip())
            company = _escape_markdown(str(job.get("company", "")).strip())
            location = _escape_markdown(str(job.get("location", "")).strip())
            apply_url = str(job.get("apply_url", "")).strip()
            user_id = job.get("user_id")
            alert_job_id = job.get("alert_job_id")

            text = (
                "🆕 *New Job Alert!*\n"
                f"*{title}* at *{company}*\n"
                f"📍 {location}\n"
                f"🔗 [Apply Here]({apply_url})"
            )

            payload = {
                "chat_id": telegram_chat_id,
                "text": text,
                "parse_mode": "Markdown",
            }

            try:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                record_notification(
                    user_id=user_id,
                    alert_job_id=alert_job_id,
                    channel="telegram",
                    status="sent",
                )
                messages_sent += 1
            except Exception as exc:
                error_msg = str(exc)
                logger.error("Failed to send Telegram alert to %s: %s", telegram_chat_id, error_msg)
                try:
                    record_notification(
                        user_id=user_id,
                        alert_job_id=alert_job_id,
                        channel="telegram",
                        status="failed",
                        error_msg=error_msg,
                    )
                except Exception:
                    logger.exception("Failed to record Telegram notification failure for job %s.", alert_job_id)
                continue

    return messages_sent
