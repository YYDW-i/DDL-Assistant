from datetime import date, datetime, time, timedelta
from app.db.models import Task, NotificationLog
from app.services.task_service import TaskService, TaskCreate
from app.reminder.core import collect_due_reminders, mark_notified


def test_default_reminders_fire_at_72_24_3_hours_and_deduplicate(temp_db):
    svc = TaskService(temp_db())
    due = datetime(2030, 1, 10, 18)
    task = svc.create(TaskCreate(title="三次提醒", due_date=due.date(), due_time=due.time()))
    for hours in (72, 24, 3):
        now = due - timedelta(hours=hours)
        assert collect_due_reminders(svc.session, now - timedelta(seconds=1)) == []
        items = collect_due_reminders(svc.session, now)
        assert [(i.task.id, i.kind) for i in items] == [(task.id, f"scheduled:{hours}h")]
        mark_notified(svc.session, task.id, items[0].kind, due)
        assert collect_due_reminders(svc.session, now) == []


def test_missed_default_reminders_catch_up_once_and_keep_next_slot(temp_db):
    svc = TaskService(temp_db())
    t = svc.create(TaskCreate(title="补推", due_date=date(2030, 1, 10), due_time=time(18)))
    now = datetime(2030, 1, 10, 10)
    items = collect_due_reminders(svc.session, now)
    assert [i.kind for i in items] == ["scheduled:24h"]
    mark_notified(svc.session, t.id, items[0].kind, items[0].due_at)
    assert collect_due_reminders(svc.session, now) == []
    assert [i.kind for i in collect_due_reminders(svc.session, datetime(2030, 1, 10, 15))] == ["scheduled:3h"]


def test_legacy_delivery_is_respected_and_custom_times_unchanged(temp_db):
    svc = TaskService(temp_db())
    t = svc.create(TaskCreate(title="旧默认", due_date=date(2030, 1, 10), due_time=time(12)))
    svc.session.add(NotificationLog(task_id=t.id, kind="scheduled", due_at=datetime(2030, 1, 10, 12), notified_at=datetime(2030, 1, 9, 20)))
    svc.session.commit()
    assert collect_due_reminders(svc.session, datetime(2030, 1, 10, 8)) == []
    assert [i.kind for i in collect_due_reminders(svc.session, datetime(2030, 1, 10, 9))] == ["scheduled:3h"]
    custom = ["2030-01-10T10:15"]
    other = svc.create(TaskCreate(title="自定义", due_date=date(2030, 1, 10), due_time=time(12), reminder_times=custom))
    assert other.reminder_times == custom
    assert not any(i.task.id == other.id for i in collect_due_reminders(svc.session, datetime(2030, 1, 10, 10)))
