"""Modelos Pydantic da API (docs/spec/05-api.md)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class PidValue(BaseModel):
    pid: str  # ex.: "0x0C"
    value: float
    unit: str
    rtt_ms: float


class SampleErrors(BaseModel):
    timeouts: int = 0
    invalid: int = 0


class Sample(BaseModel):
    seq: int = Field(ge=0)
    ts: float
    cycle_ms: float
    source: str  # "can_virtual" ou "elm327_tcp"
    values: dict[str, PidValue]
    errors: SampleErrors = Field(default_factory=SampleErrors)


class DtcEntry(BaseModel):
    code: str
    description: str
    status: Literal["stored", "pending"] = "stored"


class DtcReport(BaseModel):
    ts: float
    mil: bool
    count: int = Field(ge=0)
    codes: list[DtcEntry] = Field(default_factory=list)


class LatencyStats(BaseModel):
    mean: float
    p95: float
    p99: float
    max: float


class Stats(BaseModel):
    received: int = Field(ge=0)
    lost: int = Field(ge=0)
    duplicated: int = Field(ge=0)
    latency_ms: LatencyStats
    update_rate_hz: float
