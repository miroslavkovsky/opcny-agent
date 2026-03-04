"""
Notifikačný systém — posiela správy Mirovi cez Discord alebo Telegram.
"""

import logging

import httpx

from config.settings import settings

logger = logging.getLogger("notifications")


async def notify_miro(
    title: str,
    message: str,
    level: str = "info",  # info | warning | error | success
) -> dict:
    """
    Pošle notifikáciu Mirovi cez nakonfigurovaný kanál.

    V development mode iba loguje.
    """
    if settings.is_development:
        logger.info(f"[NOTIFICATION] [{level.upper()}] {title}: {message[:200]}")
        return {"status": "logged", "method": "development"}

    method = settings.notification_method

    if method == "discord":
        return await _notify_discord(title, message, level)
    elif method == "telegram":
        return await _notify_telegram(title, message, level)
    else:
        logger.warning(f"Neznámy notification method: {method}")
        return {"status": "error", "reason": f"unknown_method: {method}"}


async def _notify_discord(title: str, message: str, level: str) -> dict:
    """Pošle notifikáciu cez Discord webhook."""
    from services.discord_service import DiscordService

    discord = DiscordService()
    return await discord.send_notification(title=title, message=message, level=level)


async def _notify_telegram(title: str, message: str, level: str) -> dict:
    """Pošle notifikáciu cez Telegram Bot API."""
    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        logger.warning("Telegram credentials nie sú nastavené")
        return {"status": "skipped", "reason": "no_credentials"}

    emoji = {"info": "ℹ️", "warning": "⚠️", "error": "❌", "success": "✅"}.get(level, "📌")
    text = f"{emoji} *{title}*\n\n{message}"

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            response = await client.post(url, json={
                "chat_id": settings.telegram_chat_id,
                "text": text[:4096],
                "parse_mode": "Markdown",
            })
            response.raise_for_status()
            return {"status": "success", "method": "telegram"}
        except httpx.HTTPError as e:
            logger.error(f"Telegram notification error: {e}")
            return {"status": "error", "method": "telegram", "error": str(e)}
