"""One-day schedule, referencing normal tasks without cloning or deleting them."""
from datetime import date, time
from PySide6.QtCore import Qt, QDate, Signal
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QDateEdit, QLabel,
    QTableWidget, QTableWidgetItem, QHeaderView, QAbstractItemView, QDialog,
    QDialogButtonBox, QListWidget, QListWidgetItem, QMessageBox, QInputDialog)
from ..services.plan_service import DailyPlanService
from ..services.task_service import TaskCreate
from .dialogs import TaskDialog


def task_fields(dialog):
    return dict(title=dialog.get_title(), description=dialog.get_description(), category=dialog.get_category(),
                due_date=dialog.get_due_date(), due_time=dialog.get_due_time(), all_day=dialog.get_all_day(),
                priority=dialog.get_priority(), estimated_hours=dialog.get_estimated_hours(),
                reminder_times=dialog.get_reminder_times())


class ImportTodayDialog(QDialog):
    def __init__(self, service, day, included, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"导入 {day.isoformat()} 截止的任务")
        self.resize(540, 400)
        layout = QVBoxLayout(self)
        label = QLabel("勾选要加入计划的已有任务。导入仅建立引用，不复制任务或修改截止时间。")
        label.setWordWrap(True)
        layout.addWidget(label)
        self.items = QListWidget()
        for task in service.repo.list(status="pending", due_from=day, due_to=day):
            if task.id in included:
                continue
            item = QListWidgetItem(f"{task.title} · {task.due_time.strftime('%H:%M') if task.due_time else '全天'} · {task.estimated_hours:g}小时")
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked)
            item.setData(Qt.UserRole, task.id)
            self.items.addItem(item)
        layout.addWidget(self.items, 1)
        if not self.items.count():
            layout.addWidget(QLabel("没有可导入的新任务；已有计划保持不变。"))
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected_task_ids(self):
        return [self.items.item(row).data(Qt.UserRole) for row in range(self.items.count())
                if self.items.item(row).checkState() == Qt.Checked]


class DailyPlanView(QWidget):
    changed = Signal()

    def __init__(self, service, parent=None):
        super().__init__(parent)
        self.service = service
        self.plans = DailyPlanService(service.session)
        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        self.day = QDateEdit(QDate.currentDate())
        self.day.setCalendarPopup(True)
        self.day.setDisplayFormat("yyyy-MM-dd")
        self.day.dateChanged.connect(lambda _: self._mutated())
        row.addWidget(self.day)
        today = QPushButton("回到今天")
        today.clicked.connect(lambda: self.day.setDate(QDate.currentDate()))
        row.addWidget(today)
        row.addStretch()
        for label, callback in [("导入当日任务", self._import), ("手动添加计划任务", self._add), ("AI 生成计划", self._generate)]:
            button = QPushButton(label)
            button.clicked.connect(callback)
            row.addWidget(button)
        layout.addLayout(row)
        note = QLabel("计划开始时间与任务截止时间独立。移出计划会保留原任务；完成状态与全部任务同步。")
        note.setWordWrap(True)
        layout.addWidget(note)
        self.summary = QLabel("")
        layout.addWidget(self.summary)
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(["计划开始", "任务", "分类", "截止时间", "预计小时", "重要程度", "状态", "来源"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.cellDoubleClicked.connect(lambda row, col: self._set_start() if col == 0 else self._edit())
        layout.addWidget(self.table, 1)
        actions = QHBoxLayout()
        for label, callback in [("安排开始时间", self._set_start), ("编辑任务属性", self._edit),
                                ("标记完成 / 重新打开", self._toggle_complete), ("移出计划（保留任务）", self._remove)]:
            button = QPushButton(label)
            button.clicked.connect(callback)
            actions.addWidget(button)
        layout.addLayout(actions)

    def plan_date(self):
        value = self.day.date()
        return date(value.year(), value.month(), value.day())

    def reload(self, search=None):
        self.service.session.expire_all()
        entries = self.plans.list(self.plan_date(), search=search)
        self.table.setRowCount(len(entries))
        for row, (entry, task) in enumerate(entries):
            deadline = f"{task.due_date.isoformat()} {task.due_time.strftime('%H:%M') if task.due_time and not task.all_day else '全天'}"
            values = [entry.planned_start.strftime("%H:%M") if entry.planned_start else "待安排",
                      task.title, task.category, deadline, f"{task.estimated_hours:g}",
                      {1: "低", 2: "中", 3: "高", 4: "紧急"}.get(task.priority, ""),
                      "已完成" if task.status == "completed" else "待办", task.source]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(f"{task.description}\n来源：{task.source_detail}\n创建于：{task.created_at:%Y-%m-%d %H:%M}")
                item.setData(Qt.UserRole, (entry.id, task.id))
                self.table.setItem(row, col, item)
        completed = sum(task.status == "completed" for _, task in entries)
        self.summary.setText(f"{self.plan_date().isoformat()} · 共{len(entries)}项 · 已完成{completed}项 · 预计{sum(task.estimated_hours for _, task in entries):g}小时")

    def _selected(self):
        item = self.table.item(self.table.currentRow(), 0)
        return item.data(Qt.UserRole) if item else None

    def _mutated(self):
        self.reload()
        self.changed.emit()

    def _import(self):
        included = {task.id for _, task in self.plans.list(self.plan_date())}
        dialog = ImportTodayDialog(self.service, self.plan_date(), included, self)
        try:
            if dialog.exec():
                self.plans.add_existing(self.plan_date(), dialog.selected_task_ids())
                self._mutated()
        except Exception as exc:
            self.service.session.rollback()
            QMessageBox.warning(self, "未导入", str(exc))
        finally:
            dialog.deleteLater()

    def _add(self):
        dialog = TaskDialog(self)
        selected = self.plan_date()
        dialog.due_date.setDate(QDate(selected.year, selected.month, selected.day))
        try:
            if dialog.exec():
                self.plans.create_tasks(selected, [TaskCreate(**task_fields(dialog))])
                self._mutated()
        except Exception as exc:
            self.service.session.rollback()
            QMessageBox.warning(self, "未添加", str(exc))
        finally:
            dialog.deleteLater()

    def _generate(self):
        from .ai_dialog import AIDialog
        dialog = AIDialog(self, plan_date=self.plan_date())
        dialog.input.setPlaceholderText("例如：上午复习高数两小时，下午完成实验报告，晚上锻炼；请帮我制定合理计划。")
        if dialog.exec():
            self._mutated()
        dialog.deleteLater()

    def _set_start(self):
        selected = self._selected()
        if not selected:
            return
        entry_id, _ = selected
        current = self.table.item(self.table.currentRow(), 0).text()
        value, accepted = QInputDialog.getText(self, "安排计划时间", "本地开始时间 HH:MM（留空取消安排）", text="" if current == "待安排" else current)
        if not accepted:
            return
        try:
            self.plans.set_start(entry_id, time.fromisoformat(value.strip()) if value.strip() else None)
            self._mutated()
        except ValueError as exc:
            QMessageBox.warning(self, "时间无效", str(exc))

    def _edit(self):
        selected = self._selected()
        if not selected:
            return
        task = self.service.get(selected[1])
        if task is None:
            self._mutated()
            return
        dialog = TaskDialog(self, task=task)
        try:
            if dialog.exec():
                self.service.update(task.id, **task_fields(dialog))
                self._mutated()
        except Exception as exc:
            self.service.session.rollback()
            QMessageBox.warning(self, "未修改", str(exc))
        finally:
            dialog.deleteLater()

    def _toggle_complete(self):
        selected = self._selected()
        if not selected:
            return
        task = self.service.get(selected[1])
        if task is not None:
            try:
                self.service.reopen(task.id) if task.status == "completed" else self.service.complete(task.id)
                self._mutated()
            except Exception as exc:
                self.service.session.rollback()
                QMessageBox.warning(self, "未修改", str(exc))

    def _remove(self):
        selected = self._selected()
        if selected:
            try:
                self.plans.remove(selected[0])
                self._mutated()
            except Exception as exc:
                self.service.session.rollback()
                QMessageBox.warning(self, "未移出", str(exc))
