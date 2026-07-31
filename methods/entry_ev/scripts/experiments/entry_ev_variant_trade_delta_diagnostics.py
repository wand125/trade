#!/usr/bin/env python3
"""Compare two variants inside an entry-EV policy replay run."""

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

from trade_data.backtest import (  # noqa: E402
    TRADE_COLUMNS,
    add_trade_delta_blocking_diagnostics,
    build_trade_delta_frame,
    json_default,
    make_run_dir,
    read_trades_csv,
    stateful_candidate_examples_from_delta,
    trade_delta_blocking_group_summary,
    trade_delta_group_summary,
)

from entry_ev_direction_residual_loss_diagnostics import parse_csv  # noqa: E402


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


def monthly_metrics_path(run_dir: Path) -> Path:
    candidates = [
        run_dir / "monthly_exit_timing_metrics.csv",
        run_dir / "monthly_policy_metrics.csv",
        run_dir / "monthly_hold_cap_metrics.csv",
    ]
    for path in candidates:
        if path.exists():
            return path
    raise FileNotFoundError(
        "run directory does not contain a supported monthly metrics CSV: "
        f"{run_dir}"
    )


def read_monthly_metrics(run_dir: Path) -> pd.DataFrame:
    path = monthly_metrics_path(run_dir)
    frame = pd.read_csv(path)
    required = {"family", "role", "month", "candidate", "variant"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"{path} missing columns: {', '.join(missing)}")
    frame = frame.copy()
    frame["family"] = frame["family"].astype(str)
    frame["role"] = frame["role"].astype(str)
    frame["month"] = frame["month"].astype(str).str.slice(0, 7)
    frame["candidate"] = frame["candidate"].astype(str)
    frame["variant"] = frame["variant"].astype(str)
    return frame


def filter_monthly(
    frame: pd.DataFrame,
    *,
    variant: str,
    candidates: set[str],
    families: set[str],
    months: set[str],
) -> pd.DataFrame:
    output = frame[frame["variant"].eq(variant)].copy()
    if candidates:
        output = output[output["candidate"].isin(candidates)].copy()
    if families:
        output = output[output["family"].isin(families)].copy()
    if months:
        output = output[output["month"].isin(months)].copy()
    return output.reset_index(drop=True)


def monthly_key(row: pd.Series) -> tuple[str, str, str]:
    return (str(row["family"]), str(row["month"]), str(row["candidate"]))


def ensure_trade_frame_columns(frame: pd.DataFrame) -> pd.DataFrame:
    output = frame.copy()
    for column in TRADE_COLUMNS:
        if column not in output.columns:
            output[column] = pd.Series(dtype="object")
    return output


def trade_path(run_dir: Path, row: pd.Series) -> Path:
    return (
        run_dir
        / "trades"
        / str(row["family"])
        / str(row["variant"])
        / str(row["candidate"])
        / f"{row['month']}.csv"
    )


def read_month_trades(run_dir: Path, row: pd.Series) -> pd.DataFrame:
    path = trade_path(run_dir, row)
    if not path.exists():
        raise FileNotFoundError(f"missing trade file: {path}")
    trades = ensure_trade_frame_columns(read_trades_csv(path))
    trades["family"] = str(row["family"])
    trades["role"] = str(row["role"])
    trades["month"] = str(row["month"])
    trades["candidate"] = str(row["candidate"])
    trades["variant"] = str(row["variant"])
    return trades


def build_variant_delta(
    *,
    run_dir: Path,
    base_variant: str,
    candidate_variant: str,
    candidates: set[str],
    families: set[str],
    months: set[str],
) -> pd.DataFrame:
    monthly = read_monthly_metrics(run_dir)
    base_monthly = filter_monthly(
        monthly,
        variant=base_variant,
        candidates=candidates,
        families=families,
        months=months,
    )
    candidate_monthly = filter_monthly(
        monthly,
        variant=candidate_variant,
        candidates=candidates,
        families=families,
        months=months,
    )
    candidate_lookup = {monthly_key(row): row for _, row in candidate_monthly.iterrows()}
    missing = [
        key for _, row in base_monthly.iterrows() if (key := monthly_key(row)) not in candidate_lookup
    ]
    if missing:
        preview = ", ".join("/".join(key) for key in missing[:5])
        suffix = "" if len(missing) <= 5 else f" ... ({len(missing)} missing)"
        raise ValueError(f"candidate variant monthly rows missing: {preview}{suffix}")

    frames: list[pd.DataFrame] = []
    for _, base_row in base_monthly.iterrows():
        key = monthly_key(base_row)
        candidate_row = candidate_lookup[key]
        base_trades = read_month_trades(run_dir, base_row)
        candidate_trades = read_month_trades(run_dir, candidate_row)
        if base_trades.empty and candidate_trades.empty:
            continue
        delta = build_trade_delta_frame(base_trades, candidate_trades)
        delta["family"] = key[0]
        delta["month"] = key[1]
        delta["candidate"] = key[2]
        delta["base_variant"] = base_variant
        delta["candidate_variant"] = candidate_variant
        delta["base_role"] = str(base_row["role"])
        delta["candidate_role"] = str(candidate_row["role"])
        frames.append(delta)
    if not frames:
        return pd.DataFrame()
    normalized_frames = [frame.dropna(axis=1, how="all") for frame in frames]
    return pd.concat(normalized_frames, ignore_index=True)


def write_summary(
    delta: pd.DataFrame,
    run_dir: Path,
    *,
    group_name: str,
    group_columns: list[str],
) -> pd.DataFrame:
    if delta.empty:
        summary = pd.DataFrame()
    else:
        summary = trade_delta_group_summary(delta, group_columns)
    summary.to_csv(run_dir / f"group_by_{group_name}.csv", index=False)
    return summary


def write_blocking_summary(
    delta: pd.DataFrame,
    run_dir: Path,
    *,
    group_name: str,
    group_columns: list[str],
) -> pd.DataFrame:
    if delta.empty:
        summary = pd.DataFrame()
    else:
        summary = trade_delta_blocking_group_summary(delta, group_columns)
    summary.to_csv(run_dir / f"group_by_{group_name}.csv", index=False)
    return summary


def run_variant_delta(args: argparse.Namespace) -> Path:
    candidates = set(parse_csv(args.candidates))
    families = set(parse_csv(args.families))
    months = set(parse_csv(args.months))
    delta = build_variant_delta(
        run_dir=args.run_dir,
        base_variant=args.base_variant,
        candidate_variant=args.candidate_variant,
        candidates=candidates,
        families=families,
        months=months,
    )
    if not delta.empty:
        delta, blocking_pairs = add_trade_delta_blocking_diagnostics(delta)
        if "pred_taken_ev" in delta.columns:
            stateful_examples = stateful_candidate_examples_from_delta(
                delta,
                args.stateful_example_target,
            )
        else:
            stateful_examples = pd.DataFrame()
    else:
        blocking_pairs = pd.DataFrame()
        stateful_examples = pd.DataFrame()

    output_dir = make_run_dir(args.output_dir, args.label)
    delta.to_csv(output_dir / "trade_delta_rows.csv", index=False)
    blocking_pairs.to_csv(output_dir / "blocking_pairs.csv", index=False)
    stateful_examples.to_csv(output_dir / "stateful_candidate_examples.csv", index=False)

    group_specs = {
        "candidate": ["candidate"],
        "candidate_status": ["candidate", "delta_status"],
        "family_candidate": ["family", "candidate"],
        "family_candidate_status": ["family", "candidate", "delta_status"],
        "month_candidate": ["month", "candidate"],
        "month_candidate_status": ["month", "candidate", "delta_status"],
        "month_candidate_status_direction": ["month", "candidate", "delta_status", "direction"],
    }
    summaries: dict[str, pd.DataFrame] = {}
    for name, columns in group_specs.items():
        summaries[name] = write_summary(delta, output_dir, group_name=name, group_columns=columns)

    blocking_specs = {
        "blocking_month_candidate_status_direction": [
            "month",
            "candidate",
            "delta_status",
            "direction",
        ],
        "blocking_family_candidate_status_direction": [
            "family",
            "candidate",
            "delta_status",
            "direction",
        ],
    }
    for name, columns in blocking_specs.items():
        write_blocking_summary(delta, output_dir, group_name=name, group_columns=columns)

    config = {
        "run_dir": args.run_dir,
        "base_variant": args.base_variant,
        "candidate_variant": args.candidate_variant,
        "candidates": sorted(candidates),
        "families": sorted(families),
        "months": sorted(months),
        "stateful_example_target": args.stateful_example_target,
        "label": args.label,
    }
    (output_dir / "config.json").write_text(
        json.dumps(config, indent=2, default=local_json_default),
        encoding="utf-8",
    )

    if delta.empty:
        print("no trade deltas to summarize")
        print(f"artifacts: {output_dir}")
        return output_dir

    candidate_summary = summaries["candidate"]
    print("candidate delta:")
    print(
        candidate_summary[
            [
                "candidate",
                "base_trade_count",
                "candidate_trade_count",
                "base_adjusted_pnl",
                "candidate_adjusted_pnl",
                "pnl_delta",
                "removed_positive_pnl",
                "removed_negative_pnl",
                "added_positive_pnl",
                "added_negative_pnl",
            ]
        ].to_string(index=False)
    )
    month_summary = summaries["month_candidate"]
    print("\nmonth delta:")
    print(
        month_summary[
            [
                "month",
                "candidate",
                "base_trade_count",
                "candidate_trade_count",
                "base_adjusted_pnl",
                "candidate_adjusted_pnl",
                "pnl_delta",
                "removed_positive_pnl",
                "removed_negative_pnl",
                "added_positive_pnl",
                "added_negative_pnl",
            ]
        ].to_string(index=False)
    )
    print(f"artifacts: {output_dir}")
    return output_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--base-variant", default="base")
    parser.add_argument("--candidate-variant", required=True)
    parser.add_argument("--candidates", default="")
    parser.add_argument("--families", default="")
    parser.add_argument("--months", default="")
    parser.add_argument(
        "--stateful-example-target",
        choices=("stateful_net", "stateful_positive_cost", "candidate_pnl"),
        default="stateful_net",
    )
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="entry_ev_variant_trade_delta_diagnostics")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_variant_delta(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
