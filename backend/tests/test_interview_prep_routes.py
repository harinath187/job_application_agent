import json

import pytest
from fastapi.testclient import TestClient

import utils.db as dbmod


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(dbmod, "DB_PATH", tmp_path / "test_jobs.db")
    dbmod.init_db()

    import api.main as main_module
    return TestClient(main_module.app)


def _create_session_and_job():
    session_id = "session-interview-prep"
    dbmod.insert_session(session_id, "complete")
    dbmod.update_session_parsed_resume_data(session_id, {"resume_text": "Experienced engineer.", "skills": ["Python"]})
    job_id = dbmod.insert_job(session_id, {"title": "Backend Engineer", "company": "Acme", "description": "Needs Python."})
    return session_id, job_id


def test_post_interview_prep_returns_404_for_missing_job(client):
    response = client.post("/api/jobs/9999/interview-prep")
    assert response.status_code == 404


def test_get_interview_prep_returns_404_when_not_generated(client):
    _, job_id = _create_session_and_job()
    response = client.get(f"/api/jobs/{job_id}/interview-prep")
    assert response.status_code == 404


def test_post_interview_prep_generates_and_caches(client, monkeypatch):
    _, job_id = _create_session_and_job()

    import api.routes.interview_prep as route_module
    calls = []

    def fake_generate(**kwargs):
        calls.append(kwargs)
        return {
            "job_id": job_id,
            "generated_at": "2026-01-01T00:00:00",
            "technical_questions": ["Q1"],
            "behavioral_questions": ["Q2"],
            "resume_specific_questions": ["Q3"],
            "suggested_talking_points": {"technical": ["point"]},
            "source": "llm",
        }

    monkeypatch.setattr(route_module, "generate_interview_prep", fake_generate)

    response = client.post(f"/api/jobs/{job_id}/interview-prep")
    assert response.status_code == 200
    body = response.json()
    assert body["cached"] is False
    assert body["interview_prep"]["technical_questions"] == ["Q1"]
    assert len(calls) == 1

    # Second POST should hit the cache and not call the LLM again.
    response2 = client.post(f"/api/jobs/{job_id}/interview-prep")
    assert response2.status_code == 200
    assert response2.json()["cached"] is True
    assert len(calls) == 1

    # GET should also return the cached result without regenerating.
    response3 = client.get(f"/api/jobs/{job_id}/interview-prep")
    assert response3.status_code == 200
    assert response3.json()["interview_prep"]["technical_questions"] == ["Q1"]
    assert len(calls) == 1
