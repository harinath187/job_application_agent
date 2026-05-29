"""
Jobs API route - Retrieves job listings for a session.
"""
import logging
from typing import List
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from utils.db import get_job_by_id, get_jobs_by_session


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


@router.get("/jobs")
async def get_jobs(session_id: str = Query(..., description="Session ID")) -> JSONResponse:
    """
    Retrieve all jobs for a given session.
    
    Args:
        session_id: Session identifier
    
    Returns:
        JSON list of job objects with status
    """
    try:
        jobs = get_jobs_by_session(session_id)
        
        if not jobs:
            return JSONResponse(
                status_code=200,
                content={
                    "session_id": session_id,
                    "jobs": [],
                    "count": 0
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
                "count": len(job_list)
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
