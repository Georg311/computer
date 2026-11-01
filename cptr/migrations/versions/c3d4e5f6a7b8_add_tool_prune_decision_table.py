"""Add tool_prune_decision table

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2025-01-01

Add per-chat tool pruning decisions (applied deny-list).
"""
from alembic import op
import sqlalchemy as sa

revision = 'c3d4e5f6a7b8'
down_revision = 'b2c3d4e5f6a7'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'tool_prune_decision',
        sa.Column('id', sa.Text(), nullable=False),
        sa.Column('chat_id', sa.Text(), nullable=False),
        sa.Column('tool_name', sa.Text(), nullable=False),
        sa.Column('applied_at', sa.BigInteger(), default=0, server_default='0'),
        sa.ForeignKeyConstraint(['chat_id'], ['chats.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('chat_id', 'tool_name', name='_uk_chat_tool'),
    )
    op.create_index(op.f('ix_tool_prune_decision_chat_id'), 'tool_prune_decision', ['chat_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_tool_prune_decision_chat_id'), table_name='tool_prune_decision')
    op.drop_table('tool_prune_decision')
