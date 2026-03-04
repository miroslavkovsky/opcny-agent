"""
ContentReviewAgent — kontroluje kvalitu obsahu pred publikáciou.

Workflow:
1. Nájde nové/zmenené články v DB (status = 'needs_review')
2. Pošle obsah do Claude API na kontrolu
3. Uloží výsledky review do content_reviews tabuľky
4. Notifikuje Mira cez Discord/Telegram
"""

import json
from typing import Any

from sqlalchemy import select, text

from agents.base import BaseAgent
from config.persona import CONTENT_REVIEW_RULES, WRITING_PERSONA
from models import async_session, ContentReview, ScheduledPost
from services.claude_service import ClaudeService
from utils.notifications import notify_miro


class ContentReviewAgent(BaseAgent):
    """Agent zodpovedný za kontrolu kvality všetkého obsahu."""

    def __init__(self):
        super().__init__()
        self.claude = ClaudeService()

    async def execute(self, **kwargs) -> dict[str, Any]:
        action = kwargs.get("action", "check_pending")

        if action == "check_pending":
            return await self._check_pending_content()
        elif action == "review_single":
            return await self._review_single(
                target_type=kwargs["target_type"],
                target_id=kwargs["target_id"],
                content=kwargs["content"],
            )
        else:
            return {"status": "skipped", "details": {"reason": f"Unknown action: {action}"}}

    async def _check_pending_content(self) -> dict[str, Any]:
        """Nájde články čakajúce na review a skontroluje ich."""
        async with async_session() as session:
            # Nájdi posty so statusom 'pending_review' ktoré ešte nemajú review
            result = await session.execute(
                select(ScheduledPost).where(ScheduledPost.status == "pending_review")
            )
            pending_posts = result.scalars().all()

            if not pending_posts:
                return {"status": "skipped", "details": {"reason": "Žiadny obsah na review"}}

            reviewed = 0
            for post in pending_posts:
                # Skontroluj každú platformovú verziu
                for platform, content in post.content_body.items():
                    review_result = await self._run_review(content, platform)

                    review = ContentReview(
                        target_type="social_post",
                        target_id=str(post.id),
                        review_result=review_result,
                        agent_notes=review_result.get("summary", ""),
                        status=review_result.get("overall_status", "needs_changes"),
                    )
                    session.add(review)

                # Ak všetky platformy OK, nastav status
                post.status = "approved" if review_result.get("overall_status") == "approved" else "needs_changes"
                reviewed += 1

            await session.commit()

        # Notifikuj Mira
        await notify_miro(
            title="Content Review dokončený",
            message=f"Skontrolovaných {reviewed} príspevkov. "
                    f"Otvor admin panel pre detaily.",
            level="info",
        )

        return {
            "status": "success",
            "details": {"reviewed_count": reviewed},
        }

    async def _review_single(
        self, target_type: str, target_id: str, content: str
    ) -> dict[str, Any]:
        """Review jedného konkrétneho obsahu (volaný z admin API)."""
        review_result = await self._run_review(content)

        async with async_session() as session:
            review = ContentReview(
                target_type=target_type,
                target_id=target_id,
                review_result=review_result,
                agent_notes=review_result.get("summary", ""),
                status=review_result.get("overall_status", "needs_changes"),
            )
            session.add(review)
            await session.commit()

        return {"status": "success", "details": review_result}

    async def _run_review(self, content: str, platform: str | None = None) -> dict:
        """Pošle obsah do Claude API na kontrolu."""
        platform_context = f"\nPlatforma: {platform}" if platform else ""

        response = await self.claude.generate(
            system_prompt=f"{WRITING_PERSONA}\n\n{CONTENT_REVIEW_RULES}",
            user_message=f"Skontroluj nasledujúci obsah:{platform_context}\n\n---\n{content}\n---",
            response_format="json",
        )

        try:
            return json.loads(response)
        except json.JSONDecodeError:
            self.logger.warning("Claude nevrátil validný JSON, parsovanie odpovede...")
            return {
                "overall_status": "needs_changes",
                "summary": response[:500],
                "parse_error": True,
            }
