#!/usr/bin/env python3
"""Break down candidate-support gaps inside selector surface artifacts."""

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
for path in (SRC, SCRIPT_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from trade_data.backtest import make_run_dir  # noqa: E402

from entry_ev_candidate_generation_gap_audit import local_json_default  # noqa: E402
from entry_ev_replacement_abstention_surface_diagnostics import GROUP_COLUMNS  # noqa: E402
from entry_ev_surface_target_outcome_diagnostics import classify_outcomes  # noqa: E402
from entry_ev_thin_month_opposite_candidate_diagnostics import (  # noqa: E402
    bool_series,
    numeric_series,
)


DEFAULT_SURFACE_RUN_DIR = (
    ROOT
    / "data/reports/backtests"
    / "20260703_133252_20260703_entry_ev_00382_all_family_shrunk_prior_surface_00378"
)

POOL_KEY_COLUMNS = [
    "family",
    "month",
    "risk_selector",
    "risk_trade_id",
    "calibration_min_context_count",
]
POOL_ID_COLUMNS = [
    "family",
    "month",
    "risk_trade_id",
    "calibration_min_context_count",
]


def resolve_path(value: str | Path, *, base: Path = ROOT) -> Path:
    path = Path(value)
    return path if path.is_absolute() else base / path


def normalize_text(value: Any) -> str:
    return "" if pd.isna(value) else str(value)


def normalize_int(value: Any) -> int:
    if pd.isna(value):
        return 0
    return int(float(value))


def pool_key(row: pd.Series) -> tuple[str, str, str, str, int]:
    return (
        normalize_text(row.get("family", "")),
        normalize_text(row.get("month", "")),
        normalize_text(row.get("risk_selector", "")),
        normalize_text(row.get("risk_trade_id", "")),
        normalize_int(row.get("calibration_min_context_count", 0)),
    )


def pool_identity_key(row: pd.Series) -> tuple[str, str, str, int]:
    return (
        normalize_text(row.get("family", "")),
        normalize_text(row.get("month", "")),
        normalize_text(row.get("risk_trade_id", "")),
        normalize_int(row.get("calibration_min_context_count", 0)),
    )


def load_surface(surface_run_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    choices = pd.read_csv(surface_run_dir / "support_sufficient_selector_surface_choices.csv")
    candidates_path = surface_run_dir / "support_sufficient_selector_surface_candidates.csv"
    candidates = pd.read_csv(candidates_path) if candidates_path.exists() else pd.DataFrame()
    return choices, candidates


def build_pool_lookups(
    candidates: pd.DataFrame,
) -> tuple[
    dict[tuple[str, str, str, str, int], pd.DataFrame],
    dict[tuple[str, str, str, int], pd.DataFrame],
]:
    if candidates.empty:
        return {}, {}
    missing = [column for column in POOL_KEY_COLUMNS if column not in candidates.columns]
    if missing:
        raise ValueError(f"candidate artifact is missing key columns: {missing}")
    exact: dict[tuple[str, str, str, str, int], pd.DataFrame] = {}
    for _, group in candidates.groupby(POOL_KEY_COLUMNS, dropna=False):
        key = pool_key(group.iloc[0])
        exact[key] = group.copy()
    identity: dict[tuple[str, str, str, int], pd.DataFrame] = {}
    for _, group in candidates.groupby(POOL_ID_COLUMNS, dropna=False):
        key = pool_identity_key(group.iloc[0])
        identity[key] = group.copy()
    return exact, identity


def support_breakdown(
    pool: pd.DataFrame,
    *,
    min_prior_count: int,
    min_prior_month_count: int,
    min_prior_actual_mean: float,
) -> dict[str, Any]:
    if pool.empty:
        return {
            "candidate_pool_rows_observed": 0,
            "prior_count_pass_count": 0,
            "prior_month_pass_count": 0,
            "supported_count_observed": 0,
            "any_positive_candidate_count": 0,
            "supported_positive_count": 0,
            "supported_negative_count": 0,
            "best_any_actual": np.nan,
            "best_supported_actual": np.nan,
            "mean_supported_actual": np.nan,
            "max_prior_count": 0,
            "max_prior_month_count": 0,
            "max_prior_actual_mean": np.nan,
        }

    prior_count = numeric_series(pool, "prior_count", default=0.0)
    prior_month_count = numeric_series(pool, "prior_month_count", default=0.0)
    prior_actual_mean = numeric_series(pool, "prior_actual_mean", default=np.nan)
    actual = numeric_series(pool, "candidate_actual_at_pred_fixed_best_horizon", default=np.nan)

    count_mask = prior_count.ge(float(min_prior_count))
    month_mask = count_mask & prior_month_count.ge(float(min_prior_month_count))
    support_mask = month_mask & prior_actual_mean.ge(float(min_prior_actual_mean))
    supported_actual = actual[support_mask]

    return {
        "candidate_pool_rows_observed": int(len(pool)),
        "prior_count_pass_count": int(count_mask.sum()),
        "prior_month_pass_count": int(month_mask.sum()),
        "supported_count_observed": int(support_mask.sum()),
        "any_positive_candidate_count": int(actual.gt(0.0).sum()),
        "supported_positive_count": int(supported_actual.gt(0.0).sum()),
        "supported_negative_count": int(supported_actual.lt(0.0).sum()),
        "best_any_actual": float(actual.max()) if len(actual) else np.nan,
        "best_supported_actual": float(supported_actual.max()) if len(supported_actual) else np.nan,
        "mean_supported_actual": float(supported_actual.mean()) if len(supported_actual) else np.nan,
        "max_prior_count": int(prior_count.max()) if len(prior_count) else 0,
        "max_prior_month_count": int(prior_month_count.max()) if len(prior_month_count) else 0,
        "max_prior_actual_mean": float(prior_actual_mean.max()) if len(prior_actual_mean) else np.nan,
    }


def classify_support_gap(row: pd.Series) -> str:
    risk_selected = bool(row.get("risk_trade_selected", False))
    risk_loss = bool(row.get("risk_trade_is_loss", False))
    replacement = bool(row.get("replacement_chosen", False))
    outcome = normalize_text(row.get("target_outcome_category", ""))
    if not risk_selected:
        return "no_risk_trade"
    if not risk_loss:
        return "risk_trade_winner"
    if int(row.get("candidate_pool_rows_observed", 0)) <= 0:
        return "no_candidate_pool"
    if int(row.get("prior_count_pass_count", 0)) <= 0:
        return "prior_count_gap"
    if int(row.get("prior_month_pass_count", 0)) <= 0:
        max_prior_actual = float(row.get("max_prior_actual_mean", np.nan))
        min_prior_actual = float(row.get("candidate_min_prior_actual_mean", 0.0))
        if np.isfinite(max_prior_actual) and max_prior_actual < min_prior_actual:
            return "prior_month_and_actual_gap"
        return "prior_month_gap"
    if int(row.get("supported_count_observed", 0)) <= 0:
        return "prior_actual_gap"
    if outcome == "loss_replacement_repairs_month":
        return "supported_repaired"
    if not replacement:
        return "supported_no_replacement"
    return "supported_replacement_gap"


def add_support_gap_columns(choices: pd.DataFrame, candidates: pd.DataFrame) -> pd.DataFrame:
    output = classify_outcomes(choices).copy()
    exact_pool_lookup, identity_pool_lookup = build_pool_lookups(candidates)
    rows: list[dict[str, Any]] = []
    match_scopes: list[str] = []
    for _, row in output.iterrows():
        key = pool_key(row)
        identity_key = pool_identity_key(row)
        if key in exact_pool_lookup:
            pool = exact_pool_lookup[key]
            match_scopes.append("exact")
        elif identity_key in identity_pool_lookup:
            pool = identity_pool_lookup[identity_key]
            match_scopes.append("risk_selector_fallback")
        else:
            pool = pd.DataFrame()
            match_scopes.append("missing")
        rows.append(
            support_breakdown(
                pool,
                min_prior_count=normalize_int(row.get("candidate_min_prior_count", 0)),
                min_prior_month_count=normalize_int(row.get("candidate_min_prior_month_count", 0)),
                min_prior_actual_mean=float(row.get("candidate_min_prior_actual_mean", 0.0)),
            )
        )
    support = pd.DataFrame(rows)
    if support.empty:
        output["support_gap_stage"] = pd.Series(dtype=object)
        return output
    output = pd.concat([output.reset_index(drop=True), support.reset_index(drop=True)], axis=1)
    output["candidate_pool_match_scope"] = match_scopes
    output["support_count_mismatch"] = (
        numeric_series(output, "supported_candidate_rows", default=0.0).astype(int)
        != numeric_series(output, "supported_count_observed", default=0.0).astype(int)
    )
    output["candidate_count_mismatch"] = (
        numeric_series(output, "candidate_rows", default=0.0).astype(int)
        != numeric_series(output, "candidate_pool_rows_observed", default=0.0).astype(int)
    )
    output["support_gap_stage"] = output.apply(classify_support_gap, axis=1)
    return output


def summarize_support_gaps(choices: pd.DataFrame) -> pd.DataFrame:
    if choices.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    group_columns = [column for column in GROUP_COLUMNS if column in choices.columns]
    for key, group in choices.groupby(group_columns, dropna=False):
        key_tuple = key if isinstance(key, tuple) else (key,)
        row = dict(zip(group_columns, key_tuple))
        stage = group["support_gap_stage"].astype(str)
        outcome = group["target_outcome_category"].astype(str)
        after = numeric_series(group, "month_pnl_after_replacement", default=np.nan)
        delta = numeric_series(group, "delta_vs_baseline", default=0.0)
        row.update(
            {
                "target_count": int(len(group)),
                "success_count": int((outcome == "loss_replacement_repairs_month").sum()),
                "candidate_gap_count": int(
                    (outcome == "loss_selected_no_supported_candidate").sum()
                ),
                "risk_gap_count": int(outcome.isin(["no_risk_trade", "risk_trade_winner"]).sum()),
                "replacement_gap_count": int(
                    outcome.isin(
                        [
                            "loss_selected_no_replacement",
                            "loss_replacement_degrades",
                            "loss_replacement_improves_but_still_negative",
                        ]
                    ).sum()
                ),
                "prior_count_gap_count": int((stage == "prior_count_gap").sum()),
                "prior_month_gap_count": int((stage == "prior_month_gap").sum()),
                "prior_month_and_actual_gap_count": int(
                    (stage == "prior_month_and_actual_gap").sum()
                ),
                "prior_actual_gap_count": int((stage == "prior_actual_gap").sum()),
                "no_candidate_pool_count": int((stage == "no_candidate_pool").sum()),
                "supported_repaired_count": int((stage == "supported_repaired").sum()),
                "supported_replacement_gap_count": int(
                    (stage == "supported_replacement_gap").sum()
                ),
                "mean_supported_count": float(
                    numeric_series(group, "supported_count_observed", default=0.0).mean()
                ),
                "mean_best_supported_actual": float(
                    numeric_series(group, "best_supported_actual", default=np.nan).mean()
                ),
                "mean_after_pnl": float(after.mean()) if len(after) else np.nan,
                "mean_delta": float(delta.mean()) if len(delta) else np.nan,
                "support_stage_counts": ";".join(
                    f"{name}:{count}" for name, count in stage.value_counts().sort_index().items()
                ),
            }
        )
        rows.append(row)
    return pd.DataFrame(rows).sort_values(
        [
            "success_count",
            "candidate_gap_count",
            "risk_gap_count",
            "replacement_gap_count",
            "mean_after_pnl",
        ],
        ascending=[False, True, True, True, False],
    )


def run_diagnostics(args: argparse.Namespace) -> Path:
    surface_run_dir = resolve_path(args.surface_run_dir)
    choices, candidates = load_surface(surface_run_dir)
    enriched = add_support_gap_columns(choices, candidates)
    summary = summarize_support_gaps(enriched)
    run_dir = make_run_dir(resolve_path(args.output_root), args.run_label)
    enriched.to_csv(run_dir / "surface_support_gap_choices.csv", index=False)
    summary.to_csv(run_dir / "surface_support_gap_summary.csv", index=False)
    meta = {
        "surface_run_dir": surface_run_dir,
        "note": (
            "Breaks loss-selected candidate gaps into candidate-pool, prior-count, "
            "prior-month, and prior-actual support stages."
        ),
    }
    (run_dir / "surface_support_gap_meta.json").write_text(
        json.dumps(meta, indent=2, default=local_json_default) + "\n",
        encoding="utf-8",
    )
    display = [
        "risk_selector",
        "replacement_score_mode",
        "candidate_min_prior_count",
        "target_count",
        "success_count",
        "candidate_gap_count",
        "prior_count_gap_count",
        "prior_month_gap_count",
        "prior_month_and_actual_gap_count",
        "prior_actual_gap_count",
        "risk_gap_count",
        "mean_supported_count",
        "mean_after_pnl",
        "support_stage_counts",
    ]
    print("Surface support gap summary:")
    print(summary[[column for column in display if column in summary.columns]].head(int(args.print_rows)).to_string(index=False))
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--surface-run-dir", type=Path, default=DEFAULT_SURFACE_RUN_DIR)
    parser.add_argument("--output-root", type=Path, default=ROOT / "data/reports/backtests")
    parser.add_argument("--run-label", default="entry_ev_surface_support_gap_diagnostics")
    parser.add_argument("--print-rows", type=int, default=20)
    return parser


def main(argv: list[str] | None = None) -> int:
    run_diagnostics(build_parser().parse_args(argv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
