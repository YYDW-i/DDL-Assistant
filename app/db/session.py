"""数据库引擎与会话管理：初始化、版本化迁移。

设计原则：
- 升级时绝不删除用户数据；新增列用 server_default，缺失时补默认值。
- 首次运行 create_all；后续按 schema_meta 中的版本号逐步迁移。
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .. import config
from .models import Base, SchemaMeta

logger = logging.getLogger(__name__)

CURRENT_SCHEMA_VERSION = "1"

_engine: Optional[Engine] = None
_SessionFactory: Optional[sessionmaker] = None


def _resolve_db_path(db_path: Optional[Path] = None) -> Path:
    return Path(db_path) if db_path else config.db_path()


def init_engine(db_path: Optional[Path] = None) -> Engine:
    """初始化全局引擎。可传入自定义路径（测试用临时库）。"""
    global _engine, _SessionFactory
    path = _resolve_db_path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    url = f"sqlite:///{path.as_posix()}"
    _engine = create_engine(url, echo=False, future=True)
    _SessionFactory = sessionmaker(bind=_engine, expire_on_commit=False, future=True)
    _migrate(_engine)
    return _engine


def get_engine() -> Engine:
    if _engine is None:
        return init_engine()
    return _engine


def get_session() -> Session:
    if _SessionFactory is None:
        init_engine()
    assert _SessionFactory is not None
    return _SessionFactory()


def _migrate(engine: Engine) -> None:
    """建表并按版本号应用迁移。"""
    # 1. 建出所有尚未存在的表
    Base.metadata.create_all(engine)

    # 2. 读取/写入版本号
    with engine.begin() as conn:
        row = conn.execute(
            text("SELECT value FROM schema_meta WHERE key='schema_version'")
        ).fetchone()
        current = row[0] if row else "0"

    if current == CURRENT_SCHEMA_VERSION:
        logger.info("数据库已是最新版本 v%s", current)
        return

    logger.info("数据库迁移：v%s -> v%s", current, CURRENT_SCHEMA_VERSION)

    # 后续迁移在此按版本顺序追加，例如：
    # if current < "2": _migrate_to_v2(engine)

    with engine.begin() as conn:
        conn.execute(
            text("INSERT INTO schema_meta (key, value) VALUES ('schema_version', :v) "
                 "ON CONFLICT(key) DO UPDATE SET value=:v"),
            {"v": CURRENT_SCHEMA_VERSION},
        )
    logger.info("数据库迁移完成，当前版本 v%s", CURRENT_SCHEMA_VERSION)


def reset_engine_for_tests() -> None:
    """测试辅助：清空全局引擎引用。"""
    global _engine, _SessionFactory
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionFactory = None
