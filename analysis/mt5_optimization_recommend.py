from __future__ import annotations

import argparse
import json
import re
import sys
from decimal import Decimal, InvalidOperation, ROUND_FLOOR
from datetime import datetime
from pathlib import Path
from typing import Any

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analysis.market_data import TIME_FORMAT


DEFAULT_INPUT_JSON = "runtime/latest_mt5_optimization_report.json"
DEFAULT_OUTPUT_JSON = "runtime/latest_mt5_optimization_recommendation.json"
DEFAULT_OUTPUT_MD = "runtime/latest_mt5_optimization_recommendation.md"
DEFAULT_TEMPLATE_SET = "mt5/TesterSets/Swing_Evaluation_Trader_optimization.set"
DEFAULT_OUTPUT_SET = "mt5/TesterSets/Swing_Evaluation_Trader_next_optimization.set"
SIDE_NAMES = ("buy", "sell")
RR_RE = re.compile(r"\bRR\s+([0-9]+(?:\.[0-9]+)?)")
SL_RE = re.compile(r"\bSL\s+([0-9]+)-([0-9]+)pt")
TP_RE = re.compile(r"\bTP\s+([0-9]+)-([0-9]+)pt")
SET_LINE_RE = re.compile(r"^(Inp\w+)=(.*)$")
STABLE_HINT_SET_INPUTS = {
    "InpMinScore",
    "InpSwingDepth",
    "InpSwingAtrBand",
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
}
STRING_SET_INPUTS = {
    "InpBuyBlockedServerHours",
    "InpBuyBlockedMonths",
    "InpBuyBlockedWeekdays",
    "InpBuyAllowedServerHours",
    "InpSellBlockedServerHours",
    "InpSellBlockedMonths",
    "InpSellBlockedWeekdays",
    "InpSellAllowedServerHours",
}


def load_optimization_summary(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    payload = unwrap_summary_payload(payload)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def unwrap_summary_payload(payload: Any) -> Any:
    current = payload
    for _ in range(5):
        if not isinstance(current, dict) or not isinstance(current.get("summary"), dict):
            break
        current = current["summary"]
    return current


def recommend_from_summary(
    summary: dict[str, Any],
    *,
    min_overall_pf: float = 1.2,
    min_side_pf: float = 1.0,
    min_side_avg_price_r: float = 0.0,
    min_positive_forward_back: int = 1,
    min_segment_closed: int = 500,
    min_segment_pf: float = 1.2,
    max_segments: int = 10,
) -> dict[str, Any]:
    overall = as_dict(summary.get("overall"))
    side_status = side_statuses(
        summary,
        min_side_pf=min_side_pf,
        min_side_avg_price_r=min_side_avg_price_r,
    )
    score_diagnostics = side_score_statuses(summary)
    tester = tester_xml_status(summary)
    focus = {
        side: focus_for_side(
            side,
            summary,
            side_status[side],
            min_segment_closed=min_segment_closed,
            min_segment_pf=min_segment_pf,
            max_segments=max_segments,
        )
        for side in SIDE_NAMES
    }
    time_regime = time_regime_diagnostics(summary, max_segments=max_segments)
    chronological = chronological_diagnostics(summary, max_segments=max_segments)
    trend_regime = trend_regime_diagnostics(summary, max_segments=max_segments)
    apply_tester_stability_hints(focus, tester)
    apply_side_score_diagnostics(side_status, focus, score_diagnostics)
    reasons = adoption_reasons(
        overall,
        side_status,
        tester,
        chronological,
        score_diagnostics,
        min_overall_pf=min_overall_pf,
        min_positive_forward_back=min_positive_forward_back,
    )
    return {
        "generated_at": datetime.now().strftime(TIME_FORMAT),
        "decision": {
            "adoptable": not reasons,
            "reasons": reasons,
            "overall_pf": overall.get("pf", 0.0),
            "overall_closed": overall.get("closed", 0),
            "positive_forward_positive_back": tester.get("positive_forward_positive_back", 0),
            "positive_forward_negative_back": tester.get("positive_forward_negative_back", 0),
        },
        "side_status": side_status,
        "next_search": focus,
        "time_regime": time_regime,
        "chronological": chronological,
        "trend_regime": trend_regime,
        "side_score_diagnostics": score_diagnostics,
        "tester_xml": tester,
        "parameters": {
            "min_overall_pf": min_overall_pf,
            "min_side_pf": min_side_pf,
            "min_side_avg_price_r": min_side_avg_price_r,
            "min_positive_forward_back": min_positive_forward_back,
            "min_segment_closed": min_segment_closed,
            "min_segment_pf": min_segment_pf,
            "max_segments": max_segments,
        },
    }


def as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def as_rows(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [row for row in value if isinstance(row, dict)]


def metric(row: dict[str, Any], key: str, default: float = 0.0) -> float:
    value = row.get(key, default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def rounded(value: float) -> float:
    return round(value, 4)


def side_statuses(
    summary: dict[str, Any],
    *,
    min_side_pf: float,
    min_side_avg_price_r: float,
) -> dict[str, dict[str, Any]]:
    by_side = {str(row.get("group")): row for row in as_rows(summary.get("by_action"))}
    statuses: dict[str, dict[str, Any]] = {}
    for side in SIDE_NAMES:
        row = by_side.get(side, {})
        reasons: list[str] = []
        if not row:
            reasons.append("side summary missing")
        elif metric(row, "pf") < min_side_pf:
            reasons.append(f"PF {metric(row, 'pf'):.4g} < {min_side_pf:.4g}")
        if row and metric(row, "avg_price_r") < min_side_avg_price_r:
            reasons.append(f"avg_price_r {metric(row, 'avg_price_r'):.4g} < {min_side_avg_price_r:.4g}")
        status = "candidate" if not reasons else "refit_required"
        statuses[side] = {
            "status": status,
            "reasons": reasons,
            "closed": int(metric(row, "closed")) if row else 0,
            "pf": metric(row, "pf") if row else 0.0,
            "avg_price_r": metric(row, "avg_price_r") if row else 0.0,
            "net_profit": metric(row, "net_profit") if row else 0.0,
            "win_rate": metric(row, "win_rate") if row else 0.0,
        }
    return statuses


def side_score_statuses(summary: dict[str, Any]) -> dict[str, dict[str, Any]]:
    diagnostics: dict[str, dict[str, Any]] = {}
    for row in as_rows(summary.get("side_score_diagnostics")):
        side = str(row.get("side") or "").lower()
        if side not in SIDE_NAMES:
            continue
        diagnostics[side] = {
            "side": side,
            "status": str(row.get("status") or ""),
            "base_threshold": row.get("base_threshold", ""),
            "base_pf": metric(row, "base_pf"),
            "best_pf_threshold": row.get("best_pf_threshold", ""),
            "best_pf": metric(row, "best_pf"),
            "high_threshold": row.get("high_threshold", ""),
            "high_pf": metric(row, "high_pf"),
            "pf_delta_high_vs_base": metric(row, "pf_delta_high_vs_base"),
            "avg_r_delta_high_vs_base": metric(row, "avg_r_delta_high_vs_base"),
            "recommendation": row.get("recommendation", ""),
        }
    return diagnostics


def apply_side_score_diagnostics(
    side_status: dict[str, dict[str, Any]],
    focus: dict[str, dict[str, Any]],
    diagnostics: dict[str, dict[str, Any]],
) -> None:
    for side, diagnostic in diagnostics.items():
        status = str(diagnostic.get("status") or "")
        side_focus = as_dict(focus.get(side))
        side_focus["score_diagnostic"] = diagnostic
        if status == "score_inversion":
            row = side_status.setdefault(side, {"status": "score_refit_required", "reasons": []})
            row["status"] = "score_refit_required"
            reasons = row.get("reasons")
            if not isinstance(reasons, list):
                reasons = []
                row["reasons"] = reasons
            reason = side_score_inversion_reason(side, diagnostic)
            if reason not in reasons:
                reasons.append(reason)
            side_focus["action"] = "refit_score_function"
            append_focus_note(
                side_focus,
                "Score threshold is inverted; refit side-specific scoring before narrowing SL/TP search.",
            )
        elif status == "insufficient_samples":
            append_focus_note(
                side_focus,
                "Score diagnostics have insufficient closed samples; collect more Strategy Tester rows before using score as a gate.",
            )


def side_score_inversion_reason(side: str, diagnostic: dict[str, Any]) -> str:
    return (
        f"{side} score_inversion: high-score PF {metric(diagnostic, 'high_pf'):.4g} "
        f"< base PF {metric(diagnostic, 'base_pf'):.4g}"
    )


def tester_xml_status(summary: dict[str, Any]) -> dict[str, Any]:
    tester_xml = as_dict(summary.get("tester_xml"))
    back = as_dict(tester_xml.get("back"))
    forward = as_dict(tester_xml.get("forward"))
    back_parameter_diagnostics = as_rows(back.get("parameter_diagnostics"))
    forward_parameter_diagnostics = as_rows(forward.get("parameter_diagnostics"))
    top_forward = as_rows(forward.get("top"))
    stable_forward = as_rows(forward.get("stable_top"))
    forward_only = as_rows(forward.get("forward_only_top"))
    top = top_forward[0] if top_forward else {}
    top_stable = stable_forward[0] if stable_forward else {}
    forward_pf = metric(top, "Profit Factor") if top else 0.0
    forward_trades = int(metric(top, "Trades")) if top else 0
    back_result = metric(top, "Back Result") if top else 0.0
    forward_result = metric(top, "Forward Result") if top else 0.0
    stable_forward_pf = metric(top_stable, "Profit Factor") if top_stable else 0.0
    stable_forward_trades = int(metric(top_stable, "Trades")) if top_stable else 0
    stable_back_result = metric(top_stable, "Back Result") if top_stable else 0.0
    stable_forward_result = metric(top_stable, "Forward Result") if top_stable else 0.0
    diagnosis = "ok"
    if top and forward_result > 0 and back_result <= 0:
        diagnosis = "forward_positive_back_negative"
    elif not top:
        diagnosis = "missing_forward_xml"
    return {
        "diagnosis": diagnosis,
        "positive_forward_positive_back": int(metric(forward, "positive_forward_positive_back")),
        "positive_forward_negative_back": int(metric(forward, "positive_forward_negative_back")),
        "top_forward": top,
        "top_forward_pf": forward_pf,
        "top_forward_trades": forward_trades,
        "top_forward_back_result": back_result,
        "top_forward_forward_result": forward_result,
        "stable_forward": stable_forward,
        "forward_only": forward_only,
        "top_stable_forward": top_stable,
        "top_stable_forward_pf": stable_forward_pf,
        "top_stable_forward_trades": stable_forward_trades,
        "top_stable_forward_back_result": stable_back_result,
        "top_stable_forward_forward_result": stable_forward_result,
        "stable_parameter_hints": tester_parameter_hints(stable_forward),
        "back_parameter_diagnostics": back_parameter_diagnostics,
        "forward_parameter_diagnostics": forward_parameter_diagnostics,
        "back_fit_artifacts": tester_back_fit_artifacts(
            back_parameter_diagnostics,
            forward_parameter_diagnostics,
        ),
        "parameter_diagnostics": forward_parameter_diagnostics,
    }


def tester_back_fit_artifacts(
    back_diagnostics: list[dict[str, Any]],
    forward_diagnostics: list[dict[str, Any]],
    *,
    limit: int = 20,
) -> list[dict[str, Any]]:
    forward_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for item in forward_diagnostics:
        parameter = str(item.get("parameter") or "")
        for group in as_rows(item.get("groups")):
            forward_by_key[(parameter, parameter_value_key(group.get("value")))] = group

    artifacts: list[dict[str, Any]] = []
    for item in back_diagnostics:
        parameter = str(item.get("parameter") or "")
        for back_group in as_rows(item.get("groups")):
            value = back_group.get("value")
            forward_group = forward_by_key.get((parameter, parameter_value_key(value)), {})
            back_positive = metric(back_group, "positive_result")
            back_avg_result = metric(back_group, "avg_result")
            back_avg_pf = metric(back_group, "avg_pf")
            forward_positive = metric(forward_group, "positive_result")
            forward_avg_result = metric(forward_group, "avg_result")
            forward_avg_pf = metric(forward_group, "avg_pf")
            back_good = back_positive > 0 or back_avg_result > 0 or back_avg_pf >= 1.0
            forward_weak = forward_positive <= 0 or forward_avg_pf < 1.0
            if not (back_good and forward_weak):
                continue
            artifacts.append(
                {
                    "parameter": parameter,
                    "value": value,
                    "back_positive_result": int(back_positive),
                    "back_avg_result": round(back_avg_result, 4),
                    "back_avg_pf": round(back_avg_pf, 4),
                    "forward_positive_result": int(forward_positive),
                    "forward_avg_result": round(forward_avg_result, 4),
                    "forward_avg_pf": round(forward_avg_pf, 4),
                    "diagnosis": "back-fit artifact: back is positive but forward has no positive result or avg PF < 1.0",
                }
            )
    return sorted(
        artifacts,
        key=lambda row: (
            metric(row, "forward_positive_result"),
            metric(row, "forward_avg_pf"),
            -metric(row, "back_avg_pf"),
            str(row.get("parameter")),
            str(row.get("value")),
        ),
    )[:limit]


def parameter_value_key(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value).strip().lower()


def tester_parameter_hints(rows: list[dict[str, Any]]) -> dict[str, list[Any]]:
    keys = (
        "InpBuyRiskReward",
        "InpSellRiskReward",
        "InpMinScore",
        "InpSwingDepth",
        "InpSwingAtrBand",
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
    hints: dict[str, list[Any]] = {}
    for key in keys:
        values = sorted_unique(row.get(key) for row in rows if key in row)
        if values:
            hints[key] = values
    return hints


def sorted_unique(values: Any) -> list[Any]:
    unique = []
    seen: set[str] = set()
    for value in values:
        marker = json.dumps(value, sort_keys=True, ensure_ascii=False)
        if marker in seen:
            continue
        seen.add(marker)
        unique.append(value)
    return sorted(unique, key=lambda value: (str(type(value)), str(value)))


def apply_tester_stability_hints(focus: dict[str, dict[str, Any]], tester: dict[str, Any]) -> None:
    if tester.get("diagnosis") != "forward_positive_back_negative":
        return
    hints = as_dict(tester.get("stable_parameter_hints"))
    if not hints:
        return
    for side, rr_key in (("buy", "InpBuyRiskReward"), ("sell", "InpSellRiskReward")):
        side_focus = as_dict(focus.get(side))
        if not side_focus:
            continue
        stable_rr = numeric_values(hints.get(rr_key))
        side_hints = side_parameter_hints(hints, side)
        if side_hints:
            side_focus["stable_parameter_hints"] = side_hints
        if not stable_rr:
            continue
        side_focus["stable_rr_values"] = stable_rr
        current_rr = numeric_values(side_focus.get("rr_values"))
        if not current_rr:
            continue
        stable_set = set(stable_rr)
        constrained = [value for value in current_rr if value in stable_set]
        if not constrained:
            append_focus_note(
                side_focus,
                "Stable Tester RR hints did not overlap primary segment RR values; keeping segment RR values.",
            )
            continue
        excluded = [value for value in current_rr if value not in stable_set]
        side_focus["rr_values"] = constrained
        side_focus["excluded_rr_values"] = excluded
        if excluded:
            append_focus_note(
                side_focus,
                "RR values were constrained to stable back/forward Tester passes; excluded forward-only-prone RR values.",
            )


def side_parameter_hints(hints: dict[str, Any], side: str) -> dict[str, list[Any]]:
    selected: dict[str, list[Any]] = {}
    for key, value in hints.items():
        if not stable_hint_key_applies_to_side(str(key), side):
            continue
        if stable_hint_key_is_side_neutral(str(key)) or ("Buy" in str(key) if side == "buy" else "Sell" in str(key)):
            rows = as_list(value)
            if rows:
                selected[key] = rows
    return selected


def stable_hint_key_is_side_neutral(key: str) -> bool:
    return key in {
            "InpMinScore",
            "InpSwingDepth",
            "InpSwingAtrBand",
            "InpStopBufferPoints",
    }


def stable_hint_key_applies_to_side(key: str, side: str) -> bool:
    if side == "buy":
        return "Sell" not in key
    if side == "sell":
        return "Buy" not in key
    return True


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def numeric_values(value: Any) -> list[float]:
    values: list[float] = []
    for item in as_list(value):
        try:
            values.append(round(float(item), 2))
        except (TypeError, ValueError):
            continue
    return sorted(set(values))


def append_focus_note(focus: dict[str, Any], note: str) -> None:
    notes = focus.get("notes")
    if not isinstance(notes, list):
        notes = []
        focus["notes"] = notes
    if note not in notes:
        notes.append(note)


def adoption_reasons(
    overall: dict[str, Any],
    side_status: dict[str, dict[str, Any]],
    tester: dict[str, Any],
    chronological: dict[str, Any],
    score_diagnostics: dict[str, dict[str, Any]],
    *,
    min_overall_pf: float,
    min_positive_forward_back: int,
) -> list[str]:
    reasons: list[str] = []
    if metric(overall, "pf") < min_overall_pf:
        reasons.append(f"overall PF {metric(overall, 'pf'):.4g} < {min_overall_pf:.4g}")
    for side in SIDE_NAMES:
        status = side_status.get(side, {})
        if status.get("status") != "candidate":
            reasons.append(f"{side} {status.get('status')}: {', '.join(status.get('reasons', []))}")
    positive_forward_back = int(metric(tester, "positive_forward_positive_back"))
    if positive_forward_back < min_positive_forward_back:
        reasons.append(
            f"positive forward and positive back passes {positive_forward_back} < {min_positive_forward_back}"
        )
    if tester.get("diagnosis") == "forward_positive_back_negative":
        reasons.append("top forward pass is positive forward but negative back")
    if tester.get("diagnosis") == "missing_forward_xml":
        reasons.append("Tester forward XML is missing")
    for row in as_rows(chronological.get("failed_splits"))[:3]:
        reasons.append(
            "chronological split failed: "
            f"{row.get('group')} PF {metric(row, 'pf'):.4g}, avg_price_r {metric(row, 'avg_price_r'):.4g}"
        )
    return reasons


def focus_for_side(
    side: str,
    summary: dict[str, Any],
    status: dict[str, Any],
    *,
    min_segment_closed: int,
    min_segment_pf: float,
    max_segments: int,
) -> dict[str, Any]:
    best_rows = [
        row
        for row in as_rows(summary.get("best_segments"))
        if row_side(row) == side and metric(row, "pf") >= min_segment_pf
    ]
    reliable = [row for row in best_rows if int(metric(row, "closed")) >= min_segment_closed]
    reference = [row for row in best_rows if row not in reliable][:max_segments]
    weak = [row for row in as_rows(summary.get("weak_segments")) if row_side(row) == side][:max_segments]
    selected = reliable[:max_segments]
    rr_values = sorted({value for row in selected for value in row_rr_values(row)})
    sl_bands = sorted({band for row in selected for band in row_sl_bands(row)}, key=band_sort_key)
    tp_bands = sorted({band for row in selected for band in row_tp_bands(row)}, key=band_sort_key)
    action = "narrow_search" if status.get("status") == "candidate" and selected else "refit_before_search"
    if status.get("status") == "candidate" and not selected:
        action = "collect_more_or_relax_segment_threshold"
    return {
        "action": action,
        "status": status.get("status"),
        "primary_segments": slim_rows(selected),
        "reference_segments": slim_rows(reference),
        "reject_segments": slim_rows(weak),
        "rr_values": rr_values,
        "sl_bands": sl_bands,
        "tp_bands": tp_bands,
        "notes": focus_notes(side, status, selected, reference, weak, min_segment_closed),
    }


def row_side(row: dict[str, Any]) -> str:
    group = str(row.get("group") or "").lower()
    for side in SIDE_NAMES:
        if group == side or group.startswith(f"{side} "):
            return side
    return ""


def row_rr_values(row: dict[str, Any]) -> list[float]:
    group = str(row.get("group") or "")
    return [round(float(match.group(1)), 2) for match in RR_RE.finditer(group)]


def row_sl_bands(row: dict[str, Any]) -> list[str]:
    return [format_band(match) for match in SL_RE.finditer(str(row.get("group") or ""))]


def row_tp_bands(row: dict[str, Any]) -> list[str]:
    return [format_band(match) for match in TP_RE.finditer(str(row.get("group") or ""))]


def format_band(match: re.Match[str]) -> str:
    return f"{int(match.group(1))}-{int(match.group(2))}pt"


def band_sort_key(value: str) -> tuple[int, int, str]:
    match = re.match(r"([0-9]+)-([0-9]+)pt", value)
    if not match:
        return (10**9, 10**9, value)
    return (int(match.group(1)), int(match.group(2)), value)


def slim_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    keys = (
        "dimension",
        "group",
        "start_time",
        "end_time",
        "closed",
        "pf",
        "net_profit",
        "avg_price_r",
        "win_rate",
        "tp_rate",
        "sl_rate",
        "early_loss_rate",
        "diagnosis",
    )
    return [{key: row[key] for key in keys if key in row} for row in rows]


def focus_notes(
    side: str,
    status: dict[str, Any],
    selected: list[dict[str, Any]],
    reference: list[dict[str, Any]],
    weak: list[dict[str, Any]],
    min_segment_closed: int,
) -> list[str]:
    notes: list[str] = []
    if status.get("status") != "candidate":
        notes.append(f"{side} is not ready; fit side-specific scoring/filter before promotion.")
    if selected:
        notes.append(f"Primary segments have at least {min_segment_closed} closed trades.")
    elif reference:
        notes.append(f"Only low-sample positive segments were found below {min_segment_closed} closed trades.")
    if weak:
        notes.append("Reject bands should be excluded or tested with stricter entry conditions.")
    return notes


def time_regime_diagnostics(summary: dict[str, Any], *, max_segments: int) -> dict[str, Any]:
    best = slim_rows(as_rows(summary.get("best_time_segments"))[:max_segments])
    weak = slim_rows(as_rows(summary.get("weak_time_segments"))[:max_segments])
    notes: list[str] = []
    if weak:
        notes.append("Weak time regimes should be excluded, split into separate searches, or require stricter filters.")
    if best:
        notes.append("Best time regimes are diagnostic only; validate them with back/forward and annual windows before promotion.")
    if weak and not best:
        notes.append("No positive time regime met the configured PF threshold.")
    return {
        "best_segments": best,
        "weak_segments": weak,
        "notes": notes,
    }


def chronological_diagnostics(summary: dict[str, Any], *, max_segments: int) -> dict[str, Any]:
    splits = slim_rows(as_rows(summary.get("chronological_splits")))
    failed = [row for row in splits if str(row.get("diagnosis") or "")]
    notes: list[str] = []
    if failed:
        notes.append("Failed chronological splits indicate the edge did not persist across the tested period.")
    if splits and not failed:
        notes.append("No chronological split failed the PF/average-R threshold.")
    return {
        "splits": splits[:max_segments],
        "failed_splits": failed[:max_segments],
        "failure_context": chronological_failure_context(summary, failed, max_segments=max_segments),
        "notes": notes,
    }


def chronological_failure_context(
    summary: dict[str, Any],
    failed_splits: list[dict[str, Any]],
    *,
    max_segments: int,
) -> dict[str, Any]:
    if not failed_splits:
        return {}
    period_tokens = chronological_period_tokens(failed_splits)
    weak_time = rows_matching_period_tokens(as_rows(summary.get("weak_time_segments")), period_tokens)
    weak_trend = as_rows(summary.get("weak_trend_segments"))[:max_segments]
    weak_sl_tp = as_rows(summary.get("weak_segments"))[:max_segments]
    notes: list[str] = []
    if weak_time:
        notes.append("Weak time regimes overlapping failed chronological periods should be excluded or isolated in the next validation set.")
    if weak_trend:
        notes.append("Weak trend regimes should be gated or split before treating the failed period as resolved.")
    if weak_sl_tp:
        notes.append("Weak SL/TP bands remain relevant when refitting the failed chronological window.")
    context = {
        "period_tokens": sorted(period_tokens),
        "weak_time_segments": slim_rows(weak_time[:max_segments]),
        "weak_trend_segments": slim_rows(weak_trend),
        "weak_sl_tp_segments": slim_rows(weak_sl_tp),
        "notes": notes,
    }
    if not any(context[key] for key in ("weak_time_segments", "weak_trend_segments", "weak_sl_tp_segments")):
        return {}
    return context


def chronological_period_tokens(rows: list[dict[str, Any]]) -> set[str]:
    tokens: set[str] = set()
    for row in rows:
        start = parse_diagnostic_time(row.get("start_time"))
        end = parse_diagnostic_time(row.get("end_time"))
        if not start or not end:
            tokens.update(period_tokens_from_text(str(row.get("group") or "")))
            continue
        if end < start:
            start, end = end, start
        current = datetime(start.year, start.month, 1)
        end_month = datetime(end.year, end.month, 1)
        while current <= end_month:
            tokens.add(f"{current.year:04d}-{current.month:02d}")
            tokens.add(f"{current.year:04d}-Q{((current.month - 1) // 3) + 1}")
            if current.month == 12:
                current = datetime(current.year + 1, 1, 1)
            else:
                current = datetime(current.year, current.month + 1, 1)
    return tokens


def parse_diagnostic_time(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in ("%Y.%m.%d %H:%M:%S", TIME_FORMAT, "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def period_tokens_from_text(text: str) -> set[str]:
    tokens = set(re.findall(r"20[0-9]{2}-[0-9]{2}", text))
    tokens.update(re.findall(r"20[0-9]{2}-Q[1-4]", text))
    return tokens


def rows_matching_period_tokens(rows: list[dict[str, Any]], tokens: set[str]) -> list[dict[str, Any]]:
    if not tokens:
        return []
    matched: list[dict[str, Any]] = []
    for row in rows:
        row_tokens = period_tokens_from_text(str(row.get("group") or ""))
        if row_tokens & tokens:
            matched.append(row)
    return matched


def trend_regime_diagnostics(summary: dict[str, Any], *, max_segments: int) -> dict[str, Any]:
    best = slim_rows(as_rows(summary.get("best_trend_segments"))[:max_segments])
    weak = slim_rows(as_rows(summary.get("weak_trend_segments"))[:max_segments])
    notes: list[str] = []
    if weak:
        notes.append("Weak trend regimes should be refit by side before promotion.")
    if best:
        notes.append("Best trend regimes are diagnostic only; validate them in separate back/forward windows.")
    if any("unknown" in str(row.get("group") or "") for row in weak + best):
        notes.append("Trend regime is unavailable for CSV rows generated before trend columns were added.")
    return {
        "best_segments": best,
        "weak_segments": weak,
        "notes": notes,
    }


def generate_next_optimization_set(
    template_text: str,
    recommendation: dict[str, Any],
    *,
    focus_side: str = "auto",
) -> tuple[str, dict[str, Any]]:
    resolved_side = resolve_focus_side(recommendation, focus_side)
    active_sides = SIDE_NAMES if resolved_side == "both" else (resolved_side,)
    score_refit_sides = [
        side
        for side in active_sides
        if side_requires_score_refit(as_dict(as_dict(recommendation.get("next_search")).get(side)))
    ]
    updates: dict[str, str] = {
        "InpEnableBuy": bool_set_value("buy" in active_sides),
        "InpEnableSell": bool_set_value("sell" in active_sides),
        "InpUseSideRiskReward": bool_set_value(True),
        "InpUseVariableRiskReward": bool_set_value(True),
    }

    rr_by_side = {side: side_rr_values(recommendation, side) for side in active_sides}
    active_rr = sorted({rr for values in rr_by_side.values() for rr in values})
    if active_rr:
        updates["InpRiskReward"] = numeric_set_value(max(active_rr), min(active_rr), infer_step(active_rr), max(active_rr), False)
        updates["InpMinRiskReward"] = numeric_set_value(min(active_rr), min(active_rr), infer_step(active_rr), min(active_rr), False)
        updates["InpMaxRiskReward"] = numeric_set_value(max(active_rr), max(active_rr), infer_step(active_rr), max(active_rr), False)
    for side, input_name in (("buy", "InpBuyRiskReward"), ("sell", "InpSellRiskReward")):
        values = rr_by_side.get(side, [])
        if values:
            updates[input_name] = numeric_set_value(
                max(values),
                min(values),
                infer_step(values),
                max(values),
                len(set(values)) > 1,
            )
        elif active_rr:
            updates[input_name] = numeric_set_value(max(active_rr), max(active_rr), infer_step(active_rr), max(active_rr), False)

    stop_bands = sorted({band for side in active_sides for band in side_sl_bands(recommendation, side)}, key=band_sort_key)
    stop_range = stop_range_from_bands(stop_bands)
    if stop_range is not None:
        min_stop, max_stop = stop_range
        updates["InpMinStopPoints"] = numeric_set_value(min_stop, min_stop, 25, min_stop, False)
        updates["InpMaxStopPoints"] = numeric_set_value(max_stop, max_stop, 25, max_stop, False)

    stable_updates, stable_hint_artifact_exclusions, stable_hint_coverage = stable_hint_set_updates(
        recommendation,
        active_sides,
    )
    updates.update(stable_updates)

    metadata = {
        "focus_side": resolved_side,
        "active_sides": list(active_sides),
        "rr_values": active_rr,
        "sl_bands": stop_bands,
        "tp_bands": sorted(
            {band for side in active_sides for band in side_tp_bands(recommendation, side)},
            key=band_sort_key,
        ),
        "score_refit_sides": score_refit_sides,
        "diagnostic_only": bool(score_refit_sides),
        "stable_hint_updates": stable_updates,
        "stable_hint_artifact_exclusions": stable_hint_artifact_exclusions,
        "stable_hint_coverage": stable_hint_coverage,
        "updates": updates,
    }
    rendered = apply_set_updates(template_text, updates, metadata)
    pass_estimate = estimate_set_passes(rendered)
    metadata.update(pass_estimate)
    rendered = apply_set_updates(template_text, updates, metadata)
    return rendered, metadata


def resolve_focus_side(recommendation: dict[str, Any], focus_side: str) -> str:
    requested = focus_side.lower()
    if requested in {"buy", "sell", "both"}:
        return requested
    next_search = as_dict(recommendation.get("next_search"))
    primary_sides = [
        side
        for side in SIDE_NAMES
        if side_is_auto_search_candidate(as_dict(next_search.get(side)))
        and as_rows(as_dict(next_search.get(side)).get("primary_segments"))
    ]
    if len(primary_sides) == 1:
        return primary_sides[0]
    if len(primary_sides) == 2:
        return "both"
    reference_sides = [
        side
        for side in SIDE_NAMES
        if side_is_auto_search_candidate(as_dict(next_search.get(side)))
        and as_rows(as_dict(next_search.get(side)).get("reference_segments"))
    ]
    if len(reference_sides) == 1:
        return reference_sides[0]
    fallback_primary_sides = [
        side
        for side in SIDE_NAMES
        if as_rows(as_dict(next_search.get(side)).get("primary_segments"))
    ]
    if len(fallback_primary_sides) == 1:
        return fallback_primary_sides[0]
    if len(fallback_primary_sides) == 2:
        return "both"
    return "both"


def side_is_auto_search_candidate(focus: dict[str, Any]) -> bool:
    if side_requires_score_refit(focus):
        return False
    action = str(focus.get("action") or "")
    if not action:
        return True
    return action in {"narrow_search", "collect_more_or_relax_segment_threshold"}


def side_requires_score_refit(focus: dict[str, Any]) -> bool:
    if str(focus.get("action") or "") == "refit_score_function":
        return True
    diagnostic = as_dict(focus.get("score_diagnostic"))
    return str(diagnostic.get("status") or "") == "score_inversion"


def side_rr_values(recommendation: dict[str, Any], side: str) -> list[float]:
    focus = as_dict(as_dict(recommendation.get("next_search")).get(side))
    values = [round(float(value), 2) for value in focus.get("rr_values", [])]
    if values:
        return sorted(set(values))
    rows = as_rows(focus.get("primary_segments")) or as_rows(focus.get("reference_segments"))
    values = [value for row in rows for value in row_rr_values(row)]
    return sorted(set(values))


def stable_hint_set_updates(
    recommendation: dict[str, Any],
    active_sides: tuple[str, ...],
) -> tuple[dict[str, str], list[dict[str, Any]], list[dict[str, Any]]]:
    merged: dict[str, list[Any]] = {}
    requested: dict[str, list[Any]] = {}
    excluded_by_parameter: dict[str, list[Any]] = {}
    opposite_side_parameters: set[str] = set()
    artifact_keys = stable_hint_artifact_keys(recommendation)
    exclusions: list[dict[str, Any]] = []
    seen_exclusions: set[tuple[str, str]] = set()
    next_search = as_dict(recommendation.get("next_search"))
    for side in active_sides:
        hints = as_dict(as_dict(next_search.get(side)).get("stable_parameter_hints"))
        for key, values in hints.items():
            requested_values = requested.setdefault(key, [])
            requested_values.extend(as_list(values))
            if not stable_hint_key_applies_to_side(str(key), side):
                opposite_side_parameters.add(str(key))
                continue
            if key not in STABLE_HINT_SET_INPUTS:
                continue
            target = merged.setdefault(key, [])
            for value in as_list(values):
                artifact_key = (str(key), parameter_value_key(value))
                if artifact_key in artifact_keys:
                    excluded_by_parameter.setdefault(key, []).append(value)
                    if artifact_key not in seen_exclusions:
                        seen_exclusions.add(artifact_key)
                        exclusions.append(
                            {
                                "parameter": key,
                                "value": value,
                                "reason": "back-fit artifact",
                            }
                        )
                    continue
                target.append(value)
    updates: dict[str, str] = {}
    for key, values in merged.items():
        rendered = stable_hint_set_value(key, values)
        if rendered is not None:
            updates[key] = rendered
    coverage = stable_hint_coverage_rows(
        requested=requested,
        usable=merged,
        updates=updates,
        excluded_by_parameter=excluded_by_parameter,
        opposite_side_parameters=opposite_side_parameters,
    )
    return updates, exclusions, coverage


def stable_hint_coverage_rows(
    *,
    requested: dict[str, list[Any]],
    usable: dict[str, list[Any]],
    updates: dict[str, str],
    excluded_by_parameter: dict[str, list[Any]],
    opposite_side_parameters: set[str],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key in sorted(requested):
        requested_values = sorted_unique(requested.get(key, []))
        usable_values = sorted_unique(usable.get(key, []))
        excluded_values = sorted_unique(excluded_by_parameter.get(key, []))
        applied = key in updates
        row: dict[str, Any] = {
            "parameter": key,
            "requested_values": requested_values,
            "applied": applied,
        }
        if usable_values:
            row["usable_values"] = usable_values
        if excluded_values:
            row["excluded_values"] = excluded_values
        if applied:
            row["set_value"] = updates[key]
        elif key in opposite_side_parameters:
            row["skip_reason"] = "opposite_side_input"
        elif key not in STABLE_HINT_SET_INPUTS:
            row["skip_reason"] = "unsupported_input"
        elif excluded_values and not usable_values:
            row["skip_reason"] = "all_values_excluded_as_back_fit_artifacts"
        else:
            row["skip_reason"] = "could_not_render_set_value"
        rows.append(row)
    return rows


def stable_hint_artifact_keys(recommendation: dict[str, Any]) -> set[tuple[str, str]]:
    tester = as_dict(recommendation.get("tester_xml"))
    keys: set[tuple[str, str]] = set()
    for row in as_rows(tester.get("back_fit_artifacts")):
        parameter = str(row.get("parameter") or "")
        if parameter:
            keys.add((parameter, parameter_value_key(row.get("value"))))
    return keys


def stable_hint_set_value(key: str, values: list[Any]) -> str | None:
    unique = sorted_unique(values)
    if not unique:
        return None
    if key in STRING_SET_INPUTS:
        if len(unique) != 1:
            return None
        return str(unique[0])
    if all(isinstance(value, bool) for value in unique):
        return bool_set_value(any(unique), optimize=len(unique) > 1)
    numeric = numeric_values(unique)
    if len(numeric) == len(unique):
        return numeric_set_value(max(numeric), min(numeric), infer_step(numeric), max(numeric), len(set(numeric)) > 1)
    if len(unique) == 1:
        return str(unique[0])
    return None


def side_sl_bands(recommendation: dict[str, Any], side: str) -> list[str]:
    focus = as_dict(as_dict(recommendation.get("next_search")).get(side))
    bands = [str(value) for value in focus.get("sl_bands", []) if value]
    if bands:
        return sorted(set(bands), key=band_sort_key)
    rows = as_rows(focus.get("primary_segments")) or as_rows(focus.get("reference_segments"))
    bands = [band for row in rows for band in row_sl_bands(row)]
    return sorted(set(bands), key=band_sort_key)


def side_tp_bands(recommendation: dict[str, Any], side: str) -> list[str]:
    focus = as_dict(as_dict(recommendation.get("next_search")).get(side))
    bands = [str(value) for value in focus.get("tp_bands", []) if value]
    if bands:
        return sorted(set(bands), key=band_sort_key)
    rows = as_rows(focus.get("primary_segments")) or as_rows(focus.get("reference_segments"))
    bands = [band for row in rows for band in row_tp_bands(row)]
    return sorted(set(bands), key=band_sort_key)


def stop_range_from_bands(bands: list[str]) -> tuple[int, int] | None:
    ranges = [band_range(band) for band in bands]
    ranges = [item for item in ranges if item is not None]
    if not ranges:
        return None
    return (min(item[0] for item in ranges), max(item[1] for item in ranges))


def band_range(value: str) -> tuple[int, int] | None:
    match = re.match(r"([0-9]+)-([0-9]+)pt", value)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def infer_step(values: list[float]) -> float:
    unique = sorted(set(values))
    if len(unique) < 2:
        return 1.0
    deltas = [round(unique[index + 1] - unique[index], 6) for index in range(len(unique) - 1)]
    return min(delta for delta in deltas if delta > 0) if any(delta > 0 for delta in deltas) else 1.0


def bool_set_value(value: bool, *, optimize: bool = False) -> str:
    text = "true" if value else "false"
    return f"{text}||false||0||true||{'Y' if optimize else 'N'}"


def numeric_set_value(current: float, start: float, step: float, stop: float, optimize: bool) -> str:
    return (
        f"{format_number(current)}||{format_number(start)}||{format_number(step)}||"
        f"{format_number(stop)}||{'Y' if optimize else 'N'}"
    )


def format_number(value: float) -> str:
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.6f}".rstrip("0").rstrip(".")


def apply_set_updates(template_text: str, updates: dict[str, str], metadata: dict[str, Any]) -> str:
    lines = template_text.splitlines()
    seen: set[str] = set()
    diagnostic_only = bool(metadata.get("diagnostic_only"))
    rendered: list[str] = [
        "; Generated from MT5 optimization recommendation.",
        f"; Focus side: {metadata.get('focus_side')}",
        f"; RR values: {', '.join(str(value) for value in metadata.get('rr_values', [])) or '-'}",
        f"; SL bands: {', '.join(str(value) for value in metadata.get('sl_bands', [])) or '-'}",
        f"; TP bands: {', '.join(str(value) for value in metadata.get('tp_bands', [])) or '-'}",
    ]
    pass_count = metadata.get("estimated_full_factorial_passes")
    input_count = metadata.get("optimized_input_count")
    if pass_count is not None and input_count is not None:
        rendered.append(f"; Optimized inputs: {input_count}; full-factorial passes: {pass_count}")
        rendered.append("; MT5 Optimization=2 is genetic, so actual executed passes may stop before this count.")
    score_refit_sides = metadata.get("score_refit_sides")
    if isinstance(score_refit_sides, list) and score_refit_sides:
        rendered.append(
            f"; Diagnostic only: score refit required for {', '.join(str(side) for side in score_refit_sides)}."
        )
        rendered.append("; Do not treat this generated set as a normal narrowed SL/TP promotion candidate.")
    stable_updates = metadata.get("stable_hint_updates")
    if isinstance(stable_updates, dict) and stable_updates:
        rendered.append(f"; Stable hint inputs: {', '.join(sorted(stable_updates))}")
    artifact_exclusions = metadata.get("stable_hint_artifact_exclusions")
    if isinstance(artifact_exclusions, list) and artifact_exclusions:
        details = ", ".join(
            f"{row.get('parameter')}={row.get('value')}" for row in artifact_exclusions if isinstance(row, dict)
        )
        rendered.append(f"; Stable hint artifact exclusions: {details}")
    for line in lines:
        match = SET_LINE_RE.match(line)
        if match and match.group(1) in updates:
            name = match.group(1)
            value = updates[name]
            if diagnostic_only:
                value = freeze_set_optimization_value(value)
            rendered.append(f"{name}={value}")
            seen.add(name)
        elif match and inactive_side_input(match.group(1), metadata):
            rendered.append(f"{match.group(1)}={freeze_set_optimization_value(match.group(2))}")
        else:
            rendered.append(freeze_set_optimization_line(line) if diagnostic_only else line)
    missing = [name for name in updates if name not in seen]
    if missing:
        rendered.extend(["", "; Added generated inputs"])
        rendered.extend(f"{name}={updates[name]}" for name in missing)
    return "\n".join(rendered).rstrip() + "\n"


def freeze_set_optimization_line(line: str) -> str:
    match = SET_LINE_RE.match(line)
    if not match:
        return line
    return f"{match.group(1)}={freeze_set_optimization_value(match.group(2))}"


def inactive_side_input(name: str, metadata: dict[str, Any]) -> bool:
    active = metadata.get("active_sides")
    if not isinstance(active, list):
        return False
    active_sides = {str(side).lower() for side in active}
    if "buy" not in active_sides and "Buy" in name:
        return True
    if "sell" not in active_sides and "Sell" in name:
        return True
    return False


def freeze_set_optimization_value(value: str) -> str:
    parts = value.split("||")
    if len(parts) < 5:
        return value
    if parts[4].strip().upper() == "Y":
        parts[4] = "N"
    return "||".join(parts)


def estimate_set_passes(set_text: str) -> dict[str, Any]:
    inputs: list[dict[str, Any]] = []
    total = 1
    for line in set_text.splitlines():
        match = SET_LINE_RE.match(line.strip())
        if not match:
            continue
        name, value = match.groups()
        detail = optimized_input_detail(name, value)
        if detail is None:
            continue
        inputs.append(detail)
        total *= int(detail["count"])
    return {
        "optimized_input_count": len(inputs),
        "estimated_full_factorial_passes": total,
        "optimized_inputs": inputs,
    }


def optimized_input_detail(name: str, value: str) -> dict[str, Any] | None:
    parts = [part.strip() for part in value.split("||")]
    if len(parts) < 5 or parts[4].upper() != "Y":
        return None
    current, start, step, stop = parts[:4]
    count, value_type = optimization_value_count(start, step, stop)
    return {
        "name": name,
        "current": current,
        "start": start,
        "step": step,
        "stop": stop,
        "count": count,
        "type": value_type,
    }


def optimization_value_count(start: str, step: str, stop: str) -> tuple[int, str]:
    start_bool = parse_bool_text(start)
    stop_bool = parse_bool_text(stop)
    if start_bool is not None and stop_bool is not None:
        return (1 if start_bool == stop_bool else 2), "bool"

    start_decimal = parse_decimal(start)
    step_decimal = parse_decimal(step)
    stop_decimal = parse_decimal(stop)
    if start_decimal is None or step_decimal is None or stop_decimal is None:
        return 1, "string"
    if step_decimal == 0:
        return 1, "numeric"
    distance = stop_decimal - start_decimal
    if distance == 0:
        return 1, "numeric"
    if (distance > 0 and step_decimal < 0) or (distance < 0 and step_decimal > 0):
        return 1, "numeric"
    steps = (abs(distance) / abs(step_decimal)).to_integral_value(rounding=ROUND_FLOOR)
    return max(int(steps) + 1, 1), "numeric"


def parse_bool_text(value: str) -> bool | None:
    lowered = value.strip().lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    return None


def parse_decimal(value: str) -> Decimal | None:
    try:
        return Decimal(value.strip())
    except (InvalidOperation, ValueError):
        return None


def format_recommendation_markdown(recommendation: dict[str, Any]) -> str:
    decision = as_dict(recommendation.get("decision"))
    tester = as_dict(recommendation.get("tester_xml"))
    set_metadata = as_dict(recommendation.get("set_metadata"))
    lines = [
        "# MT5 Optimization Recommendation",
        "",
        f"- Generated at: {recommendation.get('generated_at')}",
        f"- Decision: {'ADOPTABLE' if decision.get('adoptable') else 'NOT READY'}",
        f"- Overall PF: {decision.get('overall_pf')}",
        f"- Closed: {decision.get('overall_closed')}",
        f"- Positive forward / positive back: {decision.get('positive_forward_positive_back')}",
        f"- Positive forward / negative back: {decision.get('positive_forward_negative_back')}",
        "",
        "## Reasons",
        "",
    ]
    reasons = decision.get("reasons")
    if isinstance(reasons, list) and reasons:
        lines.extend(f"- {reason}" for reason in reasons)
    else:
        lines.append("- None.")
    if set_metadata:
        lines.extend(
            [
                "",
                "## Next Set",
                "",
                f"- Path: {set_metadata.get('path')}",
                f"- Template: {set_metadata.get('template')}",
                f"- Focus side: {set_metadata.get('focus_side')}",
                f"- Diagnostic only: {set_metadata.get('diagnostic_only')}",
                f"- Exploratory only: {set_metadata.get('exploratory_only', '')}",
                f"- Skipped write: {set_metadata.get('skipped_write')}",
                f"- Skip reason: {set_metadata.get('skip_reason', '')}",
                f"- Write reason: {set_metadata.get('write_reason', '')}",
                f"- Optimized inputs: {set_metadata.get('optimized_input_count')}",
                f"- Full-factorial pass candidates: {set_metadata.get('estimated_full_factorial_passes')}",
            ]
        )
        if as_rows(set_metadata.get("stable_hint_coverage")):
            lines.extend(
                [
                    "",
                    "Stable hint coverage:",
                    "",
                    stable_hint_coverage_table(set_metadata.get("stable_hint_coverage")),
                ]
            )
    lines.extend(
        [
            "",
            "## Side Status",
            "",
            "| side | status | closed | PF | avg_price_r | net_profit | reasons |",
            "|---|---|---:|---:|---:|---:|---|",
        ]
    )
    for side, row in as_dict(recommendation.get("side_status")).items():
        lines.append(
            f"| {side} | {row.get('status')} | {row.get('closed')} | {row.get('pf')} | "
            f"{row.get('avg_price_r')} | {row.get('net_profit')} | {', '.join(row.get('reasons', []))} |"
        )
    lines.extend(
        [
            "",
            "## Side Score Diagnostics",
            "",
            side_score_diagnostics_table(recommendation.get("side_score_diagnostics")),
            "",
        ]
    )
    lines.extend(
        [
            "",
            "## Next Search",
            "",
        ]
    )
    for side in SIDE_NAMES:
        focus = as_dict(as_dict(recommendation.get("next_search")).get(side))
        lines.extend(
            [
                f"### {side.upper()}",
                "",
                f"- Action: {focus.get('action')}",
                f"- RR values: {', '.join(str(value) for value in focus.get('rr_values', [])) or '-'}",
                f"- SL bands: {', '.join(str(value) for value in focus.get('sl_bands', [])) or '-'}",
                f"- TP bands: {', '.join(str(value) for value in focus.get('tp_bands', [])) or '-'}",
                f"- Stable RR values: {', '.join(str(value) for value in focus.get('stable_rr_values', [])) or '-'}",
                f"- Excluded RR values: {', '.join(str(value) for value in focus.get('excluded_rr_values', [])) or '-'}",
            ]
        )
        score_diagnostic = as_dict(focus.get("score_diagnostic"))
        if score_diagnostic:
            lines.append(
                "- Score diagnostic: "
                f"{score_diagnostic.get('status')}, "
                f"base PF {score_diagnostic.get('base_pf')}, "
                f"high PF {score_diagnostic.get('high_pf')}, "
                f"{score_diagnostic.get('recommendation')}"
            )
        for note in focus.get("notes", []):
            lines.append(f"- Note: {note}")
        if as_dict(focus.get("stable_parameter_hints")):
            lines.extend(["", "Stable parameter hints:", "", tester_hints_markdown(focus.get("stable_parameter_hints")), ""])
        lines.extend(["", "Primary segments:", "", segment_table(focus.get("primary_segments", [])), ""])
        lines.extend(["Reference segments:", "", segment_table(focus.get("reference_segments", [])), ""])
        lines.extend(["Reject segments:", "", segment_table(focus.get("reject_segments", [])), ""])
    time_regime = as_dict(recommendation.get("time_regime"))
    lines.extend(["## Time Regime Diagnostics", ""])
    for note in as_list(time_regime.get("notes")):
        lines.append(f"- Note: {note}")
    lines.extend(["", "Best time segments:", "", segment_table(time_regime.get("best_segments", [])), ""])
    lines.extend(["Weak time segments:", "", segment_table(time_regime.get("weak_segments", [])), ""])
    chronological = as_dict(recommendation.get("chronological"))
    lines.extend(["## Chronological Split Diagnostics", ""])
    for note in as_list(chronological.get("notes")):
        lines.append(f"- Note: {note}")
    lines.extend(["", "Splits:", "", segment_table(chronological.get("splits", [])), ""])
    lines.extend(["Failed splits:", "", segment_table(chronological.get("failed_splits", [])), ""])
    failure_context = as_dict(chronological.get("failure_context"))
    if failure_context:
        lines.extend(["Chronological Failure Context:", ""])
        for note in as_list(failure_context.get("notes")):
            lines.append(f"- Note: {note}")
        tokens = as_list(failure_context.get("period_tokens"))
        if tokens:
            lines.append(f"- Failed period tokens: {', '.join(str(value) for value in tokens)}")
        lines.extend(
            [
                "",
                "Weak time segments overlapping failed periods:",
                "",
                segment_table(failure_context.get("weak_time_segments", [])),
                "",
                "Weak trend segments:",
                "",
                segment_table(failure_context.get("weak_trend_segments", [])),
                "",
                "Weak SL/TP segments:",
                "",
                segment_table(failure_context.get("weak_sl_tp_segments", [])),
                "",
            ]
        )
    trend_regime = as_dict(recommendation.get("trend_regime"))
    lines.extend(["## Trend Regime Diagnostics", ""])
    for note in as_list(trend_regime.get("notes")):
        lines.append(f"- Note: {note}")
    lines.extend(["", "Best trend segments:", "", segment_table(trend_regime.get("best_segments", [])), ""])
    lines.extend(["Weak trend segments:", "", segment_table(trend_regime.get("weak_segments", [])), ""])
    lines.extend(
        [
            "## Tester XML",
            "",
            f"- Diagnosis: {tester.get('diagnosis')}",
            f"- Top forward PF: {tester.get('top_forward_pf')}",
            f"- Top forward trades: {tester.get('top_forward_trades')}",
            f"- Top forward back result: {tester.get('top_forward_back_result')}",
            f"- Top forward forward result: {tester.get('top_forward_forward_result')}",
            f"- Top stable forward PF: {tester.get('top_stable_forward_pf')}",
            f"- Top stable forward trades: {tester.get('top_stable_forward_trades')}",
            f"- Top stable forward back result: {tester.get('top_stable_forward_back_result')}",
            f"- Top stable forward forward result: {tester.get('top_stable_forward_forward_result')}",
            "",
            "### Stable Parameter Hints",
            "",
            tester_hints_markdown(tester.get("stable_parameter_hints")),
            "",
            "### Stable Forward Passes",
            "",
            tester_pass_table(tester.get("stable_forward")),
            "",
            "### Forward-Only Passes",
            "",
            tester_pass_table(tester.get("forward_only")),
            "",
            "### Back Parameter Diagnostics",
            "",
            tester_parameter_diagnostics_table(tester.get("back_parameter_diagnostics")),
            "",
            "### Back-Fit Parameter Artifacts",
            "",
            tester_back_fit_artifacts_table(tester.get("back_fit_artifacts")),
            "",
            "### Forward Parameter Diagnostics",
            "",
            tester_parameter_diagnostics_table(tester.get("forward_parameter_diagnostics")),
            "",
        ]
    )
    return "\n".join(lines) + "\n"


def tester_hints_markdown(value: Any) -> str:
    hints = as_dict(value)
    if not hints:
        return "- None."
    return "\n".join(f"- {key}: {', '.join(str(item) for item in values)}" for key, values in hints.items())


def stable_hint_coverage_table(value: Any) -> str:
    rows = as_rows(value)
    if not rows:
        return "- None."
    headers = ["parameter", "applied", "set_value", "requested_values", "excluded_values", "skip_reason"]
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    for row in rows:
        rendered = dict(row)
        for key in ("requested_values", "excluded_values"):
            values = rendered.get(key)
            if isinstance(values, list):
                rendered[key] = ", ".join(str(item) for item in values)
        lines.append("| " + " | ".join(str(rendered.get(header, "")) for header in headers) + " |")
    return "\n".join(lines)


def side_score_diagnostics_table(value: Any) -> str:
    rows = list(as_dict(value).values())
    if not rows:
        return "- None."
    headers = [
        "side",
        "status",
        "base_threshold",
        "base_pf",
        "best_pf_threshold",
        "best_pf",
        "high_threshold",
        "high_pf",
        "pf_delta_high_vs_base",
        "recommendation",
    ]
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(header, "")) for header in headers) + " |")
    return "\n".join(lines)


def tester_pass_table(rows: Any) -> str:
    rows = as_rows(rows)
    if not rows:
        return "- None."
    headers = [
        "Pass",
        "Forward Result",
        "Back Result",
        "Profit Factor",
        "Trades",
        "InpMinScore",
        "InpBuyRiskReward",
        "InpSellRiskReward",
        "InpSwingDepth",
        "InpSwingAtrBand",
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


def tester_parameter_diagnostics_table(items: Any) -> str:
    items = as_rows(items)
    if not items:
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
        parameter = item.get("parameter", "")
        for group in as_rows(item.get("groups")):
            row = {"parameter": parameter, **group}
            lines.append("| " + " | ".join(str(row.get(header, "")) for header in headers) + " |")
    return "\n".join(lines) if len(lines) > 2 else "- None."


def tester_back_fit_artifacts_table(items: Any) -> str:
    rows = as_rows(items)
    if not rows:
        return "- None."
    headers = [
        "parameter",
        "value",
        "back_positive_result",
        "back_avg_result",
        "back_avg_pf",
        "forward_positive_result",
        "forward_avg_result",
        "forward_avg_pf",
        "diagnosis",
    ]
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(header, "")) for header in headers) + " |")
    return "\n".join(lines)


def segment_table(rows: Any) -> str:
    rows = as_rows(rows)
    if not rows:
        return "- None."
    headers = [
        "dimension",
        "group",
        "start_time",
        "end_time",
        "closed",
        "pf",
        "avg_price_r",
        "net_profit",
        "tp_rate",
        "sl_rate",
        "early_loss_rate",
        "diagnosis",
    ]
    active_headers = [header for header in headers if any(header in row for row in rows)]
    lines = ["| " + " | ".join(active_headers) + " |", "|" + "|".join("---" for _ in active_headers) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(header, "")) for header in active_headers) + " |")
    return "\n".join(lines)


def write_json(path: str | Path, recommendation: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"ok": True, "recommendation": recommendation}, ensure_ascii=False, indent=2) + "\n")


def write_markdown(path: str | Path, recommendation: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(format_recommendation_markdown(recommendation), encoding="utf-8")


def write_next_set(
    path: str | Path,
    template_path: str | Path,
    recommendation: dict[str, Any],
    *,
    focus_side: str,
    allow_diagnostic: bool = False,
    allow_non_adoptable: bool = False,
) -> dict[str, Any]:
    template_text = Path(template_path).read_text(encoding="utf-8")
    rendered, metadata = generate_next_optimization_set(template_text, recommendation, focus_side=focus_side)
    output = Path(path)
    metadata["path"] = str(output)
    metadata["template"] = str(template_path)
    adoptable = as_dict(recommendation.get("decision")).get("adoptable") is True
    metadata["exploratory_only"] = not adoptable
    if metadata.get("diagnostic_only") and not allow_diagnostic:
        metadata["skipped_write"] = True
        metadata["skip_reason"] = "diagnostic_only"
        return metadata
    if not adoptable and not allow_non_adoptable and not metadata.get("diagnostic_only"):
        metadata["skipped_write"] = True
        metadata["skip_reason"] = "not_adoptable"
        return metadata
    if metadata.get("diagnostic_only") and allow_diagnostic:
        metadata["write_reason"] = "diagnostic_output_set_allowed"
    elif not adoptable and allow_non_adoptable:
        metadata["write_reason"] = "non_adoptable_output_set_allowed"
    else:
        metadata["write_reason"] = "adoptable"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    metadata["skipped_write"] = False
    return metadata


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Recommend the next MT5 Tester optimization search ranges.")
    parser.add_argument("--input", default=DEFAULT_INPUT_JSON)
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", default=DEFAULT_OUTPUT_MD)
    parser.add_argument("--template-set", default=DEFAULT_TEMPLATE_SET)
    parser.add_argument("--output-set", default="")
    parser.add_argument("--focus-side", choices=("auto", "buy", "sell", "both"), default="auto")
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
            "Use a separate runtime or stable-candidate path; do not overwrite the promoted next_optimization set."
        ),
    )
    parser.add_argument("--min-overall-pf", type=float, default=1.2)
    parser.add_argument("--min-side-pf", type=float, default=1.0)
    parser.add_argument("--min-side-avg-price-r", type=float, default=0.0)
    parser.add_argument("--min-positive-forward-back", type=int, default=1)
    parser.add_argument("--min-segment-closed", type=int, default=500)
    parser.add_argument("--min-segment-pf", type=float, default=1.2)
    parser.add_argument("--max-segments", type=int, default=10)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    summary = load_optimization_summary(args.input)
    recommendation = recommend_from_summary(
        summary,
        min_overall_pf=args.min_overall_pf,
        min_side_pf=args.min_side_pf,
        min_side_avg_price_r=args.min_side_avg_price_r,
        min_positive_forward_back=args.min_positive_forward_back,
        min_segment_closed=args.min_segment_closed,
        min_segment_pf=args.min_segment_pf,
        max_segments=args.max_segments,
    )
    set_metadata = None
    if args.output_set:
        set_metadata = write_next_set(
            args.output_set,
            args.template_set,
            recommendation,
            focus_side=args.focus_side,
            allow_diagnostic=args.allow_diagnostic_output_set,
            allow_non_adoptable=args.allow_non_adoptable_output_set,
        )
        recommendation["set_metadata"] = set_metadata
    write_json(args.output_json, recommendation)
    write_markdown(args.output_md, recommendation)
    print(
        json.dumps(
            {
                "ok": True,
                "adoptable": recommendation["decision"]["adoptable"],
                "output_json": args.output_json,
                "output_md": args.output_md,
                "output_set": args.output_set,
                "set_metadata": set_metadata,
                "reasons": recommendation["decision"]["reasons"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if recommendation["decision"]["adoptable"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
