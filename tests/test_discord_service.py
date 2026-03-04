"""Testy pre services/discord_service.py — webhook posting."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest


@pytest.fixture
def discord_service():
    with patch("services.discord_service.settings") as mock_settings:
        mock_settings.discord_webhook_url = "https://discord.com/api/webhooks/test"
        mock_settings.discord_miro_user_id = "123456"
        from services.discord_service import DiscordService

        service = DiscordService()
        service.http = AsyncMock(spec=httpx.AsyncClient)
        yield service


@pytest.fixture
def discord_service_no_webhook():
    with patch("services.discord_service.settings") as mock_settings:
        mock_settings.discord_webhook_url = ""
        from services.discord_service import DiscordService

        return DiscordService()


@pytest.mark.asyncio
async def test_send_post_success(discord_service):
    """Úspešné odoslanie postu cez webhook."""
    response = MagicMock()
    response.raise_for_status = MagicMock()
    discord_service.http.post = AsyncMock(return_value=response)

    result = await discord_service.send_post(
        content="Test content",
        title="Test Title",
    )

    assert result["status"] == "success"
    assert result["platform"] == "discord"
    discord_service.http.post.assert_called_once()

    # Skontroluj embed payload
    call_args = discord_service.http.post.call_args
    payload = call_args.kwargs["json"]
    assert payload["embeds"][0]["title"] == "Test Title"
    assert payload["embeds"][0]["description"] == "Test content"


@pytest.mark.asyncio
async def test_send_post_no_webhook(discord_service_no_webhook):
    """Bez webhook URL sa post preskočí."""
    result = await discord_service_no_webhook.send_post(content="Test")
    assert result["status"] == "skipped"


@pytest.mark.asyncio
async def test_send_post_truncates_long_content(discord_service):
    """Dlhý content sa orezáva na 4096 znakov."""
    response = MagicMock()
    response.raise_for_status = MagicMock()
    discord_service.http.post = AsyncMock(return_value=response)

    long_content = "x" * 5000
    await discord_service.send_post(content=long_content)

    call_args = discord_service.http.post.call_args
    payload = call_args.kwargs["json"]
    assert len(payload["embeds"][0]["description"]) == 4096


@pytest.mark.asyncio
async def test_send_notification_mentions_miro(discord_service):
    """Notifikácia obsahuje @mention Mira."""
    response = MagicMock()
    response.raise_for_status = MagicMock()
    discord_service.http.post = AsyncMock(return_value=response)

    await discord_service.send_notification(
        title="Test",
        message="Test message",
        level="error",
    )

    call_args = discord_service.http.post.call_args
    payload = call_args.kwargs["json"]
    assert "<@123456>" in payload["content"]


@pytest.mark.asyncio
async def test_send_post_http_error(discord_service):
    """HTTP error vracia error status, nie exception."""
    discord_service.http.post = AsyncMock(
        side_effect=httpx.HTTPError("Connection refused")
    )

    result = await discord_service.send_post(content="Test")
    assert result["status"] == "error"
    assert "Connection refused" in result["error"]
