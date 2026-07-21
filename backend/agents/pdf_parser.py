"""
PDF Parser Agent - Extracts resume data using Groq LLM.
"""
import json
import logging
import os
import re
from collections import Counter
from datetime import datetime
from typing import Dict, Any

try:
    from groq import Groq
except ModuleNotFoundError:  # pragma: no cover - allows heuristic-only operation without the SDK installed
    Groq = None
from pypdf import PdfReader

from utils.groq_client import GroqCallFailedError, call_groq_with_retry


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Read Groq API key from environment at runtime.
GROQ_API_KEY = os.getenv("GROQ_API_KEY")


def get_groq_client() -> Groq:
    """
    Lazily create a Groq client when resume parsing is requested.
    """
    if Groq is None:
        raise RuntimeError("groq package is not installed. Resume parsing via Groq is unavailable.")
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

COMMON_COMPANY_WORDS = {
    "cisco", "confidential", "microsoft", "google", "amazon", "apple", "meta", "facebook",
    "netflix", "oracle", "ibm", "accenture", "salesforce", "adobe", "linkedin", "github",
    "slack", "zoom", "uber", "airbnb", "paypal", "tesla", "nvidia", "resume", "candidate"
}

SECTION_ALIASES = {
    "experience": (
        "experience", "work experience", "professional experience", "employment history", "career history"
    ),
    "education": (
        "education", "academic background", "education and training", "qualifications"
    ),
    "projects": (
        "projects", "project experience", "selected projects", "academic projects"
    ),
    "certifications": (
        "certifications", "certification", "licenses", "licenses and certifications", "credentials"
    ),
}

GENERIC_SECTION_HEADINGS = {
    "summary",
    "skills",
    "experience",
    "education",
    "projects",
    "certifications",
    "awards",
    "publications",
    "languages",
    "volunteer",
    "volunteer experience",
    "hobbies",
    "interests",
}

EDUCATION_HEADER_HINTS = ("education", "academic", "qualification", "qualifications")


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


def _clean_resume_text(resume_text: str) -> str:
    """Remove obvious repeated watermark/header noise before parsing."""
    if not resume_text:
        return ""

    lines = [line.strip() for line in resume_text.splitlines() if line.strip()]
    if not lines:
        return ""

    counts = Counter(lines)
    cleaned_lines = []
    for line in lines:
        line_lower = line.lower()
        is_repeated_boilerplate = counts[line] >= 3 and (
            line_lower in COMMON_COMPANY_WORDS or "confidential" in line_lower
        )
        if not is_repeated_boilerplate:
            cleaned_lines.append(line)

    return "\n".join(cleaned_lines).strip()


def _normalize_header_text(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def _looks_like_section_header(line: str) -> bool:
    if not line:
        return False
    stripped = line.strip()
    normalized = _normalize_header_text(stripped.rstrip(":"))
    if not normalized:
        return False
    words = normalized.split()
    if normalized in GENERIC_SECTION_HEADINGS:
        return True
    if stripped.endswith(":") and len(words) <= 5:
        return True
    if len(words) <= 4 and stripped == stripped.upper() and any(ch.isalpha() for ch in stripped):
        return True
    if len(words) <= 4 and stripped[0].isupper() and not any(ch.isdigit() for ch in stripped):
        return True
    return False


def _is_probable_section_header(line: str, next_line: str = "", line_index: int = 0, allow_title_case: bool = True) -> bool:
    """Detect section headers without confusing the top-of-resume name block for a section."""
    if not line:
        return False
    stripped = line.strip()
    normalized = _normalize_header_text(stripped.rstrip(":"))
    words = normalized.split()
    if normalized in GENERIC_SECTION_HEADINGS:
        return True
    if normalized in {alias for aliases in SECTION_ALIASES.values() for alias in aliases}:
        return True
    if stripped.endswith(":") and len(words) <= 6 and not re.search(r"\d", stripped):
        return True
    if len(words) <= 4 and stripped == stripped.upper() and any(ch.isalpha() for ch in stripped):
        return True
    if allow_title_case and line_index > 2 and len(words) <= 4 and stripped == stripped.title() and not re.search(r"\d", stripped) and (
        _looks_like_section_content(next_line) or _looks_like_date(next_line)
    ):
        return True
    return False


def _looks_like_section_content(line: str) -> bool:
    stripped = (line or "").strip()
    return bool(stripped.startswith(("-", "•", "*")) or _looks_like_date(stripped))


def _is_probable_name_candidate(candidate: str, email: str | None = None) -> bool:
    """Score whether a candidate line looks like a real person's name."""
    if not candidate:
        return False

    cleaned = re.sub(r"\s+", " ", candidate).strip()
    if len(cleaned) < 2:
        return False

    normalized = cleaned.lower()
    if normalized in COMMON_COMPANY_WORDS:
        return False
    if "confidential" in normalized or "resume" in normalized or "curriculum" in normalized:
        return False
    if re.fullmatch(r"[A-Za-z]{1,2}", cleaned):
        return False
    if any(char.isdigit() for char in cleaned):
        return False

    if email:
        local_part = email.split("@", 1)[0].lower()
        local_letters = re.sub(r"[^a-z0-9]+", "", local_part)
        candidate_letters = re.sub(r"[^a-z0-9]+", "", normalized)
        if local_letters and candidate_letters:
            if candidate_letters in local_letters or local_letters in candidate_letters:
                return True
            shared_chars = len(set(candidate_letters) & set(local_letters))
            if shared_chars >= 3:
                return True

    return len(cleaned.split()) <= 4 and not cleaned.startswith(("http://", "https://"))


def _extract_name_from_resume_text(resume_text: str, email: str | None = None) -> str:
    """Extract a likely candidate name from resume text, ignoring repetitive watermarks."""
    text = _clean_resume_text(resume_text) or resume_text or ""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return ""

    candidates = []
    first_section_index = len(lines)
    for idx, line in enumerate(lines):
        next_line = lines[idx + 1] if idx + 1 < len(lines) else ""
        if _is_probable_section_header(line, next_line=next_line, line_index=idx, allow_title_case=True):
            first_section_index = idx
            break

    for line in lines[:first_section_index]:
        if EMAIL_PATTERN.search(line):
            continue
        if line.lower().startswith(("http://", "https://")):
            continue
        if line.startswith(("-", "•", "*")):
            continue
        if _looks_like_date(line):
            continue
        if _looks_like_section_header(line):
            continue
        if not _is_probable_name_candidate(line, email=email):
            continue
        score = 0
        if len(line.split()) >= 2:
            score += 2
        if any(token[0].isupper() for token in line.split()):
            score += 1
        if email:
            local_part = email.split("@", 1)[0].lower()
            candidate_letters = re.sub(r"[^a-z0-9]+", "", line.lower())
            if local_part and candidate_letters and (candidate_letters in local_part or local_part in candidate_letters):
                score += 3
        candidates.append((score, line))

    if candidates:
        candidates.sort(key=lambda item: item[0], reverse=True)
        return candidates[0][1]

    for line in lines:
        if line.lower() in COMMON_COMPANY_WORDS:
            continue
        if len(re.sub(r"\s+", " ", line).split()) <= 4:
            return line

    return ""


def _extract_resume_sections_from_text(resume_text: str, email: str | None = None) -> Dict[str, Any]:
    """Create a lightweight structured section parser that tolerates noisy resume text."""
    cleaned_text = _clean_resume_text(resume_text) or resume_text or ""
    lines = [line.strip() for line in cleaned_text.splitlines() if line.strip()]
    name = _extract_name_from_resume_text(cleaned_text, email=email)

    contact_info = {
        "name": name,
        "email": email or extract_email_from_text(cleaned_text),
        "phone": "",
        "links": [],
    }

    sections = {
        "contact_info": contact_info,
        "summary": "",
        "skills": [],
        "projects": [],
        "certifications": [],
        "experience": [],
        "education": [],
        "additional_sections": [],
    }

    section_name = None
    section_heading = ""
    section_lines: list[str] = []

    def flush_section() -> None:
        nonlocal section_name, section_heading, section_lines
        if not section_name or not section_lines:
            return
        if section_name == "education":
            parsed_entry = _parse_education_entry(section_lines)
            if parsed_entry.get("degree") or parsed_entry.get("institution") or parsed_entry.get("dates"):
                sections["education"].append(parsed_entry)
        elif section_name == "experience":
            sections["experience"].append(_parse_experience_entry(section_lines))
        elif section_name == "skills":
            sections["skills"] = _parse_generic_section_entries(section_lines)
        elif section_name == "summary":
            sections["summary"] = " ".join(_parse_generic_section_entries(section_lines)).strip()
        elif section_name == "projects":
            sections["projects"] = _parse_generic_section_entries(section_lines)
        elif section_name == "certifications":
            sections["certifications"] = _parse_generic_section_entries(section_lines)
        else:
            sections["additional_sections"].append({
                "heading": section_heading,
                "items": _parse_generic_section_entries(section_lines),
            })
        section_name = None
        section_heading = ""
        section_lines = []

    for idx, line in enumerate(lines):
        next_line = lines[idx + 1] if idx + 1 < len(lines) else ""
        normalized = _normalize_header_text(line.rstrip(":"))
        if _is_probable_section_header(line, next_line=next_line, line_index=idx):
            flush_section()
            if normalized in {alias for aliases in SECTION_ALIASES.values() for alias in aliases}:
                section_name = next(section for section, aliases in SECTION_ALIASES.items() if normalized in aliases)
            elif any(hint in normalized for hint in EDUCATION_HEADER_HINTS):
                section_name = "education"
            elif "skill" in normalized:
                section_name = "skills"
            elif "project" in normalized:
                section_name = "projects"
            elif "certification" in normalized or "license" in normalized or "credential" in normalized:
                section_name = "certifications"
            elif "summary" in normalized or "profile" in normalized:
                section_name = "summary"
            elif "experience" in normalized and "volunteer" not in normalized and "community" not in normalized:
                section_name = "experience"
            else:
                section_name = "additional"
                section_heading = line.strip().rstrip(":")
            continue

        if section_name is None:
            continue
        section_lines.append(line)

    flush_section()

    if not sections["experience"]:
        experience_start = None
        for idx, line in enumerate(lines):
            normalized = _normalize_header_text(line.rstrip(":"))
            if normalized == "experience":
                experience_start = idx + 1
                break
        if experience_start is not None:
            experience_lines = []
            for line in lines[experience_start:]:
                normalized = _normalize_header_text(line.rstrip(":"))
                if normalized in {alias for aliases in SECTION_ALIASES.values() for alias in aliases} or any(hint in normalized for hint in EDUCATION_HEADER_HINTS):
                    break
                experience_lines.append(line)
            parsed_experience = _parse_experience_entry(experience_lines)
            if parsed_experience.get("bullets") or parsed_experience.get("company") or parsed_experience.get("title"):
                sections["experience"].append(parsed_experience)

    if sections["education"] and not sections["education"][0].get("grade"):
        education_start = None
        for idx, line in enumerate(lines):
            normalized = _normalize_header_text(line.rstrip(":"))
            if any(hint in normalized for hint in EDUCATION_HEADER_HINTS):
                education_start = idx + 1
                break
        if education_start is not None:
            for line in lines[education_start:]:
                normalized = _normalize_header_text(line.rstrip(":"))
                if normalized in {alias for aliases in SECTION_ALIASES.values() for alias in aliases} or normalized.endswith("experience"):
                    break
                grade_match = re.search(r"\b(?:cgpa|gpa|grade|percentage)\s*[:\-]?\s*([0-9.]+(?:/\s*[0-9.]+)?%?)", line, re.IGNORECASE)
                if grade_match:
                    sections["education"][0]["grade"] = grade_match.group(1).strip()
                    break

    if sections["education"] and sections["additional_sections"]:
        kept_additional = []
        for section in sections["additional_sections"]:
            heading = str(section.get("heading") or "").strip()
            heading_grade_match = re.search(r"\b(?:cgpa|gpa|grade|percentage)\s*[:\-]?\s*([0-9.]+(?:/\s*[0-9.]+)?%?)", heading, re.IGNORECASE)
            if heading_grade_match:
                if not sections["education"][0].get("grade"):
                    sections["education"][0]["grade"] = heading_grade_match.group(1).strip()
                sections["education"][0].setdefault("details", []).extend(section.get("items") or [])
            else:
                kept_additional.append(section)
        sections["additional_sections"] = kept_additional

    return sections


def _extract_section_entries_by_headers(resume_text: str, keywords: tuple[str, ...]) -> list[str]:
    cleaned_text = _clean_resume_text(resume_text) or resume_text or ""
    lines = [line.strip() for line in cleaned_text.splitlines() if line.strip()]
    collected: list[str] = []
    collecting = False
    for idx, line in enumerate(lines):
        normalized = _normalize_header_text(line.rstrip(":"))
        if any(keyword in normalized for keyword in keywords):
            collecting = True
            continue
        if collecting and _is_probable_section_header(line, next_line=lines[idx + 1] if idx + 1 < len(lines) else "", line_index=idx):
            break
        if collecting:
            collected.extend(_parse_generic_section_entries([line]))
    return [item for item in collected if item]


def _heuristic_extract_projects(resume_text: str) -> list[str]:
    explicit = _extract_section_entries_by_headers(resume_text, ("project",))
    if explicit:
        return explicit
    pattern = re.compile(r"(?im)^\s*(?:[-*•]|\d+[.)])\s*(.+(?:project|built|developed|implemented|designed).*)$")
    items = [match.group(1).strip() for match in pattern.finditer(resume_text or "")]
    return list(dict.fromkeys(items))


def _heuristic_extract_certifications(resume_text: str) -> list[str]:
    explicit = _extract_section_entries_by_headers(resume_text, ("certification", "license", "credential"))
    if explicit:
        return explicit
    pattern = re.compile(r"(?im)^\s*(?:[-*•]|\d+[.)])\s*(.+(?:certif|license|credential|aws|azure|pmp|cissp|cisa|scrum).*)$")
    items = [match.group(1).strip() for match in pattern.finditer(resume_text or "")]
    return list(dict.fromkeys(items))


def _parse_generic_section_entries(section_lines: list[str]) -> list[str]:
    items: list[str] = []
    current_item: list[str] = []
    for line in section_lines:
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(("-", "•", "*")):
            if current_item:
                items.append(" ".join(current_item).strip())
            current_item = [stripped.lstrip("-•*").strip()]
            continue
        if current_item and (_looks_like_section_header(stripped) or _looks_like_date(stripped)):
            items.append(" ".join(current_item).strip())
            current_item = [stripped]
        elif current_item:
            current_item.append(stripped)
        else:
            items.append(stripped)
    if current_item:
        items.append(" ".join(current_item).strip())
    return [item for item in items if item]


def _parse_education_entry(block_lines: list[str]) -> Dict[str, Any]:
    entry_text = " | ".join(block_lines)
    degree = ""
    institution = ""
    location = ""
    dates = ""
    grade = ""

    date_match = re.search(r"((?:19|20)\d{2}(?:\s*[-–—to]+\s*(?:19|20)\d{2}|(?:\s*[-–—to]+\s*(?:present|current)))?)", entry_text, re.IGNORECASE)
    if date_match:
        dates = date_match.group(1).strip()

    grade_match = re.search(r"\b(?:gpa|cgpa|grade|percentage)\s*[:\-]?\s*([0-9.]+(?:/\s*[0-9.]+)?%?)", entry_text, re.IGNORECASE)
    if grade_match:
        grade = grade_match.group(1).strip()

    cleaned_lines = [line.strip().lstrip("•-*").strip() for line in block_lines if line.strip()]
    for line in cleaned_lines:
        if not degree and re.search(r"\b(b\.?tech|m\.?tech|bachelor|master|mba|ph\.?d|b\.?sc|m\.?sc|associate|diploma)\b", line, re.IGNORECASE):
            degree = line
            continue
        if not institution and not _looks_like_date(line) and line != degree:
            institution = line
            continue
        if not location and not _looks_like_date(line) and line not in {degree, institution, grade}:
            location = line

    if not degree and cleaned_lines:
        degree = cleaned_lines[0]
    if not institution and len(cleaned_lines) > 1:
        institution = cleaned_lines[1]

    details = [line for line in cleaned_lines if line not in {degree, institution, location, dates, grade}]
    for line in cleaned_lines:
        if line not in details and line not in {degree, institution, location, dates, grade}:
            details.append(line)
    return {
        "degree": degree,
        "institution": institution,
        "location": location,
        "dates": dates,
        "grade": grade,
        "details": details,
    }


def _parse_experience_entry(block_lines: list[str]) -> Dict[str, Any]:
    cleaned_lines = [line.strip().lstrip("•-*").strip() for line in block_lines if line.strip()]
    title = ""
    company = ""
    dates = ""
    bullets: list[str] = []

    for line in cleaned_lines:
        if not title and "," in line:
            title, company = [part.strip() for part in line.split(",", 1)]
            continue
        if not title and not _looks_like_date(line) and not line.startswith("-"):
            title = line
            continue
        if not company and re.search(r"\b(?:inc|llc|ltd|corp|company|systems|technologies|solutions|labs)\b", line, re.IGNORECASE):
            company = line
            continue
        if not dates and _looks_like_date(line):
            dates = line
            continue
        bullets.append(line)

    if not company and len(cleaned_lines) > 1 and "," in cleaned_lines[0]:
        title, company = [part.strip() for part in cleaned_lines[0].split(",", 1)]

    return {
        "company": company,
        "title": title,
        "dates": dates,
        "bullets": bullets,
    }


def _looks_like_date(text: str) -> bool:
    """Return true for common date-like text in resume sections."""
    if not text:
        return False
    return bool(re.search(r"(19|20)\d{2}|present|current|jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec", text, re.IGNORECASE))


def _heuristic_resume_parse(resume_text: str) -> Dict[str, Any]:
    """
    Fallback resume parsing using keyword matching when Groq is unavailable.
    """
    cleaned_resume_text = _clean_resume_text(resume_text) or resume_text or ""
    normalized = cleaned_resume_text.lower()
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

    email = extract_email_from_text(cleaned_resume_text)
    resume_sections = _extract_resume_sections_from_text(cleaned_resume_text, email=email)
    resume_sections["skills"] = skills
    resume_sections["projects"] = _heuristic_extract_projects(cleaned_resume_text)
    resume_sections["certifications"] = _heuristic_extract_certifications(cleaned_resume_text)

    return {
        "skills": skills,
        "experience_level": _detect_experience_level(cleaned_resume_text),
        "experience_years": experience_years,
        "experience": _format_experience_summary(experience_years) if experience_years else None,
        "email": email,
        "resume_text": cleaned_resume_text,
        "resume_sections": resume_sections,
        "projects": resume_sections["projects"],
        "certifications": resume_sections["certifications"],
    }


def _detect_experience_level(resume_text: str) -> str | None:
    """Return fresher/1-2/3-5/5+ when the resume contains enough evidence."""
    if not resume_text:
        return None

    normalized = re.sub(r"\s+", " ", resume_text.lower())

    explicit = [
        int(match.group(1))
        for match in re.finditer(r"(\d+)\+?\s*years?\s*(?:of\s*)?(?:professional\s*)?(?:experience|work)", normalized)
    ]
    if explicit:
        years = max(explicit)
        if years <= 0:
            return "fresher"
        if years <= 2:
            return "1-2"
        if years <= 5:
            return "3-5"
        return "5+"

    if re.search(r"\bintern(ship)?\b", normalized):
        return "fresher"

    if re.search(r"(19|20)\d{2}\s*[-–—to]+\s*(?:present|current|(19|20)\d{2})", normalized):
        inferred_years, _ = _infer_experience_from_resume_text(resume_text)
        if inferred_years <= 0:
            return "fresher"
        if inferred_years <= 2:
            return "1-2"
        if inferred_years <= 5:
            return "3-5"
        return "5+"

    return None


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


def _build_resume_extraction_prompt(resume_text_for_parsing: str) -> str:
    """Build the Groq prompt used for resume extraction."""
    return f"""Analyze this resume and extract ONLY the following information in valid JSON format:
- skills: list of 5-8 key technical or professional skills mentioned.
- projects: list of notable projects, hackathons, research projects, or portfolio items.
- certifications: list of professional certifications, licenses, or credentials.
- experience_years: total years of professional work experience (integer). If they are a student with no work experience, return 0.
- experience: a short bucket such as Entry level, 1-3 years, 3-5 years, or 5+ years.
- resume_sections: an object with contact_info, summary, skills, projects, certifications, experience, education, and additional_sections.
  - Identify every section header actually present in this resume, using formatting and content cues. Do not assume a fixed set of sections. Group all bullet points and facts under the section header that immediately precedes them in the original document order. Never merge content from one section into a different section.
  - contact_info should include name, email, phone, and links.
  - experience should be an array of objects with company, title, dates, and bullets.
  - education should be an array of objects with degree, institution, location, dates, grade, and details.
- additional_sections should be a list of objects shaped like {{heading: string, items: string[]}}; use it for certifications, projects, awards, publications, languages, hobbies, or any other section not represented by the well-known fields.
  - For the section that corresponds to education, parse each entry into a single structured object instead of splitting every fragment into separate bullets.
  - Ignore repeated header/footer text, confidentiality watermarks, or company names that appear as page stamps.
  - The candidate's name is a person's full name, typically appearing near the top of the resume in a larger font or near contact details like email/phone.

Resume text:
{resume_text_for_parsing}

Return ONLY valid JSON with no additional text."""


def _normalize_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def parse_resume(pdf_path: str) -> Dict[str, Any]:
    """
    Extract structured data from a PDF resume using Groq LLM.
    
    Args:
        pdf_path: Path to the PDF resume file
    
    Returns:
        Dictionary with keys: skills (List[str]), resume_sections (dict)
    """
    try:
        resume_text = extract_text_from_pdf(pdf_path)
        logger.info("[pdf_parser] raw extracted text from %s:\n%s", pdf_path, resume_text)
        cleaned_resume_text = _clean_resume_text(resume_text)
        resume_text_for_parsing = cleaned_resume_text or resume_text

        if not resume_text.strip():
            logger.warning(f"No text extracted from {pdf_path}")
            return {
                "skills": [],
                "experience_level": None,
                "experience_years": 0,
                "experience": None,
                "email": None,
                "resume_text": "",
                "resume_sections": {
                    "contact_info": {"name": "", "email": None, "phone": "", "links": []},
                    "summary": "",
                    "skills": [],
                    "experience": [],
                    "education": [],
                    "additional_sections": [],
                },
            }

        try:
            client = get_groq_client()
            message = None
            response_text = ""
            json_error = None
            groq_call_succeeded = False
            try:
                message = call_groq_with_retry(
                    client,
                    model="llama-3.1-8b-instant",
                    max_tokens=1024,
                    messages=[
                        {
                            "role": "user",
                            "content": _build_resume_extraction_prompt(resume_text_for_parsing),
                        }
                    ]
                )
                groq_call_succeeded = True
                response_text = message.choices[0].message.content.strip()
                if response_text.startswith("```"):
                    response_text = re.sub(r"^```(?:json)?\s*|\s*```$", "", response_text.strip()).strip()
            except Exception as groq_exc:
                logger.warning("[pdf_parser] Groq call failed for %s: %s", pdf_path, groq_exc)
                return _heuristic_resume_parse(resume_text_for_parsing)

            logger.info(
                "[pdf_parser] Groq call succeeded=%s raw_response=%r",
                groq_call_succeeded,
                response_text,
            )
            if not response_text:
                logger.warning("Groq returned empty response; falling back to heuristic parsing")
                return _heuristic_resume_parse(resume_text_for_parsing)

            try:
                extracted_data = json.loads(response_text)
                logger.info("[pdf_parser] json.loads succeeded for %s", pdf_path)
            except json.JSONDecodeError as exc:
                json_error = exc
                logger.exception("[pdf_parser] json.loads failed for %s", pdf_path)
                logger.warning(
                    f"Groq response was not valid JSON ({exc}); falling back to heuristic parsing. "
                    f"Response text: {response_text!r}"
                )
                return _heuristic_resume_parse(resume_text_for_parsing)

            if not isinstance(extracted_data, dict):
                logger.warning(
                    f"Groq JSON response was not a dict (type={type(extracted_data).__name__}); falling back to heuristic parsing. "
                    f"Response text: {response_text!r}"
                )
                return _heuristic_resume_parse(resume_text_for_parsing)

            skills = extracted_data.get("skills", [])
            if not isinstance(skills, list):
                logger.warning(
                    f"Groq JSON response skills field is not a list (type={type(skills).__name__}); falling back to heuristic parsing. "
                    f"Response text: {response_text!r}"
                )
                return _heuristic_resume_parse(resume_text_for_parsing)
            projects = _normalize_string_list(extracted_data.get("projects", []))
            certifications = _normalize_string_list(extracted_data.get("certifications", []))
            experience_level = extracted_data.get("experience_level")
            if experience_level not in {"fresher", "1-2", "3-5", "5+"}:
                experience_level = _detect_experience_level(resume_text_for_parsing)

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

            resume_sections = extracted_data.get("resume_sections")
            fallback_sections = _extract_resume_sections_from_text(resume_text_for_parsing, email=extract_email_from_text(resume_text_for_parsing))
            if not isinstance(resume_sections, dict):
                resume_sections = fallback_sections
            else:
                resume_sections.setdefault("contact_info", fallback_sections.get("contact_info", {"name": "", "email": extract_email_from_text(resume_text_for_parsing), "phone": "", "links": []}))
                resume_sections.setdefault("summary", "")
                resume_sections.setdefault("skills", skills)
                resume_sections.setdefault("projects", projects)
                resume_sections.setdefault("certifications", certifications)
                if not (resume_sections.get("experience") or []):
                    resume_sections["experience"] = fallback_sections.get("experience", [])
                if not (resume_sections.get("education") or []):
                    resume_sections["education"] = fallback_sections.get("education", [])
                if not (resume_sections.get("additional_sections") or []):
                    resume_sections["additional_sections"] = fallback_sections.get("additional_sections", [])
                if not (resume_sections.get("projects") or []):
                    resume_sections["projects"] = fallback_sections.get("projects", [])
                if not (resume_sections.get("certifications") or []):
                    resume_sections["certifications"] = fallback_sections.get("certifications", [])
                if not (resume_sections.get("contact_info") or {}).get("name"):
                    resume_sections["contact_info"] = fallback_sections.get("contact_info", resume_sections.get("contact_info", {}))

            resume_sections.setdefault("contact_info", {"name": "", "email": extract_email_from_text(resume_text_for_parsing), "phone": "", "links": []})
            resume_sections.setdefault("summary", "")
            resume_sections.setdefault("skills", skills)
            resume_sections.setdefault("projects", projects)
            resume_sections.setdefault("certifications", certifications)
            resume_sections.setdefault("experience", [])
            resume_sections.setdefault("education", [])
            resume_sections.setdefault("additional_sections", [])

            logger.info(
                "[pdf_parser] parsed resume_sections keys=%s summary=%r skills=%s projects=%s certifications=%s experience_len=%d education_len=%d additional_sections_len=%d contact_name=%r",
                sorted(resume_sections.keys()),
                resume_sections.get("summary"),
                resume_sections.get("skills"),
                resume_sections.get("projects"),
                resume_sections.get("certifications"),
                len(resume_sections.get("experience") or []),
                len(resume_sections.get("education") or []),
                len(resume_sections.get("additional_sections") or []),
                (resume_sections.get("contact_info") or {}).get("name"),
            )
            logger.info("[pdf_parser] full resume_sections=%s", resume_sections)

            return {
                "skills": skills,
                "projects": projects,
                "certifications": certifications,
                "experience_level": experience_level,
                "experience_years": experience_years,
                "experience": extracted_experience,
                "email": extract_email_from_text(resume_text_for_parsing),
                "resume_text": resume_text_for_parsing,
                "resume_sections": resume_sections,
            }

        except GroqCallFailedError:
            logger.warning("Groq resume parsing failed after retries; falling back to heuristic parsing")
            return _heuristic_resume_parse(resume_text_for_parsing)
        except (RuntimeError, AttributeError) as exc:
            logger.warning(f"Groq parsing failed ({type(exc).__name__}: {exc}); falling back to heuristic parsing")
            return _heuristic_resume_parse(resume_text_for_parsing)

    except GroqCallFailedError:
        raise
    except Exception as exc:
        logger.exception("[pdf_parser] parse_resume failed for %s", pdf_path)
        return {
            "skills": [],
            "projects": [],
            "certifications": [],
            "experience_level": None,
            "experience_years": 0,
            "experience": None,
            "email": None,
            "resume_text": "",
                "resume_sections": {
                    "contact_info": {"name": "", "email": None, "phone": "", "links": []},
                    "summary": "",
                    "skills": [],
                    "projects": [],
                    "certifications": [],
                    "experience": [],
                    "education": [],
                    "additional_sections": [],
                },
            }


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
