"""
SQLite database initialization and operations for job application sessions.
"""
import sqlite3
import uuid
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any


DB_PATH = Path(__file__).resolve().parent.parent / "data" / "jobs.db"
ALLOWED_JOB_STATUSES = {"new", "applied", "interview", "rejected"}


def _add_column_if_missing(cursor: sqlite3.Cursor, table_name: str, column_name: str, alter_sql: str) -> None:
    """Add a column only when it is absent, using SQLite-compatible SQL."""
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = {row[1] for row in cursor.fetchall()}
    if column_name not in columns:
        cursor.execute(alter_sql)


def get_db_connection() -> sqlite3.Connection:
    """Return a SQLite connection with foreign keys enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """
    Initialize SQLite database with sessions, jobs, and alert scheduler tables.
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Create sessions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                experience TEXT,
                created_at TEXT NOT NULL
            )
        """)
        cursor.execute("PRAGMA table_info(sessions)")
        session_columns = {row[1] for row in cursor.fetchall()}
        if "experience" not in session_columns:
            cursor.execute("ALTER TABLE sessions ADD COLUMN experience TEXT")

        # Create search history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS search_history (
                session_id TEXT PRIMARY KEY,
                resume_name TEXT,
                resume_path TEXT,
                role TEXT NOT NULL,
                location TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
            )
        """)

        # Create jobs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                resume_id TEXT,
                title TEXT NOT NULL,
                company TEXT NOT NULL,
                location TEXT,
                job_url TEXT,
                description TEXT,
                resume_path TEXT,
                letter_path TEXT,
                salary_min INTEGER,
                salary_max INTEGER,
                salary_interval TEXT,
                match_pct INTEGER NOT NULL DEFAULT 0,
                missing_keywords TEXT DEFAULT '[]',
                status TEXT NOT NULL DEFAULT 'new',
                created_at TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS resumes (
                id TEXT PRIMARY KEY,
                label TEXT NOT NULL,
                file_path TEXT NOT NULL,
                extracted_role TEXT,
                extracted_location TEXT,
                extracted_skills TEXT,
                uploaded_at TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS skills_gaps (
                job_id TEXT PRIMARY KEY,
                missing_skills TEXT,
                transferable_skills TEXT,
                suggestions TEXT,
                FOREIGN KEY (job_id) REFERENCES jobs(id)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS interview_prep (
                job_id TEXT PRIMARY KEY,
                questions TEXT,
                FOREIGN KEY (job_id) REFERENCES jobs(id)
            )
        """)
        cursor.execute("PRAGMA table_info(jobs)")
        job_columns = {row[1] for row in cursor.fetchall()}
        _add_column_if_missing(cursor, "jobs", "resume_id", "ALTER TABLE jobs ADD COLUMN resume_id TEXT")
        _add_column_if_missing(cursor, "jobs", "resume_path", "ALTER TABLE jobs ADD COLUMN resume_path TEXT")
        _add_column_if_missing(cursor, "jobs", "salary_min", "ALTER TABLE jobs ADD COLUMN salary_min INTEGER")
        _add_column_if_missing(cursor, "jobs", "salary_max", "ALTER TABLE jobs ADD COLUMN salary_max INTEGER")
        _add_column_if_missing(cursor, "jobs", "salary_interval", "ALTER TABLE jobs ADD COLUMN salary_interval TEXT")
        if "letter_path" not in job_columns:
            cursor.execute("ALTER TABLE jobs ADD COLUMN letter_path TEXT")
            if "cover_letter_path" in job_columns:
                cursor.execute("UPDATE jobs SET letter_path = cover_letter_path WHERE letter_path IS NULL")
        _add_column_if_missing(cursor, "jobs", "match_pct", "ALTER TABLE jobs ADD COLUMN match_pct INTEGER NOT NULL DEFAULT 0")
        _add_column_if_missing(cursor, "jobs", "missing_keywords", "ALTER TABLE jobs ADD COLUMN missing_keywords TEXT DEFAULT '[]'")
        _add_column_if_missing(cursor, "jobs", "status", "ALTER TABLE jobs ADD COLUMN status TEXT NOT NULL DEFAULT 'new'")
        _add_column_if_missing(cursor, "jobs", "created_at", "ALTER TABLE jobs ADD COLUMN created_at TEXT")
        _add_column_if_missing(cursor, "jobs", "job_url", "ALTER TABLE jobs ADD COLUMN job_url TEXT")
        cursor.execute("UPDATE jobs SET status = 'new' WHERE status IS NULL OR status = ''")

        # Create alert users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alert_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                telegram_chat_id TEXT,
                name TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            )
        """)

        # Create alert preferences table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alert_preferences (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                role TEXT,
                location TEXT,
                keywords TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                alert_enabled INTEGER NOT NULL DEFAULT 1,
                last_checked_at TEXT,
                expires_at TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES alert_users(id) ON DELETE CASCADE
            )
        """)

        # Create alert jobs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alert_jobs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                preference_id INTEGER NOT NULL,
                job_hash TEXT NOT NULL,
                job_id_external TEXT,
                title TEXT,
                company TEXT,
                location TEXT,
                apply_url TEXT,
                description_snippet TEXT,
                status TEXT NOT NULL DEFAULT 'active',
                expires_at TEXT,
                first_seen_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                FOREIGN KEY (preference_id) REFERENCES alert_preferences(id) ON DELETE CASCADE,
                UNIQUE(preference_id, job_hash)
            )
        """)

        # Create notification history table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notification_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                alert_job_id INTEGER NOT NULL,
                channel TEXT NOT NULL,
                status TEXT NOT NULL,
                error_msg TEXT,
                sent_at TEXT NOT NULL,
                expires_at TEXT,
                FOREIGN KEY (user_id) REFERENCES alert_users(id) ON DELETE CASCADE,
                FOREIGN KEY (alert_job_id) REFERENCES alert_jobs(id) ON DELETE CASCADE
            )
        """)

        # Create scheduler logs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS scheduler_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_at TEXT NOT NULL,
                users_processed INTEGER NOT NULL,
                new_jobs_found INTEGER NOT NULL,
                notifications_sent INTEGER NOT NULL,
                status TEXT NOT NULL,
                error_msg TEXT
            )
        """)

        # Create session alert metadata table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS session_alerts (
                session_id TEXT PRIMARY KEY,
                alert_email TEXT,
                alerts_enabled INTEGER NOT NULL DEFAULT 0,
                alert_message TEXT,
                preference_id INTEGER,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE,
                FOREIGN KEY (preference_id) REFERENCES alert_preferences(id) ON DELETE SET NULL
            )
        """)

        conn.commit()


def insert_session(session_id: str, status: str) -> None:
    """
    Insert a new session into the database.

    Args:
        session_id: Unique session identifier
        status: Initial status (e.g., "processing")
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        created_at = datetime.utcnow().isoformat()
        cursor.execute(
            "INSERT INTO sessions (session_id, status, created_at) VALUES (?, ?, ?)",
            (session_id, status, created_at)
        )
        conn.commit()


def insert_search_history(session_id: str, resume_name: str, resume_path: str, role: str, location: str, experience: str | None = None) -> None:
    """Persist the criteria used for a search session."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        created_at = datetime.utcnow().isoformat()
        cursor.execute(
            """INSERT INTO search_history
               (session_id, resume_name, resume_path, role, location, created_at)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(session_id) DO UPDATE SET
                   resume_name = excluded.resume_name,
                   resume_path = excluded.resume_path,
                   role = excluded.role,
                   location = excluded.location""",
            (session_id, resume_name, resume_path, role, location, created_at)
        )
        cursor.execute(
            "UPDATE sessions SET experience = ? WHERE session_id = ?",
            (experience, session_id)
        )
        conn.commit()


def insert_job(
    session_id: str,
    resume_id: str | None,
    title: str,
    company: str,
    location: str,
    description: str,
    resume_path: str = None,
    letter_path: str = None,
    salary_min: int | None = None,
    salary_max: int | None = None,
    salary_interval: str | None = None,
    match_pct: int = 0,
    missing_keywords: list[str] | None = None,
    job_url: str = None,
) -> str:
    """
    Insert a job into the database.

    Args:
        session_id: Session identifier
        title: Job title
        company: Company name
        location: Job location
        description: Full job description
        resume_path: Optional tailored resume path
        letter_path: Optional cover letter path
        match_pct: ATS match percentage
        missing_keywords: List of missing keywords
        job_url: Optional job URL

    Returns:
        The generated job UUID
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        created_at = datetime.utcnow().isoformat()
        job_id = str(uuid.uuid4())
        missing_keywords_json = json.dumps(missing_keywords or [])
        cursor.execute(
            """INSERT INTO jobs
                (id, session_id, resume_id, title, company, location, job_url, description, resume_path,
                letter_path, salary_min, salary_max, salary_interval, match_pct, missing_keywords, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                job_id,
                session_id,
                resume_id,
                title,
                company,
                location,
                job_url,
                description,
                resume_path,
                letter_path,
                salary_min,
                salary_max,
                salary_interval,
                match_pct,
                missing_keywords_json,
                "new",
                created_at,
            )
        )
        conn.commit()
        return job_id


def _normalize_job_row(job: Dict[str, Any]) -> Dict[str, Any]:
    """Return job rows with compatibility aliases for the UI."""
    if not job:
        return job
    job.setdefault("match_pct", 0)
    job.setdefault("salary_min", None)
    job.setdefault("salary_max", None)
    job.setdefault("salary_interval", None)
    raw_missing_keywords = job.get("missing_keywords", "[]")
    if isinstance(raw_missing_keywords, str):
        try:
            job["missing_keywords"] = json.loads(raw_missing_keywords)
        except json.JSONDecodeError:
            job["missing_keywords"] = []
    elif raw_missing_keywords is None:
        job["missing_keywords"] = []
    job.setdefault("status", "new")
    job["cover_letter_path"] = job.get("letter_path") or job.get("cover_letter_path")
    if not job.get("letter_path") and job.get("cover_letter_path"):
        job["letter_path"] = job["cover_letter_path"]
    return job


def get_jobs(session_id: str) -> List[Dict[str, Any]]:
    """
    Retrieve all jobs for a given session.

    Args:
        session_id: Session identifier

    Returns:
        List of job dictionaries with all fields
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM jobs WHERE session_id = ? ORDER BY created_at DESC", (session_id,))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def get_search_history(session_id: str | None = None) -> List[Dict[str, Any]]:
    """Return saved search runs ordered by most recent first."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if session_id:
            cursor.execute(
                """SELECT sh.session_id, sh.resume_name, sh.resume_path, sh.role, sh.location,
                          sh.created_at, s.status, s.experience
                   FROM search_history sh
                   LEFT JOIN sessions s ON s.session_id = sh.session_id
                   WHERE sh.session_id = ?
                   ORDER BY sh.created_at DESC""",
                (session_id,)
            )
        else:
            cursor.execute(
                """SELECT sh.session_id, sh.resume_name, sh.resume_path, sh.role, sh.location,
                          sh.created_at, s.status, s.experience
                   FROM search_history sh
                   LEFT JOIN sessions s ON s.session_id = sh.session_id
                   ORDER BY sh.created_at DESC"""
            )
        rows = cursor.fetchall()
        return [_normalize_job_row(dict(row)) for row in rows]


def get_jobs_by_session(session_id: str) -> List[Dict[str, Any]]:
    """Backward-compatible alias for get_jobs."""
    return get_jobs(session_id)


def delete_search_history_item(session_id: str) -> bool:
    """Delete a saved search session and its related rows."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM search_history WHERE session_id = ?", (session_id,))
        deleted = cursor.rowcount > 0
        conn.commit()
        return deleted


def delete_search_history_items(session_ids: List[str]) -> int:
    """Delete multiple saved search sessions and return the number removed."""
    if not session_ids:
        return 0

    placeholders = ",".join("?" for _ in session_ids)
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"DELETE FROM search_history WHERE session_id IN ({placeholders})", session_ids)
        deleted_count = cursor.rowcount
        conn.commit()
        return deleted_count


def get_job(job_id: str) -> Dict[str, Any] | None:
    """
    Retrieve a specific job by its ID.

    Args:
        job_id: Job identifier

    Returns:
        Job dictionary or None if not found
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        row = cursor.fetchone()
        return _normalize_job_row(dict(row)) if row else None


def get_job_by_id(job_id: str) -> Dict[str, Any] | None:
    """Backward-compatible alias for get_job."""
    return get_job(job_id)


def update_job_status(job_id: str, status: str, resume_path: str = None, cover_letter_path: str = None) -> None:
    """
    Update job status and file paths.

    Args:
        job_id: Job ID to update
        status: New status
        resume_path: Optional path to tailored resume
        cover_letter_path: Optional path to generated cover letter
    """
    if status not in ALLOWED_JOB_STATUSES:
        raise ValueError(f"Invalid job status: {status}")

    update_job_paths(job_id, resume_path=resume_path, letter_path=cover_letter_path)
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE jobs SET status = ? WHERE id = ?",
            (status, job_id)
        )
        conn.commit()


def update_job_paths(job_id: str, resume_path: str = None, letter_path: str = None) -> None:
    """Update job output file paths once agents complete."""
    if resume_path is None and letter_path is None:
        return

    with get_db_connection() as conn:
        cursor = conn.cursor()
        if resume_path is not None and letter_path is not None:
            cursor.execute(
                "UPDATE jobs SET resume_path = ?, letter_path = ? WHERE id = ?",
                (resume_path, letter_path, job_id)
            )
        elif resume_path is not None:
            cursor.execute(
                "UPDATE jobs SET resume_path = ? WHERE id = ?",
                (resume_path, job_id)
            )
        else:
            cursor.execute(
                "UPDATE jobs SET letter_path = ? WHERE id = ?",
                (letter_path, job_id)
            )
        conn.commit()


def save_resume(label: str, file_path: str, extracted_role: str, extracted_location: str, extracted_skills: list[str]) -> str:
    """Save a reusable resume profile and return its ID."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        resume_id = str(uuid.uuid4())
        uploaded_at = datetime.utcnow().isoformat()
        cursor.execute(
            """INSERT INTO resumes
               (id, label, file_path, extracted_role, extracted_location, extracted_skills, uploaded_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                resume_id,
                label,
                file_path,
                extracted_role,
                extracted_location,
                json.dumps(extracted_skills or []),
                uploaded_at,
            )
        )
        conn.commit()
        return resume_id


def list_resumes() -> List[Dict[str, Any]]:
    """Return saved resumes ordered by most recent first."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM resumes ORDER BY uploaded_at DESC")
        rows = cursor.fetchall()
        results = []
        for row in rows:
            item = dict(row)
            try:
                item["extracted_skills"] = json.loads(item.get("extracted_skills", "[]"))
            except json.JSONDecodeError:
                item["extracted_skills"] = []
            results.append(item)
        return results


def get_resume(resume_id: str) -> Dict[str, Any] | None:
    """Return one saved resume by ID."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM resumes WHERE id = ?", (resume_id,))
        row = cursor.fetchone()
        if not row:
            return None
        item = dict(row)
        try:
            item["extracted_skills"] = json.loads(item.get("extracted_skills", "[]"))
        except json.JSONDecodeError:
            item["extracted_skills"] = []
        return item


def update_resume_label(resume_id: str, label: str) -> bool:
    """Update a saved resume label."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE resumes SET label = ? WHERE id = ?", (label, resume_id))
        conn.commit()
        return cursor.rowcount > 0


def delete_resume(resume_id: str) -> None:
    """Delete a saved resume record and its file if present."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT file_path FROM resumes WHERE id = ?", (resume_id,))
        row = cursor.fetchone()
        file_path = row["file_path"] if row else None
        cursor.execute("DELETE FROM resumes WHERE id = ?", (resume_id,))
        conn.commit()

    if file_path:
        try:
            Path(file_path).unlink(missing_ok=True)
        except Exception:
            pass


def update_job_score(job_id: str, match_pct: int, missing_keywords: list[str]) -> None:
    """Update ATS scoring fields for a job."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE jobs SET match_pct = ?, missing_keywords = ? WHERE id = ?",
            (match_pct, json.dumps(missing_keywords or []), job_id)
        )
        conn.commit()


def insert_skills_gap(job_id: str, data: Dict[str, Any]) -> None:
    """Insert or update skills gap analysis for a job."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO skills_gaps (job_id, missing_skills, transferable_skills, suggestions)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(job_id) DO UPDATE SET
                   missing_skills = excluded.missing_skills,
                   transferable_skills = excluded.transferable_skills,
                   suggestions = excluded.suggestions""",
            (
                job_id,
                json.dumps(data.get("missing_skills", [])),
                json.dumps(data.get("transferable_skills", [])),
                json.dumps(data.get("suggestions", [])),
            )
        )
        conn.commit()


def get_skills_gap(job_id: str) -> Dict[str, Any] | None:
    """Return the stored skills gap analysis for a job."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM skills_gaps WHERE job_id = ?", (job_id,))
        row = cursor.fetchone()
        if not row:
            return None
        data = dict(row)
        for key in ("missing_skills", "transferable_skills", "suggestions"):
            raw_value = data.get(key, "[]")
            try:
                data[key] = json.loads(raw_value) if isinstance(raw_value, str) else raw_value or []
            except json.JSONDecodeError:
                data[key] = []
        return data


def insert_interview_prep(job_id: str, questions: list[dict]) -> None:
    """Insert or update interview prep questions for a job."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO interview_prep (job_id, questions)
               VALUES (?, ?)
               ON CONFLICT(job_id) DO UPDATE SET
                   questions = excluded.questions""",
            (job_id, json.dumps(questions or []))
        )
        conn.commit()


def get_interview_prep(job_id: str) -> Dict[str, Any] | None:
    """Return stored interview prep data for a job."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM interview_prep WHERE job_id = ?", (job_id,))
        row = cursor.fetchone()
        if not row:
            return None
        data = dict(row)
        raw_questions = data.get("questions", "[]")
        try:
            data["questions"] = json.loads(raw_questions) if isinstance(raw_questions, str) else raw_questions or []
        except json.JSONDecodeError:
            data["questions"] = []
        return data


def update_session_status(session_id: str, status: str) -> None:
    """
    Update session processing status.

    Args:
        session_id: Session identifier
        status: New status (e.g., "complete", "failed")
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE sessions SET status = ? WHERE session_id = ?",
            (status, session_id)
        )
        conn.commit()


def update_session_experience(session_id: str, experience: str | None) -> None:
    """Persist the optional user experience on a session."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE sessions SET experience = ? WHERE session_id = ?",
            (experience, session_id)
        )
        conn.commit()


def get_session_status(session_id: str) -> str:
    """
    Retrieve session processing status.

    Args:
        session_id: Session identifier

    Returns:
        Session status (e.g., "processing", "complete", "failed")
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT status FROM sessions WHERE session_id = ?", (session_id,))
        row = cursor.fetchone()
        return row[0] if row else "processing"


def upsert_session_alert_status(
    session_id: str,
    alert_email: str = None,
    alerts_enabled: bool = False,
    alert_message: str = None,
    preference_id: int = None
) -> None:
    """Insert or update alert registration metadata for an upload session."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        now = datetime.utcnow().isoformat()
        cursor.execute(
            """INSERT INTO session_alerts
               (session_id, alert_email, alerts_enabled, alert_message, preference_id, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(session_id) DO UPDATE SET
                   alert_email = excluded.alert_email,
                   alerts_enabled = excluded.alerts_enabled,
                   alert_message = excluded.alert_message,
                   preference_id = excluded.preference_id,
                   updated_at = excluded.updated_at""",
            (
                session_id,
                alert_email,
                1 if alerts_enabled else 0,
                alert_message,
                preference_id,
                now,
                now,
            )
        )
        conn.commit()


def get_session_alert_status(session_id: str) -> Dict[str, Any]:
    """Return alert registration metadata for an upload session."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM session_alerts WHERE session_id = ?", (session_id,))
        row = cursor.fetchone()
        if not row:
            return {
                "alerts_enabled": False,
                "alert_email": None,
                "alert_message": "Email alerts pending resume parsing",
            }
        data = dict(row)
        return {
            "alerts_enabled": bool(data.get("alerts_enabled")),
            "alert_email": data.get("alert_email"),
            "alert_message": data.get("alert_message") or "",
        }


def insert_alert_user(email: str, telegram_chat_id: str = None, name: str = None) -> int:
    """Insert a new alert user and return the user ID."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        created_at = datetime.utcnow().isoformat()
        cursor.execute(
            "INSERT INTO alert_users (email, telegram_chat_id, name, created_at) VALUES (?, ?, ?, ?)",
            (email, telegram_chat_id, name, created_at)
        )
        conn.commit()
        return cursor.lastrowid


def get_user_by_email(email: str) -> Dict[str, Any] | None:
    """Retrieve a single alert user by email."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM alert_users WHERE email = ?", (email,))
        row = cursor.fetchone()
        return dict(row) if row else None


def insert_alert_preference(
    user_id: int,
    role: str = None,
    location: str = None,
    keywords: str = None,
    alert_enabled: int = 1,
    expires_at: str = None
) -> int:
    """Insert a new alert preference and return the preference ID."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        created_at = datetime.utcnow().isoformat()
        cursor.execute(
            """INSERT INTO alert_preferences
               (user_id, role, location, keywords, is_active, alert_enabled, expires_at, created_at)
               VALUES (?, ?, ?, ?, 1, ?, ?, ?)""",
            (user_id, role, location, keywords, alert_enabled, expires_at, created_at)
        )
        conn.commit()
        return cursor.lastrowid


def upsert_alert_user(email: str, telegram_chat_id: str = None, name: str = None) -> int:
    """Create or reuse an alert user by email and return the user ID."""
    normalized_email = email.strip().lower()
    user = get_user_by_email(normalized_email)
    if user:
        if telegram_chat_id and telegram_chat_id != user.get("telegram_chat_id"):
            update_user_telegram_chat_id(normalized_email, telegram_chat_id)
        return user["id"]
    return insert_alert_user(normalized_email, telegram_chat_id, name)


def upsert_alert_preference_for_user(
    user_id: int,
    role: str,
    location: str,
    keywords: str = None,
    alert_enabled: int = 1,
    expires_at: str = None
) -> int:
    """Create or reactivate a preference for the same user, role, location, and keywords."""
    normalized_role = (role or "").strip()
    normalized_location = (location or "").strip()
    normalized_keywords = (keywords or "").strip() or None

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT id FROM alert_preferences
               WHERE user_id = ?
                 AND lower(coalesce(role, '')) = lower(?)
                 AND lower(coalesce(location, '')) = lower(?)
                 AND coalesce(keywords, '') = coalesce(?, '')""",
            (user_id, normalized_role, normalized_location, normalized_keywords)
        )
        row = cursor.fetchone()
        if row:
            cursor.execute(
                """UPDATE alert_preferences
                   SET is_active = 1, alert_enabled = ?, expires_at = ?
                   WHERE id = ?""",
                (alert_enabled, expires_at, row["id"])
            )
            conn.commit()
            return row["id"]

    return insert_alert_preference(
        user_id=user_id,
        role=normalized_role,
        location=normalized_location,
        keywords=normalized_keywords,
        alert_enabled=alert_enabled,
        expires_at=expires_at,
    )


def get_alert_preference_by_id(pref_id: int) -> Dict[str, Any] | None:
    """Retrieve a single alert preference by ID."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM alert_preferences WHERE id = ?", (pref_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def update_alert_preference(pref_id: int, role: str, location: str, keywords: str | None, expires_at: str) -> None:
    """Update an alert preference with new values and an expiry date."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """UPDATE alert_preferences
               SET role = ?, location = ?, keywords = ?, expires_at = ?
               WHERE id = ?""",
            (role, location, keywords, expires_at, pref_id)
        )
        conn.commit()


def update_user_telegram_chat_id(email: str, telegram_chat_id: str) -> bool:
    """Update a user's Telegram chat ID."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE alert_users SET telegram_chat_id = ? WHERE email = ?",
            (telegram_chat_id, email)
        )
        conn.commit()
        return cursor.rowcount > 0


def set_preferences_active_by_email(email: str, active: bool) -> int:
    """Enable or disable all preferences for a given user email."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """UPDATE alert_preferences
               SET is_active = ?
               WHERE user_id = (
                   SELECT id FROM alert_users WHERE email = ?
               )""",
            (1 if active else 0, email)
        )
        conn.commit()
        return cursor.rowcount


def delete_alert_preference(pref_id: int) -> int:
    """Delete an alert preference by ID and return the associated user_id."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM alert_preferences WHERE id = ?", (pref_id,))
        row = cursor.fetchone()
        if not row:
            return 0
        user_id = row["user_id"]
        cursor.execute("DELETE FROM alert_preferences WHERE id = ?", (pref_id,))
        conn.commit()
        return user_id


def delete_alert_user_by_email(email: str) -> int:
    """Delete an alert user by email and return the number of rows removed."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM alert_users WHERE email = ?", (email,))
        conn.commit()
        return cursor.rowcount


def delete_alert_user_by_id(user_id: int) -> int:
    """Delete an alert user by ID and return the number of rows removed."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM alert_users WHERE id = ?", (user_id,))
        conn.commit()
        return cursor.rowcount


def get_user_preferences_count(user_id: int) -> int:
    """Return the number of preferences for a given user."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) AS count FROM alert_preferences WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        return row["count"] if row else 0


def get_notification_history_by_email(email: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Return the latest notification history rows for a user by email."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT nh.sent_at, nh.channel, nh.status, nh.error_msg,
                       aj.title AS job_title, aj.company AS company
               FROM notification_history nh
               JOIN alert_jobs aj ON nh.alert_job_id = aj.id
               JOIN alert_users au ON nh.user_id = au.id
               WHERE au.email = ?
               ORDER BY nh.sent_at DESC
               LIMIT ?""",
            (email, limit)
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def get_active_alert_users() -> List[Dict[str, Any]]:
    """Return users with at least one active alert preference."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        current_time = datetime.utcnow().isoformat()
        cursor.execute(
            """SELECT au.id, au.email, au.telegram_chat_id, au.created_at,
                      COUNT(ap.id) AS active_preferences,
                      MAX(ap.created_at) AS latest_preference_at
               FROM alert_users au
               JOIN alert_preferences ap ON ap.user_id = au.id
               WHERE au.is_active = 1
                 AND ap.is_active = 1
                 AND ap.alert_enabled = 1
                 AND (ap.expires_at IS NULL OR ap.expires_at > ?)
               GROUP BY au.id, au.email, au.telegram_chat_id, au.created_at
               ORDER BY latest_preference_at DESC""",
            (current_time,)
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def get_active_preferences() -> List[Dict[str, Any]]:
    """Return active preferences joined with active user information."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        current_time = datetime.utcnow().isoformat()
        cursor.execute(
            """SELECT ap.*, au.email, au.telegram_chat_id, au.name AS user_name,
                       au.is_active AS user_is_active, au.created_at AS user_created_at
               FROM alert_preferences ap
               JOIN alert_users au ON ap.user_id = au.id
               WHERE ap.is_active = 1
                 AND ap.alert_enabled = 1
                 AND au.is_active = 1
                 AND (ap.expires_at IS NULL OR ap.expires_at > ?)
               ORDER BY ap.created_at DESC""",
            (current_time,)
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def upsert_alert_job(pref_id: int, job_hash: str, job_dict: Dict[str, Any]) -> int | None:
    """Insert or update an alert job. Returns the new job ID when inserted, otherwise None."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        now = datetime.utcnow().isoformat()
        cursor.execute(
            "SELECT id FROM alert_jobs WHERE preference_id = ? AND job_hash = ?",
            (pref_id, job_hash)
        )
        row = cursor.fetchone()

        status = job_dict.get("status", "active")
        expires_at = job_dict.get("expires_at")
        job_id_external = job_dict.get("job_id_external")
        title = job_dict.get("title")
        company = job_dict.get("company")
        location = job_dict.get("location")
        apply_url = job_dict.get("apply_url")
        description_snippet = job_dict.get("description_snippet")

        if row:
            cursor.execute(
                """UPDATE alert_jobs
                   SET job_id_external = ?, title = ?, company = ?, location = ?,
                       apply_url = ?, description_snippet = ?, status = ?, expires_at = ?,
                       last_seen_at = ?
                   WHERE id = ?""",
                (
                    job_id_external,
                    title,
                    company,
                    location,
                    apply_url,
                    description_snippet,
                    status,
                    expires_at,
                    now,
                    row["id"]
                )
            )
            conn.commit()
            return None

        cursor.execute(
            """INSERT INTO alert_jobs
               (preference_id, job_hash, job_id_external, title, company, location,
                apply_url, description_snippet, status, expires_at, first_seen_at, last_seen_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                pref_id,
                job_hash,
                job_id_external,
                title,
                company,
                location,
                apply_url,
                description_snippet,
                status,
                expires_at,
                now,
                now
            )
        )
        alert_job_id = cursor.lastrowid
        conn.commit()
        return alert_job_id


def reset_preference_expiry(pref_id: int) -> None:
    """Reset the expiry date on an alert preference."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE alert_preferences SET expires_at = NULL WHERE id = ?",
            (pref_id,)
        )
        conn.commit()


def record_notification(user_id: int, alert_job_id: int, channel: str, status: str, error_msg: str = None) -> None:
    """Record a notification attempt in history."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        sent_at = datetime.utcnow().isoformat()
        cursor.execute(
            """INSERT INTO notification_history
               (user_id, alert_job_id, channel, status, error_msg, sent_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, alert_job_id, channel, status, error_msg, sent_at)
        )
        conn.commit()


def log_scheduler_run(users_processed: int, new_jobs_found: int, notifications_sent: int, status: str, error_msg: str = None) -> None:
    """Log a scheduler run in the database."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        run_at = datetime.utcnow().isoformat()
        cursor.execute(
            """INSERT INTO scheduler_logs
               (run_at, users_processed, new_jobs_found, notifications_sent, status, error_msg)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (run_at, users_processed, new_jobs_found, notifications_sent, status, error_msg)
        )
        conn.commit()
