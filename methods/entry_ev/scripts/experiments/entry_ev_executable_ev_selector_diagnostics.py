#!/usr/bin/env python3
"""Evaluate executable-EV features in a NoTrade-first selected-trade selector."""

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


def read_trade_frames(paths: list[Path]) -> pd.DataFrame:
    frames = [pd.read_csv(path) for path in paths]
    if not frames:
        raise ValueError("at least one executable EV trade CSV is required")
    return pd.concat(frames, ignore_index=True)


def bool_series(frame: pd.DataFrame, column: str, default: bool = False) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=bool)
    series = frame[column]
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(default).astype(bool)
    if pd.api.types.is_numeric_dtype(series):
        return series.fillna(float(default)).astype(float).ne(0.0)
    normalized = series.astype(str).str.lower().str.strip()
    return normalized.isin({"true", "1", "yes", "y"})


def numeric_series(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce").fillna(default).astype(float)


def normalize_trade_frame(frame: pd.DataFrame) -> pd.DataFrame:
    required = {
        "role",
        "candidate",
        "month",
        "direction",
        "entry_decision_timestamp",
        "adjusted_pnl",
        "pred_raw_executable_ev",
        "pred_capture_calibrated_ev",
        "executable_capture_factor",
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"executable EV trades missing columns: {', '.join(missing)}")
    normalized = frame.copy()
    normalized["role"] = normalized["role"].astype(str)
    normalized["candidate"] = normalized["candidate"].astype(str)
    normalized["month"] = normalized["month"].astype(str).str.slice(0, 7)
    normalized["direction"] = normalized["direction"].astype(str).str.lower()
    normalized["entry_decision_timestamp"] = pd.to_datetime(
        normalized["entry_decision_timestamp"],
        utc=True,
    )
    for column in [
        "adjusted_pnl",
        "pred_raw_executable_ev",
        "pred_capture_calibrated_ev",
        "executable_capture_factor",
        "raw_ev_abs_error",
        "capture_calibrated_ev_abs_error",
        "raw_ev_error_vs_realized",
        "capture_calibrated_ev_error_vs_realized",
        "prior_capture_support_weight",
    ]:
        normalized[column] = numeric_series(normalized, column)
    for column in ["exit_capture_failure", "same_side_missed_loss", "direction_error"]:
        normalized[column] = bool_series(normalized, column)
    return normalized


def filter_roles(frame: pd.DataFrame, roles: list[str]) -> pd.DataFrame:
    if not roles:
        return frame.copy()
    return frame[frame["role"].isin(roles)].copy()


def cumulative_max_drawdown(values: pd.Series) -> float:
    cumulative = values.astype(float).cumsum()
    if cumulative.empty:
        return 0.0
    running_max = cumulative.cummax()
    drawdown = running_max - cumulative
    return float(drawdown.max())


def summarize_trade_slice(frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty:
        return {
            "trade_count": 0,
            "total_pnl": 0.0,
            "max_drawdown": 0.0,
        }
    ordered = frame.sort_values("entry_decision_timestamp")
    long_count = int(ordered["direction"].eq("long").sum())
    short_count = int(ordered["direction"].eq("short").sum())
    trade_count = int(len(ordered))
    total_pnl = float(ordered["adjusted_pnl"].astype(float).sum())
    return {
        "trade_count": trade_count,
        "total_pnl": total_pnl,
        "avg_pnl": float(ordered["adjusted_pnl"].astype(float).mean()),
        "win_rate": float((ordered["adjusted_pnl"].astype(float) > 0.0).mean()),
        "max_drawdown": cumulative_max_drawdown(ordered["adjusted_pnl"]),
        "long_trade_count": long_count,
        "short_trade_count": short_count,
        "max_side_trade_share": (
            float(max(long_count, short_count) / trade_count) if trade_count else 0.0
        ),
        "raw_ev_mean": float(ordered["pred_raw_executable_ev"].astype(float).mean()),
        "capture_ev_mean": float(
            ordered["pred_capture_calibrated_ev"].astype(float).mean()
        ),
        "capture_ev_p10": float(
            ordered["pred_capture_calibrated_ev"].astype(float).quantile(0.10)
        ),
        "capture_ev_p25": float(
            ordered["pred_capture_calibrated_ev"].astype(float).quantile(0.25)
        ),
        "capture_ev_low2_share": float(
            (ordered["pred_capture_calibrated_ev"].astype(float) < 2.0).mean()
        ),
        "capture_ev_low3_share": float(
            (ordered["pred_capture_calibrated_ev"].astype(float) < 3.0).mean()
        ),
        "capture_factor_mean": float(
            ordered["executable_capture_factor"].astype(float).mean()
        ),
        "capture_support_mean": float(
            ordered["prior_capture_support_weight"].astype(float).mean()
        ),
        "raw_ev_mae": float(ordered["raw_ev_abs_error"].astype(float).mean()),
        "capture_ev_mae": float(
            ordered["capture_calibrated_ev_abs_error"].astype(float).mean()
        ),
        "raw_ev_bias": float(ordered["raw_ev_error_vs_realized"].astype(float).mean()),
        "capture_ev_bias": float(
            ordered["capture_calibrated_ev_error_vs_realized"].astype(float).mean()
        ),
        "exit_capture_failure_rate": float(
            ordered["exit_capture_failure"].fillna(False).astype(bool).mean()
        ),
        "same_side_missed_loss_rate": float(
            ordered["same_side_missed_loss"].fillna(False).astype(bool).mean()
        ),
        "direction_error_rate": float(
            ordered["direction_error"].fillna(False).astype(bool).mean()
        ),
    }


def summarize_role_months(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for (candidate, role, month), group in frame.groupby(
        ["candidate", "role", "month"],
        dropna=False,
    ):
        row = {"candidate": candidate, "role": role, "month": month}
        row.update(summarize_trade_slice(group))
        rows.append(row)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(
        ["candidate", "role", "month"],
    ).reset_index(drop=True)


def summarize_candidates(role_month: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for candidate, group in role_month.groupby("candidate", dropna=False):
        role_totals = group.groupby("role")["total_pnl"].sum()
        role_trades = group.groupby("role")["trade_count"].sum()
        trade_count = int(group["trade_count"].sum())
        long_count = int(group["long_trade_count"].sum())
        short_count = int(group["short_trade_count"].sum())
        total_pnl = float(group["total_pnl"].sum())
        row = {
            "candidate": candidate,
            "role_count": int(group["role"].nunique()),
            "month_count": int(group["month"].nunique()),
            "active_role_count": int((role_trades > 0).sum()),
            "positive_role_count": int((role_totals > 0).sum()),
            "active_months": int((group["trade_count"] > 0).sum()),
            "total_pnl": total_pnl,
            "min_role_total_pnl": float(role_totals.min()) if len(role_totals) else 0.0,
            "min_month_pnl": float(group["total_pnl"].min()),
            "trade_count": trade_count,
            "min_role_trades": int(role_trades.min()) if len(role_trades) else 0,
            "min_month_trades": int(group["trade_count"].min()),
            "max_drawdown": float(group["max_drawdown"].max()),
            "long_trade_count": long_count,
            "short_trade_count": short_count,
            "max_side_trade_share": (
                float(max(long_count, short_count) / trade_count) if trade_count else 0.0
            ),
            "capture_ev_mean": float(
                np.average(group["capture_ev_mean"], weights=group["trade_count"])
            ),
            "capture_ev_p10_min": float(group["capture_ev_p10"].min()),
            "capture_ev_p25_min": float(group["capture_ev_p25"].min()),
            "capture_ev_low2_share_mean": float(
                np.average(group["capture_ev_low2_share"], weights=group["trade_count"])
            ),
            "capture_ev_low3_share_mean": float(
                np.average(group["capture_ev_low3_share"], weights=group["trade_count"])
            ),
            "capture_factor_mean": float(
                np.average(group["capture_factor_mean"], weights=group["trade_count"])
            ),
            "capture_support_mean": float(
                np.average(group["capture_support_mean"], weights=group["trade_count"])
            ),
            "raw_ev_mae": float(np.average(group["raw_ev_mae"], weights=group["trade_count"])),
            "capture_ev_mae": float(
                np.average(group["capture_ev_mae"], weights=group["trade_count"])
            ),
            "raw_ev_bias": float(np.average(group["raw_ev_bias"], weights=group["trade_count"])),
            "capture_ev_bias": float(
                np.average(group["capture_ev_bias"], weights=group["trade_count"])
            ),
            "exit_capture_failure_rate": float(
                np.average(
                    group["exit_capture_failure_rate"],
                    weights=group["trade_count"],
                )
            ),
        }
        row["mae_delta_raw_minus_capture"] = row["raw_ev_mae"] - row["capture_ev_mae"]
        rows.append(row)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(
        ["min_role_total_pnl", "total_pnl", "capture_ev_mean"],
        ascending=[False, False, False],
    ).reset_index(drop=True)


def candidate_blockers(
    row: pd.Series,
    *,
    min_roles: int,
    min_positive_roles: int,
    min_active_roles: int,
    min_total_pnl: float,
    min_role_total_pnl: float,
    min_month_pnl: float,
    min_role_trades: int,
    min_month_trades: int,
    max_drawdown: float,
    max_side_trade_share: float,
    min_capture_ev_mean: float,
    max_capture_ev_low2_share: float,
) -> list[str]:
    checks = [
        ("roles_low", row["role_count"] >= min_roles),
        ("positive_roles_low", row["positive_role_count"] >= min_positive_roles),
        ("active_roles_low", row["active_role_count"] >= min_active_roles),
        ("total_pnl_below_floor", row["total_pnl"] >= min_total_pnl),
        ("role_total_pnl_below_floor", row["min_role_total_pnl"] >= min_role_total_pnl),
        ("month_pnl_below_floor", row["min_month_pnl"] >= min_month_pnl),
        ("role_trades_low", row["min_role_trades"] >= min_role_trades),
        ("month_trades_low", row["min_month_trades"] >= min_month_trades),
        ("drawdown_high", row["max_drawdown"] <= max_drawdown),
        ("side_share_high", row["max_side_trade_share"] <= max_side_trade_share),
        ("capture_ev_mean_low", row["capture_ev_mean"] >= min_capture_ev_mean),
        (
            "capture_ev_low2_share_high",
            row["capture_ev_low2_share_mean"] <= max_capture_ev_low2_share,
        ),
    ]
    return [label for label, ok in checks if not bool(ok)]


def apply_selector_gates(
    summary: pd.DataFrame,
    *,
    min_roles: int,
    min_positive_roles: int,
    min_active_roles: int,
    min_total_pnl: float,
    min_role_total_pnl: float,
    min_month_pnl: float,
    min_role_trades: int,
    min_month_trades: int,
    max_drawdown: float,
    max_side_trade_share: float,
    min_capture_ev_mean: float,
    max_capture_ev_low2_share: float,
) -> pd.DataFrame:
    result = summary.copy()
    blockers: list[str] = []
    eligible: list[bool] = []
    for _, row in result.iterrows():
        row_blockers = candidate_blockers(
            row,
            min_roles=min_roles,
            min_positive_roles=min_positive_roles,
            min_active_roles=min_active_roles,
            min_total_pnl=min_total_pnl,
            min_role_total_pnl=min_role_total_pnl,
            min_month_pnl=min_month_pnl,
            min_role_trades=min_role_trades,
            min_month_trades=min_month_trades,
            max_drawdown=max_drawdown,
            max_side_trade_share=max_side_trade_share,
            min_capture_ev_mean=min_capture_ev_mean,
            max_capture_ev_low2_share=max_capture_ev_low2_share,
        )
        blockers.append(";".join(row_blockers))
        eligible.append(not row_blockers)
    result["eligible"] = eligible
    result["blockers"] = blockers
    return result.sort_values(
        [
            "eligible",
            "min_role_total_pnl",
            "total_pnl",
            "min_month_pnl",
            "capture_ev_mean",
            "max_drawdown",
        ],
        ascending=[False, False, False, False, False, True],
    ).reset_index(drop=True)


def build_blocker_summary(gated: pd.DataFrame) -> pd.DataFrame:
    counts: dict[str, int] = {}
    for blockers in gated["blockers"].fillna("").astype(str):
        for blocker in [part for part in blockers.split(";") if part]:
            counts[blocker] = counts.get(blocker, 0) + 1
    return pd.DataFrame(
        [{"blocker": blocker, "candidate_count": count} for blocker, count in counts.items()]
    ).sort_values(["candidate_count", "blocker"], ascending=[False, True])


def select_policy(gated: pd.DataFrame) -> dict[str, Any]:
    eligible = gated[gated["eligible"]]
    if eligible.empty:
        return {
            "selected": "no_trade",
            "reason": "no executable-EV candidate passed NoTrade-first gates",
        }
    row = eligible.iloc[0].to_dict()
    row["selected"] = "policy"
    row["reason"] = "best eligible candidate after executable-EV ranking"
    return row


def build_diagnostics(args: argparse.Namespace) -> Path:
    trades = normalize_trade_frame(read_trade_frames(args.trades))
    validation_roles = parse_csv(args.validation_roles)
    fixed_roles = parse_csv(args.fixed_roles)
    validation = filter_roles(trades, validation_roles)
    fixed = filter_roles(trades, fixed_roles)
    if validation.empty:
        raise ValueError("no validation trades matched --validation-roles")

    validation_role_month = summarize_role_months(validation)
    validation_summary = summarize_candidates(validation_role_month)
    gated = apply_selector_gates(
        validation_summary,
        min_roles=args.min_roles if args.min_roles is not None else len(validation_roles),
        min_positive_roles=(
            args.min_positive_roles
            if args.min_positive_roles is not None
            else len(validation_roles)
        ),
        min_active_roles=(
            args.min_active_roles if args.min_active_roles is not None else len(validation_roles)
        ),
        min_total_pnl=args.min_total_pnl,
        min_role_total_pnl=args.min_role_total_pnl,
        min_month_pnl=args.min_month_pnl,
        min_role_trades=args.min_role_trades,
        min_month_trades=args.min_month_trades,
        max_drawdown=args.max_drawdown,
        max_side_trade_share=args.max_side_trade_share,
        min_capture_ev_mean=args.min_capture_ev_mean,
        max_capture_ev_low2_share=args.max_capture_ev_low2_share,
    )
    selection = select_policy(gated)

    fixed_role_month = summarize_role_months(fixed) if not fixed.empty else pd.DataFrame()
    fixed_summary = summarize_candidates(fixed_role_month) if not fixed_role_month.empty else pd.DataFrame()
    if not fixed_summary.empty:
        fixed_prefixed = fixed_summary.add_prefix("fixed_")
        fixed_prefixed = fixed_prefixed.rename(columns={"fixed_candidate": "candidate"})
        audit = gated.merge(fixed_prefixed, how="left", on="candidate")
    else:
        audit = gated.copy()

    run_dir = make_run_dir(args.output_dir, args.label)
    validation_role_month.to_csv(run_dir / "validation_role_month_executable_ev.csv", index=False)
    gated.to_csv(run_dir / "validation_candidate_executable_ev_selection.csv", index=False)
    audit.to_csv(run_dir / "candidate_fixed_audit.csv", index=False)
    if not fixed_role_month.empty:
        fixed_role_month.to_csv(run_dir / "fixed_role_month_executable_ev.csv", index=False)
    blocker_summary = build_blocker_summary(gated)
    blocker_summary.to_csv(run_dir / "blocker_summary.csv", index=False)
    (run_dir / "selected_policy.json").write_text(
        json.dumps(selection, indent=2, default=local_json_default),
        encoding="utf-8",
    )
    config = {
        "trades": args.trades,
        "validation_roles": validation_roles,
        "fixed_roles": fixed_roles,
        "min_roles": args.min_roles,
        "min_positive_roles": args.min_positive_roles,
        "min_active_roles": args.min_active_roles,
        "min_total_pnl": args.min_total_pnl,
        "min_role_total_pnl": args.min_role_total_pnl,
        "min_month_pnl": args.min_month_pnl,
        "min_role_trades": args.min_role_trades,
        "min_month_trades": args.min_month_trades,
        "max_drawdown": args.max_drawdown,
        "max_side_trade_share": args.max_side_trade_share,
        "min_capture_ev_mean": args.min_capture_ev_mean,
        "max_capture_ev_low2_share": args.max_capture_ev_low2_share,
        "selection_uses_fixed_roles": False,
    }
    (run_dir / "config.json").write_text(
        json.dumps(config, indent=2, default=local_json_default),
        encoding="utf-8",
    )

    print("Validation executable-EV selection:")
    print(
        gated[
            [
                "candidate",
                "eligible",
                "blockers",
                "total_pnl",
                "min_role_total_pnl",
                "min_month_pnl",
                "trade_count",
                "capture_ev_mean",
                "capture_ev_low2_share_mean",
                "mae_delta_raw_minus_capture",
            ]
        ].to_string(index=False)
    )
    print(f"selected: {selection['selected']} ({selection['reason']})")
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trades", type=Path, action="append", required=True)
    parser.add_argument("--validation-roles", required=True)
    parser.add_argument("--fixed-roles", default="")
    parser.add_argument("--min-roles", type=int, default=None)
    parser.add_argument("--min-positive-roles", type=int, default=None)
    parser.add_argument("--min-active-roles", type=int, default=None)
    parser.add_argument("--min-total-pnl", type=float, default=0.0)
    parser.add_argument("--min-role-total-pnl", type=float, default=0.0)
    parser.add_argument("--min-month-pnl", type=float, default=0.0)
    parser.add_argument("--min-role-trades", type=int, default=1)
    parser.add_argument("--min-month-trades", type=int, default=1)
    parser.add_argument("--max-drawdown", type=float, default=float("inf"))
    parser.add_argument("--max-side-trade-share", type=float, default=float("inf"))
    parser.add_argument("--min-capture-ev-mean", type=float, default=-float("inf"))
    parser.add_argument("--max-capture-ev-low2-share", type=float, default=float("inf"))
    parser.add_argument("--top-n", type=int, default=20)
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="entry_ev_executable_ev_selector_diagnostics")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    build_diagnostics(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
