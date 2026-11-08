"""Daily schedules referencing tasks, with atomic creation and non-destructive removal."""
from __future__ import annotations
from datetime import date, datetime, time
from sqlalchemy import select, func
from sqlalchemy.dialects.sqlite import insert
from ..db.models import DailyPlanItem, Task
from ..db.session import get_session
from .task_service import TaskCreate, validate_task


class DailyPlanService:
    def __init__(self, session=None):
        self.session = session or get_session()

    @staticmethod
    def _validate(day, starts):
        if not isinstance(day, date) or isinstance(day, datetime):
            raise ValueError("计划日期无效")
        for start in starts:
            if start is not None and (not isinstance(start, time) or start.tzinfo is not None):
                raise ValueError("计划开始时间必须为本地时间")

    def list(self, day, search=None):
        stmt = select(DailyPlanItem, Task).join(Task, DailyPlanItem.task_id == Task.id).where(DailyPlanItem.plan_date == day)
        if search:
            stmt = stmt.where(Task.title.contains(search, autoescape=True) | Task.description.contains(search, autoescape=True))
        stmt = stmt.order_by(DailyPlanItem.planned_start.asc().nullslast(), DailyPlanItem.position, DailyPlanItem.id)
        return list(self.session.execute(stmt).all())

    def _next_position(self, day):
        return (self.session.scalar(select(func.max(DailyPlanItem.position)).where(DailyPlanItem.plan_date == day)) or 0) + 1

    def add_existing(self, day, task_ids):
        self._validate(day, [])
        ids = list(dict.fromkeys(task_ids))
        existing = set(self.session.scalars(select(Task.id).where(Task.id.in_(ids))).all())
        if existing != set(ids):
            raise ValueError("部分任务已不存在，请刷新后重试")
        added = 0
        try:
            position = self._next_position(day)
            for task_id in ids:
                result = self.session.execute(insert(DailyPlanItem).values(plan_date=day, task_id=task_id, position=position)
                    .on_conflict_do_nothing(index_elements=["plan_date", "task_id"]))
                added += result.rowcount
                position += 1
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return added

    def create_tasks(self, day, data: list[TaskCreate], starts=None):
        starts = starts if starts is not None else [None] * len(data)
        if len(starts) != len(data):
            raise ValueError("计划时间与任务数量不一致")
        self._validate(day, starts)
        tasks = [Task(**validate_task(value)) for value in data]
        try:
            position = self._next_position(day)
            self.session.add_all(tasks)
            self.session.flush()
            self.session.add_all([DailyPlanItem(plan_date=day, task_id=t.id, planned_start=start, position=position + index)
                                  for index, (t, start) in enumerate(zip(tasks, starts))])
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return tasks

    def set_start(self, entry_id, start):
        self._validate(date.today(), [start])
        entry = self.session.get(DailyPlanItem, entry_id)
        if entry is None:
            raise ValueError("计划项已不存在，请刷新")
        try:
            entry.planned_start = start
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise

    def remove(self, entry_id):
        entry = self.session.get(DailyPlanItem, entry_id)
        if entry is None:
            return False
        try:
            self.session.delete(entry)
            self.session.commit()
        except Exception:
            self.session.rollback()
            raise
        return True
