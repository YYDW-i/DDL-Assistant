"""Text/image extraction with editable, explicitly confirmed atomic previews."""
from datetime import date, time, datetime
from pathlib import Path
from uuid import uuid4
from PySide6.QtCore import Qt, QThread, Signal, QEvent
from PySide6.QtGui import QPixmap, QKeySequence
from PySide6.QtWidgets import (QApplication, QDialog, QFileDialog, QHBoxLayout, QLabel,
    QMessageBox, QPlainTextEdit, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout, QHeaderView)
from .. import config
from ..ai import extractor
from ..ai.schema import ExtractedTaskList
from ..services.task_service import TaskCreate, TaskService, validate_task


class _AIWorker(QThread):
    done = Signal(object)

    def __init__(self, text="", image_path=None, question=None, summary=None, parent=None, plan_date=None):
        super().__init__(parent)
        self.text, self.image_path = text, image_path
        self.question, self.summary = question, summary
        self.result = None
        self.plan_date = plan_date

    def run(self):
        try:
            if self.question is not None:
                self.result = extractor.answer_question(self.question, self.summary)
            elif self.plan_date is not None:
                self.result = extractor.generate_daily_plan(self.text, self.plan_date, self.image_path)
            elif self.image_path:
                self.result = extractor.extract_tasks_from_image(self.image_path, self.text)
            else:
                self.result = extractor.extract_tasks_from_text(self.text)
        except Exception as exc:
            self.result = exc
        self.done.emit(self.result)


class BusyDialog(QDialog):
    def busy(self):
        worker = getattr(self, "_worker", None)
        return worker is not None and worker.isRunning()

    def reject(self):
        if self.busy():
            return
        super().reject()

    def closeEvent(self, event):
        if self.busy():
            event.ignore()
        else:
            self.service.session.close()
            event.accept()


class AIDialog(BusyDialog):
    def __init__(self, parent=None, initial_text="", plan_date=None):
        super().__init__(parent)
        self.setWindowTitle("AI 智能添加")
        self._plan_date = plan_date
        if plan_date:
            self.setWindowTitle(f"AI 生成一日计划 · {plan_date.isoformat()}")
        self.resize(950, 610)
        self.service = TaskService()
        self._worker = None
        self._image_path = None
        self._temp_images = []
        layout = QVBoxLayout(self)
        tip = QLabel("识别后逐条核对。缺失日期须手动填写，歧义日期须勾选确认。调用中请等待结束再关闭。")
        tip.setWordWrap(True)
        layout.addWidget(tip)
        self.input = QPlainTextEdit()
        self.input.setPlaceholderText("输入任务，或直接 Ctrl+V 粘贴截图")
        self.input.setPlainText(initial_text)
        self.input.setMaximumHeight(90)
        self.input.installEventFilter(self)
        layout.addWidget(self.input)
        row = QHBoxLayout()
        self.img_label = QLabel("未选择图片")
        self.img_label.setFixedSize(140, 80)
        row.addWidget(self.img_label)
        for title, callback in [("粘贴截图", self._paste_image), ("选择 PNG/JPG", self._load_image), ("清除图片", self._clear_image)]:
            btn = QPushButton(title)
            btn.clicked.connect(callback)
            row.addWidget(btn)
        self.recognize_btn = QPushButton("开始识别")
        self.recognize_btn.clicked.connect(self._recognize)
        row.addWidget(self.recognize_btn)
        layout.addLayout(row)
        self.status = QLabel("")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.table = QTableWidget(0, 12 if plan_date else 11)
        headers = ["添加", "标题", "分类", "截止日期", "时间", "全天", "重要程度", "描述", "日期已确认", "预计小时", "自定义提醒（;分隔）"]
        if plan_date:
            headers.append("计划开始")
        self.table.setHorizontalHeaderLabels(headers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(7, QHeaderView.Stretch)
        layout.addWidget(self.table, 1)
        self.note_label = QLabel("")
        self.note_label.setWordWrap(True)
        layout.addWidget(self.note_label)
        self.commit_btn = QPushButton("确认添加勾选任务")
        if plan_date:
            self.commit_btn.setText("确认保存任务并加入当日计划")
        self.commit_btn.setEnabled(False)
        self.commit_btn.clicked.connect(self._commit)
        layout.addWidget(self.commit_btn)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.KeyPress and event.matches(QKeySequence.Paste):
            if QApplication.clipboard().mimeData().hasImage():
                self._paste_image()
                return True
        return super().eventFilter(obj, event)

    def _paste_image(self):
        if self.busy():
            return
        image = QApplication.clipboard().image()
        if image.isNull():
            QMessageBox.information(self, "提示", "剪贴板没有图片")
            return
        folder = config.data_dir() / "screenshots"
        folder.mkdir(exist_ok=True)
        path = folder / f"{uuid4().hex}.png"
        if not image.save(str(path)):
            QMessageBox.warning(self, "提示", "截图保存失败")
            return
        self._temp_images.append(path)
        self._set_image(str(path))

    def _load_image(self):
        if self.busy():
            return
        path, _ = QFileDialog.getOpenFileName(self, "选择图片", "", "图片 (*.png *.jpg *.jpeg)")
        if path:
            self._set_image(path)

    def _clear_image(self):
        if not self.busy():
            self._image_path = None
            self.img_label.clear()
            self.img_label.setText("未选择图片")

    def _set_image(self, path):
        self._image_path = path
        self.img_label.setPixmap(QPixmap(path).scaled(140, 80, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def _recognize(self):
        if self.busy():
            return
        text = self.input.toPlainText().strip()
        if not text and not self._image_path:
            return
        self.table.setRowCount(0)
        self.note_label.clear()
        self.commit_btn.setEnabled(False)
        self.recognize_btn.setEnabled(False)
        self.status.setText("本地 AI 识别中…调用超时后可重试；请等待结束再关闭。")
        self._worker = _AIWorker(text, self._image_path, parent=self, plan_date=self._plan_date)
        self._worker.finished.connect(lambda: self._on_result(self._worker.result))
        self._worker.start()

    def _on_result(self, result):
        self.recognize_btn.setEnabled(True)
        if isinstance(result, Exception):
            self.status.setText(f"识别失败：{result}。可继续手动添加任务。")
            return
        self._fill_table(result)
        self.status.setText(f"识别到 {len(result.tasks)} 条，请编辑核对。")
        self.note_label.setText(result.note)
        self.commit_btn.setEnabled(bool(result.tasks))

    @staticmethod
    def _check(checked):
        item = QTableWidgetItem()
        item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
        item.setCheckState(Qt.Checked if checked else Qt.Unchecked)
        return item

    def _fill_table(self, data: ExtractedTaskList):
        self.table.setRowCount(len(data.tasks))
        for row, task in enumerate(data.tasks):
            self.table.setItem(row, 0, self._check(True))
            values = [task.title, task.category, task.due_date.isoformat() if task.due_date else "",
                      task.due_time.strftime("%H:%M") if task.due_time else ""]
            for col, value in enumerate(values, 1):
                self.table.setItem(row, col, QTableWidgetItem(value))
            self.table.setItem(row, 5, self._check(task.all_day))
            self.table.setItem(row, 6, QTableWidgetItem(str(task.priority)))
            self.table.setItem(row, 7, QTableWidgetItem(task.description))
            self.table.setItem(row, 8, self._check(not task.date_ambiguous and task.due_date is not None))
            self.table.setItem(row, 9, QTableWidgetItem(str(task.estimated_hours)))
            reminder = QTableWidgetItem("")
            reminder.setToolTip("留空使用默认提前72/24/3小时；也可输入多个YYYY-MM-DD HH:MM，以英文分号分隔")
            self.table.setItem(row, 10, reminder)
            if self._plan_date:
                start = getattr(task, "planned_start", None)
                self.table.setItem(row, 11, QTableWidgetItem(start.strftime("%H:%M") if start else ""))

    def preview_tasks(self):
        tasks = []
        for row in range(self.table.rowCount()):
            if self.table.item(row, 0).checkState() != Qt.Checked:
                continue
            def value(col):
                return self.table.item(row, col).text().strip()
            try:
                due = date.fromisoformat(value(3))
                if self.table.item(row, 8).checkState() != Qt.Checked:
                    raise ValueError("请勾选日期已确认")
                data = TaskCreate(title=value(1), category=value(2), due_date=due,
                    due_time=time.fromisoformat(value(4)) if value(4) else None,
                    all_day=self.table.item(row, 5).checkState() == Qt.Checked,
                    priority=int(value(6)), description=value(7), source="ai",
                    estimated_hours=float(value(9)),
                    reminder_times=[datetime.fromisoformat(v.strip()).isoformat(timespec="minutes") for v in value(10).split(";") if v.strip()] if value(10) else None,
                    source_detail=self.input.toPlainText().strip() + (" [截图]" if self._image_path else ""))
                validate_task(data)
                tasks.append(data)
            except ValueError as exc:
                raise ValueError(f"第 {row+1} 行：请填写有效日期、时间并确认。{exc}") from exc
        if not tasks:
            raise ValueError("请至少勾选一条任务")
        return tasks

    def preview_starts(self):
        return [time.fromisoformat(self.table.item(row, 11).text().strip())
                if self.table.item(row, 11).text().strip() else None
                for row in range(self.table.rowCount()) if self.table.item(row, 0).checkState() == Qt.Checked]

    def _commit(self):
        if self.busy():
            return
        try:
            tasks = self.preview_tasks()
            if self._plan_date:
                from ..services.plan_service import DailyPlanService
                DailyPlanService(self.service.session).create_tasks(self._plan_date, tasks, self.preview_starts())
            else:
                self.service.create_many(tasks)
        except Exception as exc:
            self.service.session.rollback()
            QMessageBox.warning(self, "未添加任务", str(exc))
            return
        self.service.session.close()
        self.accept()

    def done(self, result):
        if self.busy():
            return
        for path in self._temp_images:
            path.unlink(missing_ok=True)
        self.service.session.close()
        super().done(result)
