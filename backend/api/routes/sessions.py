"""
Session API route - handles resume experience input and pipeline resumption.
"""
import logging
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from orchestrator.graph import resume_from_scraper_node
from utils.db import get_session_status, set_session_status


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["sessions"])

ALLOWED_EXPERIENCE_LEVELS = {"fresher", "1-2", "3-5", "5+"}


class ExperienceUpdateRequest(BaseModel):
    experience_level: str


def _resume_pipeline(session_id: str, experience_level: str) -> None:
    try:
        result = resume_from_scraper_node(session_id, experience_level)
        final_status = "completed" if result.get("jobs") else "failed"
        set_session_status(session_id, final_status)
        logger.info("Resumed session %s completed with status %s", session_id, final_status)
    except Exception as exc:
        set_session_status(session_id, "failed")
        logger.exception("Failed to resume session %s: %s", session_id, exc)


@router.post("/sessions/{session_id}/experience")
async def update_session_experience_level(
    session_id: str,
    payload: ExperienceUpdateRequest,
    background_tasks: BackgroundTasks,
) -> JSONResponse:
    current_status = get_session_status(session_id)
    if current_status == "completed":
        raise HTTPException(status_code=409, detail="Session is already completed")
    if current_status != "needs_experience_input":
        raise HTTPException(status_code=400, detail="Session is not waiting for experience input")

    experience_level = (payload.experience_level or "").strip()
    if experience_level not in ALLOWED_EXPERIENCE_LEVELS:
        raise HTTPException(status_code=400, detail="experience_level must be one of: fresher, 1-2, 3-5, 5+")

    set_session_status(session_id, "processing")
    background_tasks.add_task(_resume_pipeline, session_id, experience_level)
    return JSONResponse(
        status_code=202,
        content={
            "session_id": session_id,
            "status": "processing",
            "experience_level": experience_level,
            "message": "Experience level accepted; pipeline resumed.",
        },
    )
