"""Local model and desktop preferences."""
import subprocess
import sys
from pathlib import Path
from PySide6.QtWidgets import QDialog, QFormLayout, QLineEdit, QCheckBox, QPushButton, QLabel, QDialogButtonBox, QMessageBox
from ..settings import load_settings, save_settings


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.resize(520, 270)
        form = QFormLayout(self)
        values = load_settings()
        self.model = QLineEdit(values.get("model", "qwen3.5:4b"))
        form.addRow("本地 Ollama 模型", self.model)
        self.close_to_tray = QCheckBox("关闭窗口时最小化到托盘")
        self.close_to_tray.setChecked(values.get("close_to_tray", True))
        form.addRow(self.close_to_tray)
        note = QLabel("后台提醒在 GUI 退出后由 Windows 任务计划程序执行。\n请将 EXE 安装到固定目录后启用；无需管理员权限。")
        note.setWordWrap(True)
        form.addRow(note)
        enable = QPushButton("启用 / 更新后台提醒")
        enable.clicked.connect(self._enable)
        form.addRow(enable)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._save)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _save(self):
        model = self.model.text().strip()
        if not model or "\n" in model:
            QMessageBox.warning(self, "提示", "请输入有效模型名")
            return
        save_settings(model=model, close_to_tray=self.close_to_tray.isChecked())
        self.accept()

    def _enable(self):
        root = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[2] / "scripts"
        script = root / "install_reminder.ps1"
        if not script.exists():
            QMessageBox.warning(self, "未找到安装脚本", "请先运行发行包中的 install.cmd 安装到固定目录。")
            return
        try:
            # Launch asynchronously; Powershell writes a persistent install log.
            subprocess.Popen(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)],
                             creationflags=subprocess.CREATE_NO_WINDOW)
            QMessageBox.information(self, "已启动配置", "后台配置已启动。结果记录在数据目录的 logs/install.log。")
        except OSError as exc:
            QMessageBox.warning(self, "启动失败", str(exc))
