from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analysis.market_data import TIME_FORMAT
from analysis.mt5_optimization_recommend import estimate_set_passes, numeric_set_value


SET_LINE_RE = re.compile(r"^([^=;#\s][^=]*)=(.*)$")

SCORE_WEIGHT_INPUT_GROUPS: dict[str, tuple[str, ...]] = {
    "trend": (
        "InpScoreTrendM30",
        "InpScoreTrendM15",
        "InpScoreTrendSlope",
        "InpScoreTrendM5",
        "InpScoreRsiM5",
    ),
    "structure": ("InpScoreSwingReversal",),
    "entry": ("InpScoreRsiTurn", "InpScoreBreakConfirm"),
    "risk": ("InpScoreRiskPlan",),
}
PENALTY_INPUTS = ("InpScoreRiskPenalty",)
SAFETY_INPUTS = {
    "InpSignalOnly": "true||false||0||true||N",
    "InpEnableTrading": "false||false||0||true||N",
    "InpAllowLiveTrading": "false||false||0||true||N",
    "InpRequireStrategyTester": "true||false||0||true||N",
    "InpChartButtonDryRunOnly": "true||false||0||true||N",
    "InpAllowChartButtonTrading": "false||false||0||true||N",
}


def generate_score_weight_set(
    template_text: str,
    weight_search_report: dict[str, Any],
    *,
    side: str = "auto",
    allow_failed_walk_forward: bool = False,
) -> tuple[str, dict[str, Any]]:
    top = weight_search_report.get("top_weight_candidate")
    if not isinstance(top, dict) or not top:
        metadata = score_weight_set_metadata(
            weight_search_report,
            side=side,
            can_write=False,
            skip_reason="missing_top_weight_candidate",
        )
        return template_text, metadata

    resolved_side = resolve_side(side, top)
    walk_forward = weight_search_report.get("walk_forward")
    wf_aggregate = walk_forward.get("aggregate") if isinstance(walk_forward, dict) else {}
    wf_status = str(wf_aggregate.get("status") or "") if isinstance(wf_aggregate, dict) else ""
    can_write = wf_status == "walk_forward_candidate_passed" or allow_failed_walk_forward
    skip_reason = "" if can_write else "walk_forward_not_passed"
    updates, mapping_rows = score_weight_set_updates(template_text, top, resolved_side)
    metadata = score_weight_set_metadata(
        weight_search_report,
        side=resolved_side,
        can_write=can_write,
        skip_reason=skip_reason,
        updates=updates,
        mapping_rows=mapping_rows,
        allow_failed_walk_forward=allow_failed_walk_forward,
    )
    if not can_write:
        return template_text, metadata
    rendered = apply_score_weight_updates(template_text, updates, metadata)
    metadata.update(estimate_set_passes(rendered))
    rendered = apply_score_weight_updates(template_text, updates, metadata)
    return rendered, metadata


def score_weight_set_updates(
    template_text: str,
    top: dict[str, Any],
    side: str,
) -> tuple[dict[str, str], list[dict[str, Any]]]:
    current_inputs = parse_set_current_inputs(template_text)
    updates: dict[str, str] = dict(SAFETY_INPUTS)
    mapping_rows: list[dict[str, Any]] = []

    if side in {"buy", "sell"}:
        updates["InpEnableBuy"] = bool_set_value(side == "buy")
        updates["InpEnableSell"] = bool_set_value(side == "sell")

    if numeric_value_present(top.get("threshold")):
        threshold = float(top["threshold"])
        updates["InpMinScore"] = fixed_numeric_set_value(threshold)
        mapping_rows.append(
            {
                "input": "InpMinScore",
                "group": "threshold",
                "base": current_inputs.get("InpMinScore"),
                "weight": "",
                "value": threshold,
            }
        )

    for group, input_names in SCORE_WEIGHT_INPUT_GROUPS.items():
        weight = float(top.get(f"{group}_w", 1.0) or 1.0)
        for input_name in input_names:
            base = current_inputs.get(input_name)
            if not numeric_value_present(base):
                continue
            value = scale_score_value(float(base), weight)
            updates[input_name] = fixed_numeric_set_value(value)
            mapping_rows.append(
                {
                    "input": input_name,
                    "group": group,
                    "base": base,
                    "weight": weight,
                    "value": value,
                }
            )

    penalty_weight = max(float(top.get("cost_w", 1.0) or 1.0), float(top.get("chop_w", 1.0) or 1.0))
    for input_name in PENALTY_INPUTS:
        base = current_inputs.get(input_name)
        if not numeric_value_present(base):
            continue
        value = scale_score_value(float(base), penalty_weight)
        updates[input_name] = fixed_numeric_set_value(value)
        mapping_rows.append(
            {
                "input": input_name,
                "group": "penalty",
                "base": base,
                "weight": penalty_weight,
                "value": value,
            }
        )
    return updates, mapping_rows


def score_weight_set_metadata(
    weight_search_report: dict[str, Any],
    *,
    side: str,
    can_write: bool,
    skip_reason: str,
    updates: dict[str, str] | None = None,
    mapping_rows: list[dict[str, Any]] | None = None,
    allow_failed_walk_forward: bool = False,
) -> dict[str, Any]:
    walk_forward = weight_search_report.get("walk_forward")
    aggregate = walk_forward.get("aggregate") if isinstance(walk_forward, dict) else {}
    top = weight_search_report.get("top_weight_candidate")
    follow_up = score_weight_follow_up_metadata(
        side=side,
        can_write=can_write,
        skip_reason=skip_reason,
        walk_forward_aggregate=aggregate if isinstance(aggregate, dict) else {},
        top_weight_candidate=top if isinstance(top, dict) else {},
        regime_search=weight_search_report.get("regime_search")
        if isinstance(weight_search_report.get("regime_search"), dict)
        else {},
    )
    metadata = {
        "generated_at": datetime.now().strftime(TIME_FORMAT),
        "source_generated_at": weight_search_report.get("generated_at", ""),
        "focus_side": side,
        "can_write": can_write,
        "skipped_write": not can_write,
        "skip_reason": skip_reason,
        "allow_failed_walk_forward": allow_failed_walk_forward,
        "walk_forward_status": aggregate.get("status", "") if isinstance(aggregate, dict) else "",
        "top_weight_candidate": top if isinstance(top, dict) else {},
        "updates": updates or {},
        "mapping": mapping_rows or [],
        "follow_up": follow_up,
    }
    metadata["decision"] = score_weight_set_decision_summary(metadata)
    return metadata


def score_weight_set_decision_summary(metadata: dict[str, Any]) -> dict[str, Any]:
    follow_up = metadata.get("follow_up") if isinstance(metadata.get("follow_up"), dict) else {}
    top = (
        metadata.get("top_weight_candidate")
        if isinstance(metadata.get("top_weight_candidate"), dict)
        else {}
    )
    return {
        "status": follow_up.get("status", ""),
        "adoptable": bool(metadata.get("can_write")),
        "write_allowed": bool(metadata.get("can_write")),
        "written": bool(metadata.get("written", False)),
        "skipped_write": bool(metadata.get("skipped_write", False)),
        "skip_reason": metadata.get("skip_reason", ""),
        "focus_side": metadata.get("focus_side", ""),
        "output_set": metadata.get("output_set", ""),
        "walk_forward_status": metadata.get("walk_forward_status", ""),
        "failure_mode": follow_up.get("failure_mode", ""),
        "sample_shortage": follow_up.get("sample_shortage", ""),
        "do_not_repeat_set_conversion": follow_up.get("do_not_repeat_set_conversion", ""),
        "next_action": follow_up.get("next_action", ""),
        "reason": follow_up.get("reason", ""),
        "top_candidate": {
            "side": top.get("side", ""),
            "threshold": top.get("threshold", ""),
            "weights": top.get("weights", ""),
            "count": top.get("count", ""),
            "avg_r": top.get("avg_r", ""),
            "pf": top.get("pf", ""),
            "total_r": top.get("total_r", ""),
        },
        "regime_candidate": {
            "status": follow_up.get("regime_status", ""),
            "dimension": follow_up.get("regime_dimension", ""),
            "group": follow_up.get("regime_group", ""),
            "sample_shortage": follow_up.get("regime_sample_shortage", ""),
            "missing_test_weight_count": follow_up.get("regime_missing_test_weight_count", ""),
            "required_test_weight_count": follow_up.get("regime_required_test_weight_count", ""),
        },
    }


def score_weight_follow_up_metadata(
    *,
    side: str,
    can_write: bool,
    skip_reason: str,
    walk_forward_aggregate: dict[str, Any],
    top_weight_candidate: dict[str, Any],
    regime_search: dict[str, Any] | None = None,
) -> dict[str, Any]:
    resolved_side = side if side in {"buy", "sell"} else str(top_weight_candidate.get("side") or side)
    if resolved_side not in {"buy", "sell"}:
        resolved_side = "sell"
    suffix = "_buy" if resolved_side == "buy" else ""
    regime_summary = score_weight_regime_follow_up_summary(regime_search or {})
    failure_mode = score_weight_failure_mode(
        can_write=can_write,
        skip_reason=skip_reason,
        walk_forward_aggregate=walk_forward_aggregate,
        regime_summary=regime_summary,
    )
    sample_shortage = (
        failure_mode == "walk_forward_sample_shortage"
        or bool(regime_summary.get("regime_sample_shortage"))
    )
    if can_write:
        status = "ready_for_mt5_validation_set"
        next_action = "run_mt5_score_weight_refit_validation"
        reason = "walk_forward_candidate_passed"
    elif skip_reason == "walk_forward_not_passed":
        status = "collect_diagnostic_samples"
        next_action = "run_score_weight_sample_collection_before_retrying_set_conversion"
        reason = "walk_forward did not beat baseline; do not write the score-weight set yet"
    else:
        status = "rerun_score_weight_search"
        next_action = "rerun_weight_search_before_set_conversion"
        reason = skip_reason or "score_weight_set_not_writable"
    sample_collection_command = (
        "python3 methods/swing_eval/analysis/mt5_next_action_run.py "
        "--target score_weight_sample_collection "
        f"--execute --refresh-ready-status --focus-side {resolved_side} "
        "--max-ready-status-age-seconds 600 "
        f"--output-json runtime/latest_mt5_next_action_run{suffix}.json "
        f"--output-md runtime/latest_mt5_next_action_run{suffix}.md"
    )
    collect_command = (
        "python3 methods/swing_eval/analysis/mt5_tester_run.py "
        "--config methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_sample_collection.ini "
        f"--report-name 'Tester\\Swing_Evaluation_Trader_sample_collection_{resolved_side}' "
        "--timeout-seconds 7200 --since-minutes 240 --sync-expert-parameters-set "
        f"--min-closed 100 --focus-side {resolved_side} --no-recommendation "
        f"--output-json runtime/latest_mt5_tester_sample_collection_{resolved_side}_run.json "
        f"--output-md runtime/latest_mt5_tester_sample_collection_{resolved_side}_run.md "
        f"--optimization-output-json runtime/latest_mt5_sample_collection_{resolved_side}_report.json "
        f"--optimization-output-md runtime/latest_mt5_sample_collection_{resolved_side}_report.md "
        "--collect-only"
    )
    return {
        "status": status,
        "next_action": next_action,
        "reason": reason,
        "side": resolved_side,
        "failure_mode": failure_mode,
        "sample_shortage": sample_shortage,
        "do_not_repeat_set_conversion": not can_write,
        "walk_forward_status": walk_forward_aggregate.get("status", ""),
        "walk_forward_delta_total_r": walk_forward_aggregate.get("delta_total_r", ""),
        "walk_forward_delta_mean_avg_r": walk_forward_aggregate.get("delta_mean_avg_r", ""),
        "walk_forward_delta_mean_pf": walk_forward_aggregate.get("delta_mean_pf", ""),
        "walk_forward_total_test_weight_r": walk_forward_aggregate.get("total_test_weight_r", ""),
        "walk_forward_total_test_baseline_r": walk_forward_aggregate.get("total_test_baseline_r", ""),
        "walk_forward_mean_test_weight_avg_r": walk_forward_aggregate.get(
            "mean_test_weight_avg_r", ""
        ),
        "walk_forward_mean_test_baseline_avg_r": walk_forward_aggregate.get(
            "mean_test_baseline_avg_r", ""
        ),
        "walk_forward_mean_test_weight_pf": walk_forward_aggregate.get(
            "mean_test_weight_pf", ""
        ),
        "walk_forward_mean_test_baseline_pf": walk_forward_aggregate.get(
            "mean_test_baseline_pf", ""
        ),
        "walk_forward_folds": walk_forward_aggregate.get("folds", ""),
        "walk_forward_folds_with_weight_trades": walk_forward_aggregate.get(
            "folds_with_weight_trades", ""
        ),
        "walk_forward_required_folds_with_weight_trades": walk_forward_aggregate.get(
            "required_folds_with_weight_trades", ""
        ),
        "walk_forward_missing_folds_with_weight_trades": walk_forward_aggregate.get(
            "missing_folds_with_weight_trades", ""
        ),
        "walk_forward_total_test_weight_count": walk_forward_aggregate.get("total_test_weight_count", ""),
        "walk_forward_required_test_weight_count": walk_forward_aggregate.get("required_test_weight_count", ""),
        "walk_forward_missing_test_weight_count": walk_forward_aggregate.get("missing_test_weight_count", ""),
        "top_candidate_threshold": top_weight_candidate.get("threshold", ""),
        "top_candidate_weights": top_weight_candidate.get("weights", ""),
        "top_candidate_count": top_weight_candidate.get("count", ""),
        "top_candidate_avg_r": top_weight_candidate.get("avg_r", ""),
        "top_candidate_pf": top_weight_candidate.get("pf", ""),
        "top_candidate_total_r": top_weight_candidate.get("total_r", ""),
        **regime_summary,
        "history_status_command": (
            "python3 methods/swing_eval/analysis/history_status.py "
            "--history runtime/latest_history_168h.json "
            "--done runtime/history_request.done.json "
            "--output-json runtime/latest_history_status.json "
            "--output-md runtime/latest_history_status.md"
        ),
        "sample_collection_command": sample_collection_command,
        "collect_command": collect_command,
    }


def score_weight_failure_mode(
    *,
    can_write: bool,
    skip_reason: str,
    walk_forward_aggregate: dict[str, Any],
    regime_summary: dict[str, Any],
) -> str:
    if can_write:
        return "walk_forward_candidate_passed"
    if skip_reason and skip_reason != "walk_forward_not_passed":
        return skip_reason
    status = str(walk_forward_aggregate.get("status") or "")
    if status == "walk_forward_sample_shortage" or positive_number(
        walk_forward_aggregate.get("missing_test_weight_count")
    ) or positive_number(walk_forward_aggregate.get("missing_folds_with_weight_trades")):
        return "walk_forward_sample_shortage"
    if status == "walk_forward_candidate_failed" and (
        negative_number(walk_forward_aggregate.get("delta_total_r"))
        or negative_number(walk_forward_aggregate.get("delta_mean_avg_r"))
        or negative_number(walk_forward_aggregate.get("delta_mean_pf"))
    ):
        return "walk_forward_performance_regression"
    if bool(regime_summary.get("regime_sample_shortage")):
        return "regime_sample_shortage"
    return status or skip_reason or "score_weight_set_not_writable"


def score_weight_regime_follow_up_summary(regime_search: dict[str, Any]) -> dict[str, Any]:
    best = regime_search.get("best_regime_candidate")
    if not isinstance(best, dict) or not best:
        return {
            "regime_status": "",
            "regime_dimension": "",
            "regime_group": "",
            "regime_sample_shortage": False,
            "regime_missing_test_weight_count": "",
            "regime_required_test_weight_count": "",
            "regime_folds_with_weight_trades": "",
            "regime_required_folds_with_weight_trades": "",
            "regime_missing_folds_with_weight_trades": "",
        }
    walk = best.get("walk_forward") if isinstance(best.get("walk_forward"), dict) else {}
    aggregate = walk.get("aggregate") if isinstance(walk.get("aggregate"), dict) else {}
    status = str(aggregate.get("status") or "")
    missing_count = aggregate.get("missing_test_weight_count", "")
    missing_folds = aggregate.get("missing_folds_with_weight_trades", "")
    return {
        "regime_status": status,
        "regime_dimension": best.get("dimension", ""),
        "regime_group": best.get("group", ""),
        "regime_threshold": best.get("threshold", ""),
        "regime_weights": best.get("weights", ""),
        "regime_count": best.get("count", ""),
        "regime_avg_r": best.get("avg_r", ""),
        "regime_pf": best.get("pf", ""),
        "regime_total_r": best.get("total_r", ""),
        "regime_sample_shortage": status == "walk_forward_sample_shortage"
        or positive_number(missing_count)
        or positive_number(missing_folds),
        "regime_missing_test_weight_count": missing_count,
        "regime_required_test_weight_count": aggregate.get("required_test_weight_count", ""),
        "regime_folds_with_weight_trades": aggregate.get("folds_with_weight_trades", ""),
        "regime_required_folds_with_weight_trades": aggregate.get(
            "required_folds_with_weight_trades", ""
        ),
        "regime_missing_folds_with_weight_trades": missing_folds,
    }


def positive_number(value: object) -> bool:
    try:
        return float(value) > 0
    except (TypeError, ValueError):
        return False


def negative_number(value: object) -> bool:
    try:
        return float(value) < 0
    except (TypeError, ValueError):
        return False


def apply_score_weight_updates(template_text: str, updates: dict[str, str], metadata: dict[str, Any]) -> str:
    lines = template_text.splitlines()
    seen: set[str] = set()
    rendered: list[str] = [
        "; Generated from score weight search.",
        f"; Focus side: {metadata.get('focus_side')}",
        f"; Source generated at: {metadata.get('source_generated_at')}",
        f"; Walk-forward status: {metadata.get('walk_forward_status')}",
        "; This set is for MT5 validation only; Promotion Gate must still require MT5 Optimization and yearly checks.",
    ]
    pass_count = metadata.get("estimated_full_factorial_passes")
    input_count = metadata.get("optimized_input_count")
    if pass_count is not None and input_count is not None:
        rendered.append(f"; Optimized inputs: {input_count}; full-factorial passes: {pass_count}")
    for line in lines:
        match = SET_LINE_RE.match(line)
        if match and match.group(1) in updates:
            name = match.group(1)
            rendered.append(f"{name}={updates[name]}")
            seen.add(name)
        else:
            rendered.append(line)
    missing = [name for name in updates if name not in seen]
    if missing:
        rendered.extend(["", "; Added generated score weight inputs"])
        rendered.extend(f"{name}={updates[name]}" for name in missing)
    return "\n".join(rendered).rstrip() + "\n"


def write_score_weight_set(
    output_set: str | Path,
    template_set: str | Path,
    weight_search_report: dict[str, Any],
    *,
    side: str = "auto",
    allow_failed_walk_forward: bool = False,
) -> dict[str, Any]:
    template_path = Path(template_set)
    output_path = Path(output_set)
    template_text = template_path.read_text(encoding="utf-8")
    rendered, metadata = generate_score_weight_set(
        template_text,
        weight_search_report,
        side=side,
        allow_failed_walk_forward=allow_failed_walk_forward,
    )
    metadata["template_set"] = str(template_path)
    metadata["output_set"] = str(output_path)
    if metadata.get("can_write"):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered, encoding="utf-8")
        metadata["written"] = True
    else:
        metadata["written"] = False
    metadata["decision"] = score_weight_set_decision_summary(metadata)
    return metadata


def parse_set_current_inputs(set_text: str) -> dict[str, float]:
    values: dict[str, float] = {}
    for line in set_text.splitlines():
        match = SET_LINE_RE.match(line.strip())
        if not match:
            continue
        parsed = parse_current_number(match.group(2))
        if parsed is not None:
            values[match.group(1)] = parsed
    return values


def parse_current_number(value: str) -> float | None:
    current = value.split("||", 1)[0].strip()
    try:
        return float(current)
    except ValueError:
        return None


def resolve_side(side: str, top: dict[str, Any]) -> str:
    requested = side.lower()
    if requested in {"buy", "sell", "both"}:
        return requested
    candidate_side = str(top.get("side") or "").lower()
    return candidate_side if candidate_side in {"buy", "sell", "both"} else "both"


def scale_score_value(base: float, weight: float) -> int:
    return max(0, min(100, int(base * weight + 0.5)))


def fixed_numeric_set_value(value: float | int) -> str:
    return numeric_set_value(float(value), float(value), 1.0, float(value), False)


def bool_set_value(value: bool) -> str:
    return f"{'true' if value else 'false'}||false||0||true||N"


def numeric_value_present(value: object) -> bool:
    if value is None or isinstance(value, bool):
        return False
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def format_score_weight_set_markdown(metadata: dict[str, Any]) -> str:
    lines = [
        "# Score Weight Set",
        "",
        f"- Generated at: {metadata.get('generated_at', '')}",
        f"- Focus side: {metadata.get('focus_side', '')}",
        f"- Written: {metadata.get('written', False)}",
        f"- Skipped write: {metadata.get('skipped_write', '')}",
        f"- Skip reason: {metadata.get('skip_reason', '')}",
        f"- Walk-forward status: {metadata.get('walk_forward_status', '')}",
        f"- Template set: {metadata.get('template_set', '')}",
        f"- Output set: {metadata.get('output_set', '')}",
        "",
        "## Decision",
        "",
    ]
    decision = metadata.get("decision") if isinstance(metadata.get("decision"), dict) else {}
    if decision:
        lines.extend(
            [
                f"- Status: {decision.get('status', '')}",
                f"- Adoptable: {decision.get('adoptable', '')}",
                f"- Write allowed: {decision.get('write_allowed', '')}",
                f"- Written: {decision.get('written', '')}",
                f"- Next action: {decision.get('next_action', '')}",
                f"- Reason: {decision.get('reason', '')}",
                f"- Failure mode: {decision.get('failure_mode', '')}",
                f"- Sample shortage: {decision.get('sample_shortage', '')}",
                f"- Do not repeat set conversion: {decision.get('do_not_repeat_set_conversion', '')}",
                "",
            ]
        )
    lines.extend(
        [
        "## Top Weight Candidate",
        "",
        ]
    )
    top = metadata.get("top_weight_candidate")
    if isinstance(top, dict) and top:
        for key in ("side", "threshold", "weights", "count", "avg_r", "pf", "total_r", "max_drawdown_r"):
            lines.append(f"- {key}: {top.get(key, '')}")
    else:
        lines.append("- None.")
    lines.extend(["", "## Input Mapping", ""])
    mapping = metadata.get("mapping")
    if isinstance(mapping, list) and mapping:
        lines.append("| input | group | base | weight | value |")
        lines.append("|---|---|---:|---:|---:|")
        for row in mapping:
            if isinstance(row, dict):
                lines.append(
                    f"| {row.get('input', '')} | {row.get('group', '')} | "
                    f"{row.get('base', '')} | {row.get('weight', '')} | {row.get('value', '')} |"
                )
    else:
        lines.append("- None.")
    follow_up = metadata.get("follow_up") if isinstance(metadata.get("follow_up"), dict) else {}
    if follow_up:
        lines.extend(
            [
                "",
                "## Follow Up",
                "",
                f"- Status: {follow_up.get('status', '')}",
                f"- Next action: {follow_up.get('next_action', '')}",
                f"- Reason: {follow_up.get('reason', '')}",
                f"- Failure mode: {follow_up.get('failure_mode', '')}",
                f"- Sample shortage: {follow_up.get('sample_shortage', '')}",
                f"- Do not repeat set conversion: {follow_up.get('do_not_repeat_set_conversion', '')}",
                f"- Walk-forward status: {follow_up.get('walk_forward_status', '')}",
                f"- Walk-forward delta total R: {follow_up.get('walk_forward_delta_total_r', '')}",
                f"- Walk-forward delta mean avg R: {follow_up.get('walk_forward_delta_mean_avg_r', '')}",
                f"- Walk-forward delta mean PF: {follow_up.get('walk_forward_delta_mean_pf', '')}",
                f"- Walk-forward total R: {follow_up.get('walk_forward_total_test_weight_r', '')}/{follow_up.get('walk_forward_total_test_baseline_r', '')}",
                f"- Walk-forward mean avg R: {follow_up.get('walk_forward_mean_test_weight_avg_r', '')}/{follow_up.get('walk_forward_mean_test_baseline_avg_r', '')}",
                f"- Walk-forward mean PF: {follow_up.get('walk_forward_mean_test_weight_pf', '')}/{follow_up.get('walk_forward_mean_test_baseline_pf', '')}",
                f"- Walk-forward test count: {follow_up.get('walk_forward_total_test_weight_count', '')}/{follow_up.get('walk_forward_required_test_weight_count', '')}",
                f"- Walk-forward missing count: {follow_up.get('walk_forward_missing_test_weight_count', '')}",
                f"- Walk-forward folds: {follow_up.get('walk_forward_folds_with_weight_trades', '')}/{follow_up.get('walk_forward_required_folds_with_weight_trades', '')}",
                f"- Walk-forward missing folds: {follow_up.get('walk_forward_missing_folds_with_weight_trades', '')}",
                f"- Top candidate: threshold={follow_up.get('top_candidate_threshold', '')}, weights={follow_up.get('top_candidate_weights', '')}, count={follow_up.get('top_candidate_count', '')}, avg_r={follow_up.get('top_candidate_avg_r', '')}, pf={follow_up.get('top_candidate_pf', '')}, total_r={follow_up.get('top_candidate_total_r', '')}",
                f"- Regime candidate: status={follow_up.get('regime_status', '')}, dimension={follow_up.get('regime_dimension', '')}, group={follow_up.get('regime_group', '')}, shortage={follow_up.get('regime_sample_shortage', '')}, missing={follow_up.get('regime_missing_test_weight_count', '')}/{follow_up.get('regime_required_test_weight_count', '')}",
                "",
                "```bash",
                str(follow_up.get("history_status_command", "")),
                str(follow_up.get("sample_collection_command", "")),
                str(follow_up.get("collect_command", "")),
                "```",
            ]
        )
    if metadata.get("estimated_full_factorial_passes") is not None:
        lines.extend(
            [
                "",
                "## Pass Budget",
                "",
                f"- Optimized inputs: {metadata.get('optimized_input_count')}",
                f"- Full-factorial passes: {metadata.get('estimated_full_factorial_passes')}",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build an MT5 validation .set from score weight search output.")
    parser.add_argument("--weight-search-json", required=True)
    parser.add_argument("--template-set", default="methods/swing_eval/mt5/TesterSets/Swing_Evaluation_Trader_optimization.set")
    parser.add_argument("--output-set", default="runtime/Swing_Evaluation_Trader_score_weight_next.set")
    parser.add_argument("--side", choices=("auto", "buy", "sell", "both"), default="auto")
    parser.add_argument("--allow-failed-walk-forward", action="store_true")
    parser.add_argument("--output-json", default="runtime/latest_score_weight_set.json")
    parser.add_argument("--output-md", default="runtime/latest_score_weight_set.md")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    report = json.loads(Path(args.weight_search_json).read_text(encoding="utf-8"))
    metadata = write_score_weight_set(
        args.output_set,
        args.template_set,
        report,
        side=args.side,
        allow_failed_walk_forward=args.allow_failed_walk_forward,
    )
    output_json = Path(args.output_json)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps({"ok": True, **metadata}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    output_md = Path(args.output_md)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_md.write_text(format_score_weight_set_markdown(metadata), encoding="utf-8")
    print(json.dumps({"ok": True, **metadata}, ensure_ascii=False, indent=2))
    print(f"wrote {output_json}")
    print(f"wrote {output_md}")
    if metadata.get("written"):
        print(f"wrote {metadata.get('output_set')}")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
