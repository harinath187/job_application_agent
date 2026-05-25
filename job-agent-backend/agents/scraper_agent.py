"""
Scraper Agent - Scrapes job listings using python-jobspy.
"""
import logging
from typing import List, Dict, Any
import jobspy


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def scrape_jobs(role: str, location: str) -> List[Dict[str, Any]]:
    """
    Scrape job listings from multiple job boards.
    
    Args:
        role: Job title or role to search for
        location: Location to search in
    
    Returns:
        List of job dictionaries with keys: title, company, location, description, job_url
    """
    try:
        # Scrape jobs using jobspy
        jobs = jobspy.scrape_jobs(
            site_name=["linkedin", "indeed", "naukri"],
            search_term=role,
            location=location,
            results_wanted=10,
            hours_old=72,
            country_indeed="US"
        )
        
        # Convert DataFrame to list of dicts and filter out empty descriptions
        results = []
        for _, job in jobs.iterrows():
            job_dict = job.to_dict()
            
            # Filter out jobs with null or empty descriptions
            if not job_dict.get("job_description") or str(job_dict.get("job_description", "")).strip() == "":
                continue
            
            # Build standardized job object
            standardized_job = {
                "title": str(job_dict.get("job_title", "")) or "Unknown",
                "company": str(job_dict.get("company", "")) or "Unknown",
                "location": str(job_dict.get("location", "")) or location,
                "description": str(job_dict.get("job_description", "")),
                "job_url": str(job_dict.get("job_url", "")) or ""
            }
            results.append(standardized_job)
        
        logger.info(f"Scraped {len(results)} jobs for {role} in {location}")
        return results
    
    except Exception as e:
        logger.error(f"Error scraping jobs: {e}")
        return []
