from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path

if Path(sys.path[0] if sys.path else "").resolve() == Path(__file__).resolve().parent:
    sys.path.pop(0)

import subprocess
from datetime import datetime
from typing import Any

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analysis.market_data import TIME_FORMAT
from analysis.mt5_agent_csv_utils import combined_source_time_coverage, summarize_csv_source_time
from analysis.mt5_compile import default_wine_path, default_wineprefix, mt5_root_to_drive_c, windows_path
from analysis.mt5_compile_status import compile_status, default_mt5_root
from analysis.mt5_optimization_recommend import (
    DEFAULT_OUTPUT_JSON as DEFAULT_RECOMMENDATION_JSON,
    DEFAULT_OUTPUT_MD as DEFAULT_RECOMMENDATION_MD,
    DEFAULT_OUTPUT_SET,
    DEFAULT_TEMPLATE_SET,
    recommend_from_summary,
    write_json as write_recommendation_json,
    write_markdown as write_recommendation_markdown,
    write_next_set,
)
from analysis.mt5_tester_optimization_report import (
    DEFAULT_OUTPUT_JSON as DEFAULT_OPTIMIZATION_JSON,
    DEFAULT_OUTPUT_MD as DEFAULT_OPTIMIZATION_MD,
    attach_set_pass_budget,
    attach_tester_xml_summary,
    default_tester_root,
    discover_tester_csvs,
    format_epoch,
    pass_budget_markdown_lines,
    parse_modified_after,
    source_time_mismatch,
    source_time_mismatch_reason,
    summarize_optimization_csvs,
    write_json as write_optimization_json,
    write_markdown as write_optimization_markdown,
)


DEFAULT_CONFIG = "mt5/TesterConfigs/Swing_Evaluation_Trader_next_optimization.ini"
DEFAULT_OUTPUT_JSON = "runtime/latest_mt5_tester_run.json"
DEFAULT_OUTPUT_MD = "runtime/latest_mt5_tester_run.md"
EXPECTED_CONSECUTIVE_LOSS_LIMIT = 20
EXPECTED_CONSECUTIVE_LOSS_COOLDOWN_MINUTES = 120
RISK_PRESET_REQUIRED_INPUTS = (
    "InpUseDailyLossStop",
    "InpDailyLossLimit",
    "InpUseConsecutiveLossStop",
    "InpConsecutiveLossLimit",
    "InpConsecutiveLossCooldownMinutes",
    "InpRequireStrategyTester",
    "InpChartButtonDryRunOnly",
    "InpAllowChartButtonTrading",
)


def drive_c_config_dir(mt5_root: str | Path) -> Path:
    return mt5_root_to_drive_c(Path(mt5_root).expanduser()) / "mt5cfg"


def section_name(line: str) -> str | None:
    stripped = line.strip()
    if stripped.startswith("[") and stripped.endswith("]"):
        return stripped[1:-1]
    return None


def set_ini_value(text: str, section: str, key: str, value: str) -> str:
    lines = text.splitlines()
    current = ""
    replaced = False
    section_seen = False
    insert_at: int | None = None
    rendered: list[str] = []
    for index, line in enumerate(lines):
        found_section = section_name(line)
        if found_section is not None:
            if current == section and not replaced and insert_at is None:
                insert_at = len(rendered)
            current = found_section
            if current == section:
                section_seen = True
        if current == section and line.strip().lower().startswith(f"{key.lower()}="):
            rendered.append(f"{key}={value}")
            replaced = True
        else:
            rendered.append(line)
        if index == len(lines) - 1 and current == section and not replaced and insert_at is None:
            insert_at = len(rendered)
    if replaced:
        return "\n".join(rendered).rstrip() + "\n"
    if section_seen and insert_at is not None:
        rendered.insert(insert_at, f"{key}={value}")
    else:
        if rendered and rendered[-1].strip():
            rendered.append("")
        rendered.extend([f"[{section}]", f"{key}={value}"])
    return "\n".join(rendered).rstrip() + "\n"


def get_ini_value(text: str, section: str, key: str) -> str:
    current = ""
    for line in text.splitlines():
        found_section = section_name(line)
        if found_section is not None:
            current = found_section
            continue
        if current == section and line.strip().lower().startswith(f"{key.lower()}="):
            return line.split("=", 1)[1].strip()
    return ""


def tester_config_metadata(text: str) -> dict[str, str]:
    return {
        "expert": get_ini_value(text, "Tester", "Expert"),
        "expert_parameters": get_ini_value(text, "Tester", "ExpertParameters"),
        "symbol": get_ini_value(text, "Tester", "Symbol"),
        "period": get_ini_value(text, "Tester", "Period"),
        "model": get_ini_value(text, "Tester", "Model"),
        "execution_mode": get_ini_value(text, "Tester", "ExecutionMode"),
        "optimization": get_ini_value(text, "Tester", "Optimization"),
        "optimization_criterion": get_ini_value(text, "Tester", "OptimizationCriterion"),
        "forward_mode": get_ini_value(text, "Tester", "ForwardMode"),
        "forward_date": get_ini_value(text, "Tester", "ForwardDate"),
        "from_date": get_ini_value(text, "Tester", "FromDate"),
        "to_date": get_ini_value(text, "Tester", "ToDate"),
        "report": get_ini_value(text, "Tester", "Report"),
        "shutdown_terminal": get_ini_value(text, "Tester", "ShutdownTerminal"),
    }


def tester_report_expectation(optimization: object, forward_mode: object) -> dict[str, str]:
    optimization_text = str(optimization or "").strip().lower()
    forward_text = str(forward_mode or "").strip().lower()
    optimization_enabled = optimization_text not in {"", "0", "false", "no"}
    forward_enabled = forward_text not in {"", "0", "false", "no"}
    if optimization_enabled and forward_enabled:
        return {
            "run_type": "optimization_forward",
            "expected_report_artifact": "XML + forward XML + Agent CSV",
            "report_expectation_note": "Optimization is enabled; collect expects the named Tester XML and forward XML pair.",
        }
    if optimization_enabled:
        return {
            "run_type": "optimization",
            "expected_report_artifact": "XML + Agent CSV",
            "report_expectation_note": "Optimization is enabled; collect expects the named Tester XML report.",
        }
    if forward_enabled:
        return {
            "run_type": "single_strategy_test_forward_profile",
            "expected_report_artifact": "HTML report + Agent CSV",
            "report_expectation_note": (
                "Optimization is disabled; collect accepts the named HTML report and Agent CSV, "
                "not an optimization forward XML pair."
            ),
        }
    return {
        "run_type": "single_strategy_test",
        "expected_report_artifact": "HTML report + Agent CSV",
        "report_expectation_note": (
            "Optimization is disabled; collect accepts the named HTML report and Agent CSV."
        ),
    }


def prepare_tester_config(
    config_text: str,
    *,
    report_name: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    forward_mode: str | None = None,
    shutdown_terminal: bool = True,
) -> tuple[str, dict[str, str]]:
    text = config_text
    if report_name:
        text = set_ini_value(text, "Tester", "Report", report_name)
    if from_date:
        text = set_ini_value(text, "Tester", "FromDate", from_date)
    if to_date:
        text = set_ini_value(text, "Tester", "ToDate", to_date)
    if forward_mode:
        text = set_ini_value(text, "Tester", "ForwardMode", forward_mode)
    text = set_ini_value(text, "Tester", "ReplaceReport", "1")
    text = set_ini_value(text, "Tester", "ShutdownTerminal", "1" if shutdown_terminal else "0")
    return text, tester_config_metadata(text)


def resolve_expert_parameters_set(
    *,
    workspace_root: str | Path,
    config_path: str | Path,
    expert_parameters: str,
) -> Path | None:
    text = str(expert_parameters or "").strip()
    if not text:
        return None
    workspace = Path(workspace_root)
    config = Path(config_path)
    raw = Path(text).expanduser()
    if raw.is_absolute():
        return raw
    candidates = [
        workspace / "mt5" / "TesterSets" / text,
        config.parent / text,
        workspace / text,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def tester_profiles_dir(mt5_root: str | Path) -> Path:
    return Path(mt5_root).expanduser() / "MQL5" / "Profiles" / "Tester"


def sync_expert_parameters_set_to_profile(
    *,
    set_file: str | Path | None,
    expert_parameters: str,
    mt5_root: str | Path,
    dry_run: bool = False,
) -> dict[str, Any]:
    source = Path(set_file).expanduser() if set_file else None
    target_name = Path(str(expert_parameters or "").strip()).name
    target = tester_profiles_dir(mt5_root) / target_name if target_name else None
    result: dict[str, Any] = {
        "requested": True,
        "ok": False,
        "source": str(source) if source else "",
        "target": str(target) if target else "",
        "dry_run": dry_run,
        "copied": False,
        "already_in_place": False,
        "errors": [],
    }
    errors = result["errors"]
    if not source:
        errors.append("ExpertParameters .set source is not resolved")
        return result
    if not source.exists():
        errors.append(f"ExpertParameters .set source not found: {source}")
        return result
    if target is None:
        errors.append("ExpertParameters target name is empty")
        return result
    try:
        if source.resolve() == target.resolve():
            result["ok"] = True
            result["already_in_place"] = True
            return result
    except OSError:
        pass
    if dry_run:
        result["ok"] = True
        return result
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    except OSError as exc:
        errors.append(str(exc))
        return result
    result["ok"] = True
    result["copied"] = True
    return result


def target_tester_set_sync_summary(
    compile_summary: dict[str, Any],
    *,
    set_file: str | Path | None,
    set_sync: dict[str, Any],
    expert_parameters: str = "",
    mt5_root: str | Path | None = None,
) -> dict[str, Any]:
    source = Path(set_file).expanduser() if set_file else None
    name = source.name if source else ""
    rows = compile_summary.get("tester_sets") if isinstance(compile_summary.get("tester_sets"), list) else []
    row = next((item for item in rows if isinstance(item, dict) and item.get("name") == name), {})
    workspace_set = row.get("workspace_set") if isinstance(row.get("workspace_set"), dict) else {}
    mt5_set = row.get("mt5_set") if isinstance(row.get("mt5_set"), dict) else {}

    if set_sync.get("requested") is True and set_sync.get("ok") is True and name:
        return {
            "name": name,
            "synced": True,
            "status": "synced_by_runner",
            "source": str(source) if source else "",
            "target": str(set_sync.get("target") or mt5_set.get("path") or ""),
            "compile_status_reported": bool(row),
            "set_sync_requested": True,
            "set_sync_ok": True,
        }

    if row:
        return {
            "name": name,
            "synced": row.get("synced"),
            "status": row.get("status", ""),
            "source": str(workspace_set.get("path") or source or ""),
            "target": str(mt5_set.get("path") or ""),
            "compile_status_reported": True,
            "set_sync_requested": bool(set_sync.get("requested")),
            "set_sync_ok": set_sync.get("ok"),
        }

    if mt5_root is not None and name:
        target_name = Path(str(expert_parameters or "").strip()).name or name
        target = tester_profiles_dir(mt5_root) / target_name
        base = {
            "name": name,
            "source": str(source) if source else "",
            "target": str(target),
            "compile_status_reported": False,
            "set_sync_requested": bool(set_sync.get("requested")),
            "set_sync_ok": set_sync.get("ok"),
        }
        if source is None or not source.exists():
            return {
                **base,
                "synced": False,
                "status": "missing_workspace_set",
            }
        if not target.exists():
            return {
                **base,
                "synced": False,
                "status": "missing_mt5_set",
            }
        try:
            synced = source.read_bytes() == target.read_bytes()
        except OSError as exc:
            return {
                **base,
                "synced": False,
                "status": "comparison_failed",
                "error": str(exc),
            }
        return {
            **base,
            "synced": synced,
            "status": "direct_synced" if synced else "set_not_synced",
        }

    return {
        "name": name,
        "synced": None,
        "status": "not_reported" if name else "missing_expert_parameters_set",
        "source": str(source) if source else "",
        "target": str(set_sync.get("target") or ""),
        "compile_status_reported": False,
        "set_sync_requested": bool(set_sync.get("requested")),
        "set_sync_ok": set_sync.get("ok"),
    }


def parse_set_current_inputs(set_text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in set_text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith(";") or "=" not in stripped:
            continue
        name, value = stripped.split("=", 1)
        name = name.strip()
        if not name.startswith("Inp"):
            continue
        values[name] = value.split("||", 1)[0].strip()
    return values


def parse_set_bool(value: object) -> bool | None:
    text = str(value or "").strip().lower()
    if text == "true":
        return True
    if text == "false":
        return False
    return None


def parse_set_float(value: object) -> float | None:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return None


def validate_tester_risk_preset(
    set_file: str | Path | None,
    *,
    expert_parameters: str = "",
    expected_consecutive_loss_limit: int = EXPECTED_CONSECUTIVE_LOSS_LIMIT,
    expected_consecutive_loss_cooldown_minutes: int = EXPECTED_CONSECUTIVE_LOSS_COOLDOWN_MINUTES,
) -> dict[str, Any]:
    path = Path(set_file).expanduser() if set_file else None
    identity = f"{expert_parameters} {path.name if path else ''}".lower()
    sample_collection = "sample_collection" in identity
    preset: dict[str, Any] = {
        "ok": False,
        "set_file": str(path) if path else "",
        "expert_parameters": expert_parameters,
        "mode": "sample_collection" if sample_collection else "forward_or_optimization",
        "expected_consecutive_loss_limit": expected_consecutive_loss_limit,
        "expected_consecutive_loss_cooldown_minutes": expected_consecutive_loss_cooldown_minutes,
        "inputs": {},
        "errors": [],
    }
    errors: list[str] = []
    if path is None:
        errors.append("ExpertParameters .set file is not resolved")
        preset["errors"] = errors
        return preset
    if not path.exists():
        errors.append(f"Tester .set file not found: {path}")
        preset["errors"] = errors
        return preset

    inputs = parse_set_current_inputs(path.read_text(encoding="utf-8"))
    observed = {
        "InpUseDailyLossStop": inputs.get("InpUseDailyLossStop", ""),
        "InpDailyLossLimit": inputs.get("InpDailyLossLimit", ""),
        "InpUseConsecutiveLossStop": inputs.get("InpUseConsecutiveLossStop", ""),
        "InpConsecutiveLossLimit": inputs.get("InpConsecutiveLossLimit", ""),
        "InpConsecutiveLossCooldownMinutes": inputs.get("InpConsecutiveLossCooldownMinutes", ""),
        "InpRequireStrategyTester": inputs.get("InpRequireStrategyTester", ""),
        "InpChartButtonDryRunOnly": inputs.get("InpChartButtonDryRunOnly", ""),
        "InpAllowChartButtonTrading": inputs.get("InpAllowChartButtonTrading", ""),
    }
    preset["inputs"] = observed

    use_daily = parse_set_bool(observed["InpUseDailyLossStop"])
    use_consecutive = parse_set_bool(observed["InpUseConsecutiveLossStop"])
    require_strategy_tester = parse_set_bool(observed["InpRequireStrategyTester"])
    chart_button_dry_run = parse_set_bool(observed["InpChartButtonDryRunOnly"])
    allow_chart_button_trading = parse_set_bool(observed["InpAllowChartButtonTrading"])
    daily_limit = parse_set_float(observed["InpDailyLossLimit"])
    consecutive_limit = parse_set_float(observed["InpConsecutiveLossLimit"])
    cooldown_minutes = parse_set_float(observed["InpConsecutiveLossCooldownMinutes"])

    if require_strategy_tester is not True:
        errors.append("InpRequireStrategyTester must be true for Tester preset safety")
    if chart_button_dry_run is not True:
        errors.append("InpChartButtonDryRunOnly must be true for Tester preset safety")
    if allow_chart_button_trading is not False:
        errors.append("InpAllowChartButtonTrading must be false for Tester preset safety")

    if sample_collection:
        if use_daily is not False:
            errors.append("InpUseDailyLossStop must be false for sample_collection runs")
        if use_consecutive is not False:
            errors.append("InpUseConsecutiveLossStop must be false for sample_collection runs")
    else:
        if use_daily is not True:
            errors.append("InpUseDailyLossStop must be true for forward/optimization runs")
        if daily_limit is None or daily_limit <= 0:
            errors.append("InpDailyLossLimit must be a positive number for forward/optimization runs")
        if use_consecutive is not True:
            errors.append("InpUseConsecutiveLossStop must be true for forward/optimization runs")
        if consecutive_limit is None or consecutive_limit < expected_consecutive_loss_limit:
            errors.append(
                "InpConsecutiveLossLimit "
                f"{observed['InpConsecutiveLossLimit'] or 'missing'} < expected {expected_consecutive_loss_limit}"
            )
        if cooldown_minutes is None or cooldown_minutes < expected_consecutive_loss_cooldown_minutes:
            errors.append(
                "InpConsecutiveLossCooldownMinutes "
                f"{observed['InpConsecutiveLossCooldownMinutes'] or 'missing'} < expected "
                f"{expected_consecutive_loss_cooldown_minutes}"
            )

    preset["errors"] = errors
    preset["ok"] = not errors
    return preset


def tester_report_base_path(mt5_root: str | Path, report_name: str) -> Path:
    tester_root = Path(mt5_root).expanduser() / "Tester"
    normalized = report_name.replace("/", "\\")
    if normalized.lower().startswith("tester\\"):
        normalized = normalized.split("\\", 1)[1]
    if normalized.lower().endswith(".xml"):
        base = normalized[:-4]
    elif normalized.lower().endswith(".htm"):
        base = normalized[:-4]
    elif normalized.lower().endswith(".html"):
        base = normalized[:-5]
    else:
        base = normalized
    return tester_root / base


def tester_report_paths(mt5_root: str | Path, report_name: str) -> tuple[Path, Path]:
    base = tester_report_base_path(mt5_root, report_name)
    return base.with_name(f"{base.name}.xml"), base.with_name(f"{base.name}.forward.xml")


def tester_html_report_paths(mt5_root: str | Path, report_name: str) -> list[Path]:
    base = tester_report_base_path(mt5_root, report_name)
    return [base.with_name(f"{base.name}.htm"), base.with_name(f"{base.name}.html")]


def first_existing_tester_html_report(mt5_root: str | Path, report_name: str) -> Path | None:
    for path in tester_html_report_paths(mt5_root, report_name):
        if path.exists():
            return path
    return None


def parse_mt5_report_number(value: str) -> float | int | None:
    text = str(value or "").strip()
    if not text:
        return None
    text = text.replace("\xa0", " ").replace("−", "-")
    text = re.sub(r"(?<=\d)\s+(?=\d)", "", text)
    text = text.replace(",", "")
    match = re.search(r"[-+]?\d+(?:\.\d+)?", text)
    if not match:
        return None
    number = float(match.group(0))
    return int(number) if number.is_integer() else number


def read_tester_html_text(path: str | Path) -> str:
    source = Path(path)
    raw = source.read_bytes()
    for encoding in ("utf-16", "utf-8-sig", "cp1252"):
        try:
            decoded = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        decoded = raw.decode("utf-8", errors="ignore")
    text = re.sub(r"<[^>]+>", " ", decoded)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def report_value_after_label(text: str, label: str) -> str:
    pattern = re.compile(
        re.escape(label) + r"(?:\s*\([^)]*\))?\s*:?\s*([-+]?\d[\d\s,]*(?:\.\d+)?)",
        re.IGNORECASE,
    )
    match = pattern.search(text)
    return match.group(1).strip() if match else ""


def parse_tester_html_report(path: str | Path) -> dict[str, Any]:
    source = Path(path)
    if not source.exists():
        return {"exists": False, "path": str(source), "ok": False, "status": "missing"}
    text = read_tester_html_text(source)
    fields = {
        "net_profit": ("Total Net Profit", "Total Net Profit"),
        "gross_profit": ("Gross Profit", "Gross Profit"),
        "gross_loss": ("Gross Loss", "Gross Loss"),
        "pf": ("Profit Factor", "Profit Factor"),
        "expected_payoff": ("Expected Payoff", "Expected Payoff"),
        "closed": ("Total Trades", "Total Trades"),
        "short_trades": ("Short Trades", "Short Trades"),
        "long_trades": ("Long Trades", "Long Trades"),
        "total_deals": ("Total Deals", "Total Deals"),
        "wins": ("Profit Trades", "Profit Trades"),
        "losses": ("Loss Trades", "Loss Trades"),
        "largest_profit_trade": ("Largest profit trade", "Largest profit trade"),
        "largest_loss_trade": ("Largest loss trade", "Largest loss trade"),
        "average_profit_trade": ("Average profit trade", "Average profit trade"),
        "average_loss_trade": ("Average loss trade", "Average loss trade"),
        "max_consecutive_loss_amount": (
            "Maximal consecutive loss",
            "Maximal consecutive loss amount",
        ),
    }
    metrics: dict[str, Any] = {
        "exists": True,
        "ok": True,
        "status": "parsed",
        "path": str(source),
        "mtime": datetime.fromtimestamp(source.stat().st_mtime).strftime(TIME_FORMAT),
    }
    for key, (label, _description) in fields.items():
        metrics[key] = parse_mt5_report_number(report_value_after_label(text, label))
    max_loss_match = re.search(
        r"Maximal consecutive loss\s*\(count\)\s*:?\s*[-+]?\d[\d\s,]*(?:\.\d+)?\s*\((\d+)\)",
        text,
        re.IGNORECASE,
    )
    if max_loss_match:
        metrics["max_consecutive_loss_count"] = int(max_loss_match.group(1))
    return metrics


EXPERT_STATS_PATTERN = re.compile(
    r"(?P<server_time>\d{4}\.\d{2}\.\d{2}\s+\d{2}:\d{2}:\d{2})\s+"
    r"Swing Evaluation Trader stats\s+closed=(?P<closed>\d+)\s+"
    r"wins=(?P<wins>\d+)\s+losses=(?P<losses>\d+)\s+"
    r"pf=(?P<pf>[-+]?\d+(?:\.\d+)?)\s+"
    r"net=(?P<net_profit>[-+]?\d+(?:\.\d+)?)\s+"
    r"max_losing_streak=(?P<max_losing_streak>\d+)"
)


def tester_log_line_epoch(path: Path, line: str) -> float | None:
    date_match = re.search(r"(\d{8})", path.name)
    time_match = re.search(r"\b(\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,6}))?\b", line)
    if not date_match or not time_match:
        return None
    date_text = date_match.group(1)
    micros = (time_match.group(4) or "0").ljust(6, "0")[:6]
    moment = datetime(
        int(date_text[0:4]),
        int(date_text[4:6]),
        int(date_text[6:8]),
        int(time_match.group(1)),
        int(time_match.group(2)),
        int(time_match.group(3)),
        int(micros),
    )
    return moment.timestamp()


def parse_expert_stats_line(path: Path, line: str) -> dict[str, Any] | None:
    match = EXPERT_STATS_PATTERN.search(line)
    if not match:
        return None
    logged_epoch = tester_log_line_epoch(path, line)
    return {
        "path": str(path),
        "log_time": datetime.fromtimestamp(logged_epoch).strftime(TIME_FORMAT) if logged_epoch else "",
        "log_epoch": round(logged_epoch, 3) if logged_epoch else None,
        "server_time": match.group("server_time"),
        "closed": int(match.group("closed")),
        "wins": int(match.group("wins")),
        "losses": int(match.group("losses")),
        "pf": float(match.group("pf")),
        "net_profit": float(match.group("net_profit")),
        "max_losing_streak": int(match.group("max_losing_streak")),
    }


def read_tester_log_text(path: Path) -> str:
    raw = path.read_bytes()
    for encoding in ("utf-16", "utf-8-sig", "cp1252"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="ignore")


def latest_single_test_expert_log_stats(
    *,
    mt5_root: str | Path,
    modified_after_epoch: float | None = None,
    report_epoch: float | None = None,
    report_grace_seconds: float = 10.0,
) -> dict[str, Any]:
    mt5 = Path(mt5_root).expanduser()
    tester_root = mt5 / "Tester"
    log_roots = [tester_root / "logs", *tester_root.glob("Agent-*/logs")]
    candidates: list[dict[str, Any]] = []
    upper_epoch = report_epoch + report_grace_seconds if report_epoch is not None else None
    for root in log_roots:
        if not root.exists():
            continue
        for path in root.glob("*.log"):
            try:
                if modified_after_epoch is not None and path.stat().st_mtime < modified_after_epoch - 60:
                    continue
                lines = read_tester_log_text(path).splitlines()
            except OSError:
                continue
            for line in lines:
                stats = parse_expert_stats_line(path, line)
                if not stats:
                    continue
                log_epoch = stats.get("log_epoch")
                if log_epoch is not None:
                    if modified_after_epoch is not None and float(log_epoch) < modified_after_epoch:
                        continue
                    if upper_epoch is not None and float(log_epoch) > upper_epoch:
                        continue
                candidates.append(stats)
    if not candidates:
        return {"available": False, "status": "missing"}
    latest = max(candidates, key=lambda item: float(item.get("log_epoch") or 0.0))
    return {"available": True, "status": "parsed", **latest}


def matching_xml_pairs(search_roots: list[str | Path]) -> list[tuple[Path, Path]]:
    pairs: list[tuple[Path, Path]] = []
    for raw_root in search_roots:
        root = Path(raw_root).expanduser()
        if not root.exists() or not root.is_dir():
            continue
        for forward in root.glob("Swing_Evaluation_Trader*.forward.xml"):
            back = forward.with_name(forward.name[: -len(".forward.xml")] + ".xml")
            if back.exists():
                pairs.append((back, forward))
    return sorted(
        pairs,
        key=lambda pair: (max(pair[0].stat().st_mtime, pair[1].stat().st_mtime), str(pair[0])),
        reverse=True,
    )


def resolve_tester_xml_paths(
    *,
    mt5_root: str | Path,
    report_name: str,
    workspace_root: str | Path | None = None,
) -> tuple[Path, Path, dict[str, Any]]:
    requested_back, requested_forward = tester_report_paths(mt5_root, report_name)
    if requested_back.exists() and requested_forward.exists():
        return requested_back, requested_forward, {
            "source": "requested_report",
            "requested_back_xml": str(requested_back),
            "requested_forward_xml": str(requested_forward),
            "used_back_xml": str(requested_back),
            "used_forward_xml": str(requested_forward),
        }

    search_roots = [Path(mt5_root).expanduser() / "Tester"]
    if workspace_root is not None:
        search_roots.append(Path(workspace_root).resolve() / "runtime" / "mt5_optimization")
    pairs = matching_xml_pairs(search_roots)
    if pairs:
        back, forward = pairs[0]
        return back, forward, {
            "source": "latest_pair_fallback",
            "requested_back_xml": str(requested_back),
            "requested_forward_xml": str(requested_forward),
            "used_back_xml": str(back),
            "used_forward_xml": str(forward),
        }

    return requested_back, requested_forward, {
        "source": "requested_missing",
        "requested_back_xml": str(requested_back),
        "requested_forward_xml": str(requested_forward),
        "used_back_xml": str(requested_back),
        "used_forward_xml": str(requested_forward),
    }


def build_terminal_command(
    *,
    wine_path: str | Path,
    mt5_root: str | Path,
    config_path: str | Path,
) -> list[str]:
    mt5 = Path(mt5_root).expanduser()
    drive_c = mt5_root_to_drive_c(mt5)
    terminal = windows_path(mt5 / "terminal64.exe", drive_c_root=drive_c)
    config = windows_path(config_path, drive_c_root=drive_c)
    return [str(Path(wine_path).expanduser()), terminal, f"/config:{config}"]


def discover_running_terminal_processes() -> list[dict[str, object]]:
    try:
        process = subprocess.run(
            ["ps", "-ax", "-o", "pid=,command="],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return []
    if process.returncode != 0:
        return []
    rows: list[dict[str, object]] = []
    for line in process.stdout.splitlines():
        stripped = line.strip()
        if not stripped or "terminal64.exe" not in stripped.lower():
            continue
        pid_text, _, command = stripped.partition(" ")
        try:
            pid: int | str = int(pid_text)
        except ValueError:
            pid = pid_text
        rows.append({"pid": pid, "command": command.strip()})
    return rows


def local_time_text(epoch_seconds: float) -> str:
    return datetime.fromtimestamp(epoch_seconds).strftime(TIME_FORMAT)


def run_terminal(
    *,
    command: list[str],
    mt5_root: str | Path,
    wineprefix: str | Path,
    timeout_seconds: int,
) -> dict[str, Any]:
    env = os.environ.copy()
    env["WINEPREFIX"] = str(Path(wineprefix).expanduser())
    started_at = time.time()
    deadline_at = started_at + timeout_seconds
    try:
        process = subprocess.run(
            command,
            cwd=str(Path(mt5_root).expanduser()),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        finished_at = time.time()
        return {
            "started_at": local_time_text(started_at),
            "finished_at": local_time_text(finished_at),
            "deadline_at": local_time_text(deadline_at),
            "timeout_seconds": timeout_seconds,
            "timeout_minutes": round(timeout_seconds / 60.0, 2),
            "elapsed_seconds": round(finished_at - started_at, 2),
            "returncode": process.returncode,
            "timeout": False,
            "stdout_tail": process.stdout[-2000:],
            "stderr_tail": process.stderr[-4000:],
        }
    except subprocess.TimeoutExpired as exc:
        finished_at = time.time()
        return {
            "started_at": local_time_text(started_at),
            "finished_at": local_time_text(finished_at),
            "deadline_at": local_time_text(deadline_at),
            "timeout_seconds": timeout_seconds,
            "timeout_minutes": round(timeout_seconds / 60.0, 2),
            "elapsed_seconds": round(finished_at - started_at, 2),
            "returncode": None,
            "timeout": True,
            "stdout_tail": (exc.stdout or "")[-2000:] if isinstance(exc.stdout, str) else "",
            "stderr_tail": (exc.stderr or "")[-4000:] if isinstance(exc.stderr, str) else "",
        }


def terminal_run_failed(terminal_run: dict[str, Any] | None) -> bool:
    if not isinstance(terminal_run, dict) or terminal_run.get("dry_run") is True:
        return False
    if terminal_run.get("timeout") is True:
        return True
    return terminal_run.get("returncode") not in (0, "0")


def terminal_failure_reason(terminal_run: dict[str, Any] | None) -> str:
    if not isinstance(terminal_run, dict):
        return "terminal run failed"
    if terminal_run.get("timeout") is True:
        return "terminal run timed out before Strategy Tester completed"
    return f"terminal run returned non-zero code {terminal_run.get('returncode')}"


def collect_outputs(
    *,
    mt5_root: str | Path,
    since_minutes: float,
    modified_after_epoch: float | None,
    min_closed: int,
    weak_pf: float,
    back_xml: str | Path | None,
    forward_xml: str | Path | None,
    set_file: str | Path | None = None,
    expected_from_date: str | None = None,
    expected_to_date: str | None = None,
    html_report: str | Path | None = None,
) -> tuple[dict[str, Any] | None, list[str]]:
    warnings: list[str] = []
    tester_root = Path(mt5_root).expanduser() / "Tester"
    csvs = discover_tester_csvs(
        [tester_root],
        since_minutes=since_minutes,
        modified_after_epoch=modified_after_epoch,
    )
    if not csvs:
        warnings.append("no EA CSV files found for the requested window")
        return None, warnings
    summary = summarize_optimization_csvs(
        csvs,
        min_closed=min_closed,
        weak_pf=weak_pf,
        expected_from_date=expected_from_date,
        expected_to_date=expected_to_date,
    )
    summary["parameters"]["since_minutes"] = since_minutes
    summary["parameters"]["modified_after"] = format_epoch(modified_after_epoch)
    attach_tester_xml_summary(summary, back_xml=back_xml, forward_xml=forward_xml)
    if html_report:
        html_metrics = parse_tester_html_report(html_report)
        summary["single_test_html_report"] = html_metrics
        report_epoch = None
        if html_metrics.get("exists") is True:
            try:
                report_epoch = Path(html_report).stat().st_mtime
            except OSError:
                report_epoch = None
        expert_stats = latest_single_test_expert_log_stats(
            mt5_root=mt5_root,
            modified_after_epoch=modified_after_epoch,
            report_epoch=report_epoch,
        )
        summary["single_test_expert_log_stats"] = expert_stats
        if expert_stats.get("available") is True:
            summary["single_test_performance"] = {
                "source": "expert_log_stats",
                "closed": expert_stats.get("closed"),
                "wins": expert_stats.get("wins"),
                "losses": expert_stats.get("losses"),
                "pf": expert_stats.get("pf"),
                "net_profit": expert_stats.get("net_profit"),
                "max_losing_streak": expert_stats.get("max_losing_streak"),
                "server_time": expert_stats.get("server_time", ""),
                "log_time": expert_stats.get("log_time", ""),
            }
        elif html_metrics.get("ok") is True:
            summary["single_test_performance"] = {
                "source": "html_report",
                "closed": html_metrics.get("closed"),
                "wins": html_metrics.get("wins"),
                "losses": html_metrics.get("losses"),
                "pf": html_metrics.get("pf"),
                "net_profit": html_metrics.get("net_profit"),
                "expected_payoff": html_metrics.get("expected_payoff"),
                "max_consecutive_loss_count": html_metrics.get("max_consecutive_loss_count"),
            }
    attach_set_pass_budget(summary, set_file)
    return summary, warnings


def archive_existing_tester_csvs(
    *,
    mt5_root: str | Path,
    archive_root: str | Path,
    filename: str = "swing_evaluation_trades.csv",
    run_id: str | None = None,
) -> dict[str, Any]:
    tester_root = Path(mt5_root).expanduser() / "Tester"
    archive_base = Path(archive_root).expanduser()
    archive_run_id = archive_run_id_value(run_id)
    archive_dir = archive_base / archive_run_id
    csvs = discover_tester_csvs([tester_root], filename=filename, since_minutes=0)
    files: list[dict[str, Any]] = []
    for source in csvs:
        stat = source.stat()
        try:
            relative = source.relative_to(tester_root)
        except ValueError:
            relative = Path(source.name)
        source_time = summarize_csv_source_time(source)
        destination = archive_dir / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(destination))
        files.append(
            {
                "source": str(source),
                "archive": str(destination),
                "agent": next((parent.name for parent in source.parents if parent.name.startswith("Agent-")), ""),
                "mtime": datetime.fromtimestamp(stat.st_mtime).strftime(TIME_FORMAT),
                "size": stat.st_size,
                "source_time": source_time,
            }
        )
    return {
        "ok": True,
        "generated_at": datetime.now().strftime(TIME_FORMAT),
        "tester_root": str(tester_root),
        "run_id": archive_run_id,
        "archive_dir": str(archive_dir),
        "filename": filename,
        "count": len(files),
        "source_time_coverage": combined_source_time_coverage(files),
        "files": files,
    }


def archive_run_id_value(value: str | None = None) -> str:
    text = str(value or "").strip()
    if not text:
        return datetime.now().strftime("%Y%m%d_%H%M%S")
    if Path(text).name != text or text in {".", ".."}:
        raise ValueError(f"invalid archive run id: {value!r}")
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")
    if any(char not in allowed for char in text):
        raise ValueError(f"invalid archive run id: {value!r}")
    return text


def run_tester_pipeline(
    *,
    config_path: str | Path = DEFAULT_CONFIG,
    workspace_root: str | Path = ".",
    mt5_root: str | Path | None = None,
    wine_path: str | Path | None = None,
    wineprefix: str | Path | None = None,
    runtime_config_dir: str | Path | None = None,
    report_name: str = "Tester\\Swing_Evaluation_Trader_next_optimization",
    from_date: str | None = None,
    to_date: str | None = None,
    forward_mode: str | None = None,
    timeout_seconds: int = 7200,
    since_minutes: float = 240.0,
    collect_only: bool = False,
    dry_run: bool = False,
    allow_stale_compile: bool = False,
    allow_invalid_risk_preset: bool = False,
    allow_running_terminal: bool = False,
    min_closed: int = 30,
    weak_pf: float = 1.0,
    min_overall_pf: float = 1.2,
    min_side_pf: float = 1.0,
    min_side_avg_price_r: float = 0.0,
    min_positive_forward_back: int = 1,
    min_segment_closed: int = 500,
    min_segment_pf: float = 1.2,
    focus_side: str = "auto",
    template_set: str | Path = DEFAULT_TEMPLATE_SET,
    output_set: str | Path = DEFAULT_OUTPUT_SET,
    allow_diagnostic_output_set: bool = False,
    allow_non_adoptable_output_set: bool = False,
    sync_expert_parameters_set: bool = False,
    write_recommendation: bool = True,
    csv_modified_after: str | None = None,
    archive_agent_csvs_before_run: bool = False,
    agent_csv_archive_dir: str | Path = "runtime/mt5_agent_csv_archive",
    agent_csv_archive_run_id: str | None = None,
) -> dict[str, Any]:
    workspace = Path(workspace_root).resolve()
    mt5 = Path(mt5_root).expanduser() if mt5_root else default_mt5_root()
    wine = Path(wine_path).expanduser() if wine_path else default_wine_path()
    prefix = Path(wineprefix).expanduser() if wineprefix else default_wineprefix()
    config = Path(config_path)
    if not config.is_absolute():
        config = workspace / config
    if not config.exists():
        raise ValueError(f"Tester config not found: {config}")
    compile_summary = compile_status(workspace_root=workspace, mt5_root=mt5)
    warnings: list[str] = []
    terminal_run: dict[str, Any] | None = None
    terminal_failed = False
    report_fallback_blocked = False
    runtime_config_path: Path | None = None
    config_metadata: dict[str, str] = {}
    agent_csv_archive: dict[str, Any] = {
        "requested": archive_agent_csvs_before_run,
        "ok": True,
        "count": 0,
        "files": [],
    }
    config_text = config.read_text(encoding="utf-8")
    config_metadata = tester_config_metadata(config_text)
    current_set_file = resolve_expert_parameters_set(
        workspace_root=workspace,
        config_path=config,
        expert_parameters=config_metadata.get("expert_parameters", ""),
    )
    set_sync: dict[str, Any] = {
        "requested": sync_expert_parameters_set,
        "ok": True,
        "source": str(current_set_file) if current_set_file else "",
        "target": "",
        "copied": False,
        "already_in_place": False,
        "errors": [],
    }
    if sync_expert_parameters_set:
        set_sync = sync_expert_parameters_set_to_profile(
            set_file=current_set_file,
            expert_parameters=config_metadata.get("expert_parameters", ""),
            mt5_root=mt5,
            dry_run=dry_run or collect_only,
        )
    risk_preset = validate_tester_risk_preset(
        current_set_file,
        expert_parameters=config_metadata.get("expert_parameters", ""),
    )
    target_tester_set_sync = target_tester_set_sync_summary(
        compile_summary,
        set_file=current_set_file,
        set_sync=set_sync,
        expert_parameters=config_metadata.get("expert_parameters", ""),
        mt5_root=mt5,
    )
    compile_blocked = (
        not collect_only
        and not allow_stale_compile
        and not bool(compile_summary.get("all_compiled_fresh"))
    )
    risk_blocked = (
        not collect_only
        and not dry_run
        and not allow_invalid_risk_preset
        and not bool(risk_preset.get("ok"))
    )
    agent_csv_archive_blocked = False
    default_prefix = default_wineprefix().expanduser().resolve()
    current_prefix = prefix.expanduser().resolve()
    running_terminal_detection_enabled = current_prefix == default_prefix
    running_terminal_processes = (
        []
        if collect_only or dry_run or not running_terminal_detection_enabled
        else discover_running_terminal_processes()
    )
    running_terminal_blocked = (
        not collect_only
        and not dry_run
        and not allow_running_terminal
        and bool(running_terminal_processes)
    )
    set_sync_blocked = (
        sync_expert_parameters_set
        and not collect_only
        and not dry_run
        and not bool(set_sync.get("ok"))
    )
    tester_set_sync_blocked = (
        not collect_only
        and not dry_run
        and not compile_blocked
        and not risk_blocked
        and not running_terminal_blocked
        and not set_sync_blocked
        and target_tester_set_sync.get("status") in {"missing_mt5_set", "set_not_synced", "comparison_failed"}
    )
    blocked = (
        compile_blocked
        or risk_blocked
        or running_terminal_blocked
        or set_sync_blocked
        or tester_set_sync_blocked
    )
    agent_csv_archive_required = not collect_only and not dry_run
    agent_csv_archive_missing = agent_csv_archive_required and not archive_agent_csvs_before_run

    started_at = time.time()
    requested_csv_modified_after_epoch = parse_modified_after(csv_modified_after)
    auto_csv_modified_after_epoch: float | None = None
    csv_modified_after_epoch = requested_csv_modified_after_epoch
    if compile_blocked:
        warnings.append("compiled binaries are stale; rerun compile before MT5 optimization")
    if risk_blocked:
        errors = risk_preset.get("errors") if isinstance(risk_preset.get("errors"), list) else []
        warnings.append("tester risk preset is invalid; rerun blocked before MT5 launch: " + "; ".join(map(str, errors)))
    elif not collect_only and not dry_run and not bool(risk_preset.get("ok")):
        errors = risk_preset.get("errors") if isinstance(risk_preset.get("errors"), list) else []
        warnings.append("tester risk preset is invalid but allowed: " + "; ".join(map(str, errors)))
    if running_terminal_blocked:
        warnings.append(
            "MT5 terminal64.exe is already running; close MT5 before launching terminal64.exe /config, "
            "or rerun with --allow-running-terminal for diagnostics"
        )
    if set_sync_blocked:
        errors = set_sync.get("errors") if isinstance(set_sync.get("errors"), list) else []
        warnings.append("failed to sync ExpertParameters .set into MT5 profile before launch: " + "; ".join(map(str, errors)))
    if tester_set_sync_blocked:
        warnings.append(
            "ExpertParameters .set is not synced into MT5 profile; rerun with --sync-expert-parameters-set "
            "or copy the workspace mt5/TesterSets preset into MQL5/Profiles/Tester before launch"
        )
    if not blocked and agent_csv_archive_missing:
        warnings.append(
            "archive-agent-csvs-before-run was not set; existing Tester Agent CSV files may mix stale date ranges into this run"
        )
    if not blocked and not collect_only and not dry_run and archive_agent_csvs_before_run:
        archive_root = Path(agent_csv_archive_dir).expanduser()
        if not archive_root.is_absolute():
            archive_root = workspace / archive_root
        try:
            agent_csv_archive = archive_existing_tester_csvs(
                mt5_root=mt5,
                archive_root=archive_root,
                run_id=agent_csv_archive_run_id,
            )
            agent_csv_archive["requested"] = True
            if int(agent_csv_archive.get("count") or 0) == 0:
                warnings.append("archive-agent-csvs-before-run requested but no existing Agent CSV files were found")
            else:
                warnings.append(
                    f"archived {agent_csv_archive.get('count')} existing Agent CSV files before Tester run"
                )
        except (OSError, ValueError) as exc:
            agent_csv_archive = {
                "requested": True,
                "ok": False,
                "reason": str(exc),
                "run_id": agent_csv_archive_run_id or "",
                "count": 0,
                "files": [],
            }
            warnings.append("failed to archive existing Agent CSV files before Tester run: " + str(exc))
            agent_csv_archive_blocked = True
            blocked = True
    blocked_components = {
        "compile_stale": compile_blocked,
        "risk_preset_invalid": risk_blocked,
        "set_sync_failed": set_sync_blocked,
        "agent_csv_archive_failed": agent_csv_archive_blocked,
    }
    if tester_set_sync_blocked:
        blocked_components["tester_set_not_synced"] = True
    if running_terminal_blocked:
        blocked_components["terminal_already_running"] = True
    if blocked:
        pass
    elif not collect_only:
        prepared_text, config_metadata = prepare_tester_config(
            config_text,
            report_name=report_name,
            from_date=from_date,
            to_date=to_date,
            forward_mode=forward_mode,
            shutdown_terminal=True,
        )
        runtime_dir = Path(runtime_config_dir).expanduser() if runtime_config_dir else drive_c_config_dir(mt5)
        runtime_config_path = runtime_dir / config.name
        if dry_run:
            command = build_terminal_command(wine_path=wine, mt5_root=mt5, config_path=runtime_config_path)
            terminal_run = {
                "dry_run": True,
                "command": command,
                "runtime_config_path": str(runtime_config_path),
                "prepared_config": prepared_text,
            }
        else:
            runtime_dir.mkdir(parents=True, exist_ok=True)
            runtime_config_path.write_text(prepared_text, encoding="utf-8")
            command = build_terminal_command(wine_path=wine, mt5_root=mt5, config_path=runtime_config_path)
            terminal_run = run_terminal(
                command=command,
                mt5_root=mt5,
                wineprefix=prefix,
                timeout_seconds=timeout_seconds,
            )
            terminal_run["command"] = command
            terminal_run["runtime_config_path"] = str(runtime_config_path)
            auto_csv_modified_after_epoch = started_at - 5.0
            terminal_failed = terminal_run_failed(terminal_run)
            if terminal_failed:
                warnings.append(terminal_failure_reason(terminal_run))

    if blocked:
        requested_back, requested_forward = tester_report_paths(mt5, report_name)
        back_xml = requested_back
        forward_xml = requested_forward
        xml_metadata = {
            "source": "blocked_not_collected",
            "requested_back_xml": str(requested_back),
            "requested_forward_xml": str(requested_forward),
            "used_back_xml": str(requested_back),
            "used_forward_xml": str(requested_forward),
        }
        optimization_summary = None
        warnings.append("skipped Tester CSV/XML collection because runner was blocked before MT5 launch")
    elif dry_run:
        requested_back, requested_forward = tester_report_paths(mt5, report_name)
        back_xml = requested_back
        forward_xml = requested_forward
        xml_metadata = {
            "source": "dry_run_not_collected",
            "requested_back_xml": str(requested_back),
            "requested_forward_xml": str(requested_forward),
            "used_back_xml": str(requested_back),
            "used_forward_xml": str(requested_forward),
        }
        optimization_summary = None
        warnings.append("dry run: skipped Tester CSV/XML collection and recommendation generation")
    elif terminal_failed:
        requested_back, requested_forward = tester_report_paths(mt5, report_name)
        back_xml = requested_back
        forward_xml = requested_forward
        xml_metadata = {
            "source": "terminal_failed_not_collected",
            "requested_back_xml": str(requested_back),
            "requested_forward_xml": str(requested_forward),
            "used_back_xml": str(requested_back),
            "used_forward_xml": str(requested_forward),
        }
        optimization_summary = None
        warnings.append("skipped Tester CSV/XML collection because terminal run failed")
    else:
        back_xml, forward_xml, xml_metadata = resolve_tester_xml_paths(
            mt5_root=mt5,
            report_name=report_name,
            workspace_root=workspace,
        )
        single_strategy_test_without_recommendation = (
            not write_recommendation
            and str(config_metadata.get("optimization") or "").strip().lower() in {"0", "false", "no"}
        )
        html_report = (
            first_existing_tester_html_report(mt5, report_name)
            if single_strategy_test_without_recommendation
            else None
        )
        if xml_metadata.get("source") == "latest_pair_fallback":
            if html_report is not None:
                requested_back, requested_forward = tester_report_paths(mt5, report_name)
                back_xml = requested_back
                forward_xml = requested_forward
                xml_metadata = {
                    "source": "requested_single_test_html_report",
                    "requested_back_xml": str(requested_back),
                    "requested_forward_xml": str(requested_forward),
                    "used_back_xml": "",
                    "used_forward_xml": "",
                    "requested_html_reports": [str(path) for path in tester_html_report_paths(mt5, report_name)],
                    "used_html_report": str(html_report),
                }
                warnings.append(
                    "requested Tester XML was missing; single Strategy Test HTML report was generated, "
                    "collecting fresh Agent CSV without optimization XML"
                )
            else:
                warnings.append(
                    "requested Tester XML was missing; using latest available XML pair "
                    f"{Path(str(xml_metadata.get('used_back_xml'))).name}"
                )
            if not collect_only and html_report is None:
                report_fallback_blocked = True
                warnings.append("skipped Tester CSV/XML collection because requested Tester report was not generated")
        elif xml_metadata.get("source") == "requested_missing" and html_report is not None:
            requested_back, requested_forward = tester_report_paths(mt5, report_name)
            back_xml = requested_back
            forward_xml = requested_forward
            xml_metadata = {
                "source": "requested_single_test_html_report",
                "requested_back_xml": str(requested_back),
                "requested_forward_xml": str(requested_forward),
                "used_back_xml": "",
                "used_forward_xml": "",
                "requested_html_reports": [str(path) for path in tester_html_report_paths(mt5, report_name)],
                "used_html_report": str(html_report),
            }
            warnings.append(
                "requested Tester XML was missing; single Strategy Test HTML report was generated, "
                "collecting fresh Agent CSV without optimization XML"
            )
        if report_fallback_blocked:
            optimization_summary = None
        else:
            collect_window = since_minutes
            if not collect_only:
                elapsed_minutes = max((time.time() - started_at) / 60.0 + 10.0, 10.0)
                collect_window = max(collect_window, elapsed_minutes)
            if csv_modified_after_epoch is None:
                csv_modified_after_epoch = auto_csv_modified_after_epoch
            optimization_summary, collect_warnings = collect_outputs(
                mt5_root=mt5,
                since_minutes=collect_window,
                modified_after_epoch=csv_modified_after_epoch,
                min_closed=min_closed,
                weak_pf=weak_pf,
                back_xml=back_xml,
                forward_xml=forward_xml,
                set_file=current_set_file,
                expected_from_date=from_date or config_metadata.get("from_date"),
                expected_to_date=to_date or config_metadata.get("to_date"),
                html_report=html_report,
            )
            warnings.extend(collect_warnings)

    recommendation: dict[str, Any] | None = None
    set_metadata: dict[str, Any] | None = None
    source_time_blocked = bool(optimization_summary is not None and source_time_mismatch(optimization_summary))
    if source_time_blocked and optimization_summary is not None:
        warnings.append("optimization source time range mismatch: " + source_time_mismatch_reason(optimization_summary))
        if write_recommendation:
            warnings.append("skipped recommendation generation because optimization source time range is invalid")
    if optimization_summary is not None and write_recommendation and not source_time_blocked:
        recommendation = recommend_from_summary(
            optimization_summary,
            min_overall_pf=min_overall_pf,
            min_side_pf=min_side_pf,
            min_side_avg_price_r=min_side_avg_price_r,
            min_positive_forward_back=min_positive_forward_back,
            min_segment_closed=min_segment_closed,
            min_segment_pf=min_segment_pf,
        )
        set_metadata = write_next_set(
            output_set,
            template_set,
            recommendation,
            focus_side=focus_side,
            allow_diagnostic=allow_diagnostic_output_set,
            allow_non_adoptable=allow_non_adoptable_output_set,
        )
        recommendation["set_metadata"] = set_metadata

    ok = (
        not blocked
        and not terminal_failed
        and not report_fallback_blocked
        and not source_time_blocked
        and (dry_run or optimization_summary is not None)
    )
    return {
        "ok": ok,
        "generated_at": datetime.now().strftime(TIME_FORMAT),
        "elapsed_seconds": round(time.time() - started_at, 2),
        "workspace_root": str(workspace),
        "mt5_root": str(mt5),
        "wine": str(wine),
        "wineprefix": str(prefix),
        "config_path": str(config),
        "runtime_config_path": str(runtime_config_path) if runtime_config_path else "",
        "collect_only": collect_only,
        "dry_run": dry_run,
        "allow_stale_compile": allow_stale_compile,
        "archive_agent_csvs_before_run": archive_agent_csvs_before_run,
        "agent_csv_archive_required": agent_csv_archive_required,
        "agent_csv_archive_missing": agent_csv_archive_missing,
        "agent_csv_archive_run_id": agent_csv_archive_run_id or "",
        "agent_csv_archive": agent_csv_archive,
        "csv_modified_after": format_epoch(csv_modified_after_epoch),
        "blocked": blocked,
        "blocked_components": blocked_components,
        "compile_blocked": compile_blocked,
        "risk_preset_blocked": risk_blocked,
        "set_sync_blocked": set_sync_blocked,
        "tester_set_sync_blocked": tester_set_sync_blocked,
        "set_sync": set_sync,
        "target_tester_set_sync": target_tester_set_sync,
        "agent_csv_archive_blocked": agent_csv_archive_blocked,
        "running_terminal_blocked": running_terminal_blocked,
        "running_terminal_detection_enabled": running_terminal_detection_enabled,
        "running_terminal_processes": running_terminal_processes,
        "terminal_failed": terminal_failed,
        "report_fallback_blocked": report_fallback_blocked,
        "source_time_blocked": source_time_blocked,
        "warnings": warnings,
        "config": config_metadata,
        "set_file": str(current_set_file) if current_set_file else "",
        "risk_preset": risk_preset,
        "report_paths": {
            **xml_metadata,
            "back_xml": str(back_xml),
            "forward_xml": str(forward_xml),
        },
        "compile_status": compile_summary,
        "terminal_run": terminal_run,
        "optimization_summary": optimization_summary,
        "recommendation": recommendation,
        "next_set": set_metadata,
    }


def write_json(path: str | Path, payload: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_markdown(path: str | Path, payload: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(format_markdown(payload), encoding="utf-8")


def blocked_child_reason(payload: dict[str, Any]) -> str:
    if payload.get("terminal_failed") is True:
        return "terminal_failed"
    if payload.get("report_fallback_blocked") is True:
        return "report_fallback_blocked"
    if payload.get("source_time_blocked") is True:
        return "source_time_blocked"
    if payload.get("blocked") is True:
        return "mt5_tester_run_blocked"
    if payload.get("dry_run") is True:
        return "dry_run"
    if payload.get("ok") is False:
        return "mt5_tester_run_not_ok"
    return "not_generated"


def blocked_child_context(payload: dict[str, Any], *, kind: str) -> dict[str, Any]:
    reason = blocked_child_reason(payload)
    warnings = payload.get("warnings") if isinstance(payload.get("warnings"), list) else []
    return {
        "generated_at": payload.get("generated_at") or datetime.now().strftime(TIME_FORMAT),
        "kind": kind,
        "blocked": True,
        "reason": reason,
        "runner_ok": payload.get("ok"),
        "runner_blocked": payload.get("blocked"),
        "terminal_failed": payload.get("terminal_failed"),
        "report_fallback_blocked": payload.get("report_fallback_blocked"),
        "source_time_blocked": payload.get("source_time_blocked"),
        "collect_only": payload.get("collect_only"),
        "dry_run": payload.get("dry_run"),
        "blocked_components": payload.get("blocked_components")
        if isinstance(payload.get("blocked_components"), dict)
        else {},
        "compile_blocked": payload.get("compile_blocked"),
        "risk_preset_blocked": payload.get("risk_preset_blocked"),
        "tester_set_sync_blocked": payload.get("tester_set_sync_blocked"),
        "agent_csv_archive_blocked": payload.get("agent_csv_archive_blocked"),
        "report_paths": payload.get("report_paths") if isinstance(payload.get("report_paths"), dict) else {},
        "terminal_run": payload.get("terminal_run") if isinstance(payload.get("terminal_run"), dict) else None,
        "compile_status": payload.get("compile_status") if isinstance(payload.get("compile_status"), dict) else {},
        "risk_preset": payload.get("risk_preset") if isinstance(payload.get("risk_preset"), dict) else {},
        "set_sync": payload.get("set_sync") if isinstance(payload.get("set_sync"), dict) else {},
        "target_tester_set_sync": (
            payload.get("target_tester_set_sync")
            if isinstance(payload.get("target_tester_set_sync"), dict)
            else {}
        ),
        "agent_csv_archive_required": payload.get("agent_csv_archive_required"),
        "agent_csv_archive_missing": payload.get("agent_csv_archive_missing"),
        "agent_csv_archive": payload.get("agent_csv_archive") if isinstance(payload.get("agent_csv_archive"), dict) else {},
        "warnings": warnings,
    }


def write_blocked_child_json(path: str | Path, payload: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def blocked_child_markdown(title: str, context: dict[str, Any]) -> str:
    report_paths = context.get("report_paths") if isinstance(context.get("report_paths"), dict) else {}
    terminal = context.get("terminal_run") if isinstance(context.get("terminal_run"), dict) else {}
    compile_status = context.get("compile_status") if isinstance(context.get("compile_status"), dict) else {}
    risk_preset = context.get("risk_preset") if isinstance(context.get("risk_preset"), dict) else {}
    set_sync = context.get("set_sync") if isinstance(context.get("set_sync"), dict) else {}
    target_tester_set_sync = (
        context.get("target_tester_set_sync")
        if isinstance(context.get("target_tester_set_sync"), dict)
        else {}
    )
    agent_csv_archive = context.get("agent_csv_archive") if isinstance(context.get("agent_csv_archive"), dict) else {}
    blocked_components = (
        context.get("blocked_components") if isinstance(context.get("blocked_components"), dict) else {}
    )
    warnings = context.get("warnings") if isinstance(context.get("warnings"), list) else []
    lines = [
        f"# {title}",
        "",
        f"- Generated at: {context.get('generated_at')}",
        f"- Reason: {context.get('reason')}",
        f"- Runner ok: {context.get('runner_ok')}",
        f"- Runner blocked: {context.get('runner_blocked')}",
        f"- Terminal failed: {context.get('terminal_failed')}",
        f"- Report fallback blocked: {context.get('report_fallback_blocked')}",
        f"- Source time blocked: {context.get('source_time_blocked')}",
        f"- Collect only: {context.get('collect_only')}",
        f"- Dry run: {context.get('dry_run')}",
        f"- Blocked components: {blocked_components}",
        f"- Report source: {report_paths.get('source', '')}",
        f"- Requested back XML: {report_paths.get('requested_back_xml', '')}",
        f"- Requested forward XML: {report_paths.get('requested_forward_xml', '')}",
        f"- Used back XML: {report_paths.get('used_back_xml', '')}",
        f"- Used forward XML: {report_paths.get('used_forward_xml', '')}",
    ]
    if terminal:
        lines.extend(
            [
                f"- Terminal started at: {terminal.get('started_at', '')}",
                f"- Terminal deadline at: {terminal.get('deadline_at', terminal.get('deadline', ''))}",
                f"- Terminal timeout seconds: {terminal.get('timeout_seconds', '')}",
                f"- Terminal elapsed seconds: {terminal.get('elapsed_seconds', '')}",
                f"- Terminal returncode: {terminal.get('returncode')}",
                f"- Terminal timeout: {terminal.get('timeout')}",
            ]
        )
    if compile_status:
        lines.extend(
            [
                "",
                "## Compile Status",
                "",
                f"- Compiled fresh: {compile_status.get('all_compiled_fresh', '')}",
                f"- Sources synced: {compile_status.get('all_sources_synced', '')}",
                f"- Tester sets synced: {compile_status.get('all_tester_sets_synced', '')}",
                f"- Tester configs synced: {compile_status.get('all_tester_configs_synced', '')}",
            ]
        )
    if risk_preset:
        errors = risk_preset.get("errors") if isinstance(risk_preset.get("errors"), list) else []
        lines.extend(
            [
                "",
                "## Tester Risk Preset",
                "",
                f"- Set file: {risk_preset.get('set_file', '')}",
                f"- Mode: {risk_preset.get('mode', '')}",
                f"- OK: {risk_preset.get('ok', '')}",
                f"- Errors: {', '.join(map(str, errors)) if errors else 'None'}",
            ]
        )
    if set_sync:
        errors = set_sync.get("errors") if isinstance(set_sync.get("errors"), list) else []
        lines.extend(
            [
                "",
                "## ExpertParameters Set Sync",
                "",
                f"- Requested: {set_sync.get('requested', '')}",
                f"- OK: {set_sync.get('ok', '')}",
                f"- Source: {set_sync.get('source', '')}",
                f"- Target: {set_sync.get('target', '')}",
                f"- Copied: {set_sync.get('copied', '')}",
                f"- Already in place: {set_sync.get('already_in_place', '')}",
                f"- Target tester set synced: {target_tester_set_sync.get('synced', '')}",
                f"- Target tester set status: {target_tester_set_sync.get('status', '')}",
                f"- Errors: {', '.join(map(str, errors)) if errors else 'None'}",
            ]
        )
    if agent_csv_archive or context.get("agent_csv_archive_required") is not None:
        lines.extend(
            [
                "",
                "## Agent CSV Archive",
                "",
                f"- Required: {context.get('agent_csv_archive_required', '')}",
                f"- Missing: {context.get('agent_csv_archive_missing', '')}",
                f"- Requested: {agent_csv_archive.get('requested', '')}",
                f"- OK: {agent_csv_archive.get('ok', '')}",
                f"- Reason: {agent_csv_archive.get('reason', '')}",
                f"- Run ID: {agent_csv_archive.get('run_id', '')}",
                f"- Count: {agent_csv_archive.get('count', '')}",
            ]
        )
    lines.extend(["", "## Warnings", ""])
    lines.extend(f"- {warning}" for warning in warnings) if warnings else lines.append("- None.")
    return "\n".join(lines) + "\n"


def write_blocked_optimization_report(path_json: str | Path, path_md: str | Path, payload: dict[str, Any]) -> None:
    context = blocked_child_context(payload, kind="optimization")
    write_blocked_child_json(path_json, {"ok": False, "summary": context})
    output = Path(path_md)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(blocked_child_markdown("MT5 Tester Optimization Report Not Updated", context), encoding="utf-8")


def write_blocked_recommendation_report(path_json: str | Path, path_md: str | Path, payload: dict[str, Any]) -> None:
    context = blocked_child_context(payload, kind="recommendation")
    reason = context["reason"]
    recommendation = {
        "generated_at": context["generated_at"],
        "decision": {
            "adoptable": False,
            "reasons": [f"mt5_tester_run blocked recommendation generation: {reason}"],
            "overall_pf": 0.0,
            "overall_closed": 0,
            "positive_forward_positive_back": 0,
            "positive_forward_negative_back": 0,
        },
        "side_status": {},
        "next_search": {},
        "set_metadata": {
            "diagnostic_only": True,
            "skipped_write": True,
            "skip_reason": reason,
        },
        "runner_context": context,
    }
    write_blocked_child_json(path_json, {"ok": False, "recommendation": recommendation})
    output = Path(path_md)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        blocked_child_markdown("MT5 Optimization Recommendation Not Generated", context),
        encoding="utf-8",
    )


def agent_csv_archive_file_rows(files: object) -> list[str]:
    if not isinstance(files, list) or not files:
        return ["| - |  |  |  |  |"]
    rows: list[str] = []
    for item in files:
        if not isinstance(item, dict):
            continue
        archive = item.get("archive", item.get("planned_archive", ""))
        source_time = item.get("source_time") if isinstance(item.get("source_time"), dict) else {}
        source_time_text = ""
        if source_time:
            source_time_text = (
                f"close={source_time.get('close_rows')} "
                f"{source_time.get('first_server_time', '')}/{source_time.get('last_server_time', '')}"
            )
        rows.append(
            f"| {item.get('agent', '')} | {item.get('size', '')} | {source_time_text} | "
            f"{item.get('source', '')} | {archive} |"
        )
    return rows if rows else ["| - |  |  |  |  |"]


def running_terminal_process_rows(processes: object) -> list[str]:
    if not isinstance(processes, list) or not processes:
        return ["| - |  |"]
    rows: list[str] = []
    for item in processes:
        if not isinstance(item, dict):
            continue
        pid = str(item.get("pid", ""))
        command = str(item.get("command", "")).replace("|", "\\|")
        rows.append(f"| {pid} | {command} |")
    return rows if rows else ["| - |  |"]


def format_markdown(payload: dict[str, Any]) -> str:
    compile_summary = payload.get("compile_status") if isinstance(payload.get("compile_status"), dict) else {}
    risk_preset = payload.get("risk_preset") if isinstance(payload.get("risk_preset"), dict) else {}
    set_sync = payload.get("set_sync") if isinstance(payload.get("set_sync"), dict) else {}
    target_tester_set_sync = (
        payload.get("target_tester_set_sync")
        if isinstance(payload.get("target_tester_set_sync"), dict)
        else {}
    )
    agent_csv_archive = payload.get("agent_csv_archive") if isinstance(payload.get("agent_csv_archive"), dict) else {}
    optimization = payload.get("optimization_summary") if isinstance(payload.get("optimization_summary"), dict) else {}
    recommendation = payload.get("recommendation") if isinstance(payload.get("recommendation"), dict) else {}
    decision = recommendation.get("decision") if isinstance(recommendation.get("decision"), dict) else {}
    next_set = payload.get("next_set") if isinstance(payload.get("next_set"), dict) else {}
    terminal = payload.get("terminal_run") if isinstance(payload.get("terminal_run"), dict) else {}
    report_paths = payload.get("report_paths") if isinstance(payload.get("report_paths"), dict) else {}
    blocked_components = (
        payload.get("blocked_components") if isinstance(payload.get("blocked_components"), dict) else {}
    )
    archive_source_time = (
        agent_csv_archive.get("source_time_coverage")
        if isinstance(agent_csv_archive.get("source_time_coverage"), dict)
        else {}
    )
    lines = [
        "# MT5 Tester Run",
        "",
        f"- Generated at: {payload.get('generated_at')}",
        f"- OK: {payload.get('ok')}",
        f"- Blocked: {payload.get('blocked')}",
        f"- Blocked components: {blocked_components}",
        f"- Terminal failed: {payload.get('terminal_failed')}",
        f"- Report fallback blocked: {payload.get('report_fallback_blocked')}",
        f"- Report source: {report_paths.get('source', '')}",
        f"- Used HTML report: {report_paths.get('used_html_report', '')}",
        f"- Source time blocked: {payload.get('source_time_blocked')}",
        f"- Collect only: {payload.get('collect_only')}",
        f"- Dry run: {payload.get('dry_run')}",
        f"- Archive Agent CSVs before run: {payload.get('archive_agent_csvs_before_run')}",
        f"- Agent CSV archive required: {payload.get('agent_csv_archive_required', '')}",
        f"- Agent CSV archive missing: {payload.get('agent_csv_archive_missing', '')}",
        f"- Agent CSV archive run ID: {agent_csv_archive.get('run_id') or payload.get('agent_csv_archive_run_id', '')}",
        f"- Agent CSV archive dir: {agent_csv_archive.get('archive_dir', '')}",
        f"- Archived Agent CSVs: {agent_csv_archive.get('count', '')}",
        f"- CSV modified after: {payload.get('csv_modified_after', '')}",
        f"- Set sync requested: {set_sync.get('requested', '')}",
        f"- Set sync OK: {set_sync.get('ok', '')}",
        f"- Set sync source: {set_sync.get('source', '')}",
        f"- Set sync target: {set_sync.get('target', '')}",
        f"- Set sync copied: {set_sync.get('copied', '')}",
        f"- Target tester set synced: {target_tester_set_sync.get('synced', '')}",
        f"- Target tester set status: {target_tester_set_sync.get('status', '')}",
        f"- Target tester set source: {target_tester_set_sync.get('source', '')}",
        f"- Target tester set target: {target_tester_set_sync.get('target', '')}",
        f"- Compiled fresh: {compile_summary.get('all_compiled_fresh')}",
        f"- Tester sets synced: {compile_summary.get('all_tester_sets_synced', '')}",
        f"- Tester configs synced: {compile_summary.get('all_tester_configs_synced', '')}",
        f"- Terminal started at: {terminal.get('started_at') if terminal else ''}",
        f"- Terminal deadline at: {terminal.get('deadline_at') if terminal else ''}",
        f"- Terminal timeout seconds: {terminal.get('timeout_seconds') if terminal else ''}",
        f"- Terminal elapsed seconds: {terminal.get('elapsed_seconds') if terminal else ''}",
        f"- Terminal returncode: {terminal.get('returncode') if terminal else ''}",
        f"- Terminal timeout: {terminal.get('timeout') if terminal else ''}",
        "",
        "## Running Terminal Detection",
        "",
        f"- Detection enabled: {payload.get('running_terminal_detection_enabled', '')}",
        f"- Blocked by running terminal: {payload.get('running_terminal_blocked', '')}",
        "",
        "| pid | command |",
        "|---:|---|",
        *running_terminal_process_rows(payload.get("running_terminal_processes")),
        "",
        "## Tester Risk Preset",
        "",
        f"- Set file: {risk_preset.get('set_file', '')}",
        f"- Mode: {risk_preset.get('mode', '')}",
        f"- OK: {risk_preset.get('ok', '')}",
        f"- Inputs: {risk_preset.get('inputs', {})}",
        f"- Errors: {', '.join(map(str, risk_preset.get('errors', []))) if isinstance(risk_preset.get('errors'), list) else ''}",
        "",
        "## Agent CSV Archive",
        "",
        f"- Requested: {agent_csv_archive.get('requested', payload.get('archive_agent_csvs_before_run'))}",
        f"- OK: {agent_csv_archive.get('ok', '')}",
        f"- Run ID: {agent_csv_archive.get('run_id') or payload.get('agent_csv_archive_run_id', '')}",
        f"- Archive dir: {agent_csv_archive.get('archive_dir', '')}",
        f"- Count: {agent_csv_archive.get('count', '')}",
        f"- Source time close rows: {archive_source_time.get('close_rows', '')}",
        f"- Source time first/last: {archive_source_time.get('first_server_time', '')} / {archive_source_time.get('last_server_time', '')}",
        f"- Source time missing rows: {archive_source_time.get('close_rows_without_server_time', '')}",
        "",
        "| agent | size | source_time | source | archive |",
        "|---|---:|---|---|---|",
        *agent_csv_archive_file_rows(agent_csv_archive.get("files")),
        "",
        "## Optimization",
        "",
    ]
    if optimization:
        overall = optimization.get("overall") if isinstance(optimization.get("overall"), dict) else {}
        single_test = (
            optimization.get("single_test_performance")
            if isinstance(optimization.get("single_test_performance"), dict)
            else {}
        )
        html_report = (
            optimization.get("single_test_html_report")
            if isinstance(optimization.get("single_test_html_report"), dict)
            else {}
        )
        expert_stats = (
            optimization.get("single_test_expert_log_stats")
            if isinstance(optimization.get("single_test_expert_log_stats"), dict)
            else {}
        )
        source_time = (
            optimization.get("source_time_diagnostics")
            if isinstance(optimization.get("source_time_diagnostics"), dict)
            else {}
        )
        lines.extend(
            [
                f"- Closed: {overall.get('closed')}",
                f"- PF: {overall.get('pf')}",
                f"- Net profit: {overall.get('net_profit')}",
                f"- Avg price R: {overall.get('avg_price_r')}",
                (
                    f"- Source time in expected range: {source_time.get('matches_expected_range')}"
                    if source_time
                    else "- Source time in expected range: "
                ),
                *pass_budget_markdown_lines(optimization),
            ]
        )
        if single_test or html_report or expert_stats:
            lines.extend(
                [
                    "",
                    "## Single Strategy Test Report",
                    "",
                    f"- Preferred source: {single_test.get('source', '')}",
                    f"- Closed: {single_test.get('closed', '')}",
                    f"- Wins/Losses: {single_test.get('wins', '')} / {single_test.get('losses', '')}",
                    f"- PF: {single_test.get('pf', '')}",
                    f"- Net profit: {single_test.get('net_profit', '')}",
                    f"- Max losing streak: {single_test.get('max_losing_streak', single_test.get('max_consecutive_loss_count', ''))}",
                    f"- HTML report: {html_report.get('path', '')}",
                    f"- HTML closed/PF/net: {html_report.get('closed', '')} / {html_report.get('pf', '')} / {html_report.get('net_profit', '')}",
                    f"- Expert log server time: {expert_stats.get('server_time', '')}",
                    f"- Expert log closed/PF/net: {expert_stats.get('closed', '')} / {expert_stats.get('pf', '')} / {expert_stats.get('net_profit', '')}",
                ]
            )
    else:
        lines.append("- No optimization summary collected.")
    lines.extend(["", "## Recommendation", ""])
    if recommendation:
        lines.extend(
            [
                f"- Decision: {'ADOPTABLE' if decision.get('adoptable') else 'NOT READY'}",
                f"- Overall PF: {decision.get('overall_pf')}",
                f"- Positive forward / positive back: {decision.get('positive_forward_positive_back')}",
            ]
        )
        if next_set:
            lines.extend(
                [
                    f"- Next set: {next_set.get('path')}",
                    f"- Next set exploratory only: {next_set.get('exploratory_only', '')}",
                    f"- Next set skipped write: {next_set.get('skipped_write')}",
                    f"- Next set skip reason: {next_set.get('skip_reason', '')}",
                    f"- Next set write reason: {next_set.get('write_reason', '')}",
                ]
            )
    else:
        lines.append("- No recommendation generated.")
    warnings = payload.get("warnings") if isinstance(payload.get("warnings"), list) else []
    lines.extend(["", "## Warnings", ""])
    lines.extend(f"- {warning}" for warning in warnings) if warnings else lines.append("- None.")
    return "\n".join(lines) + "\n"


def write_child_reports(
    payload: dict[str, Any],
    *,
    optimization_json: str | Path,
    optimization_md: str | Path,
    recommendation_json: str | Path,
    recommendation_md: str | Path,
) -> None:
    optimization = payload.get("optimization_summary")
    if isinstance(optimization, dict):
        write_optimization_json(optimization_json, optimization)
        write_optimization_markdown(optimization_md, optimization)
    elif payload.get("ok") is False:
        write_blocked_optimization_report(optimization_json, optimization_md, payload)
    recommendation = payload.get("recommendation")
    if isinstance(recommendation, dict):
        write_recommendation_json(recommendation_json, recommendation)
        write_recommendation_markdown(recommendation_md, recommendation)
    elif payload.get("ok") is False:
        write_blocked_recommendation_report(recommendation_json, recommendation_md, payload)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run MT5 Strategy Tester optimization and collect recommendation outputs.")
    parser.add_argument("--config", default=DEFAULT_CONFIG)
    parser.add_argument("--workspace-root", default=".")
    parser.add_argument("--mt5-root", default=str(default_mt5_root()))
    parser.add_argument("--wine", default=str(default_wine_path()))
    parser.add_argument("--wineprefix", default=str(default_wineprefix()))
    parser.add_argument("--runtime-config-dir", default="")
    parser.add_argument("--report-name", default="Tester\\Swing_Evaluation_Trader_next_optimization")
    parser.add_argument("--from-date", default="", help="Override Tester FromDate, e.g. 2025.01.01.")
    parser.add_argument("--to-date", default="", help="Override Tester ToDate, e.g. 2025.12.31.")
    parser.add_argument("--forward-mode", default="", help="Override Tester ForwardMode.")
    parser.add_argument("--timeout-seconds", type=int, default=7200)
    parser.add_argument("--since-minutes", type=float, default=240.0)
    parser.add_argument(
        "--csv-modified-after",
        default="",
        help="Only include EA CSV files modified at or after this local time (YYYY.MM.DD HH:MM) or epoch seconds.",
    )
    parser.add_argument("--collect-only", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--archive-agent-csvs-before-run",
        action="store_true",
        help="Move existing Tester Agent CSV logs to --agent-csv-archive-dir before launching MT5.",
    )
    parser.add_argument("--agent-csv-archive-dir", default="runtime/mt5_agent_csv_archive")
    parser.add_argument(
        "--agent-csv-archive-run-id",
        default="",
        help="Archive subdirectory name used when --archive-agent-csvs-before-run is set.",
    )
    parser.add_argument("--allow-stale-compile", action="store_true")
    parser.add_argument(
        "--allow-invalid-risk-preset",
        action="store_true",
        help="Allow launching MT5 even when the referenced .set has unsafe tester risk-stop settings.",
    )
    parser.add_argument(
        "--allow-running-terminal",
        action="store_true",
        help="Allow launching terminal64.exe /config even when an MT5 terminal64.exe process is already running.",
    )
    parser.add_argument("--min-closed", type=int, default=30)
    parser.add_argument("--weak-pf", type=float, default=1.0)
    parser.add_argument("--min-overall-pf", type=float, default=1.2)
    parser.add_argument("--min-side-pf", type=float, default=1.0)
    parser.add_argument("--min-side-avg-price-r", type=float, default=0.0)
    parser.add_argument("--min-positive-forward-back", type=int, default=1)
    parser.add_argument("--min-segment-closed", type=int, default=500)
    parser.add_argument("--min-segment-pf", type=float, default=1.2)
    parser.add_argument("--focus-side", choices=("auto", "buy", "sell", "both"), default="auto")
    parser.add_argument("--template-set", default=DEFAULT_TEMPLATE_SET)
    parser.add_argument("--output-set", default=DEFAULT_OUTPUT_SET)
    parser.add_argument(
        "--allow-diagnostic-output-set",
        action="store_true",
        help="Allow writing diagnostic-only score-refit .set files to --output-set.",
    )
    parser.add_argument(
        "--allow-non-adoptable-output-set",
        action="store_true",
        help=(
            "Allow writing an exploratory .set even when the recommendation is not adoptable. "
            "Use a separate runtime or stable-candidate path, not the promoted next_optimization set."
        ),
    )
    parser.add_argument(
        "--sync-expert-parameters-set",
        action="store_true",
        help="Copy the resolved ExpertParameters .set into the MT5 MQL5/Profiles/Tester directory before launch.",
    )
    parser.add_argument("--no-recommendation", action="store_true")
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", default=DEFAULT_OUTPUT_MD)
    parser.add_argument("--optimization-output-json", default=DEFAULT_OPTIMIZATION_JSON)
    parser.add_argument("--optimization-output-md", default=DEFAULT_OPTIMIZATION_MD)
    parser.add_argument("--recommendation-output-json", default=DEFAULT_RECOMMENDATION_JSON)
    parser.add_argument("--recommendation-output-md", default=DEFAULT_RECOMMENDATION_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        payload = run_tester_pipeline(
            config_path=args.config,
            workspace_root=args.workspace_root,
            mt5_root=args.mt5_root,
            wine_path=args.wine,
            wineprefix=args.wineprefix,
            runtime_config_dir=args.runtime_config_dir or None,
            report_name=args.report_name,
            from_date=args.from_date or None,
            to_date=args.to_date or None,
            forward_mode=args.forward_mode or None,
            timeout_seconds=args.timeout_seconds,
            since_minutes=args.since_minutes,
            csv_modified_after=args.csv_modified_after,
            collect_only=args.collect_only,
            dry_run=args.dry_run,
            allow_stale_compile=args.allow_stale_compile,
            allow_invalid_risk_preset=args.allow_invalid_risk_preset,
            allow_running_terminal=args.allow_running_terminal,
            archive_agent_csvs_before_run=args.archive_agent_csvs_before_run,
            agent_csv_archive_dir=args.agent_csv_archive_dir,
            agent_csv_archive_run_id=args.agent_csv_archive_run_id or None,
            min_closed=args.min_closed,
            weak_pf=args.weak_pf,
            min_overall_pf=args.min_overall_pf,
            min_side_pf=args.min_side_pf,
            min_side_avg_price_r=args.min_side_avg_price_r,
            min_positive_forward_back=args.min_positive_forward_back,
            min_segment_closed=args.min_segment_closed,
            min_segment_pf=args.min_segment_pf,
            focus_side=args.focus_side,
            template_set=args.template_set,
            output_set=args.output_set,
            allow_diagnostic_output_set=args.allow_diagnostic_output_set,
            allow_non_adoptable_output_set=args.allow_non_adoptable_output_set,
            sync_expert_parameters_set=args.sync_expert_parameters_set,
            write_recommendation=not args.no_recommendation,
        )
    except ValueError as exc:
        print(json.dumps({"ok": False, "reason": str(exc)}, ensure_ascii=False, indent=2))
        return 2
    write_json(args.output_json, payload)
    write_markdown(args.output_md, payload)
    write_child_reports(
        payload,
        optimization_json=args.optimization_output_json,
        optimization_md=args.optimization_output_md,
        recommendation_json=args.recommendation_output_json,
        recommendation_md=args.recommendation_output_md,
    )
    print(
        json.dumps(
            {
                "ok": payload["ok"],
                "blocked": payload["blocked"],
                "warnings": payload["warnings"],
                "output_json": args.output_json,
                "output_md": args.output_md,
                "optimization_output_json": args.optimization_output_json,
                "recommendation_output_json": args.recommendation_output_json,
                "next_set": payload.get("next_set", {}).get("path") if isinstance(payload.get("next_set"), dict) else "",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if payload["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
