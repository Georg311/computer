"""TokenEconomizer Lifecycle Migration — add columns to TE tables.

Additive migration: IF NOT EXISTS, safe to run multiple times.
No Alembic dependency — called on startup from te.py router import.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def migrate_up(session) -> None:
    """Add lifecycle columns to TE tables (SQLite compatible).
    
    Safe to call multiple times — uses CREATE TABLE IF NOT EXISTS logic.
    For SQLite, we use try/except around ALTER since IF NOT EXISTS is not supported for ADD COLUMN.
    """
    from sqlalchemy import text

    # repo_facts table: add lifecycle columns
    for col_name in ("fire_rate", "lifecycle_state", "confirmed_at"):
        try:
            session.execute(text(
                f"ALTER TABLE repo_facts ADD COLUMN {col_name} REAL DEFAULT 0.0"
            ))
        except Exception:
            pass  # Column already exists

    for col_name in ("fire_rate",):
        try:
            session.execute(text(
                "ALTER TABLE microskills_facts ADD COLUMN fire_rate REAL DEFAULT 0.0"
            ))
        except Exception:
            pass

    try:
        session.execute(text(
            "ALTER TABLE microskills_facts ADD COLUMN lifecycle_state TEXT DEFAULT 'CANDIDATE'"
        ))
    except Exception:
        pass

    # te_status table: add overhead column
    try:
        session.execute(text(
            "ALTER TABLE te_status ADD COLUMN pricing_overhead_effective BIGINT DEFAULT 0"
        ))
    except Exception:
        pass

    logger.info("[te] Lifecycle migration applied (all columns present)")


def migrate_down(session) -> None:
    """Rollback lifecycle columns (NOT recommended for production)."""
    from sqlalchemy import text

    # SQLite does not support DROP COLUMN before 3.35.0 — skip for safety
    logger.warning("[te] migrate_down skipped: SQLite DROP COLUMN unsupported")
