"""
Automation runner for Application Autofill Assist.

Launches a non-headless Playwright browser, detects the ATS platform for a
job URL, and delegates form filling to the matching adapter. The browser
window is left open under the user's control afterwards; nothing in this
module ever submits the form.
"""
import asyncio
import logging
import sys
from datetime import datetime, timezone
from typing import Optional

from playwright.async_api import async_playwright

from automation.adapters.base import ApplicantData, FillResult
from automation.adapters.greenhouse import GreenhouseAdapter
from automation.adapters.lever import LeverAdapter
from automation.platform_detector import detect_ats_platform

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ADAPTERS = {
    "greenhouse": GreenhouseAdapter,
    "lever": LeverAdapter,
}


def _log_run(job_id: Optional[int], platform: Optional[str], result: FillResult) -> None:
    """Log the outcome of an autofill run for debugging/auditing purposes."""
    logger.info(
        "Autofill run: job_id=%s platform=%s success=%s fields_filled=%s fields_skipped=%s error=%s timestamp=%s",
        job_id,
        platform,
        result.success,
        result.fields_filled,
        [f.field_name for f in result.fields_skipped],
        result.error,
        datetime.now(timezone.utc).isoformat(),
    )


async def run_autofill(job_url: str, applicant_data: ApplicantData, job_id: Optional[int] = None) -> FillResult:
    """
    Detect the ATS platform for `job_url` and autofill known applicant fields.

    Never clicks submit. Leaves the browser window open under the user's
    control on success so they can review and submit manually. Returns a
    `FillResult` describing what happened; never raises.

    Args:
        job_url: The job posting URL to autofill.
        applicant_data: Known applicant fields to fill into the form.
        job_id: Optional job identifier, used only for logging/auditing.

    Returns:
        A FillResult. `success=False` with a populated `error` covers both
        unsupported platforms (no browser is launched) and structural
        failures encountered while filling the form.
    """
    platform = detect_ats_platform(job_url)
    if platform is None:
        result = FillResult(success=False, error="Unsupported ATS platform: only Greenhouse and Lever are supported")
        _log_run(job_id, platform, result)
        return result

    # Playwright launches its driver via a subprocess, which asyncio's default
    # event loop on Windows (Selector, used by uvicorn for socket compat)
    # can't create - it raises NotImplementedError. Running the whole
    # Playwright session on a Proactor loop in a dedicated thread sidesteps
    # that without touching uvicorn's own loop policy.
    if sys.platform == "win32":
        return await asyncio.to_thread(_run_autofill_sync_on_proactor_loop, job_url, applicant_data, platform, job_id)

    return await _run_autofill(job_url, applicant_data, platform, job_id)


def _run_autofill_sync_on_proactor_loop(job_url: str, applicant_data: ApplicantData, platform: str, job_id: Optional[int]) -> FillResult:
    loop = asyncio.ProactorEventLoop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(_run_autofill(job_url, applicant_data, platform, job_id))
    finally:
        asyncio.set_event_loop(None)
        loop.close()


async def _run_autofill(job_url: str, applicant_data: ApplicantData, platform: str, job_id: Optional[int]) -> FillResult:
    adapter = ADAPTERS[platform]()

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=False)
        try:
            page = await browser.new_page()
            await page.goto(job_url, wait_until="domcontentloaded")

            try:
                result = await adapter.fill_application(page, applicant_data)
            except Exception as e:
                logger.error("Autofill form-fill failed for job_url=%s platform=%s: %s", job_url, platform, e)
                result = FillResult(
                    success=False,
                    error=f"Form structure has changed or a field could not be filled: {e}",
                )
        except Exception as e:
            logger.error("Autofill navigation failed for job_url=%s platform=%s: %s", job_url, platform, e)
            result = FillResult(success=False, error=f"Could not load the application page: {e}")
            await browser.close()
            _log_run(job_id, platform, result)
            return result

    _log_run(job_id, platform, result)
    return result
