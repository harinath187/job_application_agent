"""
Interview Prep Agent - Generates likely interview questions and talking points
for a specific job, tailored to the candidate's resume and skills.

This agent is triggered on-demand (per job, on user request) rather than
automatically for every scraped job, to avoid burning LLM calls on jobs the
user may never apply to. See backend/api/routes/interview_prep.py for the
on-demand API entry point.
"""
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional
from groq import Groq
from utils.groq_client import GroqCallFailedError, call_groq_with_retry

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")


def get_groq_client() -> Groq:
    """
    Lazily initialize the Groq client to avoid import-time failures.
    """
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not set. Interview prep generation via Groq is unavailable.")
    return Groq(api_key=GROQ_API_KEY)


# Static fallback question bank, keyed by a coarse seniority bucket. Used when
# the LLM is unavailable or returns a malformed response.
FALLBACK_QUESTION_BANK: Dict[str, Dict[str, List[str]]] = {
    "junior": {
        "technical_questions": [
            "Walk me through a project from your resume and the technical decisions you made.",
            "How do you approach debugging an issue you've never seen before?",
            "What is your process for learning a new tool or framework quickly?",
        ],
        "behavioral_questions": [
            "Tell me about a time you received critical feedback. How did you respond?",
            "Describe a situation where you had to ask for help on a task.",
            "Tell me about a time you missed a deadline. What happened?",
        ],
    },
    "mid": {
        "technical_questions": [
            "Describe the architecture of a system you've built or maintained.",
            "How do you decide when to refactor versus ship a quick fix?",
            "Walk me through how you'd debug a production incident under time pressure.",
        ],
        "behavioral_questions": [
            "Tell me about a time you disagreed with a technical decision. What did you do?",
            "Describe a project where requirements changed midway through. How did you adapt?",
            "Tell me about a time you mentored or supported a teammate.",
        ],
    },
    "senior": {
        "technical_questions": [
            "How do you approach making architectural trade-offs across a team?",
            "Describe a time you had to influence technical direction without direct authority.",
            "How do you evaluate build-vs-buy decisions for a new system?",
        ],
        "behavioral_questions": [
            "Tell me about a time you had to deliver difficult feedback to a peer or report.",
            "Describe a high-stakes decision you made with incomplete information.",
            "Tell me about a time you drove alignment across multiple stakeholders.",
        ],
    },
}


def _format_experience_entries(resume_sections: Optional[Dict[str, Any]]) -> str:
    entries = (resume_sections or {}).get("experience") or []
    if not entries:
        return "not provided"

    lines = []
    for entry in entries:
        company = entry.get("company", "")
        title = entry.get("title", "")
        dates = entry.get("dates", "")
        header = " - ".join(part for part in (title, company, dates) if part)
        lines.append(f"- {header}" if header else "-")
        for bullet in (entry.get("bullets") or [])[:4]:
            lines.append(f"  * {bullet}")
    return "\n".join(lines) if lines else "not provided"


def build_interview_prep_prompt(
    job_title: str,
    company: str,
    job_description: str,
    resume_summary: str,
    skills: List[str],
    tailored_resume_summary: Optional[str] = None,
    projects: Optional[List[str]] = None,
    certifications: Optional[List[str]] = None,
    resume_sections: Optional[Dict[str, Any]] = None,
    experience_summary: Optional[str] = None,
) -> str:
    """
    Build the LLM prompt used to generate structured interview prep content.
    Kept as its own function so prompt wording can be iterated on independently.
    """
    skills_str = ", ".join(skills) if skills else "not specified"
    resume_context = tailored_resume_summary or resume_summary or "not provided"
    projects_str = "\n".join(f"- {project}" for project in projects) if projects else "not provided"
    certifications_str = ", ".join(certifications) if certifications else "not provided"
    experience_entries_str = _format_experience_entries(resume_sections)
    experience_summary_str = experience_summary or "not provided"

    return f"""You are an expert technical interview coach preparing a candidate for a specific interview.

=== JOB ===
Title: {job_title}
Company: {company}
Description:
{job_description}

=== CANDIDATE RESUME ===
Summary: {resume_context}
Overall Experience: {experience_summary_str}
Extracted Skills: {skills_str}
Work Experience (from resume):
{experience_entries_str}
Projects (from resume):
{projects_str}
Certifications: {certifications_str}

=== TASK ===
Produce likely interview questions for this candidate for this specific job, plus short
preparation talking points (NOT full scripted answers — bullet points to jog the
candidate's memory, not a script to recite verbatim).

You MUST ground questions in the candidate's ACTUAL resume content above (specific
companies, job titles, projects, bullets, certifications) rather than generic prompts —
name the actual project, company, or technology from the resume wherever possible.

Return ONLY valid JSON matching this exact schema, with no markdown fences or commentary:
{{
  "technical_questions": ["...", "..."],
  "behavioral_questions": ["...", "..."],
  "resume_specific_questions": ["...", "..."],
  "suggested_talking_points": {{"category_name": ["bullet", "bullet"], ...}}
}}

Guidance:
- technical_questions: 4-6 questions tied directly to specific skills/tools/requirements in the job description, referencing the candidate's actual work experience or projects where they overlap with the job requirements (e.g. "You built X at Company Y — how would that translate to the Z requirement in this role?").
- behavioral_questions: 3-5 standard STAR-style questions appropriate for the apparent seniority of this role, ideally anchored to a real project or work experience entry from the resume when one plausibly fits.
- resume_specific_questions: 2-4 questions that would plausibly arise from gaps or standout points in the candidate's actual resume/skills/projects/experience relative to this job (e.g. a required skill missing from their list, an unexplained gap, or a specific project/certification worth probing deeper).
- suggested_talking_points: short bullet points per category (technical/behavioral/resume_specific), not full answers.
- If work experience, projects, or certifications are "not provided", rely on skills and the resume summary instead — do not fabricate resume details that were not given.
"""


def _infer_seniority_bucket(job_title: str, job_description: str) -> str:
    text = f"{job_title} {job_description}".lower()
    if any(term in text for term in ("senior", "staff", "principal", "lead")):
        return "senior"
    if any(term in text for term in ("junior", "entry", "intern", "graduate")):
        return "junior"
    return "mid"


def build_fallback_interview_prep(
    job: Dict[str, Any],
    skills: List[str],
    projects: Optional[List[str]] = None,
    resume_sections: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Build a generic, role-based interview prep result from the static question
    bank when the LLM is unavailable or returns a malformed response. Where actual
    resume details (a project, or the most recent job) are available, they are
    woven into the resume-specific questions instead of staying fully generic.
    """
    title = job.get("title", "this role")
    company = job.get("company", "the company")
    bucket = _infer_seniority_bucket(title, job.get("description", ""))
    bank = FALLBACK_QUESTION_BANK[bucket]

    resume_specific_questions = [
        f"Which of your listed skills ({', '.join(skills[:3]) if skills else 'your core skills'}) "
        f"are most relevant to the {title} role at {company}, and why?",
        "Is there a requirement in this job description you have limited hands-on experience with? Be ready to address it directly.",
    ]

    experience_entries = (resume_sections or {}).get("experience") or []
    if experience_entries:
        most_recent = experience_entries[0]
        recent_title = most_recent.get("title")
        recent_company = most_recent.get("company")
        if recent_title and recent_company:
            resume_specific_questions.append(
                f"Walk me through your work as {recent_title} at {recent_company} — which parts of that "
                f"experience translate most directly to the {title} role at {company}?"
            )

    if projects:
        resume_specific_questions.append(
            f"Tell me more about your \"{projects[0]}\" project — what was your specific contribution, "
            f"and how does it relate to what this role at {company} needs?"
        )

    return {
        "technical_questions": list(bank["technical_questions"]),
        "behavioral_questions": list(bank["behavioral_questions"]),
        "resume_specific_questions": resume_specific_questions,
        "suggested_talking_points": {
            "technical": ["Anchor answers in specific projects from your resume.", "Quantify impact where possible."],
            "behavioral": ["Use the STAR structure: Situation, Task, Action, Result.", "Pick recent, relevant examples."],
            "resume_specific": [f"Be upfront about gaps relative to {company}'s stated requirements.", "Bridge gaps by naming adjacent experience."],
        },
    }


def _strip_markdown_fences(raw_content: str) -> str:
    """Strip ```json ... ``` or ``` ... ``` fences some models wrap JSON output in."""
    text = raw_content.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
    return text.strip()


def _validate_llm_result(data: Any) -> bool:
    if not isinstance(data, dict):
        return False
    required_list_fields = ("technical_questions", "behavioral_questions", "resume_specific_questions")
    for field in required_list_fields:
        value = data.get(field)
        if not isinstance(value, list) or not value:
            return False
    if not isinstance(data.get("suggested_talking_points"), dict):
        return False
    return True


def generate_interview_prep(
    resume_text: str,
    extracted_skills: List[str],
    job: Dict[str, Any],
    tailored_resume_summary: Optional[str] = None,
    projects: Optional[List[str]] = None,
    certifications: Optional[List[str]] = None,
    resume_sections: Optional[Dict[str, Any]] = None,
    experience_summary: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Generate an interview prep result for a single job.

    Args:
        resume_text: Candidate's raw resume text (used as a fallback summary source)
        extracted_skills: Candidate's extracted skills
        job: Job dict with at least title, company, description, id
        tailored_resume_summary: Optional tailored resume summary for this job, if already generated
        projects: Candidate's extracted projects, if available
        certifications: Candidate's extracted certifications, if available
        resume_sections: Structured resume sections (contact_info/summary/skills/experience/education), if available
        experience_summary: Human-readable overall experience summary (e.g. "5+ years"), if available

    Returns:
        Dict with keys: job_id, generated_at, technical_questions, behavioral_questions,
        resume_specific_questions, suggested_talking_points, source ("llm" or "fallback")
    """
    job_id = job.get("id")
    resume_summary = (resume_sections or {}).get("summary") or (resume_text[:500] if resume_text else "")

    result_data: Optional[Dict[str, Any]] = None
    source = "fallback"

    try:
        client = get_groq_client()
        prompt = build_interview_prep_prompt(
            job_title=job.get("title", "Position"),
            company=job.get("company", "Company"),
            job_description=job.get("description", ""),
            resume_summary=resume_summary,
            skills=extracted_skills,
            tailored_resume_summary=tailored_resume_summary,
            projects=projects,
            certifications=certifications,
            resume_sections=resume_sections,
            experience_summary=experience_summary,
        )

        logger.info("Calling Groq for interview prep: job_id=%s", job_id)
        message = call_groq_with_retry(
            client,
            model="llama-3.1-8b-instant",
            max_tokens=1800,
            temperature=0.4,
            messages=[{"role": "user", "content": prompt}],
        )
        raw_content = message.choices[0].message.content.strip()
        cleaned_content = _strip_markdown_fences(raw_content)

        try:
            parsed = json.loads(cleaned_content)
        except json.JSONDecodeError as parse_error:
            logger.warning(
                "Interview prep LLM response was not valid JSON for job_id=%s (%s); raw content: %.500s",
                job_id, parse_error, raw_content,
            )
            parsed = None

        if parsed is not None and _validate_llm_result(parsed):
            result_data = parsed
            source = "llm"
            logger.info("Interview prep LLM call succeeded: job_id=%s", job_id)
        elif parsed is not None:
            logger.warning("Interview prep LLM output malformed for job_id=%s; using fallback", job_id)
    except GroqCallFailedError as llm_error:
        logger.error("Interview prep Groq call failed after retries for job_id=%s: %s", job_id, llm_error)
    except RuntimeError:
        logger.warning("GROQ_API_KEY not configured; using fallback interview prep template for job_id=%s", job_id)
    except (TypeError, KeyError, IndexError, AttributeError) as parse_error:
        logger.warning("Interview prep LLM response could not be parsed for job_id=%s: %s; using fallback", job_id, parse_error)
    except Exception as llm_error:
        logger.warning("Interview prep generation failed for job_id=%s: %s; using fallback", job_id, llm_error)

    if result_data is None:
        result_data = build_fallback_interview_prep(job, extracted_skills, projects=projects, resume_sections=resume_sections)
        source = "fallback"

    return {
        "job_id": job_id,
        "generated_at": datetime.utcnow().isoformat(),
        "technical_questions": result_data["technical_questions"],
        "behavioral_questions": result_data["behavioral_questions"],
        "resume_specific_questions": result_data["resume_specific_questions"],
        "suggested_talking_points": result_data["suggested_talking_points"],
        "source": source,
    }
