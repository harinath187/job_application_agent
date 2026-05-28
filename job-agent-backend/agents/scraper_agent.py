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
    if not role:
        return {**state, "jobs": []}

    jobs = _fetch_jobs(f"{role} {location}".strip(), wanted=MAX_RESULTS)
    logger.info("Fetched %s jobs for %s in %s", len(jobs), role, location)
    return {**state, "jobs": jobs}


def scrape_jobs(role: str, location: str) -> list[dict]:
    query = f"{role.strip()} {location.strip()}".strip()
    if not query:
        return []
    return _fetch_jobs(query, wanted=MAX_RESULTS)


def _fetch_jobs(query: str, wanted: int) -> list[dict]:
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

        resp = requests.get(SERPAPI_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        for raw in data.get("jobs_results", []):
            job = _normalise(raw)
            if _is_usable(job, seen_keys):
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
    apply_options = raw.get("apply_options", [])
    url = apply_options[0].get("link", "") if apply_options else ""
    return {
        "title": raw.get("title", "").strip(),
        "company": raw.get("company_name", "").strip(),
        "location": raw.get("location", "").strip(),
        "description": raw.get("description", "").strip(),
        "url": url,
        "job_url": url,
        "source": "google_jobs",
        "job_id": raw.get("job_id", ""),
    }


def _is_usable(job: dict, seen_keys: set) -> bool:
    key = (job["title"].lower(), job["company"].lower())
    if key in seen_keys:
        return False
    seen_keys.add(key)
    return (
        bool(job["title"])
        and bool(job["company"])
        and len(job["description"]) >= MIN_DESCRIPTION_LENGTH
    )


if __name__ == "__main__":
    result = run_scraper_agent(
        {
            "extracted_role": os.getenv("SCRAPER_TEST_ROLE", "software engineer"),
            "extracted_location": os.getenv("SCRAPER_TEST_LOCATION", "United States"),
        }
    )
    print(json.dumps(result["jobs"], indent=2))
