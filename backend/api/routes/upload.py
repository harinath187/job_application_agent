"""
Upload API route - Handles resume PDF uploads and triggers the agent pipeline.
"""
import asyncio
import json
import logging
import uuid
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, StreamingResponse
from orchestrator.state import AgentState
from agents.pdf_parser import get_resume_text, parse_resume, extract_email_from_text
from agents.scraper_agent import scrape_jobs
from agents.tailor_agent import tailor_resume, save_tailored_resume
from agents.ats_score_agent import score_resume
from agents.skills_gap_agent import analyze_gap
from agents.interview_prep_agent import generate_prep
from agents.cover_letter_agent import generate_cover_letter
from utils.input_validator import validate_inputs
from utils.file_helpers import save_upload, RESUMES_DIR, COVER_LETTERS_DIR, get_relative_path
from utils.db import (
    delete_resume,
    get_resume,
    insert_interview_prep,
    insert_job,
    insert_search_history,
    insert_session,
    insert_skills_gap,
    list_resumes,
    save_resume,
    update_job_score,
    update_job_status,
    update_resume_label,
    update_session_experience,
    update_session_status,
    upsert_alert_preference_for_user,
    upsert_alert_user,
    upsert_session_alert_status,
)


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["upload"])
SESSION_QUEUES: dict[str, asyncio.Queue] = {}
SESSION_CONTEXT: dict[str, dict[str, str | None]] = {}

def _get_session_queue(session_id: str) -> asyncio.Queue:
    queue = SESSION_QUEUES.get(session_id)
    if queue is None:
        queue = asyncio.Queue()
        SESSION_QUEUES[session_id] = queue
    return queue


async def _emit_status(session_id: str, msg: str, done: bool = False) -> None:
    queue = _get_session_queue(session_id)
    await queue.put({"msg": msg, "done": done})


def _normalize_resume_record(resume: dict) -> dict:
    return {
        "id": resume.get("id"),
        "label": resume.get("label"),
        "file_path": resume.get("file_path"),
        "pdf_path": resume.get("file_path"),
        "extracted_role": resume.get("extracted_role"),
        "extracted_location": resume.get("extracted_location"),
        "extracted_skills": resume.get("extracted_skills", []),
        "uploaded_at": resume.get("uploaded_at"),
    }


def _save_resume_record(file_content: bytes, original_filename: str, label: str | None = None, extracted_role: str = "", extracted_location: str = "") -> dict:
    pdf_path = save_upload(file_content, original_filename)
    resume_text = get_resume_text(pdf_path)
    parsed = parse_resume(pdf_path)
    extracted_skills = parsed.get("skills", [])
    resume_label = label or f"Resume - {original_filename}"
    resume_id = save_resume(resume_label, pdf_path, extracted_role, extracted_location, extracted_skills)
    return {
        "resume_id": resume_id,
        "pdf_path": pdf_path,
        "resume_text": resume_text,
        "extracted_role": extracted_role,
        "extracted_location": extracted_location,
        "extracted_skills": extracted_skills,
        "extracted_email": parsed.get("email") or extract_email_from_text(resume_text),
        "extracted_experience_years": parsed.get("experience_years", 0),
        "extracted_experience": parsed.get("experience"),
        "label": resume_label,
    }


def _build_state_from_resume(resume_record: dict, session_id: str, role_override: str, location_override: str, experience: str | None) -> AgentState:
    return {
        "session_id": session_id,
        "resume_id": resume_record.get("resume_id"),
        "resume_path": resume_record.get("pdf_path") or "",
        "resume_text": resume_record.get("resume_text") or "",
        "extracted_role": role_override or resume_record.get("extracted_role") or "",
        "extracted_location": location_override or resume_record.get("extracted_location") or "",
        "user_experience": experience,
        "extracted_email": resume_record.get("extracted_email"),
        "alerts_enabled": False,
        "alert_message": "Email alerts pending resume parsing",
        "extracted_skills": resume_record.get("extracted_skills", []),
        "extracted_experience_years": resume_record.get("extracted_experience_years", 0),
        "extracted_experience": resume_record.get("extracted_experience"),
        "jobs": [],
        "tailored_resumes": [],
        "ats_scores": {},
        "skills_gap_results": {},
        "interview_prep_results": {},
        "cover_letter_paths": []
    }


async def run_pipeline(session_id: str, emit) -> None:
    """
    Shared async pipeline runner used by both background execution and SSE streaming.
    """
    try:
        session_context = SESSION_CONTEXT.get(session_id)
        if not session_context:
            raise RuntimeError(f"Missing session context for {session_id}")

        state: AgentState = {
            "session_id": session_id,
            "resume_id": session_context.get("resume_id"),
            "resume_path": session_context.get("pdf_path") or "",
            "resume_text": "",
            "extracted_role": session_context.get("role") or "",
            "extracted_location": session_context.get("location") or "",
            "user_experience": session_context.get("experience"),
            "extracted_email": None,
            "alerts_enabled": False,
            "alert_message": "Email alerts pending resume parsing",
            "extracted_skills": [],
            "extracted_experience_years": 0,
            "extracted_experience": None,
            "jobs": [],
            "tailored_resumes": [],
            "ats_scores": {},
            "skills_gap_results": {},
            "interview_prep_results": {},
            "cover_letter_paths": []
        }
        pdf_path = state["resume_path"]
        role = state["extracted_role"]
        location = state["extracted_location"]
        experience = state["user_experience"]
        if session_context.get("use_saved_resume"):
            await emit("Extracting text from saved resume...", False)
            resume_text = await asyncio.to_thread(get_resume_text, pdf_path)
            state["resume_text"] = resume_text
            state["extracted_email"] = session_context.get("extracted_email") or extract_email_from_text(resume_text)
            state["extracted_skills"] = session_context.get("extracted_skills", [])
            state["extracted_experience_years"] = session_context.get("extracted_experience_years", 0)
            state["extracted_experience"] = session_context.get("extracted_experience")
        else:
            await emit("Extracting text from resume...", False)
            resume_text = await asyncio.to_thread(get_resume_text, pdf_path)
            state["resume_text"] = resume_text

            await emit("Identifying role, location and skills...", False)
            parsed_data = await asyncio.to_thread(parse_resume, pdf_path)
            extracted_email = parsed_data.get("email") or extract_email_from_text(resume_text)
            state["extracted_email"] = extracted_email
            state["extracted_skills"] = parsed_data.get("skills", [])
            state["extracted_experience_years"] = parsed_data.get("experience_years", 0)
            state["extracted_experience"] = parsed_data.get("experience")

        if extracted_email:
            try:
                user_id = await asyncio.to_thread(upsert_alert_user, extracted_email)
                preference_id = await asyncio.to_thread(upsert_alert_preference_for_user, user_id, role, location)
                message = f"Email alerts enabled automatically for {extracted_email}."
                state["alerts_enabled"] = True
                state["alert_message"] = message
                await asyncio.to_thread(upsert_session_alert_status, session_id, extracted_email, True, message, preference_id)
            except Exception as exc:
                logger.error("Failed to auto-register alerts for session %s: %s", session_id, exc)
                message = "Email address was found, but alerts could not be enabled."
                state["alerts_enabled"] = False
                state["alert_message"] = message
                await asyncio.to_thread(upsert_session_alert_status, session_id, extracted_email, False, message)
        else:
            message = "No email address found in resume; email alerts were not enabled."
            state["alerts_enabled"] = False
            state["alert_message"] = message
            await asyncio.to_thread(upsert_session_alert_status, session_id, None, False, message)

        await emit("Searching LinkedIn, Indeed and Naukri...", False)
        jobs = await asyncio.to_thread(
            scrape_jobs,
            role=role,
            location=location,
            candidate_experience_years=state.get("extracted_experience_years", 0),
            experience=experience or state.get("extracted_experience")
        )

        for job in jobs:
            job_id = await asyncio.to_thread(
                insert_job,
                session_id=session_id,
                resume_id=resume_record.get("resume_id"),
                title=job.get("title", ""),
                company=job.get("company", ""),
                location=job.get("location", ""),
                description=job.get("description", ""),
                job_url=job.get("job_url", ""),
                salary_min=job.get("salary", {}).get("min") if job.get("salary") else None,
                salary_max=job.get("salary", {}).get("max") if job.get("salary") else None,
                salary_interval=job.get("salary", {}).get("interval") if job.get("salary") else None,
            )
            job["id"] = job_id

        state["jobs"] = jobs
        await emit(f"Found {len(jobs)} jobs. Starting resume tailoring...", False)

        tailored_resumes = []
        skills = state.get("extracted_skills", [])
        for index, job in enumerate(jobs, start=1):
            company = job.get("company", "Company")
            await emit(f"Tailoring resume for {company} ({index}/{len(jobs)})...", False)
            tailored_data = await asyncio.to_thread(tailor_resume, resume_text, job, skills)
            tailored_resume_path = await asyncio.to_thread(
                save_tailored_resume,
                resume_text=resume_text,
                tailored_data=tailored_data,
                job=job,
                output_dir=str(RESUMES_DIR)
            )
            tailored_resumes.append({"job": job, "tailored": tailored_data, "resume_path": tailored_resume_path})

        state["tailored_resumes"] = tailored_resumes

        ats_scores = {}
        for index, tailored_item in enumerate(tailored_resumes, start=1):
            job = tailored_item.get("job", {})
            company = job.get("company", "Company")
            await emit(f"Scoring ATS match for {company} ({index}/{len(tailored_resumes)})...", False)
            tailored_data = tailored_item.get("tailored", {}) or {}
            tailored_resume_text = "\n".join(
                part for part in [
                    tailored_data.get("rewritten_summary", ""),
                    ", ".join(tailored_data.get("revised_skills", []) or []),
                    "\n".join(tailored_data.get("bullet_rewrites", []) or []),
                ]
                if part
            )
            score = await asyncio.to_thread(
                score_resume,
                tailored_resume_text or state.get("resume_text", ""),
                job.get("description", "")
            )
            ats_scores[job.get("id")] = score
            if job.get("id"):
                await asyncio.to_thread(
                    update_job_score,
                    job.get("id"),
                    score.get("match_pct", 0),
                    score.get("missing_keywords", [])
                )

        state["ats_scores"] = ats_scores

        skills_gap_results = {}
        for index, tailored_item in enumerate(tailored_resumes, start=1):
            job = tailored_item.get("job", {})
            company = job.get("company", "Company")
            await emit(f"Analyzing skills gap for {company} ({index}/{len(tailored_resumes)})...", False)
            result = await asyncio.to_thread(
                analyze_gap,
                state.get("extracted_skills", []),
                job.get("description", "")
            )
            job_id = job.get("id")
            if job_id:
                skills_gap_results[job_id] = result
                await asyncio.to_thread(insert_skills_gap, job_id, result)

        state["skills_gap_results"] = skills_gap_results

        interview_prep_results = {}
        for index, tailored_item in enumerate(tailored_resumes, start=1):
            job = tailored_item.get("job", {})
            company = job.get("company", "Company")
            await emit(f"Preparing interview questions for {company} ({index}/{len(tailored_resumes)})...", False)
            tailored_data = tailored_item.get("tailored", {}) or {}
            job_id = job.get("id")
            if not job_id:
                continue
            prep = await asyncio.to_thread(
                generate_prep,
                job.get("description", ""),
                tailored_data.get("rewritten_summary", "") or state.get("resume_text", "")[:500],
                skills_gap_results.get(job_id, {}).get("missing_skills", []),
            )
            interview_prep_results[job_id] = prep
            await asyncio.to_thread(insert_interview_prep, job_id, prep.get("questions", []))

        state["interview_prep_results"] = interview_prep_results

        cover_letter_paths = []
        resume_summary = state.get("resume_text", "")[:500]
        for index, tailored_item in enumerate(tailored_resumes, start=1):
            job = tailored_item.get("job", {})
            company = job.get("company", "Company")
            await emit(f"Writing cover letter for {company} ({index}/{len(tailored_resumes)})...", False)
            tailored_data = tailored_item.get("tailored", {})
            tailored_resume_summary = tailored_data.get("summary", "") or resume_summary
            cover_letter_path = await asyncio.to_thread(
                generate_cover_letter,
                job=job,
                summary=resume_summary,
                skills=skills,
                output_dir=str(COVER_LETTERS_DIR),
                tailored_resume_summary=tailored_resume_summary
            )
            if cover_letter_path:
                cover_letter_paths.append(cover_letter_path)

            relative_tailored_resume_path = get_relative_path(tailored_item.get("resume_path", "")) if tailored_item.get("resume_path") else None
            relative_cover_letter_path = get_relative_path(cover_letter_path) if cover_letter_path else None
            job_id = job.get("id")
            if job_id:
                await asyncio.to_thread(
                    update_job_status,
                    job_id=job_id,
                    status="interview",
                    resume_path=relative_tailored_resume_path,
                    cover_letter_path=relative_cover_letter_path
                )

        state["cover_letter_paths"] = cover_letter_paths
        await asyncio.to_thread(update_session_status, session_id, "complete")
        await emit(f"All done! {len(tailored_resumes)} tailored resumes ready.", True)
        logger.info("Session %s completed successfully", session_id)
    except Exception as e:
        logger.error("Error in agent pipeline for session %s: %s", session_id, e)
        await asyncio.to_thread(update_session_status, session_id, "failed")
        await emit("Connection lost — check backend logs.", True)


async def run_agent_pipeline(session_id: str) -> None:
    async def emit(msg: str, done: bool = False) -> None:
        await _emit_status(session_id, msg, done)

    await run_pipeline(session_id, emit)


@router.get("/stream/{session_id}")
async def stream_session(session_id: str):
    queue = _get_session_queue(session_id)

    async def event_stream():
        while True:
            payload = await queue.get()
            yield f"data: {json.dumps(payload)}\n\n"
            if payload.get("done"):
                break

    headers = {
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no"
    }
    return StreamingResponse(event_stream(), media_type="text/event-stream", headers=headers)


@router.post("/upload")
async def upload_resume(
    background_tasks: BackgroundTasks,
    file: UploadFile | None = File(None),
    resume_id: str | None = Form(None),
    role: str = Form(...),
    location: str = Form(...),
    experience: str | None = Form(None)
) -> JSONResponse:
    """
    Upload a resume PDF and trigger the agent pipeline.
    """
    is_valid, message = validate_inputs(role, location)
    if not is_valid:
        raise HTTPException(status_code=400, detail=message)

    try:
        session_id = str(uuid.uuid4())
        _get_session_queue(session_id)
        resume_record: dict

        if resume_id:
            saved_resume = get_resume(resume_id)
            if not saved_resume:
                raise HTTPException(status_code=404, detail="Saved resume not found")
            resume_record = _normalize_resume_record(saved_resume)
        else:
            if not file:
                raise HTTPException(status_code=400, detail="A PDF file or resume_id is required")
            if not file.filename.endswith(".pdf"):
                raise HTTPException(status_code=400, detail="Only PDF files are accepted")
            file_content = await file.read()
            resume_record = _save_resume_record(
                file_content=file_content,
                original_filename=file.filename,
                label=f"Resume - {file.filename}",
                extracted_role=role,
                extracted_location=location,
            )

        SESSION_CONTEXT[session_id] = {
            "pdf_path": resume_record.get("pdf_path"),
            "role": role,
            "location": location,
            "experience": experience,
            "resume_id": resume_record.get("resume_id"),
            "use_saved_resume": bool(resume_id),
            "extracted_email": resume_record.get("extracted_email"),
            "extracted_skills": resume_record.get("extracted_skills", []),
            "extracted_experience_years": resume_record.get("extracted_experience_years", 0),
            "extracted_experience": resume_record.get("extracted_experience"),
        }
        insert_session(session_id, "processing")
        insert_search_history(session_id, resume_record.get("label") or (file.filename if file else "Saved resume"), resume_record.get("pdf_path"), role, location, experience)
        update_session_experience(session_id, experience)
        background_tasks.add_task(run_agent_pipeline, session_id)
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


@router.post("/resumes")
async def save_resume_route(
    file: UploadFile = File(...),
    label: str | None = Form(None),
    extracted_role: str | None = Form(None),
    extracted_location: str | None = Form(None)
) -> JSONResponse:
    """Upload and save a resume without starting the job search pipeline."""
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    try:
        file_content = await file.read()
        resume_record = _save_resume_record(
            file_content=file_content,
            original_filename=file.filename,
            label=label or f"Resume - {file.filename}",
            extracted_role=extracted_role or "",
            extracted_location=extracted_location or "",
        )
        return JSONResponse(
            status_code=201,
            content={"resume_id": resume_record["resume_id"]}
        )
    except Exception as e:
        logger.error("Error saving resume: %s", e)
        raise HTTPException(status_code=500, detail="Error saving resume")


@router.get("/resumes")
async def get_resumes() -> JSONResponse:
    try:
        resumes = list_resumes()
        return JSONResponse(
            status_code=200,
            content={"resumes": [
                {
                    "id": item.get("id"),
                    "label": item.get("label"),
                    "extracted_role": item.get("extracted_role"),
                    "extracted_location": item.get("extracted_location"),
                    "uploaded_at": item.get("uploaded_at"),
                }
                for item in resumes
            ]}
        )
    except Exception as e:
        logger.error("Error listing resumes: %s", e)
        raise HTTPException(status_code=500, detail="Error listing resumes")


@router.patch("/resumes/{resume_id}")
async def rename_resume(resume_id: str, label: str = Form(...)) -> JSONResponse:
    try:
        updated = update_resume_label(resume_id, label)
        if not updated:
            raise HTTPException(status_code=404, detail="Resume not found")
        return JSONResponse(status_code=200, content={"ok": True})
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Error renaming resume %s: %s", resume_id, e)
        raise HTTPException(status_code=500, detail="Error renaming resume")


@router.delete("/resumes/{resume_id}")
async def remove_resume(resume_id: str) -> JSONResponse:
    try:
        delete_resume(resume_id)
        return JSONResponse(status_code=200, content={"ok": True})
    except Exception as e:
        logger.error("Error deleting resume %s: %s", resume_id, e)
        raise HTTPException(status_code=500, detail="Error deleting resume")
