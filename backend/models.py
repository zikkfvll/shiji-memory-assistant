from datetime import datetime, timezone
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Input(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class ActivityInput(Input):
    title: str = Field(min_length=1, max_length=100)
    description: str = Field(default='', max_length=1000)


class ActivityPatch(Input):
    paused: bool | None = None
    status: Literal['active', 'completed'] | None = None


class RecordInput(Input):
    content: str = Field(min_length=1, max_length=8000)
    source_label: str = Field(default='我', min_length=1, max_length=80)
    source_kind: Literal['self', 'family', 'artifact'] = 'self'
    source_authorized: bool = False
    kind: Literal['plan', 'report', 'observation', 'experience', 'correction', 'change'] = 'report'
    occurred_at: str | None = None
    supersedes: str | None = None
    derived_from: list[str] = Field(default_factory=list, max_length=20)
    after_help_id: str | None = None

    @field_validator('occurred_at')
    @classmethod
    def valid_time(cls, value):
        if value is None:
            return None
        result = datetime.fromisoformat(value)
        if result.tzinfo is None:
            raise ValueError('时间需要包含时区')
        return result.astimezone(timezone.utc).isoformat(timespec='microseconds')

    @model_validator(mode='after')
    def relationships(self):
        if self.source_kind == 'family' and not self.source_authorized:
            raise ValueError('请确认对方同意保存这段内容')
        if (self.kind in ('correction', 'change')) != bool(self.supersedes):
            raise ValueError('更正或变化必须关联一条已有记录；普通记录不覆盖旧记录')
        return self


class HelpInput(Input):
    mode: Literal['answer', 'cue'] = 'answer'
    question: str = Field(default='', max_length=1000)


class ImportInput(Input):
    text: str = Field(min_length=1, max_length=12000)
    model_label: str = Field(min_length=1, max_length=120)
    source_ids: list[str] = Field(min_length=1, max_length=100)
    input_record_ids: list[str] | None = Field(default=None, max_length=1000)
    question: str = Field(default='', max_length=1000)
    prompt: str = Field(default='', max_length=16000)


class FeedbackInput(Input):
    kind: Literal['helpful', 'not_helpful', 'acknowledged', 'independent_report']
    content: str = Field(default='', max_length=4000)
