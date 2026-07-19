import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test_jobs.db"
    db_file.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("backend.utils.db.DB_PATH", db_file)
    from backend.utils import db as dbmod

    dbmod.init_db()
    return db_file


def test_validate_jobs_filters_fresher_batch():
    from backend.agents.job_validator import validate_jobs

    jobs = [
        {"title": "Junior Python Developer", "description": "Entry level Python role with mentorship and strong learning opportunities."},
        {"title": "Senior Backend Engineer", "description": "Need 7+ years building distributed systems and leading architecture decisions."},
        {"title": "Platform Engineer", "description": "Build internal tools and services for a growing product team."},
        {"title": "No Description Role", "description": "short"},
    ]

    filtered, stats = validate_jobs(jobs, "fresher")

    assert [job["title"] for job in filtered] == [
        "Junior Python Developer",
        "Platform Engineer",
    ]
    assert stats == {
        "total_before": 4,
        "dropped_no_description": 1,
        "dropped_seniority_mismatch": 1,
        "total_after": 2,
    }


def test_session_data_includes_validation_stats(temp_db):
    from backend.utils.db import (
        insert_session,
        insert_search_history,
        insert_job,
        update_session_validation_stats,
        get_session_data,
    )

    session_id = "session-validation-stats"
    insert_session(session_id, "processing")
    insert_search_history(session_id, "resume.pdf", "/tmp/resume.pdf", "Engineer", "Remote")
    insert_job(session_id, {
        "title": "Junior Python Developer",
        "company": "Acme",
        "location": "Remote",
        "job_url": "https://example.com/j1",
        "description": "Entry level Python role with mentorship and strong learning opportunities.",
        "role_confidence": 0.75,
    })
    update_session_validation_stats(session_id, {
        "total_before": 1,
        "dropped_no_description": 0,
        "dropped_seniority_mismatch": 0,
        "total_after": 1,
    })

    data = get_session_data(session_id)

    assert data["validation_stats"]["total_after"] == 1
    assert data["validation_stats"]["total_before"] == 1
