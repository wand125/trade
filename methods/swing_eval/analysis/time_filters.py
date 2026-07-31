from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from analysis.economic_calendar import EconomicEvent, event_blackout_reasons


@dataclass(frozen=True)
class TimeWindow:
    name: str
    start_minute: int
    end_minute: int

    def contains(self, moment: datetime) -> bool:
        minute = moment.hour * 60 + moment.minute
        if self.start_minute <= self.end_minute:
            return self.start_minute <= minute <= self.end_minute
        return minute >= self.start_minute or minute <= self.end_minute

    def label(self) -> str:
        return f"{self.name}@{format_minute(self.start_minute)}-{format_minute(self.end_minute)}"


def parse_minute(value: str) -> int:
    parts = value.split(":")
    if len(parts) != 2:
        raise ValueError(f"time must be HH:MM: {value}")
    hour = int(parts[0])
    minute = int(parts[1])
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
        raise ValueError(f"time out of range: {value}")
    return hour * 60 + minute


def format_minute(value: int) -> str:
    return f"{value // 60:02d}:{value % 60:02d}"


DEFAULT_BLACKOUT_WINDOWS = (
    TimeWindow("rollover", parse_minute("23:45"), parse_minute("00:15")),
    # MT5 server time is used. These are conservative proxies for common high-impact US release times.
    TimeWindow("us_0830_proxy", parse_minute("15:20"), parse_minute("15:40")),
    TimeWindow("us_1000_proxy", parse_minute("16:50"), parse_minute("17:10")),
    TimeWindow("fed_1400_proxy", parse_minute("20:50"), parse_minute("21:10")),
)


def blackout_reasons(
    moment: datetime,
    windows: tuple[TimeWindow, ...] = DEFAULT_BLACKOUT_WINDOWS,
    *,
    events: tuple[EconomicEvent, ...] | list[EconomicEvent] = (),
    news_before_minutes: int = 10,
    news_after_minutes: int = 10,
    news_min_impact: str = "high",
    news_currencies: tuple[str, ...] | list[str] | None = ("USD", "XAU", "ALL", "*"),
) -> list[str]:
    reasons = [window.label() for window in windows if window.contains(moment)]
    reasons.extend(
        event_blackout_reasons(
            moment,
            events,
            before_minutes=news_before_minutes,
            after_minutes=news_after_minutes,
            min_impact=news_min_impact,
            currencies=news_currencies,
        )
    )
    return reasons


def is_blackout_time(
    moment: datetime,
    windows: tuple[TimeWindow, ...] = DEFAULT_BLACKOUT_WINDOWS,
    *,
    events: tuple[EconomicEvent, ...] | list[EconomicEvent] = (),
    news_before_minutes: int = 10,
    news_after_minutes: int = 10,
    news_min_impact: str = "high",
    news_currencies: tuple[str, ...] | list[str] | None = ("USD", "XAU", "ALL", "*"),
) -> bool:
    return bool(
        blackout_reasons(
            moment,
            windows,
            events=events,
            news_before_minutes=news_before_minutes,
            news_after_minutes=news_after_minutes,
            news_min_impact=news_min_impact,
            news_currencies=news_currencies,
        )
    )


def parse_blackout_windows(spec: str | None) -> tuple[TimeWindow, ...]:
    if not spec or spec.strip().lower() in {"default", "defaults"}:
        return DEFAULT_BLACKOUT_WINDOWS
    if spec.strip().lower() in {"none", "off", "false"}:
        return ()

    windows: list[TimeWindow] = []
    for index, item in enumerate(part.strip() for part in spec.split(",") if part.strip()):
        if "@" in item:
            name, time_range = item.split("@", 1)
            name = name.strip() or f"window_{index + 1}"
        else:
            name = f"window_{index + 1}"
            time_range = item
        if "-" not in time_range:
            raise ValueError(f"blackout window must use HH:MM-HH:MM: {item}")
        start, end = [part.strip() for part in time_range.split("-", 1)]
        windows.append(TimeWindow(name, parse_minute(start), parse_minute(end)))
    return tuple(windows)
