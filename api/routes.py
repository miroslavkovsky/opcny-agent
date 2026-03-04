"""
Internal API — health check, manuálne spustenie agentov, status.

Tieto endpointy volá hlavná appka (admin panel) alebo sa používajú
na monitoring. Chránené internal API kľúčom.
"""

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel

from agents import AnalyticsAgent, ContentReviewAgent, SocialMediaAgent
from config.settings import settings

logger = logging.getLogger("api")

router = APIRouter()


# --- Auth ---

async def verify_api_key(x_api_key: str = Header(default="")):
    """Jednoduchá API key autentifikácia pre internal komunikáciu."""
    if settings.internal_api_key and x_api_key != settings.internal_api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")


# --- Health Check ---

@router.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "opcny-agents",
        "timestamp": datetime.now(UTC).isoformat(),
    }


# --- Scheduler Status ---

@router.get("/status", dependencies=[Depends(verify_api_key)])
async def scheduler_status(request: Request):
    """Vráti stav všetkých naplánovaných jobov."""
    scheduler = getattr(request.app.state, "scheduler", None)
    if not scheduler:
        return {"jobs": [], "note": "Scheduler nie je inicializovaný"}

    return {"jobs": scheduler.get_status()}


# --- Manual Triggers ---

class GeneratePostRequest(BaseModel):
    topic: str
    platforms: list[str] = ["discord", "twitter"]
    source_blog_id: int | None = None


class ReviewRequest(BaseModel):
    target_type: str = "blog_post"
    target_id: str
    content: str


class AnalyticsRequest(BaseModel):
    start_date: str  # YYYY-MM-DD
    end_date: str


@router.post("/agents/social-media/generate", dependencies=[Depends(verify_api_key)])
async def trigger_generate_post(req: GeneratePostRequest):
    """Manuálne vygenerovanie nového postu (volaný z admin panelu)."""
    agent = SocialMediaAgent()
    result = await agent.run(
        action="generate_post",
        topic=req.topic,
        platforms=req.platforms,
        source_blog_id=req.source_blog_id,
    )
    return result


@router.post("/agents/content-review/review", dependencies=[Depends(verify_api_key)])
async def trigger_review(req: ReviewRequest):
    """Manuálne spustenie review pre konkrétny obsah."""
    agent = ContentReviewAgent()
    result = await agent.run(
        action="review_single",
        target_type=req.target_type,
        target_id=req.target_id,
        content=req.content,
    )
    return result


@router.post("/agents/content-review/check-pending", dependencies=[Depends(verify_api_key)])
async def trigger_check_pending():
    """Manuálne spustenie kontroly pending obsahu."""
    agent = ContentReviewAgent()
    result = await agent.run(action="check_pending")
    return result


@router.post("/agents/analytics/daily", dependencies=[Depends(verify_api_key)])
async def trigger_daily_analytics():
    """Manuálne spustenie denného analytics reportu."""
    agent = AnalyticsAgent()
    result = await agent.run(action="daily_report")
    return result


@router.post("/agents/analytics/weekly", dependencies=[Depends(verify_api_key)])
async def trigger_weekly_analytics():
    """Manuálne spustenie týždenného analytics reportu."""
    agent = AnalyticsAgent()
    result = await agent.run(action="weekly_report")
    return result


@router.post("/agents/analytics/custom", dependencies=[Depends(verify_api_key)])
async def trigger_custom_analytics(req: AnalyticsRequest):
    """Manuálne spustenie analytics reportu za custom obdobie."""
    agent = AnalyticsAgent()
    result = await agent.run(
        action="custom_report",
        start_date=req.start_date,
        end_date=req.end_date,
    )
    return result
