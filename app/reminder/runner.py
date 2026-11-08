"""Shared reminder dispatcher. No Qt, Ollama or UI imports."""
import logging
from sqlalchemy import text
from .core import collect_due_reminders, mark_notified
from .notifier import show_toast
from ..db.session import get_session

logger = logging.getLogger(__name__)


def run_check(now=None, send=None, dry_run=False):
    send = send or show_toast
    delivered = 0
    with get_session() as session:
        # Lock before reading. Concurrent GUI / scheduled processes cannot both send.
        session.execute(text("BEGIN IMMEDIATE"))
        try:
            for item in collect_due_reminders(session, now=now):
                title = f"{'任务已逾期' if item.kind == 'overdue' else '任务提醒'}：{item.task.title}"
                body = f"截止 {item.due_at:%Y-%m-%d %H:%M}"
                if dry_run:
                    logger.info("[dry-run] %s %s", title, body)
                    continue
                if send(title, body, tag=f"{item.task.id}:{item.kind}"):
                    mark_notified(session, item.task.id, item.kind, item.due_at, commit=False)
                    delivered += 1
                else:
                    logger.warning("Notification not accepted; will retry task=%s", item.task.id)
            session.commit()
        except Exception:
            session.rollback()
            raise
    return delivered
