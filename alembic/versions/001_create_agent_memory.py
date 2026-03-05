"""Create agent_memory table with pgvector.

Revision ID: 001
Revises:
Create Date: 2026-03-05
"""

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "agent_memory",
        sa.Column(
            "id", sa.UUID(), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "agent_name", sa.String(100), nullable=False,
        ),
        sa.Column(
            "content_type", sa.String(50), nullable=False,
        ),
        sa.Column(
            "topic", sa.String(500), nullable=False,
        ),
        sa.Column(
            "content_summary", sa.Text(), nullable=False,
        ),
        sa.Column(
            "embedding", Vector(1536), nullable=False,
        ),
        sa.Column(
            "platforms", sa.ARRAY(sa.String()), nullable=True,
        ),
        sa.Column(
            "source_post_id", sa.UUID(), nullable=True,
        ),
        sa.Column(
            "created_at", sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )

    op.create_index(
        "ix_agent_memory_agent_name", "agent_memory", ["agent_name"],
    )
    op.create_index(
        "ix_agent_memory_created_at", "agent_memory", ["created_at"],
    )
    # HNSW index pre rýchle vector search
    op.execute(
        "CREATE INDEX ix_agent_memory_embedding ON agent_memory "
        "USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.drop_table("agent_memory")
