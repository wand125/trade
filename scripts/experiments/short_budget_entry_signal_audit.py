#!/usr/bin/env python3
"""Audit entry-level signals and current-month state for replacement shorts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


CONDITION_DESCRIPTIONS: tuple[tuple[str, str], ...] = (
    ("prior_alert_or_pred_bias", "prior alert OR prior max pred-short bias >= 0.30"),
    ("focus_post_first_loss", "focus context after first realized loss"),
    ("focus_context_pnl_lt0", "focus context prior realized PnL < 0"),
    ("focus_side_gap_le0", "focus context pred side confidence gap <= 0"),
    ("focus_entry_rank_ge0p52", "focus context pred entry local rank >= 0.52"),
    (
        "focus_side_gap_le0_or_entry_rank_ge0p52",
        "focus context side gap <= 0 OR entry rank >= 0.52",
    ),
    (
        "focus_side_gap_le0_or_post_first_loss",
        "focus context side gap <= 0 OR after first realized loss",
    ),
    (
        "prior_or_focus_entry_signal",
        "prior signal OR focus context side gap <= 0 / entry rank >= 0.52",
    ),
    ("oracle_focus_ev_overestimate_ge30", "oracle diagnostic: focus context EV overestimate >= 30"),
)


def local_json_default(value: Any) -> Any:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    raise TypeError(f"cannot serialize {type(value).__name__}")


def bool_series(series: pd.Series) -> pd.Series:
    def convert(value: Any) -> bool:
        if pd.isna(value):
            return False
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "t", "yes", "y"}
        return bool(value)

    return series.map(convert).astype(bool)


def normalize_rows(frame: pd.DataFrame) -> pd.DataFrame:
    required = {
        "candidate",
        "window",
        "month",
        "entry_decision_timestamp",
        "candidate_adjusted_pnl",
        "combined_regime",
        "session_regime",
        "pred_side_confidence_gap",
        "pred_taken_entry_local_rank",
        "ev_overestimate_vs_realized",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError("replacement rows missing columns: " + ", ".join(missing))
    output = frame.copy()
    output["month"] = output["month"].astype(str)
    output["combined_regime"] = output["combined_regime"].astype(str)
    output["session_regime"] = output["session_regime"].astype(str)
    output["entry_decision_timestamp"] = pd.to_datetime(
        output["entry_decision_timestamp"],
        utc=True,
        errors="raise",
    )
    for column in [
        "candidate_adjusted_pnl",
        "pred_side_confidence_gap",
        "pred_taken_entry_local_rank",
        "ev_overestimate_vs_realized",
    ]:
        output[column] = pd.to_numeric(output[column], errors="coerce")
    if "is_loss" not in output.columns:
        output["is_loss"] = output["candidate_adjusted_pnl"] < 0
    else:
        output["is_loss"] = bool_series(output["is_loss"])
    if "prior_alert_or_pred_bias" not in output.columns:
        output["prior_alert_or_pred_bias"] = False
    else:
        output["prior_alert_or_pred_bias"] = bool_series(output["prior_alert_or_pred_bias"])
    return output.sort_values(
        [
            "candidate",
            "window",
            "month",
            "combined_regime",
            "session_regime",
            "entry_decision_timestamp",
        ]
    ).reset_index(drop=True)


def add_current_month_state(
    rows: pd.DataFrame,
    *,
    context_columns: list[str],
) -> pd.DataFrame:
    output = normalize_rows(rows)
    group_columns = ["candidate", "window", "month", *context_columns]
    output["prior_context_trade_count"] = output.groupby(group_columns).cumcount()
    context_pnl_cumsum = output.groupby(group_columns)["candidate_adjusted_pnl"].cumsum()
    output["prior_context_pnl"] = context_pnl_cumsum - output["candidate_adjusted_pnl"]
    loss_as_int = output["is_loss"].astype(int)
    output["prior_context_loss_count"] = (
        loss_as_int.groupby([output[column] for column in group_columns]).cumsum() - loss_as_int
    )
    win_as_int = (~output["is_loss"]).astype(int)
    output["prior_context_win_count"] = (
        win_as_int.groupby([output[column] for column in group_columns]).cumsum() - win_as_int
    )
    return output


def add_conditions(
    rows: pd.DataFrame,
    *,
    focus_combined_regime: str,
    focus_session_regime: str,
) -> pd.DataFrame:
    output = rows.copy()
    focus = output["combined_regime"].eq(focus_combined_regime) & output[
        "session_regime"
    ].eq(focus_session_regime)
    side_gap_le0 = output["pred_side_confidence_gap"].le(0.0)
    entry_rank_ge0p52 = output["pred_taken_entry_local_rank"].ge(0.52)
    post_first_loss = output["prior_context_loss_count"].ge(1)

    output["is_focus_context"] = focus
    output["focus_post_first_loss"] = focus & post_first_loss
    output["focus_context_pnl_lt0"] = focus & output["prior_context_pnl"].lt(0.0)
    output["focus_side_gap_le0"] = focus & side_gap_le0
    output["focus_entry_rank_ge0p52"] = focus & entry_rank_ge0p52
    output["focus_side_gap_le0_or_entry_rank_ge0p52"] = focus & (
        side_gap_le0 | entry_rank_ge0p52
    )
    output["focus_side_gap_le0_or_post_first_loss"] = focus & (
        side_gap_le0 | post_first_loss
    )
    output["prior_or_focus_entry_signal"] = output[
        "prior_alert_or_pred_bias"
    ] | output["focus_side_gap_le0_or_entry_rank_ge0p52"]
    output["oracle_focus_ev_overestimate_ge30"] = focus & output[
        "ev_overestimate_vs_realized"
    ].ge(30.0)
    return output


def bool_sum(series: pd.Series) -> int:
    return int(bool_series(series).sum())


def condition_summary(rows: pd.DataFrame) -> pd.DataFrame:
    if rows.empty:
        return pd.DataFrame()
    summary_rows: list[dict[str, Any]] = []
    for (candidate, window), group in rows.groupby(["candidate", "window"], dropna=False):
        total_rows = len(group)
        total_pnl = float(group["candidate_adjusted_pnl"].sum())
        total_loss_count = bool_sum(group["is_loss"])
        for condition, description in CONDITION_DESCRIPTIONS:
            covered = group[bool_series(group[condition])]
            uncovered = group[~bool_series(group[condition])]
            summary_rows.append(
                {
                    "candidate": candidate,
                    "window": window,
                    "condition": condition,
                    "description": description,
                    "total_rows": total_rows,
                    "total_pnl": total_pnl,
                    "total_loss_count": total_loss_count,
                    "covered_rows": len(covered),
                    "covered_pnl": float(covered["candidate_adjusted_pnl"].sum()),
                    "covered_loss_count": bool_sum(covered["is_loss"]),
                    "uncovered_rows": len(uncovered),
                    "uncovered_pnl": float(uncovered["candidate_adjusted_pnl"].sum()),
                    "uncovered_loss_count": bool_sum(uncovered["is_loss"]),
                }
            )
    return pd.DataFrame(summary_rows).sort_values(
        ["candidate", "window", "uncovered_pnl", "condition"]
    )


def focus_sequence(rows: pd.DataFrame) -> pd.DataFrame:
    if rows.empty:
        return pd.DataFrame()
    columns = [
        "candidate",
        "window",
        "month",
        "entry_decision_timestamp",
        "candidate_adjusted_pnl",
        "combined_regime",
        "session_regime",
        "prior_context_trade_count",
        "prior_context_pnl",
        "prior_context_loss_count",
        "pred_taken_ev",
        "pred_side_confidence_gap",
        "pred_taken_side_confidence",
        "pred_taken_entry_local_rank",
        "pred_taken_wait_regret",
        "pred_taken_max_adverse_pnl",
        "ev_overestimate_vs_realized",
        "prior_alert_or_pred_bias",
        "focus_side_gap_le0_or_entry_rank_ge0p52",
        "prior_or_focus_entry_signal",
    ]
    columns = [column for column in columns if column in rows.columns]
    return rows[rows["is_focus_context"]].sort_values(
        ["candidate", "window", "month", "entry_decision_timestamp"]
    )[columns]


def context_summary(rows: pd.DataFrame) -> pd.DataFrame:
    if rows.empty:
        return pd.DataFrame()
    return (
        rows.groupby(["candidate", "window", "combined_regime", "session_regime"], dropna=False)
        .agg(
            rows=("candidate_adjusted_pnl", "size"),
            total_pnl=("candidate_adjusted_pnl", "sum"),
            loss_count=("is_loss", bool_sum),
            focus_entry_signal_rows=(
                "focus_side_gap_le0_or_entry_rank_ge0p52",
                bool_sum,
            ),
            prior_or_focus_entry_signal_rows=("prior_or_focus_entry_signal", bool_sum),
            post_first_loss_rows=("focus_post_first_loss", bool_sum),
            mean_pred_side_gap=("pred_side_confidence_gap", "mean"),
            mean_entry_rank=("pred_taken_entry_local_rank", "mean"),
            mean_ev_overestimate=("ev_overestimate_vs_realized", "mean"),
        )
        .reset_index()
        .sort_values(["candidate", "window", "total_pnl", "rows"])
    )


def run_audit(args: argparse.Namespace) -> Path:
    args.output_dir.mkdir(parents=True, exist_ok=True)
    run_dir = args.output_dir / args.label
    suffix = 0
    while run_dir.exists():
        suffix += 1
        run_dir = args.output_dir / f"{args.label}_{suffix}"
    run_dir.mkdir(parents=True)

    source = pd.read_csv(args.replacement_rows)
    with_state = add_current_month_state(
        source,
        context_columns=["combined_regime", "session_regime"],
    )
    rows = add_conditions(
        with_state,
        focus_combined_regime=args.focus_combined_regime,
        focus_session_regime=args.focus_session_regime,
    )
    conditions = condition_summary(rows)
    contexts = context_summary(rows)
    sequence = focus_sequence(rows)

    rows.to_csv(run_dir / "entry_signal_rows.csv", index=False)
    conditions.to_csv(run_dir / "condition_summary.csv", index=False)
    contexts.to_csv(run_dir / "context_entry_signal_summary.csv", index=False)
    sequence.to_csv(run_dir / "focus_context_sequence.csv", index=False)
    metadata = {
        "replacement_rows": args.replacement_rows,
        "focus_combined_regime": args.focus_combined_regime,
        "focus_session_regime": args.focus_session_regime,
    }
    (run_dir / "config.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2, default=local_json_default) + "\n",
        encoding="utf-8",
    )
    if conditions.empty:
        print("no entry signal rows")
    else:
        print(conditions.head(args.print_rows).to_string(index=False))
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replacement-rows", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="short_budget_entry_signal_audit")
    parser.add_argument("--focus-combined-regime", default="range_low_vol")
    parser.add_argument("--focus-session-regime", default="ny_overlap")
    parser.add_argument("--print-rows", type=int, default=80)
    return parser


def main(argv: list[str] | None = None) -> int:
    run_audit(build_parser().parse_args(argv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
