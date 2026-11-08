"""端到端冒烟测试：覆盖创建→查询→完成→导出→备份全链路（临时库）。"""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

from app.db.session import init_engine, get_session
from app.services.task_service import TaskCreate, TaskService
from app import data_io


def test_e2e_flow(tmp_path, monkeypatch):
    db = tmp_path / "e2e.db"
    init_engine(db)
    svc = TaskService(get_session())

    # 创建两条任务
    t1 = svc.create(TaskCreate(
        title="数据结构实验报告",
        category="课程",
        due_date=date.today() + timedelta(days=2),
        source="manual",
    ))
    t2 = svc.create(TaskCreate(
        title="社团招新",
        category="活动",
        due_date=date.today() - timedelta(days=1),
    ))

    # 今日视图
    today = svc.list_view("today")
    assert all(x.id not in (t1.id, t2.id) or x.due_date == date.today() for x in today)

    # 逾期
    overdue = svc.list_view("overdue")
    assert any(x.id == t2.id for x in overdue)

    # 完成
    svc.complete(t1.id)
    assert svc.get(t1.id).status == "completed"

    # 导出 CSV / JSON
    csv_path = tmp_path / "t.csv"
    json_path = tmp_path / "t.json"
    n_csv = data_io.export_csv(csv_path)
    n_json = data_io.export_json(json_path)
    assert n_csv == 2
    assert n_json == 2
    assert csv_path.exists()
    assert json_path.exists()

    # 备份
    backup_path = data_io.backup_database()
    assert backup_path.exists()
