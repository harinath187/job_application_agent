"""
Role inference helpers for resume profiles.
"""
import json
import logging
import os
from typing import Any

try:
    from groq import Groq
except Exception:  # pragma: no cover - keep heuristic inference available without SDK
    Groq = None

from utils.groq_client import call_groq_with_retry


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

ROLE_CLUSTERS: dict[str, set[str]] = {
    "Frontend Developer": {"react", "javascript", "typescript", "html", "css", "frontend", "ui", "ux", "next.js"},
    "Backend Developer": {"python", "java", "node.js", "api", "backend", "microservices", "fastapi", "django", "flask", "spring"},
    "Full Stack Developer": {"react", "node.js", "javascript", "typescript", "api", "frontend", "backend", "full stack"},
    "Data Scientist": {"python", "pandas", "numpy", "scikit-learn", "machine learning", "ml", "statistics", "data science", "tensorflow"},
    "Data Engineer": {"python", "sql", "spark", "etl", "airflow", "dbt", "warehouse", "big data", "pyspark"},
    "DevOps Engineer": {"docker", "kubernetes", "terraform", "ci/cd", "linux", "aws", "azure", "gcp", "jenkins"},
    "Mobile Developer": {"android", "ios", "swift", "kotlin", "react native", "flutter", "mobile", "xcode", "gradle"},
    "QA Engineer": {"testing", "qa", "selenium", "cypress", "playwright", "automation", "junit", "pytest", "testng"},
    "Cloud Engineer": {"aws", "azure", "gcp", "cloud", "terraform", "ec2", "lambda", "iam", "devops"},
    "Security Engineer": {"security", "iam", "oauth", "sso", "penetration testing", "vulnerability", "siem", "threat", "compliance"},
}


def get_groq_client() -> Groq:
    if Groq is None:
        raise RuntimeError("Groq SDK is not installed. Role inference via Groq is unavailable.")
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not set. Role inference via Groq is unavailable.")
    return Groq(api_key=GROQ_API_KEY)


def infer_roles_heuristic(skills: list[str]) -> list[str]:
    normalized_skills = {str(skill).strip().lower() for skill in skills if str(skill).strip()}
    inferred: list[str] = []
    for role, keywords in ROLE_CLUSTERS.items():
        overlaps = [kw for kw in keywords if kw in normalized_skills or any(kw in skill for skill in normalized_skills)]
        if len(overlaps) >= 2:
            inferred.append(role)
    logger.info("[role_inferrer] heuristic roles=%s for skills=%s", inferred, skills)
    return inferred[:3]


def infer_roles_llm(skills: list[str], projects: list[str]) -> list[str]:
    client = get_groq_client()
    prompt = f"""Infer up to 3 likely job role titles from the candidate profile.
Return ONLY valid JSON in this format:
{{"roles":["Role 1","Role 2"]}}

Skills: {json.dumps(skills)}
Projects: {json.dumps(projects)}
"""
    message = call_groq_with_retry(
        client,
        model="llama-3.1-8b-instant",
        max_tokens=128,
        messages=[{"role": "user", "content": prompt}],
    )
    response_text = message.choices[0].message.content.strip()
    data = json.loads(response_text)
    roles = data.get("roles", [])
    if not isinstance(roles, list):
        return []
    normalized = []
    for role in roles:
        text = str(role).strip()
        if text and text not in normalized:
            normalized.append(text)
    logger.info("[role_inferrer] llm roles=%s", normalized[:3])
    return normalized[:3]


def infer_roles(skills: list[str], projects: list[str]) -> list[str]:
    heuristic_roles = infer_roles_heuristic(skills)
    if len(heuristic_roles) >= 2 or not GROQ_API_KEY:
        return heuristic_roles
    try:
        llm_roles = infer_roles_llm(skills, projects)
        combined = heuristic_roles[:]
        for role in llm_roles:
            if role not in combined:
                combined.append(role)
        logger.info("[role_inferrer] combined roles=%s", combined[:3])
        return combined[:3]
    except Exception as exc:
        logger.warning("[role_inferrer] LLM inference failed, falling back to heuristic roles: %s", exc)
        return heuristic_roles
