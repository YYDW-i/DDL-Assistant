"""Read tasks using AI and preview explicit changes before applying them."""
import json
from PySide6.QtWidgets import QVBoxLayout, QPlainTextEdit, QPushButton, QMessageBox
from .ai_dialog import BusyDialog, _AIWorker
from ..ai.actions import apply_actions, snapshot
from ..services.task_service import TaskService


class QueryDialog(BusyDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("AI 查询与修改建议")
        self.resize(780, 560)
        self.service = TaskService()
        self._worker = None
        self._actions = []
        layout = QVBoxLayout(self)
        self.input = QPlainTextEdit()
        self.input.setPlaceholderText("例如：本周有哪些任务？把高数作业推迟到 2030-01-05。")
        layout.addWidget(self.input)
        self.query_btn = QPushButton("查询 / 生成建议")
        self.query_btn.clicked.connect(self._query)
        layout.addWidget(self.query_btn)
        self.output = QPlainTextEdit()
        self.output.setReadOnly(True)
        layout.addWidget(self.output, 2)
        self.apply_btn = QPushButton("确认执行以上勾选操作（再次确认）")
        self.apply_btn.setText("确认执行以上操作（再次确认）")
        self.apply_btn.setEnabled(False)
        self.apply_btn.clicked.connect(self._apply)
        layout.addWidget(self.apply_btn)

    def _query(self):
        question = self.input.toPlainText().strip()
        if not question or self.busy():
            return
        self.service.session.expire_all()
        tasks = self.service.repo.list()
        self._expected = {t.id: snapshot(t) for t in tasks}
        summary = json.dumps([dict(id=t.id, **self._expected[t.id]) for t in tasks], default=str, ensure_ascii=False)
        self._actions = []
        self.apply_btn.setEnabled(False)
        self.query_btn.setEnabled(False)
        self.output.setPlainText("正在调用本地 AI…请等待结束再关闭。")
        self._worker = _AIWorker(question=question, summary=summary, parent=self)
        self._worker.finished.connect(self._result)
        self._worker.start()

    def _result(self):
        self.query_btn.setEnabled(True)
        result = self._worker.result
        if isinstance(result, Exception):
            self.output.setPlainText(f"AI 调用失败：{result}")
            return
        preview = [result.reply]
        seen = set()
        for action in result.suggested_actions:
            if action.task_id not in self._expected or action.task_id in seen:
                self.output.setPlainText("AI 返回了未知或重复的任务ID，已拒绝全部操作。请重新查询。")
                return
            seen.add(action.task_id)
            before = self._expected[action.task_id]
            preview.append(f"\n任务 #{action.task_id}「{before['title']}」：{action.action}\n原因：{action.reason}")
            if action.action == "update":
                for key, value in action.fields.model_dump(exclude_unset=True).items():
                    preview.append(f"  {key}: {before[key]} → {value}")
            elif action.action == "delete":
                preview.append("  将删除此任务及其提醒记录")
            else:
                preview.append(f"  当前状态：{before['status']}")
        self.output.setPlainText("\n".join(preview))
        self._actions = result.suggested_actions
        self.apply_btn.setEnabled(bool(self._actions))

    def _apply(self):
        if not self._actions or self.busy():
            return
        if QMessageBox.question(self, "确认更改", f"执行预览中的 {len(self._actions)} 项操作？删除操作无法直接撤销。",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No) != QMessageBox.Yes:
            return
        try:
            apply_actions(self._actions, self._expected, self.service.session)
        except Exception as exc:
            QMessageBox.warning(self, "未执行", str(exc))
            self.apply_btn.setEnabled(False)
            return
        self.service.session.close()
        self.accept()

    def done(self, result):
        if not self.busy():
            self.service.session.close()
            super().done(result)
