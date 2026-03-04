"""
Twitter/X service — posting cez Tweepy (X API v2).

Vyžaduje:
- X Developer Account (https://developer.x.com)
- App s OAuth 1.0a credentials (pre posting)
- Elevated access pre thread posting
"""

import logging
from typing import Any

from config.settings import settings

logger = logging.getLogger("service.twitter")


class TwitterService:
    """X/Twitter API wrapper."""

    def __init__(self):
        self._client = None

    def _get_client(self):
        """Lazy init tweepy klienta."""
        if self._client is None:
            try:
                import tweepy

                self._client = tweepy.AsyncClient(
                    consumer_key=settings.twitter_api_key,
                    consumer_secret=settings.twitter_api_secret,
                    access_token=settings.twitter_access_token,
                    access_token_secret=settings.twitter_access_token_secret,
                    bearer_token=settings.twitter_bearer_token,
                )
            except ImportError:
                logger.error("tweepy nie je nainštalovaný")
                raise

        return self._client

    async def post_tweet(
        self,
        content: str,
        reply_to_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Postne tweet alebo thread.

        Ak obsah obsahuje ---TWEET--- delimiter, postne ako thread.
        """
        if not settings.twitter_api_key:
            logger.warning("Twitter API credentials nie sú nastavené")
            return {"status": "skipped", "reason": "no_credentials"}

        client = self._get_client()

        # Detekuj thread
        if "---TWEET---" in content:
            return await self._post_thread(content, client)

        try:
            response = await client.create_tweet(
                text=content[:280],
                in_reply_to_tweet_id=reply_to_id,
            )
            tweet_id = response.data["id"]
            logger.info(f"Tweet posted: {tweet_id}")
            return {
                "status": "success",
                "platform": "twitter",
                "tweet_id": tweet_id,
            }
        except Exception as e:
            logger.error(f"Twitter post error: {e}")
            return {"status": "error", "platform": "twitter", "error": str(e)}

    async def _post_thread(self, content: str, client) -> dict[str, Any]:
        """Postne thread — sériu navzájom prepojených tweetov."""
        tweets = [t.strip() for t in content.split("---TWEET---") if t.strip()]
        tweet_ids = []
        reply_to = None

        for i, tweet_text in enumerate(tweets):
            try:
                response = await client.create_tweet(
                    text=tweet_text[:280],
                    in_reply_to_tweet_id=reply_to,
                )
                tweet_id = response.data["id"]
                tweet_ids.append(tweet_id)
                reply_to = tweet_id
                logger.info(f"Thread tweet {i+1}/{len(tweets)}: {tweet_id}")
            except Exception as e:
                logger.error(f"Thread tweet {i+1} failed: {e}")
                break

        return {
            "status": "success" if tweet_ids else "error",
            "platform": "twitter",
            "thread_ids": tweet_ids,
            "total_tweets": len(tweets),
            "posted_tweets": len(tweet_ids),
        }
