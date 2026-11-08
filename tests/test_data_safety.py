from datetime import date, datetime, time, timedelta
import json
import sqlite3

import pytest
from sqlalchemy import text

from app import data_io
from app.db.models import NotificationLog, Task
from app.db.session import get_engine, init_engine, reset_engine_for_tests
from app.services.task_service import TaskCreate, TaskService


def test_all_includes_completed_and_search_filters_every_view(temp_db):
    svc = TaskService(temp_db())
    first = svc.create(TaskCreate(title="数学", due_date=date.today()))
    svc.create(TaskCreate(title="英语", due_date=date.today()))
    svc.complete(first.id)
    assert first.id in [t.id for t in svc.list_view("all")]
    assert [t.title for t in svc.list_view("today", search="英语")] == ["英语"]
    assert svc.list_view("today", search="不存在") == []


@pytest.mark.parametrize("fields", [{"title": " "}, {"priority": 9}, {"estimated_hours": -1}, {"due_date": None}])
def test_update_rejects_invalid_values_and_keeps_original(temp_db, fields):
    svc = TaskService(temp_db())
    t = svc.create(TaskCreate(title="原任务", due_date=date.today()))
    with pytest.raises(ValueError):
        svc.update(t.id, **fields)
    assert svc.get(t.id).title == "原任务"


def test_title_change_preserves_notification_and_delete_cleans_it(temp_db):
    svc = TaskService(temp_db())
    t = svc.create(TaskCreate(title="原任务", due_date=date.today()))
    svc.session.add(NotificationLog(task_id=t.id, kind="scheduled", due_at=datetime.now()))
    svc.session.commit()
    svc.update(t.id, title="新标题")
    assert svc.session.query(NotificationLog).count() == 1
    svc.delete(t.id)
    assert svc.session.query(NotificationLog).count() == 0


def test_batch_create_is_atomic(temp_db):
    svc = TaskService(temp_db())
    with pytest.raises(ValueError):
        svc.create_many([TaskCreate(title="有效", due_date=date.today()), TaskCreate(title="缺日期")])
    assert svc.repo.list() == []


def test_backup_uses_active_database_and_is_readable(temp_db, tmp_path):
    svc = TaskService(temp_db())
    svc.create(TaskCreate(title="备份内容", due_date=date.today()))
    path = data_io.backup_database(destination_dir=tmp_path / "backups")
    with sqlite3.connect(path) as conn:
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert conn.execute("SELECT title FROM tasks").fetchone()[0] == "备份内容"
    assert data_io.backup_if_due(destination_dir=path.parent) == path


@pytest.mark.parametrize("suffix", ["json", "csv"])
def test_import_export_roundtrip_and_invalid_file_rolls_back(temp_db, tmp_path, suffix):
    svc = TaskService(temp_db())
    t = svc.create(TaskCreate(title="导入导出", due_date=date.today(), estimated_hours=1.5))
    svc.complete(t.id)
    path = tmp_path / f"tasks.{suffix}"
    getattr(data_io, f"export_{suffix}")(path)
    svc.delete(t.id)
    assert data_io.import_tasks(path) == 1
    restored = svc.repo.list()[0]
    assert restored.status == "completed" and restored.estimated_hours == 1.5
    assert restored.created_at is not None
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps([{"title": "有效", "due_date": date.today().isoformat()}, {"title": "无日期"}]), encoding="utf-8")
    with pytest.raises(ValueError):
        data_io.import_tasks(bad)
    assert len(svc.repo.list()) == 1


def test_future_schema_is_rejected_without_rewriting_version(temp_db):
    engine = get_engine()
    path = engine.url.database
    with engine.begin() as conn:
        conn.execute(text("UPDATE schema_meta SET value='999' WHERE key='schema_version'"))
    reset_engine_for_tests()
    with pytest.raises(RuntimeError, match="版本"):
        init_engine(path)
    with sqlite3.connect(path) as conn:
        assert conn.execute("SELECT value FROM schema_meta WHERE key='schema_version'").fetchone()[0] == "999"


def test_v2_migration_keeps_tasks(tmp_path):
    path = tmp_path / "old.db"
    with sqlite3.connect(path) as conn:
        conn.executescript("""
        CREATE TABLE schema_meta (key TEXT PRIMARY KEY, value TEXT);
        INSERT INTO schema_meta VALUES ('schema_version', '2');
        CREATE TABLE tasks (id INTEGER PRIMARY KEY, title TEXT NOT NULL, description TEXT NOT NULL DEFAULT '', category TEXT NOT NULL DEFAULT '', due_date DATE NOT NULL, due_time TIME, all_day BOOLEAN NOT NULL DEFAULT 0, priority INTEGER NOT NULL DEFAULT 2, status TEXT NOT NULL DEFAULT 'pending', created_at DATETIME NOT NULL, updated_at DATETIME NOT NULL, completed_at DATETIME, estimated_hours FLOAT NOT NULL DEFAULT 0, source TEXT NOT NULL DEFAULT 'manual');
        INSERT INTO tasks (title,due_date,created_at,updated_at) VALUES ('旧数据','2030-01-01','2026-01-01 00:00:00','2026-01-01 00:00:00');
        """)
    reset_engine_for_tests()
    init_engine(path)
    from app.db.session import get_session
    with get_session() as s:
        t = s.query(Task).one()
        assert t.title == "旧数据" and t.reminder_times is None
    reset_engine_for_tests()
