"""
SQLite database initialization and operations for job application sessions.
"""
import sqlite3
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any


DB_PATH = Path(__file__).parent.parent / "data" / "jobs.db"


def init_db() -> None:
    """
    Initialize SQLite database with sessions and jobs tables if they don't exist.
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        
        # Create sessions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
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
                resume_path TEXT,
                cover_letter_path TEXT,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(session_id)
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
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        created_at = datetime.utcnow().isoformat()
        cursor.execute(
            "INSERT INTO sessions (session_id, status, created_at) VALUES (?, ?, ?)",
            (session_id, status, created_at)
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
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        created_at = datetime.utcnow().isoformat()
        cursor.execute(
            """INSERT INTO jobs 
               (session_id, title, company, location, job_url, description, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                session_id,
                job.get("title", ""),
                job.get("company", ""),
                job.get("location", ""),
                job.get("job_url", ""),
                job.get("description", ""),
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
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM jobs WHERE session_id = ? ORDER BY created_at DESC", (session_id,))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]


def get_job_by_id(job_id: int) -> Dict[str, Any] | None:
    """
    Retrieve a specific job by its ID.
    
    Args:
        job_id: Job identifier
    
    Returns:
        Job dictionary or None if not found
    """
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def update_job_status(job_id: int, status: str, resume_path: str = None, cover_letter_path: str = None) -> None:
    """
    Update job status and file paths.
    
    Args:
        job_id: Job ID to update
        status: New status (e.g., "tailored", "complete", "failed")
        resume_path: Optional path to tailored resume
        cover_letter_path: Optional path to generated cover letter
    """
    with sqlite3.connect(DB_PATH) as conn:
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
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE sessions SET status = ? WHERE session_id = ?",
            (status, session_id)
        )
        conn.commit()
