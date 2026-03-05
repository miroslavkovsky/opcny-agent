"""
OpenAI Embedding Service — generovanie vektorov pre agent pamäť.

Používa model text-embedding-3-small (1536 dimenzií, $0.02/1M tokenov).
"""

import logging

from openai import AsyncOpenAI

from config.settings import settings

logger = logging.getLogger("service.embedding")


class EmbeddingService:
    """Async wrapper pre OpenAI Embeddings API."""

    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_embedding_model

    async def embed(self, text: str) -> list[float]:
        """
        Vygeneruje embedding vektor pre zadaný text.

        Args:
            text: Text na embedovanie (max ~8191 tokenov pre text-embedding-3-small)

        Returns:
            Zoznam floatov (1536 dimenzií)
        """
        try:
            response = await self.client.embeddings.create(
                model=self.model,
                input=text,
            )
            vector = response.data[0].embedding
            logger.debug(
                "Embedding created: %d dims, usage: %d tokens",
                len(vector), response.usage.total_tokens,
            )
            return vector
        except Exception as e:
            logger.error("OpenAI Embedding API error: %s", e)
            raise

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """
        Vygeneruje embeddingy pre viacero textov naraz (efektívnejšie).

        Args:
            texts: Zoznam textov na embedovanie

        Returns:
            Zoznam vektorov (rovnaké poradie ako vstupy)
        """
        try:
            response = await self.client.embeddings.create(
                model=self.model,
                input=texts,
            )
            vectors = [item.embedding for item in response.data]
            logger.debug(
                "Batch embedding: %d texts, usage: %d tokens",
                len(texts), response.usage.total_tokens,
            )
            return vectors
        except Exception as e:
            logger.error("OpenAI Embedding API batch error: %s", e)
            raise
