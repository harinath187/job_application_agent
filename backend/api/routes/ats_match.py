"""
ATS Match API route - On-demand job-fit scoring for a specific job (Part 2 of
the ATS Score feature).

Mirrors backend/api/routes/interview_prep.py: generation is strictly
on-demand, triggered only by an explicit POST for a specific job_id, and
results are cached in SQLite so repeat views (GET) never re-run the scoring
(and never re-call the LLM).
"""
import logging
from datetime import datetime
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from utils.ats_scorer import compute_ats_match_score
from utils.db import (
    get_job_by_id,
    get_session_data,
    get_ats_match_by_job_id,
    upsert_ats_match,
)


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["ats-match"])


def _serialize(job_id: int, result: dict) -> dict:
    return {
        "job_id": job_id,
        "generated_at": result.get("generated_at"),
        "matched_keywords": result.get("matched_keywords", []),
        "missing_keywords": result.get("missing_keywords", []),
        "match_score": result.get("match_score", 0),
        "notes": result.get("notes"),
        "source": result.get("source"),
    }


@router.post("/jobs/{job_id}/ats-match")
async def create_ats_match(job_id: int) -> JSONResponse:
    """
    Compute (or return the cached) ATS match result for a job.

    On-demand only: called explicitly by the user from the job detail page.
    LLM failures inside compute_ats_match_score never raise (they fall back
    to a keyword-only score), so this endpoint only 5xx's on unexpected bugs.
    """
    try:
        job = get_job_by_id(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        cached = get_ats_match_by_job_id(job_id)
        if cached:
            logger.info("ATS match cache hit for job_id=%s; skipping recomputation", job_id)
            return JSONResponse(status_code=200, content={"ats_match": _serialize(job_id, cached), "cached": True})

        session_data = get_session_data(job.get("session_id")) or {}
        parsed_resume_data = session_data.get("parsed_resume_data") or {}
        resume_text = parsed_resume_data.get("resume_text", "")
        extracted_skills = parsed_resume_data.get("skills", [])

        logger.info("Computing ATS match for job_id=%s (on-demand)", job_id)
        try:
            match_result = compute_ats_match_score(
                resume_text=resume_text,
                extracted_skills=extracted_skills,
                job_description=job.get("description", ""),
            )
        except Exception as e:
            logger.error("ATS match computation raised for job_id=%s: %s", job_id, e)
            raise HTTPException(status_code=502, detail="Unable to compute ATS match at this time")

        result = match_result.to_dict()
        result["generated_at"] = datetime.utcnow().isoformat()

        upsert_ats_match(job_id, result)
        return JSONResponse(status_code=200, content={"ats_match": _serialize(job_id, result), "cached": False})
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error computing ATS match for job %s: %s", job_id, e)
        raise HTTPException(status_code=500, detail="Error computing ATS match")


@router.get("/jobs/{job_id}/ats-match")
async def get_ats_match(job_id: int) -> JSONResponse:
    """
    Fetch a previously computed ATS match result without recomputing it.
    Returns 404 if the job or a cached result doesn't exist.
    """
    try:
        job = get_job_by_id(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        cached = get_ats_match_by_job_id(job_id)
        if not cached:
            raise HTTPException(status_code=404, detail="ATS match has not been computed for this job yet")

        return JSONResponse(status_code=200, content={"ats_match": _serialize(job_id, cached), "cached": True})
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error retrieving ATS match for job %s: %s", job_id, e)
        raise HTTPException(status_code=500, detail="Error retrieving ATS match")
