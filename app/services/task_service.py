"""任务业务逻辑：对外暴露的高层接口，UI 与后续 AI 层都走这里。"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Optional, Sequence

from ..db.models import Task, TaskStatus
from ..db.repository import TaskRepository
from ..db.session import get_session


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


class TaskService:
    def __init__(self, session=None):
        self.session = session or get_session()
        self.repo = TaskRepository(self.session)

    def create(self, data: TaskCreate) -> Task:
        if not data.title.strip():
            raise ValueError("任务标题不能为空")
        if data.due_date is None:
            raise ValueError("必须指定截止日期")
        task = Task(
            title=data.title.strip(),
            description=data.description,
            category=data.category.strip(),
            due_date=data.due_date,
            due_time=None if data.all_day else data.due_time,
            all_day=data.all_day,
            priority=data.priority,
            estimated_hours=data.estimated_hours,
            source=data.source,
        )
        return self.repo.add(task)

    def update(self, task_id: int, **fields) -> Optional[Task]:
        # 若改为全天，清空 due_time
        if fields.get("all_day"):
            fields["due_time"] = None
        return self.repo.update(task_id, **fields)

    def delete(self, task_id: int) -> bool:
        return self.repo.delete(task_id)

    def complete(self, task_id: int) -> Optional[Task]:
        return self.repo.mark_completed(task_id)

    def reopen(self, task_id: int) -> Optional[Task]:
        return self.repo.mark_pending(task_id)

    def get(self, task_id: int) -> Optional[Task]:
        return self.repo.get(task_id)

    def list_view(self, view: str, search: Optional[str] = None) -> Sequence[Task]:
        """view: today / week / all / overdue"""
        if view == "today":
            return self.repo.list_today()
        if view == "week":
            return self.repo.list_week()
        if view == "overdue":
            return self.repo.list_overdue()
        # all：默认未完成优先 + 搜索
        return self.repo.list(search=search, include_completed=False)

    def stats(self) -> dict:
        counts = self.repo.count_by_status()
        return {
            "pending": counts.get(TaskStatus.PENDING.value, 0),
            "completed": counts.get(TaskStatus.COMPLETED.value, 0),
            "today": len(self.repo.list_today()),
            "overdue": len(self.repo.list_overdue()),
            "approaching": len(self.repo.list_approaching()),
        }
