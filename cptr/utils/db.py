"""Async database engine and session management."""

from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from cptr.env import DATA_DIR, DB_FILE

_engine = None
_async_session = None


def get_engine():
    global _engine
    if _engine is None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        _engine = create_async_engine(
            f"sqlite+aiosqlite:///{DB_FILE}",
            echo=False,
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _async_session
    if _async_session is None:
        _async_session = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _async_session


async def get_db() -> AsyncSession:
    """Get an async DB session. Use as: async with await get_db() as db:"""
    factory = get_session_factory()
    return factory()


async def init_db():
    """Create tables and run Alembic migrations."""
    # Ensure WAL mode for concurrent reads
    async with get_engine().begin() as conn:
        await conn.exec_driver_sql("PRAGMA journal_mode=WAL")

    # Run Alembic migrations (sync, one-time startup cost)
    from alembic import command
    from alembic.config import Config

    alembic_cfg = Config()
    alembic_cfg.set_main_option("script_location", str(Path(__file__).parent.parent / "migrations"))
    alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite:///{DB_FILE}")
    command.upgrade(alembic_cfg, "head")

    # Seed DB config from config.toml (file is source of truth on startup)
    await _seed_config_from_toml()


async def _seed_config_from_toml():
    """Load [app_config] from config.toml and upsert into the DB config table.

    Called on every startup. The file always wins — this ensures config
    survives DB loss and allows hand-editing the TOML file.

    SKIPS 'bots' key: bot configs are managed via API/DB, not TOML.
    instance-test sanitizes bots to [] in TOML but copies app.db with real bots.
    Seeding from empty TOML would wipe those DB bots on every restart.
    """
    import logging

    logger = logging.getLogger(__name__)

    try:
        from cptr.utils.config import load_app_config_from_toml

        app_config = load_app_config_from_toml()
        if not app_config:
            return

        # Skip 'bots' — bot configs are DB-managed; TOML sanitization would wipe them
        filtered = {k: v for k, v in app_config.items() if k != "bots"}
        if not filtered:
            return

        # Direct DB upsert (not via Config.upsert to avoid re-syncing back to file)
        from cptr.models.config import Config as ConfigModel

        async with get_session_factory()() as db:
            for key, value in filtered.items():
                existing = await db.get(ConfigModel, key)
                if existing:
                    existing.value = value
                else:
                    db.add(ConfigModel(key=key, value=value))
            await db.commit()

        logger.info("Loaded %d config key(s) from config.toml (skipped 'bots')", len(filtered))</parameter>
<parameter=replace_from>
mtgef
    """Load [app_config] from config.toml and upsert into the DB config table.

    Called on every startup. The file always wins — this ensures config
    survives DB loss and allows hand-editing the TOML file.
    """
    import logging

    logger = logging.getLogger(__name__)

    try:
        from cptr.utils.config import load_app_config_from_toml

        app_config = load_app_config_from_toml()
        if not app_config:
            return

        # Direct DB upsert (not via Config.upsert to avoid re-syncing back to file)
        from cptr.models.config import Config as ConfigModel

        async with get_session_factory()() as db:
            for key, value in app_config.items():
                existing = await db.get(ConfigModel, key)
                if existing:
                    existing.value = value
                else:
                    db.add(ConfigModel(key=key, value=value))
            await db.commit()

        logger.info("Loaded %d config key(s) from config.toml", len(app_config))
    except Exception:
        logger.warning("Failed to seed config from config.toml", exc_info=True)
