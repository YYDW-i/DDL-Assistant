"""主窗口：侧边导航 + 多视图（今日/本周/全部/逾期/月历）+ 托盘 + 主题。"""
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Optional

from PySide6.QtCore import Qt, QSize, QTimer
from PySide6.QtGui import QAction, QBrush, QColor, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QStyle,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
    QButtonGroup,
)

from ..db.models import Task
from ..services.task_service import TaskCreate, TaskService
from .calendar_view import CalendarView
from .dialogs import TaskDialog

logger = logging.getLogger(__name__)

LIGHT_QSS = """
QMainWindow, QWidget { background: #f5f6fa; color: #2c3e50; font-family: "Microsoft YaHei UI", "Segoe UI"; font-size: 14px; }
#Sidebar { background: #ffffff; border-right: 1px solid #e8eaf0; }
#NavButton { text-align: left; padding: 10px 18px; border: none; border-radius: 8px; margin: 2px 8px; background: transparent; }
#NavButton:hover { background: #eef1f7; }
#NavButton:checked { background: #4a7dff; color: white; font-weight: 600; }
#Card { background: #ffffff; border: 1px solid #e8eaf0; border-radius: 10px; }
#StatLabel { font-size: 22px; font-weight: 700; }
#StatCaption { color: #7f8c9b; font-size: 12px; }
QLineEdit#SearchBox { padding: 8px 12px; border: 1px solid #dcdfe6; border-radius: 8px; background: #ffffff; }
QLineEdit#SearchBox:focus { border: 1.5px solid #4a7dff; }
QPushButton#PrimaryBtn { background: #4a7dff; color: white; border: none; padding: 8px 18px; border-radius: 8px; font-weight: 600; }
QPushButton#PrimaryBtn:hover { background: #3a6be8; }
QListWidget { background: transparent; border: none; outline: none; }
QListWidget::item { background: #ffffff; border: 1px solid #e8eaf0; border-radius: 10px; padding: 12px; margin: 4px 2px; }
QListWidget::item:hover { border-color: #c9d4f0; }
QCalendarWidget { background: #ffffff; }
"""

DARK_QSS = """
QMainWindow, QWidget { background: #1e2128; color: #e4e6eb; font-family: "Microsoft YaHei UI", "Segoe UI"; font-size: 14px; }
#Sidebar { background: #2a2d35; border-right: 1px solid #353942; }
#NavButton { text-align: left; padding: 10px 18px; border: none; border-radius: 8px; margin: 2px 8px; background: transparent; color: #cfd2d8; }
#NavButton:hover { background: #353942; }
#NavButton:checked { background: #4a7dff; color: white; font-weight: 600; }
#Card { background: #2a2d35; border: 1px solid #353942; border-radius: 10px; }
#StatLabel { font-size: 22px; font-weight: 700; }
#StatCaption { color: #8a909c; font-size: 12px; }
QLineEdit#SearchBox { padding: 8px 12px; border: 1px solid #3a3f4a; border-radius: 8px; background: #2a2d35; color: #e4e6eb; }
QLineEdit#SearchBox:focus { border: 1.5px solid #4a7dff; }
QPushButton#PrimaryBtn { background: #4a7dff; color: white; border: none; padding: 8px 18px; border-radius: 8px; font-weight: 600; }
QPushButton#PrimaryBtn:hover { background: #3a6be8; }
QListWidget { background: transparent; border: none; outline: none; }
QListWidget::item { background: #2a2d35; border: 1px solid #353942; border-radius: 10px; padding: 12px; margin: 4px 2px; }
QListWidget::item:hover { border-color: #4a7dff; }
QCalendarWidget { background: #2a2d35; color: #e4e6eb; }
QCalendarWidget QAbstractItemView:enabled { background: #2a2d35; color: #e4e6eb; }
"""


class MainWindow(QMainWindow):
    VIEWS = [
        ("today", "今日任务"),
        ("week", "本周任务"),
        ("all", "全部任务"),
        ("overdue", "逾期任务"),
        ("calendar", "月历"),
    ]

    def __init__(self):
        super().__init__()
        self.setWindowTitle("DDL Assistant")
        self.resize(1100, 740)
        self._dark = False
        self.setStyleSheet(LIGHT_QSS)

        self.service = TaskService()
        self.current_view = "today"
        self._tray: Optional[QSystemTrayIcon] = None

        self._build_ui()
        self._build_tray()
        self._build_shortcuts()
        self._reload_view()

        # 启动时自动补推一次提醒（开机后错过的通知）
        QTimer.singleShot(2000, self._run_reminder_once)

    # ---------- UI ----------
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

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
        self.theme_btn = QPushButton("🌙 暗色模式")
        self.theme_btn.setObjectName("NavButton")
        self.theme_btn.clicked.connect(self._toggle_theme)
        side_layout.addWidget(self.theme_btn)
        root.addWidget(sidebar)

        # 右侧主区
        main = QWidget()
        mlayout = QVBoxLayout(main)
        mlayout.setContentsMargins(20, 16, 20, 16)
        mlayout.setSpacing(12)

        top = QHBoxLayout()
        self.title_label = QLabel("今日任务")
        self.title_label.setStyleSheet("font-size:20px; font-weight:700;")
        top.addWidget(self.title_label)
        top.addStretch()

        self.search_box = QLineEdit()
        self.search_box.setObjectName("SearchBox")
        self.search_box.setPlaceholderText("搜索任务… (Ctrl+K)")
        self.search_box.setFixedWidth(240)
        self.search_box.textChanged.connect(self._reload_view)
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

        # 多视图堆栈
        self.stack = QStackedWidget()
        # 列表视图
        self.task_list = QListWidget()
        self.task_list.setWordWrap(True)
        self.task_list.itemDoubleClicked.connect(self._open_edit)
        self.task_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.task_list.customContextMenuRequested.connect(self._show_context_menu)
        self.stack.addWidget(self.task_list)
        # 日历视图
        self.calendar_view = CalendarView(self.service)
        self.stack.addWidget(self.calendar_view)
        mlayout.addWidget(self.stack, stretch=1)

        hint = QLabel("双击编辑；右键完成/删除；Ctrl+N 新建，Ctrl+Shift+A AI 添加，Ctrl+~ 最小化到托盘")
        hint.setStyleSheet("color:#95a0b0; font-size:12px;")
        mlayout.addWidget(hint)

        root.addWidget(main, stretch=1)

    # ---------- 托盘 ----------
    def _build_tray(self):
        self._tray = QSystemTrayIcon(self)
        self._tray.setIcon(self.style().standardIcon(QStyle.SP_ComputerIcon))
        self._tray.setToolTip("DDL Assistant")
        menu = QMenu()
        show_action = QAction("打开主窗口", self)
        show_action.triggered.connect(self.showNormal)
        add_action = QAction("新建任务", self)
        add_action.triggered.connect(self._open_add)
        ai_action = QAction("AI 智能添加", self)
        ai_action.triggered.connect(self._open_ai)
        quit_action = QAction("退出", self)
        quit_action.triggered.connect(self._quit_app)
        menu.addAction(show_action)
        menu.addAction(add_action)
        menu.addAction(ai_action)
        menu.addSeparator()
        menu.addAction(quit_action)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.showNormal()

    def _build_shortcuts(self):
        QShortcut(QKeySequence("Ctrl+N"), self, self._open_add)
        QShortcut(QKeySequence("Ctrl+Shift+A"), self, self._open_ai)
        QShortcut(QKeySequence("Ctrl+K"), self, lambda: self.search_box.setFocus())
        QShortcut(QKeySequence("Ctrl+`"), self, self.hide)

    # ---------- 数据刷新 ----------
    def _switch_view(self, key: str):
        self.current_view = key
        self._reload_view()

    def _reload_view(self):
        if self.current_view == "calendar":
            self.stack.setCurrentWidget(self.calendar_view)
            self.calendar_view._mark_days()
            self.title_label.setText("月历")
        else:
            self.stack.setCurrentWidget(self.task_list)
            title_map = dict(self.VIEWS)
            self.title_label.setText(title_map.get(self.current_view, "任务"))
            self._reload_task_list()

        s = self.service.stats()
        for k, lbl in self.stat_labels.items():
            lbl.setText(str(s.get(k, 0)))

    def _reload_task_list(self):
        search = self.search_box.text().strip() or None
        tasks = self.service.list_view(self.current_view, search=search)
        self.task_list.clear()
        if not tasks:
            empty = QListWidgetItem("（暂无任务）")
            empty.setFlags(Qt.ItemIsEnabled)
            self.task_list.addItem(empty)
            return
        for t in tasks:
            self._add_task_item(t)

    def _add_task_item(self, task: Task):
        item = QListWidgetItem()
        due_str = self._format_due(task)
        priority_tag = {1: "⚪低", 2: "🔵中", 3: "🟠高", 4: "🔴紧急"}.get(task.priority, "")
        cat = f"[{task.category}]" if task.category else ""
        completed = task.status == "completed"
        prefix = "☑ " if completed else "☐ "
        item.setText(f"{prefix}{task.title}   {cat}\n     {due_str}  {priority_tag}")
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
        time_part = "全天" if (task.all_day or task.due_time is None) else task.due_time.strftime("%H:%M")
        if delta == 0:
            return f"今天 {time_part}"
        if delta == 1:
            return f"明天 {time_part}"
        if delta < 0:
            return f"已逾期 {abs(delta)} 天"
        return f"{task.due_date.strftime('%m-%d')} {time_part}"

    def _is_urgent(self, task: Task) -> bool:
        if task.status == "completed":
            return False
        now = datetime.now()
        if task.all_day or task.due_time is None:
            due_dt = datetime.combine(task.due_date, datetime.min.time()).replace(hour=23, minute=59)
        else:
            due_dt = datetime.combine(task.due_date, task.due_time)
        return 0 <= (due_dt - now).total_seconds() <= 24 * 3600

    # ---------- 右键菜单 ----------
    def _show_context_menu(self, pos):
        item = self.task_list.itemAt(pos)
        if not item:
            return
        tid = item.data(Qt.UserRole)
        if tid is None:
            return
        menu = QMenu(self)
        act_done = menu.addAction("标记完成")
        act_reopen = menu.addAction("重新打开")
        act_edit = menu.addAction("编辑")
        menu.addSeparator()
        act_del = menu.addAction("删除")
        action = menu.exec(self.task_list.viewport().mapToGlobal(pos))
        if action == act_done:
            self.service.complete(tid)
            self._reload_view()
        elif action == act_reopen:
            self.service.reopen(tid)
            self._reload_view()
        elif action == act_edit:
            self._open_edit(item)
        elif action == act_del:
            if QMessageBox.question(self, "确认", "确定删除这条任务？") == QMessageBox.Yes:
                self.service.delete(tid)
                self._reload_view()

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
                self._reload_view()
            except ValueError as e:
                QMessageBox.warning(self, "提示", str(e))

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
            self._reload_view()

    def _open_ai(self):
        from .ai_dialog import AIDialog
        dlg = AIDialog(self)
        if dlg.exec():
            self._reload_view()

    def _toggle_theme(self):
        self._dark = not self._dark
        self.setStyleSheet(DARK_QSS if self._dark else LIGHT_QSS)
        self.theme_btn.setText("☀️ 亮色模式" if self._dark else "🌙 暗色模式")

    def _run_reminder_once(self):
        """启动时补推一次（与 reminder.py 同逻辑，但不重复弹已通知过的）。"""
        try:
            from ..reminder.core import collect_due_reminders, mark_notified
            from ..reminder.notifier import show_toast
            from ..db.session import get_session
            s = get_session()
            for it in collect_due_reminders(s):
                t = it.task
                if it.kind == "overdue":
                    title = f"⚠️ 任务已逾期：{t.title}"
                    body = f"截止 {it.due_at.strftime('%m-%d %H:%M')}"
                else:
                    title = f"📌 即将到期：{t.title}"
                    body = f"截止 {it.due_at.strftime('%m-%d %H:%M')}"
                if show_toast(title, body):
                    mark_notified(s, t.id, it.kind, it.due_at)
        except Exception as e:
            logger.warning("启动补推失败：%s", e)

    # ---------- 关闭到托盘 ----------
    def closeEvent(self, event):
        if self._tray and self._tray.isVisible():
            event.ignore()
            self.hide()
            self._tray.showMessage("DDL Assistant", "程序已最小化到托盘，后台继续提醒。")
        else:
            event.accept()

    def _quit_app(self):
        self._tray.hide()
        QApplication.quit()
