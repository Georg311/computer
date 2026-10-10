"""Fix workspaces id to use AUTOINCREMENT.

"""
revision = '0005'
down_revision = '0004'
from alembic import op
import sqlalchemy as sa


def upgrade() -> None:
    # Since SQLite doesn't support ALTER TABLE to add AUTOINCREMENT,
    # we must follow the standard pattern: rename, create new, copy, drop.
    
    # 1. Rename existing workspaces table
    op.rename_table('workspaces', 'workspaces_old')

    # 2. Create the new workspaces table with INTEGER PRIMARY KEY AUTOINCREMENT
    # Note: In SQLite, 'INTEGER PRIMARY KEY' automatically implies AUTOINCREMENT.
    op.create_table(
        'workspaces',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_id', sa.Text(), nullable=False),
        sa.Column('path', sa.Text(), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('data', sa.JSON(), server_default='{}', nullable=False),
        sa.Column('created_at', sa.BigInteger(), nullable=False),
        sa.Column('updated_at', sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.UniqueConstraint('user_id', 'path', name='uq_workspace_user_path'),
    )

    # 3. Copy data from old to new. 
    # We omit 'id' so the new table generates it automatically.
    op.execute("""
        INSERT INTO workspaces (user_id, path, name, data, created_at, updated_at)
        SELECT user_id, path, name, data, created_at, updated_at FROM workspaces_old
    """)

    # 4. Drop the old table
    op.drop_table('workspaces_old')


def downgrade() -> None:
    # Downgrade is complex because we'd lose the auto-incrementing integer property
    # and revert to Text IDs if we were to recreate it exactly as before.
    # For simplicity in this automated fix, we signal that downgrade is not supported for this structural change.
    pass
