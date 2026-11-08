"""从自然语言/截图提取任务，输出结构化结果。"""
from __future__ import annotations

import json
import logging
from datetime import date
from typing import Optional

from pydantic import ValidationError

from . import client
from .schema import ExtractedTask, ExtractedTaskList

logger = logging.getLogger(__name__)

TODAY = date.today().isoformat()

EXTRACT_PROMPT = f"""你是一个任务提取助手。当前日期是 {TODAY}。
从用户输入的文字或截图中，提取所有独立的待办任务。严格遵守：
1. 不要编造截止日期。若输入中没有明确日期，due_date 留 null，date_ambiguous 设为 true。
2. 相对日期（如"明天""下周三"）要换算成公历日期（今天是 {TODAY}）。
3. 一条任务对应一件事；不要把多个截止日期混进一条任务。
4. 输出 JSON，结构为：
{{"tasks": [{{"title": "...", "description": "", "category": "课程/竞赛/活动/个人", "due_date": "YYYY-MM-DD或null", "due_time": "HH:MM或null", "all_day": false, "priority": 1-4, "date_ambiguous": false}}], "note": "..."}}
5. priority: 1低 2中 3高 4紧急。
6. 若日期有歧义，date_ambiguous=true，并在 note 中说明。
只输出 JSON，不要解释。

用户输入：
"""


def extract_tasks_from_text(text: str) -> ExtractedTaskList:
    prompt = EXTRACT_PROMPT + text
    raw = client.chat(prompt, json_mode=True)
    return _parse(raw)


def extract_tasks_from_image(image_path: str, context: str = "") -> ExtractedTaskList:
    prompt = EXTRACT_PROMPT + (context or "请从截图中提取任务。")
    raw = client.chat(prompt, images=[image_path], json_mode=True)
    return _parse(raw)


def _parse(raw: str) -> ExtractedTaskList:
    """容错解析：模型偶尔会包 ```json 栅栏。"""
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("```", 2)[1]
        if text.startswith("json"):
            text = text[4:]
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        logger.error("AI 输出不是 JSON：%s\n%s", e, raw)
        raise ValueError(f"AI 输出解析失败：{e}")
    try:
        return ExtractedTaskList.model_validate(data)
    except ValidationError as e:
        logger.error("AI 输出校验失败：%s\n%s", e, raw)
        raise ValueError(f"AI 输出不符合结构：{e}")


def answer_question(question: str, task_summary: str) -> str:
    """AI 基于当前任务列表回答用户提问或修改建议。"""
    prompt = (
        "你是任务管理助手。以下是用户当前的任务列表（JSON）：\n"
        f"{task_summary}\n\n"
        "用户问题：" + question + "\n"
        "请用简短中文回答。如果用户要求修改/删除/批量完成，只给出建议清单，不要自行执行。"
    )
    return client.chat(prompt, json_mode=False)
