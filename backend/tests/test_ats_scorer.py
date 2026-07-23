import json

import pytest
from reportlab.pdfgen import canvas

import utils.ats_scorer as ats_scorer


def _write_pdf(path, lines):
    c = canvas.Canvas(str(path))
    y = 750
    for line in lines:
        c.drawString(50, y, line)
        y -= 15
        if y < 50:
            c.showPage()
            y = 750
    c.save()


CLEAN_RESUME_LINES = (
    ["John Doe", "john.doe@example.com", "+1 555 123 4567", ""]
    + ["Summary"]
    + ["Experienced backend engineer with a track record of shipping reliable services." for _ in range(3)]
    + [""]
    + ["Experience"]
    + [f"- Built and maintained service number {i} handling production traffic at scale." for i in range(20)]
    + [""]
    + ["Education"]
    + ["B.Tech in Computer Science, University Somewhere, 2016-2020"]
    + [""]
    + ["Skills"]
    + ["Python, FastAPI, PostgreSQL, Docker, AWS, Kubernetes, React, TypeScript"]
    + [""]
    + ["Certifications"]
    + ["AWS Certified Solutions Architect"]
)


@pytest.fixture
def clean_resume_pdf(tmp_path):
    pdf_path = tmp_path / "clean_resume.pdf"
    _write_pdf(pdf_path, CLEAN_RESUME_LINES)
    return str(pdf_path)


@pytest.fixture
def blank_pdf(tmp_path):
    """A PDF with a page but no extractable text, simulating a scanned/image-only resume."""
    pdf_path = tmp_path / "blank.pdf"
    c = canvas.Canvas(str(pdf_path))
    c.showPage()
    c.save()
    return str(pdf_path)


def _resume_text_from(lines):
    return "\n".join(lines)


class TestComputeATSStructureScore:
    def test_clean_resume_scores_high(self, clean_resume_pdf):
        resume_text = _resume_text_from(CLEAN_RESUME_LINES)
        result = ats_scorer.compute_ats_structure_score(clean_resume_pdf, resume_text)

        assert result.score >= 70
        assert result.is_likely_scanned is False
        assert "contact_email" in result.passed_checks
        assert "standard_section_headers" in result.passed_checks

    def test_scanned_like_document_forces_low_score(self, blank_pdf):
        result = ats_scorer.compute_ats_structure_score(blank_pdf, "")

        assert result.is_likely_scanned is True
        assert result.score <= 20
        failed_names = {check["check_name"] for check in result.failed_checks}
        assert "parseability" in failed_names

    def test_missing_contact_info_is_flagged(self, clean_resume_pdf):
        resume_text = "Experience\n- Did some work.\n\nEducation\nSome University\n\nSkills\nPython"
        result = ats_scorer.compute_ats_structure_score(clean_resume_pdf, resume_text)

        failed_names = {check["check_name"] for check in result.failed_checks}
        assert "contact_email" in failed_names

    def test_missing_section_headers_is_flagged(self, clean_resume_pdf):
        resume_text = "John Doe\njohn@example.com\n\nJust some free-form text with no recognizable headers at all."
        result = ats_scorer.compute_ats_structure_score(clean_resume_pdf, resume_text)

        failed_names = {check["check_name"] for check in result.failed_checks}
        assert "standard_section_headers" in failed_names

    def test_multi_column_detection_skips_gracefully_without_fitz(self, monkeypatch, clean_resume_pdf):
        monkeypatch.setattr(ats_scorer, "fitz", None)
        resume_text = _resume_text_from(CLEAN_RESUME_LINES)
        result = ats_scorer.compute_ats_structure_score(clean_resume_pdf, resume_text)

        assert "single_column_layout" not in result.passed_checks
        assert not any(check["check_name"] == "single_column_layout" for check in result.failed_checks)

    def test_to_dict_is_json_serializable(self, clean_resume_pdf):
        resume_text = _resume_text_from(CLEAN_RESUME_LINES)
        result = ats_scorer.compute_ats_structure_score(clean_resume_pdf, resume_text)

        serialized = json.dumps(result.to_dict())
        assert "score" in json.loads(serialized)


class TestComputeATSMatchScore:
    def test_high_overlap_scores_higher_than_low_overlap(self):
        resume_text = "Experienced Python and React developer."
        job_description = "We need a Python and React developer with AWS experience."

        high = ats_scorer.compute_ats_match_score(
            resume_text=resume_text,
            extracted_skills=["Python", "React", "AWS"],
            job_description=job_description,
        )
        low = ats_scorer.compute_ats_match_score(
            resume_text=resume_text,
            extracted_skills=["Cobol"],
            job_description=job_description,
        )

        assert high.match_score >= low.match_score

    def test_no_groq_api_key_falls_back_to_keyword_only(self, monkeypatch):
        monkeypatch.setattr(ats_scorer, "GROQ_API_KEY", None)

        result = ats_scorer.compute_ats_match_score(
            resume_text="Python developer.",
            extracted_skills=["Python"],
            job_description="Looking for a Python developer.",
        )

        assert result.source == "keyword"
        assert result.notes is None

    def test_malformed_llm_json_response_falls_back_without_raising(self, monkeypatch):
        monkeypatch.setattr(ats_scorer, "GROQ_API_KEY", "fake-key")

        class DummyMessage:
            content = "not valid json"

        class DummyChoice:
            message = DummyMessage()

        class DummyResponse:
            choices = [DummyChoice()]

        def fake_get_groq_client():
            return object()

        def fake_call_groq_with_retry(client, **kwargs):
            return DummyResponse()

        monkeypatch.setattr(ats_scorer, "get_groq_client", fake_get_groq_client)
        monkeypatch.setattr(ats_scorer, "call_groq_with_retry", fake_call_groq_with_retry)

        result = ats_scorer.compute_ats_match_score(
            resume_text="Python developer.",
            extracted_skills=["Python"],
            job_description="Looking for a Python developer.",
        )

        assert result.source == "keyword"

    def test_groq_call_failed_error_falls_back_without_raising(self, monkeypatch):
        monkeypatch.setattr(ats_scorer, "GROQ_API_KEY", "fake-key")

        def fake_get_groq_client():
            return object()

        def fake_call_groq_with_retry(client, **kwargs):
            raise ats_scorer.GroqCallFailedError("rate limited", attempts=3)

        monkeypatch.setattr(ats_scorer, "get_groq_client", fake_get_groq_client)
        monkeypatch.setattr(ats_scorer, "call_groq_with_retry", fake_call_groq_with_retry)

        result = ats_scorer.compute_ats_match_score(
            resume_text="Python developer.",
            extracted_skills=["Python"],
            job_description="Looking for a Python developer.",
        )

        assert result.source == "keyword"
