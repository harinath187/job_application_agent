import json

import agents.interview_prep_agent as interview_prep_agent


class DummyMessage:
    def __init__(self, content: str):
        self.content = content


class DummyChoice:
    def __init__(self, content: str):
        self.message = DummyMessage(content)


class DummyResponse:
    def __init__(self, content: str):
        self.choices = [DummyChoice(content)]


class DummyClient:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0

    @property
    def chat(self):
        return self

    @property
    def completions(self):
        return self

    def create(self, **kwargs):
        self.calls += 1
        content = self._responses.pop(0)
        return DummyResponse(content)


VALID_LLM_RESPONSE = json.dumps({
    "technical_questions": ["How have you used Kubernetes in production?"],
    "behavioral_questions": ["Tell me about a time you resolved a conflict."],
    "resume_specific_questions": ["Your resume lists Python but the JD needs Go; how would you ramp up?"],
    "suggested_talking_points": {
        "technical": ["Mention specific Kubernetes projects"],
        "behavioral": ["Use STAR format"],
        "resume_specific": ["Be upfront about the gap"],
    },
})

JOB = {"id": 12, "title": "Senior Backend Engineer", "company": "Acme", "description": "Requires Kubernetes and Go."}


def test_generate_interview_prep_uses_llm_when_response_is_valid(monkeypatch):
    client = DummyClient([VALID_LLM_RESPONSE])
    monkeypatch.setattr(interview_prep_agent, "get_groq_client", lambda: client)

    result = interview_prep_agent.generate_interview_prep(
        resume_text="Experienced Python engineer.",
        extracted_skills=["Python", "SQL"],
        job=JOB,
    )

    assert result["job_id"] == 12
    assert result["source"] == "llm"
    assert result["technical_questions"] == ["How have you used Kubernetes in production?"]
    assert result["behavioral_questions"] == ["Tell me about a time you resolved a conflict."]
    assert result["resume_specific_questions"]
    assert "technical" in result["suggested_talking_points"]
    assert client.calls == 1


def test_generate_interview_prep_falls_back_on_malformed_llm_response(monkeypatch):
    client = DummyClient(["not valid json"])
    monkeypatch.setattr(interview_prep_agent, "get_groq_client", lambda: client)

    result = interview_prep_agent.generate_interview_prep(
        resume_text="Experienced Python engineer.",
        extracted_skills=["Python", "SQL"],
        job=JOB,
    )

    assert result["source"] == "fallback"
    assert result["job_id"] == 12
    assert len(result["technical_questions"]) > 0
    assert len(result["behavioral_questions"]) > 0
    assert len(result["resume_specific_questions"]) > 0
    assert isinstance(result["suggested_talking_points"], dict)


def test_generate_interview_prep_falls_back_without_groq_api_key(monkeypatch):
    def raise_runtime_error():
        raise RuntimeError("GROQ_API_KEY is not set.")

    monkeypatch.setattr(interview_prep_agent, "get_groq_client", raise_runtime_error)

    result = interview_prep_agent.generate_interview_prep(
        resume_text="Experienced Python engineer.",
        extracted_skills=["Python"],
        job=JOB,
    )

    assert result["source"] == "fallback"
    assert result["technical_questions"]


def test_build_fallback_interview_prep_infers_seniority_bucket():
    senior_job = {"title": "Staff Engineer", "company": "Acme", "description": ""}
    result = interview_prep_agent.build_fallback_interview_prep(senior_job, ["Python"])

    assert result["technical_questions"] == interview_prep_agent.FALLBACK_QUESTION_BANK["senior"]["technical_questions"]


def test_build_fallback_interview_prep_references_actual_resume_content():
    resume_sections = {
        "experience": [{"title": "Backend Engineer", "company": "Initech", "dates": "2021-2024", "bullets": ["Built APIs"]}],
    }
    result = interview_prep_agent.build_fallback_interview_prep(
        JOB, ["Python"], projects=["Inventory Tracker"], resume_sections=resume_sections
    )

    resume_questions_text = " ".join(result["resume_specific_questions"])
    assert "Initech" in resume_questions_text
    assert "Backend Engineer" in resume_questions_text
    assert "Inventory Tracker" in resume_questions_text


def test_generate_interview_prep_passes_resume_details_into_prompt(monkeypatch):
    captured_prompts = []

    def fake_call_groq_with_retry(client, **kwargs):
        captured_prompts.append(kwargs["messages"][0]["content"])
        return DummyResponse(VALID_LLM_RESPONSE)

    monkeypatch.setattr(interview_prep_agent, "get_groq_client", lambda: object())
    monkeypatch.setattr(interview_prep_agent, "call_groq_with_retry", fake_call_groq_with_retry)

    interview_prep_agent.generate_interview_prep(
        resume_text="Experienced engineer.",
        extracted_skills=["Python"],
        job=JOB,
        projects=["Inventory Tracker"],
        certifications=["AWS Certified"],
        resume_sections={"experience": [{"title": "Backend Engineer", "company": "Initech", "dates": "2021-2024", "bullets": ["Built APIs"]}]},
        experience_summary="3+ years",
    )

    assert len(captured_prompts) == 1
    prompt = captured_prompts[0]
    assert "Inventory Tracker" in prompt
    assert "AWS Certified" in prompt
    assert "Initech" in prompt
    assert "Backend Engineer" in prompt
    assert "3+ years" in prompt
