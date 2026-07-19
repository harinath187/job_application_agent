"""
Role inference helpers for resume-derived skills and projects.
"""
import json
import logging
import os
from collections import Counter
from typing import Any

try:
    from groq import Groq
except ModuleNotFoundError:  # pragma: no cover - allows heuristic-only operation without the SDK installed
    Groq = None

from utils.groq_client import GroqCallFailedError, call_groq_with_retry


logger = logging.getLogger(__name__)
GROQ_API_KEY = os.getenv("GROQ_API_KEY")


def get_groq_client() -> Groq:
    if Groq is None:
        raise RuntimeError("groq package is not installed. Role inference via Groq is unavailable.")
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not set. Role inference via Groq is unavailable.")
    return Groq(api_key=GROQ_API_KEY)


ROLE_KEYWORD_CLUSTERS: dict[str, set[str]] = {
    "frontend engineer": {"react", "typescript", "javascript", "html", "css", "redux", "next.js", "tailwind", "ui", "frontend"},
    "backend engineer": {"python", "java", "node.js", "express", "django", "flask", "fastapi", "api", "microservices", "backend"},
    "full stack engineer": {"react", "node.js", "typescript", "javascript", "api", "sql", "frontend", "backend", "full stack"},
    "data scientist": {"pandas", "numpy", "scikit-learn", "tensorflow", "pytorch", "machine learning", "data science", "statistics", "ml"},
    "data engineer": {"sql", "spark", "etl", "airflow", "python", "databricks", "bigquery", "data pipeline", "warehouse"},
    "devops engineer": {"docker", "kubernetes", "terraform", "jenkins", "ci/cd", "linux", "aws", "azure", "gcp", "devops"},
    "mobile developer": {"android", "ios", "swift", "kotlin", "flutter", "react native", "mobile", "xcode", "app"},
    "qa engineer": {"testing", "qa", "selenium", "cypress", "playwright", "pytest", "test automation", "manual testing"},
    "product manager": {"roadmap", "stakeholder", "product", "agile", "scrum", "user research", "requirements", "prioritization"},
    "cloud engineer": {"aws", "azure", "gcp", "cloudformation", "terraform", "ec2", "lambda", "cloud", "infrastructure"},
}


def _normalize_tokens(items: list[str]) -> set[str]:
    normalized = set()
    for item in items:
        token = (item or "").strip().lower()
        if token:
            normalized.add(token)
    return normalized


def infer_roles_heuristic(skills: list[str]) -> list[str]:
    normalized_skills = _normalize_tokens(skills)
    matched_roles: list[str] = []
    for role, keywords in ROLE_KEYWORD_CLUSTERS.items():
        overlaps = sum(1 for keyword in keywords if any(keyword in skill for skill in normalized_skills))
        if overlaps >= 2:
            matched_roles.append(role.title())
    return matched_roles[:3]


def _build_role_prompt(skills: list[str], projects: list[str]) -> str:
    return f"""Infer up to 3 likely role titles from this resume profile.
Return only valid JSON in the form: {{"roles": ["Role 1", "Role 2"]}}.
Use concise common job titles only. Prefer roles strongly supported by the evidence.

Skills: {json.dumps(skills)}
Projects: {json.dumps(projects)}
"""


def _parse_roles_response(response_text: str) -> list[str]:
    payload = json.loads(response_text)
    if not isinstance(payload, dict):
        return []
    roles = payload.get("roles", [])
    if not isinstance(roles, list):
        return []
    cleaned = [str(role).strip() for role in roles if str(role).strip()]
    deduped = list(dict.fromkeys(cleaned))
    return deduped[:3]


def infer_roles_llm(skills: list[str], projects: list[str]) -> list[str]:
    client = get_groq_client()
    message = call_groq_with_retry(
        client,
        model="llama-3.1-8b-instant",
        max_tokens=256,
        messages=[{"role": "user", "content": _build_role_prompt(skills, projects)}],
    )
    response_text = message.choices[0].message.content.strip()
    return _parse_roles_response(response_text)


def infer_roles(skills: list[str], projects: list[str]) -> list[str]:
    heuristic_roles = infer_roles_heuristic(skills)
    if len(heuristic_roles) >= 2:
        logger.info("[role_inferrer] heuristic roles=%s", heuristic_roles)
        return heuristic_roles

    try:
        llm_roles = infer_roles_llm(skills, projects)
        if llm_roles:
            logger.info("[role_inferrer] llm roles=%s", llm_roles)
            return llm_roles[:3]
        logger.warning("[role_inferrer] LLM returned no roles; using heuristic result=%s", heuristic_roles)
    except (GroqCallFailedError, RuntimeError, ValueError, json.JSONDecodeError, AttributeError, TypeError) as exc:
        logger.warning("[role_inferrer] LLM inference failed; using heuristic result=%s reason=%s", heuristic_roles, exc)
    return heuristic_roles
