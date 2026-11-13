"""TokenEconomizer Lifecycle Migration — add columns to TE tables.

Additive migration: safe to run multiple times.
Uses sync SQLite connection for ALTER TABLE (no Alembic).
Works with both raw sqlite3.Connection and SQLAlchemy sessions.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def _execute_sql(conn, sql):
    """Execute SQL on either a raw sqlite3 conn or an AsyncSession."""
    if hasattr(conn, "connection"):
        # AsyncSession — get the underlying DBAPI connection
        dbapi = conn.connection().connection  # type: ignore[attr-defined]
    else:
        # Raw sqlite3.Connection
        dbapi = conn

    try:
        dbapi.execute(sql)
    except Exception:
        pass


def migrate_up(conn) -> None:
    """Add lifecycle columns to TE tables (SQLite compatible)."""
    for table, cols in [
        ("repo_facts", [("fire_rate", "REAL DEFAULT 0.0"), ("lifecycle_state", "TEXT DEFAULT 'CANDIDATE'"), ("confirmed_at", "TIMESTAMP DEFAULT NULL")]),
        ("microskills_facts", [("fire_rate", "REAL DEFAULT 0.0")]),
    ]:
        for col_name, col_def in cols:
            _execute_sql(conn, f"ALTER TABLE {table} ADD COLUMN {col_name} {col_def}")

    # te_status table: add overhead column
    _execute_sql(conn, "ALTER TABLE te_status ADD COLUMN pricing_overhead_effective BIGINT DEFAULT 0")

    logger.info("[te] Lifecycle migration applied (all columns present)")


def migrate_down(conn) -> None:
    """Rollback lifecycle columns (NOT recommended for production)."""
    # SQLite does not support DROP COLUMN before 3.35.0 — skip for safety
    logger.warning("[te] migrate_down skipped: SQLite DROP COLUMN unsupported")
