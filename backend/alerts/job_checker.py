"""
Alert job checker module for scheduler-driven job alerts.
"""
import hashlib
import logging
import os
from typing import Any, Dict, List, Optional

import httpx

from utils.db import (
    get_active_preferences,
    log_scheduler_run,
    reset_preference_expiry,
    upsert_alert_job,
)
from alerts.notifier_email import flush_email_digests, queue_email_digest
from alerts.notifier_telegram import send_telegram

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

SERPAPI_URL = "https://serpapi.com/search"
SERPAPI_KEY = os.getenv("SERPAPI_KEY")


def make_job_hash(title: str, company: str, location: str) -> str:
    """Return a deterministic SHA-256 hash for a job identity."""
    normalized = f"{title.strip().lower()}|{company.strip().lower()}|{location.strip().lower()}"
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


async def fetch_jobs_for_alert(role: str, location: str, keywords: str) -> List[Dict[str, Any]]:
    """Fetch job results from SerpApi and normalize them for alerting."""
    if not SERPAPI_KEY:
        logger.warning("SERPAPI_KEY not configured; alert job fetching is disabled.")
        return []

    query_parts = [part.strip() for part in [role, keywords] if part and part.strip()]
    query = " ".join(query_parts)
    if not query:
        return []

    params = {
        "engine": "google_jobs",
        "q": query,
        "location": location,
        "api_key": SERPAPI_KEY,
        "num": 10,
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(SERPAPI_URL, params=params)
            response.raise_for_status()
            data = response.json()
    except (httpx.RequestError, httpx.HTTPStatusError) as exc:
        logger.error("Failed to fetch alert jobs for query '%s': %s", query, exc)
        return []
    except ValueError as exc:
        logger.error("Invalid JSON returned from SerpApi for query '%s': %s", query, exc)
        return []

    jobs = []
    for raw in data.get("jobs_results", []):
        normalized = _normalize_alert_job(raw)
        if normalized:
            jobs.append(normalized)
    return jobs


def _normalize_alert_job(raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Normalize a SerpApi job result for alert storage."""
    if not isinstance(raw, dict):
        return None

    title = (raw.get("title") or "").strip()
    company = (raw.get("company_name") or "").strip()
    location = (raw.get("location") or "").strip()
    description_snippet = (raw.get("description") or "").strip()
    job_id_external = raw.get("job_id") or ""

    apply_options = raw.get("apply_options") or []
    related_links = raw.get("related_links") or []
    apply_url = ""

    if apply_options and isinstance(apply_options, list):
        first_apply = apply_options[0]
        if isinstance(first_apply, dict):
            apply_url = first_apply.get("link", "") or ""

    if not apply_url and related_links and isinstance(related_links, list):
        first_related = related_links[0]
        if isinstance(first_related, dict):
            apply_url = first_related.get("link", "") or ""

    return {
        "title": title,
        "company": company,
        "location": location,
        "apply_url": apply_url,
        "description_snippet": description_snippet,
        "job_id_external": job_id_external,
    }


async def run_alert_cycle() -> None:
    """Run the alert scheduler cycle across active preferences."""
    users_processed = 0
    new_jobs_found = 0
    notifications_sent = 0
    status = "success"
    error_msg = None

    try:
        preferences = get_active_preferences()
        users_processed = len(preferences)

        for pref in preferences:
            pref_id = pref.get("id")
            role = pref.get("role") or ""
            location = pref.get("location") or ""
            keywords = pref.get("keywords") or ""
            user_email = pref.get("email")
            user_id = pref.get("user_id")
            telegram_chat_id = pref.get("telegram_chat_id")

            jobs = await fetch_jobs_for_alert(role, location, keywords)
            new_jobs = []

            for job in jobs:
                job_hash = make_job_hash(job["title"], job["company"], job["location"])
                alert_job_id = upsert_alert_job(pref_id, job_hash, job)
                if alert_job_id:
                    job["alert_job_id"] = alert_job_id
                    job["user_id"] = user_id
                    new_jobs.append(job)

            if new_jobs:
                reset_preference_expiry(pref_id)
                new_jobs_found += len(new_jobs)

                notifications_sent += await send_telegram(telegram_chat_id, new_jobs)
                queue_email_digest(user_email, new_jobs)
                notifications_sent += 1 if user_email else 0

        flush_email_digests({
            pref.get("email"): pref.get("user_id")
            for pref in preferences
            if pref.get("email") and pref.get("user_id")
        })

    except Exception as exc:
        logger.exception("Alert cycle failed unexpectedly.")
        status = "failed"
        error_msg = str(exc)

    finally:
        log_scheduler_run(
            users_processed=users_processed,
            new_jobs_found=new_jobs_found,
            notifications_sent=notifications_sent,
            status=status,
            error_msg=error_msg,
        )
