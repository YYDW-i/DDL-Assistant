"""仓储层与服务层测试。"""
from __future__ import annotations

from datetime import date, time, timedelta

import pytest

from app.db.models import Task, TaskStatus
from app.db.repository import TaskRepository
from app.services.task_service import TaskCreate, TaskService


def _make_task(**kw) -> Task:
    defaults = dict(
        title="测试任务",
        due_date=date.today() + timedelta(days=3),
        status=TaskStatus.PENDING.value,
    )
    defaults.update(kw)
    return Task(**defaults)


class TestRepository:
    def test_add_and_get(self, temp_db):
        s = temp_db()
        repo = TaskRepository(s)
        t = repo.add(_make_task(title="写实验报告"))
        assert t.id is not None
        got = repo.get(t.id)
        assert got is not None
        assert got.title == "写实验报告"

    def test_update(self, temp_db):
        s = temp_db()
        repo = TaskRepository(s)
        t = repo.add(_make_task(title="旧标题"))
        repo.update(t.id, title="新标题")
        assert repo.get(t.id).title == "新标题"

    def test_delete(self, temp_db):
        s = temp_db()
        repo = TaskRepository(s)
        t = repo.add(_make_task())
        assert repo.delete(t.id) is True
        assert repo.get(t.id) is None
        assert repo.delete(t.id) is False

    def test_mark_completed_sets_time(self, temp_db):
        s = temp_db()
        repo = TaskRepository(s)
        t = repo.add(_make_task())
        repo.mark_completed(t.id)
        got = repo.get(t.id)
        assert got.status == TaskStatus.COMPLETED.value
        assert got.completed_at is not None

    def test_list_today_filters(self, temp_db):
        s = temp_db()
        repo = TaskRepository(s)
        repo.add(_make_task(title="今天", due_date=date.today()))
        repo.add(_make_task(title="未来", due_date=date.today() + timedelta(days=5)))
        repo.add(_make_task(title="昨天", due_date=date.today() - timedelta(days=1)))
        today = repo.list_today()
        assert len(today) == 1
        assert today[0].title == "今天"

    def test_list_overdue(self, temp_db):
        s = temp_db()
        repo = TaskRepository(s)
        repo.add(_make_task(due_date=date.today() - timedelta(days=2)))
        repo.add(_make_task(due_date=date.today()))
        overdue = repo.list_overdue()
        assert len(overdue) == 1
        assert (overdue[0].due_date - date.today()).days == -2

    def test_sort_pending_before_completed(self, temp_db):
        s = temp_db()
        repo = TaskRepository(s)
        repo.add(_make_task(title="完成的", due_date=date.today(), status=TaskStatus.COMPLETED.value))
        repo.add(_make_task(title="待办", due_date=date.today() + timedelta(days=1)))
        items = repo.list()
        assert items[0].title == "待办"
        assert items[-1].title == "完成的"

    def test_search(self, temp_db):
        s = temp_db()
        repo = TaskRepository(s)
        repo.add(_make_task(title="数据结构作业", description=""))
        repo.add(_make_task(title="体育打卡", description=""))
        result = repo.list(search="数据结构")
        assert len(result) == 1
        assert result[0].title == "数据结构作业"

    def test_count_by_status(self, temp_db):
        s = temp_db()
        repo = TaskRepository(s)
        repo.add(_make_task())
        repo.add(_make_task())
        repo.mark_completed(1) if repo.get(1) else None
        counts = repo.count_by_status()
        assert counts[TaskStatus.PENDING.value] >= 0
        assert TaskStatus.COMPLETED.value in counts


class TestTaskService:
    def test_create_requires_title(self, temp_db):
        s = temp_db()
        svc = TaskService(s)
        with pytest.raises(ValueError):
            svc.create(TaskCreate(title="   ", due_date=date.today()))

    def test_create_requires_due_date(self, temp_db):
        s = temp_db()
        svc = TaskService(s)
        with pytest.raises(ValueError):
            svc.create(TaskCreate(title="无日期"))

    def test_all_day_clears_time(self, temp_db):
        s = temp_db()
        svc = TaskService(s)
        t = svc.create(TaskCreate(
            title="全天考试",
            due_date=date.today(),
            all_day=True,
            due_time=time(10, 0),
        ))
        assert t.all_day is True
        assert t.due_time is None

    def test_complete_and_reopen(self, temp_db):
        s = temp_db()
        svc = TaskService(s)
        t = svc.create(TaskCreate(title="x", due_date=date.today()))
        svc.complete(t.id)
        assert svc.get(t.id).status == TaskStatus.COMPLETED.value
        svc.reopen(t.id)
        assert svc.get(t.id).status == TaskStatus.PENDING.value
        assert svc.get(t.id).completed_at is None

    def test_stats(self, temp_db):
        s = temp_db()
        svc = TaskService(s)
        svc.create(TaskCreate(title="a", due_date=date.today()))
        svc.create(TaskCreate(title="b", due_date=date.today() - timedelta(days=1)))
        st = svc.stats()
        assert st["today"] == 1
        assert st["overdue"] == 1
        assert st["pending"] >= 2
