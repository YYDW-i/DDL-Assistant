from datetime import date, datetime, time, timedelta
import pytest
from sqlalchemy import text
from app.db.models import Task, NotificationLog
from app.db.session import init_engine, get_engine, get_session, reset_engine_for_tests
from app.services.task_service import TaskCreate, TaskService


def test_import_today_reuses_tasks_and_remove_never_deletes_task(temp_db):
    from app.services.plan_service import DailyPlanService
    svc = TaskService(temp_db())
    task = svc.create(TaskCreate(title="已有任务", due_date=date.today(), estimated_hours=1.5))
    plan = DailyPlanService(svc.session)
    assert plan.add_existing(date.today(), [task.id]) == 1
    assert plan.add_existing(date.today(), [task.id]) == 0
    assert svc.session.query(Task).count() == 1
    entry, linked = plan.list(date.today())[0]
    assert linked.id == task.id and linked.estimated_hours == 1.5
    plan.remove(entry.id)
    assert plan.list(date.today()) == []
    assert svc.get(task.id) is not None


def test_plans_have_separate_dates_and_edit_start_does_not_change_deadline(temp_db):
    from app.services.plan_service import DailyPlanService
    svc = TaskService(temp_db())
    t = svc.create(TaskCreate(title="同一大任务", due_date=date(2030, 1, 20), due_time=time(18)))
    plan = DailyPlanService(svc.session)
    day = date(2030, 1, 10)
    plan.add_existing(day, [t.id])
    plan.add_existing(day + timedelta(days=1), [t.id])
    entry = plan.list(day)[0][0]
    plan.set_start(entry.id, time(9))
    assert plan.list(day)[0][0].planned_start == time(9)
    assert plan.list(day + timedelta(days=1))[0][0].planned_start is None
    assert svc.get(t.id).due_date == date(2030, 1, 20)
    assert svc.get(t.id).due_time == time(18)
    svc.complete(t.id)
    assert plan.list(day)[0][1].status == "completed"
    svc.delete(t.id)
    assert plan.list(day) == []


def test_plan_create_is_atomic_and_has_all_task_attributes(temp_db):
    from app.services.plan_service import DailyPlanService
    plan = DailyPlanService(temp_db())
    data = TaskCreate(title="复习", due_date=date.today(), description="章节1", category="学习",
                      due_time=time(20), priority=3, estimated_hours=2.5, source="ai", source_detail="用户原话",
                      reminder_times=["2030-01-01T09:00"])
    with pytest.raises(ValueError):
        plan.create_tasks(date.today(), [data, TaskCreate(title="无日期")], [time(9), None])
    assert plan.session.query(Task).count() == 0
    plan.create_tasks(date.today(), [data], [time(9)])
    entry, t = plan.list(date.today())[0]
    assert (entry.planned_start, t.description, t.category, t.priority, t.estimated_hours, t.source_detail) == (time(9), "章节1", "学习", 3, 2.5, "用户原话")
    assert t.reminder_times == ["2030-01-01T09:00"]
    with pytest.raises(ValueError):
        plan.add_existing(date.today(), [t.id, 999])
    assert len(plan.list(date.today())) == 1


def test_v3_to_v4_migration_preserves_existing_tasks_and_notifications(temp_db):
    svc = TaskService(temp_db())
    t = svc.create(TaskCreate(title="旧任务", due_date=date.today(), reminder_times=["2030-01-01T12:00"]))
    svc.session.add(NotificationLog(task_id=t.id, kind="custom:203001011200", due_at=datetime.now()))
    svc.session.commit()
    path = get_engine().url.database
    with get_engine().begin() as conn:
        conn.execute(text("UPDATE schema_meta SET value='3' WHERE key='schema_version'"))
        conn.exec_driver_sql("DROP TABLE IF EXISTS daily_plan_items")
    svc.session.close()
    reset_engine_for_tests()
    init_engine(path)
    with get_session() as s:
        assert s.get(Task, t.id).title == "旧任务"
        assert s.get(Task, t.id).reminder_times == ["2030-01-01T12:00"]
        assert s.query(NotificationLog).count() == 1
        assert s.execute(text("SELECT value FROM schema_meta WHERE key='schema_version'")).scalar() == "4"
        assert s.execute(text("PRAGMA integrity_check")).scalar() == "ok"
