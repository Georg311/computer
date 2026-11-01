"""Add microskills_facts table

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2025-01-01

Adds the `microskills_facts` table for rule-based fact learning
(envfacts profile). Each row stores a learned operating fact for a chat,
with confirmation tracking and fire-status monitoring.

Columns:
  - id             (TEXT PRIMARY KEY)
  - chat_id        (TEXT, FK → chats.id)
  - repo_hash      (TEXT, nullable)
  - fact_text      (TEXT NOT NULL)
  - fire_status    (BOOLEAN, default FALSE)
  - confirmation_count (INTEGER, default 0)
  - active         (BOOLEAN, default TRUE)
"""
from alembic import op
import sqlalchemy as sa

revision = 'd4e5f6a7b8c9'
down_revision = 'c3d4e5f6a7b8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the microskills_facts table and its indexes."""
    op.create_table(
        "microskills_facts",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("chat_id", sa.Text(), nullable=False),
        sa.Column("repo_hash", sa.Text(), nullable=True),
        sa.Column("fact_text", sa.Text(), nullable=False),
        sa.Column("fire_status", sa.Boolean(), server_default="0", nullable=True),
        sa.Column("confirmation_count", sa.Integer(), server_default="0", nullable=True),
        sa.Column("active", sa.Boolean(), server_default="1", nullable=True),
        sa.ForeignKeyConstraint(
            ["chat_id"],
            ["chats.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_microskills_facts_chat_id"),
        "microskills_facts",
        ["chat_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop the microskills_facts table."""
    op.drop_index(
        op.f("ix_microskills_facts_chat_id"),
        table_name="microskills_facts",
    )
    op.drop_table("microskills_facts")
