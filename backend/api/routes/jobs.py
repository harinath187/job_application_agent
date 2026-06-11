"""
Jobs API route - Retrieves job listings for a session.
"""
import logging
from typing import List
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from utils.db import (
    delete_search_history_item,
    delete_search_history_items,
    get_job_by_id,
    get_jobs_by_session,
    get_search_history,
    get_session_alert_status,
    get_session_status,
)


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["jobs"])


class JobResponse(BaseModel):
    """Response model for a job."""
    id: int
    session_id: str
    title: str
    company: str
    location: str
    job_url: str
    description: str
    resume_path: str = None
    cover_letter_path: str = None
    status: str


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
        jobs = get_jobs_by_session(session_id)
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
async def get_jobs(session_id: str = Query(..., description="Session ID")) -> JSONResponse:
    """
    Retrieve all jobs for a given session with session status.
    
    Args:
        session_id: Session identifier
    
    Returns:
        JSON list of job objects with status and overall session status
    """
    try:
        jobs = get_jobs_by_session(session_id)
        session_status = get_session_status(session_id)
        alert_status = get_session_alert_status(session_id)
        
        # Determine overall status message
        status_message = "Processing..."
        if session_status == "complete":
            status_message = "Complete!"
        elif session_status == "failed":
            status_message = "Processing failed"
        elif session_status == "processing":
            # Count completed jobs to show progress
            completed_jobs = sum(1 for job in jobs if job.get("status") == "complete")
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
                "status": job.get("status", "pending")
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
async def get_job_detail(job_id: int) -> JSONResponse:
    """
    Retrieve a single job by its ID.
    
    Args:
        job_id: Job identifier
    
    Returns:
        JSON object containing the job data
    """
    try:
        job = get_job_by_id(job_id)
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
                    "status": job.get("status", "pending")
                }
            }
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving job {job_id}: {e}")
        raise HTTPException(status_code=500, detail="Error retrieving job")
