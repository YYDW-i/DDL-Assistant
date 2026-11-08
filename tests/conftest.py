"""pytest 公共 fixture：使用临时数据库，绝不碰真实数据。"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pytest

# 让 tests 能 import app 包
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# 系统 Temp 目录权限受限，把 pytest 临时目录重定向到项目内
_TMP = ROOT / ".pytest-tmp"
_TMP.mkdir(exist_ok=True)
tempfile.tempdir = str(_TMP)


@pytest.fixture(autouse=True)
def isolated_appdata(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    from app.db.session import reset_engine_for_tests
    reset_engine_for_tests()
    yield
    reset_engine_for_tests()


@pytest.fixture()
def temp_db(tmp_path, monkeypatch):
    """把数据库路径重定向到临时目录，初始化后返回 session 工厂。"""
    db_file = tmp_path / "test.db"
    from app.db import session as session_mod
    session_mod.reset_engine_for_tests()
    engine = session_mod.init_engine(db_file)
    yield session_mod.get_session
    session_mod.reset_engine_for_tests()
    engine.dispose()
