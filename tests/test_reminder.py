"""提醒核心逻辑测试。"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta

from app.db.models import Task, TaskStatus
from app.reminder.core import (
    collect_due_reminders,
    default_reminder_time,
    due_datetime,
    mark_notified,
    reset_reminders_for_task,
)


def _pending(**kw) -> Task:
    defaults = dict(
        title="t",
        due_date=date.today() + timedelta(days=3),
        status=TaskStatus.PENDING.value,
        all_day=False,
    )
    defaults.update(kw)
    return Task(**defaults)


class TestDueTime:
    def test_due_datetime_timed(self):
        t = _pending(due_time=time(14, 30))
        assert due_datetime(t) == datetime.combine(t.due_date, time(14, 30))

    def test_due_datetime_all_day(self):
        t = _pending(all_day=True)
        assert due_datetime(t).time() == time(23, 59)

    def test_default_reminder_24_hours_before(self):
        t = _pending(due_date=date(2030, 1, 10), due_time=time(12, 0))
        r = default_reminder_time(t)
        assert r == datetime(2030, 1, 9, 12, 0)


class TestCollect:
    def _add(self, session, task: Task) -> Task:
        session.add(task)
        session.commit()
        session.refresh(task)
        return task

    def test_scheduled_fires_at_reminder_time(self, temp_db):
        s = temp_db()
        # 截止：明天 12:00；默认提醒：今天 20:00
        t = self._add(s, _pending(
            due_date=date.today() + timedelta(days=1),
            due_time=time(12, 0),
        ))
        # 现在：今天 20:30，已过提醒时刻
        now = datetime.now().replace(hour=20, minute=30, second=0, microsecond=0)
        items = collect_due_reminders(s, now=now)
        kinds = [(i.task.id, i.kind) for i in items]
        assert (t.id, "scheduled:24h") in kinds

    def test_notify_dedup(self, temp_db):
        s = temp_db()
        t = self._add(s, _pending(
            due_date=date.today() + timedelta(days=1),
            due_time=time(12, 0),
        ))
        now = datetime.now().replace(hour=20, minute=30, second=0, microsecond=0)
        items = collect_due_reminders(s, now=now)
        assert len(items) == 1
        mark_notified(s, t.id, items[0].kind, items[0].due_at)
        # 再查一次，不应再出现
        items2 = collect_due_reminders(s, now=now)
        assert all(i.task.id != t.id for i in items2)

    def test_overdue_catchup(self, temp_db):
        s = temp_db()
        # 昨天截止
        t = self._add(s, _pending(
            due_date=date.today() - timedelta(days=1),
            due_time=time(9, 0),
        ))
        now = datetime.now().replace(hour=10, minute=0)
        items = collect_due_reminders(s, now=now)
        kinds = [(i.task.id, i.kind) for i in items]
        assert (t.id, "overdue") in kinds

    def test_completed_not_reminded(self, temp_db):
        s = temp_db()
        self._add(s, _pending(
            due_date=date.today() - timedelta(days=1),
            status=TaskStatus.COMPLETED.value,
        ))
        now = datetime.now()
        items = collect_due_reminders(s, now=now)
        assert len(items) == 0

    def test_reset_reminders_allows_refire(self, temp_db):
        s = temp_db()
        t = self._add(s, _pending(
            due_date=date.today() - timedelta(days=1),
            due_time=time(9, 0),
        ))
        now = datetime.now().replace(hour=10, minute=0)
        items = collect_due_reminders(s, now=now)
        mark_notified(s, t.id, items[0].kind, items[0].due_at)
        assert collect_due_reminders(s, now=now) == []
        reset_reminders_for_task(s, t.id)
        assert len(collect_due_reminders(s, now=now)) == 1
