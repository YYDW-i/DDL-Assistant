"""AI 快速添加对话框：自然语言 / 截图 -> 任务预览 -> 确认入库。"""
from __future__ import annotations

import logging
from datetime import date, time
from typing import Optional

from PySide6.QtCore import QThread, Signal, Qt, QTimer
from PySide6.QtCore import QDateTime
from PySide6.QtGui import QPixmap, QImage
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QCheckBox,
    QDateTimeEdit,
    QHeaderView,
)

from ..ai import extractor
from ..ai.schema import ExtractedTask, ExtractedTaskList
from ..services.task_service import TaskCreate, TaskService

logger = logging.getLogger(__name__)


class _AIWorker(QThread):
    """后台调用 Ollama，避免阻塞 GUI。"""

    done = Signal(object)  # ExtractedTaskList 或 Exception
    image_path: Optional[str] = None

    def run(self):
        try:
            if self.image_path:
                result = extractor.extract_tasks_from_image(self.image_path)
            else:
                result = extractor.extract_tasks_from_text(self._text)
            self.done.emit(result)
        except Exception as e:
            self.done.emit(e)


class AIDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AI 智能添加")
        self.resize(820, 600)
        self.service = TaskService()
        self._worker: Optional[_AIWorker] = None
        self._image_path: Optional[str] = None
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        tip = QLabel("输入一段话或粘贴截图（Ctrl+V），AI 自动识别任务；确认后才入库。")
        tip.setStyleSheet("color:#7f8c9b;")
        layout.addWidget(tip)

        self.input = QPlainTextEdit()
        self.input.setPlaceholderText(
            '例如："下周三前交数据结构实验报告，周五下午考高数，周六去社团招新"'
        )
        self.input.setMaximumHeight(90)
        layout.addWidget(self.input)

        # 图片行
        img_row = QHBoxLayout()
        self.img_label = QLabel("未粘贴截图")
        self.img_label.setFixedSize(160, 90)
        self.img_label.setStyleSheet("border:1px dashed #c9d4f0; border-radius:6px; color:#9aa5b1;")
        self.img_label.setAlignment(Qt.AlignCenter)
        img_row.addWidget(self.img_label)

        btn_paste = QPushButton("粘贴截图 (Ctrl+V)")
        btn_paste.clicked.connect(self._paste_image)
        btn_load = QPushButton("选择图片文件")
        btn_load.clicked.connect(self._load_image)
        self.recognize_btn = QPushButton("开始识别")
        self.recognize_btn.setStyleSheet("background:#4a7dff;color:white;padding:6px 16px;border-radius:6px;")
        self.recognize_btn.clicked.connect(self._recognize)
        img_row.addWidget(btn_paste)
        img_row.addWidget(btn_load)
        img_row.addStretch()
        img_row.addWidget(self.recognize_btn)
        layout.addLayout(img_row)

        self.status = QLabel("")
        layout.addWidget(self.status)

        # 预览表格
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["标题", "分类", "截止日期", "时间", "全天", "优先级", "备注"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table, stretch=1)

        note_row = QHBoxLayout()
        self.note_label = QLabel("")
        self.note_label.setStyleSheet("color:#c0392b;")
        note_row.addWidget(self.note_label)
        note_row.addStretch()
        self.commit_btn = QPushButton("确认添加选中任务")
        self.commit_btn.setStyleSheet("background:#27ae60;color:white;padding:6px 16px;border-radius:6px;")
        self.commit_btn.clicked.connect(self._commit)
        self.commit_btn.setEnabled(False)
        note_row.addWidget(self.commit_btn)
        layout.addLayout(note_row)

    # ---------- 图片 ----------
    def _paste_image(self):
        from PySide6.QtWidgets import QApplication
        clipboard = QApplication.clipboard()
        img: QImage = clipboard.image()
        if img.isNull():
            QMessageBox.information(self, "提示", "剪贴板里没有图片。可以先截图再 Ctrl+V。")
            return
        tmp = self._save_tmp_image(img)
        self._set_image(tmp)

    def _load_image(self):
        path, _ = QFileDialog.getOpenFileName(self, "选择截图", "", "图片 (*.png *.jpg *.jpeg)")
        if path:
            self._set_image(path)

    def _save_tmp_image(self, img: QImage) -> str:
        import tempfile
        from pathlib import Path
        p = Path(tempfile.gettempdir()) / "ddl_clip.png"
        img.save(str(p))
        return str(p)

    def _set_image(self, path: str):
        self._image_path = path
        pix = QPixmap(path).scaled(160, 90, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.img_label.setPixmap(pix)

    # ---------- 识别 ----------
    def _recognize(self):
        text = self.input.toPlainText().strip()
        if not text and not self._image_path:
            QMessageBox.information(self, "提示", "请输入文字或粘贴截图。")
            return
        self.recognize_btn.setEnabled(False)
        self.status.setText("AI 识别中…（首次加载模型可能需要几十秒）")
        self._worker = _AIWorker()
        self._worker._text = text
        self._worker.image_path = self._image_path
        self._worker.done.connect(self._on_result)
        self._worker.start()

    def _on_result(self, result):
        self.recognize_btn.setEnabled(True)
        if isinstance(result, Exception):
            self.status.setText(f"识别失败：{result}")
            QMessageBox.warning(self, "AI 不可用", f"{result}\n\n请确认本地 Ollama 已启动且已拉取模型。普通手动添加不受影响。")
            return
        self._fill_table(result)
        self.status.setText(f"识别完成：共 {len(result.tasks)} 条。请核对后点击右下角确认添加。")
        self.commit_btn.setEnabled(True)
        if result.note:
            self.note_label.setText("⚠ " + result.note)

    def _fill_table(self, data: ExtractedTaskList):
        self.table.setRowCount(0)
        for t in data.tasks:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(t.title))
            self.table.setItem(row, 1, QTableWidgetItem(t.category))
            self.table.setItem(row, 2, QTableWidgetItem(t.due_date.isoformat() if t.due_date else ""))
            self.table.setItem(row, 3, QTableWidgetItem(t.due_time.strftime("%H:%M") if t.due_time else ""))
            chk = QTableWidgetItem()
            chk.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            chk.setCheckState(Qt.Checked if t.all_day else Qt.Unchecked)
            self.table.setItem(row, 4, chk)
            pri = QTableWidgetItem(str(t.priority))
            self.table.setItem(row, 5, pri)
            note = t.description + (" [日期待确认]" if t.date_ambiguous else "")
            self.table.setItem(row, 6, QTableWidgetItem(note))

    # ---------- 提交 ----------
    def _commit(self):
        added = 0
        for row in range(self.table.rowCount()):
            title_item = self.table.item(row, 0)
            if not title_item or not title_item.text().strip():
                continue
            due_date_text = self.table.item(row, 2).text()
            try:
                due_date = date.fromisoformat(due_date_text) if due_date_text else None
            except ValueError:
                due_date = None
            time_text = self.table.item(row, 3).text()
            try:
                due_time = time.fromisoformat(time_text) if time_text else None
            except ValueError:
                due_time = None
            all_day = self.table.item(row, 4).checkState() == Qt.Checked
            try:
                priority = int(self.table.item(row, 5).text())
            except ValueError:
                priority = 2
            self.service.create(TaskCreate(
                title=title_item.text().strip(),
                category=self.table.item(row, 1).text(),
                description=self.table.item(row, 6).text(),
                due_date=due_date or date.today(),
                due_time=due_time,
                all_day=all_day,
                priority=priority,
                source="ai",
            ))
            added += 1
        QMessageBox.information(self, "完成", f"已添加 {added} 条任务。")
        self.accept()
