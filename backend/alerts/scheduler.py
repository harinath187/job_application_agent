"""
Scheduler setup for alert jobs and cleanup tasks.
"""
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from alerts.cleanup import run_cleanup
from alerts.job_checker import run_alert_cycle

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

scheduler = AsyncIOScheduler()


def start_scheduler() -> None:
    """Start the APScheduler instance and add recurring jobs."""
    scheduler.add_job(
        run_alert_cycle,
        trigger="interval",
        hours=2,
        id="job_alert_cycle",
        misfire_grace_time=300,
        replace_existing=True,
    )
    scheduler.add_job(
        run_cleanup,
        trigger="cron",
        hour=2,
        minute=0,
        id="daily_cleanup",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Scheduler started")


def stop_scheduler() -> None:
    """Shutdown the APScheduler instance."""
    scheduler.shutdown(wait=False)
    logger.info("Scheduler stopped")
