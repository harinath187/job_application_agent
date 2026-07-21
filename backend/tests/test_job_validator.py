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
        "dropped_low_skill_overlap": 0,
        "total_after": 2,
    }


def test_validate_jobs_passes_both_experience_and_skill_checks(monkeypatch):
    from backend.agents import job_validator

    monkeypatch.setattr(job_validator, "extract_required_skills", lambda description, job_id=None: ["Python", "SQL"])
    monkeypatch.setattr(job_validator, "MIN_SKILL_OVERLAP", 0.2)

    jobs = [{"title": "Junior Python Developer", "description": "Entry level Python role requiring SQL knowledge."}]

    filtered, stats = job_validator.validate_jobs(jobs, "fresher", resume_skills=["Python", "SQL"])

    assert len(filtered) == 1
    assert stats["dropped_seniority_mismatch"] == 0
    assert stats["dropped_low_skill_overlap"] == 0


def test_validate_jobs_fails_experience_only(monkeypatch):
    from backend.agents import job_validator

    monkeypatch.setattr(job_validator, "extract_required_skills", lambda description, job_id=None: ["Python", "SQL"])

    jobs = [{"title": "Senior Backend Engineer", "description": "Need 7+ years building distributed systems in Python and SQL."}]

    filtered, stats = job_validator.validate_jobs(jobs, "fresher", resume_skills=["Python", "SQL"])

    assert len(filtered) == 0
    assert stats["dropped_seniority_mismatch"] == 1
    assert stats["dropped_low_skill_overlap"] == 0


def test_validate_jobs_fails_skills_only(monkeypatch):
    from backend.agents import job_validator

    monkeypatch.setattr(job_validator, "extract_required_skills", lambda description, job_id=None: ["Rust", "Kubernetes", "Go"])
    monkeypatch.setattr(job_validator, "MIN_SKILL_OVERLAP", 0.2)

    jobs = [{"title": "Junior Platform Engineer", "description": "Entry level role working with Rust, Kubernetes, and Go."}]

    filtered, stats = job_validator.validate_jobs(jobs, "fresher", resume_skills=["Python", "SQL"])

    assert len(filtered) == 0
    assert stats["dropped_seniority_mismatch"] == 0
    assert stats["dropped_low_skill_overlap"] == 1


def test_validate_jobs_fails_both_experience_and_skills(monkeypatch):
    from backend.agents import job_validator

    monkeypatch.setattr(job_validator, "extract_required_skills", lambda description, job_id=None: ["Rust", "Kubernetes", "Go"])
    monkeypatch.setattr(job_validator, "MIN_SKILL_OVERLAP", 0.2)

    jobs = [{"title": "Senior Platform Engineer", "description": "Need 7+ years with Rust, Kubernetes, and Go."}]

    filtered, stats = job_validator.validate_jobs(jobs, "fresher", resume_skills=["Python", "SQL"])

    assert len(filtered) == 0
    assert stats["dropped_seniority_mismatch"] == 1
    # Skill extraction is never invoked once the experience check already failed.
    assert stats["dropped_low_skill_overlap"] == 0


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
