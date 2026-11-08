"""新建/编辑任务对话框。"""
from __future__ import annotations

from datetime import date, datetime, time
from typing import Optional

from PySide6.QtCore import QDate, QTime
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QPlainTextEdit,
    QSpinBox,
    QTimeEdit,
    QDateEdit,
)

from ..db.models import Task


class TaskDialog(QDialog):
    def __init__(self, parent=None, task: Optional[Task] = None):
        super().__init__(parent)
        self.setWindowTitle("编辑任务" if task else "新建任务")
        self.setMinimumWidth(460)
        self._build_ui()
        if task:
            self._load(task)

    def _build_ui(self):
        form = QFormLayout(self)
        form.setSpacing(10)

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("例如：提交数据结构课程设计报告")
        form.addRow("标题 *", self.title_edit)

        self.category_edit = QLineEdit()
        self.category_edit.setPlaceholderText("课程 / 竞赛 / 活动 / 个人…")
        form.addRow("分类", self.category_edit)

        self.due_date = QDateEdit()
        self.due_date.setCalendarPopup(True)
        self.due_date.setDate(QDate.currentDate())
        form.addRow("截止日期 *", self.due_date)

        self.all_day = QCheckBox("全天事项")
        self.all_day.stateChanged.connect(self._on_all_day_changed)
        form.addRow("", self.all_day)

        self.due_time = QTimeEdit()
        self.due_time.setDisplayFormat("HH:mm")
        self.due_time.setTime(QTime(23, 59))
        form.addRow("截止时间", self.due_time)

        self.priority = QComboBox()
        self.priority.addItem("低", 1)
        self.priority.addItem("中", 2)
        self.priority.addItem("高", 3)
        self.priority.addItem("紧急", 4)
        self.priority.setCurrentIndex(1)
        form.addRow("重要程度", self.priority)

        self.hours = QSpinBox()
        self.hours.setRange(0, 1000)
        self.hours.setSuffix(" 小时")
        form.addRow("预计工作量", self.hours)

        self.desc = QPlainTextEdit()
        self.desc.setPlaceholderText("补充说明、链接、要求…")
        self.desc.setMinimumHeight(80)
        form.addRow("描述", self.desc)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_ok)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _on_all_day_changed(self, state: int):
        self.due_time.setEnabled(state == 0)

    def _load(self, task: Task):
        self.title_edit.setText(task.title)
        self.category_edit.setText(task.category)
        self.due_date.setDate(QDate(task.due_date.year, task.due_date.month, task.due_date.day))
        self.all_day.setChecked(task.all_day)
        if task.due_time:
            self.due_time.setTime(QTime(task.due_time.hour, task.due_time.minute))
        self.priority.setCurrentIndex(task.priority - 1)
        self.hours.setValue(int(task.estimated_hours))
        self.desc.setPlainText(task.description)

    def _on_ok(self):
        if not self.title_edit.text().strip():
            self.title_edit.setFocus()
            return
        self.accept()

    # ---------- 取值 ----------
    def get_title(self) -> str:
        return self.title_edit.text().strip()

    def get_category(self) -> str:
        return self.category_edit.text().strip()

    def get_due_date(self) -> date:
        qd = self.due_date.date()
        return date(qd.year(), qd.month(), qd.day())

    def get_all_day(self) -> bool:
        return self.all_day.isChecked()

    def get_due_time(self) -> Optional[time]:
        if self.all_day.isChecked():
            return None
        qt = self.due_time.time()
        return time(qt.hour(), qt.minute())

    def get_priority(self) -> int:
        return self.priority.currentData()

    def get_estimated_hours(self) -> float:
        return float(self.hours.value())

    def get_description(self) -> str:
        return self.desc.toPlainText().strip()
