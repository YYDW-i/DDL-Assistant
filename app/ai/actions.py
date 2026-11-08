"""Apply a previously previewed set of AI changes atomically, with stale-data checks."""
import json
from datetime import datetime
from sqlalchemy import text
from ..db.models import Task, NotificationLog
from ..services.task_service import TaskCreate, validate_task


def snapshot(task):
    fields = list(TaskCreate.__dataclass_fields__) + ["status", "updated_at", "completed_at"]
    return {key: getattr(task, key) for key in fields}


def apply_actions(actions, expected, session):
    # End any earlier read transaction, then lock before checking the preview snapshot.
    session.rollback()
    session.execute(text("BEGIN IMMEDIATE"))
    try:
        targets = {}
        for action in actions:
            if action.task_id in targets:
                raise ValueError("同一任务有多条操作，请重新请求合并建议")
            task = session.get(Task, action.task_id, populate_existing=True)
            if task is None or action.task_id not in expected or snapshot(task) != expected[action.task_id]:
                raise ValueError("任务已发生变化，请重新查询并预览")
            targets[action.task_id] = task
        for action in actions:
            task = targets[action.task_id]
            if action.action == "update":
                values = {key: getattr(task, key) for key in TaskCreate.__dataclass_fields__}
                values.update(action.fields.model_dump(exclude_unset=True))
                validated = validate_task(TaskCreate(**values))
                changed = any(getattr(task, key) != validated[key] for key in ("due_date", "due_time", "all_day", "reminder_times"))
                for key, value in validated.items():
                    setattr(task, key, value)
                if changed:
                    session.query(NotificationLog).filter_by(task_id=task.id).delete()
            elif action.action == "delete":
                session.query(NotificationLog).filter_by(task_id=task.id).delete()
                session.delete(task)
            elif action.action == "complete":
                task.status, task.completed_at = "completed", datetime.now().replace(microsecond=0)
            elif action.action == "reopen":
                task.status, task.completed_at = "pending", None
                session.query(NotificationLog).filter_by(task_id=task.id).delete()
        session.commit()
    except Exception:
        session.rollback()
        raise
