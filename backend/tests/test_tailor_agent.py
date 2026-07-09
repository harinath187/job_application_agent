import agents.tailor_agent as tailor_agent
import orchestrator.graph as graph


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


def test_tailor_resume_fails_gracefully_after_invalid_json_retry(monkeypatch):
    client = DummyClient(["not json", '{"summary": "", "skills": ["Python"], "bullet_rewrites": [""]}'])
    monkeypatch.setattr(tailor_agent, "get_groq_client", lambda: client)

    updates = []
    monkeypatch.setattr(
        tailor_agent,
        "update_job_status",
        lambda job_id, status, resume_path=None, cover_letter_path=None: updates.append((job_id, status, resume_path, cover_letter_path)),
    )

    result = tailor_agent.tailor_resume(
        resume_text="Experienced software engineer.",
        job={"id": 7, "title": "Data Scientist", "company": "Acme", "description": "Need Python and analytics."},
        skills=["Python", "SQL", "Docker", "Linux", "API"],
        target_role="Data Scientist",
        target_location="Remote",
        experience_level="3+ years",
    )

    assert result["status"] == "failed"
    assert result["reason"] == "llm_output_invalid"
    assert client.calls == 2
    assert updates == [(7, "failed", None, None)]


def test_tailor_resume_patches_existing_resume_sections(monkeypatch):
    client = DummyClient([
        '{"summary": "A strong data engineer with publication experience.", "skills": ["Python", "SQL", "Docker", "AWS", "Spark"], "bullet_rewrites": [{"job_index": 0, "bullet_index": 0, "text": "Built resilient data pipelines for analytics."}]}'
    ])
    monkeypatch.setattr(tailor_agent, "get_groq_client", lambda: client)

    resume_sections = {
        "contact_info": {"name": "Ada Lovelace", "email": "ada@example.com", "phone": "555-1234", "links": []},
        "summary": "An engineer with broad experience.",
        "skills": ["Python", "SQL"],
        "experience": [
            {"company": "Acme", "title": "Data Engineer", "dates": "2020-2023", "bullets": ["Built ETL jobs."]},
        ],
        "education": [{"school": "MIT", "degree": "BSc", "dates": "2017-2021", "details": []}],
    }

    result = tailor_agent.tailor_resume(
        resume_text="Experienced software engineer.",
        job={"id": 8, "title": "Data Engineer", "company": "Acme", "description": "Need Python and analytics."},
        skills=["Python", "SQL", "Docker", "Linux", "API"],
        target_role="Data Engineer",
        target_location="Remote",
        experience_level="3+ years",
        resume_sections=resume_sections,
    )

    assert result["summary"].endswith(".")
    assert result["skills"][:4] == ["Python", "SQL", "Docker", "AWS"]
    assert result["experience"][0]["bullets"][0] == "Built ETL jobs."
    assert result["experience"][0]["company"] == "Acme"
    assert len(result["education"]) == 1
    assert result["contact_info"]["name"] == "Ada Lovelace"


def test_tailor_node_marks_failed_empty_data_without_writing_pdf(monkeypatch, tmp_path):
    captured_resume_sections = []

    def fake_tailor_resume(*args, **kwargs):
        captured_resume_sections.append(kwargs.get("resume_sections"))
        return {
            "summary": "",
            "skills": [],
            "bullet_rewrites": [],
            "resume_sections": {},
        }

    updates = []

    monkeypatch.setattr(graph, "tailor_resume", fake_tailor_resume)
    monkeypatch.setattr(graph, "RESUMES_DIR", tmp_path)
    monkeypatch.setattr(
        graph,
        "update_job_status",
        lambda job_id, status, resume_path=None, cover_letter_path=None: updates.append((job_id, status, resume_path, cover_letter_path)),
    )

    state = {
        "resume_text": "Experienced software engineer.",
        "extracted_skills": ["Python", "SQL"],
        "extracted_role": "Software Engineer",
        "extracted_location": "Remote",
        "jobs": [{"id": 42, "title": "Software Engineer", "company": "Acme", "location": "Remote", "description": "Build software"}],
        "resume_sections": {},
    }

    result = graph.tailor_node(state)

    assert captured_resume_sections == [{}]
    assert updates == [(42, "failed_empty_data", None, None)]
    assert result["tailored_resumes"] == []
    assert list(tmp_path.glob("*.pdf")) == []


def test_save_tailored_resume_accepts_flexible_sections(monkeypatch, tmp_path):
    monkeypatch.setattr(tailor_agent, "_render_resume_pdf_generic", lambda sections, output_path: output_path.write_bytes(b"%PDF-1.4"))

    output_path = tailor_agent.save_tailored_resume(
        resume_text="Experienced software engineer.",
        tailored_data={
            "status": "ok",
            "resume_sections": {
                "contact_info": {"name": "Ada Lovelace", "email": "ada@example.com", "phone": "", "links": []},
                "summary": "A strong engineer.",
                "skills": ["Python", "SQL"],
                "experience": [{"company": "Acme", "title": "Engineer", "dates": "2020-2023", "bullets": ["Built software."]}],
                "education": [],
                "additional_sections": [{"heading": "Hobbies", "items": ["Reading"]}],
            },
        },
        job={"title": "Software Engineer", "company": "Acme"},
        output_dir=str(tmp_path),
    )

    assert output_path.endswith(".pdf")


def test_render_resume_pdf_generic_handles_arbitrary_sections(monkeypatch, tmp_path):
    captured_story = []

    class FakeDoc:
        def __init__(self, *args, **kwargs):
            pass

        def build(self, story):
            captured_story.extend(story)

    monkeypatch.setattr(tailor_agent, "SimpleDocTemplate", FakeDoc)

    sections = {
        "contact_info": {"name": "Maya Patel", "email": "maya@example.com", "phone": "555-9999", "links": ["linkedin.com/in/maya"]},
        "summary": "Seasoned engineer.",
        "skills": ["Python", "SQL"],
        "experience": [{"company": "Acme", "title": "Engineer", "dates": "2020-2023", "bullets": ["Built pipelines."]}],
        "education": [{"degree": "B.Tech", "institution": "NIT Trichy", "location": "Trichy", "dates": "2021", "grade": "8.9", "details": ["Algorithms"]}],
        "additional_sections": [
            {"heading": "Hobbies", "items": ["Trail running", "Ceramics"]},
            {"heading": "Awards", "items": ["Dean's List"]},
        ],
    }

    tailor_agent._render_resume_pdf_generic(sections, tmp_path / "resume.pdf")

    rendered_text = [getattr(item, "text", "") for item in captured_story if hasattr(item, "text")]
    assert any("Professional Summary" in text for text in rendered_text)
    assert any("Hobbies" in text for text in rendered_text)
    assert any("Awards" in text for text in rendered_text)
    assert any("Experience" in text for text in rendered_text)
