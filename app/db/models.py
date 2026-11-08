"""SQLAlchemy 数据模型。

任务字段严格对应需求：
标题、描述、分类、截止日期、截止时间、是否全天、重要程度、状态、
创建时间、预计工作量、来源信息。
"""
from __future__ import annotations

from datetime import date, datetime, time
from enum import Enum
from typing import Optional

from sqlalchemy import Date, DateTime, Float, Integer, String, Text, Time, Boolean, Index, JSON, CheckConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TaskStatus(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"


class Priority(int, Enum):
    """重要程度：数字越大越重要。"""

    LOW = 1
    MEDIUM = 2
    HIGH = 3
    URGENT = 4


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", server_default="")

    category: Mapped[str] = mapped_column(String(50), default="", server_default="")

    # 截止：日期必填；全天事项时 due_time 为 None
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    due_time: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    all_day: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")

    priority: Mapped[int] = mapped_column(Integer, default=Priority.MEDIUM.value)

    status: Mapped[str] = mapped_column(String(20), default=TaskStatus.PENDING.value)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now().replace(microsecond=0)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now().replace(microsecond=0),
        onupdate=lambda: datetime.now().replace(microsecond=0),
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # 预计工作量（小时）
    estimated_hours: Mapped[float] = mapped_column(Float, default=0.0, server_default="0")

    # 来源：manual / ai
    source: Mapped[str] = mapped_column(String(20), default="manual", server_default="manual")
    source_detail: Mapped[str] = mapped_column(Text, default="", server_default="")
    reminder_times: Mapped[Optional[list]] = mapped_column(JSON(none_as_null=True), nullable=True)

    __table_args__ = (
        Index("ix_tasks_status_date", "status", "due_date"),
        CheckConstraint("length(trim(title)) BETWEEN 1 AND 200", name="ck_task_title"),
        CheckConstraint("priority BETWEEN 1 AND 4", name="ck_task_priority"),
        CheckConstraint("estimated_hours >= 0", name="ck_task_hours"),
        CheckConstraint("status IN ('pending', 'completed')", name="ck_task_status"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Task id={self.id} title={self.title!r} due={self.due_date}>"


class SchemaMeta(Base):
    """记录当前数据库 schema 版本，用于后续迁移。"""

    __tablename__ = "schema_meta"

    key: Mapped[str] = mapped_column(String(50), primary_key=True)
    value: Mapped[str] = mapped_column(String(200), default="")


class NotificationLog(Base):
    """提醒发送记录：用于去重，避免重复弹窗。"""

    __tablename__ = "notification_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[int] = mapped_column(Integer, index=True)
    # 提醒类型："scheduled"（计划提醒）/ "overdue"（逾期补推）
    kind: Mapped[str] = mapped_column(String(20))
    due_at: Mapped[datetime] = mapped_column(DateTime)
    notified_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now().replace(microsecond=0)
    )

    __table_args__ = (
        # 同一任务同一类型只发一次
        Index("ix_notif_task_kind", "task_id", "kind", unique=True),
    )
