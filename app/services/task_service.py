"""Validated task operations; each user action commits as one transaction."""
from __future__ import annotations
import logging
import math
from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta
from typing import Optional
from ..db.models import NotificationLog, Task
from ..db.repository import TaskRepository
from ..db.session import get_session

logger = logging.getLogger(__name__)


@dataclass
class TaskCreate:
    title: str
    description: str = ""
    category: str = ""
    due_date: Optional[date] = None
    due_time: Optional[time] = None
    all_day: bool = False
    priority: int = 2
    estimated_hours: float = 0.0
    source: str = "manual"
    source_detail: str = ""
    reminder_times: Optional[list[str]] = None


def validate_task(data: TaskCreate) -> dict:
    fields = asdict(data)
    title = data.title.strip()
    if not 1 <= len(title) <= 200:
        raise ValueError("标题必须包含 1–200 个字符")
    if not isinstance(data.due_date, date) or isinstance(data.due_date, datetime):
        raise ValueError("必须指定有效截止日期；未识别日期请手动补充")
    if data.due_time is not None and (not isinstance(data.due_time, time) or data.due_time.tzinfo):
        raise ValueError("截止时间必须是本地时间")
    if data.priority not in (1, 2, 3, 4):
        raise ValueError("重要程度必须是 1–4")
    if not math.isfinite(data.estimated_hours) or data.estimated_hours < 0:
        raise ValueError("预计工作量必须是非负有限数值")
    if len(data.category) > 50 or len(data.source) > 20:
        raise ValueError("分类或来源过长")
    if data.reminder_times is not None:
        if not isinstance(data.reminder_times, list) or len(data.reminder_times) > 50:
            raise ValueError("最多设置50个自定义提醒")
        normalized = []
        for value in data.reminder_times:
            dt = datetime.fromisoformat(value)
            if dt.tzinfo is not None:
                raise ValueError("提醒必须使用本地时间，不含时区")
            normalized.append(dt.isoformat(timespec="minutes"))
        fields["reminder_times"] = sorted(set(normalized))
    fields["title"], fields["category"] = title, data.category.strip()
    if data.all_day:
        fields["due_time"] = None
    return fields


class TaskService:
    def __init__(self, session=None):
        self.session = session or get_session()
        self.repo = TaskRepository(self.session)

    def create(self, data: TaskCreate) -> Task:
        return self.create_many([data])[0]

    def create_many(self, items: list[TaskCreate]) -> list[Task]:
        tasks = [Task(**validate_task(item)) for item in items]
        try:
            self.session.add_all(tasks)
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        logger.info("Created %d tasks", len(tasks))
        return tasks

    def update(self, task_id, **fields):
        task = self.get(task_id)
        if task is None:
            return None
        allowed = TaskCreate.__dataclass_fields__
        if set(fields) - allowed.keys():
            raise ValueError("包含不可修改的字段")
        merged = {key: getattr(task, key) for key in allowed}
        merged.update(fields)
        validated = validate_task(TaskCreate(**merged))
        schedule_changed = any(getattr(task, k) != validated[k] for k in ("due_date", "due_time", "all_day", "reminder_times"))
        try:
            for key, value in validated.items():
                setattr(task, key, value)
            if schedule_changed:
                self.session.query(NotificationLog).filter_by(task_id=task_id).delete()
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        logger.info("Updated task=%s schedule_changed=%s", task_id, schedule_changed)
        return task

    def delete(self, task_id):
        task = self.get(task_id)
        if task is None:
            return False
        try:
            self.session.query(NotificationLog).filter_by(task_id=task_id).delete()
            self.session.delete(task)
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        logger.info("Deleted task=%s", task_id)
        return True

    def complete(self, task_id):
        task = self.get(task_id)
        if task is not None:
            try:
                task.status = "completed"
                task.completed_at = datetime.now().replace(microsecond=0)
                self.session.commit()
            except Exception:
                self.session.rollback()
                raise
        return task

    def reopen(self, task_id):
        task = self.get(task_id)
        if task is not None:
            try:
                task.status, task.completed_at = "pending", None
                self.session.query(NotificationLog).filter_by(task_id=task_id).delete()
                self.session.commit()
            except Exception:
                self.session.rollback()
                raise
        return task

    def get(self, task_id):
        return self.repo.get(task_id)

    def list_view(self, view, search=None):
        today = date.today()
        if view == "today":
            return self.repo.list(status="pending", due_from=today, due_to=today, search=search)
        if view == "week":
            start = today - timedelta(days=today.weekday())
            return self.repo.list(status="pending", due_from=start, due_to=start + timedelta(days=6), search=search)
        if view == "overdue":
            return [t for t in self.repo.list(status="pending", search=search) if self._due(t) <= datetime.now()]
        return self.repo.list(search=search)

    @staticmethod
    def _due(task):
        return datetime.combine(task.due_date, task.due_time if not task.all_day and task.due_time else time(23, 59))

    def stats(self):
        counts = self.repo.count_by_status()
        return {"pending": counts.get("pending", 0), "completed": counts.get("completed", 0),
                "today": len(self.list_view("today")), "overdue": len(self.list_view("overdue")),
                "approaching": len(self.repo.list_approaching())}
