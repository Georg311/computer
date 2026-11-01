"""add_token_economizer_tables

Revision ID: a1b2c3d4e5f6
Revises: fd5de24c69f4
Create Date: 2026-01-01 00:00:00.000000

Adds four TokenEconomizer tables for per-chat TE state tracking,
tool usage analytics, micro-skill facts, and loop guard envelopes.
"""
from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4e5f6'
down_revision = 'fd5de24c69f4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the four TE tables and their indexes."""
    op.create_table(
        "te_status",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("chat_id", sa.Text(), nullable=False),
        sa.Column("effective_tokens", sa.BigInteger(), server_default="0", nullable=True),
        sa.Column("total_tokens", sa.BigInteger(), server_default="0", nullable=True),
        sa.Column("cache_savings_pct", sa.Integer(), server_default="0", nullable=True),
        sa.Column("pricing_overhead", sa.BigInteger(), server_default="0", nullable=True),
        sa.ForeignKeyConstraint(["chat_id"], ["chats.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_te_status_chat_id"), "te_status", ["chat_id"], unique=False)

    op.create_table(
        "tool_usage",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("chat_id", sa.Text(), nullable=False),
        sa.Column("tool_name", sa.Text(), nullable=False),
        sa.Column("call_count", sa.Integer(), server_default="0", nullable=True),
        sa.Column("first_seen", sa.BigInteger(), server_default="0", nullable=True),
        sa.Column("last_seen", sa.BigInteger(), server_default="0", nullable=True),
        sa.ForeignKeyConstraint(["chat_id"], ["chats.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_tool_usage_chat_id"), "tool_usage", ["chat_id"], unique=False)

    op.create_table(
        "repo_facts",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("chat_id", sa.Text(), nullable=False),
        sa.Column("repo_hash", sa.Text(), nullable=True),
        sa.Column("fact_text", sa.Text(), nullable=False),
        sa.Column("fire_status", sa.Integer(), server_default="0", nullable=True),
        sa.Column("confirmation_count", sa.Integer(), server_default="0", nullable=True),
        sa.Column("active", sa.Boolean(), server_default="1", nullable=True),
        sa.ForeignKeyConstraint(["chat_id"], ["chats.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_repo_facts_chat_id"), "repo_facts", ["chat_id"], unique=False)

    op.create_table(
        "loop_envelope",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("chat_id", sa.Text(), nullable=False),
        sa.Column("envelope_size", sa.Integer(), server_default="0", nullable=True),
        sa.Column("nudges_done", sa.Integer(), server_default="0", nullable=True),
        sa.Column("aborted", sa.Boolean(), server_default="0", nullable=True),
        sa.Column("resolved_turns", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["chat_id"], ["chats.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_loop_envelope_chat_id"), "loop_envelope", ["chat_id"], unique=True)


def downgrade() -> None:
    """Drop the four TE tables in reverse dependency order."""
    op.drop_index(op.f("ix_loop_envelope_chat_id"), table_name="loop_envelope")
    op.drop_table("loop_envelope")
    op.drop_index(op.f("ix_repo_facts_chat_id"), table_name="repo_facts")
    op.drop_table("repo_facts")
    op.drop_index(op.f("ix_tool_usage_chat_id"), table_name="tool_usage")
    op.drop_table("tool_usage")
    op.drop_index(op.f("ix_te_status_chat_id"), table_name="te_status")
    op.drop_table("te_status")
