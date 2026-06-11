import asyncio
import os
from pathlib import Path

import pytest
import httpx

pytestmark = pytest.mark.asyncio


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    db_file = tmp_path / "test_jobs.db"
    # Ensure parent dir exists
    db_file.parent.mkdir(parents=True, exist_ok=True)
    # Patch DB_PATH in utils.db before importing app
    monkeypatch.setattr("backend.utils.db.DB_PATH", db_file)
    # Initialize schema
    from backend.utils import db as dbmod

    dbmod.init_db()
    return db_file


@pytest.fixture
async def client(temp_db):
    # Import app after DB_PATH patched
    from backend.api.main import app
    async with httpx.AsyncClient(app=app, base_url="http://testserver") as ac:
        yield ac


async def test_subscribe_new_user(client):
    payload = {
        "email": "alice@example.com",
        "telegram_chat_id": "",
        "role": "Software Engineer",
        "location": "Remote",
        "keywords": "python"
    }
    resp = await client.post('/api/alerts/subscribe', json=payload)
    assert resp.status_code in (200, 201)
    data = resp.json()
    assert "user_id" in data and "preference_id" in data


async def test_subscribe_existing_user_adds_preference(client):
    email = "bob@example.com"
    payload1 = {"email": email, "role": "Frontend", "location": "NY"}
    payload2 = {"email": email, "role": "Backend", "location": "NY"}

    r1 = await client.post('/api/alerts/subscribe', json=payload1)
    assert r1.status_code in (200, 201)
    data1 = r1.json()
    user_id = data1["user_id"]

    r2 = await client.post('/api/alerts/subscribe', json=payload2)
    assert r2.status_code in (200, 201)

    # Check DB for two preferences for same user
    from backend.utils.db import get_db_connection
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS c FROM alert_preferences WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    assert row["c"] >= 2
    conn.close()


async def test_upsert_alert_job_deduplication(temp_db):
    # Create user + preference
    from backend.utils.db import insert_alert_user, insert_alert_preference, upsert_alert_job

    user_id = insert_alert_user('cathy@example.com')
    pref_id = insert_alert_preference(user_id, 'SWE', 'Remote', None)

    job = {"title": "X", "company": "Y", "location": "Remote", "apply_url": "http://x", "description_snippet": "s", "job_id_external": "123"}
    job_hash = "abc123hash"

    first = upsert_alert_job(pref_id, job_hash, job)
    second = upsert_alert_job(pref_id, job_hash, job)

    assert isinstance(first, int)
    assert second is None


async def test_extract_email_from_resume_text():
    from backend.agents.pdf_parser import extract_email_from_text

    text = "Jane Doe\nEmail: Jane.Doe+jobs@example.com\nPython, FastAPI"
    assert extract_email_from_text(text) == "jane.doe+jobs@example.com"
    assert extract_email_from_text("No contact here") is None


async def test_alert_preference_upsert_reuses_same_role_location(temp_db):
    from backend.utils.db import (
        get_db_connection,
        insert_alert_user,
        upsert_alert_preference_for_user,
    )

    user_id = insert_alert_user("reuse@example.com")
    first = upsert_alert_preference_for_user(user_id, "Software Engineer", "Remote")
    second = upsert_alert_preference_for_user(user_id, "software engineer", "remote")

    assert first == second

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS c FROM alert_preferences WHERE user_id = ?", (user_id,))
    assert cur.fetchone()["c"] == 1
    conn.close()


async def test_toggle_alerts(client):
    email = "dave@example.com"
    await client.post('/api/alerts/subscribe', json={"email": email, "role": "DevOps", "location": "US"})

    resp = await client.patch('/api/alerts/toggle', json={"email": email, "active": False})
    assert resp.status_code == 200

    # Verify DB
    from backend.utils.db import get_db_connection
    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT ap.is_active FROM alert_preferences ap JOIN alert_users au ON ap.user_id = au.id WHERE au.email = ?", (email,))
    rows = cur.fetchall()
    assert all(r["is_active"] == 0 for r in rows)
    conn.close()


async def test_full_unsubscribe_cascades(temp_db):
    # Subscribe
    from backend.utils.db import insert_alert_user, insert_alert_preference, upsert_alert_job, get_db_connection
    user_id = insert_alert_user('erin@example.com')
    pref_id = insert_alert_preference(user_id, 'QA', 'Remote', None)

    job = {"title": "QA Eng", "company": "Z", "location": "Remote", "apply_url": "http://z", "description_snippet": "s", "job_id_external": "jid"}
    job_hash = "jh1"
    upsert_alert_job(pref_id, job_hash, job)

    # Unsubscribe via API
    async with httpx.AsyncClient(app=__import__('backend.api.main', fromlist=['app']).app, base_url='http://testserver') as ac:
        r = await ac.delete('/api/alerts/unsubscribe', params={"email": 'erin@example.com'})
        assert r.status_code == 200

    conn = get_db_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) AS c FROM alert_users WHERE email = ?", ('erin@example.com',))
    assert cur.fetchone()["c"] == 0
    cur.execute("SELECT COUNT(*) AS c FROM alert_preferences WHERE user_id = ?", (user_id,))
    assert cur.fetchone()["c"] == 0
    cur.execute("SELECT COUNT(*) AS c FROM alert_jobs WHERE preference_id = ?", (pref_id,))
    assert cur.fetchone()["c"] == 0
    conn.close()


async def test_cleanup_removes_never_opted_in(temp_db):
    from backend.utils.db import get_db_connection
    from backend.alerts.cleanup import run_cleanup
    conn = get_db_connection()
    cur = conn.cursor()
    # insert user
    cur.execute("INSERT INTO alert_users (email, created_at) VALUES (?, datetime('now','-2 days'))", ('old@example.com',))
    user_id = cur.lastrowid
    # insert preference with alert_enabled = 0 and created_at 2 days ago
    cur.execute(
        "INSERT INTO alert_preferences (user_id, role, location, keywords, is_active, alert_enabled, last_checked_at, expires_at, created_at) VALUES (?, ?, ?, ?, 1, 0, NULL, NULL, datetime('now','-2 days'))",
        (user_id, 'Any', 'Anywhere', None)
    )
    conn.commit()

    # Run cleanup
    run_cleanup()

    cur.execute("SELECT COUNT(*) AS c FROM alert_preferences WHERE user_id = ?", (user_id,))
    assert cur.fetchone()["c"] == 0
    conn.close()


async def test_delete_single_search_history_item(temp_db):
    from backend.utils.db import insert_session, insert_search_history, get_search_history

    session_id = "session-delete-one"
    insert_session(session_id, "complete")
    insert_search_history(session_id, "resume.pdf", "/tmp/resume.pdf", "Engineer", "Remote")

    assert len(get_search_history()) == 1

    async with httpx.AsyncClient(app=__import__('backend.api.main', fromlist=['app']).app, base_url='http://testserver') as ac:
        resp = await ac.delete(f'/api/search-history/{session_id}')
        assert resp.status_code == 200

    assert get_search_history() == []


async def test_delete_multiple_search_history_items(temp_db):
    from backend.utils.db import insert_session, insert_search_history, get_search_history

    session_ids = ["session-bulk-1", "session-bulk-2"]
    for idx, session_id in enumerate(session_ids, start=1):
      insert_session(session_id, "complete")
      insert_search_history(session_id, f"resume-{idx}.pdf", f"/tmp/resume-{idx}.pdf", "Engineer", "Remote")

    assert len(get_search_history()) == 2

    async with httpx.AsyncClient(app=__import__('backend.api.main', fromlist=['app']).app, base_url='http://testserver') as ac:
        resp = await ac.delete('/api/search-history', params=[('session_ids', session_ids[0]), ('session_ids', session_ids[1])])
        assert resp.status_code == 200

    assert get_search_history() == []
