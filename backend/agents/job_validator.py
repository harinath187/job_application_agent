"""
Heuristic job validation for description quality and seniority fit.
"""
from __future__ import annotations

import logging
import re
from typing import Any


logger = logging.getLogger(__name__)


_SENIORITY_PATTERNS: list[tuple[str, tuple[str, ...]]] = [
    ("fresher", (
        r"\bfresher\b",
        r"\bnew grad\b",
        r"\bentry level\b",
        r"\bintern\b",
        r"\binternship\b",
        r"\b0\s*[-to]+\s*1\s*years?\b",
        r"\b0\s*[-to]+\s*2\s*years?\b",
        r"\b0\s*\+\s*years?\b",
    )),
    ("1-2", (
        r"\b1\s*[-to]+\s*2\s*years?\b",
        r"\b1\s*\+\s*years?\b",
        r"\b1-2\s*years?\b",
        r"\b2\s*years?\b",
        r"\bassociate\b",
        r"\bjunior\b",
    )),
    ("3-5", (
        r"\b3\s*[-to]+\s*5\s*years?\b",
        r"\b3-5\s*years?\b",
        r"\bmid[-\s]?level\b",
        r"\bintermediate\b",
        r"\b3\s*\+\s*years?\b",
        r"\b4\s*\+\s*years?\b",
    )),
    ("5+", (
        r"\b5\s*\+\s*years?\b",
        r"\b5\+?\s*years?\b",
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


def _normalize_text(*parts: Any) -> str:
    return " ".join(str(part).strip() for part in parts if part is not None and str(part).strip()).lower()


def _has_short_description(job: dict[str, Any]) -> bool:
    description = str(job.get("description", "") or "").strip()
    return len(description) >= 20


def _classify_seniority(job: dict[str, Any]) -> str:
    text = _normalize_text(job.get("title", ""), job.get("description", ""))
    if not text:
        return "unspecified"

    matched_bucket = None
    matched_score = -1
    for score, (bucket, patterns) in enumerate(_SENIORITY_PATTERNS):
        if any(re.search(pattern, text) for pattern in patterns):
            if score >= matched_score:
                matched_bucket = bucket
                matched_score = score

    return matched_bucket or "unspecified"


def _normalize_candidate_level(experience_level: str | None) -> str:
    normalized = (experience_level or "").strip().lower()
    if normalized in {"fresher", "0", "0-1", "0 to 1", "0-1 years", "entry", "entry-level"}:
        return "fresher"
    if normalized in {"1-2", "1 to 2", "1-2 years", "1-2 yrs", "1-2 year", "1-2 years experience"}:
        return "1-2"
    if normalized in {"3-5", "3 to 5", "3-5 years", "3-5 yrs", "3-5 year", "3-5 years experience"}:
        return "3-5"
    if normalized in {"5+", "5 plus", "5+ years", "5+ yrs", "5+ year", "5+ years experience"}:
        return "5+"
    return normalized if normalized in {"fresher", "1-2", "3-5", "5+"} else "unspecified"


def _bucket_conflicts(candidate_bucket: str, job_bucket: str) -> bool:
    if job_bucket == "unspecified" or candidate_bucket == "unspecified":
        return False
    if candidate_bucket == "fresher":
        return job_bucket not in {"fresher", "1-2"}
    if candidate_bucket == "1-2":
        return job_bucket not in {"fresher", "1-2"}
    if candidate_bucket == "3-5":
        return job_bucket not in {"3-5", "5+"}
    if candidate_bucket == "5+":
        return job_bucket != "5+"
    return candidate_bucket != job_bucket


def validate_jobs(jobs: list[dict[str, Any]], experience_level: str | None) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """
    Filter jobs based on description quality and experience fit.
    """
    total_before = len(jobs or [])
    dropped_no_description = 0
    dropped_seniority_mismatch = 0

    candidate_bucket = _normalize_candidate_level(experience_level)
    validated: list[dict[str, Any]] = []

    for job in jobs or []:
        if not _has_short_description(job):
            dropped_no_description += 1
            continue

        job_bucket = _classify_seniority(job)
        if _bucket_conflicts(candidate_bucket, job_bucket):
            dropped_seniority_mismatch += 1
            continue

        validated.append(job)

    stats = {
        "total_before": total_before,
        "dropped_no_description": dropped_no_description,
        "dropped_seniority_mismatch": dropped_seniority_mismatch,
        "total_after": len(validated),
    }
    logger.info(
        "Validated %s jobs: before=%s dropped_no_description=%s dropped_seniority_mismatch=%s after=%s candidate_bucket=%s",
        len(validated),
        total_before,
        dropped_no_description,
        dropped_seniority_mismatch,
        len(validated),
        candidate_bucket,
    )
    return validated, stats
