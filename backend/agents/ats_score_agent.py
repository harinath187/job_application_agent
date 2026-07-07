"""ATS scoring agent for tailored resumes."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from utils.groq_client import groq_call


logger = logging.getLogger(__name__)

DEFAULT_SCORE = {
    "match_pct": 0,
    "matched_keywords": [],
    "missing_keywords": [],
}


def _extract_json_block(text: str) -> str:
    """Best-effort cleanup for model responses that include stray text."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        return cleaned[start : end + 1]
    return cleaned


def _coerce_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _parse_score_response(response_text: str) -> dict:
    payload = json.loads(_extract_json_block(response_text))
    match_pct = payload.get("match_pct", 0)
    try:
        match_pct = int(round(float(match_pct)))
    except (TypeError, ValueError):
        match_pct = 0

    return {
        "match_pct": max(0, min(100, match_pct)),
        "matched_keywords": _coerce_list(payload.get("matched_keywords", [])),
        "missing_keywords": _coerce_list(payload.get("missing_keywords", []))[:8],
    }


def score_resume(resume_text: str, job_description: str) -> dict:
    """
    Returns:
    {
        "match_pct": int,
        "matched_keywords": list[str],
        "missing_keywords": list[str]
    }
    """
    base_prompt = f"""Respond with valid JSON only. No other text.

You are an ATS keyword matcher.

Task:
1. Extract the top 15-20 meaningful keywords, skills, tools, and required qualifications from the job description.
2. Compare them against the tailored resume text.
3. Return the percentage match as (matched / total) * 100, rounded to the nearest integer.
4. Return missing_keywords as only the JD keywords not found in the resume, ranked by importance.

Ranking guidance for missing_keywords:
- Highest priority: items clearly listed in requirements, must-haves, or qualifications.
- Lower priority: nice-to-haves, preferred skills, or optional tools.

Rules:
- Use exact, canonical keyword phrases when possible.
- Do not invent skills that are not clearly present in the job description.
- Return missing_keywords with a maximum of 8 items.
- Keep matched_keywords and missing_keywords as short keyword phrases.
- Return strictly this JSON shape:
{{"match_pct": 0, "matched_keywords": [], "missing_keywords": []}}

Job Description:
{job_description}

Tailored Resume:
{resume_text}
"""

    strict_prompt = (
        "Respond with valid JSON only. No other text.\n"
        "Return exactly: {\"match_pct\": 0, \"matched_keywords\": [], \"missing_keywords\": []}\n"
        "Do not include markdown fences, explanations, or extra keys.\n\n"
        f"Job Description:\n{job_description}\n\nTailored Resume:\n{resume_text}\n"
    )

    try:
        response_text = groq_call(prompt=base_prompt, model="llama-3.1-8b-instant", max_tokens=1000)
        return _parse_score_response(response_text)
    except Exception as first_error:
        logger.warning("ATS scoring parse failed on first attempt: %s", first_error)
        try:
            response_text = groq_call(prompt=strict_prompt, model="llama-3.1-8b-instant", max_tokens=700)
            return _parse_score_response(response_text)
        except Exception as second_error:
            logger.warning("ATS scoring failed twice, falling back to zero score: %s", second_error)
            return DEFAULT_SCORE.copy()
