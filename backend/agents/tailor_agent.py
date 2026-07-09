"""
Tailor Agent - Tailors resume content to match job requirements using Groq LLM.
"""
import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List

from groq import Groq
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.lib.utils import simpleSplit
from reportlab.lib.pagesizes import landscape
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle, PageBreak
from reportlab.pdfgen import canvas

from utils.db import update_job_status
from utils.file_helpers import sanitise_filename
from utils.groq_client import GroqCallFailedError, call_groq_with_retry


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Read Groq API key at runtime.
GROQ_API_KEY = os.getenv("GROQ_API_KEY")


def get_groq_client() -> Groq:
    """
    Lazily initialize the Groq client to avoid import-time failures.
    """
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not set. Tailoring via Groq is unavailable.")
    return Groq(api_key=GROQ_API_KEY)


def _extract_json_payload(response_text: str) -> Dict[str, Any]:
    """Extract JSON content from an LLM response."""
    if not response_text:
        raise ValueError("empty response")

    cleaned = response_text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    match = re.search(r"\{.*\}", cleaned, flags=re.DOTALL)
    candidate = match.group(0) if match else cleaned
    return json.loads(candidate)


def _validate_tailored_payload(payload: Dict[str, Any]) -> bool:
    """Validate the structure and completeness of the tailoring payload."""
    summary = payload.get("summary") or payload.get("rewritten_summary")
    if not isinstance(summary, str) or not summary.strip():
        return False
    if not re.search(r"[.!]$", summary.strip()):
        return False

    skills = payload.get("skills") or payload.get("revised_skills")
    if not isinstance(skills, list) or len(skills) < 5:
        return False
    if not all(isinstance(skill, str) and skill.strip() for skill in skills):
        return False

    return True


def _normalize_tailored_payload(payload: Dict[str, Any], fallback_skills: List[str]) -> Dict[str, Any]:
    """Normalize LLM output to a consistent field structure for downstream use."""
    summary = payload.get("summary") or payload.get("rewritten_summary") or ""
    summary_text = str(summary).strip() if isinstance(summary, str) else ""

    skills = payload.get("skills") or payload.get("revised_skills") or fallback_skills
    if not isinstance(skills, list):
        skills = fallback_skills
    normalized_skills = [str(skill).strip() for skill in skills if str(skill).strip()]
    if len(normalized_skills) < 5:
        normalized_skills = normalized_skills or [str(skill).strip() for skill in fallback_skills if str(skill).strip()]

    return {
        "summary": summary_text,
        "skills": normalized_skills,
        "bullet_rewrites": [],
        "rewritten_summary": summary_text,
        "revised_skills": normalized_skills,
    }


def _apply_tailoring_patch(resume_sections: Dict[str, Any], tailored_payload: Dict[str, Any]) -> Dict[str, Any]:
    """Patch the full parsed resume with tailored summary and skills only."""
    patched_sections = json.loads(json.dumps(resume_sections))
    patched_sections["summary"] = tailored_payload.get("summary", patched_sections.get("summary", ""))
    patched_sections["skills"] = tailored_payload.get("skills", patched_sections.get("skills", []))
    patched_sections.setdefault("additional_sections", patched_sections.get("additional_sections", []))
    return patched_sections


def _sanity_check_resume_sections(original_sections: Dict[str, Any], patched_sections: Dict[str, Any]) -> bool:
    """Ensure merge did not drop structured sections."""
    if not isinstance(original_sections, dict) or not isinstance(patched_sections, dict):
        return False
    original_experience = original_sections.get("experience") or []
    patched_experience = patched_sections.get("experience") or []
    original_education = original_sections.get("education") or []
    patched_education = patched_sections.get("education") or []
    original_additional = original_sections.get("additional_sections") or []
    patched_additional = patched_sections.get("additional_sections") or []
    return (
        len(patched_experience) == len(original_experience)
        and len(patched_education) == len(original_education)
        and len(patched_additional) == len(original_additional)
    )


def tailor_resume(
    resume_text: str,
    job: Dict[str, Any],
    skills: List[str],
    target_role: str = "",
    target_location: str = "",
    experience_level: str = "",
    resume_sections: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """
    Tailor resume content to match a specific job posting.

    Args:
        resume_text: Full text from the candidate's resume.
        job: Job dictionary with keys: title, company, location, description, job_url.
        skills: List of extracted skills from resume.
        target_role: Role requested by the user or inferred by the orchestrator.
        target_location: Location requested by the user or inferred by the orchestrator.
        experience_level: Experience level requested by the user or inferred by the orchestrator.

    Returns:
        Dictionary with keys: summary, skills, bullet_rewrites, and compatibility aliases.
    """
    job_id = job.get("id")
    try:
        job_description_snippet = str(job.get("description", ""))[:800]

        try:
            client = get_groq_client()
        except RuntimeError as exc:
            logger.error(str(exc))
            return {"status": "failed", "reason": "groq_unavailable"}

        prompt = f"""You are a professional resume writer. Tailor the following resume to match the job posting.

IMPORTANT: Do NOT fabricate experience or skills. Only rewrite existing content to emphasize relevant qualifications.

Return ONLY valid JSON with keys: summary, skills.
Do not truncate any field. Every field must be a complete sentence or list.
Never cut off mid-word. Do not include any text outside the JSON object.

Job Title: {job.get('title', '')}
Company: {job.get('company', '')}
Target Role: {target_role or job.get('title', '')}
Target Location: {target_location or job.get('location', '')}
Experience Level: {experience_level or 'unknown'}
Job Description:
{job_description_snippet}

Current Resume:
{resume_text}

Current Extracted Skills: {', '.join(skills)}

Provide a JSON response with:
1. summary: A 2-3 sentence professional summary tailored to this job (emphasizing relevant background) and ending with punctuation.
2. skills: A list of 5-8 relevant skills from the resume and provided skills, prioritized for this role. Only include skills that appear in either the Current Resume text or the Current Extracted Skills list. Do not add skills not present in either source.

Important: Mirror the exact keywords and phrases from the job description where they honestly reflect the candidate's experience. This improves ATS compatibility.

Return ONLY valid JSON with keys summary, skills. Do not include any text outside the JSON object."""

        response_content = ""
        for attempt in range(2):
            if attempt == 1:
                prompt = f"{prompt}\nYour previous response was incomplete or invalid JSON. Return complete, valid JSON only."

            message = call_groq_with_retry(
                client,
                model="llama-3.1-8b-instant",
                max_tokens=900,
                temperature=0.3,
                messages=[{"role": "user", "content": prompt}],
            )
            response_text = getattr(getattr(message, "choices", [None])[0], "message", None)
            response_content = response_text.content if response_text else ""
            if not isinstance(response_content, str):
                response_content = ""
            response_content = response_content.strip()

            try:
                tailored_data = _extract_json_payload(response_content)
            except (json.JSONDecodeError, ValueError) as exc:
                logger.warning("Attempt %s failed to parse Groq JSON: %s", attempt + 1, exc)
                if attempt == 1:
                    logger.error("LLM tailoring output invalid after retry. Raw response: %s", response_content)
                    if job_id:
                        update_job_status(job_id=job_id, status="failed", resume_path=None, cover_letter_path=None)
                    return {"status": "failed", "reason": "llm_output_invalid"}
                continue

            if not isinstance(tailored_data, dict):
                logger.warning("Groq response did not return an object on attempt %s", attempt + 1)
                if attempt == 1:
                    logger.error("LLM tailoring output invalid after retry. Raw response: %s", response_content)
                    if job_id:
                        update_job_status(job_id=job_id, status="failed", resume_path=None, cover_letter_path=None)
                    return {"status": "failed", "reason": "llm_output_invalid"}
                continue

            if not _validate_tailored_payload(tailored_data):
                logger.warning("Groq response failed validation on attempt %s", attempt + 1)
                if attempt == 1:
                    logger.error("LLM tailoring output invalid after retry. Raw response: %s", response_content)
                    if job_id:
                        update_job_status(job_id=job_id, status="failed", resume_path=None, cover_letter_path=None)
                    return {"status": "failed", "reason": "llm_output_invalid"}
                continue

            normalized_payload = _normalize_tailored_payload(tailored_data, skills)
            logger.info("[tailor] incoming resume_sections for job %s: %s", job_id, resume_sections)
            if isinstance(resume_sections, dict):
                patched_sections = _apply_tailoring_patch(resume_sections, normalized_payload)
                logger.info("[tailor] patched resume_sections for job %s: %s", job_id, patched_sections)
                if not _sanity_check_resume_sections(resume_sections, patched_sections):
                    logger.error("Tailoring patch dropped resume sections during merge for job %s", job_id)
                return {
                    **normalized_payload,
                    "contact_info": patched_sections.get("contact_info", {}),
                    "summary": patched_sections.get("summary", normalized_payload.get("summary", "")),
                    "skills": patched_sections.get("skills", normalized_payload.get("skills", [])),
                    "experience": patched_sections.get("experience", []),
                    "education": patched_sections.get("education", []),
                    "resume_sections": patched_sections,
                }
            return normalized_payload

        logger.error("LLM tailoring output invalid after retry. Raw response: %s", response_content)
        if job_id:
            update_job_status(job_id=job_id, status="failed", resume_path=None, cover_letter_path=None)
        return {"status": "failed", "reason": "llm_output_invalid"}

    except GroqCallFailedError as exc:
        logger.error("Groq tailoring failed after retries for job %s: %s", job_id, exc)
        if job_id:
            update_job_status(job_id=job_id, status="failed_rate_limit", resume_path=None, cover_letter_path=None)
        raise
    except Exception as exc:
        logger.error("Error tailoring resume: %s", exc)
        if job_id:
            update_job_status(job_id=job_id, status="failed", resume_path=None, cover_letter_path=None)
        return {"status": "failed", "reason": "llm_output_invalid"}


def _extract_fallback_summary(resume_text: str) -> str:
    """Extract first substantial paragraph (>50 chars) from resume as fallback summary."""
    for line in resume_text.splitlines():
        cleaned = line.strip()
        if len(cleaned) > 50:
            return cleaned
    return ""


def _append_section_heading(story, heading: str, styles) -> None:
    if heading.strip():
        story.append(Paragraph(f"<b>{heading.strip()}</b>", styles["Heading2"]))


def _append_bullet_items(story, items, styles) -> None:
    for item in items or []:
        text = str(item).strip()
        if text:
            story.append(Paragraph(f"• {text}", styles["BodyText"]))


def _append_structured_section(story, heading: str, entries, styles) -> None:
    if not entries:
        return
    _append_section_heading(story, heading, styles)
    for entry in entries:
        if not isinstance(entry, dict):
            text = str(entry).strip()
            if text:
                story.append(Paragraph(f"• {text}", styles["BodyText"]))
            continue
        if heading.lower() == "education":
            degree = str(entry.get("degree") or "").strip()
            institution = str(entry.get("institution") or entry.get("school") or "").strip()
            location = str(entry.get("location") or "").strip()
            dates = str(entry.get("dates") or "").strip()
            grade = str(entry.get("grade") or "").strip()
            parts = [part for part in [degree, institution, location, dates, grade] if part]
            if parts:
                story.append(Paragraph(f"<b>{' | '.join(parts)}</b>", styles["BodyText"]))
            details = entry.get("details") or []
            _append_bullet_items(story, details, styles)
        elif heading.lower() == "experience":
            company = str(entry.get("company") or "").strip()
            title = str(entry.get("title") or "").strip()
            dates = str(entry.get("dates") or "").strip()
            label = " - ".join(part for part in [title, company] if part) or company or title
            if dates:
                label = f"{label} | {dates}" if label else dates
            if label:
                story.append(Paragraph(f"<b>{label}</b>", styles["BodyText"]))
            _append_bullet_items(story, entry.get("bullets") or [], styles)
        else:
            label = str(entry.get("heading") or heading).strip()
            if label:
                story.append(Paragraph(f"<b>{label}</b>", styles["BodyText"]))
            _append_bullet_items(story, entry.get("items") or [], styles)
        story.append(Spacer(1, 0.08 * inch))


def _iter_additional_sections(resume_sections: Dict[str, Any]):
    for section in resume_sections.get("additional_sections") or []:
        if isinstance(section, dict) and section.get("heading"):
            yield section


def _render_resume_pdf_generic(resume_sections: Dict[str, Any], output_path: Path) -> None:
    """Render resume sections generically, preserving arbitrary section headings."""
    if not isinstance(resume_sections, dict):
        raise ValueError("resume_sections must be a dictionary")

    styles = getSampleStyleSheet()
    story = []

    contact_info = resume_sections.get("contact_info") or {}
    name = str(contact_info.get("name") or "").strip()
    if not name or name.lower() == "candidate":
        raise ValueError("resume_sections.contact_info.name is missing or placeholder")

    header_parts = [name]
    for key in ("email", "phone"):
        value = str(contact_info.get(key) or "").strip()
        if value:
            header_parts.append(value)
    for link in contact_info.get("links") or []:
        link_text = str(link).strip()
        if link_text:
            header_parts.append(link_text)

    story.append(Paragraph(f"<b>{name}</b>", styles["Title"]))
    story.append(Paragraph("<br/>".join(header_parts[1:]) if len(header_parts) > 1 else "", styles["BodyText"]))
    story.append(Spacer(1, 0.2 * inch))

    summary_text = str(resume_sections.get("summary") or "").strip()
    if summary_text:
        _append_section_heading(story, "Professional Summary", styles)
        story.append(Paragraph(summary_text, styles["BodyText"]))
        story.append(Spacer(1, 0.12 * inch))

    skills = [str(skill).strip() for skill in (resume_sections.get("skills") or []) if str(skill).strip()]
    if skills:
        _append_section_heading(story, "Skills", styles)
        _append_bullet_items(story, [", ".join(skills)], styles)
        story.append(Spacer(1, 0.12 * inch))

    _append_structured_section(story, "Experience", resume_sections.get("experience") or [], styles)
    _append_structured_section(story, "Education", resume_sections.get("education") or [], styles)

    for section in _iter_additional_sections(resume_sections):
        heading = str(section.get("heading") or "").strip()
        items = section.get("items") or []
        _append_section_heading(story, heading, styles)
        _append_bullet_items(story, items, styles)
        story.append(Spacer(1, 0.12 * inch))

    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )
    doc.build(story)


def _render_resume_pdf(resume_sections: Dict[str, Any], output_path: Path) -> None:
    """Render the full structured resume to a multi-page PDF."""
    if not isinstance(resume_sections, dict):
        raise ValueError("resume_sections must be a dictionary")

    styles = getSampleStyleSheet()
    story = []

    contact_info = resume_sections.get("contact_info") or {}
    name = str(contact_info.get("name") or "").strip()
    if not name or name.lower() == "candidate":
        raise ValueError("resume_sections.contact_info.name is missing or placeholder")
    email = str(contact_info.get("email") or "").strip()
    phone = str(contact_info.get("phone") or "").strip()
    links = contact_info.get("links") or []
    header_parts = [name]
    if email:
        header_parts.append(email)
    if phone:
        header_parts.append(phone)
    if links:
        header_parts.extend([str(link) for link in links if str(link).strip()])

    story.append(Paragraph("<b>{}</b>".format(name), styles["Title"]))
    story.append(Paragraph("<br/>".join(header_parts[1:]) if len(header_parts) > 1 else "", styles["BodyText"]))
    story.append(Spacer(1, 0.2 * inch))

    summary_text = resume_sections.get("summary") or ""
    if summary_text:
        story.append(Paragraph("<b>Professional Summary</b>", styles["Heading2"]))
        story.append(Paragraph(summary_text, styles["BodyText"]))
        story.append(Spacer(1, 0.15 * inch))

    skills = resume_sections.get("skills") or []
    if skills:
        story.append(Paragraph("<b>Skills</b>", styles["Heading2"]))
        story.append(Paragraph(", ".join(str(skill) for skill in skills), styles["BodyText"]))
        story.append(Spacer(1, 0.15 * inch))

    education_entries = resume_sections.get("education") or []
    if education_entries:
        story.append(Paragraph("<b>Education</b>", styles["Heading2"]))
        for education in education_entries:
            school = str(education.get("school") or "").strip()
            degree = str(education.get("degree") or "").strip()
            dates = str(education.get("dates") or "").strip()
            label = f"{degree} — {school}" if school and degree else (school or degree)
            if dates:
                label = f"{label} | {dates}" if label else dates
            story.append(Paragraph(f"<b>{label}</b>", styles["Heading3"]))
            details = education.get("details") or []
            for detail in details:
                story.append(Paragraph(f"• {detail}", styles["BodyText"]))
            story.append(Spacer(1, 0.1 * inch))

    doc = SimpleDocTemplate(str(output_path), pagesize=letter, leftMargin=0.75 * inch, rightMargin=0.75 * inch, topMargin=0.75 * inch, bottomMargin=0.75 * inch)
    doc.build(story)


def save_tailored_resume(resume_text: str, tailored_data: Dict[str, Any], job: Dict[str, Any], output_dir: str) -> str:
    """
    Save a tailored resume as a PDF file.

    Args:
        resume_text: Original resume text.
        tailored_data: Tailored content with summary, skills, bullet_rewrites.
        job: Job dictionary with title and company.
        output_dir: Directory to save the tailored resume.

    Returns:
        Full file path to the saved tailored resume.
    """
    if tailored_data.get("status") == "failed":
        logger.warning("Skipping resume PDF generation because tailoring failed for %s", job.get("title", ""))
        return ""

    try:
        company = job.get("company", "Company")
        title = job.get("title", "Position")

        sanitised_company = sanitise_filename(company)
        sanitised_title = sanitise_filename(title)
        filename = f"resume_{sanitised_title}_{sanitised_company}.pdf"

        output_path = Path(output_dir) / filename
        output_path.parent.mkdir(parents=True, exist_ok=True)

        resume_sections = tailored_data.get("resume_sections") or {}
        logger.info("[render] resume_sections before rendering: %s", resume_sections)
        if not isinstance(resume_sections, dict):
            logger.error("Tailoring returned no usable resume_sections for %s; refusing to render a placeholder resume", job.get("title", ""))
            return ""

        contact_info = resume_sections.get("contact_info") or {}
        name = str(contact_info.get("name") or "").strip()
        summary_text = str(resume_sections.get("summary") or "").strip()
        skills_entries = resume_sections.get("skills") or []
        missing_fields = []
        if not name or name.lower() == "candidate":
            missing_fields.append("contact_info.name")
        if not summary_text:
            missing_fields.append("summary")
        if not skills_entries:
            missing_fields.append("skills")

        if missing_fields:
            logger.error(
                "Refusing to render resume PDF for %s because required fields are missing: %s",
                job.get("title", ""),
                ", ".join(missing_fields),
            )
            return ""

        _render_resume_pdf_generic(resume_sections, output_path)
        logger.info(f"Generated tailored resume: {output_path}")
        return str(output_path)
    except Exception as exc:
        logger.error("Error saving tailored resume: %s", exc)
        return ""
