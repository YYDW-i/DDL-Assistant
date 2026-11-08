"""数据导出/导入：CSV / JSON，以及每日自动备份。"""
from __future__ import annotations

import csv
import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Sequence

from . import config
from .db.models import Task
from .db.session import get_session

logger = logging.getLogger(__name__)


def export_csv(path: Path) -> int:
    session = get_session()
    tasks = session.query(Task).order_by(Task.due_date).all()
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["id", "title", "category", "due_date", "due_time", "all_day",
                    "priority", "status", "estimated_hours", "source", "description"])
        for t in tasks:
            w.writerow([
                t.id, t.title, t.category,
                t.due_date.isoformat(),
                t.due_time.strftime("%H:%M") if t.due_time else "",
                int(t.all_day), t.priority, t.status,
                t.estimated_hours, t.source, t.description,
            ])
    logger.info("导出 %d 条任务到 %s", len(tasks), path)
    return len(tasks)


def export_json(path: Path) -> int:
    session = get_session()
    tasks = session.query(Task).order_by(Task.due_date).all()
    data = [{
        "id": t.id, "title": t.title, "category": t.category,
        "due_date": t.due_date.isoformat(),
        "due_time": t.due_time.strftime("%H:%M") if t.due_time else None,
        "all_day": t.all_day, "priority": t.priority, "status": t.status,
        "estimated_hours": t.estimated_hours, "source": t.source,
        "description": t.description,
    } for t in tasks]
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("导出 %d 条任务到 %s", len(data), path)
    return len(data)


def backup_database() -> Path:
    """复制当前 db 到 backups/ 目录，带时间戳。保留最近 14 份。"""
    src = config.db_path()
    bdir = config.backup_dir()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = bdir / f"ddl_{stamp}.db"
    shutil.copy2(src, dst)
    # 清理旧备份
    backups = sorted(bdir.glob("ddl_*.db"))
    for old in backups[:-14]:
        try:
            old.unlink()
        except OSError:
            pass
    logger.info("数据库已备份到 %s", dst)
    return dst
