#!/usr/bin/env python3
"""Build soft downside-risk margin score columns for entry-EV predictions."""

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

from entry_ev_executable_ev_policy_inputs import (  # noqa: E402
    add_executable_quantile_columns,
)
from entry_ev_scale_quantile_diagnostics import month_series, parse_scope_csv  # noqa: E402
from entry_ev_supervised_shrinkage_policy_inputs import (  # noqa: E402
    local_json_default,
    numeric_series,
    parse_csv,
    parse_family_predictions,
)


DEFAULT_SCORE_KIND_PREFIX = "downside_margin"
DEFAULT_WEIGHTS = "1,2,5,10"
DEFAULT_QUANTILE_SCOPES = "month,side_month,side_regime_session_month"
DEFAULT_LONG_DOWNSIDE_COLUMN = "pred_downside_meta_long_expected_downside"
DEFAULT_SHORT_DOWNSIDE_COLUMN = "pred_downside_meta_short_expected_downside"


def parse_float_csv(value: str) -> list[float]:
    values = [float(part) for part in parse_csv(value)]
    if not values:
        raise argparse.ArgumentTypeError("at least one weight is required")
    return values


def weight_label(value: float) -> str:
    return f"{value:g}".replace("-", "neg").replace(".", "p")


def score_kind_for_weight(prefix: str, weight: float) -> str:
    return f"{prefix}_w{weight_label(weight)}"


def margin_output_columns(score_kind: str) -> tuple[str, str]:
    return (
        f"pred_{score_kind}_long_best_adjusted_pnl",
        f"pred_{score_kind}_short_best_adjusted_pnl",
    )


def add_downside_margin_columns(
    predictions: pd.DataFrame,
    *,
    family: str,
    score_kind_prefix: str,
    weights: list[float],
    long_column: str,
    short_column: str,
    long_downside_column: str,
    short_downside_column: str,
    long_rank_column: str,
    short_rank_column: str,
    quantile_scopes: list[str],
    downside_floor: float,
) -> pd.DataFrame:
    missing = sorted(
        {
            long_column,
            short_column,
            long_downside_column,
            short_downside_column,
            long_rank_column,
            short_rank_column,
        }
        - set(predictions.columns)
    )
    if missing:
        raise ValueError(f"{family} predictions missing columns: {', '.join(missing)}")

    output = predictions.copy()
    long_base = numeric_series(output, long_column, default=np.nan)
    short_base = numeric_series(output, short_column, default=np.nan)
    long_downside = np.maximum(
        numeric_series(output, long_downside_column, default=0.0) - downside_floor,
        0.0,
    )
    short_downside = np.maximum(
        numeric_series(output, short_downside_column, default=0.0) - downside_floor,
        0.0,
    )
    output[f"pred_{score_kind_prefix}_long_margin_input_downside"] = long_downside
    output[f"pred_{score_kind_prefix}_short_margin_input_downside"] = short_downside

    for weight in weights:
        if weight < 0:
            raise ValueError("weights must be non-negative")
        score_kind = score_kind_for_weight(score_kind_prefix, weight)
        long_output_column, short_output_column = margin_output_columns(score_kind)
        output[long_output_column] = long_base - weight * long_downside
        output[short_output_column] = short_base - weight * short_downside
        output = add_executable_quantile_columns(
            output,
            family=family,
            score_kind=score_kind,
            long_output_column=long_output_column,
            short_output_column=short_output_column,
            long_rank_column=long_rank_column,
            short_rank_column=short_rank_column,
            quantile_scopes=quantile_scopes,
        )
    return output


def summarize_margin_effect(
    outputs: dict[str, pd.DataFrame],
    *,
    score_kind_prefix: str,
    weights: list[float],
    long_column: str,
    short_column: str,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for family, frame in outputs.items():
        months = month_series(frame).astype(str).str.slice(0, 7)
        base_long = numeric_series(frame, long_column, default=np.nan)
        base_short = numeric_series(frame, short_column, default=np.nan)
        base_side = np.where(base_long >= base_short, "long", "short")
        base_score = np.where(base_side == "long", base_long, base_short)
        base_gap = (base_long - base_short).abs()
        for weight in weights:
            score_kind = score_kind_for_weight(score_kind_prefix, weight)
            long_output_column, short_output_column = margin_output_columns(score_kind)
            margin_long = numeric_series(frame, long_output_column, default=np.nan)
            margin_short = numeric_series(frame, short_output_column, default=np.nan)
            margin_side = np.where(margin_long >= margin_short, "long", "short")
            margin_score = np.where(margin_side == "long", margin_long, margin_short)
            margin_gap = (margin_long - margin_short).abs()
            summary = pd.DataFrame(
                {
                    "month": months,
                    "base_side": base_side,
                    "margin_side": margin_side,
                    "base_score": base_score,
                    "margin_score": margin_score,
                    "base_gap": base_gap,
                    "margin_gap": margin_gap,
                    "long_margin_delta": margin_long - base_long,
                    "short_margin_delta": margin_short - base_short,
                }
            )
            for month, group in summary.groupby("month", dropna=False):
                rows.append(
                    {
                        "family": family,
                        "month": month,
                        "weight": float(weight),
                        "score_kind": score_kind,
                        "row_count": int(len(group)),
                        "side_switch_share": float(
                            (group["base_side"] != group["margin_side"]).mean()
                        ),
                        "base_score_mean": float(group["base_score"].mean()),
                        "margin_score_mean": float(group["margin_score"].mean()),
                        "score_delta_mean": float(
                            (group["margin_score"] - group["base_score"]).mean()
                        ),
                        "base_score_q95": float(group["base_score"].quantile(0.95)),
                        "margin_score_q95": float(group["margin_score"].quantile(0.95)),
                        "base_gap_q95": float(group["base_gap"].quantile(0.95)),
                        "margin_gap_q95": float(group["margin_gap"].quantile(0.95)),
                        "long_margin_delta_mean": float(
                            group["long_margin_delta"].mean()
                        ),
                        "short_margin_delta_mean": float(
                            group["short_margin_delta"].mean()
                        ),
                    }
                )
    return pd.DataFrame(rows).sort_values(["family", "month", "weight"]).reset_index(
        drop=True
    )


def run_margin_input_generation(args: argparse.Namespace) -> Path:
    family_paths = parse_family_predictions(args.family_predictions)
    weights = parse_float_csv(args.weights)
    quantile_scopes = parse_scope_csv(args.quantile_scopes)

    outputs: dict[str, pd.DataFrame] = {}
    run_dir = make_run_dir(args.output_dir, args.label)
    prediction_dir = run_dir / "enriched_predictions"
    prediction_dir.mkdir(parents=True, exist_ok=True)
    output_paths: dict[str, Path] = {}
    for family, path in family_paths.items():
        frame = pd.read_parquet(path)
        enriched = add_downside_margin_columns(
            frame,
            family=family,
            score_kind_prefix=args.score_kind_prefix,
            weights=weights,
            long_column=args.long_column,
            short_column=args.short_column,
            long_downside_column=args.long_downside_column,
            short_downside_column=args.short_downside_column,
            long_rank_column=args.long_rank_column,
            short_rank_column=args.short_rank_column,
            quantile_scopes=quantile_scopes,
            downside_floor=args.downside_floor,
        )
        output_path = prediction_dir / f"{family}_predictions_downside_margin.parquet"
        enriched.to_parquet(output_path, index=False)
        outputs[family] = enriched
        output_paths[family] = output_path

    effect_summary = summarize_margin_effect(
        outputs,
        score_kind_prefix=args.score_kind_prefix,
        weights=weights,
        long_column=args.long_column,
        short_column=args.short_column,
    )
    effect_summary.to_csv(run_dir / "prediction_downside_margin_effect_summary.csv", index=False)

    config = {
        "family_predictions": family_paths,
        "output_paths": output_paths,
        "weights": weights,
        "score_kind_prefix": args.score_kind_prefix,
        "score_kinds": [
            score_kind_for_weight(args.score_kind_prefix, weight) for weight in weights
        ],
        "long_column": args.long_column,
        "short_column": args.short_column,
        "long_downside_column": args.long_downside_column,
        "short_downside_column": args.short_downside_column,
        "long_rank_column": args.long_rank_column,
        "short_rank_column": args.short_rank_column,
        "quantile_scopes": quantile_scopes,
        "downside_floor": args.downside_floor,
    }
    (run_dir / "config.json").write_text(
        json.dumps(config, indent=2, default=local_json_default),
        encoding="utf-8",
    )

    print("Downside margin effect summary:")
    print(
        effect_summary.groupby("weight", as_index=False)
        .agg(
            side_switch_share=("side_switch_share", "mean"),
            score_delta_mean=("score_delta_mean", "mean"),
            margin_score_q95=("margin_score_q95", "mean"),
            margin_gap_q95=("margin_gap_q95", "mean"),
        )
        .to_string(index=False)
    )
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--family-predictions", action="append", required=True)
    parser.add_argument("--weights", default=DEFAULT_WEIGHTS)
    parser.add_argument("--score-kind-prefix", default=DEFAULT_SCORE_KIND_PREFIX)
    parser.add_argument("--long-column", required=True)
    parser.add_argument("--short-column", required=True)
    parser.add_argument("--long-downside-column", default=DEFAULT_LONG_DOWNSIDE_COLUMN)
    parser.add_argument("--short-downside-column", default=DEFAULT_SHORT_DOWNSIDE_COLUMN)
    parser.add_argument("--long-rank-column", default="pred_long_entry_local_rank")
    parser.add_argument("--short-rank-column", default="pred_short_entry_local_rank")
    parser.add_argument("--quantile-scopes", default=DEFAULT_QUANTILE_SCOPES)
    parser.add_argument("--downside-floor", type=float, default=0.0)
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="entry_ev_downside_meta_risk_margin_policy_inputs")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_margin_input_generation(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
