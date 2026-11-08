"""Run backups and reminder checks outside the GUI event loop."""
import logging
from PySide6.QtCore import QThread
from ..data_io import backup_if_due
from ..reminder.runner import run_check


class MaintenanceWorker(QThread):
    def run(self):
        try:
            backup_if_due()
        except Exception:
            logging.exception("Automatic backup failed")
        try:
            run_check()
        except Exception:
            logging.exception("Reminder check failed")
