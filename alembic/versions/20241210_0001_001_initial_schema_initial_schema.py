"""Initial schema - PostgreSQL unified stack

Revision ID: 001_initial_schema
Revises:
Create Date: 2024-12-10

Creates core tables for:
- LangGraph checkpoints (conversation persistence)
- Document embeddings (pgvector RAG)
- Prompts (LangFuse local storage)
- Apache AGE graph initialization
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001_initial_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Enable required extensions
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")

    # Note: Apache AGE must be enabled by superuser and is handled separately
    # See docs/POSTGRESQL_EXTENSIONS_SETUP.md

    # ==========================================================================
    # LangGraph Checkpoints Table
    # ==========================================================================
    op.create_table(
        "langgraph_checkpoints",
        sa.Column("thread_id", sa.String(255), nullable=False),
        sa.Column("checkpoint_id", sa.String(255), nullable=False),
        sa.Column("parent_id", sa.String(255), nullable=True),
        sa.Column("checkpoint", postgresql.JSONB, nullable=False),
        sa.Column("checkpoint_compressed", sa.LargeBinary, nullable=True),
        sa.Column("metadata", postgresql.JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("expires_at", sa.DateTime, nullable=True),
        sa.PrimaryKeyConstraint("thread_id", "checkpoint_id"),
    )

    op.create_index("idx_checkpoints_thread", "langgraph_checkpoints", ["thread_id"])
    op.create_index("idx_checkpoints_expires", "langgraph_checkpoints", ["expires_at"])
    op.create_index("idx_checkpoints_parent", "langgraph_checkpoints", ["parent_id"])

    # ==========================================================================
    # Document Embeddings Table (pgvector)
    # ==========================================================================
    op.create_table(
        "document_embeddings",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("collection_name", sa.String(100), nullable=False),
        sa.Column("document_id", sa.String(255), nullable=False),
        sa.Column("chunk_id", sa.Integer, server_default="0", nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        # Vector column - created via raw SQL due to pgvector type
        sa.Column("metadata", postgresql.JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("collection_name", "document_id", "chunk_id", name="uq_doc_chunk"),
    )

    # Add vector column (SQLAlchemy doesn't have native pgvector support)
    op.execute("ALTER TABLE document_embeddings ADD COLUMN embedding vector(1536)")

    op.create_index("idx_embeddings_collection", "document_embeddings", ["collection_name"])
    op.create_index("idx_embeddings_document", "document_embeddings", ["document_id"])

    # Create HNSW index for fast vector similarity search
    op.execute("""
        CREATE INDEX idx_embeddings_vector ON document_embeddings
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)

    # ==========================================================================
    # Prompts Table (LangFuse local storage)
    # ==========================================================================
    op.create_table(
        "prompts",
        sa.Column("id", sa.String(100), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("version", sa.String(20), server_default="1.0.0", nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("description", sa.Text, server_default=""),
        sa.Column("variables", postgresql.JSONB, server_default="[]"),
        sa.Column("default_values", postgresql.JSONB, server_default="{}"),
        sa.Column("model_hint", sa.String(100), nullable=True),
        sa.Column("temperature_hint", sa.Float, nullable=True),
        sa.Column("max_tokens_hint", sa.Integer, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("is_default", sa.Boolean, server_default="false"),
        sa.Column("ab_test_group", sa.String(100), nullable=True),
        sa.Column("ab_test_weight", sa.Float, nullable=True),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("idx_prompts_type", "prompts", ["type"])
    op.create_index("idx_prompts_active", "prompts", ["is_active"])
    op.create_index("idx_prompts_default", "prompts", ["is_default"])

    # ==========================================================================
    # Audit Log Table
    # ==========================================================================
    op.create_table(
        "audit_logs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "timestamp", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False
        ),
        sa.Column("user_id", sa.String(100), nullable=True),
        sa.Column("session_id", sa.String(100), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("resource_type", sa.String(100), nullable=True),
        sa.Column("resource_id", sa.String(255), nullable=True),
        sa.Column("details", postgresql.JSONB, server_default="{}"),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("success", sa.Boolean, server_default="true"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("idx_audit_timestamp", "audit_logs", ["timestamp"])
    op.create_index("idx_audit_user", "audit_logs", ["user_id"])
    op.create_index("idx_audit_action", "audit_logs", ["action"])
    op.create_index("idx_audit_resource", "audit_logs", ["resource_type", "resource_id"])

    # ==========================================================================
    # Sessions Table
    # ==========================================================================
    op.create_table(
        "sessions",
        sa.Column("id", sa.String(100), nullable=False),
        sa.Column("user_id", sa.String(100), nullable=False),
        sa.Column("data", postgresql.JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("expires_at", sa.DateTime, nullable=False),
        sa.Column("last_accessed", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("idx_sessions_user", "sessions", ["user_id"])
    op.create_index("idx_sessions_expires", "sessions", ["expires_at"])

    # ==========================================================================
    # TWS Instances Table
    # ==========================================================================
    op.create_table(
        "tws_instances",
        sa.Column("id", sa.String(100), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("host", sa.String(255), nullable=False),
        sa.Column("port", sa.Integer, server_default="31116"),
        sa.Column("protocol", sa.String(10), server_default="https"),
        sa.Column("username", sa.String(100), nullable=True),
        sa.Column("password_encrypted", sa.Text, nullable=True),
        sa.Column("is_active", sa.Boolean, server_default="true"),
        sa.Column("is_default", sa.Boolean, server_default="false"),
        sa.Column("metadata", postgresql.JSONB, server_default="{}"),
        sa.Column("created_at", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_index("idx_tws_active", "tws_instances", ["is_active"])


def downgrade() -> None:
    # Drop tables in reverse order
    op.drop_table("tws_instances")
    op.drop_table("sessions")
    op.drop_table("audit_logs")
    op.drop_table("prompts")
    op.drop_table("document_embeddings")
    op.drop_table("langgraph_checkpoints")

    # Note: Extensions are not dropped to avoid affecting other databases
