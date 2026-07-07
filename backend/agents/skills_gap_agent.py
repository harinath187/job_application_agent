"""Skills gap analysis agent for tailored job matching."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from utils.groq_client import groq_call


logger = logging.getLogger(__name__)

DEFAULT_GAP = {
    "missing_skills": [],
    "transferable_skills": [],
    "suggestions": [],
}


def _extract_json_block(text: str) -> str:
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


def _coerce_suggestions(value: Any) -> list[dict]:
    if not isinstance(value, list):
        return []
    suggestions: list[dict] = []
    for item in value[:5]:
        if not isinstance(item, dict):
            continue
        skill = str(item.get("skill", "")).strip()
        resource_type = str(item.get("resource_type", "")).strip()
        note = str(item.get("note", "")).strip()
        if skill and resource_type and note:
            suggestions.append({
                "skill": skill,
                "resource_type": resource_type,
                "note": note,
            })
    return suggestions


def _parse_gap_response(response_text: str) -> dict:
    payload = json.loads(_extract_json_block(response_text))
    return {
        "missing_skills": _coerce_list(payload.get("missing_skills", []))[:5],
        "transferable_skills": _coerce_list(payload.get("transferable_skills", [])),
        "suggestions": _coerce_suggestions(payload.get("suggestions", [])),
    }


def analyze_gap(candidate_skills: list[str], job_description: str) -> dict:
    """
    Returns:
    {
        "missing_skills": list[str],
        "transferable_skills": list[str],
        "suggestions": list[dict]
    }
    """
    skills_text = ", ".join(candidate_skills or [])
    base_prompt = f"""Respond with valid JSON only. No other text.

You are a career coach performing a qualitative skills gap analysis.

Task:
1. Read the candidate's extracted skills and the job description.
2. Identify up to 5 hard gaps: required skills the candidate does not clearly demonstrate.
3. Identify transferable skills: candidate skills that partially or strongly relate to a gap.
4. For each hard gap, suggest a learning resource type and a short note that explains how to close the gap.

Important:
- This is broader than ATS keyword matching. Judge capability, not just exact text overlap.
- Focus on required skills and qualifications from the job description.
- Keep missing_skills to at most 5 items.
- Keep suggestions to at most 5 items.
- Suggestions must use a generic resource_type, not a real URL.
- Return strictly this JSON shape:
{{"missing_skills": [], "transferable_skills": [], "suggestions": []}}

Candidate extracted skills:
{skills_text}

Job description:
{job_description}
"""

    strict_prompt = (
        "Respond with valid JSON only. No other text.\n"
        "Return exactly: {\"missing_skills\": [], \"transferable_skills\": [], \"suggestions\": []}\n"
        "Do not include markdown fences, explanations, or extra keys.\n\n"
        f"Candidate extracted skills:\n{skills_text}\n\nJob description:\n{job_description}\n"
    )

    try:
        response_text = groq_call(prompt=base_prompt, model="llama-3.1-8b-instant", max_tokens=1000)
        return _parse_gap_response(response_text)
    except Exception as first_error:
        logger.warning("Skills gap parse failed on first attempt: %s", first_error)
        try:
            response_text = groq_call(prompt=strict_prompt, model="llama-3.1-8b-instant", max_tokens=700)
            return _parse_gap_response(response_text)
        except Exception as second_error:
            logger.warning("Skills gap analysis failed twice, falling back to empty result: %s", second_error)
            return DEFAULT_GAP.copy()
