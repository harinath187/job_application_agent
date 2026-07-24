"""
ATS platform detection for Application Autofill Assist.

Detects whether a job posting URL belongs to a supported ATS platform
(Greenhouse or Lever). Detection is intentionally conservative: URLs that
don't match a known pattern are reported as unsupported rather than guessed
at, since the autofill adapters are hand-built for these two platforms only.
"""
import logging
import re
from typing import Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GREENHOUSE_URL_PATTERNS = [
    re.compile(r"boards\.greenhouse\.io", re.IGNORECASE),
    re.compile(r"job-boards\.greenhouse\.io", re.IGNORECASE),
    re.compile(r"greenhouse\.io/embed/job_app", re.IGNORECASE),
]

LEVER_URL_PATTERNS = [
    re.compile(r"jobs\.lever\.co", re.IGNORECASE),
    re.compile(r"jobs\.eu\.lever\.co", re.IGNORECASE),
]

# Custom-domain company career pages sometimes proxy Greenhouse/Lever forms.
# The URL alone can't confirm these, so `detect_ats_platform` also accepts an
# optional page_html fallback to check for platform-specific embed markers.
GREENHOUSE_HTML_MARKERS = [
    re.compile(r"boards\.greenhouse\.io", re.IGNORECASE),
    re.compile(r"greenhouse\.io/embed/job_app", re.IGNORECASE),
    re.compile(r"grnhse_app", re.IGNORECASE),
]

LEVER_HTML_MARKERS = [
    re.compile(r"jobs\.lever\.co", re.IGNORECASE),
    re.compile(r"lever-jobs-partner", re.IGNORECASE),
]


def detect_ats_platform(job_url: str, page_html: Optional[str] = None) -> Optional[str]:
    """
    Detect which supported ATS platform (if any) a job posting URL belongs to.

    Args:
        job_url: The job posting URL.
        page_html: Optional page HTML/metadata, used as a fallback when the
            URL itself is inconclusive (e.g. a custom company career domain
            that embeds a Greenhouse or Lever form).

    Returns:
        "greenhouse", "lever", or None if the platform is unsupported/unknown.
    """
    if not job_url:
        return None

    for pattern in GREENHOUSE_URL_PATTERNS:
        if pattern.search(job_url):
            return "greenhouse"

    for pattern in LEVER_URL_PATTERNS:
        if pattern.search(job_url):
            return "lever"

    if page_html:
        for pattern in GREENHOUSE_HTML_MARKERS:
            if pattern.search(page_html):
                logger.info("Detected Greenhouse via page HTML fallback for url=%s", job_url)
                return "greenhouse"
        for pattern in LEVER_HTML_MARKERS:
            if pattern.search(page_html):
                logger.info("Detected Lever via page HTML fallback for url=%s", job_url)
                return "lever"

    return None
