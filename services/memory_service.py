"""
Agent Memory Service — ukladanie a vyhľadávanie v pamäti agentov.

Používa pgvector pre cosine similarity search nad OpenAI embeddings.
Agent si takto "pamätá" o čom písal a neopakuje sa.
"""

import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from config.settings import settings
from models import AgentMemory, async_session
from services.embedding_service import EmbeddingService

logger = logging.getLogger("service.memory")


class MemoryService:
    """Pamäťový systém pre agentov — store & semantic search."""

    def __init__(self):
        self.embeddings = EmbeddingService()
        self.similarity_threshold = settings.memory_similarity_threshold

    async def store(
        self,
        agent_name: str,
        content_type: str,
        topic: str,
        content_summary: str,
        platforms: list[str] | None = None,
        source_post_id: uuid.UUID | None = None,
    ) -> AgentMemory:
        """
        Uloží nový záznam do pamäte agenta s embeddings.

        Args:
            agent_name: Názov agenta (napr. "SocialMediaAgent")
            content_type: Typ obsahu ("social_post", "blog_review", "analytics_insight")
            topic: Téma obsahu
            content_summary: Zhrnutie generovaného obsahu
            platforms: Platformy kde bol obsah publikovaný
            source_post_id: Referencia na scheduled_posts.id

        Returns:
            Vytvorený AgentMemory záznam
        """
        embedding_text = f"{topic}\n{content_summary}"
        vector = await self.embeddings.embed(embedding_text)

        async with async_session() as session:
            memory = AgentMemory(
                agent_name=agent_name,
                content_type=content_type,
                topic=topic,
                content_summary=content_summary,
                embedding=vector,
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

    async def search_similar(
        self,
        query: str,
        agent_name: str | None = None,
        content_type: str | None = None,
        limit: int = 5,
        days_back: int | None = 30,
    ) -> list[dict]:
        """
        Vyhľadá podobný obsah v pamäti agentov pomocou cosine similarity.

        Args:
            query: Text na vyhľadanie (napr. téma nového postu)
            agent_name: Filtrovanie podľa agenta
            content_type: Filtrovanie podľa typu obsahu
            limit: Max počet výsledkov
            days_back: Hľadaj len v posledných N dňoch (None = všetko)

        Returns:
            Zoznam diktov s kľúčmi: id, topic, content_summary, similarity, created_at
        """
        query_vector = await self.embeddings.embed(query)

        async with async_session() as session:
            # pgvector cosine_distance cez SQLAlchemy ORM
            distance = AgentMemory.embedding.cosine_distance(query_vector)
            similarity = (1 - distance).label("similarity")

            stmt = (
                select(AgentMemory, similarity)
                .order_by(distance)
                .limit(limit)
            )

            if agent_name:
                stmt = stmt.where(AgentMemory.agent_name == agent_name)

            if content_type:
                stmt = stmt.where(AgentMemory.content_type == content_type)

            if days_back:
                cutoff = datetime.now(UTC) - timedelta(days=days_back)
                stmt = stmt.where(AgentMemory.created_at >= cutoff)

            result = await session.execute(stmt)
            rows = result.all()

        results = []
        for row_memory, row_similarity in rows:
            results.append({
                "id": str(row_memory.id),
                "agent_name": row_memory.agent_name,
                "content_type": row_memory.content_type,
                "topic": row_memory.topic,
                "content_summary": row_memory.content_summary,
                "platforms": row_memory.platforms,
                "similarity": round(float(row_similarity), 4),
                "created_at": row_memory.created_at.isoformat(),
            })

        logger.debug(
            "Memory search: query='%s', found=%d results",
            query[:80], len(results),
        )
        return results

    async def is_too_similar(
        self,
        topic: str,
        agent_name: str | None = None,
        threshold: float | None = None,
        days_back: int = 14,
    ) -> tuple[bool, list[dict]]:
        """
        Skontroluje či je téma príliš podobná nedávnemu obsahu.

        Args:
            topic: Téma na kontrolu
            agent_name: Filtrovanie podľa agenta
            threshold: Override pre similarity threshold (default z settings)
            days_back: Kontroluj len posledných N dní

        Returns:
            Tuple (is_similar, similar_items) — True ak sa téma opakuje
        """
        threshold = threshold or self.similarity_threshold
        results = await self.search_similar(
            query=topic,
            agent_name=agent_name,
            limit=3,
            days_back=days_back,
        )

        similar = [r for r in results if r["similarity"] >= threshold]

        if similar:
            logger.info(
                "Téma '%s' je príliš podobná existujúcemu obsahu: %s (similarity: %.2f)",
                topic[:80],
                similar[0]["topic"][:80],
                similar[0]["similarity"],
            )

        return len(similar) > 0, similar

    async def get_recent_topics(
        self,
        agent_name: str,
        days_back: int = 7,
        limit: int = 10,
    ) -> list[str]:
        """
        Vráti zoznam nedávnych tém pre daného agenta.
        Užitočné ako kontext pre Claude pri generovaní nového obsahu.

        Args:
            agent_name: Názov agenta
            days_back: Koľko dní dozadu
            limit: Max počet tém

        Returns:
            Zoznam topic stringov
        """
        cutoff = datetime.now(UTC) - timedelta(days=days_back)

        async with async_session() as session:
            result = await session.execute(
                select(AgentMemory.topic)
                .where(
                    AgentMemory.agent_name == agent_name,
                    AgentMemory.created_at >= cutoff,
                )
                .order_by(AgentMemory.created_at.desc())
                .limit(limit)
            )
            topics = [row[0] for row in result.fetchall()]

        return topics
