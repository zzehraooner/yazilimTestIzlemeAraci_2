from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, validator


class RunCreate(BaseModel):
    command: str = Field(..., min_length=1)
    baseline_run_id: Optional[int] = None


class RunBase(BaseModel):
    id: int
    command: str
    started_at: datetime | None
    ended_at: Optional[datetime]
    status: str
    exit_code: Optional[int]
    baseline_run_id: Optional[int]

    class Config:
        orm_mode = True


class RunStats(BaseModel):
    run_id: int
    avg_cpu: Optional[float]
    p95_cpu: Optional[float]
    max_cpu: Optional[float]
    avg_rss_mb: Optional[float]
    p95_rss_mb: Optional[float]
    duration_s: Optional[float]
    max_rss_mb: Optional[float] = None  # derived value

    class Config:
        orm_mode = True


class RunSummary(RunBase):
    stats: Optional[RunStats]


class RunDetail(RunBase):
    stats: Optional[RunStats]


class RunCreateResponse(BaseModel):
    id: int
    started_at: datetime


class RunFinishRequest(BaseModel):
    exit_code: int


class MetricSampleIn(BaseModel):
    ts: float
    cpu_percent: float
    rss_mb: float

    @validator("cpu_percent", "rss_mb")
    def non_negative(cls, value: float) -> float:
        if value < 0:
            raise ValueError("Metric values must be non-negative")
        return value


class RunSamplesResponse(BaseModel):
    samples: List[MetricSampleIn]


class ComparisonMetrics(BaseModel):
    avg_cpu: Optional[float]
    p95_cpu: Optional[float]
    max_cpu: Optional[float]
    avg_rss_mb: Optional[float]
    p95_rss_mb: Optional[float]
    duration_s: Optional[float]


class ComparisonResponse(BaseModel):
    current_run: RunSummary
    baseline_run: RunSummary
    messages: List[str]
