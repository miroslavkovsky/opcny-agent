"""Testy pre agents/base.py — BaseAgent lifecycle, logging, error handling."""

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture
def test_agent():
    with (
        patch("agents.base.async_session") as mock_session_factory,
        patch("agents.base.notify_miro", new_callable=AsyncMock) as mock_notify,
    ):
        session = AsyncMock()
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=False)
        mock_session_factory.return_value = session

        from agents.base import BaseAgent

        class TestAgent(BaseAgent):
            async def execute(self, **kwargs) -> dict[str, Any]:
                action = kwargs.get("action")
                if action == "fail":
                    raise ValueError("Test error")
                return {"status": "success", "details": {"test": True}}

        agent = TestAgent()
        yield agent, session, mock_notify


@pytest.mark.asyncio
async def test_run_success_logs_to_db(test_agent):
    """Úspešný run loguje do DB."""
    agent, session, _ = test_agent

    result = await agent.run(action="test")

    assert result["status"] == "success"
    session.add.assert_called_once()
    session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_run_error_catches_exception(test_agent):
    """Error v execute sa zachytí a vráti error status."""
    agent, session, mock_notify = test_agent

    result = await agent.run(action="fail")

    assert result["status"] == "error"
    assert "Test error" in result["error"]


@pytest.mark.asyncio
async def test_run_error_notifies_miro(test_agent):
    """Error v execute notifikuje Mira."""
    agent, _, mock_notify = test_agent

    await agent.run(action="fail")

    mock_notify.assert_called_once()
    call_args = mock_notify.call_args
    assert "chyba" in call_args.kwargs["title"]
    assert call_args.kwargs["level"] == "error"


@pytest.mark.asyncio
async def test_render_template(test_agent):
    """_render_template renderuje Jinja2 šablóny."""
    agent, _, _ = test_agent

    result = agent._render_template(
        "review_notification.j2",
        target_type="blog_post",
        status="approved",
        grammar_issues=[],
        tone_assessment="ok",
        tone_notes="",
        seo_score=90,
        seo_suggestions=[],
        compliance_ok=True,
        summary="All good.",
    )

    assert "Content Review" in result
    assert "Schválené" in result
    assert "All good." in result
