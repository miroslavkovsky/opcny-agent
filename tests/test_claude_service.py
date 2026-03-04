"""Testy pre services/claude_service.py — Claude API wrapper."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def claude_service():
    with patch("services.claude_service.AsyncAnthropic"):
        from services.claude_service import ClaudeService

        service = ClaudeService()
        service.client = AsyncMock()
        return service


def _make_response(text: str):
    """Pomocná funkcia pre mock Claude response."""
    response = MagicMock()
    response.content = [MagicMock(text=text)]
    response.usage = MagicMock(input_tokens=100, output_tokens=50)
    return response


@pytest.mark.asyncio
async def test_generate_basic(claude_service):
    """Základné generovanie textu."""
    claude_service.client.messages.create = AsyncMock(
        return_value=_make_response("Hello world")
    )

    result = await claude_service.generate(
        user_message="Test prompt",
        system_prompt="Test system",
    )

    assert result == "Hello world"
    claude_service.client.messages.create.assert_called_once()


@pytest.mark.asyncio
async def test_generate_json_format(claude_service):
    """JSON format pridáva inštrukciu do promptu."""
    claude_service.client.messages.create = AsyncMock(
        return_value=_make_response('{"key": "value"}')
    )

    result = await claude_service.generate(
        user_message="Test prompt",
        response_format="json",
    )

    assert result == '{"key": "value"}'
    call_args = claude_service.client.messages.create.call_args
    messages = call_args.kwargs["messages"]
    assert "JSON" in messages[0]["content"]


@pytest.mark.asyncio
async def test_generate_strips_markdown_json(claude_service):
    """Odstraní markdown backticky z JSON odpovede."""
    claude_service.client.messages.create = AsyncMock(
        return_value=_make_response('```json\n{"key": "value"}\n```')
    )

    result = await claude_service.generate(
        user_message="Test",
        response_format="json",
    )

    assert result == '{"key": "value"}'


@pytest.mark.asyncio
async def test_generate_api_error_propagates(claude_service):
    """API error sa propaguje hore."""
    claude_service.client.messages.create = AsyncMock(
        side_effect=Exception("API rate limit")
    )

    with pytest.raises(Exception, match="API rate limit"):
        await claude_service.generate(user_message="Test")
