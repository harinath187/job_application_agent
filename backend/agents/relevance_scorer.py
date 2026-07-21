"""
Heuristic relevance scoring for job-role fit.
"""
from __future__ import annotations

import os
import re
from typing import Iterable

from agents.skill_extractor import compute_skill_overlap, extract_required_skills


# Relative importance of each scoring factor in compute_final_score. Values are
# normalized against their sum, so they don't need to add up to any fixed total.
SCORE_WEIGHTS = {
    "relevance": float(os.getenv("SCORE_WEIGHT_RELEVANCE", "40")),
    "role_confidence": float(os.getenv("SCORE_WEIGHT_ROLE_CONFIDENCE", "25")),
    "experience_match": float(os.getenv("SCORE_WEIGHT_EXPERIENCE_MATCH", "15")),
    "skill_overlap": float(os.getenv("SCORE_WEIGHT_SKILL_OVERLAP", "20")),
}


_PHRASE_PATTERNS = (
    "machine learning",
    "data science",
    "software engineer",
    "frontend developer",
    "backend developer",
    "full stack",
    "full-stack",
    "project management",
    "cloud computing",
    "quality assurance",
    "business analyst",
    "devops",
    "site reliability",
    "natural language processing",
    "computer vision",
)


_SENIORITY_BUCKETS = ("fresher", "1-2", "3-5", "5+", "unspecified")


def _normalize_text(*values: str | None) -> str:
    text = " ".join(value for value in values if value)
    return re.sub(r"\s+", " ", text.lower()).strip()


def _tokenize(text: str | None) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9+#]+", _normalize_text(text)) if len(token) > 1}


def _collect_text(items: Iterable[str] | None) -> str:
    return " ".join(item for item in (items or []) if item)


def classify_job_seniority(job: dict) -> str:
    """
    Infer a coarse seniority bucket from title + description.
    """
    text = _normalize_text(job.get("title"), job.get("description"))
    if not text:
        return "unspecified"

    patterns = [
        ("fresher", (
            r"\bfresher\b",
            r"\bnew grad\b",
            r"\bentry level\b",
            r"\bentry-level\b",
            r"\bintern\b",
            r"\binternship\b",
            r"\b0\s*[-to]+\s*1\s*years?\b",
            r"\b0\s*[-to]+\s*2\s*years?\b",
        )),
        ("1-2", (
            r"\b1\s*[-to]+\s*2\s*years?\b",
            r"\b1\s*\+\s*years?\b",
            r"\b2\s*years?\b",
            r"\bjunior\b",
            r"\bassociate\b",
        )),
        ("3-5", (
            r"\b3\s*[-to]+\s*5\s*years?\b",
            r"\bmid[-\s]?level\b",
            r"\bintermediate\b",
            r"\b3\s*\+\s*years?\b",
            r"\b4\s*\+\s*years?\b",
        )),
        ("5+", (
            r"\b5\s*\+\s*years?\b",
            r"\b6\s*\+\s*years?\b",
            r"\b7\s*\+\s*years?\b",
            r"\bsenior\b",
            r"\blead\b",
            r"\bstaff\b",
            r"\bprincipal\b",
            r"\bmanager\b",
            r"\barchitect\b",
        )),
    ]

    for bucket, patterns_for_bucket in patterns:
        if any(re.search(pattern, text) for pattern in patterns_for_bucket):
            return bucket
    return "unspecified"


def compute_role_confidence(job: dict, projects: list[str], certifications: list[str]) -> float:
    """
    Estimate how closely a job matches the candidate using local keyword/phrase overlap only.
    """
    description = _normalize_text(job.get("description"))
    if not description:
        return 0.0

    candidate_text = _normalize_text(" ".join([
        _collect_text(projects),
        _collect_text(certifications),
    ]))
    if not candidate_text:
        return 0.0

    job_tokens = _tokenize(description)
    candidate_tokens = _tokenize(candidate_text)
    if not job_tokens or not candidate_tokens:
        return 0.0

    token_overlap = len(job_tokens & candidate_tokens) / max(1, len(job_tokens))
    phrase_overlap = 0.0
    for phrase in _PHRASE_PATTERNS:
        if phrase in description and phrase in candidate_text:
            phrase_overlap += 1.0

    certification_bonus = 0.0
    for cert in certifications or []:
        cert_text = _normalize_text(cert)
        if cert_text and cert_text in description:
            certification_bonus += 0.15

    score = (token_overlap * 0.65) + (min(phrase_overlap, 3.0) * 0.1) + min(certification_bonus, 0.25)
    return max(0.0, min(1.0, score))


def _normalize_experience_level(experience_level: str | None) -> str:
    normalized = _normalize_text(experience_level)
    aliases = {
        "fresher": "fresher",
        "entry": "fresher",
        "entry level": "fresher",
        "entry-level": "fresher",
        "0": "fresher",
        "0-1": "fresher",
        "1-2": "1-2",
        "1 to 2": "1-2",
        "3-5": "3-5",
        "3 to 5": "3-5",
        "5+": "5+",
        "5 plus": "5+",
    }
    return aliases.get(normalized, normalized if normalized in _SENIORITY_BUCKETS else "unspecified")


def compute_final_score(
    job: dict,
    projects: list[str],
    certifications: list[str],
    experience_level: str | None,
    resume_skills: list[str] | None = None,
) -> dict:
    """
    Combine relevance, role confidence, experience fit, and skill overlap into a
    final 0-100 score, weighted by SCORE_WEIGHTS.
    """
    relevance_score = compute_role_confidence(job, projects, certifications)
    role_confidence = float(job.get("role_confidence") or compute_role_confidence(job, projects, certifications) or 0.0)
    job_bucket = classify_job_seniority(job)
    candidate_bucket = _normalize_experience_level(experience_level)

    if job_bucket == "unspecified" or candidate_bucket == "unspecified":
        experience_match_score = 0.5 if job_bucket == "unspecified" else 0.0
    else:
        experience_match_score = 1.0 if job_bucket == candidate_bucket else 0.0

    # Filtering (job_validator.validate_jobs) already computes and caches skill
    # overlap on the job dict when resume_skills is supplied; reuse it here so
    # ranking never triggers a second LLM extraction call for the same job.
    if "skill_overlap_score" in job:
        skill_overlap_score = float(job.get("skill_overlap_score") or 0.0)
        matched_skills = job.get("matched_skills", [])
        missing_skills = job.get("missing_skills", [])
        required_skills = job.get("required_skills", [])
    elif resume_skills is not None:
        required_skills = extract_required_skills(job.get("description", ""), job_id=job.get("id"))
        overlap = compute_skill_overlap(resume_skills, required_skills)
        skill_overlap_score = overlap.overlap_score
        matched_skills = overlap.matched_skills
        missing_skills = overlap.missing_skills
    else:
        skill_overlap_score = 0.0
        matched_skills = []
        missing_skills = []
        required_skills = []

    weights = SCORE_WEIGHTS
    weight_total = sum(weights.values()) or 1.0
    final_score = (
        (relevance_score * weights["relevance"]) +
        (role_confidence * weights["role_confidence"]) +
        (experience_match_score * weights["experience_match"]) +
        (skill_overlap_score * weights["skill_overlap"])
    ) * (100.0 / weight_total)
    final_score = max(0.0, min(100.0, final_score))

    skill_match_percentage = round(skill_overlap_score * 100.0, 2)
    return {
        "final_score": round(final_score, 2),
        "relevance_score": round(relevance_score * 100.0, 2),
        "role_confidence_score": round(role_confidence * 100.0, 2),
        "experience_match_score": round(experience_match_score * 100.0, 2),
        "skill_overlap_score": round(skill_overlap_score * 100.0, 2),
        "seniority_bucket": job_bucket,
        "candidate_experience_bucket": candidate_bucket,
        "required_skills": required_skills,
        "matched_skills": matched_skills,
        "missing_skills": missing_skills,
        "skill_match_percentage": skill_match_percentage,
    }
