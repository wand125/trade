#!/usr/bin/env python3
"""Add chronological loss-first empirical-CDF quantile columns."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
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
from trade_data.quantile_calibration import empirical_cdf_scores  # noqa: E402

from entry_ev_quantile_policy_backtest import parse_family_predictions  # noqa: E402


@dataclass(frozen=True)
class FamilyPredictions:
    family: str
    path: Path
    frame: pd.DataFrame
    months: pd.Series


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


def prediction_month_series(frame: pd.DataFrame) -> pd.Series:
    if "dataset_month" in frame.columns:
        return frame["dataset_month"].astype(str).str.slice(0, 7)
    if "decision_timestamp" not in frame.columns:
        raise ValueError("predictions require dataset_month or decision_timestamp")
    return pd.to_datetime(frame["decision_timestamp"], utc=True).dt.strftime("%Y-%m")


def read_family_predictions(family_paths: dict[str, Path]) -> list[FamilyPredictions]:
    families: list[FamilyPredictions] = []
    for family, path in family_paths.items():
        frame = pd.read_parquet(path)
        months = prediction_month_series(frame)
        families.append(FamilyPredictions(family=family, path=path, frame=frame, months=months))
    return families


def finite_count(values: pd.Series) -> int:
    numeric = pd.to_numeric(values, errors="coerce")
    return int(np.isfinite(numeric).sum())


def quantile_stats(values: pd.Series) -> dict[str, float | int]:
    numeric = pd.to_numeric(values, errors="coerce")
    finite = numeric[np.isfinite(numeric)]
    if finite.empty:
        return {
            "count": 0,
            "mean": float("nan"),
            "min": float("nan"),
            "p50": float("nan"),
            "p90": float("nan"),
            "max": float("nan"),
        }
    return {
        "count": int(finite.shape[0]),
        "mean": float(finite.mean()),
        "min": float(finite.min()),
        "p50": float(finite.quantile(0.50)),
        "p90": float(finite.quantile(0.90)),
        "max": float(finite.max()),
    }


def fit_values_for_month(
    families: list[FamilyPredictions],
    *,
    target_family: str,
    target_month: str,
    column: str,
    pooling: str,
) -> pd.Series:
    pieces: list[pd.Series] = []
    for family_predictions in families:
        if pooling == "family" and family_predictions.family != target_family:
            continue
        prior_mask = family_predictions.months < target_month
        if prior_mask.any():
            pieces.append(family_predictions.frame.loc[prior_mask, column])
    if not pieces:
        return pd.Series(dtype="float64")
    return pd.concat(pieces, ignore_index=True)


def add_chronological_loss_first_quantiles(
    families: list[FamilyPredictions],
    *,
    long_column: str,
    short_column: str,
    long_output_column: str,
    short_output_column: str,
    pooling: str,
    min_fit_rows: int,
    insufficient_fill_value: float,
) -> tuple[dict[str, pd.DataFrame], pd.DataFrame]:
    if pooling not in {"global", "family"}:
        raise ValueError("pooling must be global or family")
    if min_fit_rows < 1:
        raise ValueError("min_fit_rows must be positive")

    output_frames: dict[str, pd.DataFrame] = {}
    summary_rows: list[dict[str, Any]] = []
    column_pairs = [
        (long_column, long_output_column),
        (short_column, short_output_column),
    ]
    for family_predictions in families:
        missing = [
            column
            for column in (long_column, short_column)
            if column not in family_predictions.frame.columns
        ]
        if missing:
            raise ValueError(
                f"{family_predictions.family} missing columns: {', '.join(missing)}"
            )

    for family_predictions in families:
        output = family_predictions.frame.copy()
        for _, output_column in column_pairs:
            output[output_column] = np.nan
        months = sorted(
            month for month in family_predictions.months.dropna().unique().tolist() if month
        )
        for month in months:
            apply_mask = family_predictions.months == month
            for source_column, output_column in column_pairs:
                fit_values = fit_values_for_month(
                    families,
                    target_family=family_predictions.family,
                    target_month=month,
                    column=source_column,
                    pooling=pooling,
                )
                fit_rows = finite_count(fit_values)
                apply_values = family_predictions.frame.loc[apply_mask, source_column]
                status = "ok" if fit_rows >= min_fit_rows else "insufficient_fit"
                if status == "ok":
                    output.loc[apply_mask, output_column] = empirical_cdf_scores(
                        fit_values,
                        apply_values,
                    ).to_numpy()
                else:
                    output.loc[apply_mask, output_column] = insufficient_fill_value
                stats = quantile_stats(output.loc[apply_mask, output_column])
                summary_rows.append(
                    {
                        "family": family_predictions.family,
                        "month": month,
                        "pooling": pooling,
                        "source_column": source_column,
                        "output_column": output_column,
                        "fit_rows": fit_rows,
                        "apply_rows": int(apply_mask.sum()),
                        "status": status,
                        "quantile_count": stats["count"],
                        "quantile_mean": stats["mean"],
                        "quantile_min": stats["min"],
                        "quantile_p50": stats["p50"],
                        "quantile_p90": stats["p90"],
                        "quantile_max": stats["max"],
                    }
                )
        output_frames[family_predictions.family] = output
    return output_frames, pd.DataFrame(summary_rows)


def run_generation(args: argparse.Namespace) -> Path:
    family_paths = parse_family_predictions(args.family_predictions)
    families = read_family_predictions(family_paths)
    output_frames, summary = add_chronological_loss_first_quantiles(
        families,
        long_column=args.long_column,
        short_column=args.short_column,
        long_output_column=args.long_output_column,
        short_output_column=args.short_output_column,
        pooling=args.pooling,
        min_fit_rows=args.min_fit_rows,
        insufficient_fill_value=args.insufficient_fill_value,
    )
    run_dir = make_run_dir(args.output_dir, args.label)
    predictions_dir = run_dir / "enriched_predictions"
    predictions_dir.mkdir(parents=True, exist_ok=True)
    output_paths: dict[str, str] = {}
    for family, frame in output_frames.items():
        path = predictions_dir / f"{family}_predictions_loss_first_quantile.parquet"
        frame.to_parquet(path, index=False)
        output_paths[family] = str(path)
    summary.to_csv(run_dir / "loss_first_quantile_summary.csv", index=False)
    config = {
        "family_predictions": family_paths,
        "output_paths": output_paths,
        "long_column": args.long_column,
        "short_column": args.short_column,
        "long_output_column": args.long_output_column,
        "short_output_column": args.short_output_column,
        "pooling": args.pooling,
        "min_fit_rows": args.min_fit_rows,
        "insufficient_fill_value": args.insufficient_fill_value,
    }
    (run_dir / "config.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2, default=local_json_default),
        encoding="utf-8",
    )

    print(
        summary[
            [
                "family",
                "month",
                "source_column",
                "fit_rows",
                "status",
                "quantile_mean",
                "quantile_p90",
            ]
        ].to_string(index=False)
    )
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--family-predictions", action="append", required=True)
    parser.add_argument("--long-column", default="pred_long_exit_event_prob_2")
    parser.add_argument("--short-column", default="pred_short_exit_event_prob_2")
    parser.add_argument(
        "--long-output-column",
        default="pred_long_loss_first_global_expanding_quantile",
    )
    parser.add_argument(
        "--short-output-column",
        default="pred_short_loss_first_global_expanding_quantile",
    )
    parser.add_argument("--pooling", choices=("global", "family"), default="global")
    parser.add_argument("--min-fit-rows", type=int, default=1000)
    parser.add_argument("--insufficient-fill-value", type=float, default=0.0)
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="entry_ev_loss_first_quantile_inputs")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_generation(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
