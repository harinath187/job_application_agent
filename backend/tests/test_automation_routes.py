import pytest
from fastapi.testclient import TestClient

import utils.db as dbmod


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(dbmod, "DB_PATH", tmp_path / "test_jobs.db")
    dbmod.init_db()

    import api.main as main_module
    return TestClient(main_module.app)


def _create_session_and_job(job_url="https://boards.greenhouse.io/acme/jobs/123"):
    session_id = "session-automation"
    dbmod.insert_session(session_id, "complete")
    job_id = dbmod.insert_job(session_id, {
        "title": "Backend Engineer",
        "company": "Acme",
        "description": "Needs Python.",
        "job_url": job_url,
    })
    return session_id, job_id


def test_autofill_support_returns_404_for_missing_job(client):
    response = client.get("/api/jobs/9999/autofill-support")
    assert response.status_code == 404


def test_autofill_support_reports_supported_platform(client):
    _, job_id = _create_session_and_job("https://boards.greenhouse.io/acme/jobs/123")
    response = client.get(f"/api/jobs/{job_id}/autofill-support")
    assert response.status_code == 200
    body = response.json()
    assert body["supported"] is True
    assert body["platform"] == "greenhouse"


def test_autofill_support_reports_unsupported_platform(client):
    _, job_id = _create_session_and_job("https://careers.acme.com/jobs/123")
    response = client.get(f"/api/jobs/{job_id}/autofill-support")
    assert response.status_code == 200
    body = response.json()
    assert body["supported"] is False
    assert body["platform"] is None


def test_autofill_returns_404_for_missing_job(client):
    response = client.post("/api/jobs/9999/autofill")
    assert response.status_code == 404


def test_autofill_unsupported_platform_returns_200_with_failure(client, monkeypatch):
    _, job_id = _create_session_and_job("https://careers.acme.com/jobs/123")

    response = client.post(f"/api/jobs/{job_id}/autofill")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert "unsupported" in body["error"].lower()


def test_autofill_happy_path_calls_runner_and_returns_result(client, monkeypatch):
    _, job_id = _create_session_and_job("https://boards.greenhouse.io/acme/jobs/123")

    import api.routes.automation as route_module
    from automation.adapters.base import FillResult, SkippedField

    calls = []

    async def fake_run_autofill(job_url, applicant_data, job_id=None):
        calls.append((job_url, applicant_data, job_id))
        return FillResult(
            fields_filled=["email"],
            fields_skipped=[SkippedField(field_name="work_authorization", reason="requires manual input")],
            success=True,
        )

    monkeypatch.setattr(route_module, "run_autofill", fake_run_autofill)

    response = client.post(f"/api/jobs/{job_id}/autofill")
    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["fields_filled"] == ["email"]
    assert body["fields_skipped"][0]["field_name"] == "work_authorization"
    assert len(calls) == 1
    assert calls[0][0] == "https://boards.greenhouse.io/acme/jobs/123"
