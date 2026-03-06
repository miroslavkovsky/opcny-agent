"""
Discord service — posting cez webhook + DM notifikácie.

Webhook je najjednoduchší spôsob postovania (nepotrebuje bot permissions).
Pre DM notifikácie Mirovi sa používa discord.py bot.
"""

import logging

import httpx

from config.settings import settings

logger = logging.getLogger("service.discord")


class DiscordService:
    """Discord integrácia — webhooky pre posty, bot pre notifikácie."""

    def __init__(self):
        self.webhook_url = settings.discord_webhook_url
        self.http = httpx.AsyncClient(timeout=30)

    async def send_post(
        self,
        content: str,
        title: str | None = None,
        url: str | None = None,
        image_url: str | None = None,
        color: int = 0x1A2B4A,  # Tvoj dark navy
    ) -> dict:
        """
        Pošle embed post cez Discord webhook.

        Args:
            content: Text príspevku
            title: Titulok embedu
            url: Link na článok
            image_url: URL obrázka
            color: Farba embedu (hex)
        """
        if not self.webhook_url:
            logger.warning("Discord webhook URL nie je nastavený")
            return {"status": "skipped", "reason": "no_webhook_url"}

        embed = {
            "description": content[:4096],  # Discord limit
            "color": color,
        }

        if title:
            embed["title"] = title[:256]
        if url:
            embed["url"] = url
        if image_url:
            embed["image"] = {"url": image_url}

        embed["footer"] = {
            "text": "OptionsSimulator.com — Learn to trade options risk-free",
        }

        payload = {
            "username": "OptionsSimulator",
            "embeds": [embed],
        }

        try:
            response = await self.http.post(self.webhook_url, json=payload)
            response.raise_for_status()
            logger.info(f"Discord post odoslaný: {title}")
            return {"status": "success", "platform": "discord"}
        except httpx.HTTPError as e:
            logger.error(f"Discord webhook error: {e}")
            return {"status": "error", "platform": "discord", "error": str(e)}

    async def send_notification(self, title: str, message: str, level: str = "info") -> dict:
        """
        Pošle notifikáciu Mirovi cez webhook (jednoduchšie ako bot DM).
        Pre produkciu môžeš nahradiť za discord.py bot s DM.
        """
        color_map = {
            "info": 0x3498DB,
            "warning": 0xF39C12,
            "error": 0xE74C3C,
            "success": 0x2ECC71,
        }

        icon_map = {"info": "🔔", "warning": "⚠️", "error": "❌", "success": "✅"}
        icon = icon_map.get(level, "🔔")

        payload = {
            "username": "Agent Notifikácie",
            "embeds": [{
                "title": f"{icon} {title}",
                "description": message[:4096],
                "color": color_map.get(level, 0x3498DB),
            }],
        }

        if settings.discord_miro_user_id:
            payload["content"] = f"<@{settings.discord_miro_user_id}>"

        try:
            response = await self.http.post(self.webhook_url, json=payload)
            response.raise_for_status()
            return {"status": "success"}
        except httpx.HTTPError as e:
            logger.error(f"Discord notification error: {e}")
            return {"status": "error", "error": str(e)}
