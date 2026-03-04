"""
AnalyticsAgent — sťahuje dáta z Google Analytics 4 a generuje insights.

Workflow:
1. Pripojí sa na GA4 Data API
2. Stiahne metriky za zadané obdobie
3. Uloží snapshot do databázy
4. Generuje AI insights cez Claude API
5. Posiela report Mirovi
"""

import json
from datetime import date, timedelta
from typing import Any

from agents.base import BaseAgent
from models import async_session, AnalyticsSnapshot
from services.claude_service import ClaudeService
from services.ga4_service import GA4Service
from utils.notifications import notify_miro


class AnalyticsAgent(BaseAgent):
    """Agent zodpovedný za sledovanie a vyhodnocovanie návštevnosti."""

    def __init__(self):
        super().__init__()
        self.ga4 = GA4Service()
        self.claude = ClaudeService()

    async def execute(self, **kwargs) -> dict[str, Any]:
        action = kwargs.get("action", "daily_report")

        if action == "daily_report":
            return await self._daily_report()
        elif action == "weekly_report":
            return await self._weekly_report()
        elif action == "custom_report":
            return await self._custom_report(
                start_date=kwargs["start_date"],
                end_date=kwargs["end_date"],
            )
        else:
            return {"status": "skipped", "details": {"reason": f"Unknown action: {action}"}}

    async def _daily_report(self) -> dict[str, Any]:
        """Denný report — včerajšie metriky."""
        yesterday = date.today() - timedelta(days=1)
        return await self._generate_report(
            period_start=yesterday,
            period_end=yesterday,
            period_type="daily",
        )

    async def _weekly_report(self) -> dict[str, Any]:
        """Týždenný report — posledných 7 dní s porovnaním."""
        end = date.today() - timedelta(days=1)
        start = end - timedelta(days=6)
        return await self._generate_report(
            period_start=start,
            period_end=end,
            period_type="weekly",
        )

    async def _custom_report(self, start_date: str, end_date: str) -> dict[str, Any]:
        """Custom report pre ľubovoľné obdobie."""
        return await self._generate_report(
            period_start=date.fromisoformat(start_date),
            period_end=date.fromisoformat(end_date),
            period_type="custom",
        )

    async def _generate_report(
        self,
        period_start: date,
        period_end: date,
        period_type: str,
    ) -> dict[str, Any]:
        """Stiahne dáta z GA4, vygeneruje insights, uloží a notifikuje."""

        # 1. Stiahni metriky z GA4
        metrics = await self.ga4.get_metrics(
            start_date=period_start.isoformat(),
            end_date=period_end.isoformat(),
        )

        # 2. Stiahni top stránky
        top_pages = await self.ga4.get_top_pages(
            start_date=period_start.isoformat(),
            end_date=period_end.isoformat(),
            limit=10,
        )

        # 3. Stiahni zdroje návštevnosti
        traffic_sources = await self.ga4.get_traffic_sources(
            start_date=period_start.isoformat(),
            end_date=period_end.isoformat(),
        )

        full_metrics = {
            "overview": metrics,
            "top_pages": top_pages,
            "traffic_sources": traffic_sources,
        }

        # 4. Generuj AI insights
        insights = await self._generate_insights(full_metrics, period_type)

        # 5. Ulož snapshot do DB
        async with async_session() as session:
            snapshot = AnalyticsSnapshot(
                period_start=period_start,
                period_end=period_end,
                period_type=period_type,
                metrics=full_metrics,
                insights=insights,
            )
            session.add(snapshot)
            await session.commit()

        # 6. Notifikuj Mira
        report_summary = self._format_report_summary(full_metrics, insights, period_type)
        await notify_miro(
            title=f"Analytics Report — {period_type}",
            message=report_summary,
            level="info",
        )

        return {
            "status": "success",
            "details": {
                "period": f"{period_start} → {period_end}",
                "type": period_type,
                "metrics_summary": metrics,
            },
        }

    async def _generate_insights(self, metrics: dict, period_type: str) -> str:
        """Nechá Claude analyzovať metriky a poskytnúť actionable insights."""
        prompt = (
            f"Analyzuj tieto Google Analytics dáta pre OptionsSimulator.com "
            f"({period_type} report):\n\n"
            f"```json\n{json.dumps(metrics, indent=2, default=str)}\n```\n\n"
            f"Prosím poskytni:\n"
            f"1. Hlavné trendy (čo rastie/klesá)\n"
            f"2. Najlepšie performujúci obsah a prečo\n"
            f"3. Zdroje návštevnosti — odkiaľ prichádzajú návštevníci\n"
            f"4. 2-3 konkrétne odporúčania na zlepšenie\n"
            f"5. Anomálie alebo neočakávané zmeny\n\n"
            f"Buď stručný a zamerianý na actionable insights pre solo developera."
        )

        return await self.claude.generate(
            system_prompt="Si expert na web analytics a SEO pre fintech/edukačné projekty.",
            user_message=prompt,
        )

    def _format_report_summary(
        self, metrics: dict, insights: str, period_type: str
    ) -> str:
        """Formátuje report pre Discord/Telegram notifikáciu."""
        overview = metrics.get("overview", {})

        summary = (
            f"📊 **{period_type.upper()} Report**\n\n"
            f"👥 Sessions: {overview.get('sessions', 'N/A')}\n"
            f"👀 Pageviews: {overview.get('pageviews', 'N/A')}\n"
            f"📈 Users: {overview.get('active_users', 'N/A')}\n"
            f"⏱ Avg Duration: {overview.get('avg_session_duration', 'N/A')}s\n"
            f"🔙 Bounce Rate: {overview.get('bounce_rate', 'N/A')}%\n\n"
            f"**Top 3 stránky:**\n"
        )

        top_pages = metrics.get("top_pages", [])[:3]
        for i, page in enumerate(top_pages, 1):
            summary += f"{i}. {page.get('page_path', '?')} — {page.get('pageviews', '?')} views\n"

        summary += f"\n**Insights:**\n{insights[:500]}..."

        return summary
