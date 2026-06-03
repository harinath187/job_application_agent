"""
Cleanup tasks for alert scheduler data retention.
"""
import logging

from utils.db import get_db_connection

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def run_cleanup() -> None:
    """Run cleanup queries for alert scheduler tables."""
    counts = {
        "deleted_stale_preferences": 0,
        "deleted_expired_preferences": 0,
        "deleted_orphaned_users": 0,
        "deleted_removed_jobs": 0,
        "deleted_old_notifications": 0,
    }

    conn = get_db_connection()
    try:
        cursor = conn.cursor()

        cursor.execute(
            """
            DELETE FROM alert_preferences
            WHERE alert_enabled = 0
              AND created_at < datetime('now', '-1 day')
            """
        )
        counts["deleted_stale_preferences"] = cursor.rowcount

        cursor.execute(
            """
            DELETE FROM alert_preferences
            WHERE expires_at IS NOT NULL
              AND expires_at < datetime('now')
            """
        )
        counts["deleted_expired_preferences"] = cursor.rowcount

        cursor.execute(
            """
            DELETE FROM alert_users
            WHERE id NOT IN (
                SELECT DISTINCT user_id FROM alert_preferences
            )
            """
        )
        counts["deleted_orphaned_users"] = cursor.rowcount

        cursor.execute(
            """
            DELETE FROM alert_jobs
            WHERE status = 'removed'
              AND expires_at < datetime('now')
            """
        )
        counts["deleted_removed_jobs"] = cursor.rowcount

        cursor.execute(
            """
            DELETE FROM notification_history
            WHERE expires_at < datetime('now')
            """
        )
        counts["deleted_old_notifications"] = cursor.rowcount

        conn.commit()
        logger.info("Cleanup completed: %s", counts)
    except Exception as exc:
        conn.rollback()
        logger.error("Cleanup failed and rolled back: %s", exc)
    finally:
        conn.close()
