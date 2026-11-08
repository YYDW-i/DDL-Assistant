"""Pydantic 模型：AI 输出结构化校验。"""
from __future__ import annotations

from datetime import date, time
from typing import Optional

from pydantic import BaseModel, Field


class ExtractedTask(BaseModel):
    """从自然语言/截图中识别出的单个任务。"""

    title: str = Field(description="任务标题，简洁明确")
    description: str = Field(default="", description="补充说明")
    category: str = Field(default="", description="分类：课程/竞赛/活动/个人 等")
    due_date: Optional[date] = Field(default=None, description="截止日期；无法确定时留空，不要编造")
    due_time: Optional[time] = Field(default=None, description="截止时间；全天事项留空")
    all_day: bool = Field(default=False)
    priority: int = Field(default=2, ge=1, le=4)
    date_ambiguous: bool = Field(
        default=False,
        description="日期是否存在歧义（例如'下周三'未说明月份）；为 true 时必须由用户确认",
    )


class ExtractedTaskList(BaseModel):
    tasks: list[ExtractedTask] = Field(default_factory=list)
    note: str = Field(default="", description="给用户的补充说明，例如日期歧义提醒")


class AIQueryResult(BaseModel):
    """AI 回答用户关于任务的提问/修改建议。"""

    reply: str
    suggested_actions: list[dict] = Field(default_factory=list)
