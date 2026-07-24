"""
Application Autofill Assist API route.

Fills known applicant fields into a job's application form via Playwright,
then hands control back to the user in the opened browser window to review
and submit manually. Scoped intentionally to Greenhouse and Lever only; see
backend/automation/__init__.py for the full list of scope boundaries.
"""
import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from automation.adapters.base import ApplicantData
from automation.platform_detector import detect_ats_platform
from automation.runner import run_autofill
from utils.db import get_job_by_id, get_session_data

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["automation"])


def _build_applicant_data(job: dict, session_data: dict) -> ApplicantData:
    parsed_resume_data = session_data.get("parsed_resume_data") or {}
    return ApplicantData(
        name=parsed_resume_data.get("candidate_name") or session_data.get("candidate_name") or "",
        email=session_data.get("extracted_email") or parsed_resume_data.get("email") or "",
        phone=parsed_resume_data.get("phone") or session_data.get("phone"),
        location=parsed_resume_data.get("location") or session_data.get("location"),
        resume_path=job.get("resume_path") or session_data.get("resume_path"),
        cover_letter_path=job.get("cover_letter_path"),
        linkedin_url=parsed_resume_data.get("linkedin_url"),
    )


@router.get("/jobs/{job_id}/autofill-support")
async def get_autofill_support(job_id: int) -> JSONResponse:
    """Report whether this job's application form is on a supported ATS platform."""
    try:
        job = get_job_by_id(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        platform = detect_ats_platform(job.get("job_url") or "")
        return JSONResponse(status_code=200, content={"supported": platform is not None, "platform": platform})
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error checking autofill support for job %s: %s", job_id, e)
        raise HTTPException(status_code=500, detail="Error checking autofill support")


@router.post("/jobs/{job_id}/autofill")
async def autofill_application(job_id: int) -> JSONResponse:
    """
    Autofill known fields into this job's application form.

    Opens a visible browser window, fills what it can, and leaves the window
    open for the user to review and submit manually. Never submits on the
    user's behalf. Unsupported platforms are a normal 200 response with
    `success=False`, not an error.
    """
    try:
        job = get_job_by_id(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        job_url = job.get("job_url") or ""
        session_data = get_session_data(job.get("session_id")) or {}
        applicant_data = _build_applicant_data(job, session_data)

        logger.info("Starting autofill for job_id=%s", job_id)
        result = await run_autofill(job_url, applicant_data, job_id=job_id)

        return JSONResponse(status_code=200, content=result.model_dump())
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error running autofill for job %s: %s", job_id, e)
        raise HTTPException(status_code=500, detail="Error running autofill")
