"""
PDF Parser Agent - Extracts resume data using Groq LLM.
"""
import json
import logging
import os
import re
from typing import Dict, Any

from groq import Groq
from pypdf import PdfReader


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Read Groq API key from environment at runtime.
GROQ_API_KEY = os.getenv("GROQ_API_KEY")


def get_groq_client() -> Groq:
    """
    Lazily create a Groq client when resume parsing is requested.
    """
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not set. Resume parsing via Groq is unavailable.")
    return Groq(api_key=GROQ_API_KEY)


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
        "email": extract_email_from_text(resume_text)
    }


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
            return {"skills": [], "experience_years": 0, "email": None}
        
        # Try Groq first, fall back to heuristic parsing if unavailable or fails
        try:
            client = get_groq_client()
            
            message = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                max_tokens=1024,
                messages=[
                    {
                        "role": "user",
                        "content": f"""Analyze this resume and extract ONLY the following information in valid JSON format:
- skills: list of 5-8 key technical or professional skills mentioned
- experience_years: total years of professional work experience (integer). If they are a student with no work experience, return 0.

Resume text:
{resume_text}

Return ONLY valid JSON with no additional text. Example format:
{{"skills": ["Python", "AWS", "Docker", "React", "PostgreSQL"], "experience_years": 5}}"""
                    }
                ]
            )
            
            response_text = message.choices[0].message.content.strip()
            
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
            
            return {
                "skills": skills,
                "experience_years": experience_years,
                "email": extract_email_from_text(resume_text)
            }
        
        except (RuntimeError, AttributeError) as e:
            # Fall back to heuristic parsing if Groq unavailable or the Groq client fails
            logger.warning(f"Groq parsing failed ({type(e).__name__}: {e}); falling back to heuristic parsing")
            return _heuristic_resume_parse(resume_text)
        
    except Exception as e:
        logger.error(f"Error parsing resume: {e}")
        return {"skills": [], "experience_years": 0, "email": None}


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
