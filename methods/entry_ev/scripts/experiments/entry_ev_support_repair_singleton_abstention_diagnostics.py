#!/usr/bin/env python3
"""Diagnose observable abstention rules for singleton support-repair candidates."""

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

from entry_ev_support_repair_horizon_replay import (  # noqa: E402
    read_base_monthly,
    read_base_trades,
    summarize_admission,
    summarize_repair_targets,
    update_monthly_metrics,
)
from entry_ev_support_repair_pairwise_switch_diagnostics import (  # noqa: E402
    numeric_series,
    parse_csv,
    text_series,
)


DEFAULT_RULES = (
    "none,"
    "singleton_any,"
    "singleton_720_prior_mean_neg,"
    "singleton_720_prior_tail_ge0p35,"
    "singleton_720_prior_mean_neg_tail_ge0p35,"
    "singleton_720_prior_risk_ge5,"
    "singleton_720_pred_pnl_lt2,"
    "singleton_720_pred_best_60m"
)


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


def prepare_current_additions(frame: pd.DataFrame, scenario_label: str = "") -> pd.DataFrame:
    output = frame.copy()
    if scenario_label:
        output = output[output["scenario_label"].astype(str).eq(scenario_label)].copy()
    output["current_replay_selected"] = bool_series(output, "current_replay_selected")
    output = output[output["current_replay_selected"]].copy()
    if output.empty:
        raise ValueError("no current selected rows in teacher examples")
    output["decision_timestamp"] = pd.to_datetime(
        output["decision_timestamp"],
        utc=True,
        errors="coerce",
    )
    output["entry_timestamp"] = pd.to_datetime(
        output.get("entry_timestamp", output["decision_timestamp"]),
        utc=True,
        errors="coerce",
    )
    output["exit_timestamp"] = pd.to_datetime(
        output.get("exit_timestamp"),
        utc=True,
        errors="coerce",
    )
    if "direction" not in output.columns:
        output["direction"] = text_series(output, "side")
    for column in ["role", "family", "month", "side", "direction", "scenario_label"]:
        output[column] = text_series(output, column)
    output["adjusted_pnl"] = numeric_series(
        output,
        "adjusted_pnl",
        default=np.nan,
    )
    missing_adjusted = output["adjusted_pnl"].isna()
    if missing_adjusted.any():
        output.loc[missing_adjusted, "adjusted_pnl"] = numeric_series(
            output.loc[missing_adjusted],
            "actual_pnl_at_hv_chosen_horizon",
        )
    output["actual_pnl_at_hv_chosen_horizon"] = numeric_series(
        output,
        "actual_pnl_at_hv_chosen_horizon",
    )
    output["quota_group_is_singleton"] = bool_series(output, "quota_group_is_singleton")
    return output.reset_index(drop=True)


def rule_mask(additions: pd.DataFrame, rule: str) -> pd.Series:
    singleton = bool_series(additions, "quota_group_is_singleton")
    horizon = numeric_series(additions, "hv_chosen_horizon_minutes")
    is_720 = horizon.ge(720.0)
    prior_mean = numeric_series(
        additions,
        "ranker_hv_720m_prior_mean_pnl",
        default=np.nan,
    )
    prior_tail = numeric_series(
        additions,
        "ranker_hv_720m_prior_tail_loss_rate",
        default=np.nan,
    )
    prior_risk = numeric_series(
        additions,
        "ranker_hv_720m_prior_risk_score",
        default=np.nan,
    )
    pred_pnl = numeric_series(additions, "hv_chosen_pred_pnl", default=np.nan)
    pred_best_horizon = numeric_series(
        additions,
        "pred_fixed_best_horizon_minutes",
        default=np.nan,
    )

    if rule == "none":
        return pd.Series(False, index=additions.index, dtype=bool)
    if rule == "singleton_any":
        return singleton
    if rule == "singleton_720_prior_mean_neg":
        return singleton & is_720 & prior_mean.lt(0.0)
    if rule == "singleton_720_prior_tail_ge0p35":
        return singleton & is_720 & prior_tail.ge(0.35)
    if rule == "singleton_720_prior_mean_neg_tail_ge0p35":
        return singleton & is_720 & prior_mean.lt(0.0) & prior_tail.ge(0.35)
    if rule == "singleton_720_prior_risk_ge5":
        return singleton & is_720 & prior_risk.ge(5.0)
    if rule == "singleton_720_pred_pnl_lt2":
        return singleton & is_720 & pred_pnl.lt(2.0)
    if rule == "singleton_720_pred_best_60m":
        return singleton & is_720 & pred_best_horizon.eq(60.0)
    raise ValueError(f"unknown abstention rule: {rule}")


def summarize_abstention_rule(
    *,
    rule: str,
    base_monthly: pd.DataFrame,
    base_trades: pd.DataFrame,
    additions: pd.DataFrame,
    min_total_pnl: float,
    min_role_total_pnl: float,
    month_floor: float,
    shallow_month_floor: float,
    min_role_trades: int,
    min_month_trades: int,
    max_side_trade_share: float,
) -> tuple[dict[str, Any], pd.DataFrame, pd.DataFrame]:
    abstain = rule_mask(additions, rule)
    flagged = additions[abstain].copy()
    kept = additions[~abstain].copy()
    scenario_label = additions["scenario_label"].iloc[0]
    monthly = update_monthly_metrics(
        base_monthly,
        base_trades,
        kept,
        scenario={"scenario_label": f"{scenario_label}__abstain_{rule}"},
    )
    repair_summary, _ = summarize_repair_targets(
        monthly,
        month_floor=month_floor,
        min_month_trades=min_month_trades,
        max_side_trade_share=max_side_trade_share,
        shallow_month_floor=shallow_month_floor,
    )
    admission = summarize_admission(
        monthly,
        min_total_pnl=min_total_pnl,
        min_role_total_pnl=min_role_total_pnl,
        month_floor=month_floor,
        min_role_trades=min_role_trades,
        min_month_trades=min_month_trades,
        max_side_trade_share=max_side_trade_share,
    )
    flagged_actual = numeric_series(flagged, "actual_pnl_at_hv_chosen_horizon")
    kept_actual = numeric_series(kept, "actual_pnl_at_hv_chosen_horizon")
    row = {
        "rule": rule,
        "abstained_count": int(len(flagged)),
        "abstained_actual_sum": float(flagged_actual.sum()) if len(flagged) else 0.0,
        "abstained_loss_count": int(flagged_actual.lt(0.0).sum()) if len(flagged) else 0,
        "abstained_tail_loss_count": int(flagged_actual.le(-5.0).sum()) if len(flagged) else 0,
        "abstained_positive_count": int(flagged_actual.gt(0.0).sum()) if len(flagged) else 0,
        "kept_addition_count": int(len(kept)),
        "kept_addition_pnl": float(kept_actual.sum()) if len(kept) else 0.0,
        "added_pnl_delta_vs_no_abstain": float(
            (kept_actual.sum() if len(kept) else 0.0)
            - numeric_series(additions, "actual_pnl_at_hv_chosen_horizon").sum()
        ),
        **admission,
        **repair_summary,
    }
    if not flagged.empty:
        flagged = flagged.copy()
        flagged["abstention_rule"] = rule
    monthly = monthly.copy()
    monthly["abstention_rule"] = rule
    return row, flagged, monthly


def run_diagnostics(args: argparse.Namespace) -> Path:
    base_monthly = read_base_monthly(
        args.base_monthly_metrics,
        candidate=args.candidate,
        variant_contains=args.variant_contains,
        entry_block_rule=args.base_entry_block_rule,
    )
    base_trades = read_base_trades(
        args.base_trades,
        candidate=args.candidate,
        variant_contains=args.variant_contains,
        entry_block_rule=args.base_entry_block_rule,
    )
    teacher_examples = pd.read_csv(args.teacher_examples)
    additions = prepare_current_additions(teacher_examples, scenario_label=args.scenario_label)
    rules = parse_csv(args.rules)

    rows: list[dict[str, Any]] = []
    flagged_frames: list[pd.DataFrame] = []
    monthly_frames: list[pd.DataFrame] = []
    for rule in rules:
        row, flagged, monthly = summarize_abstention_rule(
            rule=rule,
            base_monthly=base_monthly,
            base_trades=base_trades,
            additions=additions,
            min_total_pnl=args.min_total_pnl,
            min_role_total_pnl=args.min_role_total_pnl,
            month_floor=args.month_floor,
            shallow_month_floor=args.shallow_month_floor,
            min_role_trades=args.min_role_trades,
            min_month_trades=args.min_month_trades,
            max_side_trade_share=args.max_side_trade_share,
        )
        rows.append(row)
        if not flagged.empty:
            flagged_frames.append(flagged)
        monthly_frames.append(monthly)

    summary = pd.DataFrame(rows)
    flagged_all = (
        pd.concat(flagged_frames, ignore_index=True, sort=False)
        if flagged_frames
        else pd.DataFrame()
    )
    monthly_all = pd.concat(monthly_frames, ignore_index=True, sort=False)

    run_dir = make_run_dir(args.output_dir, args.label)
    summary.to_csv(run_dir / "singleton_abstention_summary.csv", index=False)
    flagged_all.to_csv(run_dir / "singleton_abstention_flagged_rows.csv", index=False)
    monthly_all.to_csv(run_dir / "singleton_abstention_monthly_metrics.csv", index=False)
    (run_dir / "config.json").write_text(
        json.dumps(
            {
                "base_monthly_metrics": args.base_monthly_metrics,
                "base_trades": args.base_trades,
                "teacher_examples": args.teacher_examples,
                "candidate": args.candidate,
                "variant_contains": args.variant_contains,
                "base_entry_block_rule": args.base_entry_block_rule,
                "scenario_label": args.scenario_label,
                "rules": rules,
                "min_total_pnl": args.min_total_pnl,
                "min_role_total_pnl": args.min_role_total_pnl,
                "month_floor": args.month_floor,
                "shallow_month_floor": args.shallow_month_floor,
                "min_role_trades": args.min_role_trades,
                "min_month_trades": args.min_month_trades,
                "max_side_trade_share": args.max_side_trade_share,
            },
            indent=2,
            sort_keys=True,
            default=local_json_default,
        )
        + "\n",
        encoding="utf-8",
    )

    print("Singleton abstention diagnostics:")
    print(summary.to_string(index=False))
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-monthly-metrics", type=Path, required=True)
    parser.add_argument("--base-trades", type=Path, required=True)
    parser.add_argument("--teacher-examples", type=Path, required=True)
    parser.add_argument(
        "--candidate",
        default="q95_sg95_rank90_floor5_side_regime_session_month",
    )
    parser.add_argument(
        "--variant-contains",
        default="loss_exit30_cd15__holdext_isolated_large_loss_long_t-5_h720",
    )
    parser.add_argument("--base-entry-block-rule", default="long_range_normal_ny_fixed60_pred_gt0")
    parser.add_argument("--scenario-label", default="")
    parser.add_argument("--rules", default=DEFAULT_RULES)
    parser.add_argument("--min-total-pnl", type=float, default=0.0)
    parser.add_argument("--min-role-total-pnl", type=float, default=0.0)
    parser.add_argument("--month-floor", type=float, default=0.0)
    parser.add_argument("--shallow-month-floor", type=float, default=-1.0)
    parser.add_argument("--min-role-trades", type=int, default=4)
    parser.add_argument("--min-month-trades", type=int, default=1)
    parser.add_argument("--max-side-trade-share", type=float, default=0.95)
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="entry_ev_support_repair_singleton_abstention")
    return parser


def main(argv: list[str] | None = None) -> int:
    run_diagnostics(build_parser().parse_args(argv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
