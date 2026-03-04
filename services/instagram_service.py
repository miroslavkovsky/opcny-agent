"""
Instagram service — posting cez Meta Graph API.

Vyžaduje:
- Meta Developer Account
- Instagram Business/Creator Account prepojený s Facebook Page
- Long-lived access token (obnovuj každých 60 dní)

Poznámka: Instagram Graph API neumožňuje direct posting obrázkov z URL
bez predošlého hostenia. Obrázky musia byť na verejne dostupnom URL.
"""

import logging
from typing import Any

import httpx

from config.settings import settings

logger = logging.getLogger("service.instagram")

GRAPH_API_BASE = "https://graph.facebook.com/v21.0"


class InstagramService:
    """Instagram Graph API wrapper."""

    def __init__(self):
        self.access_token = settings.instagram_access_token
        self.account_id = settings.instagram_business_account_id
        self.http = httpx.AsyncClient(timeout=60)

    async def post(
        self,
        caption: str,
        image_url: str | None = None,
        carousel_urls: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Postne na Instagram.

        Args:
            caption: Text príspevku (max 2200 znakov)
            image_url: URL jedného obrázka
            carousel_urls: Zoznam URL pre carousel (2-10 obrázkov)
        """
        if not self.access_token or not self.account_id:
            logger.warning("Instagram credentials nie sú nastavené")
            return {"status": "skipped", "reason": "no_credentials"}

        try:
            if carousel_urls and len(carousel_urls) >= 2:
                return await self._post_carousel(caption, carousel_urls)
            elif image_url:
                return await self._post_single(caption, image_url)
            else:
                logger.warning("Instagram vyžaduje obrázok — post preskočený")
                return {"status": "skipped", "reason": "no_image"}
        except Exception as e:
            logger.error(f"Instagram post error: {e}")
            return {"status": "error", "platform": "instagram", "error": str(e)}

    async def _post_single(self, caption: str, image_url: str) -> dict:
        """Single image post."""
        # Step 1: Vytvor media container
        create_url = f"{GRAPH_API_BASE}/{self.account_id}/media"
        response = await self.http.post(create_url, params={
            "image_url": image_url,
            "caption": caption[:2200],
            "access_token": self.access_token,
        })
        response.raise_for_status()
        container_id = response.json()["id"]

        # Step 2: Publikuj
        return await self._publish(container_id)

    async def _post_carousel(self, caption: str, image_urls: list[str]) -> dict:
        """Carousel post (2-10 obrázkov)."""
        children_ids = []

        # Step 1: Vytvor child containers
        for url in image_urls[:10]:
            response = await self.http.post(
                f"{GRAPH_API_BASE}/{self.account_id}/media",
                params={
                    "image_url": url,
                    "is_carousel_item": "true",
                    "access_token": self.access_token,
                },
            )
            response.raise_for_status()
            children_ids.append(response.json()["id"])

        # Step 2: Vytvor carousel container
        response = await self.http.post(
            f"{GRAPH_API_BASE}/{self.account_id}/media",
            params={
                "media_type": "CAROUSEL",
                "children": ",".join(children_ids),
                "caption": caption[:2200],
                "access_token": self.access_token,
            },
        )
        response.raise_for_status()
        container_id = response.json()["id"]

        # Step 3: Publikuj
        return await self._publish(container_id)

    async def _publish(self, container_id: str) -> dict:
        """Publikuj pripravený media container."""
        response = await self.http.post(
            f"{GRAPH_API_BASE}/{self.account_id}/media_publish",
            params={
                "creation_id": container_id,
                "access_token": self.access_token,
            },
        )
        response.raise_for_status()
        media_id = response.json()["id"]

        logger.info(f"Instagram post published: {media_id}")
        return {
            "status": "success",
            "platform": "instagram",
            "media_id": media_id,
        }
