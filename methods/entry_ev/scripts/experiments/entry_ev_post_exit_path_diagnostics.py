#!/usr/bin/env python3
"""Diagnose post-exit re-entry paths for stateful entry-EV trades."""

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

from entry_ev_supervised_shrinkage_policy_inputs import local_json_default  # noqa: E402


REQUIRED_TRADE_COLUMNS = {
    "direction",
    "entry_timestamp",
    "exit_timestamp",
    "adjusted_pnl",
    "holding_minutes",
    "entry_decision_timestamp",
    "exit_decision_timestamp",
}


def parse_float_csv(value: str) -> list[float]:
    return [float(part.strip()) for part in value.split(",") if part.strip()]


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


def trade_csv_paths(root: Path) -> list[Path]:
    if root.is_file():
        return [root]
    paths = [
        path
        for path in root.rglob("*.csv")
        if not path.name.endswith("_desired_position.csv")
    ]
    return sorted(paths)


def parse_trade_path(path: Path, root: Path) -> dict[str, str]:
    try:
        relative = path.relative_to(root)
    except ValueError:
        relative = path.name
    parts = relative.parts if isinstance(relative, Path) else (str(relative),)
    if len(parts) >= 4:
        return {
            "family": parts[-4],
            "variant": parts[-3],
            "candidate": parts[-2],
            "month": Path(parts[-1]).stem[:7],
        }
    return {
        "family": "__unknown__",
        "variant": "__unknown__",
        "candidate": "__unknown__",
        "month": path.stem[:7],
    }


def read_trade_csv(label: str, root: Path, path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    missing = sorted(REQUIRED_TRADE_COLUMNS - set(frame.columns))
    if missing:
        raise ValueError(f"{path} missing trade columns: {', '.join(missing)}")
    meta = parse_trade_path(path, root)
    output = frame.copy()
    output.insert(0, "source", label)
    output.insert(1, "trade_file", str(path))
    for column, value in meta.items():
        output[column] = value
    return output


def load_trades(pairs: list[tuple[str, Path]]) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for label, root in pairs:
        for path in trade_csv_paths(root):
            frame = read_trade_csv(label, root, path)
            if not frame.empty:
                frames.append(frame)
    if not frames:
        raise ValueError("no trade rows found")
    return pd.concat(frames, ignore_index=True)


def numeric_series(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    values = pd.to_numeric(frame[column], errors="coerce")
    return values.replace([np.inf, -np.inf], np.nan).fillna(default).astype(float)


def enrich_trade_sequence(frame: pd.DataFrame, *, large_loss_threshold: float) -> pd.DataFrame:
    output = frame.copy()
    for column in [
        "entry_timestamp",
        "exit_timestamp",
        "entry_decision_timestamp",
        "exit_decision_timestamp",
    ]:
        output[column] = pd.to_datetime(output[column], utc=True, errors="coerce")
    output["adjusted_pnl"] = numeric_series(output, "adjusted_pnl")
    output["holding_minutes"] = numeric_series(output, "holding_minutes")
    output["direction"] = output["direction"].astype(str).str.lower()
    output = output.sort_values(
        ["source", "family", "variant", "candidate", "month", "entry_decision_timestamp"]
    ).reset_index(drop=True)
    group_columns = ["source", "family", "variant", "candidate", "month"]
    grouped = output.groupby(group_columns, dropna=False)
    output["trade_index_in_month"] = grouped.cumcount() + 1
    output["prev_adjusted_pnl"] = grouped["adjusted_pnl"].shift(1)
    output["prev_direction"] = grouped["direction"].shift(1)
    output["prev_exit_timestamp"] = grouped["exit_timestamp"].shift(1)
    output["prev_exit_decision_timestamp"] = grouped["exit_decision_timestamp"].shift(1)
    output["minutes_since_prev_exit"] = (
        output["entry_timestamp"] - output["prev_exit_timestamp"]
    ).dt.total_seconds() / 60.0
    output["decision_minutes_since_prev_exit"] = (
        output["entry_decision_timestamp"] - output["prev_exit_decision_timestamp"]
    ).dt.total_seconds() / 60.0
    output["is_loss"] = output["adjusted_pnl"].lt(0.0)
    output["is_large_loss"] = output["adjusted_pnl"].le(large_loss_threshold)
    output["prev_was_loss"] = output["prev_adjusted_pnl"].lt(0.0)
    output["prev_was_large_loss"] = output["prev_adjusted_pnl"].le(large_loss_threshold)
    output["same_side_as_prev"] = output["direction"].eq(output["prev_direction"])
    output["post_exit_gap_bucket"] = pd.cut(
        output["decision_minutes_since_prev_exit"],
        bins=[-np.inf, 15, 30, 60, 120, 240, 1440, np.inf],
        labels=["<=15", "15-30", "30-60", "60-120", "120-240", "240-1440", ">1440"],
    ).astype("string").fillna("first")
    output["prev_result_bucket"] = np.select(
        [
            output["prev_adjusted_pnl"].isna(),
            output["prev_adjusted_pnl"].lt(0.0),
            output["prev_adjusted_pnl"].ge(0.0),
        ],
        ["first", "prev_loss", "prev_non_loss"],
        default="unknown",
    )
    return output


def summarize_group(frame: pd.DataFrame, group_columns: list[str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for key, group in frame.groupby(group_columns, dropna=False):
        if not isinstance(key, tuple):
            key = (key,)
        row = dict(zip(group_columns, key))
        pnl = group["adjusted_pnl"].astype(float)
        row.update(
            {
                "trade_count": int(len(group)),
                "total_pnl": float(pnl.sum()),
                "avg_pnl": float(pnl.mean()) if len(group) else 0.0,
                "loss_count": int(pnl.lt(0.0).sum()),
                "large_loss_count": int(group["is_large_loss"].astype(bool).sum()),
                "loss_pnl": float(pnl[pnl < 0.0].sum()),
                "win_pnl": float(pnl[pnl >= 0.0].sum()),
                "min_trade_pnl": float(pnl.min()) if len(group) else 0.0,
                "avg_holding_minutes": float(group["holding_minutes"].astype(float).mean())
                if len(group)
                else 0.0,
            }
        )
        rows.append(row)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(["total_pnl", "trade_count"], ascending=[True, False])


def cooldown_grid_summary(
    trades: pd.DataFrame,
    *,
    cooldown_minutes: list[float],
    prev_loss_thresholds: list[float],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    total_pnl = float(trades["adjusted_pnl"].sum())
    total_trades = int(len(trades))
    for threshold in prev_loss_thresholds:
        for minutes in cooldown_minutes:
            flagged = (
                trades["prev_adjusted_pnl"].le(threshold)
                & trades["decision_minutes_since_prev_exit"].le(minutes)
                & trades["decision_minutes_since_prev_exit"].ge(0.0)
            )
            flagged_trades = trades[flagged].copy()
            flagged_pnl = float(flagged_trades["adjusted_pnl"].sum())
            rows.append(
                {
                    "prev_loss_threshold": float(threshold),
                    "cooldown_minutes": float(minutes),
                    "trade_count": total_trades,
                    "total_pnl": total_pnl,
                    "flagged_trade_count": int(flagged.sum()),
                    "flagged_pnl": flagged_pnl,
                    "kept_pnl_if_removed_no_replacement": float(total_pnl - flagged_pnl),
                    "delta_if_removed_no_replacement": float(-flagged_pnl),
                    "flagged_loss_count": int(flagged_trades["adjusted_pnl"].lt(0.0).sum()),
                    "flagged_large_loss_count": int(
                        flagged_trades["is_large_loss"].astype(bool).sum()
                    ),
                    "flagged_same_side_share": float(
                        flagged_trades["same_side_as_prev"].astype(float).mean()
                    )
                    if len(flagged_trades)
                    else 0.0,
                }
            )
    return pd.DataFrame(rows).sort_values(
        ["delta_if_removed_no_replacement", "flagged_trade_count"],
        ascending=[False, False],
    ).reset_index(drop=True)


def monthly_cooldown_summary(
    trades: pd.DataFrame,
    *,
    cooldown_minutes: list[float],
    prev_loss_thresholds: list[float],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    group_columns = ["source", "family", "variant", "candidate", "month"]
    for key, group in trades.groupby(group_columns, dropna=False):
        source, family, variant, candidate, month = key
        grid = cooldown_grid_summary(
            group,
            cooldown_minutes=cooldown_minutes,
            prev_loss_thresholds=prev_loss_thresholds,
        )
        for row in grid.to_dict("records"):
            row.update(
                {
                    "source": source,
                    "family": family,
                    "variant": variant,
                    "candidate": candidate,
                    "month": month,
                }
            )
            rows.append(row)
    return pd.DataFrame(rows)


def run_diagnostics(args: argparse.Namespace) -> Path:
    trade_roots = parse_labeled_paths(args.trade_root)
    cooldown_minutes = parse_float_csv(args.cooldown_minutes)
    prev_loss_thresholds = parse_float_csv(args.prev_loss_thresholds)
    raw_trades = load_trades(trade_roots)
    trades = enrich_trade_sequence(raw_trades, large_loss_threshold=args.large_loss_threshold)

    run_dir = make_run_dir(args.output_dir, args.label)
    trades.to_csv(run_dir / "post_exit_path_trades.csv", index=False)
    summarize_group(
        trades,
        ["source", "family", "variant", "candidate", "month"],
    ).to_csv(run_dir / "post_exit_month_summary.csv", index=False)
    summarize_group(
        trades,
        ["source", "family", "variant", "candidate", "prev_result_bucket", "post_exit_gap_bucket"],
    ).to_csv(run_dir / "post_exit_gap_summary.csv", index=False)
    summarize_group(
        trades,
        ["source", "family", "variant", "candidate", "prev_result_bucket", "same_side_as_prev"],
    ).to_csv(run_dir / "post_exit_prev_result_side_summary.csv", index=False)
    cooldown = cooldown_grid_summary(
        trades,
        cooldown_minutes=cooldown_minutes,
        prev_loss_thresholds=prev_loss_thresholds,
    )
    cooldown.to_csv(run_dir / "post_exit_cooldown_grid_summary.csv", index=False)
    monthly_cooldown_summary(
        trades,
        cooldown_minutes=cooldown_minutes,
        prev_loss_thresholds=prev_loss_thresholds,
    ).to_csv(run_dir / "post_exit_monthly_cooldown_summary.csv", index=False)
    config = {
        "trade_root": trade_roots,
        "cooldown_minutes": cooldown_minutes,
        "prev_loss_thresholds": prev_loss_thresholds,
        "large_loss_threshold": args.large_loss_threshold,
    }
    (run_dir / "config.json").write_text(
        json.dumps(config, indent=2, default=local_json_default),
        encoding="utf-8",
    )

    print("Post-exit cooldown grid summary:")
    print(
        cooldown[
            [
                "prev_loss_threshold",
                "cooldown_minutes",
                "flagged_trade_count",
                "flagged_pnl",
                "kept_pnl_if_removed_no_replacement",
                "delta_if_removed_no_replacement",
                "flagged_loss_count",
            ]
        ]
        .head(args.print_top)
        .to_string(index=False)
    )
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trade-root", action="append", required=True)
    parser.add_argument("--cooldown-minutes", default="15,30,60,120,240,1440")
    parser.add_argument("--prev-loss-thresholds", default="0,-1,-2")
    parser.add_argument("--large-loss-threshold", type=float, default=-2.0)
    parser.add_argument("--print-top", type=int, default=12)
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="entry_ev_post_exit_path_diagnostics")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_diagnostics(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
