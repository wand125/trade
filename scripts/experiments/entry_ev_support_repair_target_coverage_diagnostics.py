#!/usr/bin/env python3
"""Diagnose remaining support-repair target coverage in horizon viability outputs."""

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

from trade_data.backtest import json_default, make_run_dir  # noqa: E402


DEFAULT_HORIZONS = [60, 240, 720]
DEFAULT_TARGETS = (
    "fresh2024_validation:2024-03,"
    "fresh2024_validation:2024-11,"
    "refit2025_validation:2025-07"
)
DEFAULT_ROW_SCOPES = "available_candidates,greedy_selected"
DEFAULT_PROB_THRESHOLDS = "0.3,0.4,0.5,0.6"
DEFAULT_EV_THRESHOLDS = "-2,0,2"
DEFAULT_TAIL_PROB_THRESHOLDS = "0.3,0.5,0.7"
DEFAULT_REQUIRE_MODEL_USED = "true,false"

BASE_REQUIRED_COLUMNS = {
    "role",
    "month",
    "decision_timestamp",
    "side",
    "needed_side",
    "extra_side_needed",
    "row_scope",
    "target_fixed_best_adjusted_pnl",
    "target_fixed_best_horizon_minutes",
}


def local_json_default(value: Any) -> Any:
    try:
        return json_default(value)
    except TypeError:
        pass
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    raise TypeError(f"cannot serialize {type(value).__name__}")


def parse_csv(value: str) -> list[str]:
    return [item.strip() for item in str(value).split(",") if item.strip()]


def parse_int_csv(value: str) -> list[int]:
    return [int(item) for item in parse_csv(value)]


def parse_float_csv(value: str) -> list[float]:
    return [float(item) for item in parse_csv(value)]


def parse_bool_csv(value: str) -> list[bool]:
    output: list[bool] = []
    for item in parse_csv(value):
        lowered = item.lower()
        if lowered in {"true", "1", "yes", "y"}:
            output.append(True)
        elif lowered in {"false", "0", "no", "n"}:
            output.append(False)
        else:
            raise ValueError(f"invalid boolean value: {item}")
    return output


def parse_targets(value: str) -> list[tuple[str, str]]:
    targets: list[tuple[str, str]] = []
    for item in parse_csv(value):
        if ":" not in item:
            raise ValueError(f"target must be role:YYYY-MM: {item}")
        role, month = item.rsplit(":", 1)
        if not role or not month:
            raise ValueError(f"target must be role:YYYY-MM: {item}")
        targets.append((role, month[:7]))
    return targets


def numeric_series(frame: pd.DataFrame, column: str, default: float = np.nan) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    return (
        pd.to_numeric(frame[column], errors="coerce")
        .replace([np.inf, -np.inf], np.nan)
        .fillna(default)
        .astype(float)
    )


def bool_series(frame: pd.DataFrame, column: str, default: bool = False) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=bool)
    values = frame[column]
    if pd.api.types.is_bool_dtype(values):
        return values.fillna(default).astype(bool)
    if pd.api.types.is_numeric_dtype(values):
        return values.fillna(float(default)).astype(float).ne(0.0)
    return (
        values.fillna(str(default))
        .astype(str)
        .str.lower()
        .str.strip()
        .isin({"true", "1", "yes", "y"})
    )


def required_columns_for_horizons(horizons: list[int]) -> set[str]:
    columns = set(BASE_REQUIRED_COLUMNS)
    for horizon in horizons:
        columns.update(
            {
                f"side_fixed_{horizon}m_adjusted_pnl",
                f"pred_hv_{horizon}m_executable_prob",
                f"pred_hv_{horizon}m_pnl",
                f"pred_hv_{horizon}m_tail_loss_prob",
                f"pred_hv_{horizon}m_executable_model_used",
                f"pred_hv_{horizon}m_pnl_model_used",
                f"pred_hv_{horizon}m_tail_model_used",
            }
        )
    return columns


def normalize_predictions(frame: pd.DataFrame, *, horizons: list[int]) -> pd.DataFrame:
    missing = sorted(required_columns_for_horizons(horizons) - set(frame.columns))
    if missing:
        raise ValueError("predictions missing columns: " + ", ".join(missing))
    output = frame.copy()
    for column in ["role", "family", "side", "needed_side", "row_scope", "selection_bucket"]:
        if column in output.columns:
            output[column] = output[column].astype(str)
    output["month"] = output["month"].astype(str).str.slice(0, 7)
    output["decision_timestamp"] = pd.to_datetime(
        output["decision_timestamp"],
        utc=True,
        errors="coerce",
    )
    output["extra_side_needed"] = numeric_series(output, "extra_side_needed", default=0.0)
    output["target_fixed_best_adjusted_pnl"] = numeric_series(
        output,
        "target_fixed_best_adjusted_pnl",
    )
    output["target_fixed_best_horizon_minutes"] = numeric_series(
        output,
        "target_fixed_best_horizon_minutes",
    )
    output["stateful_available"] = bool_series(output, "stateful_available", default=False)
    output["selected_any"] = bool_series(output, "selected_any", default=False)
    output["strict_side_specific"] = bool_series(output, "strict_side_specific", default=False)
    output["relaxed_side_specific"] = bool_series(output, "relaxed_side_specific", default=False)
    output["one_failed_strict_stage"] = bool_series(
        output,
        "one_failed_strict_stage",
        default=False,
    )
    for horizon in horizons:
        for column in [
            f"side_fixed_{horizon}m_adjusted_pnl",
            f"pred_hv_{horizon}m_executable_prob",
            f"pred_hv_{horizon}m_pnl",
            f"pred_hv_{horizon}m_tail_loss_prob",
        ]:
            output[column] = numeric_series(output, column)
        for column in [
            f"pred_hv_{horizon}m_executable_model_used",
            f"pred_hv_{horizon}m_pnl_model_used",
            f"pred_hv_{horizon}m_tail_model_used",
        ]:
            output[column] = bool_series(output, column)
    return output.dropna(subset=["decision_timestamp"]).reset_index(drop=True)


def select_target_rows(
    predictions: pd.DataFrame,
    *,
    targets: list[tuple[str, str]],
    row_scopes: list[str],
    target_only: bool,
) -> pd.DataFrame:
    output = predictions.copy()
    if targets:
        target_index = pd.MultiIndex.from_tuples(targets, names=["role", "month"])
        current_index = pd.MultiIndex.from_frame(output[["role", "month"]])
        output = output[current_index.isin(target_index)].copy()
    if row_scopes:
        output = output[output["row_scope"].isin(row_scopes)].copy()
    if target_only:
        output = output[
            output["side"].eq(output["needed_side"]) & output["extra_side_needed"].gt(0.0)
        ].copy()
    return output.reset_index(drop=True)


def horizon_long_frame(rows: pd.DataFrame, *, horizons: list[int]) -> pd.DataFrame:
    output_rows: list[dict[str, Any]] = []
    metadata_columns = [
        "family",
        "role",
        "month",
        "decision_timestamp",
        "row_scope",
        "selection_bucket",
        "selected_any",
        "side",
        "needed_side",
        "extra_side_needed",
        "stateful_available",
        "strict_side_specific",
        "relaxed_side_specific",
        "one_failed_strict_stage",
        "target_fixed_best_adjusted_pnl",
        "target_fixed_best_horizon_minutes",
        "target_pnl_hurdle",
        "target_trade_count",
        "target_long_trade_count",
        "target_short_trade_count",
        "combined_regime",
        "session_regime",
        "entry_hour",
        "side_score",
        "side_margin",
        "score_pct",
        "side_margin_pct",
        "entry_rank_pct",
    ]
    available_metadata = [column for column in metadata_columns if column in rows.columns]
    for _, row in rows.iterrows():
        base = {column: row[column] for column in available_metadata}
        for horizon in horizons:
            model_used = (
                bool(row[f"pred_hv_{horizon}m_executable_model_used"])
                and bool(row[f"pred_hv_{horizon}m_pnl_model_used"])
                and bool(row[f"pred_hv_{horizon}m_tail_model_used"])
            )
            actual_pnl = float(row[f"side_fixed_{horizon}m_adjusted_pnl"])
            output_rows.append(
                {
                    **base,
                    "horizon_minutes": int(horizon),
                    "actual_pnl": actual_pnl,
                    "actual_positive": bool(actual_pnl > 0.0),
                    "target_best_horizon_match": bool(
                        int(float(row["target_fixed_best_horizon_minutes"])) == int(horizon)
                    )
                    if np.isfinite(float(row["target_fixed_best_horizon_minutes"]))
                    else False,
                    "pred_executable_prob": float(
                        row[f"pred_hv_{horizon}m_executable_prob"]
                    ),
                    "pred_pnl": float(row[f"pred_hv_{horizon}m_pnl"]),
                    "pred_tail_loss_prob": float(
                        row[f"pred_hv_{horizon}m_tail_loss_prob"]
                    ),
                    "pred_model_used": model_used,
                    "pred_executable_model_used": bool(
                        row[f"pred_hv_{horizon}m_executable_model_used"]
                    ),
                    "pred_pnl_model_used": bool(row[f"pred_hv_{horizon}m_pnl_model_used"]),
                    "pred_tail_model_used": bool(row[f"pred_hv_{horizon}m_tail_model_used"]),
                }
            )
    return pd.DataFrame(output_rows)


def greedy_nonoverlap(
    rows: pd.DataFrame,
    *,
    horizon_column: str,
    sort_column: str,
) -> pd.DataFrame:
    if rows.empty:
        return rows.copy()
    selected: list[pd.Series] = []
    ordered = rows.sort_values([sort_column, "decision_timestamp"], ascending=[False, True])
    intervals: list[tuple[pd.Timestamp, pd.Timestamp]] = []
    for _, row in ordered.iterrows():
        start = row["decision_timestamp"]
        horizon = float(row[horizon_column])
        if pd.isna(start) or not np.isfinite(horizon) or horizon <= 0:
            continue
        end = start + pd.to_timedelta(horizon, unit="m")
        if any(start < existing_end and end > existing_start for existing_start, existing_end in intervals):
            continue
        intervals.append((start, end))
        intervals.sort()
        selected.append(row)
    if not selected:
        return rows.iloc[0:0].copy()
    return pd.DataFrame(selected).reset_index(drop=True)


def summarize_target_groups(rows: pd.DataFrame, *, horizons: list[int]) -> pd.DataFrame:
    summary_rows: list[dict[str, Any]] = []
    group_columns = ["role", "month", "side", "row_scope"]
    for key, group in rows.groupby(group_columns, dropna=False):
        row = dict(zip(group_columns, key, strict=True))
        target_best = numeric_series(group, "target_fixed_best_adjusted_pnl")
        oracle_nonoverlap = greedy_nonoverlap(
            group,
            horizon_column="target_fixed_best_horizon_minutes",
            sort_column="target_fixed_best_adjusted_pnl",
        )
        row.update(
            {
                "candidate_rows": int(len(group)),
                "stateful_available_rows": int(bool_series(group, "stateful_available").sum()),
                "selected_any_rows": int(bool_series(group, "selected_any").sum()),
                "strict_side_specific_rows": int(
                    bool_series(group, "strict_side_specific").sum()
                ),
                "relaxed_side_specific_rows": int(
                    bool_series(group, "relaxed_side_specific").sum()
                ),
                "one_failed_strict_rows": int(
                    bool_series(group, "one_failed_strict_stage").sum()
                ),
                "extra_side_needed_max": int(
                    np.ceil(numeric_series(group, "extra_side_needed", default=0.0).max())
                )
                if len(group)
                else 0,
                "target_pnl_hurdle_max": float(
                    numeric_series(group, "target_pnl_hurdle", default=0.0).max()
                ),
                "fixed_best_positive_rows": int(target_best.gt(0.0).sum()),
                "fixed_best_max": float(target_best.max()) if len(group) else np.nan,
                "fixed_best_positive_sum": float(target_best[target_best.gt(0.0)].sum()),
                "fixed_best_negative_rows": int(target_best.lt(0.0).sum()),
                "oracle_nonoverlap_count": int(len(oracle_nonoverlap)),
                "oracle_nonoverlap_pnl_sum": float(
                    numeric_series(
                        oracle_nonoverlap,
                        "target_fixed_best_adjusted_pnl",
                        default=0.0,
                    ).sum()
                )
                if len(oracle_nonoverlap)
                else 0.0,
            }
        )
        for horizon in horizons:
            actual = numeric_series(group, f"side_fixed_{horizon}m_adjusted_pnl")
            row[f"fixed{horizon}_positive_rows"] = int(actual.gt(0.0).sum())
            row[f"fixed{horizon}_max"] = float(actual.max()) if len(group) else np.nan
            row[f"fixed{horizon}_positive_sum"] = float(actual[actual.gt(0.0)].sum())
            row[f"pred{horizon}_prob_max"] = float(
                numeric_series(group, f"pred_hv_{horizon}m_executable_prob").max()
            )
            row[f"pred{horizon}_pnl_max"] = float(
                numeric_series(group, f"pred_hv_{horizon}m_pnl").max()
            )
            row[f"pred{horizon}_tail_min"] = float(
                numeric_series(group, f"pred_hv_{horizon}m_tail_loss_prob").min()
            )
            row[f"pred{horizon}_model_used_rows"] = int(
                (
                    bool_series(group, f"pred_hv_{horizon}m_executable_model_used")
                    & bool_series(group, f"pred_hv_{horizon}m_pnl_model_used")
                    & bool_series(group, f"pred_hv_{horizon}m_tail_model_used")
                ).sum()
            )
        summary_rows.append(row)
    if not summary_rows:
        return pd.DataFrame()
    return pd.DataFrame(summary_rows).sort_values(
        ["role", "month", "side", "row_scope"],
        ascending=True,
    )


def best_horizon_choices(
    horizon_rows: pd.DataFrame,
    *,
    prob_threshold: float,
    ev_threshold: float,
    tail_prob_threshold: float,
    require_model_used: bool,
) -> pd.DataFrame:
    frame = horizon_rows.copy()
    frame["prob_pass"] = numeric_series(frame, "pred_executable_prob", default=0.0).ge(
        prob_threshold
    )
    frame["ev_pass"] = numeric_series(frame, "pred_pnl", default=-np.inf).ge(ev_threshold)
    frame["tail_pass"] = numeric_series(frame, "pred_tail_loss_prob", default=1.0).le(
        tail_prob_threshold
    )
    frame["model_pass"] = bool_series(frame, "pred_model_used") if require_model_used else True
    frame["gate_pass"] = (
        frame["prob_pass"] & frame["ev_pass"] & frame["tail_pass"] & frame["model_pass"]
    )
    frame["choice_score"] = numeric_series(frame, "pred_executable_prob", default=0.0) * (
        numeric_series(frame, "pred_pnl", default=np.nan)
    )
    chosen = frame[frame["gate_pass"]].copy()
    if chosen.empty:
        return chosen
    chosen = chosen.sort_values(
        ["role", "month", "side", "row_scope", "decision_timestamp", "choice_score"],
        ascending=[True, True, True, True, True, False],
    )
    chosen = chosen.drop_duplicates(
        ["role", "month", "side", "row_scope", "decision_timestamp"],
        keep="first",
    )
    return chosen.reset_index(drop=True)


def summarize_thresholds(
    horizon_rows: pd.DataFrame,
    *,
    prob_thresholds: list[float],
    ev_thresholds: list[float],
    tail_prob_thresholds: list[float],
    require_model_used_options: list[bool],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    group_columns = ["role", "month", "side", "row_scope"]
    for require_model_used in require_model_used_options:
        for prob_threshold in prob_thresholds:
            for ev_threshold in ev_thresholds:
                for tail_prob_threshold in tail_prob_thresholds:
                    frame = horizon_rows.copy()
                    frame["prob_pass"] = numeric_series(
                        frame,
                        "pred_executable_prob",
                        default=0.0,
                    ).ge(prob_threshold)
                    frame["ev_pass"] = numeric_series(frame, "pred_pnl", default=-np.inf).ge(
                        ev_threshold
                    )
                    frame["tail_pass"] = numeric_series(
                        frame,
                        "pred_tail_loss_prob",
                        default=1.0,
                    ).le(tail_prob_threshold)
                    frame["model_pass"] = (
                        bool_series(frame, "pred_model_used")
                        if require_model_used
                        else pd.Series(True, index=frame.index, dtype=bool)
                    )
                    frame["gate_pass"] = (
                        frame["prob_pass"]
                        & frame["ev_pass"]
                        & frame["tail_pass"]
                        & frame["model_pass"]
                    )
                    choices = best_horizon_choices(
                        frame,
                        prob_threshold=prob_threshold,
                        ev_threshold=ev_threshold,
                        tail_prob_threshold=tail_prob_threshold,
                        require_model_used=require_model_used,
                    )
                    for key, group in frame.groupby(group_columns, dropna=False):
                        group_key = dict(zip(group_columns, key, strict=True))
                        choice_group = choices
                        for column, value in group_key.items():
                            choice_group = choice_group[choice_group[column].eq(value)]
                        positive_actual = group["actual_positive"]
                        positive_gate = group["actual_positive"] & group["gate_pass"]
                        chosen_actual = numeric_series(choice_group, "actual_pnl", default=0.0)
                        rows.append(
                            {
                                **group_key,
                                "prob_threshold": float(prob_threshold),
                                "ev_threshold": float(ev_threshold),
                                "tail_prob_threshold": float(tail_prob_threshold),
                                "require_model_used": bool(require_model_used),
                                "row_horizon_count": int(len(group)),
                                "actual_positive_horizon_count": int(positive_actual.sum()),
                                "actual_positive_gate_pass_count": int(positive_gate.sum()),
                                "prob_pass_count": int(group["prob_pass"].sum()),
                                "ev_pass_count": int(group["ev_pass"].sum()),
                                "tail_pass_count": int(group["tail_pass"].sum()),
                                "model_pass_count": int(group["model_pass"].sum()),
                                "all_gate_pass_horizon_count": int(group["gate_pass"].sum()),
                                "choice_count": int(len(choice_group)),
                                "choice_positive_count": int(chosen_actual.gt(0.0).sum())
                                if len(choice_group)
                                else 0,
                                "choice_negative_count": int(chosen_actual.lt(0.0).sum())
                                if len(choice_group)
                                else 0,
                                "choice_actual_pnl_sum": float(chosen_actual.sum())
                                if len(choice_group)
                                else 0.0,
                                "choice_actual_pnl_max": float(chosen_actual.max())
                                if len(choice_group)
                                else np.nan,
                                "choice_actual_pnl_min": float(chosen_actual.min())
                                if len(choice_group)
                                else np.nan,
                                "choice_score_max": float(
                                    numeric_series(choice_group, "choice_score").max()
                                )
                                if len(choice_group)
                                else np.nan,
                                "positive_actual_blocked_by_prob_count": int(
                                    (positive_actual & ~group["prob_pass"]).sum()
                                ),
                                "positive_actual_blocked_by_ev_count": int(
                                    (positive_actual & ~group["ev_pass"]).sum()
                                ),
                                "positive_actual_blocked_by_tail_count": int(
                                    (positive_actual & ~group["tail_pass"]).sum()
                                ),
                                "positive_actual_blocked_by_model_count": int(
                                    (positive_actual & ~group["model_pass"]).sum()
                                ),
                            }
                        )
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(
        [
            "role",
            "month",
            "side",
            "row_scope",
            "choice_actual_pnl_sum",
            "choice_count",
        ],
        ascending=[True, True, True, True, False, False],
    )


def build_best_candidates(
    rows: pd.DataFrame,
    horizon_rows: pd.DataFrame,
    *,
    best_rows_per_group: int,
) -> pd.DataFrame:
    if rows.empty and horizon_rows.empty:
        return pd.DataFrame()
    group_columns = ["role", "month", "side", "row_scope"]
    row_best = rows.sort_values(
        [*group_columns, "target_fixed_best_adjusted_pnl"],
        ascending=[True, True, True, True, False],
    ).groupby(group_columns, dropna=False).head(best_rows_per_group)
    horizon_best = (
        horizon_rows.sort_values(
            [*group_columns, "actual_pnl"],
            ascending=[True, True, True, True, False],
        )
        .groupby(group_columns, dropna=False)
        .head(best_rows_per_group)
        if not horizon_rows.empty
        else pd.DataFrame()
    )
    row_best = row_best.copy() if not row_best.empty else pd.DataFrame()
    row_best["candidate_kind"] = "row_fixed_best"
    horizon_best = horizon_best.copy() if not horizon_best.empty else pd.DataFrame()
    horizon_best["candidate_kind"] = "horizon_actual_best"
    return pd.concat([row_best, horizon_best], ignore_index=True, sort=False)


def run_diagnostics(args: argparse.Namespace) -> Path:
    horizons = parse_int_csv(args.horizons)
    targets = parse_targets(args.targets)
    row_scopes = parse_csv(args.row_scopes)
    predictions = normalize_predictions(pd.read_csv(args.predictions), horizons=horizons)
    target_rows = select_target_rows(
        predictions,
        targets=targets,
        row_scopes=row_scopes,
        target_only=args.target_only,
    )
    horizon_rows = horizon_long_frame(target_rows, horizons=horizons)
    target_summary = summarize_target_groups(target_rows, horizons=horizons)
    threshold_summary = summarize_thresholds(
        horizon_rows,
        prob_thresholds=parse_float_csv(args.prob_thresholds),
        ev_thresholds=parse_float_csv(args.ev_thresholds),
        tail_prob_thresholds=parse_float_csv(args.tail_prob_thresholds),
        require_model_used_options=parse_bool_csv(args.require_model_used),
    )
    best_candidates = build_best_candidates(
        target_rows,
        horizon_rows,
        best_rows_per_group=args.best_rows_per_group,
    )

    run_dir = make_run_dir(args.output_dir, args.label)
    target_summary.to_csv(run_dir / "support_repair_target_coverage_summary.csv", index=False)
    threshold_summary.to_csv(
        run_dir / "support_repair_target_threshold_coverage.csv",
        index=False,
    )
    horizon_rows.to_csv(run_dir / "support_repair_target_horizon_rows.csv", index=False)
    best_candidates.to_csv(run_dir / "support_repair_target_best_candidates.csv", index=False)
    (run_dir / "config.json").write_text(
        json.dumps(
            {
                "predictions": args.predictions,
                "horizons": horizons,
                "targets": targets,
                "row_scopes": row_scopes,
                "target_only": args.target_only,
                "prob_thresholds": parse_float_csv(args.prob_thresholds),
                "ev_thresholds": parse_float_csv(args.ev_thresholds),
                "tail_prob_thresholds": parse_float_csv(args.tail_prob_thresholds),
                "require_model_used": parse_bool_csv(args.require_model_used),
                "best_rows_per_group": args.best_rows_per_group,
            },
            indent=2,
            default=local_json_default,
        ),
        encoding="utf-8",
    )
    print("Support repair target coverage summary:")
    print(target_summary.to_string(index=False))
    print("\nBest threshold coverage rows:")
    if threshold_summary.empty:
        print("empty threshold summary")
    else:
        print(
            threshold_summary.sort_values(
                ["choice_actual_pnl_sum", "choice_count"],
                ascending=[False, False],
            )
            .head(args.print_top)
            .to_string(index=False)
        )
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--horizons", default="60,240,720")
    parser.add_argument("--targets", default=DEFAULT_TARGETS)
    parser.add_argument("--row-scopes", default=DEFAULT_ROW_SCOPES)
    parser.add_argument("--target-only", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--prob-thresholds", default=DEFAULT_PROB_THRESHOLDS)
    parser.add_argument("--ev-thresholds", default=DEFAULT_EV_THRESHOLDS)
    parser.add_argument("--tail-prob-thresholds", default=DEFAULT_TAIL_PROB_THRESHOLDS)
    parser.add_argument("--require-model-used", default=DEFAULT_REQUIRE_MODEL_USED)
    parser.add_argument("--best-rows-per-group", type=int, default=5)
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="entry_ev_support_repair_target_coverage")
    parser.add_argument("--print-top", type=int, default=16)
    return parser


def main(argv: list[str] | None = None) -> int:
    run_diagnostics(build_parser().parse_args(argv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
