#!/usr/bin/env python3
"""Replay hold-extension decisions on the realized base trade path."""

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


DEFAULT_THRESHOLDS = "5,10"
DEFAULT_APPLY_UNIVERSES = "isolated_large_loss"
DEFAULT_HORIZON_MODES = "predicted"
DEFAULT_GROUP_COLUMNS = [
    "source",
    "role",
    "family",
    "variant",
    "candidate",
    "month",
]
REQUIRED_COLUMNS = {
    "source",
    "role",
    "family",
    "variant",
    "candidate",
    "month",
    "direction",
    "entry_timestamp",
    "exit_timestamp",
    "entry_price",
    "exit_price",
    "raw_pnl",
    "adjusted_pnl",
    "holding_minutes",
    "exit_reason",
    "entry_decision_timestamp",
    "exit_decision_timestamp",
    "pred_hold_extension_best_delta",
    "pred_hold_extension_best_horizon_minutes",
}
TRADE_COLUMNS = [
    "direction",
    "entry_timestamp",
    "exit_timestamp",
    "entry_price",
    "exit_price",
    "raw_pnl",
    "adjusted_pnl",
    "holding_minutes",
    "exit_reason",
    "entry_decision_timestamp",
    "exit_decision_timestamp",
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


def parse_float_csv(value: str) -> list[float]:
    return [float(part) for part in parse_csv(value)]


def numeric_series(frame: pd.DataFrame, column: str, default: float = np.nan) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    values = pd.to_numeric(frame[column], errors="coerce")
    return values.replace([np.inf, -np.inf], np.nan).fillna(default).astype(float)


def bool_series(frame: pd.DataFrame, column: str, default: bool = False) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=bool)
    series = frame[column]
    if pd.api.types.is_bool_dtype(series):
        return series.fillna(default).astype(bool)
    if pd.api.types.is_numeric_dtype(series):
        return series.fillna(float(default)).astype(float).ne(0.0)
    return series.astype(str).str.strip().str.lower().isin({"true", "1", "yes", "y"})


def read_scored_trades(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    missing = sorted(REQUIRED_COLUMNS - set(frame.columns))
    if missing:
        raise ValueError(f"{path} missing columns: {', '.join(missing)}")
    output = frame.copy()
    for column in [
        "entry_timestamp",
        "exit_timestamp",
        "entry_decision_timestamp",
        "exit_decision_timestamp",
    ]:
        output[column] = pd.to_datetime(output[column], utc=True, errors="coerce")
    for column in DEFAULT_GROUP_COLUMNS:
        output[column] = output[column].astype(str)
    output["month"] = output["month"].astype(str).str.slice(0, 7)
    output["direction"] = output["direction"].astype(str).str.lower()
    for column in [
        "entry_price",
        "exit_price",
        "raw_pnl",
        "adjusted_pnl",
        "holding_minutes",
        "pred_hold_extension_best_delta",
        "pred_hold_extension_best_horizon_minutes",
    ]:
        output[column] = numeric_series(output, column, default=np.nan)
    return output.sort_values(DEFAULT_GROUP_COLUMNS + ["entry_decision_timestamp"]).reset_index(
        drop=True
    )


def universe_mask(frame: pd.DataFrame, universe: str) -> pd.Series:
    for suffix, side in (("_long", "long"), ("_short", "short")):
        if universe.endswith(suffix):
            base_universe = universe[: -len(suffix)]
            if not base_universe:
                raise ValueError(f"unknown universe: {universe}")
            return universe_mask(frame, base_universe) & frame["direction"].astype(str).eq(side)
    if universe == "all":
        return pd.Series(True, index=frame.index, dtype=bool)
    if universe == "loss":
        return numeric_series(frame, "adjusted_pnl", default=0.0).lt(0.0)
    if universe == "large_loss":
        return bool_series(frame, "is_large_loss")
    if universe == "isolated":
        return bool_series(frame, "isolated_context")
    if universe == "isolated_loss":
        return bool_series(frame, "isolated_context") & numeric_series(
            frame,
            "adjusted_pnl",
            default=0.0,
        ).lt(0.0)
    if universe == "isolated_large_loss":
        return bool_series(frame, "isolated_large_loss")
    if universe == "isolated_exit_capture_failure":
        return bool_series(frame, "isolated_exit_capture_failure")
    if universe == "isolated_large_loss_capture_failure":
        return bool_series(frame, "isolated_large_loss_capture_failure")
    raise ValueError(f"unknown universe: {universe}")


def parse_horizon_modes(value: str) -> list[str]:
    modes = parse_csv(value)
    if not modes:
        raise argparse.ArgumentTypeError("at least one horizon mode is required")
    normalized: list[str] = []
    for mode in modes:
        text = mode.strip().lower()
        if text == "predicted":
            normalized.append(text)
            continue
        try:
            horizon = int(text)
        except ValueError as exc:
            raise argparse.ArgumentTypeError(
                "horizon modes must be 'predicted' or fixed minute integers"
            ) from exc
        if horizon <= 0:
            raise argparse.ArgumentTypeError("fixed horizon modes must be positive")
        normalized.append(str(horizon))
    return normalized


def horizon_and_score(row: pd.Series, horizon_mode: str) -> tuple[int, float, str]:
    if horizon_mode == "predicted":
        return (
            int(row["pred_hold_extension_best_horizon_minutes"]),
            float(row["pred_hold_extension_best_delta"]),
            "pred_hold_extension_best_delta",
        )
    horizon = int(horizon_mode)
    score_column = f"pred_hold_extension_delta_{horizon}m"
    if score_column not in row.index:
        raise ValueError(f"missing fixed-horizon score column: {score_column}")
    return horizon, float(row[score_column]), score_column


def horizon_model_used(row: pd.Series, horizon_minutes: int) -> bool:
    column = f"pred_hold_extension_model_used_{int(horizon_minutes)}m"
    if column not in row.index:
        return False
    value = row[column]
    if pd.isna(value):
        return False
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (int, float, np.integer, np.floating)):
        return bool(float(value))
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def raw_from_adjusted(adjusted_pnl: float, *, profit_multiplier: float, loss_multiplier: float) -> float:
    if adjusted_pnl > 0:
        return adjusted_pnl / profit_multiplier if profit_multiplier != 0 else adjusted_pnl
    if adjusted_pnl < 0:
        return adjusted_pnl / loss_multiplier if loss_multiplier != 0 else adjusted_pnl
    return 0.0


def extended_trade_row(
    row: pd.Series,
    *,
    horizon_minutes: int,
    predicted_score: float,
    score_column: str,
    horizon_mode: str,
    profit_multiplier: float,
    loss_multiplier: float,
) -> dict[str, Any]:
    fixed_column = f"actual_taken_fixed_{horizon_minutes}m_adjusted_pnl"
    if fixed_column not in row.index:
        raise ValueError(f"missing fixed horizon column: {fixed_column}")
    adjusted = float(row[fixed_column])
    raw = raw_from_adjusted(
        adjusted,
        profit_multiplier=profit_multiplier,
        loss_multiplier=loss_multiplier,
    )
    direction_sign = 1 if str(row["direction"]).lower() == "long" else -1
    entry_price = float(row["entry_price"])
    exit_price = entry_price + direction_sign * raw
    entry_timestamp = pd.Timestamp(row["entry_timestamp"])
    exit_timestamp = entry_timestamp + pd.Timedelta(minutes=int(horizon_minutes))
    return {
        **{column: row.get(column) for column in DEFAULT_GROUP_COLUMNS},
        "direction": str(row["direction"]).lower(),
        "entry_timestamp": entry_timestamp,
        "exit_timestamp": exit_timestamp,
        "entry_price": entry_price,
        "exit_price": float(exit_price),
        "raw_pnl": float(raw),
        "adjusted_pnl": adjusted,
        "holding_minutes": float(
            (exit_timestamp - entry_timestamp) / pd.Timedelta(minutes=1)
        ),
        "exit_reason": f"hold_extension_{horizon_minutes}m",
        "entry_decision_timestamp": pd.Timestamp(row["entry_decision_timestamp"]),
        "exit_decision_timestamp": exit_timestamp - pd.Timedelta(minutes=1),
        "base_adjusted_pnl": float(row["adjusted_pnl"]),
        "base_exit_timestamp": pd.Timestamp(row["exit_timestamp"]),
        "base_exit_decision_timestamp": pd.Timestamp(row["exit_decision_timestamp"]),
        "hold_extension_applied": True,
        "hold_extension_horizon_mode": horizon_mode,
        "hold_extension_horizon_minutes": int(horizon_minutes),
        "hold_extension_score_column": score_column,
        "hold_extension_pred_delta": float(predicted_score),
        "hold_extension_delta_vs_base": float(adjusted - float(row["adjusted_pnl"])),
    }


def base_trade_row(row: pd.Series) -> dict[str, Any]:
    return {
        **{column: row.get(column) for column in DEFAULT_GROUP_COLUMNS},
        **{column: row.get(column) for column in TRADE_COLUMNS},
        "base_adjusted_pnl": float(row["adjusted_pnl"]),
        "base_exit_timestamp": pd.Timestamp(row["exit_timestamp"]),
        "base_exit_decision_timestamp": pd.Timestamp(row["exit_decision_timestamp"]),
        "hold_extension_applied": False,
        "hold_extension_horizon_mode": "none",
        "hold_extension_horizon_minutes": 0,
        "hold_extension_score_column": "pred_hold_extension_best_delta",
        "hold_extension_pred_delta": float(row["pred_hold_extension_best_delta"]),
        "hold_extension_delta_vs_base": 0.0,
    }


def replay_group(
    group: pd.DataFrame,
    *,
    apply_mask: pd.Series,
    threshold: float,
    horizon_mode: str,
    require_model_used: bool,
    profit_multiplier: float,
    loss_multiplier: float,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    output_rows: list[dict[str, Any]] = []
    skipped_rows: list[dict[str, Any]] = []
    occupied_until: pd.Timestamp | None = None
    ordered = group.sort_values("entry_decision_timestamp")
    for index, row in ordered.iterrows():
        entry_timestamp = pd.Timestamp(row["entry_timestamp"])
        if occupied_until is not None and entry_timestamp < occupied_until:
            skipped = row.to_dict()
            skipped["skipped_by_occupied_until"] = occupied_until
            skipped_rows.append(skipped)
            continue

        horizon, predicted_score, score_column = horizon_and_score(row, horizon_mode)
        extension_exit = entry_timestamp + pd.Timedelta(minutes=horizon)
        model_used = horizon_model_used(row, horizon)
        can_extend = (
            bool(apply_mask.loc[index])
            and np.isfinite(predicted_score)
            and predicted_score >= threshold
            and (not require_model_used or model_used)
            and horizon > 0
            and f"actual_taken_fixed_{horizon}m_adjusted_pnl" in row.index
            and pd.notna(row[f"actual_taken_fixed_{horizon}m_adjusted_pnl"])
            and extension_exit > pd.Timestamp(row["exit_timestamp"])
        )
        if can_extend:
            output = extended_trade_row(
                row,
                horizon_minutes=horizon,
                predicted_score=predicted_score,
                score_column=score_column,
                horizon_mode=horizon_mode,
                profit_multiplier=profit_multiplier,
                loss_multiplier=loss_multiplier,
            )
        else:
            output = base_trade_row(row)
        output_rows.append(output)
        occupied_until = pd.Timestamp(output["exit_timestamp"])
    return output_rows, skipped_rows


def max_drawdown_from_trades(trades: pd.DataFrame) -> float:
    if trades.empty:
        return 0.0
    ordered = trades.sort_values("exit_timestamp")
    equity = ordered["adjusted_pnl"].astype(float).cumsum()
    running_max = equity.cummax().clip(lower=0.0)
    drawdown = running_max - equity
    return float(drawdown.max()) if len(drawdown) else 0.0


def summarize_stateful(
    trades: pd.DataFrame,
    *,
    base: pd.DataFrame,
    skipped: pd.DataFrame,
    group_columns: list[str],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    grouped_keys = base[group_columns].drop_duplicates()
    for _, key_row in grouped_keys.iterrows():
        mask = pd.Series(True, index=base.index)
        trade_mask = pd.Series(True, index=trades.index)
        skipped_mask = pd.Series(True, index=skipped.index) if not skipped.empty else pd.Series(dtype=bool)
        for column in group_columns:
            mask &= base[column].astype(str).eq(str(key_row[column]))
            trade_mask &= trades[column].astype(str).eq(str(key_row[column]))
            if not skipped.empty:
                skipped_mask &= skipped[column].astype(str).eq(str(key_row[column]))
        base_group = base[mask]
        trade_group = trades[trade_mask]
        skipped_group = skipped[skipped_mask] if not skipped.empty else skipped
        long_count = int(trade_group["direction"].astype(str).eq("long").sum()) if len(trade_group) else 0
        short_count = int(trade_group["direction"].astype(str).eq("short").sum()) if len(trade_group) else 0
        trade_count = int(len(trade_group))
        rows.append(
            {
                **{column: key_row[column] for column in group_columns},
                "base_trade_count": int(len(base_group)),
                "base_total_adjusted_pnl": float(base_group["adjusted_pnl"].astype(float).sum()),
                "trade_count": trade_count,
                "total_adjusted_pnl": float(trade_group["adjusted_pnl"].astype(float).sum())
                if trade_count
                else 0.0,
                "pnl_delta_vs_base": float(
                    trade_group["adjusted_pnl"].astype(float).sum()
                    - base_group["adjusted_pnl"].astype(float).sum()
                )
                if trade_count
                else float(-base_group["adjusted_pnl"].astype(float).sum()),
                "extended_trade_count": int(
                    trade_group["hold_extension_applied"].astype(bool).sum()
                )
                if trade_count
                else 0,
                "extension_delta_vs_base_sum": float(
                    trade_group["hold_extension_delta_vs_base"].astype(float).sum()
                )
                if trade_count
                else 0.0,
                "skipped_trade_count": int(len(skipped_group)),
                "skipped_adjusted_pnl": float(skipped_group["adjusted_pnl"].astype(float).sum())
                if len(skipped_group)
                else 0.0,
                "long_trade_count": long_count,
                "short_trade_count": short_count,
                "max_side_trade_share": float(max(long_count, short_count) / trade_count)
                if trade_count
                else 0.0,
                "max_drawdown": max_drawdown_from_trades(trade_group),
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["total_adjusted_pnl", "pnl_delta_vs_base"],
        ascending=[True, True],
    )


def summarize_selection(monthly: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if monthly.empty:
        return pd.DataFrame()
    monthly = monthly.copy()
    if "horizon_mode" not in monthly.columns:
        monthly["horizon_mode"] = "predicted"
    for key, group in monthly.groupby(["apply_universe", "threshold", "horizon_mode"], dropna=False):
        apply_universe, threshold, horizon_mode = key
        role_group = group.groupby("role", dropna=False).agg(
            role_total_pnl=("total_adjusted_pnl", "sum"),
            role_trade_count=("trade_count", "sum"),
        )
        rows.append(
            {
                "apply_universe": apply_universe,
                "threshold": float(threshold),
                "horizon_mode": horizon_mode,
                "total_adjusted_pnl_sum": float(group["total_adjusted_pnl"].sum()),
                "base_total_adjusted_pnl_sum": float(group["base_total_adjusted_pnl"].sum()),
                "pnl_delta_vs_base_sum": float(group["pnl_delta_vs_base"].sum()),
                "trade_count_sum": int(group["trade_count"].sum()),
                "base_trade_count_sum": int(group["base_trade_count"].sum()),
                "extended_trade_count_sum": int(group["extended_trade_count"].sum()),
                "skipped_trade_count_sum": int(group["skipped_trade_count"].sum()),
                "skipped_adjusted_pnl_sum": float(group["skipped_adjusted_pnl"].sum()),
                "month_pnl_min": float(group["total_adjusted_pnl"].min()),
                "role_total_pnl_min": float(role_group["role_total_pnl"].min())
                if len(role_group)
                else 0.0,
                "positive_role_count": int((role_group["role_total_pnl"] > 0).sum())
                if len(role_group)
                else 0,
                "role_count": int(len(role_group)),
                "max_side_trade_share": float(group["max_side_trade_share"].max()),
                "max_drawdown_max": float(group["max_drawdown"].max()),
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["month_pnl_min", "total_adjusted_pnl_sum"],
        ascending=[False, False],
    )


def selector_compatible_monthly_metrics(monthly: pd.DataFrame) -> pd.DataFrame:
    if monthly.empty:
        return pd.DataFrame()
    output = monthly.copy()
    if "horizon_mode" not in output.columns:
        output["horizon_mode"] = "predicted"
    threshold_label = (
        output["threshold"].astype(float).map(lambda value: f"{value:g}".replace(".", "p"))
    )
    output["variant"] = (
        output["variant"].astype(str)
        + "__holdext_"
        + output["apply_universe"].astype(str)
        + "_t"
        + threshold_label
        + "_h"
        + output["horizon_mode"].astype(str)
    )
    return output


def replay_stateful_extensions(args: argparse.Namespace) -> Path:
    scored = read_scored_trades(args.scored_trades)
    thresholds = parse_float_csv(args.thresholds)
    apply_universes = parse_csv(args.apply_universes)
    horizon_modes = parse_horizon_modes(args.horizon_modes)
    group_columns = DEFAULT_GROUP_COLUMNS
    run_dir = make_run_dir(args.output_dir, args.label)
    monthly_frames: list[pd.DataFrame] = []
    selection_frames: list[pd.DataFrame] = []
    all_trade_frames: list[pd.DataFrame] = []
    all_skipped_frames: list[pd.DataFrame] = []

    for universe in apply_universes:
        mask = universe_mask(scored, universe)
        for threshold in thresholds:
            for horizon_mode in horizon_modes:
                trade_rows: list[dict[str, Any]] = []
                skipped_rows: list[dict[str, Any]] = []
                for _, group in scored.groupby(group_columns, dropna=False, sort=False):
                    group_trades, group_skipped = replay_group(
                        group,
                        apply_mask=mask,
                        threshold=threshold,
                        horizon_mode=horizon_mode,
                        require_model_used=args.require_model_used,
                        profit_multiplier=args.profit_multiplier,
                        loss_multiplier=args.loss_multiplier,
                    )
                    trade_rows.extend(group_trades)
                    skipped_rows.extend(group_skipped)
                trades = pd.DataFrame(trade_rows)
                skipped = pd.DataFrame(skipped_rows)
                for frame in (trades, skipped):
                    if frame.empty:
                        continue
                    frame["apply_universe"] = universe
                    frame["threshold"] = float(threshold)
                    frame["horizon_mode"] = horizon_mode
                monthly = summarize_stateful(
                    trades,
                    base=scored,
                    skipped=skipped,
                    group_columns=group_columns,
                )
                monthly["apply_universe"] = universe
                monthly["threshold"] = float(threshold)
                monthly["horizon_mode"] = horizon_mode
                monthly_frames.append(monthly)
                selection_frames.append(summarize_selection(monthly))
                all_trade_frames.append(trades)
                if not skipped.empty:
                    all_skipped_frames.append(skipped)

    stateful_trades = (
        pd.concat(all_trade_frames, ignore_index=True) if all_trade_frames else pd.DataFrame()
    )
    skipped_trades = (
        pd.concat(all_skipped_frames, ignore_index=True) if all_skipped_frames else pd.DataFrame()
    )
    monthly_summary = (
        pd.concat(monthly_frames, ignore_index=True) if monthly_frames else pd.DataFrame()
    )
    selection_summary = (
        pd.concat(selection_frames, ignore_index=True) if selection_frames else pd.DataFrame()
    )
    selector_monthly = selector_compatible_monthly_metrics(monthly_summary)

    stateful_trades.to_csv(run_dir / "hold_extension_stateful_trades.csv", index=False)
    skipped_trades.to_csv(run_dir / "hold_extension_stateful_skipped_trades.csv", index=False)
    monthly_summary.to_csv(run_dir / "hold_extension_stateful_monthly_summary.csv", index=False)
    selection_summary.to_csv(run_dir / "hold_extension_stateful_selection_summary.csv", index=False)
    selector_monthly.to_csv(
        run_dir / "hold_extension_stateful_selector_monthly_metrics.csv",
        index=False,
    )

    config = {
        "scored_trades": args.scored_trades,
        "thresholds": thresholds,
        "apply_universes": apply_universes,
        "horizon_modes": horizon_modes,
        "require_model_used": args.require_model_used,
        "profit_multiplier": args.profit_multiplier,
        "loss_multiplier": args.loss_multiplier,
        "group_columns": group_columns,
    }
    (run_dir / "config.json").write_text(
        json.dumps(config, indent=2, default=local_json_default),
        encoding="utf-8",
    )

    print("Stateful hold-extension selection summary:")
    print(
        selection_summary[
            [
                "apply_universe",
                "threshold",
                "horizon_mode",
                "total_adjusted_pnl_sum",
                "pnl_delta_vs_base_sum",
                "month_pnl_min",
                "role_total_pnl_min",
                "extended_trade_count_sum",
                "skipped_trade_count_sum",
                "skipped_adjusted_pnl_sum",
            ]
        ]
        .head(args.print_top)
        .to_string(index=False)
    )
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scored-trades", type=Path, required=True)
    parser.add_argument("--thresholds", default=DEFAULT_THRESHOLDS)
    parser.add_argument("--apply-universes", default=DEFAULT_APPLY_UNIVERSES)
    parser.add_argument("--horizon-modes", default=DEFAULT_HORIZON_MODES)
    parser.add_argument("--require-model-used", action="store_true")
    parser.add_argument("--profit-multiplier", type=float, default=1.0)
    parser.add_argument("--loss-multiplier", type=float, default=1.2)
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="entry_ev_hold_extension_stateful_replay")
    parser.add_argument("--print-top", type=int, default=20)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    replay_stateful_extensions(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
