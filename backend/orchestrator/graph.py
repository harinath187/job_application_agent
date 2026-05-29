"""
LangGraph orchestrator that coordinates all agents in the job application pipeline.
"""
import logging
import time  # FIXED: Add delay support for Groq rate limit protection.
from langgraph.graph import StateGraph, END
from orchestrator.state import AgentState
from agents.pdf_parser import parse_resume, get_resume_text
from agents.scraper_agent import scrape_jobs
from agents.tailor_agent import tailor_resume, save_tailored_resume
from agents.cover_letter_agent import generate_cover_letter
from utils.file_helpers import COVER_LETTERS_DIR, RESUMES_DIR


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def pdf_parser_node(state: AgentState) -> AgentState:
    """
    Node that parses the PDF resume and extracts skills.
    
    Args:
        state: Current agent state
    
    Returns:
        Updated state with extracted resume skills
    """
    logger.info(f"Processing PDF: {state['resume_path']}")
    
    # Extract text from PDF
    resume_text = get_resume_text(state["resume_path"])
    state["resume_text"] = resume_text
    
    # Parse resume to extract structured data
    parsed_data = parse_resume(state["resume_path"])
    state["extracted_skills"] = parsed_data.get("skills", [])
    state["extracted_experience_years"] = parsed_data.get("experience_years", 0)
    
    logger.info(f"Extracted skills={state['extracted_skills']} experience_years={state['extracted_experience_years']} role={state.get('extracted_role', '')} location={state.get('extracted_location', '')}")
    
    return state


def scraper_node(state: AgentState) -> AgentState:
    """
    Node that scrapes job listings based on extracted role and location.
    
    Args:
        state: Current agent state
    
    Returns:
        Updated state with scraped jobs
    """
    role = state.get("extracted_role", "Software Engineer")
    location = state.get("extracted_location", "USA")
    
    logger.info(f"Scraping jobs for: {role} in {location}")
    
    experience_years = state.get("extracted_experience_years", 0)
    jobs = scrape_jobs(role=role, location=location, candidate_experience_years=experience_years)
    state["jobs"] = jobs
    
    logger.info(f"Found {len(jobs)} jobs")
    
    return state


def tailor_node(state: AgentState) -> AgentState:
    """
    Node that tailors resume for each scraped job and saves tailored versions.
    
    Args:
        state: Current agent state
    
    Returns:
        Updated state with tailored resumes and their file paths
    """
    tailored_resumes = []
    resume_text = state.get("resume_text", "")
    skills = state.get("extracted_skills", [])
    
    for job in state.get("jobs", []):
        logger.info(f"Tailoring resume for {job.get('title')} at {job.get('company')}")
        
        tailored_data = tailor_resume(
            resume_text=resume_text,
            job=job,
            skills=skills
        )
        
        # Save tailored resume to disk
        tailored_resume_path = save_tailored_resume(
            resume_text=resume_text,
            tailored_data=tailored_data,
            job=job,
            output_dir=str(RESUMES_DIR)
        )
        
        tailored_resumes.append({
            "job": job,
            "tailored": tailored_data,
            "resume_path": tailored_resume_path
        })
    
    state["tailored_resumes"] = tailored_resumes
    logger.info(f"Tailored {len(tailored_resumes)} resumes")
    
    return state


def cover_letter_node(state: AgentState) -> AgentState:
    """
    Node that generates tailored cover letters for each job.
    Uses the candidate's skills and tailored resume summary for specificity.
    
    Args:
        state: Current agent state
    
    Returns:
        Updated state with cover letter paths
    """
    cover_letter_paths = []
    skills = state.get("extracted_skills", [])  # Get extracted skills from state
    
    # Use the resume text as fallback summary if tailored summary not available
    resume_summary = state.get("resume_text", "")[:500]
    
    for tailored_item in state.get("tailored_resumes", []):
        job = tailored_item.get("job", {})
        tailored_data = tailored_item.get("tailored", {})
        
        logger.info(f"Generating cover letter for {job.get('title')} at {job.get('company')}")
        
        # Use the tailored resume summary if available (more specific than generic resume text)
        tailored_resume_summary = tailored_data.get("summary", "") or resume_summary
        
        cover_letter_path = generate_cover_letter(
            job=job,
            summary=resume_summary,
            skills=skills,
            output_dir=str(COVER_LETTERS_DIR),
            tailored_resume_summary=tailored_resume_summary  # Pass tailored summary for better specificity
        )
        
        if cover_letter_path:
            cover_letter_paths.append(cover_letter_path)
        
        time.sleep(2)  # FIXED: Pause after each tailor + cover letter pair to reduce Groq rate limit pressure.
    
    state["cover_letter_paths"] = cover_letter_paths
    logger.info(f"Generated {len(cover_letter_paths)} cover letters")
    
    return state


def build_graph():
    """
    Build and compile the LangGraph orchestration graph.
    
    Returns:
        Compiled LangGraph StateGraph
    """
    workflow = StateGraph(AgentState)
    
    # Register nodes
    workflow.add_node("pdf_parser", pdf_parser_node)
    workflow.add_node("scraper", scraper_node)
    workflow.add_node("tailor", tailor_node)
    workflow.add_node("cover_letter", cover_letter_node)
    
    # Define edges (linear flow)
    workflow.set_entry_point("pdf_parser")
    workflow.add_edge("pdf_parser", "scraper")
    workflow.add_edge("scraper", "tailor")
    workflow.add_edge("tailor", "cover_letter")
    workflow.add_edge("cover_letter", END)
    
    # Compile and return
    graph = workflow.compile()
    return graph
