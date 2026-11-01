"""add_session_cost_usd_to_te_status

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-01-15 00:00:00.000000

Adds session_cost_usd column to te_status table for tracking USD costs.
"""
from alembic import op
import sqlalchemy as sa

revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add session_cost_usd column to te_status table."""
    op.add_column(
        "te_status",
        sa.Column("session_cost_usd", sa.Float(), server_default="0.0", nullable=True),
    )


def downgrade() -> None:
    """Remove session_cost_usd column from te_status table."""
    op.drop_column("te_status", "session_cost_usd")
