from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class EvalRunRequest(BaseModel):
    dataset: str = Field(default="default", max_length=200)


class EvalResultOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    case_id: str
    passed: bool
    expected: dict
    actual: dict
    detail: str | None
    latency_ms: int | None


class EvalRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    dataset_name: str
    provider: str
    status: str
    started_at: datetime
    finished_at: datetime | None
    summary: dict | None
    results: list[EvalResultOut] | None = None
