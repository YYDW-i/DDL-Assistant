"""提醒脚本入口：由任务计划程序调用。

用法：
    python -m app.reminder            # 正常检查并提醒
    python -m app.reminder --dry-run # 只打印将要提醒的内容，不弹通知不写记录
"""
from __future__ import annotations

import argparse
import logging
import sys

from .. import config
from ..db.session import init_engine, get_session
from .core import collect_due_reminders, mark_notified
from .notifier import show_toast


def _setup_logging():
    log_file = config.log_dir() / "reminder.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="只打印不实际发送/记录")
    args = parser.parse_args(argv)

    _setup_logging()
    init_engine()
    session = get_session()

    items = collect_due_reminders(session)
    logging.info("本轮检查到 %d 条待提醒", len(items))

    for it in items:
        t = it.task
        if it.kind == "overdue":
            title = f"⚠️ 任务已逾期：{t.title}"
            body = f"截止 {it.due_at.strftime('%m-%d %H:%M')}，请尽快处理。"
        else:
            title = f"📌 即将到期：{t.title}"
            body = f"截止 {it.due_at.strftime('%m-%d %H:%M')}（还剩不到一天）"

        if args.dry_run:
            print(f"[dry-run] {title}\n          {body}")
            continue

        ok = show_toast(title, body)
        if ok:
            mark_notified(session, t.id, it.kind, it.due_at)
            logging.info("已提醒 task=%s kind=%s", t.id, it.kind)
        else:
            logging.warning("通知未弹出，不写记录以便下次重试 task=%s", t.id)

    return 0


if __name__ == "__main__":
    sys.exit(main())
