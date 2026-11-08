"""Desktop entry point and explicit diagnostic commands."""
import argparse
import json
import logging
import os
import sys
from pathlib import Path
from . import config
from .logging_setup import setup_logging


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-check", action="store_true", help="Open the GUI briefly, record diagnostics, then exit")
    parser.add_argument("--register-identity", action="store_true")
    parser.add_argument("--shortcut-path", default=None)
    args = parser.parse_args(argv)
    setup_logging()
    if args.register_identity:
        from .windows_identity import register_shortcut
        frozen = getattr(sys, "frozen", False)
        target = sys.executable
        arguments = "" if frozen else f'"{Path(__file__).resolve().parents[1] / "launcher.py"}"'
        register_shortcut(target, arguments, args.shortcut_path)
        return 0
    from PySide6.QtCore import QLockFile, QTimer
    from PySide6.QtWidgets import QApplication, QMessageBox
    from PySide6.QtGui import QFontDatabase, QFont
    from .db.session import init_engine
    app = QApplication([sys.argv[0]])
    # Explicit fallback also supports isolated diagnostic sessions.
    font_file = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts/msyh.ttc"
    if font_file.exists():
        font_id = QFontDatabase.addApplicationFont(str(font_file))
        families = QFontDatabase.applicationFontFamilies(font_id)
        if families:
            app.setFont(QFont(families[0], 10))
    app.setApplicationName("DDL Assistant")
    app.setQuitOnLastWindowClosed(False)
    if os.name == "nt":
        import ctypes
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("DDLAssistant.Desktop")
    lock = QLockFile(str(config.data_dir() / "gui.lock"))
    if not lock.tryLock(100):
        QMessageBox.information(None, "DDL Assistant", "程序已在运行，请从系统托盘打开。")
        return 0
    try:
        init_engine()
        from .ui.main_window import MainWindow
        win = MainWindow()
        win.show()

        def report_exception(kind, value, traceback):
            logging.error("Unhandled exception", exc_info=(kind, value, traceback))
            QMessageBox.critical(win, "操作失败", f"{value}\n详情见数据目录 logs/app.log。")
        sys.excepthook = report_exception
        if args.self_check:
            def check():
                from .data_io import backup_if_due
                from .ui.ai_dialog import AIDialog
                from .ui.query_dialog import QueryDialog
                from .ui.settings_dialog import SettingsDialog
                for kind in (AIDialog, QueryDialog, SettingsDialog):
                    dialog = kind(win)
                    dialog.close()
                win._switch_view("calendar")
                win._switch_view("plan")
                win.grab().save(str(config.data_dir() / "plan-self-check.png"))
                win._switch_view("all")
                win.grab().save(str(config.data_dir() / "self-check.png"))
                path = backup_if_due()
                (config.data_dir() / "self-check.json").write_text(json.dumps({
                    "gui_ready": win.isVisible(), "database": str(config.db_path()),
                    "backup": str(path), "stats": win.service.stats(),
                    "python": sys.version, "frozen": bool(getattr(sys, "frozen", False)),
                    "daily_plan_ready": win.plan_view.table is not None
                }, ensure_ascii=False, indent=2), encoding="utf-8")
                win._quit_app()
            QTimer.singleShot(500, check)
        return app.exec()
    except Exception as exc:
        logging.exception("Startup failed")
        QMessageBox.critical(None, "DDL Assistant 无法启动", f"{exc}\n日志：{config.log_dir()}")
        return 1
    finally:
        lock.unlock()


if __name__ == "__main__":
    raise SystemExit(main())
