from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


TIME_FORMATS = (
    "%Y.%m.%d %H:%M:%S",
    "%Y.%m.%d %H:%M",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y/%m/%d %H:%M:%S",
    "%Y/%m/%d %H:%M",
)
IMPACT_LEVELS = {
    "": 0,
    "none": 0,
    "low": 1,
    "l": 1,
    "medium": 2,
    "med": 2,
    "m": 2,
    "moderate": 2,
    "high": 3,
    "h": 3,
    "重要": 3,
}


@dataclass(frozen=True)
class EconomicEvent:
    time: datetime
    title: str
    currency: str = ""
    impact: str = ""
    source: str = ""

    def label(self) -> str:
        parts = ["news"]
        if self.currency:
            parts.append(self.currency)
        if self.impact:
            parts.append(normalize_impact(self.impact))
        if self.title:
            parts.append(self.title)
        return ":".join(parts) + "@" + self.time.strftime("%Y.%m.%d %H:%M")

    def as_dict(self) -> dict[str, object]:
        return {
            "time": self.time.strftime("%Y.%m.%d %H:%M:%S"),
            "title": self.title,
            "currency": self.currency,
            "impact": self.impact,
            "source": self.source,
        }


def load_economic_calendar(
    path: str | Path | None,
    *,
    missing_ok: bool = True,
    input_utc_offset_hours: float | None = None,
    server_utc_offset_hours: float | None = None,
) -> list[EconomicEvent]:
    if not path:
        return []
    calendar_path = Path(path)
    if not calendar_path.exists():
        if missing_ok:
            return []
        raise FileNotFoundError(calendar_path)

    if calendar_path.suffix.lower() == ".csv":
        with calendar_path.open(encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
    else:
        with calendar_path.open(encoding="utf-8") as f:
            payload = json.load(f)
        if isinstance(payload, dict):
            raw_rows = payload.get("events", [])
        else:
            raw_rows = payload
        if not isinstance(raw_rows, list):
            raise ValueError(f"{calendar_path} must contain a list or an object with events")
        rows = [row for row in raw_rows if isinstance(row, dict)]

    events: list[EconomicEvent] = []
    for row in rows:
        event = event_from_row(
            row,
            source=str(calendar_path),
            input_utc_offset_hours=input_utc_offset_hours,
            server_utc_offset_hours=server_utc_offset_hours,
        )
        if event is not None:
            events.append(event)
    return sorted(events, key=lambda event: event.time)


def event_from_row(
    row: dict[str, Any],
    *,
    source: str = "",
    input_utc_offset_hours: float | None = None,
    server_utc_offset_hours: float | None = None,
) -> EconomicEvent | None:
    row_input_offset = row_utc_offset(row) if input_utc_offset_hours is None else input_utc_offset_hours
    moment = parse_event_time(
        row,
        input_utc_offset_hours=row_input_offset,
        server_utc_offset_hours=server_utc_offset_hours,
    )
    if moment is None:
        return None
    return EconomicEvent(
        time=moment,
        title=first_text(row, "title", "event", "name", "indicator", "description"),
        currency=first_text(row, "currency", "ccy", "country", "symbol").upper(),
        impact=normalize_impact(first_text(row, "impact", "importance", "priority")),
        source=source,
    )


def parse_event_time(
    row: dict[str, Any],
    *,
    input_utc_offset_hours: float | None = None,
    server_utc_offset_hours: float | None = None,
) -> datetime | None:
    date = first_text(row, "date", "day")
    hour = first_text(row, "hour", "release_time", "time")
    direct = f"{date} {hour}" if date and hour else ""
    if not direct:
        direct = first_text(row, "server_time", "mt5_time", "datetime", "date_time", "time")
    if not direct:
        return None
    return parse_datetime(
        direct,
        input_utc_offset_hours=input_utc_offset_hours,
        server_utc_offset_hours=server_utc_offset_hours,
    )


def parse_datetime(
    value: str,
    *,
    input_utc_offset_hours: float | None = None,
    server_utc_offset_hours: float | None = None,
) -> datetime | None:
    text = value.strip()
    if not text:
        return None
    iso_text = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(iso_text)
        return convert_to_server_time(
            parsed,
            input_utc_offset_hours=input_utc_offset_hours,
            server_utc_offset_hours=server_utc_offset_hours,
        )
    except ValueError:
        pass
    normalized = text.replace("T", " ")
    for fmt in TIME_FORMATS:
        try:
            parsed = datetime.strptime(normalized, fmt)
            return convert_to_server_time(
                parsed,
                input_utc_offset_hours=input_utc_offset_hours,
                server_utc_offset_hours=server_utc_offset_hours,
            )
        except ValueError:
            continue
    return None


def convert_to_server_time(
    moment: datetime,
    *,
    input_utc_offset_hours: float | None = None,
    server_utc_offset_hours: float | None = None,
) -> datetime:
    if server_utc_offset_hours is None:
        return moment.replace(tzinfo=None)
    target = timezone(timedelta(hours=server_utc_offset_hours))
    if moment.tzinfo is not None:
        return moment.astimezone(target).replace(tzinfo=None)
    if input_utc_offset_hours is None:
        return moment
    source = timezone(timedelta(hours=input_utc_offset_hours))
    return moment.replace(tzinfo=source).astimezone(target).replace(tzinfo=None)


def event_blackout_reasons(
    moment: datetime,
    events: list[EconomicEvent] | tuple[EconomicEvent, ...],
    *,
    before_minutes: int = 10,
    after_minutes: int = 10,
    min_impact: str = "high",
    currencies: tuple[str, ...] | list[str] | None = ("USD", "XAU", "ALL", "*"),
) -> list[str]:
    reasons: list[str] = []
    for event in events:
        if not event_is_relevant(event, min_impact=min_impact, currencies=currencies):
            continue
        start = event.time - timedelta(minutes=before_minutes)
        end = event.time + timedelta(minutes=after_minutes)
        if start <= moment <= end:
            reasons.append(event.label())
    return reasons


def event_is_relevant(
    event: EconomicEvent,
    *,
    min_impact: str = "high",
    currencies: tuple[str, ...] | list[str] | None = ("USD", "XAU", "ALL", "*"),
) -> bool:
    if impact_rank(event.impact) < impact_rank(min_impact):
        return False
    if currencies is None:
        return True
    wanted = {currency.upper() for currency in currencies if currency}
    if "*" in wanted or "ALL" in wanted:
        return True
    if not event.currency:
        return True
    return event.currency.upper() in wanted


def parse_currencies(value: str | None) -> tuple[str, ...]:
    if value is None or not value.strip():
        return ("USD", "XAU", "ALL", "*")
    if value.strip().lower() in {"all", "*"}:
        return ("*",)
    return tuple(item.strip().upper() for item in value.split(",") if item.strip())


def row_utc_offset(row: dict[str, Any]) -> float | None:
    text = first_text(row, "utc_offset", "timezone_offset", "tz_offset", "offset")
    if not text:
        return None
    normalized = text.upper().replace("UTC", "").replace("GMT", "").strip()
    if not normalized:
        return 0.0
    try:
        return float(normalized)
    except ValueError:
        pass
    sign = -1 if normalized.startswith("-") else 1
    normalized = normalized.lstrip("+-")
    if ":" not in normalized:
        return None
    hour_text, minute_text = normalized.split(":", 1)
    try:
        return sign * (float(hour_text) + float(minute_text) / 60.0)
    except ValueError:
        return None


def normalize_impact(value: str) -> str:
    text = value.strip().lower()
    if text in {"重要", "high"}:
        return "high"
    if text in {"中", "medium", "moderate", "med"}:
        return "medium"
    if text in {"低", "low"}:
        return "low"
    return text


def impact_rank(value: str) -> int:
    return IMPACT_LEVELS.get(normalize_impact(value), 0)


def first_text(row: dict[str, Any], *keys: str) -> str:
    lower_map = {str(key).lower(): value for key, value in row.items()}
    for key in keys:
        value = lower_map.get(key.lower())
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""
