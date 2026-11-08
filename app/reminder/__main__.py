"""Independent reminder command, also used by reminder.exe."""
import argparse
import logging
from ..db.session import init_engine
from ..logging_setup import setup_logging
from ..data_io import backup_if_due
from .runner import run_check
from .notifier import show_toast


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--test-toast", action="store_true", help="Send one real diagnostic notification")
    parser.add_argument("--check-libraries", action="store_true", help="Load notification bindings without sending")
    args = parser.parse_args(argv)
    setup_logging("reminder")
    try:
        if args.check_libraries:
            import json
            from windows_toasts import Toast
            from winrt.windows.ui.notifications import ToastNotificationManager
            from .. import config
            toast = Toast(text_fields=["DDL Assistant", "library check"])
            (config.data_dir() / "reminder-diagnostics.json").write_text(json.dumps({"notification_libraries_loaded": True, "text_fields": toast.text_fields}), encoding="utf-8")
            return 0
        init_engine()
        if args.test_toast:
            return 0 if show_toast("DDL Assistant 通知测试", "这是一条真实测试通知。") else 1
        if not args.dry_run:
            backup_if_due()
        run_check(dry_run=args.dry_run)
        return 0
    except Exception:
        logging.exception("Reminder check failed")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
