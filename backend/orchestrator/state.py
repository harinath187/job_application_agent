"""
State definition for the LangGraph orchestrator.
"""
from typing import TypedDict, List


class AgentState(TypedDict):
    """
    Represents the state shared across all agents in the LangGraph pipeline.
    """
    session_id: str  # Session ID for tracking and database updates
    resume_path: str  # Path to uploaded PDF resume
    resume_text: str  # Extracted text from resume
    extracted_role: str  # Job role/title provided by the user
    extracted_location: str  # Location provided by the user
    user_experience: str | None  # Optional experience value provided by the user
    extracted_email: str | None  # Email extracted from resume text, if present
    alerts_enabled: bool  # Whether automatic email alerts were enabled for this session
    alert_message: str  # Human-readable alert registration status
    extracted_skills: List[str]  # Extracted skills from resume (5-8 items)
    extracted_experience_years: int  # Candidate's total years of professional experience
    extracted_experience: str | None  # Human-readable experience summary inferred from the resume
    jobs: List[dict]  # List of scraped jobs
    tailored_resumes: List[dict]  # List of tailored resume data and file paths
    cover_letter_paths: List[str]  # List of generated cover letter file paths
