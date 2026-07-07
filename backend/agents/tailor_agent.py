"""
Tailor Agent - Tailors resume content to match job requirements using Groq LLM.
"""
import json
import logging
import re
from pathlib import Path
from typing import Dict, List, Any

from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen import canvas

from utils.groq_client import groq_call
from utils.file_helpers import sanitise_filename


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def tailor_resume(resume_text: str, job: Dict[str, Any], skills: List[str]) -> Dict[str, Any]:
    """
    Tailor resume content to match a specific job posting.
    
    Args:
        resume_text: Full text from the candidate's resume
        job: Job dictionary with keys: title, company, location, description, job_url
        skills: List of extracted skills from resume
    
    Returns:
        Dictionary with keys: rewritten_summary (str), revised_skills (List[str]), 
        bullet_rewrites (List[str])
    """
    try:
        # Truncate job description to 800 characters for prompt efficiency
        job_description_snippet = job.get('description', '')[:800]
        
        prompt = f"""You are a professional resume writer. Tailor the following resume to match the job posting.

IMPORTANT: Do NOT fabricate experience or skills. Only rewrite existing content to emphasize relevant qualifications.

Job Title: {job.get('title', '')}
Company: {job.get('company', '')}
Job Description:
{job_description_snippet}

Current Resume:
{resume_text}

Current Extracted Skills: {', '.join(skills)}

Provide a JSON response with:
1. rewritten_summary: A 2-3 sentence professional summary tailored to this job (emphasizing relevant background)
2. revised_skills: A list of relevant skills from the resume and provided skills, prioritized for this role (5-8 items). Only include skills that appear in either the Current Resume text or the Current Extracted Skills list. Do not add skills not present in either source.
3. bullet_rewrites: Identify the 3 experience bullets from the resume most relevant to this job, then rewrite each one to better match the job description's language — without changing the underlying achievement or adding new experience.

IMPORTANT: Mirror the exact keywords and phrases from the job description where they honestly reflect the candidate's experience. This improves ATS compatibility.

If there are fewer than 3 experience bullets in the resume, return however many exist. Never return null for any field — use an empty list [] if needed.

Return ONLY valid JSON with no additional text. Example format:
{{"rewritten_summary": "...", "revised_skills": [...], "bullet_rewrites": [...]}}"""
        
        response_text = groq_call(prompt=prompt, model="llama-3.1-8b-instant", max_tokens=1500)
        
        # Parse JSON response
        tailored_data = json.loads(response_text)
        
        return {
            "rewritten_summary": str(tailored_data.get("rewritten_summary", "")),
            "revised_skills": tailored_data.get("revised_skills", skills) if isinstance(tailored_data.get("revised_skills"), list) else skills,
            "bullet_rewrites": tailored_data.get("bullet_rewrites", []) if isinstance(tailored_data.get("bullet_rewrites"), list) else []
        }
    
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON response from Groq: {e}")
        return {
            "rewritten_summary": "",
            "revised_skills": skills,
            "bullet_rewrites": []
        }
    except Exception as e:
        logger.error(f"Error tailoring resume: {e}")
        return {
            "rewritten_summary": "",
            "revised_skills": skills,
            "bullet_rewrites": []
        }


def _extract_candidate_name(resume_text: str) -> str:
    """Extract a candidate name from the resume text."""
    for line in resume_text.splitlines():
        cleaned = line.strip()
        if not cleaned:
            continue
        if "@" in cleaned or "http" in cleaned.lower() or re.search(r"\d", cleaned):
            continue
        return cleaned
    return "Candidate"


def _extract_fallback_summary(resume_text: str) -> str:
    """Extract first substantial paragraph (>50 chars) from resume as fallback summary."""
    for line in resume_text.splitlines():
        cleaned = line.strip()
        if len(cleaned) > 50:
            return cleaned
    return ""


def _draw_wrapped_text(c: canvas.Canvas, text: str, x: float, y: float, max_width: float, font_name: str, font_size: int, leading: int) -> float:
    """Draw wrapped text on the PDF canvas and return the new Y position."""
    lines = simpleSplit(text, font_name, font_size, max_width)
    for line in lines:
        c.drawString(x, y, line)
        y -= leading
    return y


def _start_new_page(c: canvas.Canvas) -> float:
    c.showPage()
    return letter[1] - inch


def save_tailored_resume(resume_text: str, tailored_data: Dict[str, Any], job: Dict[str, Any], output_dir: str) -> str:
    """
    Save a tailored resume as a PDF file.
    
    Args:
        resume_text: Original resume text
        tailored_data: Tailored content with rewritten_summary, revised_skills, bullet_rewrites
        job: Job dictionary with title and company
        output_dir: Directory to save the tailored resume
    
    Returns:
        Full file path to the saved tailored resume
    """
    try:
        candidate_name = _extract_candidate_name(resume_text)
        company = job.get("company", "Company")
        title = job.get("title", "Position")

        sanitised_company = sanitise_filename(company)
        sanitised_title = sanitise_filename(title)
        filename = f"resume_{sanitised_title}_{sanitised_company}.pdf"

        output_path = Path(output_dir) / filename
        output_path.parent.mkdir(parents=True, exist_ok=True)

        c = canvas.Canvas(str(output_path), pagesize=letter)
        width, height = letter
        margin = inch
        y = height - margin

        c.setFont("Helvetica-Bold", 24)
        c.drawString(margin, y, candidate_name)
        y -= 36

        def ensure_space(required_space: float, current_y: float) -> float:
            if current_y < margin + required_space:
                current_y = _start_new_page(c)
            return current_y

        # Professional Summary (with fallback to extracted text if empty)
        summary_text = tailored_data.get("rewritten_summary", "")
        if not summary_text or not isinstance(summary_text, str):
            summary_text = _extract_fallback_summary(resume_text)
        
        if summary_text:
            c.setFont("Helvetica-Bold", 14)
            c.drawString(margin, y, "Professional Summary")
            y -= 20
            c.setFont("Helvetica", 11)
            y = ensure_space(40, y)
            y = _draw_wrapped_text(c, summary_text, margin, y, width - 2 * margin, "Helvetica", 11, 14)
            y -= 16

        # Skills (only if non-empty)
        revised_skills = tailored_data.get("revised_skills", [])
        if revised_skills and isinstance(revised_skills, list) and len(revised_skills) > 0:
            y = ensure_space(40, y)
            c.setFont("Helvetica-Bold", 14)
            c.drawString(margin, y, "Skills")
            y -= 20
            c.setFont("Helvetica", 11)
            skills_text = ", ".join(str(skill) for skill in revised_skills)
            y = ensure_space(40, y)
            y = _draw_wrapped_text(c, skills_text, margin, y, width - 2 * margin, "Helvetica", 11, 14)
            y -= 16

        # Key Experience Highlights (only if non-empty)
        bullet_rewrites = tailored_data.get("bullet_rewrites", [])
        if bullet_rewrites and isinstance(bullet_rewrites, list) and len(bullet_rewrites) > 0:
            y = ensure_space(40, y)
            c.setFont("Helvetica-Bold", 14)
            c.drawString(margin, y, "Key Experience Highlights")
            y -= 20
            c.setFont("Helvetica", 11)
            for bullet in bullet_rewrites:
                y = ensure_space(40, y)
                bullet_lines = simpleSplit(str(bullet), "Helvetica", 11, width - 2 * margin - 20)
                for index, line in enumerate(bullet_lines):
                    if index == 0:
                        c.drawString(margin, y, "•")
                        c.drawString(margin + 14, y, line)
                    else:
                        c.drawString(margin + 14, y, line)
                    y -= 14
                y -= 6

        # Divider line
        y = ensure_space(30, y)
        c.setLineWidth(0.5)
        c.line(margin, y, width - margin, y)
        y -= 22

        # Full Original Resume (always included)
        y = ensure_space(40, y)
        c.setFont("Helvetica-Bold", 14)
        c.drawString(margin, y, "Full Original Resume")
        y -= 20
        c.setFont("Helvetica", 11)

        for paragraph_text in resume_text.splitlines():
            if not paragraph_text.strip():
                y -= 12
                continue
            y = ensure_space(28, y)
            y = _draw_wrapped_text(c, paragraph_text.strip(), margin, y, width - 2 * margin, "Helvetica", 11, 14)
            y -= 10

        c.save()
        logger.info(f"Generated tailored resume: {output_path}")
        return str(output_path)
    except Exception as e:
        logger.error(f"Error saving tailored resume: {e}")
        return ""
