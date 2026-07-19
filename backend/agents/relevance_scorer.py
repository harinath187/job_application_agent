"""
Heuristic relevance scoring for job-role fit.
"""
import re
from typing import Iterable


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


def _normalize_text(value: str | None) -> str:
    return re.sub(r"\s+", " ", (value or "").lower()).strip()


def _tokenize(text: str | None) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9+#]+", _normalize_text(text)) if len(token) > 1}


def _collect_text(items: Iterable[str] | None) -> str:
    return " ".join(item for item in (items or []) if item)


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
