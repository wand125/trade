#!/usr/bin/env python3
"""Audit chronological support and horizon confidence choices for support rows."""

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
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from trade_data.backtest import json_default, make_run_dir  # noqa: E402


DEFAULT_TARGETS = (
    "fresh2024_validation:2024-03:long,"
    "fresh2024_validation:2024-08:long,"
    "fresh2024_validation:2024-11:long,"
    "refit2025_validation:2025-03:short,"
    "refit2025_validation:2025-07:short"
)
DEFAULT_ROW_SCOPES = "available_candidates,greedy_selected"
REQUIRED_COLUMNS = {
    "role",
    "month",
    "side",
    "decision_timestamp",
    "row_scope",
    "hv_chosen_horizon_minutes",
    "horizon_actual_pnl",
    "ranker_pred_pnl",
    "ranker_pred_executable_prob",
    "ranker_pred_tail_loss_prob",
    "ranker_core_model_used",
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


def parse_targets(value: str) -> list[tuple[str, str, str]]:
    targets: list[tuple[str, str, str]] = []
    for item in parse_csv(value):
        parts = item.split(":")
        if len(parts) != 3:
            raise ValueError(f"target must be role:YYYY-MM:side: {item}")
        role, month, side = parts
        targets.append((role, month[:7], side))
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


def text_series(frame: pd.DataFrame, column: str, default: str = "") -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=object)
    return frame[column].fillna(default).astype(str)


def normalize_scored_examples(frame: pd.DataFrame) -> pd.DataFrame:
    missing = sorted(REQUIRED_COLUMNS - set(frame.columns))
    if missing:
        raise ValueError("scored examples missing columns: " + ", ".join(missing))
    output = frame.copy()
    for column in ["family", "role", "side", "row_scope", "selection_bucket"]:
        output[column] = text_series(output, column)
    output["month"] = output["month"].astype(str).str.slice(0, 7)
    output["decision_timestamp"] = pd.to_datetime(
        output["decision_timestamp"],
        utc=True,
        errors="coerce",
    )
    output = output[output["decision_timestamp"].notna()].copy()
    for column in [
        "hv_chosen_horizon_minutes",
        "horizon_actual_pnl",
        "ranker_pred_pnl",
        "ranker_pred_delta_vs_60",
        "ranker_pred_executable_prob",
        "ranker_pred_tail_loss_prob",
        "ranker_pred_beats60_prob",
        "ranker_pred_harmful_overestimate_prob",
        "duration_prior_count",
        "duration_prior_months",
        "duration_prior_mean_pnl",
        "duration_prior_delta_vs_60_mean",
        "duration_prior_tail_loss_rate",
        "repair_duration_risk_score",
    ]:
        output[column] = numeric_series(output, column)
    output["ranker_core_model_used"] = bool_series(output, "ranker_core_model_used")
    output["target_key"] = (
        output["role"].astype(str)
        + "|"
        + output["month"].astype(str)
        + "|"
        + output["side"].astype(str)
    )
    output["candidate_key"] = (
        output["target_key"]
        + "|"
        + output["row_scope"].astype(str)
        + "|"
        + output["decision_timestamp"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    )
    return output.reset_index(drop=True)


def filter_targets(
    frame: pd.DataFrame,
    *,
    targets: list[tuple[str, str, str]],
    row_scopes: list[str],
) -> pd.DataFrame:
    output = frame.copy()
    if targets:
        target_index = pd.MultiIndex.from_tuples(targets, names=["role", "month", "side"])
        current_index = pd.MultiIndex.from_frame(output[["role", "month", "side"]])
        output = output[current_index.isin(target_index)].copy()
    if row_scopes:
        output = output[output["row_scope"].isin(row_scopes)].copy()
    return output.reset_index(drop=True)


def add_score_columns(
    frame: pd.DataFrame,
    *,
    tail_weight: float,
    delta_weight: float,
    beats60_weight: float,
    executable_weight: float,
) -> pd.DataFrame:
    output = frame.copy()
    pnl = numeric_series(output, "ranker_pred_pnl", default=0.0)
    tail = numeric_series(output, "ranker_pred_tail_loss_prob", default=0.0)
    delta = numeric_series(output, "ranker_pred_delta_vs_60", default=0.0).clip(lower=0.0)
    beats60 = numeric_series(output, "ranker_pred_beats60_prob", default=0.0)
    executable = numeric_series(output, "ranker_pred_executable_prob", default=0.0)
    output["score_pnl"] = pnl
    output["score_pnl_minus_tail"] = pnl - tail_weight * tail
    output["score_pnl_delta_tail"] = (
        pnl + delta_weight * delta + beats60_weight * beats60 - tail_weight * tail
    )
    output["score_executable_pnl_tail"] = (
        pnl + executable_weight * executable - tail_weight * tail
    )
    return output


def summarize_rows(frame: pd.DataFrame, *, prefix: str) -> dict[str, Any]:
    actual = numeric_series(frame, "horizon_actual_pnl", default=np.nan)
    valid = actual.notna()
    positive = actual.gt(0.0)
    tail = actual.le(-5.0)
    return {
        f"{prefix}_count": int(len(frame)),
        f"{prefix}_actual_sum": float(actual[valid].sum()) if valid.any() else 0.0,
        f"{prefix}_actual_mean": float(actual[valid].mean()) if valid.any() else np.nan,
        f"{prefix}_actual_min": float(actual[valid].min()) if valid.any() else np.nan,
        f"{prefix}_actual_max": float(actual[valid].max()) if valid.any() else np.nan,
        f"{prefix}_positive_count": int(positive.sum()),
        f"{prefix}_tail_loss_count": int(tail.sum()),
        f"{prefix}_model_used_count": int(bool_series(frame, "ranker_core_model_used").sum()),
    }


def horizon_summary(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for (target_key, scope, horizon), group in frame.groupby(
        ["target_key", "row_scope", "hv_chosen_horizon_minutes"],
        dropna=False,
        sort=True,
    ):
        row: dict[str, Any] = {
            "target_key": target_key,
            "role": group.iloc[0]["role"],
            "month": group.iloc[0]["month"],
            "side": group.iloc[0]["side"],
            "row_scope": scope,
            "horizon_minutes": int(float(horizon)),
            "decision_count": int(group["decision_timestamp"].nunique()),
        }
        row.update(summarize_rows(group, prefix="horizon"))
        for column in [
            "ranker_pred_pnl",
            "ranker_pred_executable_prob",
            "ranker_pred_tail_loss_prob",
            "duration_prior_count",
            "duration_prior_months",
            "duration_prior_mean_pnl",
            "duration_prior_tail_loss_rate",
        ]:
            row[f"{column}_mean"] = float(numeric_series(group, column).mean())
        rows.append(row)
    return pd.DataFrame(rows)


def choice_summary(frame: pd.DataFrame, *, score_columns: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    summary_rows: list[dict[str, Any]] = []
    choice_frames: list[pd.DataFrame] = []
    if frame.empty:
        return pd.DataFrame(), pd.DataFrame()

    grouped = frame.groupby(["target_key", "row_scope"], dropna=False, sort=True)
    for (target_key, scope), group in grouped:
        candidate_count = int(group["candidate_key"].nunique())
        oracle_idx = group.groupby("candidate_key")["horizon_actual_pnl"].idxmax()
        oracle = group.loc[oracle_idx].copy()
        fixed: dict[int, pd.DataFrame] = {}
        for horizon in [60, 240, 720]:
            fixed[horizon] = group[
                numeric_series(group, "hv_chosen_horizon_minutes").round().eq(horizon)
            ].copy()
        for score_column in score_columns:
            choice_idx = group.groupby("candidate_key")[score_column].idxmax()
            chosen = group.loc[choice_idx].copy()
            chosen.insert(0, "score_name", score_column)
            choice_frames.append(chosen)
            row: dict[str, Any] = {
                "target_key": target_key,
                "role": group.iloc[0]["role"],
                "month": group.iloc[0]["month"],
                "side": group.iloc[0]["side"],
                "row_scope": scope,
                "score_name": score_column,
                "candidate_count": candidate_count,
                "oracle_actual_sum": float(
                    numeric_series(oracle, "horizon_actual_pnl", default=0.0).sum()
                ),
            }
            row.update(summarize_rows(chosen, prefix="chosen"))
            for horizon, fixed_rows in fixed.items():
                row[f"fixed_{horizon}m_actual_sum"] = float(
                    numeric_series(fixed_rows, "horizon_actual_pnl", default=0.0).sum()
                )
                row[f"fixed_{horizon}m_count"] = int(len(fixed_rows))
                row[f"chosen_{horizon}m_count"] = int(
                    numeric_series(chosen, "hv_chosen_horizon_minutes").round().eq(horizon).sum()
                )
            summary_rows.append(row)
    choices = pd.concat(choice_frames, ignore_index=True, sort=False) if choice_frames else pd.DataFrame()
    return pd.DataFrame(summary_rows), choices


def fold_support_summary(fold_summary: pd.DataFrame, *, targets: list[tuple[str, str, str]]) -> pd.DataFrame:
    if fold_summary.empty:
        return pd.DataFrame()
    output = fold_summary.copy()
    output["target_month"] = output["target_month"].astype(str).str.slice(0, 7)
    months = sorted({month for _, month, _ in targets})
    output = output[output["target_month"].isin(months)].copy()
    return output.sort_values(["target_month", "target_name"]).reset_index(drop=True)


def missing_target_summary(
    frame: pd.DataFrame,
    *,
    targets: list[tuple[str, str, str]],
    row_scopes: list[str],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for role, month, side in targets:
        target_rows = frame[
            frame["role"].eq(role) & frame["month"].eq(month) & frame["side"].eq(side)
        ]
        for scope in row_scopes:
            scoped = target_rows[target_rows["row_scope"].eq(scope)]
            rows.append(
                {
                    "target_key": f"{role}|{month}|{side}",
                    "role": role,
                    "month": month,
                    "side": side,
                    "row_scope": scope,
                    "has_rows": bool(len(scoped)),
                    "row_count": int(len(scoped)),
                    "decision_count": int(scoped["decision_timestamp"].nunique())
                    if len(scoped)
                    else 0,
                }
            )
    return pd.DataFrame(rows)


def run_audit(args: argparse.Namespace) -> Path:
    targets = parse_targets(args.targets)
    row_scopes = parse_csv(args.row_scopes)
    scored = normalize_scored_examples(pd.read_csv(args.scored_examples))
    scored = add_score_columns(
        scored,
        tail_weight=args.tail_weight,
        delta_weight=args.delta_weight,
        beats60_weight=args.beats60_weight,
        executable_weight=args.executable_weight,
    )
    filtered = filter_targets(scored, targets=targets, row_scopes=row_scopes)
    score_columns = parse_csv(args.score_columns)
    horizon = horizon_summary(filtered)
    choices_summary, choices = choice_summary(filtered, score_columns=score_columns)
    missing = missing_target_summary(scored, targets=targets, row_scopes=row_scopes)
    fold = (
        fold_support_summary(pd.read_csv(args.fold_summary), targets=targets)
        if args.fold_summary
        else pd.DataFrame()
    )

    run_dir = make_run_dir(args.output_dir, args.label)
    filtered.to_csv(run_dir / "horizon_confidence_audit_rows.csv", index=False)
    horizon.to_csv(run_dir / "horizon_confidence_horizon_summary.csv", index=False)
    choices_summary.to_csv(run_dir / "horizon_confidence_choice_summary.csv", index=False)
    choices.to_csv(run_dir / "horizon_confidence_candidate_choices.csv", index=False)
    missing.to_csv(run_dir / "horizon_confidence_missing_targets.csv", index=False)
    fold.to_csv(run_dir / "horizon_confidence_fold_support.csv", index=False)
    (run_dir / "config.json").write_text(
        json.dumps(
            {
                "scored_examples": args.scored_examples,
                "fold_summary": args.fold_summary,
                "targets": args.targets,
                "row_scopes": row_scopes,
                "score_columns": score_columns,
                "tail_weight": args.tail_weight,
                "delta_weight": args.delta_weight,
                "beats60_weight": args.beats60_weight,
                "executable_weight": args.executable_weight,
            },
            indent=2,
            sort_keys=True,
            default=local_json_default,
        )
        + "\n",
        encoding="utf-8",
    )

    print("Horizon confidence support audit:")
    print(f"rows: {len(filtered)}")
    print(missing.to_string(index=False))
    print(choices_summary.head(20).to_string(index=False) if not choices_summary.empty else "no choices")
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scored-examples", type=Path, required=True)
    parser.add_argument("--fold-summary", type=Path)
    parser.add_argument("--targets", default=DEFAULT_TARGETS)
    parser.add_argument("--row-scopes", default=DEFAULT_ROW_SCOPES)
    parser.add_argument(
        "--score-columns",
        default="score_pnl,score_pnl_minus_tail,score_pnl_delta_tail,score_executable_pnl_tail",
    )
    parser.add_argument("--tail-weight", type=float, default=2.0)
    parser.add_argument("--delta-weight", type=float, default=0.25)
    parser.add_argument("--beats60-weight", type=float, default=0.5)
    parser.add_argument("--executable-weight", type=float, default=1.0)
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="entry_ev_horizon_confidence_support_audit")
    return parser


def main(argv: list[str] | None = None) -> int:
    run_audit(build_parser().parse_args(argv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
