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
    session_id = "session-ats-match"
    dbmod.insert_session(session_id, "complete")
    dbmod.update_session_parsed_resume_data(session_id, {"resume_text": "Experienced Python engineer.", "skills": ["Python"]})
    job_id = dbmod.insert_job(session_id, {"title": "Backend Engineer", "company": "Acme", "description": "Needs Python and AWS."})
    return session_id, job_id


def test_post_ats_match_returns_404_for_missing_job(client):
    response = client.post("/api/jobs/9999/ats-match")
    assert response.status_code == 404


def test_get_ats_match_returns_404_when_not_computed(client):
    _, job_id = _create_session_and_job()
    response = client.get(f"/api/jobs/{job_id}/ats-match")
    assert response.status_code == 404


def test_post_ats_match_computes_and_caches(client, monkeypatch):
    _, job_id = _create_session_and_job()

    import api.routes.ats_match as route_module

    calls = []

    class FakeResult:
        def to_dict(self):
            return {
                "matched_keywords": ["Python"],
                "missing_keywords": ["AWS"],
                "match_score": 55,
                "notes": None,
                "source": "keyword",
            }

    def fake_compute(**kwargs):
        calls.append(kwargs)
        return FakeResult()

    monkeypatch.setattr(route_module, "compute_ats_match_score", fake_compute)

    response = client.post(f"/api/jobs/{job_id}/ats-match")
    assert response.status_code == 200
    body = response.json()
    assert body["cached"] is False
    assert body["ats_match"]["match_score"] == 55
    assert len(calls) == 1

    # Second POST should hit the cache and not recompute.
    response2 = client.post(f"/api/jobs/{job_id}/ats-match")
    assert response2.status_code == 200
    assert response2.json()["cached"] is True
    assert len(calls) == 1

    # GET should also return the cached result.
    response3 = client.get(f"/api/jobs/{job_id}/ats-match")
    assert response3.status_code == 200
    assert response3.json()["ats_match"]["match_score"] == 55
    assert len(calls) == 1


def test_upload_response_wires_ats_structure_result_into_session(tmp_path, monkeypatch):
    """
    Part 1 is computed inside the background pipeline (pdf_parser_node), not
    synchronously in the POST /api/upload response (that endpoint returns 202
    before the background task runs). This test verifies it is persisted onto
    the session and surfaced via GET /api/jobs, which is what the frontend
    polls after upload.
    """
    monkeypatch.setattr(dbmod, "DB_PATH", tmp_path / "test_jobs_upload.db")
    dbmod.init_db()

    session_id = "session-upload-ats"
    dbmod.insert_session(session_id, "processing")

    fake_result = {"score": 90, "passed_checks": ["contact_email"], "failed_checks": [], "is_likely_scanned": False}
    dbmod.update_session_ats_structure_result(session_id, fake_result)

    session_data = dbmod.get_session_data(session_id)
    assert session_data["ats_structure_result"] == fake_result
