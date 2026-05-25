"""
Tailor Agent - Tailors resume content to match job requirements using Groq LLM.
"""
import json
import logging
import os
from groq import Groq
from typing import Dict, List, Any


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Groq client
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
client = Groq(api_key=GROQ_API_KEY)


def tailor_resume(resume_text: str, job: Dict[str, Any], skills: List[str]) -> Dict[str, Any]:
    """
    Tailor resume content to match a specific job posting.
    
    Args:
        resume_text: Full text from the candidate's resume
        job: Job dictionary with keys: title, company, location, description, job_url
        skills: List of extracted skills from resume
    
    Returns:
        Dictionary with keys: rewritten_summary (str), revised_skills (List[str]), 
        bullet_rewrites (List[str])
    """
    try:
        # Call Groq API to tailor resume
        prompt = f"""You are a professional resume writer. Tailor the following resume to match the job posting.

IMPORTANT: Do NOT fabricate experience or skills. Only rewrite existing content to emphasize relevant qualifications.

Job Title: {job.get('title', '')}
Company: {job.get('company', '')}
Job Description:
{job.get('description', '')}

Current Resume:
{resume_text}

Current Extracted Skills: {', '.join(skills)}

Provide a JSON response with:
1. rewritten_summary: A 2-3 sentence professional summary tailored to this job (emphasizing relevant background)
2. revised_skills: A list of relevant skills from the resume and provided skills, prioritized for this role (5-8 items)
3. bullet_rewrites: Top 3 experience bullets rewritten to match job requirements (only reword existing experience, don't add new ones)

Return ONLY valid JSON with no additional text. Example format:
{{"rewritten_summary": "...", "revised_skills": [...], "bullet_rewrites": [...]}}"""
        
        message = client.messages.create(
            model="llama3-8b-8192",
            max_tokens=1500,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )
        
        response_text = message.content[0].text.strip()
        
        # Parse JSON response
        tailored_data = json.loads(response_text)
        
        return {
            "rewritten_summary": str(tailored_data.get("rewritten_summary", "")),
            "revised_skills": tailored_data.get("revised_skills", skills) if isinstance(tailored_data.get("revised_skills"), list) else skills,
            "bullet_rewrites": tailored_data.get("bullet_rewrites", []) if isinstance(tailored_data.get("bullet_rewrites"), list) else []
        }
    
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON response from Groq: {e}")
        return {
            "rewritten_summary": "",
            "revised_skills": skills,
            "bullet_rewrites": []
        }
    except Exception as e:
        logger.error(f"Error tailoring resume: {e}")
        return {
            "rewritten_summary": "",
            "revised_skills": skills,
            "bullet_rewrites": []
        }
