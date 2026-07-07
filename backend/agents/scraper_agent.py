"""
Scraper Agent - Fetches job listings from SerpApi Google Jobs.
"""
import logging
import json
import os
import time
import random
from typing import Any

import requests
from dotenv import load_dotenv

from agents.salary_agent import enrich_salary


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()
SERPAPI_KEY = os.getenv("SERPAPI_KEY")
SERPAPI_URL = "https://serpapi.com/search"
MAX_POOL_SIZE = 50
MAX_RESULTS = 10
MIN_DESCRIPTION_LENGTH = 200
REQUEST_DELAY = 1.5


def extract_salary(job_row) -> dict | None:
    """
    Returns {"min": int, "max": int, "interval": str} if JobSpy provided salary data,
    otherwise None. Checks min_amount/max_amount/interval columns on the DataFrame row.
    """
    if job_row is None:
        return None

    def _get_value(key: str):
        if isinstance(job_row, dict):
            return job_row.get(key)
        return getattr(job_row, key, None)

    min_amount = _get_value("min_amount")
    max_amount = _get_value("max_amount")
    interval = _get_value("interval")

    if min_amount is None and max_amount is None and not interval:
        return None

    try:
        min_val = int(float(min_amount)) if min_amount not in (None, "") else None
    except (TypeError, ValueError):
        min_val = None

    try:
        max_val = int(float(max_amount)) if max_amount not in (None, "") else None
    except (TypeError, ValueError):
        max_val = None

    interval_text = str(interval).strip().lower() if interval else ""
    if interval_text not in {"yearly", "monthly", "hourly"}:
        interval_text = ""

    if min_val is None and max_val is None and not interval_text:
        return None

    payload = {}
    if min_val is not None:
        payload["min"] = min_val
    if max_val is not None:
        payload["max"] = max_val
    if interval_text:
        payload["interval"] = interval_text
    return payload or None


def run_scraper_agent(state: dict[str, Any]) -> dict[str, Any]:
    role = state.get("extracted_role", "").strip()
    location = state.get("extracted_location", "").strip()
    experience_years = state.get("extracted_experience_years", 0)
    experience = state.get("user_experience") or state.get("extracted_experience")
    if not role:
        return {**state, "jobs": []}

    jobs = _fetch_jobs(_build_query(role, location, experience), wanted=MAX_RESULTS, candidate_experience_years=experience_years)
    logger.info("Fetched %s jobs for %s in %s", len(jobs), role, location)
    return {**state, "jobs": jobs}


def _experience_keyword(experience: str | None) -> str:
    """Map the provided experience text to a search-friendly keyword."""
    normalized = (experience or "").strip().lower()
    if not normalized:
        return ""
    if "entry" in normalized or "intern" in normalized or "fresher" in normalized:
        return "entry level"
    if "1-3" in normalized or "1 to 3" in normalized or "junior" in normalized:
        return "junior"
    if "3-5" in normalized or "3 to 5" in normalized or "mid" in normalized:
        return "mid level"
    if "5+" in normalized or "5 plus" in normalized or "senior" in normalized:
        return "senior"
    return experience.strip()


def _build_query(role: str, location: str, experience: str | None = None) -> str:
    """Build the SerpApi query string while keeping experience optional."""
    query_parts = [part.strip() for part in [role, _experience_keyword(experience), location] if part and part.strip()]
    return " ".join(query_parts).strip()


def scrape_jobs(role: str, location: str, candidate_experience_years: int = 999, experience: str | None = None) -> list[dict]:
    if not SERPAPI_KEY:
        logger.warning("SERPAPI_KEY not configured; job scraping is disabled. Returning empty job list.")
        return []

    query = _build_query(role, location, experience)
    if not query:
        return []
    return _fetch_jobs(query, wanted=MAX_RESULTS, candidate_experience_years=candidate_experience_years)


def _fetch_jobs(query: str, wanted: int, candidate_experience_years: int = 999) -> list[dict]:
    collected = []
    seen_keys = set()
    next_page_token = None

    # Collect a larger pool of jobs (up to MAX_POOL_SIZE)
    while len(collected) < MAX_POOL_SIZE:
        params = {
            "engine": "google_jobs",
            "q": query,
            "hl": "en",
            "api_key": SERPAPI_KEY,
        }
        if next_page_token:
            params["next_page_token"] = next_page_token

        try:
            resp = requests.get(SERPAPI_URL, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except requests.RequestException as request_error:
            logger.error(f"Job scraping failed for query '{query}': {request_error}")
            return []
        except ValueError as decode_error:
            logger.error(f"Job scraping returned invalid JSON for query '{query}': {decode_error}")
            return []

        for raw in data.get("jobs_results", []):
            job = _normalise(raw)
            if _is_usable(job, seen_keys, candidate_experience_years):
                collected.append(job)
            if len(collected) >= MAX_POOL_SIZE:
                break

        next_page_token = data.get("serpapi_pagination", {}).get("next_page_token")
        if not next_page_token:
            break
        time.sleep(REQUEST_DELAY)

    # Weighted random selection based on SerpApi ranking (higher ranked = higher probability)
    if len(collected) > wanted:
        weights = [max(1, len(collected) - idx) for idx in range(len(collected))]
        selected = random.choices(collected, weights=weights, k=wanted)
        # Deduplicate the selected jobs
        deduped = []
        dedup_keys = set()
        for job in selected:
            key = (job["title"].lower(), job["company"].lower())
            if key not in dedup_keys:
                dedup_keys.add(key)
                deduped.append(job)
        # Ensure we have exactly MAX_RESULTS jobs
        return deduped[:MAX_RESULTS]
    
    return collected[:wanted]


def _normalise(raw: dict) -> dict:
    import re
    
    apply_options = raw.get("apply_options", [])
    url = apply_options[0].get("link", "") if apply_options else ""
    description = raw.get("description", "").strip()
    
    # Extract experience requirement from job description
    required_experience = None
    if description:
        patterns = [
            r"(\d+)\+?\s*(?:to\s+\d+)?\s*years",
            r"minimum\s+(\d+)\s*years",
            r"(\d+)\s*years?\s*(?:of\s+|experience)",
        ]
        for pattern in patterns:
            match = re.search(pattern, description, re.IGNORECASE)
            if match:
                try:
                    required_experience = int(match.group(1))
                    break
                except (ValueError, IndexError):
                    continue
    
    salary = extract_salary(raw)
    if salary is None:
        try:
            salary = enrich_salary(raw.get("title", ""), raw.get("location", ""))
        except Exception:
            salary = None

    return {
        "title": raw.get("title", "").strip(),
        "company": raw.get("company_name", "").strip(),
        "location": raw.get("location", "").strip(),
        "description": description,
        "url": url,
        "job_url": url,
        "source": "google_jobs",
        "job_id": raw.get("job_id", ""),
        "required_experience_years": required_experience,
        "salary": salary,
    }


def _is_usable(job: dict, seen_keys: set, candidate_experience_years: int = 999) -> bool:
    key = (job["title"].lower(), job["company"].lower())
    if key in seen_keys:
        return False
    seen_keys.add(key)
    
    # Basic checks
    if not (bool(job["title"]) and bool(job["company"]) and len(job["description"]) >= MIN_DESCRIPTION_LENGTH):
        return False
    
    # Experience level check: filter out jobs requiring significantly more experience
    required_experience = job.get("required_experience_years")
    if required_experience is not None and required_experience > candidate_experience_years + 2:
        logger.info(f"Filtering out {job['title']} at {job['company']}: requires {required_experience} years, candidate has {candidate_experience_years}")
        return False
    
    return True


if __name__ == "__main__":
    result = run_scraper_agent(
        {
            "extracted_role": os.getenv("SCRAPER_TEST_ROLE", "software engineer"),
            "extracted_location": os.getenv("SCRAPER_TEST_LOCATION", "United States"),
        }
    )
    print(json.dumps(result["jobs"], indent=2))
