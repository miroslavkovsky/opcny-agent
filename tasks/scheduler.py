"""
Agent Scheduler — riadi kedy sa ktorý agent spustí.

Používa APScheduler s AsyncIOScheduler pre non-blocking execution.
Cron expressions sa načítavajú z config/settings.
"""

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from agents import ContentReviewAgent, SocialMediaAgent, AnalyticsAgent
from config.settings import settings

logger = logging.getLogger("scheduler")


def parse_cron(expr: str) -> dict:
    """Parsuje cron expression '*/30 * * * *' na APScheduler kwargs."""
    parts = expr.split()
    if len(parts) != 5:
        raise ValueError(f"Nevalidný cron expression: {expr}")
    return {
        "minute": parts[0],
        "hour": parts[1],
        "day": parts[2],
        "month": parts[3],
        "day_of_week": parts[4],
    }


class AgentScheduler:
    """Spravuje a koordinuje beh všetkých agentov."""

    def __init__(self):
        self.scheduler = AsyncIOScheduler(timezone="Europe/Bratislava")

        # Inicializuj agentov
        self.content_review = ContentReviewAgent()
        self.social_media = SocialMediaAgent()
        self.analytics = AnalyticsAgent()

    async def start(self):
        """Zaregistruj joby a spusti scheduler."""

        # --- Content Review Agent ---
        # Kontrola nových článkov každých 30 minút
        self.scheduler.add_job(
            self.content_review.run,
            CronTrigger(**parse_cron(settings.review_check_cron)),
            kwargs={"action": "check_pending"},
            id="content_review_check",
            name="Content Review — kontrola pending obsahu",
            misfire_grace_time=300,
        )

        # --- Social Media Agent ---
        # Publikovanie schválených postov podľa plánu
        self.scheduler.add_job(
            self.social_media.run,
            CronTrigger(**parse_cron(settings.content_post_cron)),
            kwargs={"action": "publish_scheduled"},
            id="social_media_publish",
            name="Social Media — publikácia schválených postov",
            misfire_grace_time=600,
        )

        # --- Analytics Agent ---
        # Denný report
        self.scheduler.add_job(
            self.analytics.run,
            CronTrigger(**parse_cron(settings.analytics_daily_cron)),
            kwargs={"action": "daily_report"},
            id="analytics_daily",
            name="Analytics — denný report",
            misfire_grace_time=3600,
        )

        # Týždenný report (pondelok ráno)
        self.scheduler.add_job(
            self.analytics.run,
            CronTrigger(**parse_cron(settings.analytics_weekly_cron)),
            kwargs={"action": "weekly_report"},
            id="analytics_weekly",
            name="Analytics — týždenný report",
            misfire_grace_time=3600,
        )

        self.scheduler.start()
        logger.info(
            f"Scheduler spustený s {len(self.scheduler.get_jobs())} jobmi"
        )

        # Vypíš registrované joby
        for job in self.scheduler.get_jobs():
            logger.info(f"  → {job.name} | next run: {job.next_run_time}")

    async def stop(self):
        """Zastaví scheduler."""
        self.scheduler.shutdown(wait=True)
        logger.info("Scheduler zastavený")

    def get_status(self) -> list[dict]:
        """Vráti stav všetkých jobov (pre admin API)."""
        return [
            {
                "id": job.id,
                "name": job.name,
                "next_run": str(job.next_run_time) if job.next_run_time else None,
                "pending": job.pending,
            }
            for job in self.scheduler.get_jobs()
        ]
