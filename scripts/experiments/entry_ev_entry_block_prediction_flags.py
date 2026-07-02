#!/usr/bin/env python3
"""Add observable entry-block flag columns to entry-EV prediction parquet files."""

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

from entry_ev_quantile_policy_backtest import parse_family_predictions  # noqa: E402


FLAG_COLUMNS = [
    "entryblock_short_rollover_lossprob_ge0p4",
    "entryblock_short_rollover_sidegap_neg",
    "entryblock_short_rollover_sidegap_neg_lossprob_ge0p4",
    "entryblock_short_down_high_vol_rollover",
    "entryblock_short_down_high_vol_rollover_lossprob_ge0p4",
    "entryblock_short_entry_hour_23_lossprob_ge0p4",
    "entryblock_short_london_midloss_sidegap_pos",
    "entryblock_short_rollover_or_london_midloss",
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


def numeric_series(frame: pd.DataFrame, column: str, default: float = np.nan) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    values = pd.to_numeric(frame[column], errors="coerce")
    return values.replace([np.inf, -np.inf], np.nan).fillna(default).astype(float)


def text_series(frame: pd.DataFrame, column: str, default: str = "") -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype="string")
    return frame[column].astype("string").fillna(default).str.strip()


def true_false(mask: pd.Series) -> pd.Series:
    return pd.Series(np.where(mask.fillna(False).astype(bool), "true", "false"), index=mask.index)


def entry_hour(frame: pd.DataFrame) -> pd.Series:
    if "entry_hour" in frame.columns:
        return numeric_series(frame, "entry_hour", default=np.nan)
    if "decision_timestamp" not in frame.columns:
        return pd.Series(np.nan, index=frame.index, dtype=float)
    timestamps = pd.to_datetime(frame["decision_timestamp"], utc=True, errors="coerce")
    return timestamps.dt.hour.astype(float)


def add_entry_block_prediction_flags(frame: pd.DataFrame) -> pd.DataFrame:
    output = frame.copy()
    session = text_series(output, "session_regime")
    combined = text_series(output, "combined_regime")
    short_loss_first = numeric_series(output, "pred_short_exit_event_prob_2", default=np.nan)
    long_conf = numeric_series(output, "pred_best_side_prob_1", default=np.nan)
    short_conf = numeric_series(output, "pred_best_side_prob_-1", default=np.nan)
    short_conf_gap = short_conf - long_conf
    hour = entry_hour(output)

    rollover = session.eq("rollover")
    london = session.eq("london")
    short_lossprob_ge0p4 = short_loss_first.ge(0.4)
    short_midloss = short_loss_first.ge(0.3) & short_loss_first.le(0.45)
    short_sidegap_neg = short_conf_gap.lt(0.0)
    short_sidegap_pos = short_conf_gap.gt(0.0)
    down_high_vol = combined.eq("down_high_vol")

    flags = {
        "entryblock_short_rollover_lossprob_ge0p4": rollover & short_lossprob_ge0p4,
        "entryblock_short_rollover_sidegap_neg": rollover & short_sidegap_neg,
        "entryblock_short_rollover_sidegap_neg_lossprob_ge0p4": (
            rollover & short_sidegap_neg & short_lossprob_ge0p4
        ),
        "entryblock_short_down_high_vol_rollover": rollover & down_high_vol,
        "entryblock_short_down_high_vol_rollover_lossprob_ge0p4": (
            rollover & down_high_vol & short_lossprob_ge0p4
        ),
        "entryblock_short_entry_hour_23_lossprob_ge0p4": hour.eq(23.0)
        & short_lossprob_ge0p4,
        "entryblock_short_london_midloss_sidegap_pos": (
            london & short_midloss & short_sidegap_pos
        ),
    }
    flags["entryblock_short_rollover_or_london_midloss"] = (
        flags["entryblock_short_rollover_lossprob_ge0p4"]
        | flags["entryblock_short_london_midloss_sidegap_pos"]
    )
    for column in FLAG_COLUMNS:
        output[column] = true_false(flags[column])
    return output


def summarize_flags(frame: pd.DataFrame, *, family: str) -> pd.DataFrame:
    working = frame.copy()
    if "dataset_month" in working.columns:
        month = working["dataset_month"].astype(str).str.slice(0, 7)
    elif "decision_timestamp" in working.columns:
        month = pd.to_datetime(working["decision_timestamp"], utc=True).dt.strftime("%Y-%m")
    else:
        month = pd.Series("unknown", index=working.index)
    working["_month"] = month
    rows: list[dict[str, Any]] = []
    for month_value, group in working.groupby("_month", dropna=False):
        row: dict[str, Any] = {
            "family": family,
            "month": month_value,
            "row_count": int(len(group)),
        }
        for column in FLAG_COLUMNS:
            row[column] = int(group[column].astype(str).eq("true").sum())
        rows.append(row)
    return pd.DataFrame(rows)


def build_flags(args: argparse.Namespace) -> Path:
    family_predictions = parse_family_predictions(args.family_predictions)
    run_dir = make_run_dir(args.output_dir, args.label)
    output_dir = run_dir / "enriched_predictions"
    output_dir.mkdir(parents=True, exist_ok=True)

    summary_frames: list[pd.DataFrame] = []
    output_paths: dict[str, Path] = {}
    for family, path in family_predictions.items():
        frame = pd.read_parquet(path)
        enriched = add_entry_block_prediction_flags(frame)
        output_path = output_dir / f"{family}_predictions_entry_block_flags.parquet"
        enriched.to_parquet(output_path, index=False)
        output_paths[family] = output_path
        summary_frames.append(summarize_flags(enriched, family=family))

    summary = pd.concat(summary_frames, ignore_index=True) if summary_frames else pd.DataFrame()
    summary.to_csv(run_dir / "entry_block_prediction_flag_summary.csv", index=False)
    config = {
        "family_predictions": family_predictions,
        "output_predictions": output_paths,
        "flag_columns": FLAG_COLUMNS,
        "note": (
            "Flags are observable prediction-row approximations for entry block "
            "diagnostics. hold-extension state-dependent blocks are intentionally not "
            "encoded here."
        ),
    }
    (run_dir / "config.json").write_text(
        json.dumps(config, indent=2, default=local_json_default),
        encoding="utf-8",
    )
    print(f"Wrote entry-block prediction flags to {run_dir}")
    print(summary.to_string(index=False))
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--family-predictions", action="append", required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="entry_ev_entry_block_prediction_flags")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    build_flags(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
