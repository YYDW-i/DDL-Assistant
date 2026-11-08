"""CSV/JSON round trips and consistent SQLite online backups."""
from __future__ import annotations
import csv
import json
import logging
import sqlite3
from contextlib import closing
from dataclasses import fields
from datetime import date, datetime, time
from pathlib import Path

from . import config
from .db.models import Task
from .db.session import get_engine, get_session
from .services.task_service import TaskCreate, validate_task

logger = logging.getLogger(__name__)
TASK_FIELDS = [f.name for f in fields(TaskCreate)]
EXPORT_FIELDS = ["id"] + TASK_FIELDS + ["status", "created_at", "updated_at", "completed_at"]


def _records():
    with get_session() as session:
        return [{key: _serialize(getattr(t, key)) for key in EXPORT_FIELDS}
                for t in session.query(Task).order_by(Task.due_date).all()]


def _serialize(value):
    return value.isoformat() if isinstance(value, (date, time, datetime)) else value


def export_json(path: Path) -> int:
    data = _records()
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(data)


def export_csv(path: Path) -> int:
    data = _records()
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=EXPORT_FIELDS)
        writer.writeheader()
        for row in data:
            row["reminder_times"] = json.dumps(row["reminder_times"])
            writer.writerow(row)
    return len(data)


def read_import(path: Path) -> list[dict]:
    path = Path(path)
    if path.suffix.lower() == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as f:
            raw = list(csv.DictReader(f))
    elif path.suffix.lower() == ".json":
        raw = json.loads(path.read_text(encoding="utf-8-sig"))
    else:
        raise ValueError("仅支持 CSV / JSON")
    if not isinstance(raw, list):
        raise ValueError("导入内容必须是任务列表")
    result = []
    for index, row in enumerate(raw, 1):
        try:
            values = {k: v for k, v in row.items() if k in TASK_FIELDS}
            values["due_date"] = date.fromisoformat(values.get("due_date") or "")
            values["due_time"] = time.fromisoformat(values["due_time"]) if values.get("due_time") else None
            if "all_day" in values and not isinstance(values["all_day"], bool):
                if str(values["all_day"]).lower() not in ("true", "false", "1", "0"):
                    raise ValueError("全天字段无效")
                values["all_day"] = str(values["all_day"]).lower() in ("true", "1")
            values["priority"] = int(values.get("priority", 2))
            values["estimated_hours"] = float(values.get("estimated_hours", 0))
            if isinstance(values.get("reminder_times"), str):
                values["reminder_times"] = json.loads(values["reminder_times"] or "null")
            values = validate_task(TaskCreate(**values))
            status = row.get("status") or "pending"
            if status not in ("pending", "completed"):
                raise ValueError("状态无效")
            values["status"] = status
            for key in ("created_at", "updated_at", "completed_at"):
                if row.get(key):
                    dt = datetime.fromisoformat(row[key])
                    if dt.tzinfo:
                        raise ValueError("时间戳应为本地时间")
                    values[key] = dt
            if status == "completed" and not values.get("completed_at"):
                values["completed_at"] = datetime.now()
            result.append(values)
        except (ValueError, TypeError, AttributeError) as exc:
            raise ValueError(f"第 {index} 条任务无效：{exc}") from exc
    return result


def import_records(records: list[dict]) -> int:
    # records must originate from read_import; never update existing IDs.
    with get_session() as session:
        try:
            session.add_all([Task(**row) for row in records])
            session.commit()
        except Exception:
            session.rollback()
            raise
    logger.info("Imported %d tasks", len(records))
    return len(records)


def import_tasks(path: Path) -> int:
    return import_records(read_import(path))


def backup_database(destination_dir=None) -> Path:
    source = Path(get_engine().url.database)
    bdir = Path(destination_dir) if destination_dir else config.backup_dir()
    bdir.mkdir(parents=True, exist_ok=True)
    target = bdir / f"ddl_{datetime.now():%Y%m%d_%H%M%S_%f}.db"
    partial = target.with_suffix(".tmp")
    try:
        with closing(sqlite3.connect(source)) as src, closing(sqlite3.connect(partial)) as dst:
            src.backup(dst)
            if dst.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise RuntimeError("备份完整性检查失败")
        partial.replace(target)
    except Exception:
        partial.unlink(missing_ok=True)
        raise
    for old in sorted(bdir.glob("ddl_*.db"))[:-14]:
        old.unlink(missing_ok=True)
    logger.info("Database backed up to %s", target)
    return target


def backup_if_due(destination_dir=None):
    bdir = Path(destination_dir) if destination_dir else config.backup_dir()
    existing = sorted(bdir.glob(f"ddl_{datetime.now():%Y%m%d}_*.db"))
    if existing:
        return existing[-1]
    return backup_database(destination_dir=bdir)
