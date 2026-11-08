"""主窗口：侧边导航 + 任务列表 + 顶部统计 + 搜索。"""
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Optional

from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QAction, QBrush, QColor, QIcon, QPainter, QPen
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
    QButtonGroup,
)

from ..db.models import Task
from ..services.task_service import TaskCreate, TaskService
from .dialogs import TaskDialog

logger = logging.getLogger(__name__)

# ---------- 浅色主题 QSS ----------
LIGHT_QSS = """
QMainWindow, QWidget { background: #f5f6fa; color: #2c3e50; font-family: "Microsoft YaHei UI", "Segoe UI"; font-size: 14px; }
#Sidebar { background: #ffffff; border-right: 1px solid #e8eaf0; }
#NavButton { text-align: left; padding: 10px 18px; border: none; border-radius: 8px; margin: 2px 8px; background: transparent; }
#NavButton:hover { background: #eef1f7; }
#NavButton:checked { background: #4a7dff; color: white; font-weight: 600; }
#Card { background: #ffffff; border: 1px solid #e8eaf0; border-radius: 10px; }
#StatLabel { font-size: 22px; font-weight: 700; color: #2c3e50; }
#StatCaption { color: #7f8c9b; font-size: 12px; }
QLineEdit#SearchBox { padding: 8px 12px; border: 1px solid #dcdfe6; border-radius: 8px; background: #ffffff; }
QLineEdit#SearchBox:focus { border: 1.5px solid #4a7dff; }
QPushButton#PrimaryBtn { background: #4a7dff; color: white; border: none; padding: 8px 18px; border-radius: 8px; font-weight: 600; }
QPushButton#PrimaryBtn:hover { background: #3a6be8; }
QListWidget { background: transparent; border: none; outline: none; }
QListWidget::item { background: #ffffff; border: 1px solid #e8eaf0; border-radius: 10px; padding: 12px; margin: 4px 2px; }
QListWidget::item:hover { border-color: #c9d4f0; }
"""


class MainWindow(QMainWindow):
    VIEWS = [
        ("today", "今日任务"),
        ("week", "本周任务"),
        ("all", "全部任务"),
        ("overdue", "逾期任务"),
    ]

    def __init__(self):
        super().__init__()
        self.setWindowTitle("DDL Assistant")
        self.resize(1080, 720)
        self.setStyleSheet(LIGHT_QSS)

        self.service = TaskService()
        self.current_view = "today"

        self._build_ui()
        self.refresh()

    # ---------- UI 搭建 ----------
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # 侧边栏
        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(180)
        side_layout = QVBoxLayout(sidebar)
        side_layout.setContentsMargins(8, 20, 8, 12)
        side_layout.setSpacing(4)

        logo = QLabel("  DDL Assistant")
        logo.setStyleSheet("font-size:18px; font-weight:700; padding: 4px 8px 16px 8px;")
        side_layout.addWidget(logo)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        for key, label in self.VIEWS:
            btn = QPushButton(f"  {label}")
            btn.setObjectName("NavButton")
            btn.setCheckable(True)
            btn.clicked.connect(lambda _=False, k=key: self._switch_view(k))
            self.nav_group.addButton(btn)
            side_layout.addWidget(btn)
            if key == self.current_view:
                btn.setChecked(True)

        side_layout.addStretch()
        root.addWidget(sidebar)

        # 右侧主区
        main = QWidget()
        mlayout = QVBoxLayout(main)
        mlayout.setContentsMargins(20, 16, 20, 16)
        mlayout.setSpacing(12)

        # 顶部：标题 + 搜索 + 新建
        top = QHBoxLayout()
        self.title_label = QLabel("今日任务")
        self.title_label.setStyleSheet("font-size:20px; font-weight:700;")
        top.addWidget(self.title_label)
        top.addStretch()

        self.search_box = QLineEdit()
        self.search_box.setObjectName("SearchBox")
        self.search_box.setPlaceholderText("搜索任务标题或描述…")
        self.search_box.setFixedWidth(260)
        self.search_box.textChanged.connect(self.refresh)
        top.addWidget(self.search_box)

        add_btn = QPushButton("+ 新建任务")
        add_btn.setObjectName("PrimaryBtn")
        add_btn.clicked.connect(self._open_add)
        top.addWidget(add_btn)

        ai_btn = QPushButton("✨ AI 智能添加")
        ai_btn.setStyleSheet("background:#8e44ad;color:white;padding:8px 18px;border-radius:8px;font-weight:600;")
        ai_btn.clicked.connect(self._open_ai)
        top.addWidget(ai_btn)
        mlayout.addLayout(top)

        # 统计卡片
        stats_row = QHBoxLayout()
        stats_row.setSpacing(12)
        self.stat_labels = {}
        for key, caption in [("pending", "待办"), ("today", "今日截止"), ("overdue", "已逾期"), ("approaching", "24h 内")]:
            card = QFrame()
            card.setObjectName("Card")
            card.setFixedHeight(70)
            cl = QVBoxLayout(card)
            cl.setContentsMargins(14, 10, 14, 10)
            num = QLabel("0")
            num.setObjectName("StatLabel")
            cap = QLabel(caption)
            cap.setObjectName("StatCaption")
            cl.addWidget(num)
            cl.addWidget(cap)
            stats_row.addWidget(card)
            self.stat_labels[key] = num
        mlayout.addLayout(stats_row)

        # 任务列表
        self.task_list = QListWidget()
        self.task_list.setWordWrap(True)
        self.task_list.itemDoubleClicked.connect(self._open_edit)
        mlayout.addWidget(self.task_list, stretch=1)

        # 底部提示
        hint = QLabel("双击任务可编辑；右键菜单可完成/删除。")
        hint.setStyleSheet("color:#95a0b0; font-size:12px;")
        mlayout.addWidget(hint)

        root.addWidget(main, stretch=1)

    # ---------- 数据刷新 ----------
    def _switch_view(self, key: str):
        self.current_view = key
        self.refresh()

    def refresh(self):
        # 统计
        s = self.service.stats()
        for k, lbl in self.stat_labels.items():
            lbl.setText(str(s.get(k, 0)))

        # 标题
        title_map = dict(self.VIEWS)
        self.title_label.setText(title_map.get(self.current_view, "任务"))

        # 列表
        search = self.search_box.text().strip() or None
        tasks = self.service.list_view(self.current_view, search=search)
        self.task_list.clear()
        if not tasks:
            empty = QListWidgetItem("（暂无任务，点击右上角「新建任务」添加）")
            empty.setFlags(Qt.ItemIsEnabled)
            self.task_list.addItem(empty)
            return
        for t in tasks:
            self._add_task_item(t)

    def _add_task_item(self, task: Task):
        item = QListWidgetItem()
        # 高度根据内容
        due_str = self._format_due(task)
        priority_tag = {1: "⚪低", 2: "🔵中", 3: "🟠高", 4: "🔴紧急"}.get(task.priority, "")
        cat = f"[{task.category}]" if task.category else ""
        completed = task.status == "completed"
        prefix = "☑ " if completed else "☐ "
        text = f"{prefix}{task.title}   {cat}\n     {due_str}  {priority_tag}"
        item.setText(text)
        if completed:
            item.setForeground(QBrush(QColor("#9aa5b1")))
        elif self._is_urgent(task):
            item.setForeground(QBrush(QColor("#c0392b")))
        item.setSizeHint(QSize(0, 64))
        item.setData(Qt.UserRole, task.id)
        self.task_list.addItem(item)

    def _format_due(self, task: Task) -> str:
        today = date.today()
        delta = (task.due_date - today).days
        if task.all_day or task.due_time is None:
            time_part = "全天"
        else:
            time_part = task.due_time.strftime("%H:%M")
        if delta == 0:
            day_str = f"今天 {time_part}"
        elif delta == 1:
            day_str = f"明天 {time_part}"
        elif delta < 0:
            day_str = f"已逾期 {abs(delta)} 天"
        else:
            day_str = f"{task.due_date.strftime('%m-%d')} {time_part}"
        return day_str

    def _is_urgent(self, task: Task) -> bool:
        if task.status == "completed":
            return False
        now = datetime.now()
        if task.all_day or task.due_time is None:
            due_dt = datetime.combine(task.due_date, datetime.min.time()).replace(hour=23, minute=59)
        else:
            due_dt = datetime.combine(task.due_date, task.due_time)
        return 0 <= (due_dt - now).total_seconds() <= 24 * 3600

    # ---------- 操作 ----------
    def _open_add(self):
        dlg = TaskDialog(self)
        if dlg.exec():
            try:
                self.service.create(TaskCreate(
                    title=dlg.get_title(),
                    description=dlg.get_description(),
                    category=dlg.get_category(),
                    due_date=dlg.get_due_date(),
                    due_time=dlg.get_due_time(),
                    all_day=dlg.get_all_day(),
                    priority=dlg.get_priority(),
                    estimated_hours=dlg.get_estimated_hours(),
                ))
                self.refresh()
            except ValueError as e:
                logger.warning("创建任务失败：%s", e)

    def _open_edit(self, item: QListWidgetItem):
        tid = item.data(Qt.UserRole)
        if tid is None:
            return
        task = self.service.get(tid)
        if not task:
            return
        dlg = TaskDialog(self, task=task)
        if dlg.exec():
            self.service.update(
                tid,
                title=dlg.get_title(),
                description=dlg.get_description(),
                category=dlg.get_category(),
                due_date=dlg.get_due_date(),
                due_time=dlg.get_due_time(),
                all_day=dlg.get_all_day(),
                priority=dlg.get_priority(),
                estimated_hours=dlg.get_estimated_hours(),
            )
            self.refresh()

    def _open_ai(self):
        from .ai_dialog import AIDialog
        dlg = AIDialog(self)
        if dlg.exec():
            self.refresh()
