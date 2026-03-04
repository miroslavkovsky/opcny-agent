"""
Google Analytics 4 service — sťahovanie metrík cez GA4 Data API.

Vyžaduje:
- GA4 property ID
- Service account s prístupom k GA4 property
- Credentials JSON (base64-encoded v env premennej)

Setup:
1. Google Cloud Console → Create Service Account
2. GA4 Admin → Property Access Management → pridaj service account email
3. Stiahni JSON key → base64 encode → ulož ako GA4_CREDENTIALS_JSON
"""

import base64
import json
import logging
from typing import Any

from config.settings import settings

logger = logging.getLogger("service.ga4")


class GA4Service:
    """Google Analytics 4 Data API wrapper."""

    def __init__(self):
        self.property_id = settings.ga4_property_id
        self._client = None

    def _get_client(self):
        """Lazy init GA4 klienta."""
        if self._client is None:
            try:
                from google.analytics.data_v1beta import BetaAnalyticsDataAsyncClient
                from google.oauth2 import service_account

                # Dekóduj credentials z base64
                if not settings.ga4_credentials_json:
                    raise ValueError("GA4_CREDENTIALS_JSON nie je nastavený")

                creds_json = base64.b64decode(settings.ga4_credentials_json)
                creds_dict = json.loads(creds_json)

                credentials = service_account.Credentials.from_service_account_info(
                    creds_dict,
                    scopes=["https://www.googleapis.com/auth/analytics.readonly"],
                )

                self._client = BetaAnalyticsDataAsyncClient(credentials=credentials)

            except ImportError:
                logger.error("google-analytics-data nie je nainštalovaný")
                raise

        return self._client

    async def get_metrics(
        self,
        start_date: str,
        end_date: str,
    ) -> dict[str, Any]:
        """
        Získa základné metriky za obdobie.

        Returns:
            {sessions, pageviews, active_users, avg_session_duration, bounce_rate, ...}
        """
        if not self.property_id:
            logger.warning("GA4 property ID nie je nastavený")
            return {"error": "no_property_id"}

        try:
            from google.analytics.data_v1beta import types

            client = self._get_client()

            request = types.RunReportRequest(
                property=self.property_id,
                date_ranges=[types.DateRange(start_date=start_date, end_date=end_date)],
                metrics=[
                    types.Metric(name="sessions"),
                    types.Metric(name="screenPageViews"),
                    types.Metric(name="activeUsers"),
                    types.Metric(name="newUsers"),
                    types.Metric(name="averageSessionDuration"),
                    types.Metric(name="bounceRate"),
                    types.Metric(name="engagedSessions"),
                ],
            )

            response = await client.run_report(request)

            if not response.rows:
                return {}

            row = response.rows[0]
            metric_names = [
                "sessions", "pageviews", "active_users", "new_users",
                "avg_session_duration", "bounce_rate", "engaged_sessions",
            ]

            return {
                name: self._parse_value(val.value)
                for name, val in zip(metric_names, row.metric_values)
            }

        except Exception as e:
            logger.error(f"GA4 metrics error: {e}")
            return {"error": str(e)}

    async def get_top_pages(
        self,
        start_date: str,
        end_date: str,
        limit: int = 10,
    ) -> list[dict]:
        """Získa najnavštevovanejšie stránky."""
        try:
            from google.analytics.data_v1beta import types

            client = self._get_client()

            request = types.RunReportRequest(
                property=self.property_id,
                date_ranges=[types.DateRange(start_date=start_date, end_date=end_date)],
                dimensions=[types.Dimension(name="pagePath")],
                metrics=[
                    types.Metric(name="screenPageViews"),
                    types.Metric(name="activeUsers"),
                    types.Metric(name="averageSessionDuration"),
                ],
                order_bys=[
                    types.OrderBy(
                        metric=types.OrderBy.MetricOrderBy(metric_name="screenPageViews"),
                        desc=True,
                    )
                ],
                limit=limit,
            )

            response = await client.run_report(request)

            return [
                {
                    "page_path": row.dimension_values[0].value,
                    "pageviews": self._parse_value(row.metric_values[0].value),
                    "users": self._parse_value(row.metric_values[1].value),
                    "avg_duration": self._parse_value(row.metric_values[2].value),
                }
                for row in response.rows
            ]

        except Exception as e:
            logger.error(f"GA4 top pages error: {e}")
            return []

    async def get_traffic_sources(
        self,
        start_date: str,
        end_date: str,
    ) -> list[dict]:
        """Získa zdroje návštevnosti."""
        try:
            from google.analytics.data_v1beta import types

            client = self._get_client()

            request = types.RunReportRequest(
                property=self.property_id,
                date_ranges=[types.DateRange(start_date=start_date, end_date=end_date)],
                dimensions=[
                    types.Dimension(name="sessionSource"),
                    types.Dimension(name="sessionMedium"),
                ],
                metrics=[
                    types.Metric(name="sessions"),
                    types.Metric(name="activeUsers"),
                ],
                order_bys=[
                    types.OrderBy(
                        metric=types.OrderBy.MetricOrderBy(metric_name="sessions"),
                        desc=True,
                    )
                ],
                limit=15,
            )

            response = await client.run_report(request)

            return [
                {
                    "source": row.dimension_values[0].value,
                    "medium": row.dimension_values[1].value,
                    "sessions": self._parse_value(row.metric_values[0].value),
                    "users": self._parse_value(row.metric_values[1].value),
                }
                for row in response.rows
            ]

        except Exception as e:
            logger.error(f"GA4 traffic sources error: {e}")
            return []

    @staticmethod
    def _parse_value(value: str) -> int | float:
        """Parsuje GA4 hodnotu na číslo."""
        try:
            if "." in value:
                return round(float(value), 2)
            return int(value)
        except ValueError:
            return 0
