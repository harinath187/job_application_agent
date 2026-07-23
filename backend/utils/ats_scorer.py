"""
ATS Score Utilities.

This module implements two independent scoring features:

  * Part 1 - compute_ats_structure_score(): FREE, INSTANT, rule-based. Runs on
    every resume upload (wired into backend/orchestrator/graph.py's
    pdf_parser_node) with no LLM call and no extra round trip. It inspects the
    resume PDF/text itself (not tied to any job posting) and flags structural
    issues that commonly trip up ATS parsers: scanned/image-only PDFs,
    multi-column layouts, missing standard section headers, missing contact
    info, resume length, and heavy use of special characters/glyphs.

  * Part 2 - compute_ats_match_score(): ON-DEMAND, cached per job (mirrors the
    interview-prep agent pattern), LLM-assisted with a graceful keyword-only
    fallback. It reuses the existing skill-overlap scoring from
    agents.skill_extractor (compute_skill_overlap) rather than reimplementing
    keyword matching, and only calls Groq for a short qualitative fit
    assessment when GROQ_API_KEY is configured. Any LLM failure (missing key,
    rate limit, malformed JSON) falls back to the keyword-only score and never
    raises.
"""
import json
import logging
import os
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from pypdf import PdfReader

from agents.skill_extractor import compute_skill_overlap
from utils.groq_client import GroqCallFailedError, call_groq_with_retry

try:
    import fitz  # PyMuPDF - already a project dependency (see requirements.txt); used
    # here for block-layout analysis (multi-column detection) that pypdf can't do.
except ImportError:  # pragma: no cover - degrade gracefully if PyMuPDF isn't installed
    fitz = None

try:
    from groq import Groq
except ModuleNotFoundError:  # pragma: no cover - allows keyword-only operation without the SDK
    Groq = None


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Standard resume section headers an ATS-friendly resume is expected to contain
# at least a few of. Kept as a small local list rather than importing the
# private SECTION_ALIASES helpers from pdf_parser.py.
EXPECTED_SECTION_KEYWORDS = (
    "experience", "work experience", "professional experience", "employment history",
    "education", "academic background",
    "skills", "technical skills",
    "summary", "objective", "professional summary",
    "projects", "project experience",
    "certifications", "licenses",
)

PHONE_PATTERN = re.compile(r"(\+?\d{1,3}[\s.-]?)?(\(?\d{3}\)?[\s.-]?)?\d{3}[\s.-]?\d{4}\b")
EMAIL_PATTERN = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")

MIN_WORD_COUNT = 150
MAX_WORD_COUNT = 1200
# Characters commonly used as bullet glyphs; these are fine in moderation but a
# resume saturated with decorative glyphs/emoji tends to confuse ATS parsers.
SPECIAL_GLYPH_PATTERN = re.compile(
    "[•●▪–—→★✔✖"
    "\U0001F300-\U0001FAFF\U00002600-\U000027BF]"
)
SPECIAL_GLYPH_DENSITY_THRESHOLD = 0.02  # glyphs per character


@dataclass
class ATSStructureResult:
    """Result of the free, instant, rule-based structural ATS check (Part 1)."""

    score: int
    passed_checks: List[str] = field(default_factory=list)
    failed_checks: List[Dict[str, str]] = field(default_factory=list)
    is_likely_scanned: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ATSMatchResult:
    """Result of the on-demand, cached keyword+LLM job-fit check (Part 2)."""

    matched_keywords: List[str] = field(default_factory=list)
    missing_keywords: List[str] = field(default_factory=list)
    match_score: int = 0
    notes: Optional[str] = None
    source: str = "keyword"  # "keyword" or "llm"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _add_check(result: ATSStructureResult, passed: bool, check_name: str, message: str, severity: str = "medium") -> None:
    if passed:
        result.passed_checks.append(check_name)
    else:
        result.failed_checks.append({"check_name": check_name, "message": message, "severity": severity})


def _get_pdf_page_count(pdf_path: str) -> int:
    try:
        reader = PdfReader(pdf_path)
        return len(reader.pages)
    except Exception as exc:
        logger.warning("[ats_scorer] Could not read PDF page count for %s: %s", pdf_path, exc)
        return 0


def _detect_multi_column_layout(pdf_path: str) -> Optional[bool]:
    """
    Best-effort multi-column layout detection using PyMuPDF text block x-coordinates.

    Returns None (unknown) when PyMuPDF isn't installed or the PDF can't be
    analyzed, so callers can skip this check gracefully rather than treating
    "unknown" as "single column".
    """
    if fitz is None:
        return None
    try:
        doc = fitz.open(pdf_path)
        multi_column_pages = 0
        analyzed_pages = 0
        for page in doc:
            blocks = page.get_text("blocks") or []
            block_starts = [block[0] for block in blocks if block and (block[2] - block[0]) > 5]
            if len(block_starts) < 4:
                continue
            analyzed_pages += 1
            page_width = page.rect.width or 1
            # Bucket block left-edges into left-half vs right-half of the page;
            # a real two-column layout puts a meaningful share of blocks in
            # both halves, whereas a single-column resume clusters near the left.
            left_half = sum(1 for x in block_starts if x < page_width * 0.15)
            right_half = sum(1 for x in block_starts if x > page_width * 0.4)
            if left_half >= 3 and right_half >= 3:
                multi_column_pages += 1
        doc.close()
        if analyzed_pages == 0:
            return None
        return multi_column_pages > 0
    except Exception as exc:
        logger.warning("[ats_scorer] PyMuPDF layout analysis failed for %s: %s", pdf_path, exc)
        return None


def compute_ats_structure_score(pdf_path: str, resume_text: str) -> ATSStructureResult:
    """
    Run free, instant, rule-based structural ATS checks against a resume.

    Args:
        pdf_path: Path to the uploaded PDF resume
        resume_text: Already-extracted resume text (from extract_text_from_pdf)

    Returns:
        ATSStructureResult with a 0-100 score, passed/failed checks, and whether
        the PDF looks like a scanned image (which dominates the score downward).
    """
    result = ATSStructureResult(score=100)
    text = resume_text or ""
    normalized_text = text.lower()
    word_count = len(text.split())

    # --- Parseability / scanned-document check ---
    page_count = _get_pdf_page_count(pdf_path)
    text_density = word_count / max(1, page_count)
    is_likely_scanned = bool(page_count > 0 and text_density < 20)
    result.is_likely_scanned = is_likely_scanned
    _add_check(
        result,
        passed=not is_likely_scanned,
        check_name="parseability",
        message="This resume appears to be a scanned image or otherwise non-machine-readable PDF; ATS systems cannot extract text from it.",
        severity="high",
    )

    # --- Multi-column layout check ---
    multi_column = _detect_multi_column_layout(pdf_path)
    if multi_column is None:
        pass  # Skip gracefully: PyMuPDF unavailable or inconclusive.
    else:
        _add_check(
            result,
            passed=not multi_column,
            check_name="single_column_layout",
            message="Multi-column layout detected; many ATS parsers read multi-column resumes out of order.",
            severity="medium",
        )

    # --- Standard section headers present ---
    found_sections = [keyword for keyword in EXPECTED_SECTION_KEYWORDS if keyword in normalized_text]
    has_enough_sections = len(set(_canonical_section(keyword) for keyword in found_sections)) >= 3
    _add_check(
        result,
        passed=has_enough_sections,
        check_name="standard_section_headers",
        message="Resume is missing standard section headers (e.g. Experience, Education, Skills, Summary); ATS systems rely on these to categorize content.",
        severity="medium",
    )

    # --- Contact info present ---
    has_email = bool(EMAIL_PATTERN.search(text))
    has_phone = bool(PHONE_PATTERN.search(text))
    _add_check(
        result,
        passed=has_email,
        check_name="contact_email",
        message="No email address was found in the resume text.",
        severity="high",
    )
    _add_check(
        result,
        passed=has_phone,
        check_name="contact_phone",
        message="No phone number was found in the resume text.",
        severity="low",
    )

    # --- Length check ---
    too_short = word_count < MIN_WORD_COUNT
    too_long = word_count > MAX_WORD_COUNT
    _add_check(
        result,
        passed=not too_short and not too_long,
        check_name="resume_length",
        message=(
            f"Resume text is very short ({word_count} words); ATS systems may treat it as incomplete."
            if too_short else
            f"Resume text is very long ({word_count} words); consider trimming to keep it scannable."
        ) if (too_short or too_long) else "",
        severity="low",
    )

    # --- Special character / glyph heaviness ---
    glyph_matches = len(SPECIAL_GLYPH_PATTERN.findall(text))
    glyph_density = glyph_matches / max(1, len(text))
    glyph_heavy = glyph_density > SPECIAL_GLYPH_DENSITY_THRESHOLD
    _add_check(
        result,
        passed=not glyph_heavy,
        check_name="special_characters",
        message="Resume text is heavy with special characters, emoji, or decorative bullet glyphs; some ATS parsers mis-handle these.",
        severity="low",
    )

    # --- Score computation ---
    severity_penalty = {"high": 30, "medium": 15, "low": 5}
    score = 100
    for failed in result.failed_checks:
        score -= severity_penalty.get(failed.get("severity", "medium"), 15)
    score = max(0, min(100, score))

    if is_likely_scanned:
        # A scanned/non-machine-readable resume is effectively invisible to an
        # ATS regardless of what else looks fine, so this dominates the score.
        score = min(score, 20)

    result.score = score
    return result


def _canonical_section(keyword: str) -> str:
    """Collapse header keyword variants (e.g. 'work experience') to one canonical bucket."""
    if "experience" in keyword and "professional" not in keyword and "employment" not in keyword:
        return "experience"
    if "experience" in keyword or "employment" in keyword:
        return "experience"
    if "education" in keyword or "academic" in keyword:
        return "education"
    if "skill" in keyword:
        return "skills"
    if "summary" in keyword or "objective" in keyword:
        return "summary"
    if "project" in keyword:
        return "projects"
    if "certification" in keyword or "license" in keyword:
        return "certifications"
    return keyword


def get_groq_client() -> "Groq":
    """Lazily initialize the Groq client, matching the pattern used elsewhere in the codebase."""
    if Groq is None:
        raise RuntimeError("groq package is not installed. ATS match LLM assessment is unavailable.")
    if not GROQ_API_KEY:
        raise RuntimeError("GROQ_API_KEY is not set. ATS match LLM assessment is unavailable.")
    return Groq(api_key=GROQ_API_KEY)


def _build_ats_match_prompt(resume_text: str, job_description: str, matched_keywords: List[str], missing_keywords: List[str]) -> str:
    return f"""You are an ATS (Applicant Tracking System) fit-assessment assistant.

A keyword-overlap analysis has already been run between the candidate's resume and the job
description below. Your task is to sanity-check that score and produce a short qualitative note.

Matched keywords: {", ".join(matched_keywords) if matched_keywords else "none"}
Missing keywords: {", ".join(missing_keywords) if missing_keywords else "none"}

Job description:
{job_description[:3000]}

Candidate resume (excerpt):
{resume_text[:2000]}

Return ONLY valid JSON with no markdown fences or commentary, in this exact schema:
{{"match_score": <integer 0-100>, "notes": "<one or two sentence explanation>"}}
"""


def _strip_markdown_fences(raw_content: str) -> str:
    text = (raw_content or "").strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1] if "\n" in text else text[3:]
        if text.rstrip().endswith("```"):
            text = text.rstrip()[:-3]
    return text.strip()


def compute_ats_match_score(resume_text: str, extracted_skills: List[str], job_description: str) -> ATSMatchResult:
    """
    Compute how well a resume matches a specific job description.

    Reuses agents.skill_extractor.compute_skill_overlap for the keyword-overlap
    baseline (never reimplements keyword matching), then optionally refines
    the score/notes with a short Groq call when GROQ_API_KEY is configured.
    Any LLM failure (missing key, rate limit, malformed JSON) falls back to
    the keyword-only score and never raises.
    """
    overlap = compute_skill_overlap(extracted_skills or [], _extract_job_keywords(job_description))
    keyword_score = round(overlap.overlap_score * 100)

    result = ATSMatchResult(
        matched_keywords=overlap.matched_skills,
        missing_keywords=overlap.missing_skills,
        match_score=keyword_score,
        notes=None,
        source="keyword",
    )

    if not GROQ_API_KEY:
        logger.info("[ats_scorer] GROQ_API_KEY not configured; using keyword-only ATS match score")
        return result

    try:
        client = get_groq_client()
        prompt = _build_ats_match_prompt(resume_text or "", job_description or "", overlap.matched_skills, overlap.missing_skills)
        message = call_groq_with_retry(
            client,
            model="llama-3.1-8b-instant",
            max_tokens=300,
            temperature=0.2,
            messages=[{"role": "user", "content": prompt}],
        )
        raw_content = message.choices[0].message.content.strip()
        cleaned_content = _strip_markdown_fences(raw_content)
        parsed = json.loads(cleaned_content)

        if not isinstance(parsed, dict):
            raise ValueError("LLM response was not a JSON object")

        llm_score = parsed.get("match_score")
        llm_notes = parsed.get("notes")
        if not isinstance(llm_score, (int, float)):
            raise ValueError("LLM response missing a numeric match_score")

        result.match_score = max(0, min(100, int(llm_score)))
        result.notes = str(llm_notes).strip() if llm_notes else None
        result.source = "llm"
        logger.info("[ats_scorer] ATS match LLM assessment succeeded")
    except GroqCallFailedError as exc:
        logger.warning("[ats_scorer] ATS match Groq call failed after retries; using keyword-only score: %s", exc)
    except RuntimeError as exc:
        logger.info("[ats_scorer] %s; using keyword-only ATS match score", exc)
    except (json.JSONDecodeError, ValueError, TypeError, KeyError, IndexError, AttributeError) as exc:
        logger.warning("[ats_scorer] ATS match LLM response could not be parsed (%s); using keyword-only score", exc)
    except Exception as exc:  # pragma: no cover - final safety net, must never raise
        logger.warning("[ats_scorer] ATS match LLM call failed unexpectedly (%s); using keyword-only score", exc)

    return result


def _extract_job_keywords(job_description: str) -> List[str]:
    """
    Lightweight keyword tokenization of a job description for the overlap
    baseline. Deliberately simple (unlike agents.skill_extractor.extract_required_skills,
    which uses an LLM/taxonomy) since Part 2's score is meant to be a fast,
    always-available baseline that the optional LLM call can refine.
    """
    if not job_description:
        return []
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9+#.]{1,}", job_description)
    seen: Dict[str, None] = {}
    for token in tokens:
        cleaned = token.strip(".")
        if len(cleaned) <= 2:
            continue
        if cleaned.lower() in _STOPWORDS:
            continue
        seen.setdefault(cleaned, None)
    return list(seen.keys())[:40]


_STOPWORDS = {
    "the", "and", "for", "with", "you", "your", "our", "are", "will", "this", "that",
    "have", "has", "from", "who", "job", "role", "work", "team", "years", "experience",
    "including", "such", "into", "able", "using", "use", "can", "all", "any", "not",
    "about", "over", "per", "etc", "may", "must", "strong", "good", "excellent",
}
