from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Candidate:
    candidate_id: str
    time: datetime
    time_text: str
    index: int
    symbol: str
    side: str
    pattern: str
    entry: float
    sl: float
    tp: float
    risk: float
    risk_reward: float
    swing_time: str
    swing_price: float
    swing_kind: str
    features: dict[str, float | int | str | bool | None] = field(default_factory=dict)
    score: float = 0.0
    score_parts: dict[str, float | str] = field(default_factory=dict)


@dataclass(frozen=True)
class BacktestResult:
    candidate_id: str
    result: str
    r_multiple: float
    net_r_multiple: float
    exit_time: str
    exit_price: float
    exit_reason: str
    bars_held: int

