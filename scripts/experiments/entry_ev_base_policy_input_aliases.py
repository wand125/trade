#!/usr/bin/env python3
"""Prepare base prediction parquets for Entry EV quantile/selector pipelines."""

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

from entry_ev_executable_ev_policy_inputs import add_executable_quantile_columns  # noqa: E402
from entry_ev_forced_exit_policy_inputs import parse_family_predictions  # noqa: E402
from entry_ev_scale_quantile_diagnostics import month_series, parse_scope_csv  # noqa: E402


DEFAULT_QUANTILE_SCOPES = "month,side_month,side_regime_session_month"


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


def require_columns(frame: pd.DataFrame, columns: list[str]) -> None:
    missing = [column for column in columns if column not in frame.columns]
    if missing:
        raise ValueError(f"prediction frame missing columns: {', '.join(missing)}")


def finite_numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    values = pd.to_numeric(frame[column], errors="coerce")
    return values.where(np.isfinite(values))


def prepare_predictions(
    predictions: pd.DataFrame,
    *,
    family: str,
    score_kind: str,
    long_column: str,
    short_column: str,
    long_rank_column: str,
    short_rank_column: str,
    long_holding_source: str,
    short_holding_source: str,
    long_holding_output: str,
    short_holding_output: str,
    risk_prefix: str,
    quantile_scopes: list[str],
) -> pd.DataFrame:
    require_columns(
        predictions,
        [
            long_column,
            short_column,
            long_rank_column,
            short_rank_column,
            long_holding_source,
            short_holding_source,
        ],
    )
    output = predictions.copy()
    output[long_holding_output] = output[long_holding_source]
    output[short_holding_output] = output[short_holding_source]
    for side in ["long", "short"]:
        output[f"{risk_prefix}_{side}_predicted_ev_overestimate_risk"] = 0.0
    return add_executable_quantile_columns(
        output,
        family=family,
        score_kind=score_kind,
        long_output_column=long_column,
        short_output_column=short_column,
        long_rank_column=long_rank_column,
        short_rank_column=short_rank_column,
        quantile_scopes=quantile_scopes,
    )


def summarize_predictions(
    frame: pd.DataFrame,
    *,
    family: str,
    long_column: str,
    short_column: str,
    long_holding_output: str,
    short_holding_output: str,
) -> dict[str, object]:
    months = sorted(month_series(frame).astype(str).str.slice(0, 7).unique().tolist())
    long_score = finite_numeric(frame, long_column)
    short_score = finite_numeric(frame, short_column)
    selected_score = pd.Series(
        np.where(long_score >= short_score, long_score, short_score),
        index=frame.index,
    )
    long_hold = finite_numeric(frame, long_holding_output)
    short_hold = finite_numeric(frame, short_holding_output)
    return {
        "family": family,
        "row_count": int(len(frame)),
        "months": ",".join(months),
        "month_count": int(len(months)),
        "long_score_mean": float(long_score.mean()),
        "short_score_mean": float(short_score.mean()),
        "selected_score_q95": float(selected_score.quantile(0.95)),
        "selected_score_q99": float(selected_score.quantile(0.99)),
        "long_holding_missing": int(long_hold.isna().sum()),
        "short_holding_missing": int(short_hold.isna().sum()),
    }


def run(args: argparse.Namespace) -> Path:
    family_predictions = parse_family_predictions(args.family_predictions)
    quantile_scopes = parse_scope_csv(args.quantile_scopes)
    run_dir = make_run_dir(args.output_dir, args.label)
    enriched_dir = run_dir / "enriched_predictions"
    enriched_dir.mkdir(parents=True, exist_ok=True)

    summary_rows: list[dict[str, object]] = []
    output_paths: dict[str, str] = {}
    for family, prediction_path in family_predictions.items():
        predictions = pd.read_parquet(prediction_path)
        enriched = prepare_predictions(
            predictions,
            family=family,
            score_kind=args.score_kind,
            long_column=args.long_column,
            short_column=args.short_column,
            long_rank_column=args.long_rank_column,
            short_rank_column=args.short_rank_column,
            long_holding_source=args.long_holding_source,
            short_holding_source=args.short_holding_source,
            long_holding_output=args.long_holding_output,
            short_holding_output=args.short_holding_output,
            risk_prefix=args.risk_prefix,
            quantile_scopes=quantile_scopes,
        )
        output_path = enriched_dir / f"{family}_predictions_base_policy.parquet"
        enriched.to_parquet(output_path, index=False)
        output_paths[family] = str(output_path)
        summary_rows.append(
            summarize_predictions(
                enriched,
                family=family,
                long_column=args.long_column,
                short_column=args.short_column,
                long_holding_output=args.long_holding_output,
                short_holding_output=args.short_holding_output,
            )
        )

    summary = pd.DataFrame(summary_rows)
    summary.to_csv(run_dir / "base_policy_input_summary.csv", index=False)
    config = {
        "family_predictions": family_predictions,
        "output_paths": output_paths,
        "score_kind": args.score_kind,
        "long_column": args.long_column,
        "short_column": args.short_column,
        "long_rank_column": args.long_rank_column,
        "short_rank_column": args.short_rank_column,
        "long_holding_source": args.long_holding_source,
        "short_holding_source": args.short_holding_source,
        "long_holding_output": args.long_holding_output,
        "short_holding_output": args.short_holding_output,
        "risk_prefix": args.risk_prefix,
        "quantile_scopes": quantile_scopes,
    }
    (run_dir / "config.json").write_text(
        json.dumps(config, indent=2, default=local_json_default) + "\n",
        encoding="utf-8",
    )
    print("Base policy input summary:")
    print(summary.to_string(index=False))
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--family-predictions", action="append", required=True)
    parser.add_argument("--score-kind", default="base_calibrated")
    parser.add_argument("--long-column", default="pred_calibrated_long_best_adjusted_pnl")
    parser.add_argument("--short-column", default="pred_calibrated_short_best_adjusted_pnl")
    parser.add_argument("--long-rank-column", default="pred_long_entry_local_rank")
    parser.add_argument("--short-rank-column", default="pred_short_entry_local_rank")
    parser.add_argument("--long-holding-source", default="pred_long_exit_event_minutes")
    parser.add_argument("--short-holding-source", default="pred_short_exit_event_minutes")
    parser.add_argument("--long-holding-output", default="pred_mlp_long_exit_event_minutes")
    parser.add_argument("--short-holding-output", default="pred_mlp_short_exit_event_minutes")
    parser.add_argument("--risk-prefix", default="pred_base")
    parser.add_argument("--quantile-scopes", default=DEFAULT_QUANTILE_SCOPES)
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="entry_ev_base_policy_input_aliases")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
