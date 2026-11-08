"""月历视图：在日历上标记有任务的日期，点击日期查看当天任务。"""
from __future__ import annotations

from datetime import date, timedelta

from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QColor, QTextCharFormat, QBrush
from PySide6.QtWidgets import (
    QCalendarWidget,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..db.models import Task
from ..services.task_service import TaskService


class CalendarView(QWidget):
    def __init__(self, service: TaskService, parent=None):
        super().__init__(parent)
        self.service = service
        layout = QHBoxLayout(self)

        self.calendar = QCalendarWidget()
        self.calendar.setVerticalHeaderFormat(QCalendarWidget.NoVerticalHeader)
        self.calendar.clicked.connect(self._on_date_clicked)
        layout.addWidget(self.calendar, stretch=2)

        right = QVBoxLayout()
        self.day_title = QLabel("选择日期")
        self.day_title.setStyleSheet("font-size:16px;font-weight:700;")
        right.addWidget(self.day_title)
        self.day_list = QListWidget()
        right.addWidget(self.day_list, stretch=1)
        layout.addLayout(right, stretch=3)

        self._mark_days()

    def _mark_days(self):
        """给有未完成任务的日期加红点标记。"""
        all_tasks = self.service.repo.list(status="pending")
        marked: dict[date, int] = {}
        for t in all_tasks:
            marked[t.due_date] = marked.get(t.due_date, 0) + 1
        for d, cnt in marked.items():
            qd = QDate(d.year, d.month, d.day)
            fmt = QTextCharFormat()
            fmt.setBackground(QBrush(QColor("#4a7dff")))
            fmt.setForeground(QBrush(QColor("#ffffff")))
            self.calendar.setDateTextFormat(qd, fmt)

    def _on_date_clicked(self, qd: QDate):
        d = date(qd.year(), qd.month(), qd.day())
        self.day_title.setText(d.strftime("%Y-%m-%d"))
        self.day_list.clear()
        tasks = self.service.repo.list(status="pending", due_from=d, due_to=d)
        if not tasks:
            self.day_list.addItem("当天无任务")
            return
        for t in tasks:
            due_str = t.due_time.strftime("%H:%M") if t.due_time else "全天"
            item = QListWidgetItem(f"{'🔴' if t.priority>=3 else '⚪'} {t.title}  ({due_str})")
            self.day_list.addItem(item)
