"""提醒核心逻辑：纯函数，不弹系统通知，便于单元测试。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session

from ..db.models import NotificationLog, Task, TaskStatus

# Default offsets are relative to the actual deadline (all-day = 23:59).
DEFAULT_REMINDER_HOURS = (72, 24, 3)


def due_datetime(task: Task) -> datetime:
    """任务截止的精确时刻。"""
    if task.all_day or task.due_time is None:
        return datetime.combine(task.due_date, time(23, 59))
    return datetime.combine(task.due_date, task.due_time)


def default_reminder_times(task: Task) -> list[datetime]:
    due = due_datetime(task)
    return [max(datetime.min, due - timedelta(hours=hours))
            if due >= datetime.min + timedelta(hours=hours) else datetime.min
            for hours in DEFAULT_REMINDER_HOURS]


def default_reminder_time(task: Task) -> datetime:
    """Compatibility helper for the 24 hour reminder."""
    return default_reminder_times(task)[1]


@dataclass
class ReminderItem:
    task: Task
    kind: str  # "scheduled" | "overdue"
    due_at: datetime


def collect_due_reminders(session: Session, now: Optional[datetime] = None) -> Sequence[ReminderItem]:
    """扫描未完成任务，返回需要提醒且尚未提醒的条目。

    - scheduled：到了默认提醒时刻、但还没到截止时刻
    - overdue：已过截止时刻（覆盖关机/休眠期间错过的提醒，开机后补推）
    """
    now = now or datetime.now().replace(microsecond=0)
    rows = session.execute(
        select(Task).where(Task.status == TaskStatus.PENDING.value)
    ).scalars().all()

    # 已通知记录
    logs = session.execute(select(NotificationLog)).scalars().all()
    notified = {(r.task_id, r.kind) for r in logs}
    legacy = {r.task_id: r.notified_at for r in logs if r.kind == "scheduled"}

    out: list[ReminderItem] = []
    for t in rows:
        due = due_datetime(t)
        if now >= due:
            if (t.id, "overdue") not in notified:
                out.append(ReminderItem(task=t, kind="overdue", due_at=due))
            continue
        if t.reminder_times is None:
            elapsed = [(f"scheduled:{hours}h", at) for hours, at in zip(DEFAULT_REMINDER_HOURS, default_reminder_times(t)) if at <= now]
            if elapsed:
                kind, at = elapsed[-1]
                # Latest elapsed slot covers older missed slots; future slots remain active.
                if (t.id, kind) not in notified and legacy.get(t.id, datetime.min) < at:
                    out.append(ReminderItem(task=t, kind=kind, due_at=due))
            continue
        schedule = [
            ("custom:" + datetime.fromisoformat(value).strftime("%Y%m%d%H%M"), datetime.fromisoformat(value))
            for value in t.reminder_times
        ]

        # 计划提醒：now 已到提醒时刻，且尚未到截止时刻
        for kind, rem in schedule:
            if rem <= now < due and (t.id, kind) not in notified:
                out.append(ReminderItem(task=t, kind=kind, due_at=due))

    out.sort(key=lambda x: x.due_at)
    return out


def mark_notified(session: Session, task_id: int, kind: str, due_at: datetime, commit=True) -> None:
    """写入通知记录（去重）。"""
    session.execute(insert(NotificationLog).values(task_id=task_id, kind=kind, due_at=due_at).on_conflict_do_nothing(index_elements=["task_id", "kind"]))
    if commit:
        session.commit()


def reset_reminders_for_task(session: Session, task_id: int) -> None:
    """任务被修改后，清空其通知记录，以便新的提醒能正常触发。"""
    session.query(NotificationLog).filter(NotificationLog.task_id == task_id).delete()
    session.commit()
