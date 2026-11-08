"""任务仓储层：封装所有 SQL 操作，业务层不直接写 SQL。"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Optional, Sequence

from sqlalchemy import select, func, or_
from sqlalchemy.orm import Session

from .models import Task, TaskStatus


class TaskRepository:
    def __init__(self, session: Session):
        self.session = session

    # ---------- 写操作 ----------
    def add(self, task: Task) -> Task:
        self.session.add(task)
        self.session.commit()
        self.session.refresh(task)
        return task

    def update(self, task_id: int, **fields) -> Optional[Task]:
        task = self.get(task_id)
        if task is None:
            return None
        for k, v in fields.items():
            if not hasattr(task, k):
                raise AttributeError(f"Task 没有字段 {k}")
            setattr(task, k, v)
        self.session.commit()
        self.session.refresh(task)
        return task

    def delete(self, task_id: int) -> bool:
        task = self.get(task_id)
        if task is None:
            return False
        self.session.delete(task)
        self.session.commit()
        return True

    def mark_completed(self, task_id: int) -> Optional[Task]:
        return self.update(
            task_id,
            status=TaskStatus.COMPLETED.value,
            completed_at=datetime.now().replace(microsecond=0),
        )

    def mark_pending(self, task_id: int) -> Optional[Task]:
        return self.update(
            task_id,
            status=TaskStatus.PENDING.value,
            completed_at=None,
        )

    # ---------- 读操作 ----------
    def get(self, task_id: int) -> Optional[Task]:
        return self.session.get(Task, task_id)

    def list(
        self,
        status: Optional[str] = None,
        category: Optional[str] = None,
        search: Optional[str] = None,
        due_from: Optional[date] = None,
        due_to: Optional[date] = None,
        include_completed: bool = True,
    ) -> Sequence[Task]:
        stmt = select(Task)

        if status is not None:
            stmt = stmt.where(Task.status == status)
        elif not include_completed:
            stmt = stmt.where(Task.status == TaskStatus.PENDING.value)

        if category:
            stmt = stmt.where(Task.category == category)
        if search:
            like = f"%{search}%"
            stmt = stmt.where(or_(Task.title.like(like), Task.description.like(like)))
        if due_from:
            stmt = stmt.where(Task.due_date >= due_from)
        if due_to:
            stmt = stmt.where(Task.due_date <= due_to)

        # 排序：未完成在前；同状态按截止日期升序，再按时间升序
        # 未完成按日期升序（最急的在前），已完成沉底
        stmt = stmt.order_by(
            Task.status == TaskStatus.COMPLETED.value,  # False 在前
            Task.due_date.asc(),
            Task.due_time.asc().nullsfirst(),
            Task.priority.desc(),
        )
        return list(self.session.execute(stmt).scalars().all())

    # ---------- 视图查询（今日/本周/逾期） ----------
    def list_today(self) -> Sequence[Task]:
        today = date.today()
        return self.list(status=TaskStatus.PENDING.value, due_from=today, due_to=today)

    def list_week(self) -> Sequence[Task]:
        today = date.today()
        # 本周：从今天到本周日（含），未来 7 天
        end = today + timedelta(days=6 - today.weekday())
        return self.list(status=TaskStatus.PENDING.value, due_from=today, due_to=end)

    def list_overdue(self) -> Sequence[Task]:
        today = date.today()
        stmt = select(Task).where(
            Task.status == TaskStatus.PENDING.value,
            Task.due_date < today,
        )
        stmt = stmt.order_by(Task.due_date.asc(), Task.due_time.asc().nullsfirst())
        return list(self.session.execute(stmt).scalars().all())

    def list_all(self) -> Sequence[Task]:
        return self.list()

    def count_by_status(self) -> dict:
        """统计：未完成 / 已完成数量。"""
        rows = self.session.execute(
            select(Task.status, func.count(Task.id)).group_by(Task.status)
        ).all()
        result = {TaskStatus.PENDING.value: 0, TaskStatus.COMPLETED.value: 0}
        for s, c in rows:
            result[s] = c
        return result

    def list_approaching(self, within_hours: int = 24) -> Sequence[Task]:
        """临近 DDL：未完成且截止时间在 now+within_hours 内。"""
        now = datetime.now()
        deadline = now + timedelta(hours=within_hours)
        # 全天任务：当天即算临近
        today = now.date()
        stmt = select(Task).where(Task.status == TaskStatus.PENDING.value)
        out = []
        for t in self.session.execute(stmt).scalars().all():
            if t.all_day or t.due_time is None:
                due_dt = datetime.combine(t.due_date, time(23, 59))
            else:
                due_dt = datetime.combine(t.due_date, t.due_time)
            if now <= due_dt <= deadline:
                out.append(t)
        out.sort(key=lambda x: (x.due_date, x.due_time or time(0, 0)))
        return out
