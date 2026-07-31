#!/usr/bin/env python3
"""Diagnose isolated large-loss exit-capture failures for entry-EV trades."""

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


REQUIRED_COLUMNS = {
    "direction",
    "entry_timestamp",
    "exit_timestamp",
    "adjusted_pnl",
    "holding_minutes",
    "entry_decision_timestamp",
    "exit_decision_timestamp",
    "actual_taken_best_adjusted_pnl",
    "actual_taken_best_holding_minutes",
    "exit_regret",
}

DEFAULT_GROUP_COLUMNS = [
    "source",
    "role",
    "family",
    "variant",
    "candidate",
    "month",
]


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
    return [part.strip() for part in value.split(",") if part.strip()]


def parse_int_csv(value: str) -> list[int]:
    return [int(part) for part in parse_csv(value)]


def parse_labeled_paths(values: list[str]) -> list[tuple[str, Path]]:
    pairs: list[tuple[str, Path]] = []
    for value in values:
        if "=" not in value:
            raise argparse.ArgumentTypeError("paths must use label=path")
        label, path_text = value.split("=", 1)
        label = label.strip()
        if not label:
            raise argparse.ArgumentTypeError("label must not be empty")
        pairs.append((label, Path(path_text.strip())))
    if not pairs:
        raise argparse.ArgumentTypeError("at least one path is required")
    return pairs


def numeric_series(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    values = pd.to_numeric(frame[column], errors="coerce")
    return values.replace([np.inf, -np.inf], np.nan).fillna(default).astype(float)


def read_enriched_trades(pairs: list[tuple[str, Path]]) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for label, path in pairs:
        frame = pd.read_csv(path)
        missing = sorted(REQUIRED_COLUMNS - set(frame.columns))
        if missing:
            raise ValueError(f"{path} missing columns: {', '.join(missing)}")
        output = frame.copy()
        output.insert(0, "source", label)
        frames.append(output)
    if not frames:
        raise ValueError("no enriched trade rows found")
    return pd.concat(frames, ignore_index=True)


def ensure_group_columns(frame: pd.DataFrame) -> pd.DataFrame:
    output = frame.copy()
    for column in DEFAULT_GROUP_COLUMNS:
        if column not in output.columns:
            output[column] = "__unknown__"
        output[column] = output[column].fillna("__unknown__").astype(str)
    output["month"] = output["month"].astype(str).str.slice(0, 7)
    return output


def selected_side_value(
    frame: pd.DataFrame,
    *,
    long_column: str,
    short_column: str,
    default: float = np.nan,
) -> pd.Series:
    long_values = numeric_series(frame, long_column, default=default)
    short_values = numeric_series(frame, short_column, default=default)
    direction = frame["direction"].astype(str).str.lower()
    return pd.Series(
        np.where(direction.eq("long"), long_values, short_values),
        index=frame.index,
        dtype=float,
    )


def normalize_enriched_trades(frame: pd.DataFrame, *, fixed_horizons: list[int]) -> pd.DataFrame:
    output = ensure_group_columns(frame)
    output["direction"] = output["direction"].astype(str).str.lower()
    for column in [
        "entry_timestamp",
        "exit_timestamp",
        "entry_decision_timestamp",
        "exit_decision_timestamp",
    ]:
        output[column] = pd.to_datetime(output[column], utc=True, errors="coerce")
    for column in [
        "adjusted_pnl",
        "holding_minutes",
        "actual_taken_best_adjusted_pnl",
        "actual_taken_best_holding_minutes",
        "exit_regret",
        "pred_taken_ev",
        "pred_taken_best_holding_minutes",
        "pred_side_confidence_gap",
    ]:
        output[column] = numeric_series(output, column)
    for horizon in fixed_horizons:
        output[f"actual_taken_fixed_{horizon}m_adjusted_pnl"] = selected_side_value(
            output,
            long_column=f"long_fixed_{horizon}m_adjusted_pnl",
            short_column=f"short_fixed_{horizon}m_adjusted_pnl",
            default=np.nan,
        )
        output[f"fixed_{horizon}m_delta_vs_realized"] = (
            output[f"actual_taken_fixed_{horizon}m_adjusted_pnl"] - output["adjusted_pnl"]
        )
        output[f"fixed_{horizon}m_improves_loss"] = (
            output["adjusted_pnl"].lt(0.0)
            & output[f"fixed_{horizon}m_delta_vs_realized"].gt(0.0)
        )
    return output


def add_sequence_features(
    frame: pd.DataFrame,
    *,
    large_loss_threshold: float,
    long_gap_minutes: float,
) -> pd.DataFrame:
    output = frame.copy()
    group_columns = DEFAULT_GROUP_COLUMNS
    output = output.sort_values([*group_columns, "entry_decision_timestamp"]).reset_index(
        drop=True
    )
    grouped = output.groupby(group_columns, dropna=False)
    output["trade_index_in_month"] = grouped.cumcount() + 1
    output["prev_adjusted_pnl"] = grouped["adjusted_pnl"].shift(1)
    output["prev_direction"] = grouped["direction"].shift(1)
    output["prev_exit_timestamp"] = grouped["exit_timestamp"].shift(1)
    output["prev_exit_decision_timestamp"] = grouped["exit_decision_timestamp"].shift(1)
    output["decision_minutes_since_prev_exit"] = (
        output["entry_decision_timestamp"] - output["prev_exit_decision_timestamp"]
    ).dt.total_seconds() / 60.0
    output["same_side_as_prev"] = output["direction"].eq(output["prev_direction"])
    output["is_loss"] = output["adjusted_pnl"].lt(0.0)
    output["is_large_loss"] = output["adjusted_pnl"].le(large_loss_threshold)
    output["prev_result_bucket"] = np.select(
        [
            output["prev_adjusted_pnl"].isna(),
            output["prev_adjusted_pnl"].lt(0.0),
            output["prev_adjusted_pnl"].ge(0.0),
        ],
        ["first", "prev_loss", "prev_non_loss"],
        default="unknown",
    )
    output["post_exit_gap_bucket"] = pd.cut(
        output["decision_minutes_since_prev_exit"],
        bins=[-np.inf, 15, 30, 60, 120, 240, 1440, np.inf],
        labels=["<=15", "15-30", "30-60", "60-120", "120-240", "240-1440", ">1440"],
    ).astype("string").fillna("first")
    output["long_gap_after_prev_exit"] = output["decision_minutes_since_prev_exit"].gt(
        long_gap_minutes
    )
    output["isolated_context"] = (
        output["prev_adjusted_pnl"].isna()
        | output["prev_adjusted_pnl"].ge(0.0)
        | output["long_gap_after_prev_exit"]
    )
    output["isolated_large_loss"] = output["isolated_context"] & output["is_large_loss"]
    return output


def add_exit_capture_features(
    frame: pd.DataFrame,
    *,
    min_oracle_edge: float,
    low_capture_threshold: float,
    large_exit_regret_threshold: float,
    hold_gap_minutes: float,
) -> pd.DataFrame:
    output = frame.copy()
    adjusted = output["adjusted_pnl"].astype(float)
    oracle = output["actual_taken_best_adjusted_pnl"].astype(float)
    output["same_side_oracle_edge"] = oracle.gt(min_oracle_edge)
    output["same_side_missed_loss"] = adjusted.lt(0.0) & output["same_side_oracle_edge"]
    output["exit_capture_ratio"] = np.where(
        output["same_side_oracle_edge"],
        adjusted / oracle.replace(0.0, np.nan),
        np.nan,
    )
    output["exit_capture_shortfall"] = np.where(
        output["same_side_oracle_edge"],
        np.maximum(oracle - adjusted, 0.0),
        0.0,
    )
    output["low_exit_capture"] = (
        output["same_side_oracle_edge"]
        & pd.Series(output["exit_capture_ratio"], index=output.index).lt(
            low_capture_threshold
        )
    )
    output["large_exit_regret"] = output["exit_regret"].astype(float).ge(
        large_exit_regret_threshold
    )
    output["exit_capture_failure"] = (
        output["same_side_missed_loss"]
        | output["low_exit_capture"]
        | output["large_exit_regret"]
    )
    output["oracle_hold_delta_minutes"] = (
        output["actual_taken_best_holding_minutes"].astype(float)
        - output["holding_minutes"].astype(float)
    )
    output["oracle_after_actual_exit"] = output["oracle_hold_delta_minutes"].gt(
        hold_gap_minutes
    )
    output["oracle_before_actual_exit"] = output["oracle_hold_delta_minutes"].lt(
        -hold_gap_minutes
    )
    output["isolated_exit_capture_failure"] = (
        output["isolated_context"] & output["exit_capture_failure"]
    )
    output["isolated_large_loss_capture_failure"] = (
        output["isolated_large_loss"] & output["exit_capture_failure"]
    )
    output["ev_overestimate_vs_realized"] = (
        numeric_series(output, "pred_taken_ev") - output["adjusted_pnl"].astype(float)
    )
    return output


def summarize_groups(
    frame: pd.DataFrame,
    group_columns: list[str],
    *,
    fixed_horizons: list[int],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for key, group in frame.groupby(group_columns, dropna=False, observed=True):
        if not isinstance(key, tuple):
            key = (key,)
        row = dict(zip(group_columns, key))
        pnl = group["adjusted_pnl"].astype(float)
        loss = pnl.lt(0.0)
        large_loss = group["is_large_loss"].astype(bool)
        isolated = group["isolated_context"].astype(bool)
        row.update(
            {
                "trade_count": int(len(group)),
                "total_pnl": float(pnl.sum()),
                "loss_count": int(loss.sum()),
                "large_loss_count": int(large_loss.sum()),
                "isolated_trade_count": int(isolated.sum()),
                "isolated_large_loss_count": int(
                    group["isolated_large_loss"].astype(bool).sum()
                ),
                "loss_pnl": float(pnl[loss].sum()),
                "min_trade_pnl": float(pnl.min()) if len(group) else 0.0,
                "same_side_missed_loss_count": int(
                    group["same_side_missed_loss"].astype(bool).sum()
                ),
                "exit_capture_failure_count": int(
                    group["exit_capture_failure"].astype(bool).sum()
                ),
                "isolated_exit_capture_failure_count": int(
                    group["isolated_exit_capture_failure"].astype(bool).sum()
                ),
                "isolated_large_loss_capture_failure_count": int(
                    group["isolated_large_loss_capture_failure"].astype(bool).sum()
                ),
                "exit_regret_sum": float(group["exit_regret"].astype(float).sum()),
                "exit_capture_shortfall_sum": float(
                    group["exit_capture_shortfall"].astype(float).sum()
                ),
                "oracle_after_actual_exit_count": int(
                    group["oracle_after_actual_exit"].astype(bool).sum()
                ),
                "oracle_before_actual_exit_count": int(
                    group["oracle_before_actual_exit"].astype(bool).sum()
                ),
                "oracle_hold_delta_mean": float(
                    group["oracle_hold_delta_minutes"].astype(float).mean()
                ),
                "ev_overestimate_vs_realized_mean": float(
                    group["ev_overestimate_vs_realized"].astype(float).mean()
                ),
            }
        )
        capture_ratio = pd.to_numeric(group["exit_capture_ratio"], errors="coerce")
        row["exit_capture_ratio_mean"] = (
            float(capture_ratio.dropna().mean()) if capture_ratio.notna().any() else 0.0
        )
        for horizon in fixed_horizons:
            delta_column = f"fixed_{horizon}m_delta_vs_realized"
            fixed_column = f"actual_taken_fixed_{horizon}m_adjusted_pnl"
            row[f"fixed_{horizon}m_delta_sum"] = float(
                pd.to_numeric(group[delta_column], errors="coerce").fillna(0.0).sum()
            )
            row[f"fixed_{horizon}m_loss_delta_sum"] = float(
                pd.to_numeric(group.loc[loss, delta_column], errors="coerce")
                .fillna(0.0)
                .sum()
            )
            row[f"fixed_{horizon}m_large_loss_delta_sum"] = float(
                pd.to_numeric(group.loc[large_loss, delta_column], errors="coerce")
                .fillna(0.0)
                .sum()
            )
            row[f"fixed_{horizon}m_loss_improved_count"] = int(
                group[f"fixed_{horizon}m_improves_loss"].astype(bool).sum()
            )
            row[f"fixed_{horizon}m_pnl_sum"] = float(
                pd.to_numeric(group[fixed_column], errors="coerce").fillna(0.0).sum()
            )
        rows.append(row)
    if not rows:
        return pd.DataFrame(columns=group_columns)
    return pd.DataFrame(rows).sort_values(
        ["total_pnl", "isolated_large_loss_capture_failure_count", "trade_count"],
        ascending=[True, False, False],
    )


def target_rule_mask(frame: pd.DataFrame, rule: str) -> pd.Series:
    if rule == "isolated_large_loss_capture_failure":
        return frame["isolated_large_loss_capture_failure"].astype(bool)
    if rule == "isolated_large_loss":
        return frame["isolated_large_loss"].astype(bool)
    if rule == "isolated_loss_capture_failure":
        return (
            frame["isolated_context"].astype(bool)
            & frame["is_loss"].astype(bool)
            & frame["exit_capture_failure"].astype(bool)
        )
    if rule == "first_large_loss":
        return frame["prev_result_bucket"].eq("first") & frame["is_large_loss"].astype(bool)
    if rule == "prev_non_loss_gt1440_large_loss":
        return (
            frame["prev_result_bucket"].eq("prev_non_loss")
            & frame["post_exit_gap_bucket"].eq(">1440")
            & frame["is_large_loss"].astype(bool)
        )
    raise ValueError(f"unknown target rule: {rule}")


def replacement_grid_summary(
    frame: pd.DataFrame,
    *,
    fixed_horizons: list[int],
    rules: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    total_pnl = float(frame["adjusted_pnl"].astype(float).sum())
    month_keys = ["source", "role", "family", "variant", "candidate", "month"]
    monthly_rows: list[dict[str, Any]] = []
    overall_rows: list[dict[str, Any]] = []
    for rule in rules:
        base_mask = target_rule_mask(frame, rule)
        for horizon in fixed_horizons:
            fixed_column = f"actual_taken_fixed_{horizon}m_adjusted_pnl"
            replacement_pnl = pd.to_numeric(frame[fixed_column], errors="coerce")
            valid_mask = base_mask & replacement_pnl.notna()
            delta = (replacement_pnl - frame["adjusted_pnl"].astype(float)).where(
                valid_mask,
                0.0,
            )
            adjusted_after = frame["adjusted_pnl"].astype(float) + delta
            flagged = frame[valid_mask]
            grouped_after = adjusted_after.groupby(
                [frame[column] for column in month_keys],
                dropna=False,
            ).sum()
            month_min_after = float(grouped_after.min()) if len(grouped_after) else 0.0
            overall_rows.append(
                {
                    "target_rule": rule,
                    "fixed_horizon_minutes": int(horizon),
                    "trade_count": int(len(frame)),
                    "total_pnl": total_pnl,
                    "flagged_trade_count": int(valid_mask.sum()),
                    "flagged_pnl": float(frame.loc[valid_mask, "adjusted_pnl"].sum()),
                    "flagged_fixed_pnl": float(replacement_pnl[valid_mask].sum()),
                    "delta_if_replaced_no_replay": float(delta.sum()),
                    "total_pnl_if_replaced_no_replay": float(total_pnl + delta.sum()),
                    "month_min_if_replaced_no_replay": month_min_after,
                    "flagged_loss_count": int(frame.loc[valid_mask, "is_loss"].sum()),
                    "flagged_large_loss_count": int(
                        frame.loc[valid_mask, "is_large_loss"].sum()
                    ),
                    "flagged_exit_capture_failure_count": int(
                        frame.loc[valid_mask, "exit_capture_failure"].sum()
                    ),
                }
            )
            month_frame = frame.copy()
            month_frame["_replacement_delta"] = delta
            month_frame["_adjusted_after"] = adjusted_after
            for key, group in month_frame.groupby(month_keys, dropna=False):
                if not isinstance(key, tuple):
                    key = (key,)
                group_mask = valid_mask.loc[group.index]
                row = dict(zip(month_keys, key))
                row.update(
                    {
                        "target_rule": rule,
                        "fixed_horizon_minutes": int(horizon),
                        "total_pnl": float(group["adjusted_pnl"].sum()),
                        "flagged_trade_count": int(group_mask.sum()),
                        "flagged_pnl": float(group.loc[group_mask, "adjusted_pnl"].sum()),
                        "flagged_fixed_pnl": float(
                            replacement_pnl.loc[group.index][group_mask].sum()
                        ),
                        "delta_if_replaced_no_replay": float(
                            group["_replacement_delta"].sum()
                        ),
                        "pnl_if_replaced_no_replay": float(group["_adjusted_after"].sum()),
                    }
                )
                monthly_rows.append(row)
    overall = pd.DataFrame(overall_rows).sort_values(
        [
            "month_min_if_replaced_no_replay",
            "total_pnl_if_replaced_no_replay",
            "delta_if_replaced_no_replay",
        ],
        ascending=[False, False, False],
    )
    monthly = pd.DataFrame(monthly_rows).sort_values(
        ["pnl_if_replaced_no_replay", "delta_if_replaced_no_replay"],
        ascending=[True, False],
    )
    return overall, monthly


def build_diagnostics(args: argparse.Namespace) -> Path:
    fixed_horizons = parse_int_csv(args.fixed_horizons)
    raw = read_enriched_trades(parse_labeled_paths(args.enriched_trades))
    trades = normalize_enriched_trades(raw, fixed_horizons=fixed_horizons)
    if args.candidates:
        trades = trades[trades["candidate"].isin(parse_csv(args.candidates))].copy()
    if args.variants:
        trades = trades[trades["variant"].isin(parse_csv(args.variants))].copy()
    if args.roles:
        trades = trades[trades["role"].isin(parse_csv(args.roles))].copy()
    if args.months:
        trades = trades[trades["month"].isin(parse_csv(args.months))].copy()
    if trades.empty:
        raise ValueError("no enriched trades remain after filters")
    trades = add_sequence_features(
        trades,
        large_loss_threshold=args.large_loss_threshold,
        long_gap_minutes=args.long_gap_minutes,
    )
    trades = add_exit_capture_features(
        trades,
        min_oracle_edge=args.min_oracle_edge,
        low_capture_threshold=args.low_capture_threshold,
        large_exit_regret_threshold=args.large_exit_regret_threshold,
        hold_gap_minutes=args.hold_gap_minutes,
    )

    run_dir = make_run_dir(args.output_dir, args.label)
    trades.to_csv(run_dir / "isolated_exit_capture_trades.csv", index=False)

    summarize_groups(
        trades,
        ["prev_result_bucket", "post_exit_gap_bucket", "isolated_context"],
        fixed_horizons=fixed_horizons,
    ).to_csv(run_dir / "path_exit_capture_summary.csv", index=False)

    summarize_groups(
        trades,
        ["source", "role", "family", "variant", "candidate", "month"],
        fixed_horizons=fixed_horizons,
    ).to_csv(run_dir / "month_exit_capture_summary.csv", index=False)

    summarize_groups(
        trades,
        ["source", "role", "direction", "combined_regime", "session_regime"],
        fixed_horizons=fixed_horizons,
    ).to_csv(run_dir / "context_exit_capture_summary.csv", index=False)

    isolated_large_losses = trades[trades["isolated_large_loss"].astype(bool)].sort_values(
        "adjusted_pnl"
    )
    isolated_large_losses.to_csv(run_dir / "isolated_large_loss_details.csv", index=False)

    replacement_overall, replacement_monthly = replacement_grid_summary(
        trades,
        fixed_horizons=fixed_horizons,
        rules=parse_csv(args.target_rules),
    )
    replacement_overall.to_csv(
        run_dir / "fixed_horizon_replacement_grid_summary.csv",
        index=False,
    )
    replacement_monthly.to_csv(
        run_dir / "fixed_horizon_monthly_replacement_summary.csv",
        index=False,
    )

    config = {
        "enriched_trades": parse_labeled_paths(args.enriched_trades),
        "fixed_horizons": fixed_horizons,
        "large_loss_threshold": args.large_loss_threshold,
        "long_gap_minutes": args.long_gap_minutes,
        "min_oracle_edge": args.min_oracle_edge,
        "low_capture_threshold": args.low_capture_threshold,
        "large_exit_regret_threshold": args.large_exit_regret_threshold,
        "hold_gap_minutes": args.hold_gap_minutes,
        "candidates": args.candidates,
        "variants": args.variants,
        "roles": args.roles,
        "months": args.months,
        "target_rules": args.target_rules,
    }
    (run_dir / "config.json").write_text(
        json.dumps(config, indent=2, default=local_json_default),
        encoding="utf-8",
    )

    path_summary = summarize_groups(
        trades,
        ["prev_result_bucket", "post_exit_gap_bucket", "isolated_context"],
        fixed_horizons=fixed_horizons,
    )
    print("Worst path exit-capture summary:")
    print(
        path_summary[
            [
                "prev_result_bucket",
                "post_exit_gap_bucket",
                "isolated_context",
                "trade_count",
                "total_pnl",
                "large_loss_count",
                "isolated_large_loss_capture_failure_count",
                "exit_capture_shortfall_sum",
                "oracle_after_actual_exit_count",
            ]
        ]
        .head(args.print_top)
        .to_string(index=False)
    )
    print(f"isolated large losses: {len(isolated_large_losses)}")
    print("Top fixed-horizon no-replay replacement rows:")
    print(
        replacement_overall[
            [
                "target_rule",
                "fixed_horizon_minutes",
                "flagged_trade_count",
                "delta_if_replaced_no_replay",
                "total_pnl_if_replaced_no_replay",
                "month_min_if_replaced_no_replay",
            ]
        ]
        .head(args.print_top)
        .to_string(index=False)
    )
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--enriched-trades", action="append", required=True)
    parser.add_argument("--fixed-horizons", default="60,240,720")
    parser.add_argument("--large-loss-threshold", type=float, default=-2.0)
    parser.add_argument("--long-gap-minutes", type=float, default=1440.0)
    parser.add_argument("--min-oracle-edge", type=float, default=5.0)
    parser.add_argument("--low-capture-threshold", type=float, default=0.25)
    parser.add_argument("--large-exit-regret-threshold", type=float, default=5.0)
    parser.add_argument("--hold-gap-minutes", type=float, default=5.0)
    parser.add_argument("--candidates", default="")
    parser.add_argument("--variants", default="")
    parser.add_argument("--roles", default="")
    parser.add_argument("--months", default="")
    parser.add_argument(
        "--target-rules",
        default=(
            "isolated_large_loss_capture_failure,isolated_large_loss,"
            "isolated_loss_capture_failure,first_large_loss,"
            "prev_non_loss_gt1440_large_loss"
        ),
    )
    parser.add_argument("--print-top", type=int, default=12)
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="entry_ev_isolated_exit_capture_diagnostics")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    build_diagnostics(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
