import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from datetime import date
import pytest
from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import QApplication, QMessageBox
from app.ai.schema import ExtractedTaskList


@pytest.fixture
def qt_app():
    return QApplication.instance() or QApplication([])


def test_ai_missing_date_never_defaults_to_today(temp_db, qt_app):
    from app.ui.ai_dialog import AIDialog
    dlg = AIDialog()
    dlg._fill_table(ExtractedTaskList.model_validate({"tasks": [{"title": "无日期"}]}))
    with pytest.raises(ValueError):
        dlg.preview_tasks()
    assert dlg.service.repo.list() == []
    dlg.close()


def test_ai_selection_and_ambiguous_date_confirmation(temp_db, qt_app):
    from app.ui.ai_dialog import AIDialog
    dlg = AIDialog()
    dlg._fill_table(ExtractedTaskList.model_validate({"tasks": [
        {"title": "歧义", "due_date": "2030-01-01", "date_ambiguous": True},
        {"title": "不添加", "due_date": "2030-01-02"}]}))
    with pytest.raises(ValueError, match="确认"):
        dlg.preview_tasks()
    dlg.table.item(0, 8).setCheckState(Qt.Checked)
    dlg.table.item(1, 0).setCheckState(Qt.Unchecked)
    assert [t.title for t in dlg.preview_tasks()] == ["歧义"]
    dlg.close()


def test_calendar_removes_stale_marks(temp_db, qt_app):
    from app.ui.calendar_view import CalendarView
    from app.services.task_service import TaskService, TaskCreate
    svc = TaskService(temp_db())
    t = svc.create(TaskCreate(title="日历任务", due_date=date(2030, 1, 1)))
    view = CalendarView(svc)
    day = QDate(2030, 1, 1)
    assert view.calendar.dateTextFormat(day).hasProperty(2080)
    svc.complete(t.id)
    view._mark_days()
    assert not view.calendar.dateTextFormat(day).hasProperty(2080)


def test_manual_dialog_supports_fractional_hours_and_multiple_reminders(temp_db, qt_app):
    from app.ui.dialogs import TaskDialog
    dlg = TaskDialog()
    dlg.hours.setValue(1.5)
    dlg.reminders.setPlainText("2030-01-01 09:00\n2030-01-02 18:00")
    assert dlg.get_estimated_hours() == 1.5
    assert len(dlg.get_reminder_times()) == 2
