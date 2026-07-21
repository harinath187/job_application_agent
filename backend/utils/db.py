"""
SQLite database initialization and operations for job application sessions.
"""
import sqlite3
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any


DB_PATH = Path(__file__).parent.parent / "data" / "jobs.db"


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
                projects TEXT,
                certifications TEXT,
                inferred_roles TEXT,
                validation_stats TEXT,
                parsed_resume_data TEXT,
                created_at TEXT NOT NULL
            )
        """)
        cursor.execute("PRAGMA table_info(sessions)")
        session_columns = {row[1] for row in cursor.fetchall()}
        if "experience" not in session_columns:
            cursor.execute("ALTER TABLE sessions ADD COLUMN experience TEXT")
        for column in ("projects", "certifications", "inferred_roles"):
            if column not in session_columns:
                try:
                    cursor.execute(f"ALTER TABLE sessions ADD COLUMN {column} TEXT")
                except Exception:
                    pass
        if "validation_stats" not in session_columns:
            try:
                cursor.execute("ALTER TABLE sessions ADD COLUMN validation_stats TEXT")
            except Exception:
                pass
        if "parsed_resume_data" not in session_columns:
            try:
                cursor.execute("ALTER TABLE sessions ADD COLUMN parsed_resume_data TEXT")
            except Exception:
                pass

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
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                title TEXT NOT NULL,
                company TEXT NOT NULL,
                location TEXT,
                job_url TEXT,
                description TEXT,
                source_city TEXT,
                source_role TEXT,
                role_confidence REAL,
                relevance_score REAL,
                final_score REAL,
                experience_match_score REAL,
                seniority_bucket TEXT,
                skill_match_percentage REAL,
                matched_skills TEXT,
                missing_skills TEXT,
                resume_path TEXT,
                cover_letter_path TEXT,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id) ON DELETE CASCADE
            )
        """)
        cursor.execute("PRAGMA table_info(jobs)")
        job_columns = {row[1] for row in cursor.fetchall()}
        if "source_city" not in job_columns:
            try:
                cursor.execute("ALTER TABLE jobs ADD COLUMN source_city TEXT")
            except Exception:
                pass
        if "source_role" not in job_columns:
            try:
                cursor.execute("ALTER TABLE jobs ADD COLUMN source_role TEXT")
            except Exception:
                pass
        if "role_confidence" not in job_columns:
            try:
                cursor.execute("ALTER TABLE jobs ADD COLUMN role_confidence REAL")
            except Exception:
                pass
        for column, ddl in (
            ("relevance_score", "ALTER TABLE jobs ADD COLUMN relevance_score REAL"),
            ("final_score", "ALTER TABLE jobs ADD COLUMN final_score REAL"),
            ("experience_match_score", "ALTER TABLE jobs ADD COLUMN experience_match_score REAL"),
            ("seniority_bucket", "ALTER TABLE jobs ADD COLUMN seniority_bucket TEXT"),
            ("skill_match_percentage", "ALTER TABLE jobs ADD COLUMN skill_match_percentage REAL"),
            ("matched_skills", "ALTER TABLE jobs ADD COLUMN matched_skills TEXT"),
            ("missing_skills", "ALTER TABLE jobs ADD COLUMN missing_skills TEXT"),
        ):
            if column not in job_columns:
                try:
                    cursor.execute(ddl)
                except Exception:
                    pass

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


def _json_encode_list(values: list[str] | None) -> str | None:
    if values is None:
        return None
    return json.dumps([str(value) for value in values if str(value).strip()])


def _json_encode(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(value)


def _json_decode(value: str | None) -> Any:
    if not value:
        return None
    try:
        return json.loads(value)
    except Exception:
        return None


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
            "INSERT INTO sessions (session_id, status, projects, certifications, inferred_roles, validation_stats, parsed_resume_data, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (session_id, status, _json_encode_list([]), _json_encode_list([]), _json_encode_list([]), _json_encode({}), _json_encode({}), created_at)
        )
        conn.commit()


def insert_search_history(session_id: str, resume_name: str, resume_path: str, role: str, location: str, experience: str | None = None) -> None:
    """Persist the criteria used for a search session."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        created_at = datetime.utcnow().isoformat()
        normalized_role = role or ""
        normalized_location = location or ""
        cursor.execute(
            """INSERT INTO search_history
               (session_id, resume_name, resume_path, role, location, created_at)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(session_id) DO UPDATE SET
                   resume_name = excluded.resume_name,
                   resume_path = excluded.resume_path,
                   role = excluded.role,
                   location = excluded.location""",
            (session_id, resume_name, resume_path, normalized_role, normalized_location, created_at)
        )
        cursor.execute(
            "UPDATE sessions SET experience = ? WHERE session_id = ?",
            (experience, session_id)
        )
        conn.commit()


def insert_job(session_id: str, job: Dict[str, Any]) -> int:
    """
    Insert a job into the database.

    Args:
        session_id: Session identifier
        job: Job dictionary with keys: title, company, location, description, job_url

    Returns:
        The job ID of the inserted record
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        created_at = datetime.utcnow().isoformat()
        cursor.execute(
            """INSERT INTO jobs
               (session_id, title, company, location, job_url, description, source_city, source_role, role_confidence, relevance_score, final_score, experience_match_score, seniority_bucket, skill_match_percentage, matched_skills, missing_skills, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                session_id,
                job.get("title", ""),
                job.get("company", ""),
                job.get("location", ""),
                job.get("job_url", ""),
                job.get("description", ""),
                _json_encode(job.get("source_city") if isinstance(job.get("source_city"), list) else ([job.get("source_city")] if job.get("source_city") else [])),
                _json_encode(job.get("source_role") if isinstance(job.get("source_role"), list) else ([job.get("source_role")] if job.get("source_role") else [])),
                float(job.get("role_confidence")) if job.get("role_confidence") is not None else None,
                float(job.get("relevance_score")) if job.get("relevance_score") is not None else None,
                float(job.get("final_score")) if job.get("final_score") is not None else None,
                float(job.get("experience_match_score")) if job.get("experience_match_score") is not None else None,
                job.get("seniority_bucket"),
                float(job.get("skill_match_percentage")) if job.get("skill_match_percentage") is not None else None,
                _json_encode(job.get("matched_skills") or []),
                _json_encode(job.get("missing_skills") or []),
                "pending",
                created_at
            )
        )
        conn.commit()
        return cursor.lastrowid


def get_jobs_by_session(session_id: str) -> List[Dict[str, Any]]:
    """
    Retrieve all jobs for a given session.

    Args:
        session_id: Session identifier

    Returns:
        List of job dictionaries with all fields
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM jobs WHERE session_id = ? ORDER BY COALESCE(final_score, 0) DESC, created_at DESC", (session_id,))
        rows = cursor.fetchall()
        jobs = []
        for row in rows:
            job = dict(row)
            job["source_city"] = _json_decode(job.get("source_city")) or []
            job["source_role"] = _json_decode(job.get("source_role")) or []
            job["matched_skills"] = _json_decode(job.get("matched_skills")) or []
            job["missing_skills"] = _json_decode(job.get("missing_skills")) or []
            role_confidence = job.get("role_confidence")
            job["role_confidence"] = float(role_confidence) if role_confidence is not None else 0.0
            for key in ("relevance_score", "final_score", "experience_match_score", "skill_match_percentage"):
                value = job.get(key)
                job[key] = float(value) if value is not None else 0.0
            jobs.append(job)
        return jobs


def update_search_history_criteria(session_id: str, role: str | None = None, location: str | None = None) -> None:
    """Backfill the role/location shown in Search History once the resume parser infers them.

    Only overwrites a field when the caller supplies a non-empty value and the
    stored value is currently blank, so an explicit user-provided role/location
    is never clobbered.
    """
    if not role and not location:
        return
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if role:
            cursor.execute(
                "UPDATE search_history SET role = ? WHERE session_id = ? AND (role IS NULL OR role = '')",
                (role, session_id)
            )
        if location:
            cursor.execute(
                "UPDATE search_history SET location = ? WHERE session_id = ? AND (location IS NULL OR location = '')",
                (location, session_id)
            )
        conn.commit()


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
        return [dict(row) for row in rows]


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


def get_job_by_id(job_id: int) -> Dict[str, Any] | None:
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
        if not row:
            return None
        job = dict(row)
        job["source_city"] = _json_decode(job.get("source_city")) or []
        job["source_role"] = _json_decode(job.get("source_role")) or []
        job["matched_skills"] = _json_decode(job.get("matched_skills")) or []
        job["missing_skills"] = _json_decode(job.get("missing_skills")) or []
        role_confidence = job.get("role_confidence")
        job["role_confidence"] = float(role_confidence) if role_confidence is not None else 0.0
        for key in ("relevance_score", "final_score", "experience_match_score", "skill_match_percentage"):
            value = job.get(key)
            job[key] = float(value) if value is not None else 0.0
        return job


def update_job_status(job_id: int, status: str, resume_path: str = None, cover_letter_path: str = None) -> None:
    """
    Update job status and file paths.

    Args:
        job_id: Job ID to update
        status: New status (e.g., "tailored", "complete", "failed")
        resume_path: Optional path to tailored resume
        cover_letter_path: Optional path to generated cover letter
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """UPDATE jobs 
               SET status = ?, resume_path = ?, cover_letter_path = ?
               WHERE id = ?""",
            (status, resume_path, cover_letter_path, job_id)
        )
        conn.commit()


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


def set_session_status(session_id: str, status: str) -> None:
    update_session_status(session_id, status)


def update_session_profile_data(
    session_id: str,
    projects: list[str] | None = None,
    certifications: list[str] | None = None,
    inferred_roles: list[str] | None = None,
) -> None:
    """Persist extracted profile lists for a session."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """UPDATE sessions
               SET projects = COALESCE(?, projects),
                   certifications = COALESCE(?, certifications),
                   inferred_roles = COALESCE(?, inferred_roles)
               WHERE session_id = ?""",
            (_json_encode_list(projects), _json_encode_list(certifications), _json_encode_list(inferred_roles), session_id),
        )
        conn.commit()


def update_session_validation_stats(session_id: str, validation_stats: Dict[str, Any]) -> None:
    """Persist validation counts for a session."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE sessions SET validation_stats = ? WHERE session_id = ?",
            (_json_encode(validation_stats), session_id),
        )
        conn.commit()


def update_session_parsed_resume_data(session_id: str, parsed_data: Dict[str, Any]) -> None:
    """Persist the parsed resume payload so the pipeline can resume without reparsing."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE sessions SET parsed_resume_data = ? WHERE session_id = ?",
            (_json_encode(parsed_data), session_id),
        )
        conn.commit()


def get_session_data(session_id: str) -> Dict[str, Any] | None:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))
        row = cursor.fetchone()
        if not row:
            return None
        data = dict(row)
        data["projects"] = _json_decode(data.get("projects")) or []
        data["certifications"] = _json_decode(data.get("certifications")) or []
        data["inferred_roles"] = _json_decode(data.get("inferred_roles")) or []
        data["validation_stats"] = _json_decode(data.get("validation_stats")) or {}
        data["parsed_resume_data"] = _json_decode(data.get("parsed_resume_data")) or {}
        return data


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


def is_alert_email_active(email: str) -> bool:
    """Return whether an email currently has at least one active, enabled alert preference."""
    if not email:
        return False
    with get_db_connection() as conn:
        cursor = conn.cursor()
        current_time = datetime.utcnow().isoformat()
        cursor.execute(
            """SELECT COUNT(*) AS count
               FROM alert_preferences ap
               JOIN alert_users au ON ap.user_id = au.id
               WHERE au.email = ?
                 AND au.is_active = 1
                 AND ap.is_active = 1
                 AND ap.alert_enabled = 1
                 AND (ap.expires_at IS NULL OR ap.expires_at > ?)""",
            (email, current_time)
        )
        row = cursor.fetchone()
        return bool(row and row["count"] > 0)


def get_session_alert_status(session_id: str) -> Dict[str, Any]:
    """Return alert registration metadata for an upload session.

    The `alerts_enabled` flag reflects the *current* state of the user's alert
    preferences (looked up live by email), not the snapshot taken when the
    session first registered for alerts, so disabling/unsubscribing an email
    on the Manage Alerts page is reflected immediately here too.
    """
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
        alert_email = data.get("alert_email")
        was_registered = bool(data.get("alerts_enabled"))
        currently_active = is_alert_email_active(alert_email)
        alerts_enabled = was_registered and currently_active
        alert_message = data.get("alert_message") or ""
        if was_registered and not currently_active:
            alert_message = f"Email alerts have been disabled for {alert_email}."
        return {
            "alerts_enabled": alerts_enabled,
            "alert_disabled_by_user": was_registered and not currently_active,
            "alert_email": alert_email,
            "alert_message": alert_message,
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
