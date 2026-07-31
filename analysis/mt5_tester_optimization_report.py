from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analysis.market_data import TIME_FORMAT
from analysis.mt5_forward_collect import DEFAULT_FILENAME
from analysis.mt5_forward_report import (
    append_score_threshold_table,
    append_side_score_diagnostics,
    exit_reason,
    group_sort_key,
    group_value,
    number,
    price_r_multiple,
    score_threshold_summary,
    server_datetime,
    side_score_diagnostics,
    take_profit_points,
)
from analysis.mt5_optimization_recommend import estimate_set_passes


DEFAULT_OUTPUT_JSON = "runtime/latest_mt5_optimization_report.json"
DEFAULT_OUTPUT_MD = "runtime/latest_mt5_optimization_report.md"
SPREADSHEET_NS = "urn:schemas-microsoft-com:office:spreadsheet"
TESTER_PARAMETER_KEYS = (
    "InpSwingDepth",
    "InpSwingAtrBand",
    "InpMinScore",
    "InpBuyRiskReward",
    "InpSellRiskReward",
    "InpStopBufferPoints",
    "InpUseFittedBuyBreakFilter",
    "InpUseBuyM30M15UpGate",
    "InpUseFittedBuyEntryFilter",
    "InpBuyRequireBreakConfirm",
    "InpBuyMinM1ClosePosition",
    "InpBuyMinM1BodyAtr",
    "InpBuyMinM5CloseSlowAtr",
    "InpUseFittedBuyTimeFilter",
    "InpBuyBlockedServerHours",
    "InpUseFittedBuyCalendarFilter",
    "InpBuyBlockedMonths",
    "InpBuyBlockedWeekdays",
    "InpUseBuyAllowedServerHours",
    "InpBuyAllowedServerHours",
    "InpUseFittedSellFilter",
    "InpUseFittedSellTrendFilter",
    "InpUseSellM30M15DownGate",
    "InpUseFittedSellTimeFilter",
    "InpUseFittedSellCalendarFilter",
    "InpUseSellAllowedServerHours",
    "InpUseFittedSellEntryFilter",
    "InpSellRequireBreakConfirm",
    "InpSellBlockedServerHours",
    "InpSellBlockedMonths",
    "InpSellBlockedWeekdays",
    "InpSellAllowedServerHours",
    "InpSellMinM5CloseSlowAtr",
    "InpSellMinM1AlternatingRatio",
    "InpSellMaxM1ClosePosition",
    "InpSellMinM1BodyAtr",
    "InpSellMaxM5CloseSlowAtr",
)


def default_tester_root() -> Path:
    return (
        Path.home()
        / "Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5/Tester"
    )


def discover_tester_csvs(
    source_roots: list[str | Path] | None = None,
    *,
    filename: str = DEFAULT_FILENAME,
    since_minutes: float = 180.0,
    modified_after_epoch: float | None = None,
    modified_before_epoch: float | None = None,
) -> list[Path]:
    roots = [Path(root).expanduser() for root in (source_roots or [default_tester_root()])]
    cutoff = time.time() - since_minutes * 60.0 if since_minutes > 0 else None
    candidates: list[Path] = []
    for root in roots:
        if not root.exists():
            continue
        if root.is_file():
            paths = [root] if root.name == filename else []
        else:
            paths = list(root.rglob(filename))
        for path in paths:
            if not path.is_file():
                continue
            stat = path.stat()
            if cutoff is not None and stat.st_mtime < cutoff:
                continue
            if modified_after_epoch is not None and stat.st_mtime < modified_after_epoch:
                continue
            if modified_before_epoch is not None and stat.st_mtime > modified_before_epoch:
                continue
            candidates.append(path)
    return sorted(set(candidates), key=lambda path: (path.stat().st_mtime, str(path)), reverse=True)


def parse_modified_after(value: str | None) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        pass
    for fmt in (TIME_FORMAT, "%Y.%m.%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).timestamp()
        except ValueError:
            continue
    raise ValueError(f"invalid modified-after value: {value!r}")


def format_epoch(value: float | None) -> str:
    if value is None:
        return ""
    return datetime.fromtimestamp(value).strftime(TIME_FORMAT)


@dataclass
class RunningStats:
    closed: int = 0
    wins: int = 0
    losses: int = 0
    breakeven: int = 0
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    net_profit: float = 0.0
    price_r_sum: float = 0.0
    price_r_count: int = 0
    price_r_values: list[float] | None = None
    stop_sum: float = 0.0
    stop_count: int = 0
    tp_points_sum: float = 0.0
    tp_points_count: int = 0
    tp_closes: int = 0
    sl_closes: int = 0
    early_profit_closes: int = 0
    early_loss_closes: int = 0
    other_closes: int = 0

    def add_close(self, row: dict[str, str]) -> None:
        value = number(row.get("net_profit")) or 0.0
        self.closed += 1
        self.net_profit += value
        if value > 0:
            self.wins += 1
            self.gross_profit += value
        elif value < 0:
            self.losses += 1
            self.gross_loss += -value
        else:
            self.breakeven += 1

        price_r = price_r_multiple(row)
        if price_r is not None:
            self.price_r_sum += price_r
            self.price_r_count += 1
            if self.price_r_values is None:
                self.price_r_values = []
            self.price_r_values.append(price_r)
        stop_points = number(row.get("stop_points"))
        if stop_points is not None:
            self.stop_sum += stop_points
            self.stop_count += 1
        tp_points = take_profit_points(row)
        if tp_points is not None:
            self.tp_points_sum += tp_points
            self.tp_points_count += 1

        reason = exit_reason(row)
        if reason == "tp":
            self.tp_closes += 1
        elif reason == "sl":
            self.sl_closes += 1
        elif reason == "early_profit":
            self.early_profit_closes += 1
        elif reason == "early_loss":
            self.early_loss_closes += 1
        else:
            self.other_closes += 1

    def to_dict(self, *, group: str | None = None, dimension: str | None = None) -> dict[str, Any]:
        closed = max(self.closed, 1)
        payload: dict[str, Any] = {}
        if dimension is not None:
            payload["dimension"] = dimension
        if group is not None:
            payload["group"] = group
        avg_price_r = round(self.price_r_sum / self.price_r_count, 4) if self.price_r_count else 0.0
        payload.update(
            {
                "closed": self.closed,
                "wins": self.wins,
                "losses": self.losses,
                "breakeven": self.breakeven,
                "win_rate": round(self.wins / closed, 4) if self.closed else 0.0,
                "gross_profit": round(self.gross_profit, 2),
                "gross_loss": round(self.gross_loss, 2),
                "net_profit": round(self.net_profit, 2),
                "avg_net": round(self.net_profit / closed, 2) if self.closed else 0.0,
                "pf": profit_factor(self.gross_profit, self.gross_loss),
                "avg_price_r": avg_price_r,
                "max_drawdown_price_r": round(max_drawdown(self.price_r_values or []), 4),
                "expectancy_price_r": avg_price_r,
                "avg_stop_points": round(self.stop_sum / self.stop_count, 2) if self.stop_count else 0.0,
                "avg_take_profit_points": round(self.tp_points_sum / self.tp_points_count, 2)
                if self.tp_points_count
                else 0.0,
                "tp_closes": self.tp_closes,
                "sl_closes": self.sl_closes,
                "early_profit_closes": self.early_profit_closes,
                "early_loss_closes": self.early_loss_closes,
                "other_closes": self.other_closes,
                "tp_rate": round(self.tp_closes / closed, 4) if self.closed else 0.0,
                "sl_rate": round(self.sl_closes / closed, 4) if self.closed else 0.0,
                "early_loss_rate": round(self.early_loss_closes / closed, 4) if self.closed else 0.0,
            }
        )
        return payload


def profit_factor(gross_profit: float, gross_loss: float) -> float:
    if gross_loss > 0:
        return round(gross_profit / gross_loss, 4)
    return 99.0 if gross_profit > 0 else 0.0


def max_drawdown(values: list[float]) -> float:
    equity = 0.0
    peak = 0.0
    maximum = 0.0
    for value in values:
        equity += value
        peak = max(peak, equity)
        maximum = max(maximum, peak - equity)
    return maximum


def chronological_sort_key(index: int, row: dict[str, str]) -> tuple[float, int]:
    moment = server_datetime(row)
    if moment is None:
        return (float("inf"), index)
    return (moment.timestamp(), index)


def chronological_time_text(row: dict[str, str]) -> str:
    moment = server_datetime(row)
    if moment is None:
        return str(row.get("server_time") or "")
    return moment.strftime("%Y.%m.%d %H:%M:%S")


def source_time_coverage(rows: list[dict[str, str]]) -> dict[str, Any]:
    moments = [moment for moment in (server_datetime(row) for row in rows) if moment is not None]
    first = min(moments) if moments else None
    last = max(moments) if moments else None
    span_days = None
    if first is not None and last is not None:
        span_days = round((last - first).total_seconds() / 86400.0, 4)
    return {
        "close_rows": len(rows),
        "close_rows_with_server_time": len(moments),
        "close_rows_without_server_time": len(rows) - len(moments),
        "first_server_time": first.strftime("%Y.%m.%d %H:%M:%S") if first else "",
        "last_server_time": last.strftime("%Y.%m.%d %H:%M:%S") if last else "",
        "span_days": span_days,
    }


def parse_expected_date(value: str | None) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in ("%Y.%m.%d", "%Y-%m-%d", "%Y.%m.%d %H:%M:%S", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    raise ValueError(f"invalid expected date value: {value!r}")


def source_time_diagnostics(
    coverage: dict[str, Any],
    *,
    expected_from_date: str | None = None,
    expected_to_date: str | None = None,
) -> dict[str, Any]:
    warnings: list[str] = []
    expected_from = parse_expected_date(expected_from_date)
    expected_to = parse_expected_date(expected_to_date)
    first = parse_expected_date(str(coverage.get("first_server_time") or ""))
    last = parse_expected_date(str(coverage.get("last_server_time") or ""))
    expected_present = expected_from is not None or expected_to is not None
    matches_expected_range: bool | None = None

    if expected_present:
        if first is None or last is None:
            matches_expected_range = False
            warnings.append("close server_time unavailable; cannot verify expected Tester date range")
        else:
            matches_expected_range = True
            if expected_from is not None and first.date() < expected_from.date():
                matches_expected_range = False
                warnings.append(
                    f"first close {first.strftime('%Y.%m.%d')} is before expected FromDate "
                    f"{expected_from.strftime('%Y.%m.%d')}"
                )
            if expected_to is not None and last.date() > expected_to.date():
                matches_expected_range = False
                warnings.append(
                    f"last close {last.strftime('%Y.%m.%d')} is after expected ToDate "
                    f"{expected_to.strftime('%Y.%m.%d')}"
                )
    return {
        "expected_from_date": expected_from.strftime("%Y.%m.%d") if expected_from else "",
        "expected_to_date": expected_to.strftime("%Y.%m.%d") if expected_to else "",
        "actual_first_server_time": coverage.get("first_server_time", ""),
        "actual_last_server_time": coverage.get("last_server_time", ""),
        "actual_span_days": coverage.get("span_days"),
        "matches_expected_range": matches_expected_range,
        "warnings": warnings,
    }


def source_time_mismatch(summary: dict[str, Any]) -> bool:
    diagnostics = summary.get("source_time_diagnostics") if isinstance(summary, dict) else None
    if not isinstance(diagnostics, dict):
        return False
    expected_from = str(diagnostics.get("expected_from_date") or "").strip()
    expected_to = str(diagnostics.get("expected_to_date") or "").strip()
    if not expected_from and not expected_to:
        return False
    return diagnostics.get("matches_expected_range") is False


def source_time_mismatch_reason(summary: dict[str, Any]) -> str:
    diagnostics = summary.get("source_time_diagnostics") if isinstance(summary, dict) else {}
    if not isinstance(diagnostics, dict):
        return "source_time_diagnostics missing"
    warnings = diagnostics.get("warnings")
    warning_text = "; ".join(map(str, warnings)) if isinstance(warnings, list) and warnings else ""
    expected_from = str(diagnostics.get("expected_from_date") or "")
    expected_to = str(diagnostics.get("expected_to_date") or "")
    actual_first = str(diagnostics.get("actual_first_server_time") or "")
    actual_last = str(diagnostics.get("actual_last_server_time") or "")
    detail = f"expected {expected_from}/{expected_to}, actual {actual_first}/{actual_last}"
    return f"{detail}; {warning_text}" if warning_text else detail


def csv_file_source_time_coverage(path: str | Path) -> dict[str, Any]:
    close_rows: list[dict[str, str]] = []
    with Path(path).open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            if str(row.get("event") or "").lower() == "close":
                close_rows.append(row)
    return source_time_coverage(close_rows)


def filter_paths_by_expected_source_time(
    paths: list[Path],
    *,
    expected_from_date: str | None,
    expected_to_date: str | None,
) -> tuple[list[Path], dict[str, Any]]:
    status: dict[str, Any] = {
        "enabled": True,
        "expected_from_date": str(expected_from_date or ""),
        "expected_to_date": str(expected_to_date or ""),
        "input_files": len(paths),
        "kept_files": 0,
        "dropped_files": [],
    }
    expected_present = bool(str(expected_from_date or "").strip() or str(expected_to_date or "").strip())
    if not expected_present:
        status["kept_files"] = len(paths)
        status["note"] = "expected date range not provided; no files dropped"
        return paths, status

    kept: list[Path] = []
    dropped: list[dict[str, Any]] = []
    for path in paths:
        coverage = csv_file_source_time_coverage(path)
        diagnostics = source_time_diagnostics(
            coverage,
            expected_from_date=expected_from_date,
            expected_to_date=expected_to_date,
        )
        if diagnostics.get("matches_expected_range") is False:
            dropped.append(
                {
                    "path": str(path),
                    "source_time": coverage,
                    "diagnostics": diagnostics,
                    "reason": source_time_filter_reason(diagnostics),
                }
            )
            continue
        kept.append(path)

    status["kept_files"] = len(kept)
    status["dropped_files"] = dropped
    return kept, status


def source_time_filter_reason(diagnostics: dict[str, Any]) -> str:
    warnings = diagnostics.get("warnings")
    if isinstance(warnings, list) and warnings:
        return "; ".join(str(item) for item in warnings)
    return "source_time outside expected date range"


def chronological_split_diagnostics(rows: list[dict[str, str]], *, weak_pf: float) -> list[dict[str, Any]]:
    ordered_rows = [
        row
        for _, row in sorted(
            enumerate(rows),
            key=lambda item: chronological_sort_key(item[0], item[1]),
        )
    ]
    if not ordered_rows:
        return []

    results: list[dict[str, Any]] = []
    split_specs = (
        ("chronological_half", ("first_half", "second_half")),
        ("chronological_quarter", ("q1", "q2", "q3", "q4")),
    )
    for dimension, labels in split_specs:
        bucket_count = len(labels)
        for index, label in enumerate(labels):
            start = index * len(ordered_rows) // bucket_count
            end = (index + 1) * len(ordered_rows) // bucket_count
            bucket = ordered_rows[start:end]
            if not bucket:
                continue
            stats = RunningStats()
            for row in bucket:
                stats.add_close(row)
            payload = stats.to_dict(group=label, dimension=dimension)
            payload["start_time"] = chronological_time_text(bucket[0])
            payload["end_time"] = chronological_time_text(bucket[-1])
            if float(payload["pf"]) < weak_pf or float(payload["avg_price_r"]) < 0.0:
                payload["diagnosis"] = chronological_split_diagnosis(payload)
            results.append(payload)
    return results


def chronological_split_diagnosis(row: dict[str, Any]) -> str:
    group = str(row.get("group") or "")
    pf = float(row.get("pf") or 0.0)
    avg_r = float(row.get("avg_price_r") or 0.0)
    closed = int(row.get("closed") or 0)
    return f"chronological split failed: {group}; PF {pf:.4f}, avg R {avg_r:.4f}, closed {closed}"


def summarize_optimization_csvs(
    paths: list[str | Path],
    *,
    min_closed: int = 30,
    weak_pf: float = 1.0,
    expected_from_date: str | None = None,
    expected_to_date: str | None = None,
) -> dict[str, Any]:
    event_counts: Counter[str] = Counter()
    source_rows = 0
    overall = RunningStats()
    dimensions = {
        "by_action": "action",
        "by_risk_reward": "risk_reward",
        "by_action_risk_reward": "action_risk_reward",
        "by_stop_points": "action_stop_points_band",
        "by_take_profit_points": "action_take_profit_points_band",
        "by_risk_reward_stop_points": "action_rr_stop_points_band",
        "by_risk_reward_take_profit_points": "action_rr_take_profit_points_band",
        "by_quarter": "server_quarter",
        "by_month": "server_month",
        "by_weekday": "server_weekday",
        "by_server_hour": "server_hour",
        "by_entry_server_hour": "entry_server_hour",
        "by_action_risk_reward_month": "action_risk_reward_month",
        "by_m30_trend": "m30_trend",
        "by_m15_trend": "m15_trend",
        "by_m5_trend": "m5_trend",
        "by_m30_slope": "m30_slope",
        "by_m15_slope": "m15_slope",
        "by_m30_m15_trend": "m30_m15_trend",
        "by_trend_alignment": "trend_alignment",
        "by_action_trend_alignment": "action_trend_alignment",
        "by_action_m30_m15_trend": "action_m30_m15_trend",
    }
    grouped: dict[str, defaultdict[str, RunningStats]] = {
        name: defaultdict(RunningStats) for name in dimensions
    }
    file_infos: list[dict[str, Any]] = []
    close_rows: list[dict[str, str]] = []

    for raw_path in paths:
        path = Path(raw_path)
        stat = path.stat()
        rows_in_file = 0
        closes_in_file = 0
        close_rows_in_file: list[dict[str, str]] = []
        with path.open(encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                rows_in_file += 1
                source_rows += 1
                event = str(row.get("event") or "").lower()
                event_counts[event] += 1
                if event != "close":
                    continue
                closes_in_file += 1
                close_rows_in_file.append(row)
                close_rows.append(row)
                overall.add_close(row)
                for name, key in dimensions.items():
                    grouped[name][group_value(row, key)].add_close(row)
        file_infos.append(
            {
                "path": str(path),
                "agent": tester_agent_name(path),
                "mtime": datetime.fromtimestamp(stat.st_mtime).strftime(TIME_FORMAT),
                "size": stat.st_size,
                "rows": rows_in_file,
                "closed": closes_in_file,
                "source_time": source_time_coverage(close_rows_in_file),
            }
        )

    group_payloads = {
        name: format_group_stats(stats, min_closed=0)
        for name, stats in grouped.items()
    }
    weak_segments = find_segments(grouped, min_closed=min_closed, weak_pf=weak_pf, weak=True)
    best_segments = find_segments(grouped, min_closed=min_closed, weak_pf=weak_pf, weak=False)
    weak_time_segments = find_time_segments(grouped, min_closed=min_closed, weak_pf=weak_pf, weak=True)
    best_time_segments = find_time_segments(grouped, min_closed=min_closed, weak_pf=weak_pf, weak=False)
    weak_trend_segments = find_trend_segments(grouped, min_closed=min_closed, weak_pf=weak_pf, weak=True)
    best_trend_segments = find_trend_segments(grouped, min_closed=min_closed, weak_pf=weak_pf, weak=False)
    score_thresholds = score_threshold_summary(close_rows)
    coverage = source_time_coverage(close_rows)

    return {
        "generated_at": datetime.now().strftime(TIME_FORMAT),
        "files": file_infos,
        "source_rows": source_rows,
        "source_time_coverage": coverage,
        "source_time_diagnostics": source_time_diagnostics(
            coverage,
            expected_from_date=expected_from_date,
            expected_to_date=expected_to_date,
        ),
        "event_counts": dict(sorted(event_counts.items())),
        "overall": overall.to_dict(),
        **group_payloads,
        "chronological_splits": chronological_split_diagnostics(close_rows, weak_pf=weak_pf),
        "weak_segments": weak_segments,
        "best_segments": best_segments,
        "weak_time_segments": weak_time_segments,
        "best_time_segments": best_time_segments,
        "weak_trend_segments": weak_trend_segments,
        "best_trend_segments": best_trend_segments,
        "score_thresholds": score_thresholds,
        "side_score_diagnostics": side_score_diagnostics(score_thresholds, min_closed=min_closed),
        "parameters": {
            "min_closed": min_closed,
            "weak_pf": weak_pf,
            "expected_from_date": str(expected_from_date or ""),
            "expected_to_date": str(expected_to_date or ""),
        },
    }


def default_tester_xml_paths() -> tuple[Path, Path]:
    root = default_tester_root()
    return (
        root / "Swing_Evaluation_Trader_optimization.xml",
        root / "Swing_Evaluation_Trader_optimization.forward.xml",
    )


def parse_excel_xml_table(path: str | Path) -> list[dict[str, str]]:
    root = ET.parse(path).getroot()
    rows = root.findall(f".//{{{SPREADSHEET_NS}}}Worksheet/{{{SPREADSHEET_NS}}}Table/{{{SPREADSHEET_NS}}}Row")
    parsed_rows = [excel_xml_row_values(row) for row in rows]
    if not parsed_rows:
        return []
    headers = [str(value or "").strip() for value in parsed_rows[0]]
    table: list[dict[str, str]] = []
    for values in parsed_rows[1:]:
        row = {}
        for index, header in enumerate(headers):
            if not header:
                continue
            row[header] = values[index] if index < len(values) else ""
        if any(value != "" for value in row.values()):
            table.append(row)
    return table


def excel_xml_row_values(row: ET.Element) -> list[str]:
    values: list[str] = []
    for cell in row.findall(f"{{{SPREADSHEET_NS}}}Cell"):
        index_attr = cell.attrib.get(f"{{{SPREADSHEET_NS}}}Index")
        if index_attr:
            target = max(int(index_attr) - 1, 0)
            while len(values) < target:
                values.append("")
        data = cell.find(f"{{{SPREADSHEET_NS}}}Data")
        values.append(data.text if data is not None and data.text is not None else "")
    return values


def attach_tester_xml_summary(
    summary: dict[str, Any],
    *,
    back_xml: str | Path | None = None,
    forward_xml: str | Path | None = None,
    limit: int = 10,
) -> None:
    default_back, default_forward = default_tester_xml_paths()
    back_path = Path(back_xml).expanduser() if back_xml else default_back
    forward_path = Path(forward_xml).expanduser() if forward_xml else default_forward
    payload: dict[str, Any] = {}
    if back_path.exists():
        rows = parse_excel_xml_table(back_path)
        payload["back"] = {
            "path": str(back_path),
            "rows": len(rows),
            "top": top_tester_rows(rows, "Result", limit=limit),
            "parameter_diagnostics": tester_parameter_diagnostics(rows, "Result", limit=limit),
        }
    if forward_path.exists():
        rows = parse_excel_xml_table(forward_path)
        top_forward = top_tester_rows(rows, "Forward Result", limit=limit)
        stable_forward = [
            row
            for row in rows
            if (number(row.get("Forward Result")) or 0.0) > 0.0
            and (number(row.get("Back Result")) or 0.0) > 0.0
        ]
        forward_only = [
            row
            for row in rows
            if (number(row.get("Forward Result")) or 0.0) > 0.0
            and (number(row.get("Back Result")) or 0.0) < 0.0
        ]
        payload["forward"] = {
            "path": str(forward_path),
            "rows": len(rows),
            "top": top_forward,
            "stable_top": top_tester_rows(stable_forward, "Forward Result", limit=limit),
            "forward_only_top": top_tester_rows(forward_only, "Forward Result", limit=limit),
            "parameter_diagnostics": tester_parameter_diagnostics(rows, "Forward Result", limit=limit),
            "positive_forward_negative_back": sum(
                1
                for row in forward_only
            ),
            "positive_forward_positive_back": sum(
                1
                for row in stable_forward
            ),
        }
    if payload:
        summary["tester_xml"] = payload


def attach_set_pass_budget(summary: dict[str, Any], set_file: str | Path | None) -> None:
    if not set_file:
        return
    path = Path(set_file).expanduser()
    budget: dict[str, Any] = {
        "set_file": str(path),
        "available": path.exists(),
        "note": "Full-factorial candidates are an upper bound; MT5 genetic optimization may execute fewer passes.",
    }
    if not path.exists():
        budget["reason"] = "set file not found"
        summary["optimization_pass_budget"] = budget
        return
    try:
        budget.update(estimate_set_passes(path.read_text(encoding="utf-8")))
    except OSError as exc:
        budget["available"] = False
        budget["reason"] = str(exc)
    executed_rows = tester_xml_row_counts(summary)
    if executed_rows:
        budget["executed_tester_xml_rows"] = executed_rows
    summary["optimization_pass_budget"] = budget


def tester_xml_row_counts(summary: dict[str, Any]) -> dict[str, int]:
    tester_xml = summary.get("tester_xml") if isinstance(summary.get("tester_xml"), dict) else {}
    counts: dict[str, int] = {}
    for key in ("back", "forward"):
        payload = tester_xml.get(key) if isinstance(tester_xml.get(key), dict) else {}
        rows = payload.get("rows")
        if isinstance(rows, bool):
            continue
        if isinstance(rows, int):
            counts[key] = rows
            continue
        try:
            counts[key] = int(str(rows))
        except (TypeError, ValueError):
            continue
    return counts


def tester_parameter_diagnostics(rows: list[dict[str, str]], result_key: str, *, limit: int) -> list[dict[str, Any]]:
    diagnostics: list[dict[str, Any]] = []
    for key in TESTER_PARAMETER_KEYS:
        grouped: defaultdict[str, list[dict[str, str]]] = defaultdict(list)
        for row in rows:
            if key not in row:
                continue
            raw_value = str(row.get(key) or "")
            if raw_value == "":
                continue
            grouped[raw_value].append(row)
        if len(grouped) < 2:
            continue
        groups = [tester_parameter_group_summary(raw_value, group_rows, result_key) for raw_value, group_rows in grouped.items()]
        groups = [group for group in groups if group["passes"] > 0]
        if len(groups) < 2:
            continue
        groups.sort(key=lambda group: (float(group["avg_result"]), float(group["avg_pf"]), int(group["passes"])), reverse=True)
        diagnostics.append(
            {
                "parameter": key,
                "groups": groups[:limit],
                "spread_avg_result": round(float(groups[0]["avg_result"]) - float(groups[-1]["avg_result"]), 4),
                "spread_avg_pf": round(float(groups[0]["avg_pf"]) - float(groups[-1]["avg_pf"]), 4),
            }
        )
    diagnostics.sort(
        key=lambda item: (
            abs(float(item.get("spread_avg_result") or 0.0)),
            abs(float(item.get("spread_avg_pf") or 0.0)),
        ),
        reverse=True,
    )
    return diagnostics[:limit]


def tester_parameter_group_summary(raw_value: str, rows: list[dict[str, str]], result_key: str) -> dict[str, Any]:
    result_values = [value for value in (number(row.get(result_key)) for row in rows) if value is not None]
    pf_values = [value for value in (number(row.get("Profit Factor")) for row in rows) if value is not None]
    trade_values = [value for value in (number(row.get("Trades")) for row in rows) if value is not None]
    return {
        "value": typed_cell(raw_value),
        "passes": len(rows),
        "positive_result": sum(1 for value in result_values if value > 0.0),
        "avg_result": round(sum(result_values) / len(result_values), 4) if result_values else 0.0,
        "max_result": round(max(result_values), 4) if result_values else 0.0,
        "avg_pf": round(sum(pf_values) / len(pf_values), 4) if pf_values else 0.0,
        "max_pf": round(max(pf_values), 4) if pf_values else 0.0,
        "avg_trades": round(sum(trade_values) / len(trade_values), 1) if trade_values else 0.0,
    }


def top_tester_rows(rows: list[dict[str, str]], score_key: str, *, limit: int) -> list[dict[str, Any]]:
    selected = sorted(rows, key=lambda row: number(row.get(score_key)) or -1e100, reverse=True)[:limit]
    keys = [
        "Pass",
        "Result",
        "Forward Result",
        "Back Result",
        "Profit",
        "Expected Payoff",
        "Profit Factor",
        "Recovery Factor",
        "Sharpe Ratio",
        "Custom",
        "Equity DD %",
        "Trades",
        *TESTER_PARAMETER_KEYS,
    ]
    return [{key: typed_cell(row.get(key, "")) for key in keys if key in row} for row in selected]


def typed_cell(value: str) -> Any:
    text = str(value)
    if text.lower() in {"true", "false"}:
        return text.lower() == "true"
    numeric = number(text)
    if numeric is None:
        return text
    if numeric.is_integer() and not any(char in text for char in (".", "e", "E")):
        return int(numeric)
    return round(numeric, 6)


def tester_agent_name(path: Path) -> str:
    for parent in path.parents:
        if parent.name.startswith("Agent-"):
            return parent.name
    return ""


def format_group_stats(stats: dict[str, RunningStats], *, min_closed: int) -> list[dict[str, Any]]:
    rows = [
        stat.to_dict(group=group)
        for group, stat in stats.items()
        if stat.closed >= min_closed
    ]
    return sorted(rows, key=lambda row: group_sort_key(str(row.get("group") or "")))


def find_segments(
    grouped: dict[str, defaultdict[str, RunningStats]],
    *,
    min_closed: int,
    weak_pf: float,
    weak: bool,
    limit: int = 15,
) -> list[dict[str, Any]]:
    dimensions = (
        "by_action_risk_reward",
        "by_stop_points",
        "by_take_profit_points",
        "by_risk_reward_stop_points",
        "by_risk_reward_take_profit_points",
    )
    rows: list[dict[str, Any]] = []
    for dimension in dimensions:
        for group, stats in grouped[dimension].items():
            if stats.closed < min_closed:
                continue
            payload = stats.to_dict(group=group, dimension=dimension)
            if weak:
                if float(payload["pf"]) >= weak_pf and float(payload["avg_price_r"]) >= 0:
                    continue
                payload["diagnosis"] = segment_diagnosis(payload)
            else:
                if float(payload["pf"]) < weak_pf or float(payload["avg_price_r"]) <= 0:
                    continue
            rows.append(payload)
    if weak:
        rows.sort(key=lambda row: (float(row["pf"]), float(row["net_profit"]), -int(row["closed"])))
    else:
        rows.sort(key=lambda row: (float(row["pf"]), float(row["avg_price_r"]), float(row["net_profit"])), reverse=True)
    return rows[:limit]


def find_time_segments(
    grouped: dict[str, defaultdict[str, RunningStats]],
    *,
    min_closed: int,
    weak_pf: float,
    weak: bool,
    limit: int = 15,
) -> list[dict[str, Any]]:
    dimensions = (
        "by_quarter",
        "by_month",
        "by_weekday",
        "by_server_hour",
        "by_entry_server_hour",
        "by_action_risk_reward_month",
    )
    rows: list[dict[str, Any]] = []
    for dimension in dimensions:
        for group, stats in grouped[dimension].items():
            if stats.closed < min_closed:
                continue
            payload = stats.to_dict(group=group, dimension=dimension)
            if weak:
                if float(payload["pf"]) >= weak_pf and float(payload["avg_price_r"]) >= 0:
                    continue
                payload["diagnosis"] = time_segment_diagnosis(payload)
            else:
                if float(payload["pf"]) < weak_pf or float(payload["avg_price_r"]) <= 0:
                    continue
            rows.append(payload)
    if weak:
        rows.sort(key=lambda row: (float(row["pf"]), float(row["net_profit"]), -int(row["closed"])))
    else:
        rows.sort(key=lambda row: (float(row["pf"]), float(row["avg_price_r"]), float(row["net_profit"])), reverse=True)
    return rows[:limit]


def find_trend_segments(
    grouped: dict[str, defaultdict[str, RunningStats]],
    *,
    min_closed: int,
    weak_pf: float,
    weak: bool,
    limit: int = 15,
) -> list[dict[str, Any]]:
    dimensions = (
        "by_m30_trend",
        "by_m15_trend",
        "by_m5_trend",
        "by_m30_slope",
        "by_m15_slope",
        "by_m30_m15_trend",
        "by_trend_alignment",
        "by_action_trend_alignment",
        "by_action_m30_m15_trend",
    )
    rows: list[dict[str, Any]] = []
    for dimension in dimensions:
        for group, stats in grouped[dimension].items():
            if stats.closed < min_closed:
                continue
            payload = stats.to_dict(group=group, dimension=dimension)
            if weak:
                if float(payload["pf"]) >= weak_pf and float(payload["avg_price_r"]) >= 0:
                    continue
                payload["diagnosis"] = trend_segment_diagnosis(payload)
            else:
                if float(payload["pf"]) < weak_pf or float(payload["avg_price_r"]) <= 0:
                    continue
            rows.append(payload)
    if weak:
        rows.sort(key=lambda row: (float(row["pf"]), float(row["net_profit"]), -int(row["closed"])))
    else:
        rows.sort(key=lambda row: (float(row["pf"]), float(row["avg_price_r"]), float(row["net_profit"])), reverse=True)
    return rows[:limit]


def trend_segment_diagnosis(row: dict[str, Any]) -> str:
    group = str(row.get("group") or "")
    pf = float(row.get("pf") or 0.0)
    avg_r = float(row.get("avg_price_r") or 0.0)
    closed = int(row.get("closed") or 0)
    if "unknown" in group:
        return f"trend regime unavailable in CSV; PF {pf:.4f}, avg R {avg_r:.4f}, closed {closed}"
    return f"trend regime failed: {group}; PF {pf:.4f}, avg R {avg_r:.4f}, closed {closed}"


def time_segment_diagnosis(row: dict[str, Any]) -> str:
    dimension = str(row.get("dimension") or "")
    group = str(row.get("group") or "")
    pf = float(row.get("pf") or 0.0)
    avg_r = float(row.get("avg_price_r") or 0.0)
    closed = int(row.get("closed") or 0)
    if dimension == "by_action_risk_reward_month":
        return f"RR/month regime failed: {group}; PF {pf:.4f}, avg R {avg_r:.4f}, closed {closed}"
    if dimension in {"by_month", "by_quarter"}:
        return f"time regime failed: {group}; PF {pf:.4f}, avg R {avg_r:.4f}, closed {closed}"
    if dimension == "by_server_hour":
        return f"hour-of-day regime failed: {group}; PF {pf:.4f}, avg R {avg_r:.4f}, closed {closed}"
    if dimension == "by_entry_server_hour":
        return f"entry-hour regime failed: {group}; PF {pf:.4f}, avg R {avg_r:.4f}, closed {closed}"
    if dimension == "by_weekday":
        return f"weekday regime failed: {group}; PF {pf:.4f}, avg R {avg_r:.4f}, closed {closed}"
    return f"time segment failed: {group}; PF {pf:.4f}, avg R {avg_r:.4f}, closed {closed}"


def segment_diagnosis(row: dict[str, Any]) -> str:
    tp_rate = float(row.get("tp_rate") or 0.0)
    sl_rate = float(row.get("sl_rate") or 0.0)
    early_loss_rate = float(row.get("early_loss_rate") or 0.0)
    avg_sl = float(row.get("avg_stop_points") or 0.0)
    avg_tp = float(row.get("avg_take_profit_points") or 0.0)
    if tp_rate < 0.08 and sl_rate + early_loss_rate >= 0.80:
        return f"TP capture too low; losses dominate; avg SL {avg_sl:.1f}pt avg TP {avg_tp:.1f}pt"
    if early_loss_rate >= 0.45 and early_loss_rate > sl_rate:
        return f"early losses dominate; avg SL {avg_sl:.1f}pt avg TP {avg_tp:.1f}pt"
    if sl_rate >= 0.35:
        return f"planned SL hit too often; avg SL {avg_sl:.1f}pt avg TP {avg_tp:.1f}pt"
    if avg_sl > 0 and avg_tp / avg_sl >= 4.5 and tp_rate < 0.12:
        return f"TP likely too far; avg SL {avg_sl:.1f}pt avg TP {avg_tp:.1f}pt"
    return f"negative edge; avg SL {avg_sl:.1f}pt avg TP {avg_tp:.1f}pt"


def write_json(path: str | Path, summary: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"ok": True, "summary": summary}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_markdown(path: str | Path, summary: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(format_markdown(summary), encoding="utf-8")


def format_markdown(summary: dict[str, Any]) -> str:
    overall = summary["overall"]
    events = summary.get("event_counts", {})
    parameters = summary.get("parameters") if isinstance(summary.get("parameters"), dict) else {}
    lines = [
        "# MT5 Tester Optimization Report",
        "",
        f"- Generated at: {summary.get('generated_at')}",
        f"- Files: {len(summary.get('files', []))}",
        f"- Since minutes: {parameters.get('since_minutes', '')}",
        f"- Modified after: {parameters.get('modified_after', '')}",
        f"- Source rows: {summary.get('source_rows')}",
        f"- Open/Close/Reject: {events.get('open', 0)} / {events.get('close', 0)} / {events.get('reject', 0)}",
        f"- Closed: {overall.get('closed')}",
        f"- Win rate: {overall.get('win_rate')}",
        f"- PF: {overall.get('pf')}",
        f"- Net profit: {overall.get('net_profit')}",
        f"- Avg price R: {overall.get('avg_price_r')}",
        f"- Max drawdown price R: {overall.get('max_drawdown_price_r')}",
        f"- Expectancy price R: {overall.get('expectancy_price_r')}",
        *pass_budget_markdown_lines(summary),
        *source_time_markdown_lines(summary),
        "",
        "## By Risk Reward",
        "",
        table(summary.get("by_risk_reward", [])),
        "",
        "## By Action And Risk Reward",
        "",
        table(summary.get("by_action_risk_reward", [])),
        "",
        "## By SL Points",
        "",
        table(summary.get("by_stop_points", [])),
        "",
        "## By TP Points",
        "",
        table(summary.get("by_take_profit_points", [])),
        "",
        "## By Risk Reward And SL Points",
        "",
        table(summary.get("by_risk_reward_stop_points", [])),
        "",
        "## By Risk Reward And TP Points",
        "",
        table(summary.get("by_risk_reward_take_profit_points", [])),
        "",
        "## Best Segments",
        "",
        table(summary.get("best_segments", []), include_diagnosis=False),
        "",
        "## Weak SL/TP Segments",
        "",
        table(summary.get("weak_segments", []), include_diagnosis=True),
        "",
        "## Score Thresholds",
        "",
        score_threshold_markdown(summary.get("score_thresholds", [])),
        "",
        "## Side Score Diagnostics",
        "",
        side_score_diagnostics_markdown(summary.get("side_score_diagnostics", [])),
        "",
        "## Temporal Diagnostics",
        "",
        "### By Quarter",
        "",
        table(summary.get("by_quarter", [])),
        "",
        "### By Month",
        "",
        table(summary.get("by_month", [])),
        "",
        "### By Weekday",
        "",
        table(summary.get("by_weekday", [])),
        "",
        "### By Server Hour",
        "",
        "Close/deal time based hour buckets.",
        "",
        table(summary.get("by_server_hour", [])),
        "",
        "### By Entry Server Hour",
        "",
        "Entry/open time based hour buckets. Older CSV rows without `opened_at` or `entry_server_hour` appear as `unknown`.",
        "",
        table(summary.get("by_entry_server_hour", [])),
        "",
        "### By Action, RR And Month",
        "",
        table(summary.get("by_action_risk_reward_month", [])),
        "",
        "## Chronological Split Diagnostics",
        "",
        "Close rows sorted by `server_time`; half and quarter buckets are a coarse train/test stability check.",
        "",
        chronological_table(summary.get("chronological_splits", [])),
        "",
        "## Best Time Segments",
        "",
        table(summary.get("best_time_segments", []), include_diagnosis=False),
        "",
        "## Weak Time Segments",
        "",
        table(summary.get("weak_time_segments", []), include_diagnosis=True),
        "",
        "## Trend Regime Diagnostics",
        "",
        "### By M30 Trend",
        "",
        table(summary.get("by_m30_trend", [])),
        "",
        "### By M15 Trend",
        "",
        table(summary.get("by_m15_trend", [])),
        "",
        "### By M5 Trend",
        "",
        table(summary.get("by_m5_trend", [])),
        "",
        "### By M30 Slope",
        "",
        table(summary.get("by_m30_slope", [])),
        "",
        "### By M15 Slope",
        "",
        table(summary.get("by_m15_slope", [])),
        "",
        "### By M30/M15 Trend",
        "",
        table(summary.get("by_m30_m15_trend", [])),
        "",
        "### By Trend Alignment",
        "",
        table(summary.get("by_trend_alignment", [])),
        "",
        "### By Action And Trend Alignment",
        "",
        table(summary.get("by_action_trend_alignment", [])),
        "",
        "## Best Trend Segments",
        "",
        table(summary.get("best_trend_segments", []), include_diagnosis=False),
        "",
        "## Weak Trend Segments",
        "",
        table(summary.get("weak_trend_segments", []), include_diagnosis=True),
        "",
        "## Tester Optimization XML",
        "",
        tester_xml_markdown(summary.get("tester_xml")),
        "",
        "## Source Files",
        "",
        "| agent | rows | closed | first_server_time | last_server_time | mtime | size |",
        "|---|---:|---:|---|---|---|---:|",
    ]
    for item in summary.get("files", []):
        source_time = item.get("source_time") if isinstance(item.get("source_time"), dict) else {}
        lines.append(
            f"| {item.get('agent')} | {item.get('rows')} | {item.get('closed')} | "
            f"{source_time.get('first_server_time', '')} | {source_time.get('last_server_time', '')} | "
            f"{item.get('mtime')} | {item.get('size')} |"
        )
    return "\n".join(lines) + "\n"


def pass_budget_markdown_lines(summary: dict[str, Any]) -> list[str]:
    budget = summary.get("optimization_pass_budget")
    if not isinstance(budget, dict):
        return []
    tester_xml = summary.get("tester_xml") if isinstance(summary.get("tester_xml"), dict) else {}
    back = tester_xml.get("back") if isinstance(tester_xml.get("back"), dict) else {}
    forward = tester_xml.get("forward") if isinstance(tester_xml.get("forward"), dict) else {}
    lines = [f"- Set file: {budget.get('set_file')}"]
    if not budget.get("available"):
        lines.append(f"- Full-factorial pass candidates: unavailable ({budget.get('reason', 'unknown')})")
        return lines
    lines.extend(
        [
            f"- Optimized inputs: {budget.get('optimized_input_count')}",
            f"- Full-factorial pass candidates: {budget.get('estimated_full_factorial_passes')}",
        ]
    )
    executed_rows = budget.get("executed_tester_xml_rows")
    if isinstance(executed_rows, dict):
        lines.append(
            f"- Executed Tester XML rows: back {executed_rows.get('back', '')} / "
            f"forward {executed_rows.get('forward', '')}"
        )
    elif back or forward:
        lines.append(f"- Executed Tester XML rows: back {back.get('rows', '')} / forward {forward.get('rows', '')}")
    lines.append(f"- Pass note: {budget.get('note')}")
    return lines


def source_time_markdown_lines(summary: dict[str, Any]) -> list[str]:
    coverage = summary.get("source_time_coverage") if isinstance(summary.get("source_time_coverage"), dict) else {}
    diagnostics = (
        summary.get("source_time_diagnostics")
        if isinstance(summary.get("source_time_diagnostics"), dict)
        else {}
    )
    if not coverage and not diagnostics:
        return []
    lines = [
        f"- Source time first/last: {coverage.get('first_server_time', '')} / {coverage.get('last_server_time', '')}",
        (
            f"- Source time rows: with server_time {coverage.get('close_rows_with_server_time', '')} / "
            f"without {coverage.get('close_rows_without_server_time', '')}"
        ),
    ]
    expected_from = diagnostics.get("expected_from_date") if diagnostics else ""
    expected_to = diagnostics.get("expected_to_date") if diagnostics else ""
    if expected_from or expected_to:
        lines.append(f"- Expected Tester date range: {expected_from} / {expected_to}")
        lines.append(f"- Source time in expected range: {diagnostics.get('matches_expected_range')}")
        warnings = diagnostics.get("warnings")
        if isinstance(warnings, list) and warnings:
            lines.append(f"- Source time warnings: {'; '.join(map(str, warnings))}")
    source_filter = summary.get("source_time_file_filter")
    if isinstance(source_filter, dict) and source_filter:
        lines.append(
            "- Source time file filter: "
            f"kept {source_filter.get('kept_files')} / {source_filter.get('input_files')}, "
            f"dropped {len(source_filter.get('dropped_files') if isinstance(source_filter.get('dropped_files'), list) else [])}"
        )
        dropped = source_filter.get("dropped_files")
        if isinstance(dropped, list) and dropped:
            for item in dropped[:5]:
                if not isinstance(item, dict):
                    continue
                source_time = item.get("source_time") if isinstance(item.get("source_time"), dict) else {}
                lines.append(
                    "- Dropped source file: "
                    f"{item.get('path')} "
                    f"({source_time.get('first_server_time', '')} / {source_time.get('last_server_time', '')}) "
                    f"{item.get('reason', '')}"
                )
    return lines


def score_threshold_markdown(rows: object) -> str:
    lines: list[str] = []
    append_score_threshold_table(lines, rows)
    return "\n".join(lines)


def side_score_diagnostics_markdown(rows: object) -> str:
    lines: list[str] = []
    append_side_score_diagnostics(lines, rows)
    return "\n".join(lines)


def tester_xml_markdown(payload: Any) -> str:
    if not isinstance(payload, dict) or not payload:
        return "- None."
    lines: list[str] = []
    back = payload.get("back")
    if isinstance(back, dict):
        lines.extend(
            [
                f"- Back XML rows: {back.get('rows')}",
                "",
                "### Top Back Passes",
                "",
                tester_table(back.get("top", [])),
                "",
                "### Back Parameter Diagnostics",
                "",
                tester_parameter_diagnostics_table(back.get("parameter_diagnostics", [])),
                "",
            ]
        )
    forward = payload.get("forward")
    if isinstance(forward, dict):
        lines.extend(
            [
                f"- Forward XML rows: {forward.get('rows')}",
                f"- Positive forward / negative back: {forward.get('positive_forward_negative_back')}",
                f"- Positive forward / positive back: {forward.get('positive_forward_positive_back')}",
                "",
                "### Stable Forward Passes",
                "",
                tester_table(forward.get("stable_top", [])),
                "",
                "### Forward-Only Passes",
                "",
                tester_table(forward.get("forward_only_top", [])),
                "",
                "### Top Forward Passes",
                "",
                tester_table(forward.get("top", [])),
                "",
                "### Forward Parameter Diagnostics",
                "",
                tester_parameter_diagnostics_table(forward.get("parameter_diagnostics", [])),
            ]
        )
    return "\n".join(lines)


def tester_parameter_diagnostics_table(items: Any) -> str:
    if not isinstance(items, list) or not items:
        return "- None."
    headers = [
        "parameter",
        "value",
        "passes",
        "positive_result",
        "avg_result",
        "max_result",
        "avg_pf",
        "max_pf",
        "avg_trades",
    ]
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    for item in items:
        if not isinstance(item, dict):
            continue
        parameter = item.get("parameter", "")
        for group in item.get("groups", []):
            if not isinstance(group, dict):
                continue
            row = {"parameter": parameter, **group}
            lines.append("| " + " | ".join(str(row.get(header, "")) for header in headers) + " |")
    return "\n".join(lines) if len(lines) > 2 else "- None."


def tester_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "- None."
    headers = [
        "Pass",
        "Result",
        "Forward Result",
        "Back Result",
        "Profit",
        "Profit Factor",
        "Trades",
        "InpMinScore",
        "InpBuyRiskReward",
        "InpSellRiskReward",
        "InpStopBufferPoints",
        "InpUseFittedBuyBreakFilter",
        "InpUseBuyM30M15UpGate",
        "InpUseFittedBuyEntryFilter",
        "InpBuyRequireBreakConfirm",
        "InpBuyMinM1ClosePosition",
        "InpBuyMinM1BodyAtr",
        "InpBuyMinM5CloseSlowAtr",
        "InpUseFittedBuyTimeFilter",
        "InpBuyBlockedServerHours",
        "InpUseFittedBuyCalendarFilter",
        "InpBuyBlockedMonths",
        "InpBuyBlockedWeekdays",
        "InpUseBuyAllowedServerHours",
        "InpBuyAllowedServerHours",
        "InpUseFittedSellFilter",
        "InpUseFittedSellTrendFilter",
        "InpUseSellM30M15DownGate",
        "InpUseFittedSellTimeFilter",
        "InpUseFittedSellCalendarFilter",
        "InpUseSellAllowedServerHours",
        "InpUseFittedSellEntryFilter",
        "InpSellRequireBreakConfirm",
        "InpSellBlockedMonths",
        "InpSellBlockedWeekdays",
        "InpSellAllowedServerHours",
        "InpSellMaxM1ClosePosition",
        "InpSellMinM1BodyAtr",
        "InpSellMaxM5CloseSlowAtr",
    ]
    active_headers = [header for header in headers if any(header in row for row in rows)]
    lines = ["| " + " | ".join(active_headers) + " |", "|" + "|".join("---" for _ in active_headers) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(header, "")) for header in active_headers) + " |")
    return "\n".join(lines)


def table(rows: list[dict[str, Any]], *, include_diagnosis: bool = False) -> str:
    if not rows:
        return "- None."
    headers = [
        "group",
        "closed",
        "win_rate",
        "pf",
        "net_profit",
        "avg_price_r",
        "max_drawdown_price_r",
        "expectancy_price_r",
        "tp_rate",
        "sl_rate",
        "early_loss_rate",
        "avg_stop_points",
        "avg_take_profit_points",
    ]
    if include_diagnosis:
        headers.append("diagnosis")
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(header, "")) for header in headers) + " |")
    return "\n".join(lines)


def chronological_table(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "- None."
    headers = [
        "group",
        "start_time",
        "end_time",
        "closed",
        "win_rate",
        "pf",
        "net_profit",
        "avg_price_r",
        "max_drawdown_price_r",
        "expectancy_price_r",
        "tp_rate",
        "sl_rate",
        "early_loss_rate",
        "avg_stop_points",
        "avg_take_profit_points",
        "diagnosis",
    ]
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(header, "")) for header in headers) + " |")
    return "\n".join(lines)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize MT5 Strategy Tester optimization agent CSV files.")
    parser.add_argument("--source-root", action="append", default=None, help="Tester root, agent dir, or CSV file.")
    parser.add_argument("--filename", default=DEFAULT_FILENAME)
    parser.add_argument("--since-minutes", type=float, default=180.0)
    parser.add_argument(
        "--modified-after",
        default="",
        help="Only include CSV files modified at or after this local time (YYYY.MM.DD HH:MM) or epoch seconds.",
    )
    parser.add_argument(
        "--modified-before",
        default="",
        help="Only include CSV files modified at or before this local time (YYYY.MM.DD HH:MM) or epoch seconds.",
    )
    parser.add_argument("--min-closed", type=int, default=30)
    parser.add_argument("--weak-pf", type=float, default=1.0)
    parser.add_argument("--tester-xml", default=None)
    parser.add_argument("--tester-forward-xml", default=None)
    parser.add_argument("--set-file", default="", help="Tester .set file used by this optimization run.")
    parser.add_argument("--expected-from-date", default="", help="Expected Tester FromDate, e.g. 2025.01.01.")
    parser.add_argument("--expected-to-date", default="", help="Expected Tester ToDate, e.g. 2025.12.31.")
    parser.add_argument(
        "--fail-on-source-time-mismatch",
        action="store_true",
        help="Exit without writing output files when close server_time is outside the expected date range.",
    )
    parser.add_argument(
        "--drop-source-time-mismatch-files",
        action="store_true",
        help="Drop individual Agent CSV files whose close server_time is outside the expected date range.",
    )
    parser.add_argument("--skip-tester-xml", action="store_true")
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", default=DEFAULT_OUTPUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        modified_after_epoch = parse_modified_after(args.modified_after)
        modified_before_epoch = parse_modified_after(args.modified_before)
    except ValueError as exc:
        print(json.dumps({"ok": False, "reason": str(exc)}, ensure_ascii=False, indent=2))
        return 2
    paths = discover_tester_csvs(
        args.source_root,
        filename=args.filename,
        since_minutes=args.since_minutes,
        modified_after_epoch=modified_after_epoch,
        modified_before_epoch=modified_before_epoch,
    )
    if not paths:
        payload = {
            "ok": False,
            "generated_at": datetime.now().strftime(TIME_FORMAT),
            "reason": f"no {args.filename} found",
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 1
    source_time_file_filter: dict[str, Any] | None = None
    if args.drop_source_time_mismatch_files:
        paths, source_time_file_filter = filter_paths_by_expected_source_time(
            paths,
            expected_from_date=args.expected_from_date,
            expected_to_date=args.expected_to_date,
        )
        if not paths:
            payload = {
                "ok": False,
                "generated_at": datetime.now().strftime(TIME_FORMAT),
                "reason": "no CSV files remained after source-time file filter",
                "source_time_file_filter": source_time_file_filter,
            }
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return 1
    try:
        summary = summarize_optimization_csvs(
            paths,
            min_closed=args.min_closed,
            weak_pf=args.weak_pf,
            expected_from_date=args.expected_from_date,
            expected_to_date=args.expected_to_date,
        )
    except ValueError as exc:
        print(json.dumps({"ok": False, "reason": str(exc)}, ensure_ascii=False, indent=2))
        return 2
    if source_time_file_filter is not None:
        summary["source_time_file_filter"] = source_time_file_filter
    summary["parameters"]["since_minutes"] = args.since_minutes
    summary["parameters"]["modified_after"] = format_epoch(modified_after_epoch)
    summary["parameters"]["modified_before"] = format_epoch(modified_before_epoch)
    summary["parameters"]["drop_source_time_mismatch_files"] = bool(args.drop_source_time_mismatch_files)
    if args.fail_on_source_time_mismatch and source_time_mismatch(summary):
        print(
            json.dumps(
                {
                    "ok": False,
                    "reason": "source_time_mismatch",
                    "message": source_time_mismatch_reason(summary),
                    "files": len(paths),
                    "closed": summary["overall"]["closed"],
                    "source_time_diagnostics": summary.get("source_time_diagnostics"),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 3
    if not args.skip_tester_xml:
        attach_tester_xml_summary(summary, back_xml=args.tester_xml, forward_xml=args.tester_forward_xml)
    attach_set_pass_budget(summary, args.set_file)
    write_json(args.output_json, summary)
    write_markdown(args.output_md, summary)
    print(
        json.dumps(
            {
                "ok": True,
                "files": len(paths),
                "dropped_source_time_files": len(
                    source_time_file_filter.get("dropped_files")
                    if isinstance(source_time_file_filter, dict)
                    and isinstance(source_time_file_filter.get("dropped_files"), list)
                    else []
                ),
                "output_json": args.output_json,
                "output_md": args.output_md,
                "closed": summary["overall"]["closed"],
                "pf": summary["overall"]["pf"],
                "net_profit": summary["overall"]["net_profit"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
