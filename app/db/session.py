"""SQLite initialization and additive, versioned migrations."""
from __future__ import annotations
import logging
from pathlib import Path
from contextlib import closing
from sqlalchemy import create_engine, event, inspect, text
from sqlalchemy.orm import Session, sessionmaker
from .. import config
from .models import Base
from .locking import initialization_lock

logger = logging.getLogger(__name__)
CURRENT_SCHEMA_VERSION = "3"
_engine = None
_SessionFactory = None


def init_engine(db_path=None):
    path = Path(db_path) if db_path else config.db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with initialization_lock(path):
        return _init_engine(path)


def _init_engine(db_path):
    global _engine, _SessionFactory
    path = Path(db_path) if db_path else config.db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"sqlite:///{path.as_posix()}", connect_args={"timeout": 30})

    @event.listens_for(engine, "connect")
    def configure(dbapi, _):
        dbapi.execute("PRAGMA busy_timeout=30000")
        dbapi.execute("PRAGMA foreign_keys=ON")
        dbapi.execute("PRAGMA journal_mode=WAL")

    try:
        _migrate(engine)
    except Exception:
        engine.dispose()
        raise
    if _engine is not None:
        _engine.dispose()
    _engine = engine
    _SessionFactory = sessionmaker(bind=engine, expire_on_commit=False)
    return engine


def get_engine():
    return _engine if _engine is not None else init_engine()


def get_session() -> Session:
    if _SessionFactory is None:
        init_engine()
    return _SessionFactory()


def _migrate(engine):
    tables = inspect(engine).get_table_names()
    current = 0
    if "schema_meta" in tables:
        with engine.connect() as conn:
            current = int(conn.execute(text("SELECT value FROM schema_meta WHERE key='schema_version'")).scalar() or 0)
    if current > int(CURRENT_SCHEMA_VERSION):
        raise RuntimeError(f"数据库版本 v{current} 高于程序支持版本，请使用新版程序。")
    if "tasks" in tables and current < int(CURRENT_SCHEMA_VERSION):
        import sqlite3
        from datetime import datetime
        source = Path(engine.url.database)
        dest = source.parent / "backups"
        dest.mkdir(exist_ok=True)
        with closing(sqlite3.connect(source)) as src, closing(sqlite3.connect(dest / f"migration_{datetime.now():%Y%m%d_%H%M%S_%f}.db")) as dst:
            src.backup(dst)
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.exec_driver_sql("BEGIN IMMEDIATE")
        columns = {c["name"] for c in inspect(conn).get_columns("tasks")}
        additions = {
            "estimated_hours": "FLOAT NOT NULL DEFAULT 0",
            "source": "VARCHAR(20) NOT NULL DEFAULT 'manual'",
            "source_detail": "TEXT NOT NULL DEFAULT ''",
            "reminder_times": "JSON",
        }
        for name, ddl in additions.items():
            if name not in columns:
                conn.exec_driver_sql(f"ALTER TABLE tasks ADD COLUMN {name} {ddl}")
        for action in ("INSERT", "UPDATE"):
            conn.exec_driver_sql(f"""CREATE TRIGGER IF NOT EXISTS validate_tasks_{action.lower()}
                BEFORE {action} ON tasks WHEN
                NEW.title IS NULL OR length(trim(NEW.title)) NOT BETWEEN 1 AND 200
                OR NEW.due_date IS NULL OR NEW.priority NOT BETWEEN 1 AND 4
                OR NEW.estimated_hours < 0 OR NEW.status NOT IN ('pending','completed')
                BEGIN SELECT RAISE(ABORT, 'Invalid task fields'); END""")
        conn.execute(text("INSERT INTO schema_meta(key,value) VALUES ('schema_version',:v) ON CONFLICT(key) DO UPDATE SET value=:v"), {"v": CURRENT_SCHEMA_VERSION})
    logger.info("Database ready, schema v%s", CURRENT_SCHEMA_VERSION)


def reset_engine_for_tests():
    global _engine, _SessionFactory
    if _engine is not None:
        _engine.dispose()
    _engine = _SessionFactory = None
