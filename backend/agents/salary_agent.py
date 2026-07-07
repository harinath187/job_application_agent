"""Enriches jobs missing salary data using SerpApi Google Jobs results."""

from __future__ import annotations

import os
import logging
from typing import Any

import requests


logger = logging.getLogger(__name__)
SERPAPI_URL = "https://serpapi.com/search.json"


def enrich_salary(job_title: str, location: str) -> dict | None:
    """
    Enrich a job title/location with salary data from SerpApi.

    Parameters:
        job_title: Job title to search.
        location: Location to search.

    Returns:
        {"min": int, "max": int, "interval": str} or None when unavailable.
    """
    api_key = os.environ.get("SERPAPI_KEY")
    if not api_key:
        return None

    params = {
        "engine": "google_jobs",
        "q": f"{job_title} {location}".strip(),
        "hl": "en",
        "api_key": api_key,
    }

    try:
        response = requests.get(SERPAPI_URL, params=params, timeout=15)
        response.raise_for_status()
        data = response.json()
    except Exception:
        return None

    for job in data.get("jobs_results", []):
        salary = _extract_salary(job)
        if salary:
            return salary
    return None


def _extract_salary(job: dict[str, Any]) -> dict | None:
    salary_info = job.get("salary")
    if isinstance(salary_info, dict):
        min_val = _safe_int(salary_info.get("min"))
        max_val = _safe_int(salary_info.get("max"))
        interval = _normalize_interval(salary_info.get("interval"))
        if min_val is not None or max_val is not None or interval:
            payload = {}
            if min_val is not None:
                payload["min"] = min_val
            if max_val is not None:
                payload["max"] = max_val
            if interval:
                payload["interval"] = interval
            return payload

    return None


def _safe_int(value: Any) -> int | None:
    try:
        return int(float(str(value).replace(",", "").strip()))
    except (TypeError, ValueError):
        return None


def _normalize_interval(value: Any) -> str:
    interval = str(value or "").strip().lower()
    if interval in {"year", "yearly", "annual", "annually"}:
        return "yearly"
    if interval in {"month", "monthly"}:
        return "monthly"
    if interval in {"hour", "hourly"}:
        return "hourly"
    return ""
