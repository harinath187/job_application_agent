"""
State definition for the LangGraph orchestrator.
"""
from typing import TypedDict, List


class AgentState(TypedDict):
    """
    Represents the state shared across all agents in the LangGraph pipeline.
    """
    resume_path: str  # Path to uploaded PDF resume
    resume_text: str  # Extracted text from resume
    extracted_role: str  # Extracted job role/title from resume
    extracted_location: str  # Extracted location from resume
    extracted_skills: List[str]  # Extracted skills from resume (5-8 items)
    jobs: List[dict]  # List of scraped jobs
    tailored_resumes: List[dict]  # List of tailored resume/job pairs
    cover_letter_paths: List[str]  # List of generated cover letter file paths
