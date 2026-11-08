"""程序入口。"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from . import config
from .db.session import init_engine


def _setup_logging():
    log_file = config.log_dir() / "app.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )


def main():
    _setup_logging()
    init_engine()  # 初始化数据库

    app = QApplication(sys.argv)
    app.setApplicationName("DDL Assistant")

    from .ui.main_window import MainWindow
    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
