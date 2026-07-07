"""
Jobs API route - Retrieves job listings for a session.
"""
import logging
from typing import List, Literal
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from utils.db import (
    delete_search_history_item,
    delete_search_history_items,
    get_job,
    get_jobs as fetch_jobs_for_session,
    get_interview_prep,
    get_search_history,
    get_session_alert_status,
    get_session_status,
    get_skills_gap,
    insert_interview_prep,
    update_job_status,
)
from agents.pdf_parser import get_resume_text
from agents.interview_prep_agent import generate_prep


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["jobs"])


class JobResponse(BaseModel):
    """Response model for a job."""
    id: str
    session_id: str
    title: str
    company: str
    location: str
    job_url: str | None = None
    description: str
    resume_path: str = None
    cover_letter_path: str = None
    match_pct: int = 0
    missing_keywords: list[str] = Field(default_factory=list)
    status: str


class JobStatusUpdate(BaseModel):
    status: Literal["new", "applied", "interview", "rejected"]


class InterviewPrepRegenerateResponse(BaseModel):
    questions: list[dict]


@router.get("/search-history")
async def search_history() -> JSONResponse:
    """Return all saved search sessions."""
    try:
        history = get_search_history()
        return JSONResponse(status_code=200, content={"history": history, "count": len(history)})
    except Exception as e:
        logger.error("Error retrieving search history: %s", e)
        raise HTTPException(status_code=500, detail="Error retrieving search history")


@router.delete("/search-history/{session_id}")
async def delete_search_history(session_id: str) -> JSONResponse:
    """Delete one saved search session."""
    try:
        deleted = delete_search_history_item(session_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Search history item not found")
        return JSONResponse(status_code=200, content={"deleted": 1, "session_ids": [session_id]})
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error deleting search history item %s: %s", session_id, e)
        raise HTTPException(status_code=500, detail="Error deleting search history item")


@router.delete("/search-history")
async def delete_search_history_bulk(session_ids: List[str] = Query(..., description="Session IDs to delete")) -> JSONResponse:
    """Delete multiple saved search sessions."""
    try:
        deleted_count = delete_search_history_items(session_ids)
        return JSONResponse(status_code=200, content={"deleted": deleted_count, "session_ids": session_ids})
    except Exception as e:
        logger.error("Error deleting search history items %s: %s", session_ids, e)
        raise HTTPException(status_code=500, detail="Error deleting search history items")


@router.get("/search-history/{session_id}")
async def search_history_item(session_id: str) -> JSONResponse:
    """Return one saved search session."""
    try:
        history = get_search_history(session_id=session_id)
        if not history:
            raise HTTPException(status_code=404, detail="Search history item not found")
        jobs = fetch_jobs_for_session(session_id)
        session_status = get_session_status(session_id)
        alert_status = get_session_alert_status(session_id)
        return JSONResponse(
            status_code=200,
            content={
                "history": history[0],
                "jobs": jobs,
                "session_id": session_id,
                "status": session_status,
                **alert_status
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error retrieving search history item %s: %s", session_id, e)
        raise HTTPException(status_code=500, detail="Error retrieving search history item")


@router.get("/jobs")
async def list_jobs(session_id: str = Query(..., description="Session ID")) -> JSONResponse:
    """
    Retrieve all jobs for a given session with session status.
    
    Args:
        session_id: Session identifier
    
    Returns:
        JSON list of job objects with status and overall session status
    """
    try:
        jobs = fetch_jobs_for_session(session_id)
        session_status = get_session_status(session_id)
        alert_status = get_session_alert_status(session_id)
        
        # Determine overall status message
        status_message = "Processing..."
        if session_status == "complete":
            status_message = "Complete!"
        elif session_status == "failed":
            status_message = "Processing failed"
        elif session_status == "processing":
            # Count applied jobs to show progress
            completed_jobs = sum(1 for job in jobs if job.get("status") in {"applied", "interview"})
            total_jobs = len(jobs)
            if total_jobs > 0:
                status_message = f"Processing jobs ({completed_jobs}/{total_jobs})..."
            else:
                status_message = "Fetching jobs..."
        
        if not jobs:
            return JSONResponse(
                status_code=200,
                content={
                    "session_id": session_id,
                    "jobs": [],
                    "count": 0,
                    "status": status_message,
                    **alert_status
                }
            )
        
        # Format response
        job_list = []
        for job in jobs:
            job_list.append({
                "id": job.get("id"),
                "session_id": job.get("session_id"),
                "title": job.get("title"),
                "company": job.get("company"),
                "location": job.get("location"),
                "job_url": job.get("job_url"),
                "description": job.get("description", "")[:500],  # Truncate for response
                "resume_path": job.get("resume_path"),
                "cover_letter_path": job.get("cover_letter_path"),
                "salary_min": job.get("salary_min"),
                "salary_max": job.get("salary_max"),
                "salary_interval": job.get("salary_interval"),
                "match_pct": job.get("match_pct", 0),
                "missing_keywords": job.get("missing_keywords", []),
                "status": job.get("status", "new")
            })
        
        logger.info(f"Retrieved {len(job_list)} jobs for session {session_id}")
        
        return JSONResponse(
            status_code=200,
            content={
                "session_id": session_id,
                "jobs": job_list,
                "count": len(job_list),
                "status": status_message,
                **alert_status
            }
        )
    
    except Exception as e:
        logger.error(f"Error retrieving jobs for session {session_id}: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving jobs")


@router.get("/jobs/{job_id}")
async def get_job_detail(job_id: str) -> JSONResponse:
    """
    Retrieve a single job by its ID.
    
    Args:
        job_id: Job identifier
    
    Returns:
        JSON object containing the job data
    """
    try:
        job = get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        return JSONResponse(
            status_code=200,
            content={
                "job": {
                    "id": job.get("id"),
                    "session_id": job.get("session_id"),
                    "title": job.get("title"),
                    "company": job.get("company"),
                    "location": job.get("location"),
                    "job_url": job.get("job_url"),
                    "description": job.get("description", ""),
                    "resume_path": job.get("resume_path"),
                    "cover_letter_path": job.get("cover_letter_path"),
                    "salary_min": job.get("salary_min"),
                    "salary_max": job.get("salary_max"),
                    "salary_interval": job.get("salary_interval"),
                    "match_pct": job.get("match_pct", 0),
                    "missing_keywords": job.get("missing_keywords", []),
                    "status": job.get("status", "new")
                }
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving job {job_id}: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving job")


@router.get("/jobs/{job_id}/skills-gap")
async def get_job_skills_gap(job_id: str) -> JSONResponse:
    """Return the stored skills gap analysis for a single job."""
    try:
        gap = get_skills_gap(job_id)
        if not gap:
            return JSONResponse(
                status_code=200,
                content={
                    "missing_skills": [],
                    "transferable_skills": [],
                    "suggestions": []
                }
            )

        return JSONResponse(
            status_code=200,
            content={
                "missing_skills": gap.get("missing_skills", []),
                "transferable_skills": gap.get("transferable_skills", []),
                "suggestions": gap.get("suggestions", []),
            }
        )
    except Exception as e:
        logger.error("Error retrieving skills gap for job %s: %s", job_id, e)
        raise HTTPException(status_code=500, detail="Error retrieving skills gap")


@router.get("/jobs/{job_id}/interview-prep")
async def get_job_interview_prep(job_id: str) -> JSONResponse:
    """Return the stored interview prep questions for a single job."""
    try:
        prep = get_interview_prep(job_id)
        return JSONResponse(
            status_code=200,
            content={
                "questions": prep.get("questions", []) if prep else []
            }
        )
    except Exception as e:
        logger.error("Error retrieving interview prep for job %s: %s", job_id, e)
        raise HTTPException(status_code=500, detail="Error retrieving interview prep")


@router.post("/jobs/{job_id}/interview-prep/regenerate")
async def regenerate_job_interview_prep(job_id: str) -> JSONResponse:
    """Regenerate interview prep questions for a job."""
    try:
        job = get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        gap = get_skills_gap(job_id) or {}
        tailored_resume_summary = ""
        resume_path = job.get("resume_path")
        if resume_path:
            tailored_resume_summary = get_resume_text(resume_path)[:500]

        prep = generate_prep(
            job_description=job.get("description", ""),
            tailored_resume_summary=tailored_resume_summary,
            missing_skills=gap.get("missing_skills", []),
        )
        insert_interview_prep(job_id, prep.get("questions", []))
        return JSONResponse(status_code=200, content={"questions": prep.get("questions", [])})
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error regenerating interview prep for job %s: %s", job_id, e)
        raise HTTPException(status_code=500, detail="Error regenerating interview prep")


@router.patch("/jobs/{job_id}/status")
async def update_job_state(job_id: str, payload: JobStatusUpdate) -> JSONResponse:
    """Update a job application status."""
    try:
        update_job_status(job_id, payload.status)
        return JSONResponse(status_code=200, content={"ok": True})
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid status value")
    except Exception as e:
        logger.error("Error updating job %s status: %s", job_id, e)
        raise HTTPException(status_code=500, detail="Error updating job status")
