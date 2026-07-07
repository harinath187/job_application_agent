"""Generates likely interview questions with model answers for a specific job."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from utils.groq_client import groq_call


logger = logging.getLogger(__name__)

DEFAULT_PREP = {"questions": []}


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


def _coerce_questions(value: Any) -> list[dict]:
    if not isinstance(value, list):
        return []

    questions: list[dict] = []
    for item in value[:5]:
        if not isinstance(item, dict):
            continue
        question = str(item.get("question", "")).strip()
        category = str(item.get("category", "")).strip()
        model_answer = str(item.get("model_answer", "")).strip()
        tip = str(item.get("tip", "")).strip()
        if question and category and model_answer and tip:
            questions.append(
                {
                    "question": question,
                    "category": category,
                    "model_answer": model_answer,
                    "tip": tip,
                }
            )
    return questions


def _parse_prep_response(response_text: str) -> dict:
    payload = json.loads(_extract_json_block(response_text))
    return {"questions": _coerce_questions(payload.get("questions", []))}


def generate_prep(job_description: str, tailored_resume_summary: str, missing_skills: list[str]) -> dict:
    """
    Returns:
    {
        "questions": [
            {
                "question": str,
                "category": str,
                "model_answer": str,
                "tip": str
            }
        ]
    }
    """
    missing_skills_text = ", ".join(missing_skills or [])
    base_prompt = f"""Respond with valid JSON only. No other text.

You are generating interview prep tailored to a specific job.

Requirements:
- Generate exactly 5 questions.
- Aim for a mix of 2 behavioral, 2 technical/role-specific, and 1 situational question.
- If missing_skills is non-empty, include at least one question that probes how the candidate would learn or compensate for that gap.
- Base the model answer on the candidate's actual resume content below. Do not invent experience not present in the resume.
- Keep each model_answer to 2-4 sentences.
- Category must be one of: behavioral, technical, situational.
- Return strictly this JSON shape:
{{"questions": []}}

Job description:
{job_description}

Candidate tailored resume summary:
{tailored_resume_summary}

Missing skills:
{missing_skills_text}
"""

    strict_prompt = (
        "Respond with valid JSON only. No other text.\n"
        "Return exactly: {\"questions\": []}\n"
        "Do not include markdown fences, explanations, or extra keys.\n\n"
        f"Job description:\n{job_description}\n\nCandidate tailored resume summary:\n{tailored_resume_summary}\n\nMissing skills:\n{missing_skills_text}\n"
    )

    try:
        response_text = groq_call(prompt=base_prompt, model="llama-3.1-8b-instant", max_tokens=1400)
        return _parse_prep_response(response_text)
    except Exception as first_error:
        logger.warning("Interview prep parse failed on first attempt: %s", first_error)
        try:
            response_text = groq_call(prompt=strict_prompt, model="llama-3.1-8b-instant", max_tokens=900)
            return _parse_prep_response(response_text)
        except Exception as second_error:
            logger.warning("Interview prep failed twice, falling back to empty result: %s", second_error)
            return DEFAULT_PREP.copy()
