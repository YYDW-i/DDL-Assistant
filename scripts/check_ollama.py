"""Opt-in real-model acceptance check. No database writes or model downloads.

Run with the project Python; creates only a screenshot fixture and JSON report
under .pytest-tmp/ollama-check. Not part of the mocked contract test suite.
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUTPUT = ROOT / ".pytest-tmp" / "ollama-check"
OUTPUT.mkdir(parents=True, exist_ok=True)
os.environ["LOCALAPPDATA"] = str(OUTPUT)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QImage, QPainter, QFont, QColor, QFontDatabase
from app.ai.extractor import extract_tasks_from_text, extract_tasks_from_image, answer_question, generate_daily_plan
from datetime import date

app = QApplication([])
font_path = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts/msyh.ttc"
font_id = QFontDatabase.addApplicationFont(str(font_path))
families = QFontDatabase.applicationFontFamilies(font_id)
assert families, "中文字体不可用，无法构造截图验收输入"
image = QImage(1200, 360, QImage.Format_RGB32)
image.fill(QColor("white"))
painter = QPainter(image)
painter.setPen(QColor("black"))
painter.setFont(QFont(families[0], 24))
painter.drawText(30, 70, "任务通知（验收测试输入）")
painter.drawText(30, 160, "2030年1月6日14:30 参加高数考试")
painter.drawText(30, 250, "2030年1月7日18:00前 完成社团报名")
painter.end()
path = OUTPUT / "input.png"
image.save(str(path))

text = extract_tasks_from_text("2030年1月5日20:00前提交数据结构实验报告；另外准备英语口语练习，日期未定。")
picture = extract_tasks_from_image(str(path))
suggestion = answer_question("把ID为41的任务标记完成，不要修改其他任务", json.dumps([
    {"id": 41, "title": "高数作业", "due_date": "2030-01-06", "status": "pending"},
    {"id": 42, "title": "英语作业", "due_date": "2030-01-07", "status": "pending"}], ensure_ascii=False))
plan = generate_daily_plan("上午9点复习高数两小时，下午14点写实验报告1.5小时，晚上19点锻炼半小时。", date(2030, 1, 10))
report = {"text": text.model_dump(mode="json"), "image": picture.model_dump(mode="json"), "suggestion": suggestion.model_dump(mode="json"), "daily_plan": plan.model_dump(mode="json")}
(OUTPUT / "result.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
assert len(text.tasks) == 2, report
assert any(t.due_date is None and t.date_ambiguous for t in text.tasks), report
assert any(str(t.due_date) == "2030-01-05" and str(t.due_time) == "20:00:00" for t in text.tasks), report
assert {str(t.due_date) for t in picture.tasks} == {"2030-01-06", "2030-01-07"}, report
assert [(a.action, a.task_id) for a in suggestion.suggested_actions] == [("complete", 41)], report
assert len(plan.tasks) >= 3 and all(t.due_date == date(2030, 1, 10) for t in plan.tasks), report
assert any(t.planned_start and t.estimated_hours > 0 for t in plan.tasks), report
print("Real Ollama text and image checks passed. Report:", OUTPUT / "result.json")
