"""
ATS Job Fetcher - Pulls live job postings directly from Greenhouse and Lever
job boards, for apply links SerpApi's Google Jobs results point at.

SerpApi's `apply_options` links often go straight to a company's Greenhouse
or Lever board rather than the aggregator itself. Both platforms expose
public, no-auth JSON APIs for their job boards, so once a link is recognized
as one of the two, the richer/most current listing data can be pulled
directly instead of relying on whatever SerpApi already scraped.

Only Greenhouse and Lever are supported; any other link (LinkedIn,
ZipRecruiter, a custom company careers page, etc.) is reported as
unsupported rather than guessed at.
"""
import logging
import re
from typing import Any, Optional

import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GREENHOUSE_URL_PATTERN = re.compile(
    r"(?:boards|job-boards)\.greenhouse\.io/([^/?#]+)(?:/jobs/([^/?#]+))?", re.IGNORECASE
)
LEVER_URL_PATTERN = re.compile(
    r"jobs(?:\.\w+)?\.lever\.co/([^/?#]+)(?:/([^/?#]+))?", re.IGNORECASE
)

GREENHOUSE_JOBS_API_URL = "https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs"
LEVER_POSTINGS_API_URL = "https://api.lever.co/v0/postings/{company_slug}"

REQUEST_TIMEOUT_SECONDS = 15


def detect_ats_source(url: str) -> dict[str, Optional[str]]:
    """
    Detect whether `url` is a Greenhouse or Lever job link, and pull out the
    identifier needed to call that platform's public jobs API.

    Args:
        url: A job apply link, e.g. from SerpApi's `apply_options`.

    Returns:
        A dict with:
          - platform: "greenhouse", "lever", or "unsupported"
          - identifier: the Greenhouse board token or Lever company slug,
            or None if unsupported
          - posting_id: the specific job/posting id embedded in the URL
            (if present), used to pick one job out of the full board listing
    """
    if not url:
        return {"platform": "unsupported", "identifier": None, "posting_id": None}

    greenhouse_match = GREENHOUSE_URL_PATTERN.search(url)
    if greenhouse_match:
        return {
            "platform": "greenhouse",
            "identifier": greenhouse_match.group(1),
            "posting_id": greenhouse_match.group(2),
        }

    lever_match = LEVER_URL_PATTERN.search(url)
    if lever_match:
        return {
            "platform": "lever",
            "identifier": lever_match.group(1),
            "posting_id": lever_match.group(2),
        }

    return {"platform": "unsupported", "identifier": None, "posting_id": None}


def _normalize_greenhouse_job(raw: dict[str, Any]) -> dict[str, Any]:
    departments = raw.get("departments") or []
    department = ", ".join(d.get("name", "") for d in departments if d.get("name"))
    return {
        "id": str(raw.get("id", "")),
        "title": (raw.get("title") or "").strip(),
        "location": (raw.get("location") or {}).get("name", ""),
        "applyUrl": raw.get("absolute_url", ""),
        "description": raw.get("content", ""),
        "department": department,
    }


def _normalize_lever_job(raw: dict[str, Any]) -> dict[str, Any]:
    categories = raw.get("categories") or {}
    return {
        "id": str(raw.get("id", "")),
        "title": (raw.get("text") or "").strip(),
        "location": categories.get("location", ""),
        "applyUrl": raw.get("hostedUrl") or raw.get("applyUrl", ""),
        "description": raw.get("descriptionPlain") or raw.get("description", ""),
        "department": categories.get("department", ""),
    }


def fetch_greenhouse_jobs(board_token: str) -> list[dict[str, Any]]:
    """
    Fetch every open posting on a Greenhouse board.

    Returns an empty list (never raises) if the board token is invalid (404)
    or the request fails, so a batch job enriching many links can continue
    past a single bad one.
    """
    url = GREENHOUSE_JOBS_API_URL.format(board_token=board_token)
    try:
        response = requests.get(url, params={"content": "true"}, timeout=REQUEST_TIMEOUT_SECONDS)
        if response.status_code == 404:
            logger.warning("Greenhouse board not found for token=%s", board_token)
            return []
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as request_error:
        logger.error("Greenhouse jobs fetch failed for token=%s: %s", board_token, request_error)
        return []
    except ValueError as decode_error:
        logger.error("Greenhouse jobs fetch returned invalid JSON for token=%s: %s", board_token, decode_error)
        return []

    return [_normalize_greenhouse_job(raw) for raw in data.get("jobs", [])]


def fetch_lever_jobs(company_slug: str) -> list[dict[str, Any]]:
    """
    Fetch every open posting on a Lever board.

    Returns an empty list (never raises) if the company slug is invalid
    (404) or the request fails, so a batch job enriching many links can
    continue past a single bad one.
    """
    url = LEVER_POSTINGS_API_URL.format(company_slug=company_slug)
    try:
        response = requests.get(url, params={"mode": "json"}, timeout=REQUEST_TIMEOUT_SECONDS)
        if response.status_code == 404:
            logger.warning("Lever board not found for slug=%s", company_slug)
            return []
        response.raise_for_status()
        data = response.json()
    except requests.RequestException as request_error:
        logger.error("Lever jobs fetch failed for slug=%s: %s", company_slug, request_error)
        return []
    except ValueError as decode_error:
        logger.error("Lever jobs fetch returned invalid JSON for slug=%s: %s", company_slug, decode_error)
        return []

    if not isinstance(data, list):
        logger.error("Lever jobs fetch returned an unexpected payload shape for slug=%s", company_slug)
        return []

    return [_normalize_lever_job(raw) for raw in data]


def _find_matching_job(jobs: list[dict[str, Any]], apply_url: str, posting_id: Optional[str]) -> Optional[dict[str, Any]]:
    if posting_id:
        for job in jobs:
            if job["id"] == posting_id:
                return job
    for job in jobs:
        if job.get("applyUrl") and job["applyUrl"] == apply_url:
            return job
    return None


def get_job_details(apply_url: str) -> Optional[dict[str, Any]]:
    """
    Resolve a single apply link to its normalized Greenhouse/Lever job.

    Detects the platform, fetches the full board listing, and returns the
    one posting matching `apply_url` (by posting id if the URL has one,
    otherwise by exact apply URL). Returns None if the platform isn't
    Greenhouse/Lever, the board can't be fetched, or no matching posting is
    found on the board.
    """
    source = detect_ats_source(apply_url)
    if source["platform"] == "unsupported":
        return None

    if source["platform"] == "greenhouse":
        jobs = fetch_greenhouse_jobs(source["identifier"])
    else:
        jobs = fetch_lever_jobs(source["identifier"])

    if not jobs:
        return None

    return _find_matching_job(jobs, apply_url, source.get("posting_id"))
