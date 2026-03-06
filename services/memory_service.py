"""
Agent Memory Service — ukladanie a vyhľadávanie v pamäti agentov.

Používa jednoduchú PostgreSQL tabuľku (bez pgvector).
Deduplikáciu tém rieši Claude porovnaním zoznamu nedávnych tém.
"""

import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from models import AgentMemory, ScheduledPost, async_session
from services.claude_service import ClaudeService

logger = logging.getLogger("service.memory")


class MemoryService:
    """Pamäťový systém pre agentov — store & Claude-based deduplikácia."""

    def __init__(self):
        self.claude = ClaudeService()

    async def store(
        self,
        agent_name: str,
        content_type: str,
        topic: str,
        content_summary: str,
        platforms: list[str] | None = None,
        source_post_id: uuid.UUID | None = None,
    ) -> AgentMemory:
        """Uloží nový záznam do pamäte agenta."""
        async with async_session() as session:
            memory = AgentMemory(
                agent_name=agent_name,
                content_type=content_type,
                topic=topic,
                content_summary=content_summary,
                platforms=platforms,
                source_post_id=source_post_id,
            )
            session.add(memory)
            await session.commit()
            await session.refresh(memory)

        logger.info(
            "Memory stored: agent=%s, type=%s, topic='%s'",
            agent_name, content_type, topic[:80],
        )
        return memory

    async def get_recent_topics(
        self,
        agent_name: str,
        days_back: int = 7,
        limit: int = 20,
        only_published: bool = False,
    ) -> list[dict]:
        """Vráti nedávne témy s ich zhrnutiami pre daného agenta.

        Args:
            only_published: Ak True, vráti len témy kde linked post bol publikovaný.

        Returns:
            Zoznam diktov: {"topic": str, "content_summary": str, "created_at": str}
        """
        cutoff = datetime.now(UTC) - timedelta(days=days_back)

        query = (
            select(
                AgentMemory.topic,
                AgentMemory.content_summary,
                AgentMemory.created_at,
            )
            .where(
                AgentMemory.agent_name == agent_name,
                AgentMemory.created_at >= cutoff,
            )
        )

        if only_published:
            query = query.join(
                ScheduledPost,
                AgentMemory.source_post_id == ScheduledPost.id,
            ).where(ScheduledPost.status == "published")

        query = query.order_by(AgentMemory.created_at.desc()).limit(limit)

        async with async_session() as session:
            result = await session.execute(query)
            rows = result.all()

        return [
            {
                "topic": row.topic,
                "content_summary": row.content_summary[:200],
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ]

    async def is_too_similar(
        self,
        topic: str,
        agent_name: str,
        days_back: int = 14,
    ) -> tuple[bool, str]:
        """
        Nechá Clauda posúdiť či je nová téma príliš podobná nedávnym.

        Returns:
            Tuple (is_similar, reason) — True ak sa téma opakuje
        """
        # Kontroluj len proti publikovaným postom — draft/needs_changes/failed neblokujú
        recent = await self.get_recent_topics(
            agent_name=agent_name,
            days_back=days_back,
            limit=20,
            only_published=True,
        )

        if not recent:
            return False, ""

        topics_list = "\n".join(
            f"- {r['topic']}" for r in recent
        )

        response = await self.claude.generate(
            system_prompt=(
                "You are a content deduplication checker. "
                "Answer ONLY with a JSON object: "
                '{"is_duplicate": true/false, "reason": "brief explanation"}. '
                "Consider a topic duplicate if it covers the SAME core concept "
                "with no meaningful new angle. Similar but distinct topics are OK."
            ),
            user_message=(
                f"New topic to check:\n\"{topic}\"\n\n"
                f"Recently published topics:\n{topics_list}\n\n"
                f"Is the new topic a duplicate of any recent topic?"
            ),
            response_format="json",
            max_tokens=200,
        )

        try:
            import json
            result = json.loads(response)
            is_dup = result.get("is_duplicate", False)
            reason = result.get("reason", "")
        except (json.JSONDecodeError, AttributeError):
            logger.warning("Failed to parse dedup response: %s", response[:200])
            return False, ""

        if is_dup:
            logger.info(
                "Téma '%s' je duplicitná: %s",
                topic[:80], reason,
            )

        return is_dup, reason
