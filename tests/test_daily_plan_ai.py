from datetime import date
from unittest.mock import patch
import pytest
from app.ai import extractor


def test_daily_plan_generation_uses_selected_day_and_full_attributes():
    payload = '{"tasks":[{"title":"复习高数","due_date":"2030-01-10","due_time":"18:00","planned_start":"09:00","estimated_hours":2.5,"priority":3,"category":"学习","description":"复习积分"}],"note":"建议安排，请确认"}'
    with patch.object(extractor.client, "chat", return_value=payload) as call:
        result = extractor.generate_daily_plan("上午复习高数", date(2030, 1, 10))
    assert "2030-01-10" in call.call_args.args[0]
    assert call.call_args.kwargs["schema"]["properties"]["tasks"]
    assert result.tasks[0].estimated_hours == 2.5
    assert str(result.tasks[0].planned_start) == "09:00:00"


def test_daily_plan_rejects_invalid_hours_and_time():
    from app.ai.schema import DailyPlanProposal
    with pytest.raises(ValueError):
        DailyPlanProposal.model_validate({"tasks": [{"title": "任务", "estimated_hours": -1}]})
    with pytest.raises(ValueError):
        DailyPlanProposal.model_validate({"tasks": [{"title": "任务", "planned_start": "09:00Z"}]})
