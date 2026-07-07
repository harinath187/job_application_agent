"""Lightweight semantic validation for user-provided job inputs."""

from __future__ import annotations

from typing import Iterable


COMMON_LOCATIONS = {
    "chennai",
    "bangalore",
    "hyderabad",
    "mumbai",
    "delhi",
    "pune",
    "kolkata",
    "noida",
    "gurugram",
    "remote",
}

JOB_TITLE_KEYWORDS = {
    "engineer",
    "developer",
    "analyst",
    "scientist",
    "manager",
    "architect",
    "consultant",
    "tester",
    "designer",
    "administrator",
}


def _normalize(value: str) -> str:
    return " ".join(value.strip().lower().split())


def _contains_any(text: str, keywords: Iterable[str]) -> bool:
    return any(keyword in text for keyword in keywords)


def validate_inputs(role: str, location: str) -> tuple[bool, str]:
    """Validate that role looks like a job title and location looks like a place."""
    normalized_role = _normalize(role or "")
    normalized_location = _normalize(location or "") 

    if not normalized_role or not normalized_location:
        return False, "Job Title and Location are required."

    role_is_location = normalized_role in COMMON_LOCATIONS
    location_is_location = normalized_location in COMMON_LOCATIONS
    role_is_job_title = _contains_any(normalized_role, JOB_TITLE_KEYWORDS)
    location_is_job_title = _contains_any(normalized_location, JOB_TITLE_KEYWORDS)

    if role_is_location and location_is_job_title:
        return (
            False,
            "It looks like Job Title and Location may be swapped. Suggested values:\n"
            f"Job Title: {location.strip()}\n"
            f"Location: {role.strip()}",
        )

    if role_is_location and not location_is_location:
        return False, f"It looks like Job Title should be a role, but got a location: {role.strip()}."

    if location_is_job_title and not role_is_job_title:
        return (
            False,
            "It looks like Job Title and Location may be swapped. Suggested values:\n"
            f"Job Title: {location.strip()}\n"
            f"Location: {role.strip()}",
        )

    if role_is_job_title and location_is_location:
        return True, ""

    return True, ""
