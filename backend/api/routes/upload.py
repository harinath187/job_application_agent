"""
Upload API route - Handles resume PDF uploads and triggers the agent pipeline.
"""
import logging
import uuid
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from orchestrator.graph import build_graph
from orchestrator.state import AgentState
from utils.file_helpers import save_upload, RESUMES_DIR, get_relative_path
from utils.db import insert_session, insert_job, update_job_status, update_session_status


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["upload"])


def run_agent_pipeline(session_id: str, pdf_path: str, role: str, location: str) -> None:
    """
    Background task that runs the LangGraph agent pipeline.
    
    Args:
        session_id: Session ID for tracking
        pdf_path: Path to the uploaded resume PDF
        role: Job title / role provided by the user
        location: Location provided by the user
    """
    try:
        # Build and run the graph
        graph = build_graph()
        
        initial_state: AgentState = {
            "resume_path": pdf_path,
            "resume_text": "",
            "extracted_role": role,
            "extracted_location": location,
            "extracted_skills": [],
            "extracted_experience_years": 0,
            "jobs": [],
            "tailored_resumes": [],
            "cover_letter_paths": []
        }
        
        # Run the graph
        result = graph.invoke(initial_state)
        
        # Insert jobs and cover letters into database
        for idx, tailored_item in enumerate(result.get("tailored_resumes", [])):
            job = tailored_item.get("job", {})
            job_id = insert_job(session_id, job)
            
            # Get corresponding cover letter path if available and convert to relative path
            cover_letter_path = result.get("cover_letter_paths", [])[idx] if idx < len(result.get("cover_letter_paths", [])) else None
            
            # Get the tailored resume path (already absolute from the agent)
            tailored_resume_path = tailored_item.get("resume_path", "")
            
            # Convert absolute paths to relative paths for storage
            relative_tailored_resume_path = get_relative_path(tailored_resume_path) if tailored_resume_path else None
            relative_cover_letter_path = get_relative_path(cover_letter_path) if cover_letter_path else None
            
            # Update job with tailored resume path and cover letter path
            update_job_status(
                job_id=job_id,
                status="complete",
                resume_path=relative_tailored_resume_path,
                cover_letter_path=relative_cover_letter_path
            )
        
        # Mark session as complete
        update_session_status(session_id, "complete")
        logger.info(f"Session {session_id} completed successfully")
    
    except Exception as e:
        logger.error(f"Error in agent pipeline for session {session_id}: {e}")
        update_session_status(session_id, "failed")


@router.post("/upload")
async def upload_resume(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    role: str = Form(...),
    location: str = Form(...)
) -> JSONResponse:
    """
    Upload a resume PDF and trigger the agent pipeline.
    
    Args:
        file: Uploaded PDF file
        background_tasks: FastAPI background tasks
        role: Role provided by the user
        location: Location provided by the user
    
    Returns:
        JSON with session_id and status
    """
    # Validate file type
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")
    
    try:
        # Read file content
        file_content = await file.read()
        
        # Generate session ID and filename
        session_id = str(uuid.uuid4())
        filename = f"{session_id}.pdf"
        
        # Save file
        pdf_path = save_upload(file_content, filename)
        
        # Create session in database
        insert_session(session_id, "processing")
        
        # Add background task to run pipeline
        background_tasks.add_task(run_agent_pipeline, session_id, pdf_path, role, location)
        
        logger.info(f"Created session {session_id} for resume upload")
        
        return JSONResponse(
            status_code=202,
            content={
                "session_id": session_id,
                "jobReferenceId": session_id,
                "status": "processing",
                "message": "Resume uploaded and processing started"
            }
        )
    
    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        raise HTTPException(status_code=500, detail="Error processing upload")
