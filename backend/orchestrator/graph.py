"""
LangGraph orchestrator that coordinates all agents in the job application pipeline.
"""
import logging
import time  # FIXED: Add delay support for Groq rate limit protection.
import os
from langgraph.graph import StateGraph, END
from orchestrator.state import AgentState
from agents.pdf_parser import parse_resume, get_resume_text, extract_email_from_text
from agents.role_inferrer import infer_roles
from agents.job_validator import validate_jobs
from agents.relevance_scorer import compute_final_score, compute_role_confidence
from agents.scraper_agent import run_scraper_agent
from agents.tailor_agent import tailor_resume, save_tailored_resume
from agents.cover_letter_agent import generate_cover_letter
from utils.file_helpers import COVER_LETTERS_DIR, RESUMES_DIR, get_relative_path
from utils.db import (
    insert_job,
    get_session_data,
    get_search_history,
    set_session_status,
    update_session_parsed_resume_data,
    update_session_validation_stats,
    update_job_status,
    upsert_alert_preference_for_user,
    upsert_alert_user,
    upsert_session_alert_status,
    update_session_profile_data,
)
from utils.groq_client import GroqCallFailedError


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
FINAL_JOB_LIMIT = int(os.getenv("FINAL_JOB_LIMIT", "10"))
GENERATION_FAILED_STATUS = "generation_failed"
COMPLETED_STATUS = "complete"


def pdf_parser_node(state: AgentState) -> AgentState:
    """
    Node that parses the PDF resume and extracts skills.
    
    Args:
        state: Current agent state
    
    Returns:
        Updated state with extracted resume skills
    """
    logger.info(f"Processing PDF: {state['resume_path']}")
    
    # Extract text from PDF
    resume_text = get_resume_text(state["resume_path"])
    state["resume_text"] = resume_text
    
    # Parse resume to extract structured data
    try:
        parsed_data = parse_resume(state["resume_path"])
    except GroqCallFailedError as exc:
        session_id = state.get("session_id")
        if session_id:
            update_session_status(session_id, "failed_rate_limit")
        logger.error("Resume parsing failed due to Groq rate limiting for session %s: %s", session_id, exc)
        raise
    extracted_email = parsed_data.get("email") or extract_email_from_text(resume_text)
    state["extracted_email"] = extracted_email
    state["extracted_skills"] = parsed_data.get("skills", [])
    state["projects"] = parsed_data.get("projects", [])
    state["certifications"] = parsed_data.get("certifications", [])
    state["extracted_experience_years"] = parsed_data.get("experience_years", 0)
    state["extracted_experience"] = parsed_data.get("experience")
    state["resume_sections"] = parsed_data.get("resume_sections", {})
    state["experience_level"] = parsed_data.get("experience_level")

    inferred_roles = infer_roles(state.get("extracted_skills", []), state.get("projects", []))
    state["inferred_roles"] = inferred_roles
    session_id = state.get("session_id")
    if session_id:
        update_session_parsed_resume_data(session_id, parsed_data)
        update_session_profile_data(
            session_id=session_id,
            projects=state.get("projects", []),
            certifications=state.get("certifications", []),
            inferred_roles=inferred_roles,
        )

    logger.info(
        "Extracted skills=%s projects=%s certifications=%s inferred_roles=%s experience_years=%s experience=%s email=%s role=%s location=%s",
        state["extracted_skills"],
        state["projects"],
        state["certifications"],
        state["inferred_roles"],
        state["extracted_experience_years"],
        state.get("extracted_experience"),
        extracted_email,
        state.get("extracted_role", ""),
        state.get("extracted_location", ""),
    )
    logger.info("[graph] state.resume_sections after parser: %s", state.get("resume_sections"))
    
    return state


def _run_post_parse_pipeline(state: AgentState) -> AgentState:
    state = auto_alert_registration_node(state)
    state = scraper_node(state)
    state = tailor_node(state)
    state = cover_letter_node(state)
    return state


def resume_from_scraper_node(session_id: str, experience_level: str) -> AgentState:
    session_data = get_session_data(session_id)
    if not session_data:
        raise ValueError("Session not found")
    if session_data.get("status") == "completed":
        raise ValueError("Session already completed")

    history_rows = get_search_history(session_id=session_id)
    history = history_rows[0] if history_rows else {}

    parsed_data = session_data.get("parsed_resume_data")
    if isinstance(parsed_data, str):
        import json
        parsed_data = json.loads(parsed_data) if parsed_data else {}
    parsed_data = parsed_data or {}

    state: AgentState = {
        "session_id": session_id,
        "resume_path": history.get("resume_path", ""),
        "resume_text": parsed_data.get("resume_text", ""),
        "extracted_role": history.get("role") or None,
        "extracted_location": history.get("location") or None,
        "user_experience": session_data.get("experience"),
        "extracted_email": parsed_data.get("email"),
        "alerts_enabled": False,
        "alert_message": "",
        "extracted_skills": parsed_data.get("skills", []),
        "projects": parsed_data.get("projects", []),
        "certifications": parsed_data.get("certifications", []),
        "inferred_roles": parsed_data.get("inferred_roles", []),
        "experience_level": experience_level,
        "extracted_experience_years": parsed_data.get("experience_years", 0),
        "extracted_experience": parsed_data.get("experience"),
        "resume_sections": parsed_data.get("resume_sections", {}),
        "jobs": [],
        "top_ranked_jobs": [],
        "tailored_resumes": [],
        "cover_letter_paths": [],
    }
    return _run_post_parse_pipeline(state)


def auto_alert_registration_node(state: AgentState) -> AgentState:
    """
    Node that automatically registers email alerts from the resume email.
    """
    session_id = state.get("session_id")
    email = state.get("extracted_email")
    role = state.get("extracted_role") or ""
    location = state.get("extracted_location") or ""

    if state.get("experience_level") is None:
        if session_id:
            set_session_status(session_id, "needs_experience_input")
        logger.warning("Experience level missing for session %s; pausing before scraper node", session_id)
        state["alert_message"] = "Experience input required before job search can continue."
        return state

    if not email:
        message = "No email address found in resume; email alerts were not enabled."
        state["alerts_enabled"] = False
        state["alert_message"] = message
        upsert_session_alert_status(session_id, None, False, message)
        logger.info("Skipping automatic alert registration for session %s: no email found", session_id)
        return state

    try:
        user_id = upsert_alert_user(email)
        preference_id = upsert_alert_preference_for_user(user_id, role, location)
        message = f"Email alerts enabled automatically for {email}."
        state["alerts_enabled"] = True
        state["alert_message"] = message
        upsert_session_alert_status(session_id, email, True, message, preference_id)
        logger.info("Enabled automatic email alerts for session %s and email %s", session_id, email)
    except Exception as exc:
        message = "Email address was found, but alerts could not be enabled."
        state["alerts_enabled"] = False
        state["alert_message"] = message
        upsert_session_alert_status(session_id, email, False, message)
        logger.error("Failed to auto-register alerts for session %s: %s", session_id, exc)

    return state


def scraper_node(state: AgentState) -> AgentState:
    """
    Node that scrapes job listings based on extracted role and location.
    Inserts scraped jobs into database with 'pending' status for incremental display.
    
    Args:
        state: Current agent state
    
    Returns:
        Updated state with scraped jobs and their database IDs
    """
    role = state.get("extracted_role") or ""
    location = state.get("extracted_location") or ""

    logger.info(f"Scraping jobs for: {role} in {location}")

    jobs_state = run_scraper_agent(state)
    jobs = jobs_state.get("jobs", [])
    jobs, validation_stats = validate_jobs(jobs, state.get("experience_level"))
    state["validation_stats"] = validation_stats
    projects = state.get("projects", [])
    certifications = state.get("certifications", [])
    session_id = state.get("session_id")
    if session_id:
        update_session_validation_stats(session_id, validation_stats)

    scored_jobs = []
    for job in jobs:
        job["role_confidence"] = compute_role_confidence(job, projects, certifications)
        scores = compute_final_score(job, projects, certifications, state.get("experience_level"))
        job.update(scores)
        scored_jobs.append(job)

    scored_jobs.sort(key=lambda item: item.get("final_score", 0.0), reverse=True)
    final_jobs = scored_jobs[:FINAL_JOB_LIMIT]
    logger.info("Found %s validated jobs, keeping top %s by final_score", len(scored_jobs), len(final_jobs))
    
    # Insert each job into database with pending status for incremental display
    for job in final_jobs:
        job_id = insert_job(session_id, job)
        job["id"] = job_id  # Add the database ID to the job

    state["jobs"] = final_jobs
    state["top_ranked_jobs"] = final_jobs

    return state


def tailor_node(state: AgentState) -> AgentState:
    """
    Node that tailors resume for each scraped job and saves tailored versions.
    Updates database immediately after each job is tailored for incremental display.
    
    Args:
        state: Current agent state
    
    Returns:
        Updated state with tailored resumes and their file paths
    """
    tailored_resumes = []
    resume_text = state.get("resume_text", "")
    skills = state.get("extracted_skills", [])
    
    jobs_to_process = state.get("top_ranked_jobs") or state.get("jobs", [])
    for job in jobs_to_process:
        time.sleep(2)
        logger.info(f"Tailoring resume for {job.get('title')} at {job.get('company')}")

        try:
            tailored_data = tailor_resume(
                resume_text=resume_text,
                job=job,
                skills=skills,
                target_role=state.get("extracted_role", ""),
                target_location=state.get("extracted_location", ""),
                experience_level=state.get("user_experience") or state.get("extracted_experience") or str(state.get("extracted_experience_years", "")),
                resume_sections=state.get("resume_sections"),
            )
        except GroqCallFailedError as exc:
            job_id = job.get("id")
            if job_id:
                update_job_status(job_id=job_id, status=GENERATION_FAILED_STATUS, resume_path=None, cover_letter_path=None)
            logger.error("Tailoring failed for job %s due to Groq rate limiting: %s", job.get("title", ""), exc)
            continue
        except Exception as exc:
            job_id = job.get("id")
            if job_id:
                update_job_status(job_id=job_id, status=GENERATION_FAILED_STATUS, resume_path=None, cover_letter_path=None)
            logger.exception("Tailoring failed for job %s: %s", job.get("title", ""), exc)
            continue

        if tailored_data.get("status") in {"failed", "failed_rate_limit"}:
            job_id = job.get("id")
            if job_id:
                update_job_status(job_id=job_id, status=GENERATION_FAILED_STATUS, resume_path=None, cover_letter_path=None)
            logger.warning("Skipping resume rendering for %s because tailoring failed with reason %s", job.get("title", ""), tailored_data.get("reason"))
            continue

        # Save tailored resume to disk
        tailored_resume_path = save_tailored_resume(
            resume_text=resume_text,
            tailored_data=tailored_data,
            job=job,
            output_dir=str(RESUMES_DIR)
        )
        if not tailored_resume_path:
            job_id = job.get("id")
            if job_id:
                update_job_status(job_id=job_id, status=GENERATION_FAILED_STATUS, resume_path=None, cover_letter_path=None)
            logger.warning("No tailored resume PDF was generated for %s; marking the job as %s", job.get("title", ""), GENERATION_FAILED_STATUS)
            continue

        tailored_resumes.append({
            "job": job,
            "tailored": tailored_data,
            "resume_path": tailored_resume_path
        })
    
    state["tailored_resumes"] = tailored_resumes
    logger.info(f"Tailored {len(tailored_resumes)} resumes")
    
    return state


def cover_letter_node(state: AgentState) -> AgentState:
    """
    Node that generates tailored cover letters for each job.
    Updates database with completed status after each job is processed for incremental display.
    Uses the candidate's skills and tailored resume summary for specificity.
    
    Args:
        state: Current agent state
    
    Returns:
        Updated state with cover letter paths
    """
    cover_letter_paths = []
    skills = state.get("extracted_skills", [])  # Get extracted skills from state
    
    # Use the resume text as fallback summary if tailored summary not available
    resume_summary = state.get("resume_text", "")[:500]
    
    for tailored_item in state.get("tailored_resumes", []):
        time.sleep(2)
        job = tailored_item.get("job", {})
        tailored_data = tailored_item.get("tailored", {})

        logger.info(f"Generating cover letter for {job.get('title')} at {job.get('company')}")
        
        if tailored_data.get("status") == "failed":
            logger.warning("Skipping cover letter generation for %s because tailoring failed", job.get("title", ""))
            job_id = job.get("id")
            if job_id:
                update_job_status(job_id=job_id, status=GENERATION_FAILED_STATUS, resume_path=None, cover_letter_path=None)
            continue

        # Use the tailored resume summary if available (more specific than generic resume text)
        tailored_resume_summary = tailored_data.get("summary", "") or tailored_data.get("rewritten_summary", "") or resume_summary

        try:
            cover_letter_path = generate_cover_letter(
                job=job,
                summary=resume_summary,
                skills=skills,
                output_dir=str(COVER_LETTERS_DIR),
                tailored_resume_summary=tailored_resume_summary  # Pass tailored summary for better specificity
            )
        except GroqCallFailedError as exc:
            job_id = job.get("id")
            if job_id:
                update_job_status(job_id=job_id, status=GENERATION_FAILED_STATUS, resume_path=None, cover_letter_path=None)
            logger.error("Cover letter generation failed for job %s due to Groq rate limiting: %s", job.get("title", ""), exc)
            continue
        except Exception as exc:
            job_id = job.get("id")
            if job_id:
                update_job_status(job_id=job_id, status=GENERATION_FAILED_STATUS, resume_path=None, cover_letter_path=None)
            logger.exception("Cover letter generation failed for job %s: %s", job.get("title", ""), exc)
            continue

        if cover_letter_path:
            cover_letter_paths.append(cover_letter_path)
        
        # Convert absolute paths to relative paths for storage
        relative_tailored_resume_path = get_relative_path(tailored_item.get("resume_path", "")) if tailored_item.get("resume_path") else None
        relative_cover_letter_path = get_relative_path(cover_letter_path) if cover_letter_path else None
        
        # Update job in database immediately as "complete" so frontend displays it incrementally
        job_id = job.get("id")
        if job_id:
            update_job_status(
                job_id=job_id,
                status=COMPLETED_STATUS,
                resume_path=relative_tailored_resume_path,
                cover_letter_path=relative_cover_letter_path
            )
            logger.info(f"Updated job {job_id} to complete status")
        
        time.sleep(2)  # Pause after each tailor + cover letter pair to reduce Groq rate limit pressure.
    
    state["cover_letter_paths"] = cover_letter_paths
    logger.info(f"Generated {len(cover_letter_paths)} cover letters")
    
    return state


def build_graph():
    """
    Build and compile the LangGraph orchestration graph.
    
    Returns:
        Compiled LangGraph StateGraph
    """
    workflow = StateGraph(AgentState)
    
    # Register nodes
    workflow.add_node("pdf_parser", pdf_parser_node)
    workflow.add_node("auto_alert_registration", auto_alert_registration_node)
    workflow.add_node("scraper", scraper_node)
    workflow.add_node("tailor", tailor_node)
    workflow.add_node("cover_letter", cover_letter_node)
    
    # Define edges (linear flow)
    workflow.set_entry_point("pdf_parser")
    workflow.add_edge("pdf_parser", "auto_alert_registration")
    workflow.add_conditional_edges(
        "auto_alert_registration",
        lambda state: "end" if state.get("experience_level") is None else "scraper",
        {
            "end": END,
            "scraper": "scraper",
        },
    )
    workflow.add_edge("scraper", "tailor")
    workflow.add_edge("tailor", "cover_letter")
    workflow.add_edge("cover_letter", END)
    
    # Compile and return
    graph = workflow.compile()
    return graph
