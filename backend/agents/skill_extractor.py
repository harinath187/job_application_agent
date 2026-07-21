"""
Skill extraction and resume/job skill-overlap scoring.

Closes the gap where the candidate's extracted resume skills were parsed but
never used anywhere in job filtering or ranking: this module extracts the
skills required by a job description (LLM-first, keyword-fallback, cached
per job) and scores how well a candidate's resume skills cover them.
"""
from __future__ import annotations

import hashlib
import logging
import os
import re
from dataclasses import dataclass, field
from typing import Any

try:
    from rapidfuzz import fuzz
except ModuleNotFoundError:  # pragma: no cover - allows exact/alias-only matching without the dependency installed
    fuzz = None

try:
    from groq import Groq
except ModuleNotFoundError:  # pragma: no cover - allows heuristic-only operation without the SDK installed
    Groq = None

from utils.groq_client import GroqCallFailedError, call_groq_with_retry


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Read Groq API key from environment at runtime.
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

FUZZY_MATCH_THRESHOLD = int(os.getenv("SKILL_FUZZY_MATCH_THRESHOLD", "85"))

# Per-job LLM extraction competes with resume parsing and cover letter generation for the
# same Groq rate limit and can add one call per scraped job. Default to the free keyword
# fallback and only spend LLM calls on this when explicitly opted in.
SKILL_EXTRACTION_USE_LLM = os.getenv("SKILL_EXTRACTION_USE_LLM", "false").strip().lower() in {"1", "true", "yes"}


def get_groq_client() -> Groq:
    """
    Lazily create a Groq client when skill extraction is requested.
    """
    if Groq is None:
        raise RuntimeError("groq package is not installed. Skill extraction via Groq is unavailable.")
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not set. Skill extraction via Groq is unavailable.")
    return Groq(api_key=GROQ_API_KEY)


# Maintained skills taxonomy used by the keyword/regex fallback extractor.
SKILLS_TAXONOMY = [
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
    "REST API", "GraphQL", "Microservices", "AWS Lambda", "Firebase", "Jira", "Agile", "Scrum",
]

# Common synonym/alias pairs so "JS" matches "JavaScript", "ML" matches "Machine Learning", etc.
# Every key/value is compared after normalization (lowercased, whitespace-collapsed).
SKILL_ALIASES: dict[str, str] = {
    "js": "javascript",
    "ts": "typescript",
    "ml": "machine learning",
    "ai": "artificial intelligence",
    "nlp": "natural language processing",
    "cv": "computer vision",
    "k8s": "kubernetes",
    "postgres": "postgresql",
    "mongo": "mongodb",
    "node": "node.js",
    "nodejs": "node.js",
    "vue": "vue.js",
    "reactjs": "react",
    "react.js": "react",
    "golang": "go",
    "py": "python",
    "ci cd": "ci/cd",
    "cicd": "ci/cd",
    "rest apis": "rest api",
    "restful api": "rest api",
    "restful apis": "rest api",
    "gcp": "google cloud platform",
    "aws lambda": "lambda",
    "dl": "deep learning",
    "oop": "object oriented programming",
}

# In-memory cache of extracted skills keyed by job id or a hash of the description,
# so repeated calls for the same posting never re-invoke the LLM.
_SKILL_EXTRACTION_CACHE: dict[str, list[str]] = {}


@dataclass
class SkillOverlapResult:
    """Result of comparing a candidate's resume skills against a job's required skills."""

    overlap_score: float
    matched_skills: list[str] = field(default_factory=list)
    missing_skills: list[str] = field(default_factory=list)


def _normalize_skill(skill: str) -> str:
    normalized = re.sub(r"\s+", " ", str(skill or "").strip().lower())
    return SKILL_ALIASES.get(normalized, normalized)


def _description_cache_key(job_description: str) -> str:
    return hashlib.sha256(job_description.strip().lower().encode("utf-8")).hexdigest()


def _heuristic_extract_skills(job_description: str) -> list[str]:
    """
    Non-LLM fallback: scan the job description for taxonomy skills via substring match.
    Mirrors the fallback pattern used in pdf_parser.py's _heuristic_resume_parse.
    """
    description_lower = f" {job_description.lower()} "
    found: list[str] = []
    for skill in SKILLS_TAXONOMY:
        pattern = r"(?<![a-z0-9])" + re.escape(skill.lower()) + r"(?![a-z0-9])"
        if re.search(pattern, description_lower):
            found.append(skill)
        if len(found) >= 15:
            break
    return found


def _build_skill_extraction_prompt(job_description: str) -> str:
    return f"""Extract the required and preferred technical skills from this job description.
Return ONLY valid JSON with no additional text, in this exact format:
{{"skills": ["skill1", "skill2", ...]}}

Rules:
- Return between 5 and 15 skills.
- Use short, canonical skill names (e.g. "Python", "React", "AWS") rather than full sentences.
- Only include skills that are actually mentioned or clearly implied by the text.

Job description:
{job_description[:4000]}
"""


def extract_required_skills(job_description: str, job_id: str | None = None) -> list[str]:
    """
    Extract 5-15 required/preferred skills from a job description.

    Uses the LLM (Groq) with a structured JSON-output prompt when available,
    falling back to a keyword/regex-based extractor against SKILLS_TAXONOMY
    when the LLM key is not configured or the call fails. Results are cached
    per job (by job_id, or a hash of the description when no id is given) so
    repeated calls for the same posting never re-invoke the LLM.
    """
    if not job_description or not job_description.strip():
        return []

    cache_key = job_id or _description_cache_key(job_description)
    if cache_key in _SKILL_EXTRACTION_CACHE:
        return _SKILL_EXTRACTION_CACHE[cache_key]

    skills = _extract_required_skills_uncached(job_description)
    _SKILL_EXTRACTION_CACHE[cache_key] = skills
    return skills


def _extract_required_skills_uncached(job_description: str) -> list[str]:
    import json

    if not SKILL_EXTRACTION_USE_LLM:
        return _heuristic_extract_skills(job_description)

    try:
        client = get_groq_client()
    except RuntimeError as exc:
        logger.info("Skipping LLM skill extraction, using keyword fallback: %s", exc)
        return _heuristic_extract_skills(job_description)

    try:
        message = call_groq_with_retry(
            client,
            model="llama-3.1-8b-instant",
            max_tokens=512,
            messages=[{"role": "user", "content": _build_skill_extraction_prompt(job_description)}],
        )
        response_text = message.choices[0].message.content.strip()
        if response_text.startswith("```"):
            response_text = re.sub(r"^```(?:json)?\s*|\s*```$", "", response_text.strip()).strip()
        parsed = json.loads(response_text)
        skills = parsed.get("skills", [])
        if not isinstance(skills, list) or not skills:
            raise ValueError("LLM response did not contain a non-empty 'skills' list")
        return [str(skill).strip() for skill in skills if str(skill).strip()][:15]
    except GroqCallFailedError as exc:
        logger.warning("Groq skill extraction failed due to rate limiting, using keyword fallback: %s", exc)
        return _heuristic_extract_skills(job_description)
    except Exception as exc:
        logger.warning("Groq skill extraction failed (%s), using keyword fallback", exc)
        return _heuristic_extract_skills(job_description)


def compute_skill_overlap(resume_skills: list[str], job_skills: list[str]) -> SkillOverlapResult:
    """
    Compare a candidate's resume skills against a job's required skills.

    Pure/stateless: normalizes casing/whitespace, resolves common aliases,
    then falls back to fuzzy string matching (rapidfuzz) for near-matches
    that survive normalization but aren't exact/alias matches.
    """
    job_skills = [skill for skill in (job_skills or []) if str(skill).strip()]
    if not job_skills:
        return SkillOverlapResult(overlap_score=0.0, matched_skills=[], missing_skills=[])

    resume_normalized = {_normalize_skill(skill) for skill in (resume_skills or []) if str(skill).strip()}

    matched: list[str] = []
    missing: list[str] = []
    for job_skill in job_skills:
        normalized_job_skill = _normalize_skill(job_skill)
        if not resume_normalized:
            missing.append(job_skill)
            continue

        if normalized_job_skill in resume_normalized:
            matched.append(job_skill)
            continue

        if fuzz is not None and any(
            fuzz.token_sort_ratio(normalized_job_skill, resume_skill) >= FUZZY_MATCH_THRESHOLD
            for resume_skill in resume_normalized
        ):
            matched.append(job_skill)
            continue

        missing.append(job_skill)

    overlap_score = len(matched) / len(job_skills)
    return SkillOverlapResult(
        overlap_score=round(overlap_score, 4),
        matched_skills=matched,
        missing_skills=missing,
    )
