"""
Scraper Agent - Fetches job listings from SerpApi Google Jobs.
"""
import logging
import json
import os
import re
import time
import random
from typing import Any

import requests
from dotenv import load_dotenv


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()
SERPAPI_KEY = os.getenv("SERPAPI_KEY")
SERPAPI_URL = "https://serpapi.com/search"
MAX_POOL_SIZE = 50
MAX_RESULTS = 10
MIN_DESCRIPTION_LENGTH = 200
REQUEST_DELAY = 1.5


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
        logger.warning("SERPAPI_KEY not configured; job scraping is disabled. Returning mock job list for development.")
        return _mock_jobs(role=role, location=location, wanted=MAX_RESULTS)

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


def _mock_jobs(role: str, location: str, wanted: int = 5) -> list[dict]:
    """Return a small set of deterministic mock jobs for development when SerpApi key is missing."""
    role_short = (role or "Software Engineer").strip() or "Software Engineer"
    location_short = (location or "Remote").strip() or "Remote"
    samples = []
    for i in range(1, wanted + 1):
        samples.append({
            "title": f"{role_short} ({i})",
            "company": f"ExampleCorp {i}",
            "location": location_short,
            "description": f"This is a mock job description for {role_short} at ExampleCorp {i}. " * 10,
            "url": f"https://example.com/jobs/{i}",
            "job_url": f"https://example.com/jobs/{i}",
            "source": "mock",
            "job_id": f"mock-{i}",
            "required_experience_years": None,
        })
    return samples[:wanted]


def _clean_description(description: str) -> str:
    """
    Normalize whitespace and formatting from a raw scraped job description.

    Google Jobs / SerpApi descriptions frequently contain excessive blank
    lines, inconsistent line endings, and trailing whitespace on individual
    lines. This function cleans that up without altering the actual wording
    of the description.
    """
    if not description:
        return ""

    text = description

    # Normalize different line-ending styles to a single "\n"
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Strip trailing whitespace from each individual line
    text = "\n".join(line.rstrip() for line in text.split("\n"))

    # Collapse 3+ consecutive blank lines down to a single blank line (max)
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Collapse runs of 2+ spaces/tabs (not newlines) into a single space
    text = re.sub(r"[ \t]{2,}", " ", text)

    # Remove leading/trailing whitespace on the whole string
    return text.strip()


def _bulletize_description(description: str) -> str:
    """
    Optional secondary pass: convert common bullet markers (•, -, *, numbered
    lists) that SerpApi sometimes embeds as literal characters into consistent
    "- " bullet lines, one per line. Safe to call after _clean_description.
    """
    if not description:
        return ""

    # Insert a newline before bullet-like markers that appear mid-line
    # e.g. "...responsibilities: • Develop • Design" -> separate lines
    text = re.sub(r"\s*[•▪●○]\s*", "\n- ", description)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _normalise(raw: dict) -> dict:
    apply_options = raw.get("apply_options", [])
    url = apply_options[0].get("link", "") if apply_options else ""

    raw_description = raw.get("description", "")
    description = _clean_description(raw_description)

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