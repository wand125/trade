#!/usr/bin/env python3
"""Build and audit short replacement-risk targets from model-trade-delta output."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


DEFAULT_WINDOWS = (
    "all_2025_01_12:2025-01:2025-12",
    "late_2025_08_12:2025-08:2025-12",
    "late_2025_09_12:2025-09:2025-12",
)
NUMERIC_COLUMNS = (
    "candidate_adjusted_pnl",
    "pred_taken_ev",
    "pred_best_ev",
    "pred_opposite_ev",
    "pred_side_confidence_gap",
    "pred_taken_entry_local_rank",
    "pred_taken_wait_regret",
    "pred_taken_max_adverse_pnl",
    "pred_taken_profit_barrier_hit",
    "pred_taken_side_confidence",
    "pred_opposite_side_confidence",
    "candidate_holding_minutes",
    "candidate_blocked_base_count",
    "candidate_blocked_base_adjusted_pnl",
    "candidate_stateful_net_adjusted_pnl",
    "candidate_stateful_positive_cost_adjusted_pnl",
)
BOOL_COLUMNS = (
    "is_loss",
    "is_win",
    "is_forced_exit",
    "direction_error",
    "predicted_side_error",
    "predicted_side_matches_trade",
    "actual_side_matches_trade",
)
TOP_COLUMNS = (
    "candidate",
    "window",
    "month",
    "entry_decision_timestamp",
    "direction",
    "delta_status",
    "candidate_adjusted_pnl",
    "replacement_large_loss",
    "combined_regime",
    "session_regime",
    "candidate_exit_reason",
    "pred_taken_ev",
    "pred_side_confidence_gap",
    "pred_taken_entry_local_rank",
    "pred_taken_wait_regret",
    "pred_taken_max_adverse_pnl",
    "pred_taken_profit_barrier_hit",
    "predicted_best_side",
    "actual_best_side",
    "direction_error",
    "candidate_stateful_net_adjusted_pnl",
)


@dataclass(frozen=True)
class NamedPath:
    name: str
    path: Path


@dataclass(frozen=True)
class MonthWindow:
    name: str
    start_month: str
    end_month: str


def parse_named_path(value: str) -> NamedPath:
    if "=" not in value:
        raise argparse.ArgumentTypeError("delta run must be formatted as name=path")
    name, path_text = value.split("=", 1)
    name = name.strip()
    path_text = path_text.strip()
    if not name:
        raise argparse.ArgumentTypeError("delta run name is empty")
    if not path_text:
        raise argparse.ArgumentTypeError("delta run path is empty")
    return NamedPath(name=name, path=Path(path_text))


def parse_window(value: str) -> MonthWindow:
    parts = [part.strip() for part in value.split(":")]
    if len(parts) != 3:
        raise argparse.ArgumentTypeError("window must be formatted as name:start_month:end_month")
    if not all(parts):
        raise argparse.ArgumentTypeError("window parts must be non-empty")
    return MonthWindow(name=parts[0], start_month=parts[1], end_month=parts[2])


def local_json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, NamedPath):
        return {"name": value.name, "path": value.path}
    if isinstance(value, MonthWindow):
        return {
            "name": value.name,
            "start_month": value.start_month,
            "end_month": value.end_month,
        }
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    raise TypeError(f"cannot serialize {type(value).__name__}")


def to_bool_series(series: pd.Series) -> pd.Series:
    def convert(value: Any) -> bool:
        if pd.isna(value):
            return False
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "t", "yes", "y"}
        return bool(value)

    return series.map(convert).astype(bool)


def delta_csv_path(path: Path) -> Path:
    if path.is_dir():
        return path / "trade_delta_rows.csv"
    return path


def load_delta(named_path: NamedPath) -> pd.DataFrame:
    source = delta_csv_path(named_path.path)
    if not source.exists():
        raise FileNotFoundError(f"trade delta csv not found: {source}")
    frame = pd.read_csv(source)
    required = {"month", "direction", "delta_status", "candidate_adjusted_pnl"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"{source} missing columns: {', '.join(missing)}")
    output = frame.copy()
    output["candidate"] = named_path.name
    output["source_path"] = str(source)
    output["month"] = output["month"].astype(str)
    output["direction"] = output["direction"].astype(str)
    output["delta_status"] = output["delta_status"].astype(str)
    return output


def normalize_rows(frame: pd.DataFrame) -> pd.DataFrame:
    output = frame.copy()
    for column in NUMERIC_COLUMNS:
        if column in output.columns:
            output[column] = pd.to_numeric(output[column], errors="coerce")
    for column in BOOL_COLUMNS:
        if column in output.columns:
            output[column] = to_bool_series(output[column])
    for column in ["combined_regime", "session_regime", "candidate_exit_reason"]:
        if column not in output.columns:
            output[column] = "unknown"
        output[column] = output[column].fillna("unknown").astype(str)
    return output


def add_replacement_targets(rows: pd.DataFrame, *, large_loss_threshold: float) -> pd.DataFrame:
    output = normalize_rows(rows)
    output["replacement_pnl"] = output["candidate_adjusted_pnl"].astype(float)
    output["replacement_is_loss"] = output["replacement_pnl"].lt(0.0)
    output["replacement_is_win"] = output["replacement_pnl"].gt(0.0)
    output["replacement_large_loss"] = output["replacement_pnl"].le(-large_loss_threshold)
    if "pred_taken_ev" in output.columns:
        output["replacement_ev_overestimate_vs_pnl"] = (
            output["pred_taken_ev"] - output["replacement_pnl"]
        )
    else:
        output["replacement_ev_overestimate_vs_pnl"] = np.nan
    return output


def replacement_examples(
    frame: pd.DataFrame,
    *,
    window: MonthWindow,
    direction: str,
    delta_status: str,
    large_loss_threshold: float,
) -> pd.DataFrame:
    data = add_replacement_targets(frame, large_loss_threshold=large_loss_threshold)
    mask = (
        data["month"].ge(window.start_month)
        & data["month"].le(window.end_month)
        & data["direction"].eq(direction)
        & data["delta_status"].eq(delta_status)
    )
    rows = data.loc[mask].copy()
    rows["window"] = window.name
    rows["window_start_month"] = window.start_month
    rows["window_end_month"] = window.end_month
    return rows


def bool_sum(series: pd.Series) -> int:
    return int(to_bool_series(series).sum())


def negative_pnl_sum(series: pd.Series) -> float:
    values = pd.to_numeric(series, errors="coerce")
    return float(values[values < 0].sum())


def positive_pnl_sum(series: pd.Series) -> float:
    values = pd.to_numeric(series, errors="coerce")
    return float(values[values > 0].sum())


def target_summary(rows: pd.DataFrame) -> pd.DataFrame:
    if rows.empty:
        return pd.DataFrame()
    return (
        rows.groupby(["candidate", "window"], dropna=False)
        .agg(
            rows=("replacement_pnl", "size"),
            total_pnl=("replacement_pnl", "sum"),
            loss_count=("replacement_is_loss", bool_sum),
            large_loss_count=("replacement_large_loss", bool_sum),
            win_count=("replacement_is_win", bool_sum),
            loss_pnl=("replacement_pnl", negative_pnl_sum),
            win_pnl=("replacement_pnl", positive_pnl_sum),
            mean_pnl=("replacement_pnl", "mean"),
            median_pnl=("replacement_pnl", "median"),
            worst_trade_pnl=("replacement_pnl", "min"),
            best_trade_pnl=("replacement_pnl", "max"),
            mean_pred_taken_ev=("pred_taken_ev", "mean"),
            mean_entry_rank=("pred_taken_entry_local_rank", "mean"),
            mean_side_gap=("pred_side_confidence_gap", "mean"),
            mean_ev_overestimate=("replacement_ev_overestimate_vs_pnl", "mean"),
        )
        .reset_index()
        .sort_values(["candidate", "window"])
    )


def grouped_summary(rows: pd.DataFrame, group_columns: list[str]) -> pd.DataFrame:
    if rows.empty:
        return pd.DataFrame()
    data = rows.copy()
    for column in group_columns:
        if column not in data.columns:
            data[column] = "unknown"
        data[column] = data[column].fillna("unknown").astype(str)
    return (
        data.groupby(["candidate", "window", *group_columns], dropna=False)
        .agg(
            rows=("replacement_pnl", "size"),
            total_pnl=("replacement_pnl", "sum"),
            loss_count=("replacement_is_loss", bool_sum),
            large_loss_count=("replacement_large_loss", bool_sum),
            loss_pnl=("replacement_pnl", negative_pnl_sum),
            win_pnl=("replacement_pnl", positive_pnl_sum),
            mean_pnl=("replacement_pnl", "mean"),
            worst_trade_pnl=("replacement_pnl", "min"),
            mean_entry_rank=("pred_taken_entry_local_rank", "mean"),
            mean_side_gap=("pred_side_confidence_gap", "mean"),
            mean_pred_taken_ev=("pred_taken_ev", "mean"),
        )
        .reset_index()
        .sort_values(["candidate", "window", "total_pnl", "rows"])
    )


def condition_masks(rows: pd.DataFrame) -> dict[str, pd.Series]:
    data = rows
    false = pd.Series(False, index=data.index)

    def numeric(column: str) -> pd.Series:
        if column not in data.columns:
            return pd.Series(np.nan, index=data.index)
        return pd.to_numeric(data[column], errors="coerce")

    entry_rank = numeric("pred_taken_entry_local_rank")
    side_gap = numeric("pred_side_confidence_gap")
    wait_regret = numeric("pred_taken_wait_regret")
    pred_ev = numeric("pred_taken_ev")
    profit_hit = numeric("pred_taken_profit_barrier_hit")
    max_adverse = numeric("pred_taken_max_adverse_pnl")
    blocked_base_count = numeric("candidate_blocked_base_count")

    masks = {
        "entry_rank_ge0p52": entry_rank.ge(0.52),
        "entry_rank_ge0p53": entry_rank.ge(0.53),
        "entry_rank_ge0p54": entry_rank.ge(0.54),
        "entry_rank_ge0p55": entry_rank.ge(0.55),
        "side_gap_le0": side_gap.le(0.0),
        "side_gap_le_m0p05": side_gap.le(-0.05),
        "wait_regret_ge4": wait_regret.ge(4.0),
        "pred_ev_lt15": pred_ev.lt(15.0),
        "pred_ev_lt20": pred_ev.lt(20.0),
        "profit_hit_lt0p5": profit_hit.lt(0.5),
        "max_adverse_le_m15": max_adverse.le(-15.0),
        "blocked_base_count_ge1": blocked_base_count.ge(1.0),
    }
    if "combined_regime" in data.columns and "session_regime" in data.columns:
        focus = data["combined_regime"].eq("range_low_vol") & data["session_regime"].eq(
            "ny_overlap"
        )
        masks["focus_range_low_ny_overlap"] = focus
        masks["focus_rank_ge0p53"] = focus & entry_rank.ge(0.53)
        masks["focus_side_gap_le0"] = focus & side_gap.le(0.0)
    else:
        masks["focus_range_low_ny_overlap"] = false
        masks["focus_rank_ge0p53"] = false
        masks["focus_side_gap_le0"] = false
    return {name: mask.fillna(False).astype(bool) for name, mask in masks.items()}


def condition_summary(rows: pd.DataFrame) -> pd.DataFrame:
    if rows.empty:
        return pd.DataFrame()
    summaries: list[dict[str, Any]] = []
    for (candidate, window), group in rows.groupby(["candidate", "window"], dropna=False):
        total_pnl = float(group["replacement_pnl"].sum())
        total_loss_pnl = negative_pnl_sum(group["replacement_pnl"])
        total_loss_count = bool_sum(group["replacement_is_loss"])
        total_large_loss_count = bool_sum(group["replacement_large_loss"])
        for condition, mask in condition_masks(group).items():
            covered = group[mask]
            uncovered = group[~mask]
            covered_pnl = float(covered["replacement_pnl"].sum())
            covered_loss_pnl = negative_pnl_sum(covered["replacement_pnl"])
            summaries.append(
                {
                    "candidate": candidate,
                    "window": window,
                    "condition": condition,
                    "total_rows": len(group),
                    "total_pnl": total_pnl,
                    "total_loss_count": total_loss_count,
                    "total_large_loss_count": total_large_loss_count,
                    "total_loss_pnl": total_loss_pnl,
                    "covered_rows": len(covered),
                    "covered_pnl": covered_pnl,
                    "covered_loss_count": bool_sum(covered["replacement_is_loss"]),
                    "covered_large_loss_count": bool_sum(covered["replacement_large_loss"]),
                    "covered_loss_pnl": covered_loss_pnl,
                    "uncovered_rows": len(uncovered),
                    "uncovered_pnl": float(uncovered["replacement_pnl"].sum()),
                    "uncovered_loss_count": bool_sum(uncovered["replacement_is_loss"]),
                    "uncovered_large_loss_count": bool_sum(uncovered["replacement_large_loss"]),
                    "uncovered_loss_pnl": negative_pnl_sum(uncovered["replacement_pnl"]),
                    "delta_if_block_covered": -covered_pnl,
                    "loss_pnl_coverage": (
                        covered_loss_pnl / total_loss_pnl if total_loss_pnl < 0 else np.nan
                    ),
                }
            )
    return pd.DataFrame(summaries).sort_values(
        ["candidate", "window", "delta_if_block_covered"],
        ascending=[True, True, False],
    )


def top_bad_replacements(rows: pd.DataFrame, top_n: int) -> pd.DataFrame:
    if rows.empty:
        return pd.DataFrame()
    columns = [column for column in TOP_COLUMNS if column in rows.columns]
    return rows.sort_values("replacement_pnl", ascending=True)[columns].head(top_n)


def run_diagnostics(args: argparse.Namespace) -> Path:
    args.output_dir.mkdir(parents=True, exist_ok=True)
    run_dir = args.output_dir / args.label
    suffix = 0
    while run_dir.exists():
        suffix += 1
        run_dir = args.output_dir / f"{args.label}_{suffix}"
    run_dir.mkdir(parents=True)

    frames = [load_delta(delta_run) for delta_run in args.delta_runs]
    examples: list[pd.DataFrame] = []
    for frame in frames:
        for window in args.windows:
            examples.append(
                replacement_examples(
                    frame,
                    window=window,
                    direction=args.direction,
                    delta_status=args.delta_status,
                    large_loss_threshold=args.large_loss_threshold,
                )
            )
    rows = pd.concat(examples, ignore_index=True, sort=False) if examples else pd.DataFrame()

    targets = target_summary(rows)
    conditions = condition_summary(rows)
    by_month = grouped_summary(rows, ["month"])
    by_context = grouped_summary(rows, ["combined_regime", "session_regime"])
    top_bad = top_bad_replacements(rows, args.top_n)

    rows.to_csv(run_dir / "replacement_risk_examples.csv", index=False)
    targets.to_csv(run_dir / "target_summary.csv", index=False)
    conditions.to_csv(run_dir / "condition_summary.csv", index=False)
    by_month.to_csv(run_dir / "by_month.csv", index=False)
    by_context.to_csv(run_dir / "by_regime_session.csv", index=False)
    top_bad.to_csv(run_dir / "top_bad_replacements.csv", index=False)
    metadata = {
        "delta_runs": args.delta_runs,
        "windows": args.windows,
        "direction": args.direction,
        "delta_status": args.delta_status,
        "large_loss_threshold": args.large_loss_threshold,
        "top_n": args.top_n,
    }
    (run_dir / "config.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, default=local_json_default) + "\n",
        encoding="utf-8",
    )
    if targets.empty:
        print("no replacement risk examples")
    else:
        print(targets.to_string(index=False))
        print("\ncondition summary:")
        print(conditions.head(args.print_rows).to_string(index=False))
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--delta-run", dest="delta_runs", action="append", type=parse_named_path, required=True)
    parser.add_argument("--window", dest="windows", action="append", type=parse_window)
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="short_replacement_risk_target_diagnostics")
    parser.add_argument("--direction", default="short")
    parser.add_argument("--delta-status", default="only_candidate")
    parser.add_argument("--large-loss-threshold", type=float, default=10.0)
    parser.add_argument("--top-n", type=int, default=40)
    parser.add_argument("--print-rows", type=int, default=80)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.windows is None:
        args.windows = [parse_window(value) for value in DEFAULT_WINDOWS]
    run_diagnostics(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
