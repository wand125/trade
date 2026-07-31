#!/usr/bin/env python3
"""Audit candidate universe coverage before thin-month repair target filtering."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from trade_data.backtest import make_run_dir  # noqa: E402

from entry_ev_candidate_generation_gap_audit import parse_targets  # noqa: E402
from entry_ev_quantile_policy_backtest import policy_candidate_from_name  # noqa: E402
from entry_ev_thin_month_opposite_candidate_diagnostics import (  # noqa: E402
    SIDE_LABELS,
    TARGET_REQUIRED_COLUMNS,
    build_side_rows,
    bool_series,
    current_intervals,
    local_json_default,
    mark_stateful_available,
    month_series,
    numeric_series,
    parquet_columns,
    parse_side_penalty_rules,
    read_current_trades,
    summarize_bucket,
)


DEFAULT_TARGETS = (
    "fresh2024_validation:2024-03:long,"
    "fresh2024_validation:2024-08:long,"
    "fresh2024_validation:2024-11:long,"
    "refit2025_validation:2025-03:short,"
    "refit2025_validation:2025-07:short"
)
DEFAULT_CONFIG = (
    ROOT
    / "data/reports/backtests"
    / "20260702_111114_20260702_entry_ev_00318_thin_month_opposite_candidates_00314_w5_s2"
    / "config.json"
)


def resolve_path(value: str | Path, *, base: Path = ROOT) -> Path:
    path = Path(value)
    return path if path.is_absolute() else base / path


def role_to_family(role: str) -> str:
    text = str(role)
    for suffix in ["_validation", "_train", "_test"]:
        if text.endswith(suffix):
            return text[: -len(suffix)]
    return text


def filter_repair_targets(
    frame: pd.DataFrame,
    *,
    candidate: str,
    variant_contains: str,
    entry_block_rule: str,
) -> pd.DataFrame:
    missing = sorted(TARGET_REQUIRED_COLUMNS - set(frame.columns))
    if missing:
        raise ValueError("repair targets missing columns: " + ", ".join(missing))
    output = frame.copy()
    output["month"] = output["month"].astype(str).str.slice(0, 7)
    output = output[output["candidate"].astype(str).eq(candidate)]
    if variant_contains:
        output = output[output["variant"].astype(str).str.contains(variant_contains, regex=False)]
    if entry_block_rule:
        output = output[output["entry_block_rule"].astype(str).eq(entry_block_rule)]
    output["extra_long_needed"] = numeric_series(output, "extra_long_needed", default=0.0).astype(int)
    output["extra_short_needed"] = numeric_series(output, "extra_short_needed", default=0.0).astype(int)
    output["total_adjusted_pnl"] = numeric_series(output, "total_adjusted_pnl", default=np.nan)
    output["month_pnl_hurdle"] = numeric_series(output, "month_pnl_hurdle", default=0.0)
    return output.reset_index(drop=True)


def read_repair_targets_all(
    path: Path,
    *,
    candidate: str,
    variant_contains: str,
    entry_block_rule: str,
) -> pd.DataFrame:
    return filter_repair_targets(
        pd.read_csv(path),
        candidate=candidate,
        variant_contains=variant_contains,
        entry_block_rule=entry_block_rule,
    )


def classify_upstream_gap(row: pd.Series) -> str:
    repair_present = bool(row.get("repair_target_present", False))
    emitted_by_00318 = bool(row.get("repair_target_emitted_by_00318", False))
    month_floor_breach = bool(row.get("month_floor_breach", False))
    if not repair_present:
        return "repair_target_missing"
    if not emitted_by_00318 and month_floor_breach:
        return "repair_target_has_no_extra_side_need"
    if not emitted_by_00318:
        return "repair_target_not_emitted_no_extra_side_need"
    if int(row.get("raw_prediction_rows", 0)) == 0:
        return "no_prediction_rows"
    if int(row.get("side_rows", 0)) == 0:
        return "no_target_side_rows"
    if int(row.get("holding_ok_rows", 0)) == 0:
        return "holding_window_filtered"
    if int(row.get("candidate_rows", 0)) == 0:
        return "threshold_filtered"
    if int(row.get("candidate_available_rows", 0)) == 0:
        return "stateful_overlap_filtered"
    return "candidate_generation_possible"


def current_trade_subset(current: pd.DataFrame, *, role: str, family: str, month: str) -> pd.DataFrame:
    return current[
        current["role"].astype(str).eq(role)
        & current["family"].astype(str).eq(family)
        & current["month"].astype(str).eq(month)
    ].copy()


def summarize_current_trades(current: pd.DataFrame) -> dict[str, Any]:
    if current.empty:
        return {
            "current_trade_rows": 0,
            "current_long_rows": 0,
            "current_short_rows": 0,
            "current_adjusted_pnl_sum": 0.0,
        }
    direction = current["direction"].fillna("").astype(str) if "direction" in current.columns else pd.Series("", index=current.index)
    return {
        "current_trade_rows": int(len(current)),
        "current_long_rows": int(direction.eq("long").sum()),
        "current_short_rows": int(direction.eq("short").sum()),
        "current_adjusted_pnl_sum": float(numeric_series(current, "adjusted_pnl", default=0.0).sum()),
    }


def strict_stage_checks(
    rows: pd.DataFrame,
    *,
    policy: Any,
    min_strict_side_margin: float,
) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "holding": bool_series(rows, "holding_ok", default=False),
            "score_floor": numeric_series(rows, "side_score", default=-np.inf).gt(policy.entry_threshold),
            "score_q": numeric_series(rows, "score_pct", default=-np.inf).ge(policy.score_quantile),
            "side_margin_q": numeric_series(rows, "side_margin_pct", default=-np.inf).ge(policy.side_gap_quantile),
            "rank_q": numeric_series(rows, "entry_rank_pct", default=-np.inf).ge(policy.rank_quantile),
            "side_margin": numeric_series(rows, "side_margin", default=-np.inf).ge(min_strict_side_margin),
        },
        index=rows.index,
    )


def annotate_target_rows(
    rows: pd.DataFrame,
    *,
    role: str,
    needed_side: str,
    extra_side_needed: int,
    intervals: list[tuple[pd.Timestamp, pd.Timestamp]],
    policy: Any,
    min_strict_side_margin: float,
    relaxed_min_score: float,
    relaxed_score_quantile: float,
    relaxed_side_margin_quantile: float,
    relaxed_rank_quantile: float,
    relaxed_min_side_margin: float,
) -> pd.DataFrame:
    output = rows.copy()
    if output.empty:
        for column in [
            "role",
            "needed_side",
            "extra_side_needed",
            "strict_side_specific",
            "relaxed_side_specific",
            "strict_failed_stage_count",
            "one_failed_strict_stage",
            "stateful_available",
        ]:
            output[column] = []
        return output
    output["role"] = role
    output["needed_side"] = needed_side
    output["extra_side_needed"] = int(extra_side_needed)
    output["strict_side_specific"] = (
        output["holding_ok"]
        & output["side_score"].gt(policy.entry_threshold)
        & output["score_pct"].ge(policy.score_quantile)
        & output["side_margin_pct"].ge(policy.side_gap_quantile)
        & output["entry_rank_pct"].ge(policy.rank_quantile)
        & output["side_margin"].ge(min_strict_side_margin)
    )
    output["relaxed_side_specific"] = (
        output["holding_ok"]
        & output["side_score"].gt(relaxed_min_score)
        & output["score_pct"].ge(relaxed_score_quantile)
        & output["side_margin_pct"].ge(relaxed_side_margin_quantile)
        & output["entry_rank_pct"].ge(relaxed_rank_quantile)
        & output["side_margin"].ge(relaxed_min_side_margin)
    )
    checks = strict_stage_checks(
        output,
        policy=policy,
        min_strict_side_margin=min_strict_side_margin,
    )
    output["strict_failed_stage_count"] = (~checks).sum(axis=1).astype(int)
    output["one_failed_strict_stage"] = output["strict_failed_stage_count"].eq(1)
    return mark_stateful_available(output, intervals)


def build_target_summary_row(
    *,
    role: str,
    family: str,
    month: str,
    side: str,
    repair_row: pd.Series | None,
    raw_prediction_rows: int,
    current_trades: pd.DataFrame,
    intervals: list[tuple[pd.Timestamp, pd.Timestamp]],
    target_rows: pd.DataFrame,
) -> dict[str, Any]:
    extra_column = f"extra_{side}_needed"
    extra_side_needed = int(repair_row.get(extra_column, 0)) if repair_row is not None else 0
    total_adjusted_pnl = float(repair_row.get("total_adjusted_pnl", np.nan)) if repair_row is not None else np.nan
    month_pnl_hurdle = float(repair_row.get("month_pnl_hurdle", 0.0)) if repair_row is not None else 0.0
    candidate_mask = (
        bool_series(target_rows, "strict_side_specific")
        | bool_series(target_rows, "relaxed_side_specific")
        | bool_series(target_rows, "one_failed_strict_stage")
    )
    candidate_rows = target_rows[candidate_mask].copy()
    candidate_available = candidate_rows[bool_series(candidate_rows, "stateful_available")]
    base = {
        "role": role,
        "family": family,
        "month": month,
        "needed_side": side,
        "repair_target_present": repair_row is not None,
        "repair_target_emitted_by_00318": extra_side_needed > 0,
        "month_floor_breach": bool(
            repair_row is not None
            and (
                (np.isfinite(total_adjusted_pnl) and total_adjusted_pnl < 0.0)
                or month_pnl_hurdle > 0.0
            )
        ),
        "extra_side_needed": extra_side_needed,
        "target_total_adjusted_pnl": total_adjusted_pnl,
        "target_month_pnl_hurdle": month_pnl_hurdle,
        "target_trade_count": int(float(repair_row.get("trade_count", 0.0))) if repair_row is not None else 0,
        "target_long_trade_count": int(float(repair_row.get("long_trade_count", 0.0))) if repair_row is not None else 0,
        "target_short_trade_count": int(float(repair_row.get("short_trade_count", 0.0))) if repair_row is not None else 0,
        "current_interval_count": int(len(intervals)),
        "raw_prediction_rows": int(raw_prediction_rows),
        "side_rows": int(len(target_rows)),
        "holding_ok_rows": int(bool_series(target_rows, "holding_ok").sum()),
        "candidate_rows": int(len(candidate_rows)),
        "candidate_available_rows": int(len(candidate_available)),
        **summarize_current_trades(current_trades),
        **summarize_bucket(target_rows[bool_series(target_rows, "strict_side_specific")], "strict"),
        **summarize_bucket(target_rows[bool_series(target_rows, "relaxed_side_specific")], "relaxed"),
        **summarize_bucket(target_rows[bool_series(target_rows, "one_failed_strict_stage")], "onefail"),
    }
    base["gap_stage"] = classify_upstream_gap(pd.Series(base))
    return base


def select_repair_row(repair_targets: pd.DataFrame, *, role: str, month: str) -> pd.Series | None:
    rows = repair_targets[
        repair_targets["role"].astype(str).eq(role)
        & repair_targets["month"].astype(str).eq(month)
    ].copy()
    if rows.empty:
        return None
    rows = rows.sort_values(["role", "month", "variant", "entry_block_rule"])
    return rows.iloc[0]


def load_side_rows(
    *,
    family_predictions: dict[str, Path],
    target_months: dict[str, set[str]],
    long_column: str,
    short_column: str,
    long_holding_column: str,
    short_holding_column: str,
    min_valid_predicted_hold_minutes: float,
    max_predicted_hold_minutes: float,
    side_penalty_rules: list[tuple[str, str, str, float]],
) -> tuple[pd.DataFrame, dict[tuple[str, str], int]]:
    side_parts: list[pd.DataFrame] = []
    raw_counts: dict[tuple[str, str], int] = {}
    needed_columns = [
        "decision_timestamp",
        "entry_timestamp",
        "dataset_month",
        "month",
        "combined_regime",
        "session_regime",
        long_column,
        short_column,
        long_holding_column,
        short_holding_column,
        "pred_long_entry_local_rank",
        "pred_short_entry_local_rank",
        "long_best_adjusted_pnl",
        "short_best_adjusted_pnl",
        "long_best_holding_minutes",
        "short_best_holding_minutes",
        "long_fixed_60m_adjusted_pnl",
        "short_fixed_60m_adjusted_pnl",
        "long_fixed_240m_adjusted_pnl",
        "short_fixed_240m_adjusted_pnl",
        "long_fixed_720m_adjusted_pnl",
        "short_fixed_720m_adjusted_pnl",
        *[rule[1] for rule in side_penalty_rules],
    ]
    for family, months in sorted(target_months.items()):
        if family not in family_predictions:
            continue
        prediction_path = family_predictions[family]
        columns = parquet_columns(prediction_path)
        read_columns = [column for column in dict.fromkeys(needed_columns) if column in columns]
        predictions = pd.read_parquet(prediction_path, columns=read_columns)
        predictions["month"] = month_series(predictions)
        predictions = predictions[predictions["month"].isin(months)].copy()
        for month, group in predictions.groupby("month", sort=True):
            raw_counts[(family, str(month))] = int(len(group))
        if predictions.empty:
            continue
        side_parts.append(
            build_side_rows(
                predictions,
                family=family,
                long_column=long_column,
                short_column=short_column,
                long_holding_column=long_holding_column,
                short_holding_column=short_holding_column,
                min_valid_predicted_hold_minutes=min_valid_predicted_hold_minutes,
                max_predicted_hold_minutes=max_predicted_hold_minutes,
                side_penalty_rules=side_penalty_rules,
            )
        )
    if not side_parts:
        return pd.DataFrame(), raw_counts
    return pd.concat(side_parts, ignore_index=True), raw_counts


def run_diagnostics(args: argparse.Namespace) -> Path:
    config_path = resolve_path(args.config)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    repair_targets_path = resolve_path(config["repair_targets"])
    current_trades_path = resolve_path(config["current_trades"])
    family_predictions = {
        str(family): resolve_path(path)
        for family, path in dict(config["family_predictions"]).items()
    }
    targets = parse_targets(args.targets)
    target_months: dict[str, set[str]] = {}
    for role, month, _side in targets:
        target_months.setdefault(role_to_family(role), set()).add(month)

    policy = policy_candidate_from_name(config["candidate"])
    side_penalty_rules = parse_side_penalty_rules(config.get("side_ev_penalty_rules", ""))
    repair_targets = read_repair_targets_all(
        repair_targets_path,
        candidate=config["candidate"],
        variant_contains=config.get("variant_contains", ""),
        entry_block_rule=config.get("entry_block_rule", ""),
    )
    current = read_current_trades(
        current_trades_path,
        candidate=config["candidate"],
        selector_variant_contains=config.get("selector_variant_contains", ""),
        entry_block_rule=config.get("entry_block_rule", ""),
    )
    all_side_rows, raw_counts = load_side_rows(
        family_predictions=family_predictions,
        target_months=target_months,
        long_column=config["long_column"],
        short_column=config["short_column"],
        long_holding_column=config.get("long_holding_column", "pred_mlp_long_exit_event_minutes"),
        short_holding_column=config.get("short_holding_column", "pred_mlp_short_exit_event_minutes"),
        min_valid_predicted_hold_minutes=float(config.get("min_valid_predicted_hold_minutes", 30.0)),
        max_predicted_hold_minutes=float(config.get("max_predicted_hold_minutes", 720.0)),
        side_penalty_rules=side_penalty_rules,
    )

    summary_rows: list[dict[str, Any]] = []
    side_stage_rows: list[pd.DataFrame] = []
    example_rows: list[pd.DataFrame] = []
    current_rows: list[pd.DataFrame] = []
    for role, month, side in targets:
        if side not in SIDE_LABELS:
            raise ValueError(f"unknown target side: {side}")
        family = role_to_family(role)
        repair_row = select_repair_row(repair_targets, role=role, month=month)
        if repair_row is not None:
            family = str(repair_row.get("family", family))
        extra_side_needed = (
            int(repair_row.get(f"extra_{side}_needed", 0)) if repair_row is not None else 0
        )
        target_side_rows = (
            all_side_rows[
                all_side_rows["family"].astype(str).eq(family)
                & all_side_rows["month"].astype(str).eq(month)
                & all_side_rows["side"].astype(str).eq(side)
            ].copy()
            if not all_side_rows.empty
            else pd.DataFrame()
        )
        current_target = current_trade_subset(current, role=role, family=family, month=month)
        intervals = current_intervals(current, family=family, role=role, month=month)
        annotated = annotate_target_rows(
            target_side_rows,
            role=role,
            needed_side=side,
            extra_side_needed=extra_side_needed,
            intervals=intervals,
            policy=policy,
            min_strict_side_margin=float(config.get("min_strict_side_margin", 0.0)),
            relaxed_min_score=float(config.get("relaxed_min_score", 5.0)),
            relaxed_score_quantile=float(config.get("relaxed_score_quantile", 0.90)),
            relaxed_side_margin_quantile=float(config.get("relaxed_side_margin_quantile", 0.90)),
            relaxed_rank_quantile=float(config.get("relaxed_rank_quantile", 0.80)),
            relaxed_min_side_margin=float(config.get("relaxed_min_side_margin", 0.0)),
        )
        summary_rows.append(
            build_target_summary_row(
                role=role,
                family=family,
                month=month,
                side=side,
                repair_row=repair_row,
                raw_prediction_rows=raw_counts.get((family, month), 0),
                current_trades=current_target,
                intervals=intervals,
                target_rows=annotated,
            )
        )
        if not annotated.empty:
            candidate_mask = (
                annotated["strict_side_specific"]
                | annotated["relaxed_side_specific"]
                | annotated["one_failed_strict_stage"]
            )
            stage = annotated.copy()
            stage["candidate_row"] = candidate_mask
            side_stage_rows.append(stage)
            examples = (
                stage[candidate_mask]
                .sort_values(
                    ["side_score", "score_pct", "side_margin_pct", "entry_rank_pct"],
                    ascending=[False, False, False, False],
                )
                .head(int(args.example_rows))
            )
            if not examples.empty:
                example_rows.append(examples)
        if not current_target.empty:
            current_rows.append(current_target)

    summary_frame = pd.DataFrame(summary_rows).sort_values(["role", "month", "needed_side"])
    side_stage_frame = pd.concat(side_stage_rows, ignore_index=True) if side_stage_rows else pd.DataFrame()
    example_frame = pd.concat(example_rows, ignore_index=True) if example_rows else pd.DataFrame()
    current_frame = pd.concat(current_rows, ignore_index=True) if current_rows else pd.DataFrame()

    output_root = resolve_path(args.output_root)
    run_dir = make_run_dir(output_root, args.run_label)
    summary_frame.to_csv(run_dir / "upstream_universe_target_summary.csv", index=False)
    side_stage_frame.to_csv(run_dir / "upstream_universe_side_stage_summary.csv", index=False)
    example_frame.to_csv(run_dir / "upstream_universe_candidate_examples.csv", index=False)
    current_frame.to_csv(run_dir / "upstream_universe_current_trades.csv", index=False)
    meta = {
        "config": config_path,
        "repair_targets": repair_targets_path,
        "current_trades": current_trades_path,
        "family_predictions": family_predictions,
        "targets": targets,
        "example_rows": args.example_rows,
        "config_values": config,
    }
    (run_dir / "upstream_universe_meta.json").write_text(
        json.dumps(meta, indent=2, default=local_json_default) + "\n",
        encoding="utf-8",
    )

    print("Upstream universe coverage summary:")
    print(
        summary_frame[
            [
                "role",
                "month",
                "needed_side",
                "gap_stage",
                "repair_target_emitted_by_00318",
                "extra_side_needed",
                "raw_prediction_rows",
                "side_rows",
                "candidate_rows",
                "candidate_available_rows",
            ]
        ].to_string(index=False)
    )
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--targets", default=DEFAULT_TARGETS)
    parser.add_argument("--output-root", type=Path, default=ROOT / "data/reports/backtests")
    parser.add_argument("--run-label", default="entry_ev_upstream_universe_coverage_diagnostics")
    parser.add_argument("--example-rows", type=int, default=20)
    return parser


def main(argv: list[str] | None = None) -> int:
    run_diagnostics(build_parser().parse_args(argv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
