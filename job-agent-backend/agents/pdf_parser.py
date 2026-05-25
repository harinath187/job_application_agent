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
        Dictionary with keys: role (str), location (str), skills (List[str])
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
            return {"role": "", "location": "", "skills": []}
        
        # Call Groq API to parse resume
        message = client.messages.create(
            model="llama3-8b-8192",
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": f"""Analyze this resume and extract ONLY the following information in valid JSON format:
- role: the primary job title/role from the resume
- location: the primary location/city from the resume
- skills: list of 5-8 key technical or professional skills mentioned

Resume text:
{resume_text}

Return ONLY valid JSON with no additional text. Example format:
{{"role": "Software Engineer", "location": "San Francisco", "skills": ["Python", "AWS", "Docker", "React", "PostgreSQL"]}}"""
                }
            ]
        )
        
        response_text = message.content[0].text.strip()
        
        # Parse JSON response
        extracted_data = json.loads(response_text)
        
        # Validate and set defaults
        return {
            "role": str(extracted_data.get("role", "")),
            "location": str(extracted_data.get("location", "")),
            "skills": extracted_data.get("skills", []) if isinstance(extracted_data.get("skills"), list) else []
        }
    
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON response from Groq: {e}")
        return {"role": "", "location": "", "skills": []}
    except Exception as e:
        logger.error(f"Error parsing resume: {e}")
        return {"role": "", "location": "", "skills": []}


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
