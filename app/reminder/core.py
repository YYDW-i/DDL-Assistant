"""提醒核心逻辑：纯函数，不弹系统通知，便于单元测试。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session

from ..db.models import NotificationLog, Task, TaskStatus

# 默认提醒：截止前一天 20:00
DEFAULT_REMINDER_DAYS_BEFORE = 1
DEFAULT_REMINDER_HOUR = 20
DEFAULT_REMINDER_MINUTE = 0


def due_datetime(task: Task) -> datetime:
    """任务截止的精确时刻。"""
    if task.all_day or task.due_time is None:
        return datetime.combine(task.due_date, time(23, 59))
    return datetime.combine(task.due_date, task.due_time)


def default_reminder_time(task: Task) -> datetime:
    """默认计划提醒时刻：截止前一天 20:00。

    若截止日就是今天（前一天已过），则提前 1 小时。
    """
    due = due_datetime(task)
    candidate = (due - timedelta(days=DEFAULT_REMINDER_DAYS_BEFORE)).replace(
        hour=DEFAULT_REMINDER_HOUR,
        minute=DEFAULT_REMINDER_MINUTE,
        second=0,
        microsecond=0,
    )
    if candidate >= due:
        candidate = due - timedelta(hours=1)
    return candidate


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
    notified = set(
        (r.task_id, r.kind)
        for r in session.execute(select(NotificationLog)).scalars().all()
    )

    out: list[ReminderItem] = []
    for t in rows:
        due = due_datetime(t)
        if now >= due:
            if (t.id, "overdue") not in notified:
                out.append(ReminderItem(task=t, kind="overdue", due_at=due))
            continue
        schedule = [("scheduled", default_reminder_time(t))] if t.reminder_times is None else [
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
