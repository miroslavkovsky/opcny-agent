"""
SocialMediaAgent — generuje a publikuje príspevky na sociálne siete.

Workflow:
1. Nájde schválený obsah pripravený na publikáciu
2. Generuje platformovo-špecifické varianty cez Claude API
3. Publikuje na Discord, X, Instagram podľa harmonogramu
4. Sleduje engagement a ukladá metriky
"""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import or_, select

from agents.base import BaseAgent
from config.persona import PLATFORM_GUIDELINES, WRITING_PERSONA
from models import ScheduledPost, async_session
from services.claude_service import ClaudeService
from services.discord_service import DiscordService
from services.instagram_service import InstagramService
from services.memory_service import MemoryService
from services.twitter_service import TwitterService
from utils.notifications import notify_miro


class SocialMediaAgent(BaseAgent):
    """Agent zodpovedný za social media posting."""

    def __init__(self):
        super().__init__()
        self.claude = ClaudeService()
        self.discord = DiscordService()
        self.twitter = TwitterService()
        self.instagram = InstagramService()
        self.memory = MemoryService()

    async def execute(self, **kwargs) -> dict[str, Any]:
        action = kwargs.get("action", "publish_scheduled")

        if action == "publish_scheduled":
            return await self._publish_scheduled()
        elif action == "generate_post":
            return await self._generate_post(
                topic=kwargs["topic"],
                platforms=kwargs.get("platforms", ["discord", "twitter"]),
                source_blog_id=kwargs.get("source_blog_id"),
            )
        else:
            return {"status": "skipped", "details": {"reason": f"Unknown action: {action}"}}

    async def _publish_scheduled(self) -> dict[str, Any]:
        """Nájde a publikuje všetky schválené posty ktorých čas nastal."""
        now = datetime.now(UTC)

        async with async_session() as session:
            result = await session.execute(
                select(ScheduledPost).where(
                    ScheduledPost.status.in_(["scheduled", "approved"]),
                    or_(
                        ScheduledPost.scheduled_at <= now,
                        ScheduledPost.scheduled_at.is_(None),  # Auto-approved
                    ),
                )
            )
            posts = result.scalars().all()

            if not posts:
                return {"status": "skipped", "details": {"reason": "Žiadne posty na publikáciu"}}

            published = 0
            failed = 0

            for post in posts:
                try:
                    results = await self._publish_to_platforms(post)

                    # Skontroluj či aspoň jedna platforma uspela
                    any_success = any(
                        r.get("status") == "success" for r in results.values()
                    )
                    all_skipped = all(
                        r.get("status") == "skipped" for r in results.values()
                    )

                    if all_skipped:
                        # Žiadna platforma nebola nakonfigurovaná
                        post.status = "failed"
                        post.error_message = "All platforms skipped (not configured)"
                        failed += 1
                        self.logger.warning(
                            f"Post {post.id}: všetky platformy preskočené"
                        )
                    elif any_success:
                        post.status = "published"
                        post.published_at = now
                        post.engagement_data = {"publish_results": results}
                        published += 1
                    else:
                        # Všetky platformy zlyhali
                        post.status = "failed"
                        post.error_message = str(results)
                        failed += 1
                        self.logger.error(f"Post {post.id}: všetky platformy zlyhali")
                except Exception as e:
                    post.status = "failed"
                    post.error_message = str(e)
                    failed += 1
                    self.logger.error(f"Chyba pri publikácii {post.id}: {e}")

            await session.commit()

        if failed > 0:
            await notify_miro(
                title="Social Media — problémy",
                message=f"Publikovaných: {published}, Zlyhalo: {failed}",
                level="warning",
            )

        return {
            "status": "success",
            "details": {"published": published, "failed": failed},
        }

    async def _generate_post(
        self,
        topic: str,
        platforms: list[str],
        source_blog_id: int | None = None,
    ) -> dict[str, Any]:
        """Vygeneruje nový príspevok pre zadané platformy s kontrolou pamäte."""

        # --- Kontrola pamäte: neopakuj sa ---
        memory_context = ""
        is_duplicate, reason = await self.memory.is_too_similar(
            topic=topic,
            agent_name="SocialMediaAgent",
            days_back=14,
        )
        if is_duplicate:
            self.logger.info(
                "Téma '%s' je duplicitná: %s",
                topic[:80], reason,
            )
            return {
                "status": "skipped",
                "details": {
                    "reason": "Topic too similar to recent content",
                    "duplicate_reason": reason,
                },
            }

        # Pridaj kontext o nedávnych témach do promptu
        recent = await self.memory.get_recent_topics(
            agent_name="SocialMediaAgent",
            days_back=7,
            limit=10,
        )
        if recent:
            topics_list = "\n".join(f"- {r['topic']}" for r in recent)
            memory_context = (
                f"\n\nIMPORTANT — Topics we recently covered (DO NOT repeat these, "
                f"bring a fresh angle):\n{topics_list}\n"
            )

        content_body = {}

        for platform in platforms:
            guidelines = PLATFORM_GUIDELINES.get(platform, {})

            prompt = (
                f"Create a post for {platform.upper()} about:\n"
                f"{topic}\n\n"
                f"Platform rules:\n"
                f"- Max length: {guidelines.get('max_length', 2000)} characters\n"
                f"- Style: {guidelines.get('style', 'professional')}\n"
                f"- Language: English\n"
            )

            if guidelines.get("hashtags"):
                suggested = guidelines.get("suggested_hashtags", [])
                prompt += f"- Use relevant hashtags from: {', '.join(suggested)}\n"

            if platform == "twitter" and guidelines.get("thread_max"):
                prompt += (
                    f"- If a thread is needed, max {guidelines['thread_max']} tweets\n"
                    f"- Separate tweets with ---TWEET---\n"
                )

            prompt += memory_context

            response = await self.claude.generate(
                system_prompt=WRITING_PERSONA,
                user_message=prompt,
            )
            content_body[platform] = response

        # Ulož do DB ako draft
        async with async_session() as session:
            post = ScheduledPost(
                title=topic[:255],
                content_body=content_body,
                source_blog_id=source_blog_id,
                platforms=platforms,
                status="pending_review",  # Najprv pôjde cez ContentReviewAgent
            )
            session.add(post)
            await session.commit()

            post_id = str(post.id)

        # --- Ulož do pamäte ---
        summary = " | ".join(
            f"{p}: {c[:200]}" for p, c in content_body.items()
        )
        await self.memory.store(
            agent_name="SocialMediaAgent",
            content_type="social_post",
            topic=topic,
            content_summary=summary,
            platforms=platforms,
            source_post_id=uuid.UUID(post_id),
        )

        return {
            "status": "success",
            "details": {
                "post_id": post_id,
                "platforms": platforms,
                "status": "pending_review",
            },
        }

    async def _publish_to_platforms(self, post: ScheduledPost) -> dict:
        """Publikuje post na všetky jeho platformy."""
        results = {}

        for platform in post.platforms:
            content = post.content_body.get(platform, "")

            if platform == "discord":
                result = await self.discord.send_post(
                    content=content,
                )
            elif platform == "twitter":
                result = await self.twitter.post_tweet(content=content)
            elif platform == "instagram":
                result = await self.instagram.post(
                    caption=content,
                    # image_url bude riešené neskôr
                )
            else:
                result = {"error": f"Neznáma platforma: {platform}"}

            results[platform] = result
            self.logger.info(f"Publikované na {platform}: {result}")

        return results
