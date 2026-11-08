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
    QDoubleSpinBox,
    QMessageBox,
    QLabel,
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

        self.hours = QDoubleSpinBox()
        self.hours.setRange(0, 1000)
        self.hours.setSuffix(" 小时")
        form.addRow("预计工作量", self.hours)

        self.desc = QPlainTextEdit()
        self.desc.setPlaceholderText("补充说明、链接、要求…")
        self.desc.setMinimumHeight(80)
        form.addRow("描述", self.desc)

        self.use_default_reminders = QCheckBox("默认：截止前72小时、24小时、3小时")
        self.use_default_reminders.setChecked(True)
        self.use_default_reminders.toggled.connect(self._refresh_default_reminders)
        form.addRow(self.use_default_reminders)
        self.reminders = QPlainTextEdit()
        self.reminders.setPlaceholderText("自定义多个本地时间，每行一个，如2030-01-01 09:00")
        self.reminders.setMaximumHeight(80)
        form.addRow("自定义提醒", self.reminders)
        self.source_label = QLabel("手动添加")
        self.source_label.setWordWrap(True)
        form.addRow("来源", self.source_label)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_ok)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)
        self.due_date.dateChanged.connect(self._refresh_default_reminders)
        self.due_time.timeChanged.connect(self._refresh_default_reminders)
        self.all_day.toggled.connect(self._refresh_default_reminders)
        self._refresh_default_reminders()

    def _refresh_default_reminders(self, *_):
        using_default = self.use_default_reminders.isChecked()
        self.reminders.setEnabled(not using_default)
        if using_default:
            from ..reminder.core import default_reminder_times
            task = Task(due_date=self.get_due_date(), due_time=self.get_due_time(), all_day=self.get_all_day())
            self.reminders.setPlainText("\n".join(dt.isoformat(timespec="minutes") for dt in default_reminder_times(task)))

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
        self.hours.setValue(task.estimated_hours)
        self.desc.setPlainText(task.description)
        self.reminders.setPlainText("\n".join(task.reminder_times or []))
        self.use_default_reminders.setChecked(task.reminder_times is None)
        self._refresh_default_reminders()
        self.source_label.setText(f"{task.source} · 创建于 {task.created_at:%Y-%m-%d %H:%M}\n{task.source_detail}")

    def _on_ok(self):
        if not self.title_edit.text().strip():
            self.title_edit.setFocus()
            return
        try:
            self.get_reminder_times()
        except ValueError as exc:
            QMessageBox.warning(self, "提醒时间无效", str(exc))
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

    def get_reminder_times(self):
        if self.use_default_reminders.isChecked():
            return None
        lines = self.reminders.toPlainText().strip().splitlines()
        if not lines:
            return []
        result = []
        for line in lines:
            if not line.strip():
                continue
            dt = datetime.fromisoformat(line.strip())
            if dt.tzinfo:
                raise ValueError("请使用本地日期时间，如 2030-01-01 09:00")
            result.append(dt.isoformat(timespec="minutes"))
        return result
