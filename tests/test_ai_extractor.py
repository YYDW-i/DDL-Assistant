"""AI 提取层测试：mock Ollama 输出，验证解析与 Pydantic 校验。"""
from __future__ import annotations

from datetime import date
from unittest.mock import patch

import pytest

from app.ai import extractor
from app.ai.schema import ExtractedTaskList


class TestExtractParse:
    def test_plain_json(self):
        raw = '{"tasks":[{"title":"交作业","due_date":"2030-01-05","due_time":"20:00","priority":3}],"note":""}'
        with patch.object(extractor.client, "chat", return_value=raw):
            result = extractor.extract_tasks_from_text("明天交作业")
        assert isinstance(result, ExtractedTaskList)
        assert result.tasks[0].title == "交作业"
        assert result.tasks[0].due_date == date(2030, 1, 5)
        assert result.tasks[0].priority == 3

    def test_fenced_json(self):
        raw = '```json\n{"tasks":[{"title":"考试","due_date":null,"due_time":null,"date_ambiguous":true}],"note":"日期未说明"}\n```'
        with patch.object(extractor.client, "chat", return_value=raw):
            result = extractor.extract_tasks_from_text("周五考试")
        assert result.tasks[0].due_date is None
        assert result.tasks[0].date_ambiguous is True
        assert "日期" in result.note

    def test_bad_json_raises(self):
        with patch.object(extractor.client, "chat", return_value="这不是JSON"):
            with pytest.raises(ValueError):
                extractor.extract_tasks_from_text("xxx")

    def test_priority_clamped(self):
        raw = '{"tasks":[{"title":"x","due_date":null,"priority":9}],"note":""}'
        with patch.object(extractor.client, "chat", return_value=raw):
            with pytest.raises(ValueError):
                extractor.extract_tasks_from_text("x")

    def test_image_extract_calls_image(self):
        raw = '{"tasks":[],"note":""}'
        with patch.object(extractor.client, "chat", return_value=raw) as m:
            extractor.extract_tasks_from_image("C:/fake.png", context="截图")
            args, kwargs = m.call_args
            assert kwargs.get("images") == ["C:/fake.png"]
