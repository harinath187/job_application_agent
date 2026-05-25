"""
LangGraph orchestrator that coordinates all agents in the job application pipeline.
"""
import logging
from langgraph.graph import StateGraph, END
from orchestrator.state import AgentState
from agents.pdf_parser import parse_resume, get_resume_text
from agents.scraper_agent import scrape_jobs
from agents.tailor_agent import tailor_resume
from agents.cover_letter_agent import generate_cover_letter
from utils.file_helpers import COVER_LETTERS_DIR


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def pdf_parser_node(state: AgentState) -> AgentState:
    """
    Node that parses the PDF resume and extracts role, location, and skills.
    
    Args:
        state: Current agent state
    
    Returns:
        Updated state with extracted resume data
    """
    logger.info(f"Processing PDF: {state['resume_path']}")
    
    # Extract text from PDF
    resume_text = get_resume_text(state["resume_path"])
    state["resume_text"] = resume_text
    
    # Parse resume to extract structured data
    parsed_data = parse_resume(state["resume_path"])
    state["extracted_role"] = parsed_data.get("role", "")
    state["extracted_location"] = parsed_data.get("location", "")
    state["extracted_skills"] = parsed_data.get("skills", [])
    
    logger.info(f"Extracted: Role={state['extracted_role']}, Location={state['extracted_location']}, Skills={state['extracted_skills']}")
    
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
    
    jobs = scrape_jobs(role=role, location=location)
    state["jobs"] = jobs
    
    logger.info(f"Found {len(jobs)} jobs")
    
    return state


def tailor_node(state: AgentState) -> AgentState:
    """
    Node that tailors resume for each scraped job.
    
    Args:
        state: Current agent state
    
    Returns:
        Updated state with tailored resumes
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
        
        tailored_resumes.append({
            "job": job,
            "tailored": tailored_data
        })
    
    state["tailored_resumes"] = tailored_resumes
    logger.info(f"Tailored {len(tailored_resumes)} resumes")
    
    return state


def cover_letter_node(state: AgentState) -> AgentState:
    """
    Node that generates cover letters for each job.
    
    Args:
        state: Current agent state
    
    Returns:
        Updated state with cover letter paths
    """
    cover_letter_paths = []
    summary = state.get("resume_text", "")[:500]  # Use resume excerpt as summary
    
    for tailored_item in state.get("tailored_resumes", []):
        job = tailored_item.get("job", {})
        logger.info(f"Generating cover letter for {job.get('title')} at {job.get('company')}")
        
        cover_letter_path = generate_cover_letter(
            job=job,
            summary=summary,
            output_dir=str(COVER_LETTERS_DIR)
        )
        
        if cover_letter_path:
            cover_letter_paths.append(cover_letter_path)
    
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
