#!/usr/bin/env python3
"""Enrich multi-family policy trade CSVs with their matching prediction rows."""

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
    enrich_trades_with_predictions,
    json_default,
    make_run_dir,
    prepare_analysis_predictions,
    read_trades_csv,
)

from entry_ev_direction_residual_loss_diagnostics import (  # noqa: E402
    DEFAULT_EXTRA_COLUMNS,
    add_selected_residual_features,
    parse_csv,
    read_monthly_metrics,
    summarize_by,
    trade_path,
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


def parse_policy_runs(values: list[str]) -> dict[str, Path]:
    runs: dict[str, Path] = {}
    for value in values:
        if "=" not in value:
            raise argparse.ArgumentTypeError("policy runs must use name=path")
        name, path = value.split("=", 1)
        name = name.strip()
        if not name:
            raise argparse.ArgumentTypeError("policy run name must not be empty")
        runs[name] = Path(path.strip())
    if not runs:
        raise argparse.ArgumentTypeError("at least one policy run is required")
    return runs


def parse_family_predictions(values: list[str]) -> dict[str, Path]:
    families: dict[str, Path] = {}
    for value in values:
        if "=" not in value:
            raise argparse.ArgumentTypeError("family predictions must use family=path")
        family, path = value.split("=", 1)
        family = family.strip()
        if not family:
            raise argparse.ArgumentTypeError("family name must not be empty")
        families[family] = Path(path.strip())
    if not families:
        raise argparse.ArgumentTypeError("at least one family prediction is required")
    return families


def load_analysis_predictions(
    family_predictions: dict[str, Path],
    *,
    long_column: str,
    short_column: str,
    extra_prediction_columns: list[str],
) -> dict[str, pd.DataFrame]:
    loaded: dict[str, pd.DataFrame] = {}
    for family, path in family_predictions.items():
        predictions = pd.read_parquet(path)
        analysis = prepare_analysis_predictions(
            predictions,
            long_column,
            short_column,
            extra_prediction_columns,
        )
        analysis["decision_timestamp"] = pd.to_datetime(
            analysis["decision_timestamp"],
            utc=True,
        )
        duplicated = analysis["decision_timestamp"].duplicated()
        if duplicated.any():
            raise ValueError(
                f"{path} has duplicated decision_timestamp values: {int(duplicated.sum())}"
            )
        loaded[family] = analysis.sort_values("decision_timestamp").reset_index(drop=True)
    return loaded


def read_multifamily_policy_run_trades(
    *,
    run_name: str,
    run_dir: Path,
    analysis_predictions: dict[str, pd.DataFrame],
    extra_prediction_columns: list[str],
    families: set[str],
    roles: set[str],
    months: set[str],
    candidates: set[str],
    variants: set[str],
) -> pd.DataFrame:
    monthly = filter_monthly_metrics(
        read_monthly_metrics(run_dir),
        families=families,
        roles=roles,
        months=months,
        candidates=candidates,
        variants=variants,
    )
    frames: list[pd.DataFrame] = []
    missing_paths: list[Path] = []
    missing_families: set[str] = set()
    for _, row in monthly.iterrows():
        family = str(row["family"])
        if family not in analysis_predictions:
            missing_families.add(family)
            continue
        path = trade_path(run_dir, row)
        if not path.exists():
            missing_paths.append(path)
            continue
        trades = read_trades_csv(path)
        if trades.empty:
            continue
        enriched = enrich_trades_with_predictions(
            trades,
            analysis_predictions[family],
            extra_prediction_columns,
        )
        enriched.insert(0, "run_name", run_name)
        enriched.insert(1, "family", family)
        enriched.insert(2, "role", str(row["role"]))
        enriched.insert(3, "variant", str(row.get("variant", "base")))
        enriched.insert(4, "month", str(row["month"]))
        enriched.insert(5, "candidate", str(row["candidate"]))
        frames.append(enriched)
    if missing_families:
        raise ValueError(f"missing family predictions: {', '.join(sorted(missing_families))}")
    if missing_paths:
        preview = ", ".join(str(path) for path in missing_paths[:5])
        suffix = "" if len(missing_paths) <= 5 else f" ... ({len(missing_paths)} missing)"
        raise FileNotFoundError(f"missing trade files: {preview}{suffix}")
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def filter_monthly_metrics(
    monthly: pd.DataFrame,
    *,
    families: set[str],
    roles: set[str],
    months: set[str],
    candidates: set[str],
    variants: set[str],
) -> pd.DataFrame:
    filtered = monthly.copy()
    if "variant" not in filtered.columns:
        filtered["variant"] = "base"
    filtered["variant"] = filtered["variant"].fillna("base").astype(str)
    filter_specs = [
        ("family", families),
        ("role", roles),
        ("month", months),
        ("candidate", candidates),
        ("variant", variants),
    ]
    for column, allowed in filter_specs:
        if allowed:
            filtered = filtered[filtered[column].astype(str).isin(allowed)].copy()
    return filtered.reset_index(drop=True)


def match_summary(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    grouped = frame.groupby(
        ["run_name", "family", "variant", "candidate", "month"],
        dropna=False,
    )
    rows: list[dict[str, Any]] = []
    for keys, group in grouped:
        run_name, family, variant, candidate, month = keys
        rows.append(
            {
                "run_name": run_name,
                "family": family,
                "variant": variant,
                "candidate": candidate,
                "month": month,
                "trade_count": int(len(group)),
                "matched_prediction_share": float(group["matched_prediction"].mean()),
                "total_pnl": float(pd.to_numeric(group["adjusted_pnl"], errors="coerce").sum()),
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["matched_prediction_share", "total_pnl"],
        ascending=[True, True],
    ).reset_index(drop=True)


def build_enrichment(args: argparse.Namespace) -> Path:
    policy_runs = parse_policy_runs(args.policy_run)
    family_predictions = parse_family_predictions(args.family_predictions)
    extra_columns = list(dict.fromkeys([*DEFAULT_EXTRA_COLUMNS, *parse_csv(args.extra_columns)]))
    families = set(parse_csv(getattr(args, "families", "")))
    roles = set(parse_csv(getattr(args, "roles", "")))
    months = set(parse_csv(getattr(args, "months", "")))
    candidates = set(parse_csv(getattr(args, "candidates", "")))
    variants = set(parse_csv(getattr(args, "variants", "")))
    analysis_predictions = load_analysis_predictions(
        family_predictions,
        long_column=args.long_column,
        short_column=args.short_column,
        extra_prediction_columns=extra_columns,
    )

    frames: list[pd.DataFrame] = []
    for run_name, run_dir in policy_runs.items():
        trades = read_multifamily_policy_run_trades(
            run_name=run_name,
            run_dir=run_dir,
            analysis_predictions=analysis_predictions,
            extra_prediction_columns=extra_columns,
            families=families,
            roles=roles,
            months=months,
            candidates=candidates,
            variants=variants,
        )
        frames.append(trades)
    combined = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    combined = add_selected_residual_features(combined)

    candidate = summarize_by(combined, ["run_name", "family", "variant", "candidate"])
    month = summarize_by(combined, ["run_name", "family", "variant", "candidate", "month"])
    matches = match_summary(combined)

    run_dir = make_run_dir(args.output_dir, args.label)
    combined.to_csv(run_dir / "residual_enriched_trades.csv", index=False)
    candidate.to_csv(run_dir / "candidate_residual_summary.csv", index=False)
    month.to_csv(run_dir / "month_residual_summary.csv", index=False)
    matches.to_csv(run_dir / "prediction_match_summary.csv", index=False)
    config = {
        "policy_runs": policy_runs,
        "family_predictions": family_predictions,
        "long_column": args.long_column,
        "short_column": args.short_column,
        "extra_columns": extra_columns,
        "families": sorted(families),
        "roles": sorted(roles),
        "months": sorted(months),
        "candidates": sorted(candidates),
        "variants": sorted(variants),
        "note": (
            "each trade CSV is joined with predictions for its monthly metrics family; "
            "monthly_policy_metrics.csv and monthly_exit_timing_metrics.csv are supported"
        ),
    }
    (run_dir / "config.json").write_text(
        json.dumps(config, indent=2, default=local_json_default),
        encoding="utf-8",
    )

    print("Prediction match summary:")
    print(matches.to_string(index=False))
    print("\nCandidate residual summary:")
    print(candidate.to_string(index=False))
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--policy-run", action="append", required=True)
    parser.add_argument("--family-predictions", action="append", required=True)
    parser.add_argument(
        "--long-column",
        default="pred_side_prior_pressure_s0p5_long_best_adjusted_pnl",
    )
    parser.add_argument(
        "--short-column",
        default="pred_side_prior_pressure_s0p5_short_best_adjusted_pnl",
    )
    parser.add_argument("--extra-columns", default="")
    parser.add_argument("--families", default="")
    parser.add_argument("--roles", default="")
    parser.add_argument("--months", default="")
    parser.add_argument("--candidates", default="")
    parser.add_argument("--variants", default="")
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="entry_ev_multifamily_policy_trade_enrichment")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    build_enrichment(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
