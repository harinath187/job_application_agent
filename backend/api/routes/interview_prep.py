"""
Interview Prep API route - On-demand generation of interview prep for a job.

Generation is strictly on-demand: it is triggered only by an explicit POST for
a specific job_id, never automatically for every scraped job, to keep LLM
costs proportional to jobs the user actually cares about. Results are cached
in SQLite so repeat views (GET) never re-call the LLM.
"""
import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from agents.interview_prep_agent import generate_interview_prep
from utils.db import (
    get_job_by_id,
    get_session_data,
    get_interview_prep_by_job_id,
    upsert_interview_prep,
)


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["interview-prep"])


def _serialize(job_id: int, result: dict) -> dict:
    return {
        "job_id": job_id,
        "generated_at": result.get("generated_at"),
        "technical_questions": result.get("technical_questions", []),
        "behavioral_questions": result.get("behavioral_questions", []),
        "resume_specific_questions": result.get("resume_specific_questions", []),
        "suggested_talking_points": result.get("suggested_talking_points", {}),
        "source": result.get("source"),
    }


@router.post("/jobs/{job_id}/interview-prep")
async def create_interview_prep(job_id: int) -> JSONResponse:
    """
    Generate (or return the cached) interview prep result for a job.

    On-demand only: called explicitly by the user from the job detail page.
    """
    try:
        job = get_job_by_id(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        cached = get_interview_prep_by_job_id(job_id)
        if cached:
            logger.info("Interview prep cache hit for job_id=%s; skipping LLM call", job_id)
            return JSONResponse(status_code=200, content={"interview_prep": _serialize(job_id, cached), "cached": True})

        session_data = get_session_data(job.get("session_id")) or {}
        parsed_resume_data = session_data.get("parsed_resume_data") or {}
        resume_text = parsed_resume_data.get("resume_text", "")
        extracted_skills = parsed_resume_data.get("skills", [])
        projects = parsed_resume_data.get("projects") or session_data.get("projects") or []
        certifications = parsed_resume_data.get("certifications") or session_data.get("certifications") or []
        resume_sections = parsed_resume_data.get("resume_sections") or {}
        experience_summary = parsed_resume_data.get("experience") or session_data.get("experience")

        logger.info("Generating interview prep for job_id=%s (on-demand)", job_id)
        try:
            result = generate_interview_prep(
                resume_text=resume_text,
                extracted_skills=extracted_skills,
                job=job,
                projects=projects,
                certifications=certifications,
                resume_sections=resume_sections,
                experience_summary=experience_summary,
            )
        except Exception as e:
            logger.error("Interview prep generation raised for job_id=%s: %s", job_id, e)
            raise HTTPException(status_code=502, detail="Unable to generate interview prep at this time")

        upsert_interview_prep(job_id, result)
        return JSONResponse(status_code=200, content={"interview_prep": _serialize(job_id, result), "cached": False})
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error generating interview prep for job %s: %s", job_id, e)
        raise HTTPException(status_code=500, detail="Error generating interview prep")


@router.get("/jobs/{job_id}/interview-prep")
async def get_interview_prep(job_id: int) -> JSONResponse:
    """
    Fetch a previously generated interview prep result without regenerating it.
    Returns 404 if the job or a cached result doesn't exist.
    """
    try:
        job = get_job_by_id(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        cached = get_interview_prep_by_job_id(job_id)
        if not cached:
            raise HTTPException(status_code=404, detail="Interview prep has not been generated for this job yet")

        return JSONResponse(status_code=200, content={"interview_prep": _serialize(job_id, cached), "cached": True})
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error retrieving interview prep for job %s: %s", job_id, e)
        raise HTTPException(status_code=500, detail="Error retrieving interview prep")
