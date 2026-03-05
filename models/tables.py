"""
Databázové modely pre agent worker service.
Tieto tabuľky existujú v zdieľanej PostgreSQL databáze s hlavnou appkou.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    ARRAY,
    JSON,
    BigInteger,
    Date,
    DateTime,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from models.base import Base


class ScheduledPost(Base):
    """Naplánované príspevky pre sociálne siete."""
    __tablename__ = "scheduled_posts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    content_body: Mapped[dict] = mapped_column(
        JSON, nullable=False, comment="{ discord: '...', twitter: '...', instagram: '...' }"
    )
    source_blog_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    platforms: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, comment="{'discord', 'twitter', 'instagram'}"
    )
    status: Mapped[str] = mapped_column(
        String(50), default="draft",
        comment="draft | pending_review | approved | scheduled | published | failed"
    )
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    engagement_data: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        Index("idx_scheduled_posts_status", "status"),
        Index("idx_scheduled_posts_scheduled_at", "scheduled_at"),
    )


class ContentReview(Base):
    """Záznamy z content review procesu."""
    __tablename__ = "content_reviews"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    target_type: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="blog_post | social_post"
    )
    target_id: Mapped[str] = mapped_column(String(255), nullable=False)
    review_result: Mapped[dict] = mapped_column(
        JSON, nullable=False,
        comment="{ grammar_issues, tone_assessment, seo_score, overall_status... }"
    )
    agent_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(50), default="pending", comment="pending | approved | needs_changes"
    )
    reviewed_by: Mapped[str] = mapped_column(
        String(50), default="agent", comment="agent | miro"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("idx_content_reviews_target", "target_type", "target_id"),
    )


class AnalyticsSnapshot(Base):
    """GA4 analytics snapshoty."""
    __tablename__ = "analytics_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    period_type: Mapped[str] = mapped_column(
        String(20), nullable=False, comment="daily | weekly | monthly"
    )
    metrics: Mapped[dict] = mapped_column(
        JSON, nullable=False,
        comment="{ pageviews, sessions, bounce_rate, avg_session_duration, top_pages... }"
    )
    insights: Mapped[str | None] = mapped_column(
        Text, nullable=True, comment="AI-generované insights"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("idx_analytics_snapshots_period", "period_start", "period_type"),
    )


class AgentLog(Base):
    """Activity logy pre všetkých agentov."""
    __tablename__ = "agent_logs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    agent_name: Mapped[str] = mapped_column(String(100), nullable=False)
    action: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="success | error | skipped"
    )
    details: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("idx_agent_logs_agent", "agent_name", "created_at"),
    )


class AgentMemory(Base):
    """Pamäť agentov — ukladá embeddingy generovaného obsahu pre deduplikáciu."""
    __tablename__ = "agent_memory"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    agent_name: Mapped[str] = mapped_column(
        String(100), nullable=False, comment="Ktorý agent vytvoril záznam"
    )
    content_type: Mapped[str] = mapped_column(
        String(50), nullable=False, comment="social_post | blog_review | analytics_insight"
    )
    topic: Mapped[str] = mapped_column(
        String(500), nullable=False, comment="Téma / krátky popis obsahu"
    )
    content_summary: Mapped[str] = mapped_column(
        Text, nullable=False, comment="Zhrnutie generovaného obsahu"
    )
    embedding = mapped_column(
        Vector(1536), nullable=False, comment="OpenAI text-embedding-3-small vektor"
    )
    platforms: Mapped[list[str] | None] = mapped_column(
        ARRAY(String), nullable=True, comment="Na aké platformy bol obsah publikovaný"
    )
    source_post_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True, comment="Referencia na scheduled_posts.id"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("idx_agent_memory_agent", "agent_name", "created_at"),
        Index("idx_agent_memory_type", "content_type"),
    )
