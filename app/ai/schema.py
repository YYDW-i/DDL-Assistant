"""Strict structured outputs for extraction and proposed task changes."""
from datetime import date, time
from typing import Literal, Optional, Annotated
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator, WithJsonSchema

LocalTime = Annotated[time, WithJsonSchema({"type": "string", "pattern": "^(?:[01][0-9]|2[0-3]):[0-5][0-9]$", "description": "HH:MM本地时间，如14:30，不带时区"})]


class ExtractedTask(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: str = Field(min_length=1, max_length=200)
    description: str = ""
    category: str = Field(default="", max_length=50)
    due_date: Optional[date] = None
    due_time: Optional[LocalTime] = None
    all_day: bool = False
    priority: int = Field(default=2, ge=1, le=4)
    date_ambiguous: bool = False

    @field_validator("due_time")
    @classmethod
    def local_time(cls, value):
        if value is not None and value.tzinfo is not None:
            raise ValueError("请返回HH:MM本地时间，不要添加时区")
        return value

    @model_validator(mode="after")
    def require_confirmation(self):
        if self.due_date is None:
            self.date_ambiguous = True
        return self


class ExtractedTaskList(BaseModel):
    model_config = ConfigDict(extra="forbid")
    tasks: list[ExtractedTask] = Field(default_factory=list)
    note: str = ""


class TaskPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    category: Optional[str] = Field(default=None, max_length=50)
    due_date: Optional[date] = None
    due_time: Optional[LocalTime] = None
    all_day: Optional[bool] = None
    priority: Optional[int] = Field(default=None, ge=1, le=4)
    estimated_hours: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)

    @model_validator(mode="before")
    @classmethod
    def omit_unchanged_fields(cls, values):
        # Small local models often emit every optional key as null. Null is not
        # an instruction to erase data. Set all_day=true to clear the time.
        if isinstance(values, dict):
            return {key: value for key, value in values.items() if value is not None}
        return values

    @model_validator(mode="after")
    def reject_null_required_fields(self):
        for key in self.model_fields_set - {"due_time"}:
            if getattr(self, key) is None:
                raise ValueError(f"{key} 不能设为空")
        return self


class SuggestedAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["update", "delete", "complete", "reopen"]
    task_id: int = Field(gt=0)
    fields: TaskPatch = Field(default_factory=TaskPatch)
    reason: str = ""

    @model_validator(mode="after")
    def check_action(self):
        values = self.fields.model_dump(exclude_unset=True)
        if self.action != "update" and values:
            raise ValueError("只有修改操作可携带字段")
        if self.action == "update" and not values:
            raise ValueError("修改操作必须包含字段")
        return self


class AIQueryResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reply: str
    suggested_actions: list[SuggestedAction] = Field(default_factory=list)
