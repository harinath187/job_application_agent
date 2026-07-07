"""
PDF Parser Agent - Extracts resume data using Groq LLM.
"""
import json
import logging
import re
from datetime import datetime
from typing import Dict, Any

from pypdf import PdfReader

from utils.groq_client import groq_call

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

COMMON_SKILLS = [
    # Languages
    "Python", "Java", "JavaScript", "TypeScript", "C++", "C#", "Go", "Rust", "Ruby", "PHP", "Swift", "Kotlin",
    # Cloud & Infrastructure
    "AWS", "Azure", "GCP", "Docker", "Kubernetes", "Terraform", "CloudFormation",
    # Frontend
    "React", "Angular", "Vue.js", "HTML", "CSS", "SCSS", "Bootstrap", "Tailwind",
    # Backend & Frameworks
    "Node.js", "Django", "Flask", "FastAPI", "Spring", "ASP.NET", "Express", "Rails",
    # Databases
    "SQL", "PostgreSQL", "MySQL", "MongoDB", "Redis", "DynamoDB", "Cassandra",
    # DevOps & Tools
    "Git", "GitHub", "GitLab", "Jenkins", "CI/CD", "Linux", "Bash", "PowerShell",
    # Data & ML
    "Machine Learning", "TensorFlow", "PyTorch", "Pandas", "NumPy", "Scikit-learn", "Data Science",
    # Other
    "REST API", "GraphQL", "Microservices", "AWS Lambda", "Firebase", "Jira", "Agile", "Scrum"
]


EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")


def extract_email_from_text(text: str) -> str | None:
    """Extract the first valid-looking email address from resume text."""
    if not text:
        return None
    match = EMAIL_PATTERN.search(text)
    return match.group(0).lower() if match else None


def extract_text_from_pdf(pdf_path: str) -> str:
    """
    Extract raw text from a PDF using pypdf.

    Args:
        pdf_path: Path to the PDF file

    Returns:
        Extracted text as a string.
    """
    reader = PdfReader(pdf_path)
    text = []
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            text.append(page_text)
    return "\n".join(text)


def _heuristic_resume_parse(resume_text: str) -> Dict[str, Any]:
    """
    Fallback resume parsing using keyword matching when Groq is unavailable.
    """
    normalized = resume_text.lower()
    skills = []
    for skill in COMMON_SKILLS:
        if skill.lower() in normalized and skill not in skills:
            skills.append(skill)
        if len(skills) >= 8:
            break

    experience_years = 0
    for pattern in [r"(\d+)\+?\s*years?", r"(\d+)\s*years?\s*of\s*experience"]:
        match = re.search(pattern, normalized)
        if match:
            try:
                experience_years = int(match.group(1))
                break
            except ValueError:
                continue

    return {
        "skills": skills,
        "experience_years": experience_years,
        "experience": _format_experience_summary(experience_years) if experience_years else None,
        "email": extract_email_from_text(resume_text)
    }


def _format_experience_summary(years: int) -> str:
    """Convert inferred years into a user-facing experience bucket."""
    if years <= 1:
        return "Entry level"
    if years <= 3:
        return "1-3 years"
    if years <= 5:
        return "3-5 years"
    return "5+ years"


def _year_from_date_string(date_text: str) -> int | None:
    """Extract a year from a resume date string when possible."""
    if not date_text:
        return None
    match = re.search(r"(19|20)\d{2}", date_text)
    return int(match.group(0)) if match else None


def _infer_experience_from_resume_text(resume_text: str) -> tuple[int, str | None]:
    """Infer total years of experience from work-history date ranges in resume text."""
    if not resume_text:
        return 0, None

    normalized = re.sub(r"\s+", " ", resume_text)
    patterns = [
        r"(?P<start>(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?\s+\d{4})\s*[-–—to]+\s*(?P<end>Present|Current|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\.?\s+\d{4})",
        r"(?P<start>(?:19|20)\d{2})\s*[-–—to]+\s*(?P<end>Present|Current|(?:19|20)\d{2})",
    ]

    total_months = 0
    for pattern in patterns:
        for match in re.finditer(pattern, normalized, re.IGNORECASE):
            start_year = _year_from_date_string(match.group("start"))
            end_text = match.group("end")
            end_year = datetime.utcnow().year if re.search(r"present|current", end_text, re.IGNORECASE) else _year_from_date_string(end_text)
            if start_year is None or end_year is None or end_year < start_year:
                continue
            total_months += max(0, (end_year - start_year) * 12)

    if total_months <= 0:
        return 0, None

    experience_years = max(1, round(total_months / 12))
    return experience_years, _format_experience_summary(experience_years)


def parse_resume(pdf_path: str) -> Dict[str, Any]:
    """
    Extract structured data from a PDF resume using Groq LLM.
    
    Args:
        pdf_path: Path to the PDF resume file
    
    Returns:
        Dictionary with keys: skills (List[str])
    """
    try:
        # Extract text from PDF
        resume_text = extract_text_from_pdf(pdf_path)
        
        if not resume_text.strip():
            logger.warning(f"No text extracted from {pdf_path}")
            return {"skills": [], "experience_years": 0, "experience": None, "email": None}
        
        # Try Groq first, fall back to heuristic parsing if unavailable or fails
        try:
            response_text = groq_call(
                prompt=f"""Analyze this resume and extract ONLY the following information in valid JSON format:
- skills: list of 5-8 key technical or professional skills mentioned
- experience_years: total years of professional work experience (integer). If they are a student with no work experience, return 0.
- experience: a short bucket such as Entry level, 1-3 years, 3-5 years, or 5+ years.

Resume text:
{resume_text}

Return ONLY valid JSON with no additional text. Example format:
{{"skills": ["Python", "AWS", "Docker", "React", "PostgreSQL"], "experience_years": 5, "experience": "3-5 years"}}""",
                model="llama-3.1-8b-instant",
                max_tokens=1024,
            )

            # Check if response is empty before attempting JSON parsing
            if not response_text:
                logger.warning("Groq returned empty response; falling back to heuristic parsing")
                return _heuristic_resume_parse(resume_text)
            
            # Parse JSON response
            try:
                extracted_data = json.loads(response_text)
            except json.JSONDecodeError as e:
                logger.warning(
                    f"Groq response was not valid JSON ({e}); falling back to heuristic parsing. "
                    f"Response text: {response_text!r}"
                )
                return _heuristic_resume_parse(resume_text)
            
            if not isinstance(extracted_data, dict):
                logger.warning(
                    f"Groq JSON response was not a dict (type={type(extracted_data).__name__}); falling back to heuristic parsing. "
                    f"Response text: {response_text!r}"
                )
                return _heuristic_resume_parse(resume_text)
            
            skills = extracted_data.get("skills", [])
            if not isinstance(skills, list):
                logger.warning(
                    f"Groq JSON response skills field is not a list (type={type(skills).__name__}); falling back to heuristic parsing. "
                    f"Response text: {response_text!r}"
                )
                return _heuristic_resume_parse(resume_text)
            
            # Validate and set defaults
            experience_years = extracted_data.get("experience_years", 0)
            try:
                experience_years = int(experience_years) if experience_years else 0
            except (ValueError, TypeError):
                experience_years = 0

            extracted_experience = extracted_data.get("experience")
            if not isinstance(extracted_experience, str) or not extracted_experience.strip():
                inferred_years, inferred_experience = _infer_experience_from_resume_text(resume_text)
                if not experience_years and inferred_years:
                    experience_years = inferred_years
                extracted_experience = inferred_experience or _format_experience_summary(experience_years)
            
            return {
                "skills": skills,
                "experience_years": experience_years,
                "experience": extracted_experience,
                "email": extract_email_from_text(resume_text)
            }
        
        except (RuntimeError, AttributeError) as e:
            # Fall back to heuristic parsing if Groq unavailable or the Groq client fails
            logger.warning(f"Groq parsing failed ({type(e).__name__}: {e}); falling back to heuristic parsing")
            return _heuristic_resume_parse(resume_text)
        
    except Exception as e:
        logger.error(f"Error parsing resume: {e}")
        return {"skills": [], "experience_years": 0, "experience": None, "email": None}


def get_resume_text(pdf_path: str) -> str:
    """
    Extract raw text from PDF resume.
    
    Args:
        pdf_path: Path to the PDF file
    
    Returns:
        Extracted text as string
    """
    try:
        return extract_text_from_pdf(pdf_path)
    except Exception as e:
        logger.error(f"Error extracting text from PDF: {e}")
        return ""
