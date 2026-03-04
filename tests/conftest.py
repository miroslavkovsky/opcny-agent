"""
Spoločné fixtures pre testy — mockované DB sessions, Claude API, HTTP klienty.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_async_session():
    """Mockovaná async DB session."""
    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)

    # Mock execute result
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(return_value=result)
    session.commit = AsyncMock()
    session.add = MagicMock()

    return session


@pytest.fixture
def mock_claude_service():
    """Mockovaný ClaudeService — nerobí reálne API volania."""
    with patch("services.claude_service.AsyncAnthropic"):
        from services.claude_service import ClaudeService

        service = ClaudeService()
        service.client = AsyncMock()
        yield service


@pytest.fixture
def mock_notify_miro():
    """Mockované notifikácie — neposielajú sa reálne."""
    with patch("utils.notifications.notify_miro", new_callable=AsyncMock) as mock:
        yield mock
