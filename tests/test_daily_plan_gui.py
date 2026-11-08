import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from datetime import date, time
import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from app.services.task_service import TaskService, TaskCreate


@pytest.fixture
def qt_app():
    return QApplication.instance() or QApplication([])


def test_plan_import_only_lists_today_and_respects_checked_rows(temp_db, qt_app):
    from app.ui.daily_plan import ImportTodayDialog
    svc = TaskService(temp_db())
    svc.create(TaskCreate(title="今日1", due_date=date(2030, 1, 10)))
    t = svc.create(TaskCreate(title="今日2", due_date=date(2030, 1, 10)))
    svc.create(TaskCreate(title="明日", due_date=date(2030, 1, 11)))
    dialog = ImportTodayDialog(svc, date(2030, 1, 10), set())
    assert dialog.items.count() == 2
    dialog.items.item(0).setCheckState(Qt.Unchecked)
    assert dialog.selected_task_ids() == [t.id]


def test_plan_ai_preview_has_hours_reminders_and_start_before_atomic_save(temp_db, qt_app):
    from app.ui.ai_dialog import AIDialog
    from app.ai.schema import DailyPlanProposal
    from app.services.plan_service import DailyPlanService
    dialog = AIDialog(plan_date=date(2030, 1, 10))
    dialog._fill_table(DailyPlanProposal.model_validate({"tasks": [
        {"title": "生成的计划任务", "due_date": "2030-01-10", "planned_start": "09:00", "estimated_hours": 2.5}]}))
    assert dialog.service.repo.list() == []
    values = dialog.preview_tasks()
    assert values[0].estimated_hours == 2.5 and values[0].reminder_times is None
    assert dialog.preview_starts() == [time(9)]
    dialog._commit()
    assert len(DailyPlanService(dialog.service.session).list(date(2030, 1, 10))) == 1
    dialog.close()


def test_daily_plan_widget_lists_imported_tasks(temp_db, qt_app):
    from app.ui.daily_plan import DailyPlanView
    from app.services.plan_service import DailyPlanService
    svc = TaskService(temp_db())
    t = svc.create(TaskCreate(title="计划内任务", due_date=date.today()))
    DailyPlanService(svc.session).add_existing(date.today(), [t.id])
    widget = DailyPlanView(svc)
    widget.reload()
    assert widget.table.rowCount() == 1
    assert widget.table.item(0, 1).text() == "计划内任务"
    widget.close()
