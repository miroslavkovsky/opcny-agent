"""Testy pre agents/content_review.py — ContentReviewAgent."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

MOCK_REVIEW_APPROVED = {
    "grammar_issues": [],
    "tone_assessment": "ok",
    "tone_notes": "",
    "accuracy_issues": [],
    "seo_score": 85,
    "seo_suggestions": [],
    "compliance_ok": True,
    "compliance_notes": "",
    "overall_status": "approved",
    "summary": "Content is good.",
}

MOCK_REVIEW_NEEDS_CHANGES = {
    "grammar_issues": [{"text": "typo", "suggestion": "fix", "severity": "low"}],
    "tone_assessment": "needs_adjustment",
    "tone_notes": "Too aggressive",
    "accuracy_issues": [],
    "seo_score": 40,
    "seo_suggestions": ["Add meta description"],
    "compliance_ok": True,
    "compliance_notes": "",
    "overall_status": "needs_changes",
    "summary": "Needs grammar and tone fixes.",
}


@pytest.fixture
def content_review_agent():
    with (
        patch("agents.content_review.async_session") as mock_session_factory,
        patch("agents.content_review.notify_miro", new_callable=AsyncMock),
        patch("agents.base.async_session"),
        patch("agents.base.notify_miro", new_callable=AsyncMock),
    ):
        session = AsyncMock()
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=False)
        mock_session_factory.return_value = session

        from agents.content_review import ContentReviewAgent

        agent = ContentReviewAgent()
        agent.claude = AsyncMock()
        yield agent, session


@pytest.mark.asyncio
async def test_check_pending_no_posts(content_review_agent):
    """Žiadne pending posty — vracia skipped."""
    agent, session = content_review_agent
    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(return_value=result_mock)

    result = await agent.execute(action="check_pending")

    assert result["status"] == "skipped"


@pytest.mark.asyncio
async def test_check_pending_approves_post(content_review_agent):
    """Post s approved review dostane status approved."""
    agent, session = content_review_agent

    # Mock pending post
    mock_post = MagicMock()
    mock_post.id = "test-uuid"
    mock_post.content_body = {"discord": "Test content"}
    mock_post.status = "pending_review"

    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = [mock_post]
    session.execute = AsyncMock(return_value=result_mock)

    # Mock Claude review
    import json
    agent.claude.generate = AsyncMock(return_value=json.dumps(MOCK_REVIEW_APPROVED))

    result = await agent.execute(action="check_pending")

    assert result["status"] == "success"
    assert result["details"]["reviewed_count"] == 1
    assert mock_post.status == "approved"


@pytest.mark.asyncio
async def test_check_pending_needs_changes(content_review_agent):
    """Post s needs_changes review dostane status needs_changes."""
    agent, session = content_review_agent

    mock_post = MagicMock()
    mock_post.id = "test-uuid"
    mock_post.content_body = {"discord": "Bad content"}
    mock_post.status = "pending_review"

    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = [mock_post]
    session.execute = AsyncMock(return_value=result_mock)

    import json
    agent.claude.generate = AsyncMock(return_value=json.dumps(MOCK_REVIEW_NEEDS_CHANGES))

    result = await agent.execute(action="check_pending")

    assert result["status"] == "success"
    assert mock_post.status == "needs_changes"


@pytest.mark.asyncio
async def test_check_pending_multi_platform_all_must_pass(content_review_agent):
    """Ak jedna platforma zlyhá, celý post je needs_changes."""
    agent, session = content_review_agent

    mock_post = MagicMock()
    mock_post.id = "test-uuid"
    mock_post.content_body = {"discord": "Content", "twitter": "Bad content"}
    mock_post.status = "pending_review"

    result_mock = MagicMock()
    result_mock.scalars.return_value.all.return_value = [mock_post]
    session.execute = AsyncMock(return_value=result_mock)

    import json
    # Discord approved, Twitter needs changes
    agent.claude.generate = AsyncMock(
        side_effect=[
            json.dumps(MOCK_REVIEW_APPROVED),
            json.dumps(MOCK_REVIEW_NEEDS_CHANGES),
        ]
    )

    await agent.execute(action="check_pending")

    assert mock_post.status == "needs_changes"


@pytest.mark.asyncio
async def test_review_single(content_review_agent):
    """Review jedného obsahu cez API endpoint."""
    agent, session = content_review_agent

    import json
    agent.claude.generate = AsyncMock(return_value=json.dumps(MOCK_REVIEW_APPROVED))

    result = await agent.execute(
        action="review_single",
        target_type="blog_post",
        target_id="test-123",
        content="Test blog post content...",
    )

    assert result["status"] == "success"
    assert result["details"]["overall_status"] == "approved"
    session.add.assert_called_once()
    session.commit.assert_called_once()


@pytest.mark.asyncio
async def test_unknown_action(content_review_agent):
    """Neznáma akcia vracia skipped."""
    agent, _ = content_review_agent
    result = await agent.execute(action="nonexistent")
    assert result["status"] == "skipped"
