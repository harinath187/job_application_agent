"""
PDF Parser Agent - Extracts resume data using Groq LLM.
"""
import json
import logging
import os
import fitz  # PyMuPDF
from groq import Groq
from typing import Dict, Any


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Groq client
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY)


def parse_resume(pdf_path: str) -> Dict[str, Any]:
    """
    Extract structured data from a PDF resume using Groq LLM.
    
    Args:
        pdf_path: Path to the PDF resume file
    
    Returns:
        Dictionary with keys: skills (List[str])
    """
    try:
        # Extract text from PDF
        doc = fitz.open(pdf_path)
        resume_text = ""
        for page_num in range(len(doc)):
            page = doc[page_num]
            resume_text += page.get_text()
        doc.close()
        
        if not resume_text.strip():
            logger.warning(f"No text extracted from {pdf_path}")
            return {"skills": []}
        
        # Call Groq API to parse resume
        message = client.chat.completions.create(  # FIXED: Use Groq chat completions API.
            model="llama-3.1-8b-instant",  # FIXED: Replace decommissioned llama3-8b-8192 model.
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": f"""Analyze this resume and extract ONLY the following information in valid JSON format:
- skills: list of 5-8 key technical or professional skills mentioned
- experience_years: total years of professional work experience (integer). If they are a student with no work experience, return 0.

Resume text:
{resume_text}

Return ONLY valid JSON with no additional text. Example format:
{{"skills": ["Python", "AWS", "Docker", "React", "PostgreSQL"], "experience_years": 5}}"""
                }
            ]
        )
        
        response_text = message.choices[0].message.content.strip()  # FIXED: Read chat completion response content.
        
        # Parse JSON response
        extracted_data = json.loads(response_text)
        
        # Validate and set defaults
        experience_years = extracted_data.get("experience_years", 0)
        try:
            experience_years = int(experience_years) if experience_years else 0
        except (ValueError, TypeError):
            experience_years = 0
        
        return {
            "skills": extracted_data.get("skills", []) if isinstance(extracted_data.get("skills"), list) else [],
            "experience_years": experience_years
        }
    
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON response from Groq: {e}")
        return {"skills": [], "experience_years": 0}
    except Exception as e:
        logger.error(f"Error parsing resume: {e}")
        return {"skills": [], "experience_years": 0}


def get_resume_text(pdf_path: str) -> str:
    """
    Extract raw text from PDF resume.
    
    Args:
        pdf_path: Path to the PDF file
    
    Returns:
        Extracted text as string
    """
    try:
        doc = fitz.open(pdf_path)
        text = ""
        for page_num in range(len(doc)):
            page = doc[page_num]
            text += page.get_text()
        doc.close()
        return text
    except Exception as e:
        logger.error(f"Error extracting text from PDF: {e}")
        return ""
