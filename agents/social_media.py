"""
SocialMediaAgent — generuje a publikuje príspevky na sociálne siete.

Workflow:
1. Nájde schválený obsah pripravený na publikáciu
2. Generuje platformovo-špecifické varianty cez Claude API
3. Publikuje na Discord, X, Instagram podľa harmonogramu
4. Sleduje engagement a ukladá metriky
"""

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from agents.base import BaseAgent
from config.persona import PLATFORM_GUIDELINES, WRITING_PERSONA
from models import ScheduledPost, async_session
from services.claude_service import ClaudeService
from services.discord_service import DiscordService
from services.instagram_service import InstagramService
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
                    ScheduledPost.status == "approved",
                    ScheduledPost.scheduled_at <= now,
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
                    post.status = "published"
                    post.published_at = now
                    post.engagement_data = {"publish_results": results}
                    published += 1
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
        """Vygeneruje nový príspevok pre zadané platformy."""
        content_body = {}

        for platform in platforms:
            guidelines = PLATFORM_GUIDELINES.get(platform, {})

            prompt = (
                f"Vytvor príspevok pre platformu {platform.upper()} na tému:\n"
                f"{topic}\n\n"
                f"Pravidlá platformy:\n"
                f"- Max dĺžka: {guidelines.get('max_length', 2000)} znakov\n"
                f"- Štýl: {guidelines.get('style', 'profesionálny')}\n"
            )

            if guidelines.get("hashtags"):
                suggested = guidelines.get("suggested_hashtags", [])
                prompt += f"- Použi relevantné hashtagy z: {', '.join(suggested)}\n"

            if platform == "twitter" and guidelines.get("thread_max"):
                prompt += (
                    f"- Ak je potrebný thread, max {guidelines['thread_max']} tweetov\n"
                    f"- Oddeľ tweety pomocou ---TWEET---\n"
                )

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
                    title=post.title,
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
