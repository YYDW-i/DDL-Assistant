from datetime import date, datetime, time
from unittest.mock import patch
from app.db.models import NotificationLog
from app.services.task_service import TaskCreate, TaskService
from app.reminder.core import collect_due_reminders


def test_multiple_custom_times_have_independent_delivery(temp_db):
    svc = TaskService(temp_db())
    svc.create(TaskCreate(title="多个提醒", due_date=date(2030, 1, 3),
                          reminder_times=["2030-01-01T09:00", "2030-01-02T18:00"]))
    from app.reminder.runner import run_check
    sent = []
    send = lambda title, body, **kw: sent.append(title) or True
    assert run_check(now=datetime(2030, 1, 1, 10), send=send) == 1
    assert run_check(now=datetime(2030, 1, 1, 11), send=send) == 0
    assert run_check(now=datetime(2030, 1, 2, 19), send=send) == 1
    assert len(sent) == 2


def test_failed_delivery_can_retry_and_completed_tasks_stop(temp_db):
    svc = TaskService(temp_db())
    task = svc.create(TaskCreate(title="重试", due_date=date(2030, 1, 3)))
    from app.reminder.runner import run_check
    now = datetime(2030, 1, 2, 21)
    assert run_check(now=now, send=lambda *a, **k: False) == 0
    assert run_check(now=now, send=lambda *a, **k: True) == 1
    svc.complete(task.id)
    assert run_check(now=datetime(2030, 1, 4), send=lambda *a, **k: True) == 0


def test_two_processes_do_not_send_same_notification(temp_db, tmp_path):
    import subprocess, sys
    from app.db.session import get_engine
    svc = TaskService(temp_db())
    svc.create(TaskCreate(title="并发", due_date=date(2030, 1, 3)))
    target = tmp_path / "sent.txt"
    code = """
from app.db.session import init_engine
from app.reminder.runner import run_check
from datetime import datetime
import sys, time
init_engine(sys.argv[1])
def send(*a, **kw):
    with open(sys.argv[2], 'a') as f: f.write('sent\\n')
    time.sleep(.1)
    return True
run_check(now=datetime(2030,1,2,21), send=send)
"""
    args = [sys.executable, "-c", code, str(get_engine().url.database), str(target)]
    procs = [subprocess.Popen(args) for _ in range(2)]
    assert [p.wait(timeout=30) for p in procs] == [0, 0]
    assert target.read_text().splitlines() == ["sent"]


def test_real_toast_library_contract():
    from windows_toasts import Toast
    from app.reminder.notifier import show_toast
    with patch("windows_toasts.WindowsToaster") as toaster, patch("winrt.windows.ui.notifications.ToastNotificationManager") as manager:
        toaster.return_value.toastNotifier.setting = 0
        def accepted(toast):
            manager.history.get_history_with_id.return_value = [toast]
        toaster.return_value.show_toast.side_effect = accepted
        assert show_toast("标题", "说明") is True
        toast = toaster.return_value.show_toast.call_args.args[0]
        assert isinstance(toast, Toast)
        assert toast.text_fields == ["标题", "说明"]


def test_late_notification_failure_is_not_marked_delivered():
    import threading
    from app.reminder.notifier import show_toast
    with patch("windows_toasts.WindowsToaster") as toaster, patch("winrt.windows.ui.notifications.ToastNotificationManager") as manager:
        toaster.return_value.toastNotifier.setting = 0
        manager.history.get_history_with_id.return_value = []
        def delayed(toast):
            timer = threading.Timer(.4, lambda: toast.on_failed(None))
            timer.start()
        toaster.return_value.show_toast.side_effect = delayed
        assert show_toast("不会成功", "延迟失败") is False


def test_minimum_date_does_not_block_other_reminders(temp_db):
    svc = TaskService(temp_db())
    svc.create(TaskCreate(title="最早日期", due_date=date.min))
    svc.create(TaskCreate(title="正常任务", due_date=date(2030, 1, 3)))
    from app.reminder.runner import run_check
    assert run_check(now=datetime(2030, 1, 2, 21), send=lambda *a, **k: True) == 2
