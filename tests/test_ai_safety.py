from datetime import date, datetime
from unittest.mock import patch
import pytest
from app.ai import client, extractor
from app.ai.schema import ExtractedTaskList
from app.services.task_service import TaskCreate, TaskService


def test_extract_supplies_json_schema_and_fresh_date():
    with patch.object(extractor.client, "chat", return_value='{"tasks":[]}') as call:
        with patch.object(extractor, "date") as clock:
            clock.today.return_value = date(2032, 2, 3)
            extractor.extract_tasks_from_text("明天交作业")
        assert "2032-02-03" in call.call_args.args[0]
        assert call.call_args.kwargs["schema"]["properties"]["tasks"]


def test_empty_title_fails_schema():
    with pytest.raises(ValueError):
        ExtractedTaskList.model_validate({"tasks": [{"title": " "}]})


def test_ai_actions_are_atomic_and_detect_stale_preview(temp_db):
    from app.ai.actions import apply_actions, snapshot
    from app.ai.schema import SuggestedAction
    svc = TaskService(temp_db())
    t = svc.create(TaskCreate(title="原任务", due_date=date.today()))
    expected = {t.id: snapshot(t)}
    actions = [SuggestedAction(action="update", task_id=t.id, fields={"title": "修改"})]
    svc.update(t.id, title="用户已修改")
    with pytest.raises(ValueError, match="变化"):
        apply_actions(actions, expected, svc.session)
    assert svc.get(t.id).title == "用户已修改"
    expected = {t.id: snapshot(t)}
    apply_actions(actions, expected, svc.session)
    assert svc.get(t.id).title == "修改"


def test_ai_cannot_invent_ids_or_modify_internal_fields():
    from app.ai.schema import SuggestedAction
    with pytest.raises(ValueError):
        SuggestedAction(action="update", task_id=1, fields={"id": 200})


def test_model_null_patch_fields_mean_unchanged():
    from app.ai.schema import SuggestedAction
    action = SuggestedAction.model_validate({"action": "complete", "task_id": 41,
        "fields": {"title": None, "due_date": None, "due_time": None, "priority": None}})
    assert action.fields.model_dump(exclude_unset=True) == {}
    update = SuggestedAction.model_validate({"action": "update", "task_id": 41,
        "fields": {"title": "新标题", "due_date": None, "due_time": None}})
    assert update.fields.model_dump(exclude_unset=True) == {"title": "新标题"}
