#!/usr/bin/env python3
"""Audit selected one-fail rows as a replacement candidate scope."""

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

from entry_ev_candidate_generation_gap_audit import (  # noqa: E402
    DEFAULT_HORIZONS,
    DEFAULT_TARGETS,
    build_horizon_rows,
    bool_series,
    local_json_default,
    normalize_predictions,
    numeric_series,
    parse_csv,
    parse_int_csv,
    parse_targets,
    summarize_gate,
    target_scope_summary,
    text_series,
)


DEFAULT_ROW_SCOPES = "available_candidates,greedy_selected,selected_onefail_replacement"
DEFAULT_SELECTION_BUCKETS = "one_failed_strict_stage"


def strict_stage_frame(
    frame: pd.DataFrame,
    *,
    strict_score_floor: float,
    strict_score_pct: float,
    strict_side_margin_pct: float,
    strict_entry_rank_pct: float,
    strict_min_side_margin: float,
) -> pd.DataFrame:
    checks = pd.DataFrame(index=frame.index)
    checks["holding"] = bool_series(frame, "holding_ok", default=False)
    checks["score_floor"] = numeric_series(frame, "side_score", default=-np.inf).gt(
        strict_score_floor
    )
    checks["score_q"] = numeric_series(frame, "score_pct", default=-np.inf).ge(
        strict_score_pct
    )
    checks["side_margin_q"] = numeric_series(
        frame,
        "side_margin_pct",
        default=-np.inf,
    ).ge(strict_side_margin_pct)
    checks["rank_q"] = numeric_series(frame, "entry_rank_pct", default=-np.inf).ge(
        strict_entry_rank_pct
    )
    checks["side_margin"] = numeric_series(frame, "side_margin", default=-np.inf).ge(
        strict_min_side_margin
    )
    return checks


def failed_stage_labels(checks: pd.DataFrame) -> pd.Series:
    labels: list[str] = []
    for _, row in checks.iterrows():
        failed = [column for column, passed in row.items() if not bool(passed)]
        labels.append(",".join(failed) if failed else "none")
    return pd.Series(labels, index=checks.index, dtype=object)


def selected_replacement_rows(
    predictions: pd.DataFrame,
    *,
    synthetic_scope: str,
    selection_buckets: list[str],
    require_stateful_available: bool,
    require_target_support: bool,
    strict_score_floor: float,
    strict_score_pct: float,
    strict_side_margin_pct: float,
    strict_entry_rank_pct: float,
    strict_min_side_margin: float,
) -> pd.DataFrame:
    output = predictions.copy()
    mask = bool_series(output, "selected_any", default=False)
    if require_stateful_available:
        mask &= bool_series(output, "stateful_available", default=False)
    if selection_buckets:
        mask &= text_series(output, "selection_bucket").isin(selection_buckets)
    if require_target_support:
        mask &= output["side"].eq(output["needed_side"]) & numeric_series(
            output,
            "extra_side_needed",
            default=0.0,
        ).gt(0.0)
    selected = output[mask].copy()
    if selected.empty:
        return selected
    selected["source_row_scope"] = selected["row_scope"].astype(str)
    selected["source_selection_bucket"] = selected["selection_bucket"].astype(str)
    selected["row_scope"] = synthetic_scope
    selected["synthetic_scope"] = synthetic_scope
    selected["synthetic_scope_reason"] = "selected_stateful_available"
    checks = strict_stage_frame(
        selected,
        strict_score_floor=strict_score_floor,
        strict_score_pct=strict_score_pct,
        strict_side_margin_pct=strict_side_margin_pct,
        strict_entry_rank_pct=strict_entry_rank_pct,
        strict_min_side_margin=strict_min_side_margin,
    )
    selected["recomputed_strict_failed_stage_count"] = (~checks).sum(axis=1).astype(int)
    selected["recomputed_strict_failed_stages"] = failed_stage_labels(checks)
    return selected.reset_index(drop=True)


def selected_scope_summary(selected: pd.DataFrame, *, horizons: list[int]) -> pd.DataFrame:
    if selected.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    group_columns = [
        "role",
        "month",
        "side",
        "row_scope",
        "source_row_scope",
        "source_selection_bucket",
        "recomputed_strict_failed_stages",
    ]
    for key, group in selected.groupby(group_columns, dropna=False, sort=True):
        row = dict(zip(group_columns, key, strict=True))
        row["selected_replacement_rows"] = int(len(group))
        row["stateful_available_rows"] = int(bool_series(group, "stateful_available").sum())
        row["target_support_rows"] = int(
            (
                group["side"].eq(group["needed_side"])
                & numeric_series(group, "extra_side_needed", default=0.0).gt(0.0)
            ).sum()
        )
        row["max_side_score"] = float(numeric_series(group, "side_score").max())
        row["max_score_pct"] = float(numeric_series(group, "score_pct").max())
        row["max_side_margin_pct"] = float(numeric_series(group, "side_margin_pct").max())
        row["max_entry_rank_pct"] = float(numeric_series(group, "entry_rank_pct").max())
        for horizon in horizons:
            actual = numeric_series(group, f"side_fixed_{horizon}m_adjusted_pnl")
            row[f"fixed{horizon}_actual_sum"] = float(actual.sum())
            row[f"fixed{horizon}_actual_max"] = float(actual.max())
            pred_column = (
                f"ranker_hv_{horizon}m_pred_pnl"
                if f"ranker_hv_{horizon}m_pred_pnl" in group.columns
                else f"pred_hv_{horizon}m_pnl"
            )
            row[f"pred{horizon}_pnl_max"] = float(numeric_series(group, pred_column).max())
            row[f"pred{horizon}_prob_max"] = float(
                numeric_series(group, f"pred_hv_{horizon}m_executable_prob").max()
            )
            row[f"pred{horizon}_tail_min"] = float(
                numeric_series(group, f"pred_hv_{horizon}m_tail_loss_prob").min()
            )
        rows.append(row)
    return pd.DataFrame(rows).sort_values(
        ["role", "month", "side", "row_scope"],
        ascending=True,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument(
        "--output-root",
        type=Path,
        default=ROOT / "data" / "reports" / "backtests",
    )
    parser.add_argument(
        "--run-label",
        default="entry_ev_selected_replacement_scope_diagnostics",
    )
    parser.add_argument("--targets", default=DEFAULT_TARGETS)
    parser.add_argument("--row-scopes", default=DEFAULT_ROW_SCOPES)
    parser.add_argument("--horizons", default="60,240,720")
    parser.add_argument("--synthetic-scope", default="selected_onefail_replacement")
    parser.add_argument("--selection-buckets", default=DEFAULT_SELECTION_BUCKETS)
    parser.add_argument("--strict-min-prob", type=float, default=0.45)
    parser.add_argument("--strict-min-pred-pnl", type=float, default=0.0)
    parser.add_argument("--strict-max-tail-prob", type=float, default=0.50)
    parser.add_argument("--relaxed-min-prob", type=float, default=0.30)
    parser.add_argument("--relaxed-min-pred-pnl", type=float, default=-2.0)
    parser.add_argument("--relaxed-max-tail-prob", type=float, default=0.50)
    parser.add_argument("--strict-score-floor", type=float, default=5.0)
    parser.add_argument("--strict-score-pct", type=float, default=0.95)
    parser.add_argument("--strict-side-margin-pct", type=float, default=0.95)
    parser.add_argument("--strict-entry-rank-pct", type=float, default=0.90)
    parser.add_argument("--strict-min-side-margin", type=float, default=0.0)
    parser.add_argument(
        "--allow-stateful-blocked",
        action="store_true",
        help="Include selected rows even when stateful_available is false.",
    )
    parser.add_argument(
        "--allow-non-target-support",
        action="store_true",
        help="Include selected rows whose side is not the current needed side.",
    )
    parser.add_argument(
        "--use-base-pnl",
        action="store_true",
        help="Use pred_hv_*_pnl even when ranker_hv_*_pred_pnl exists.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    targets = parse_targets(args.targets)
    row_scopes = parse_csv(args.row_scopes)
    horizons = parse_int_csv(args.horizons)
    predictions = normalize_predictions(
        pd.read_csv(args.predictions),
        horizons=horizons,
        prefer_ranker_pnl=not args.use_base_pnl,
    )
    synthetic = selected_replacement_rows(
        predictions,
        synthetic_scope=args.synthetic_scope,
        selection_buckets=parse_csv(args.selection_buckets),
        require_stateful_available=not args.allow_stateful_blocked,
        require_target_support=not args.allow_non_target_support,
        strict_score_floor=args.strict_score_floor,
        strict_score_pct=args.strict_score_pct,
        strict_side_margin_pct=args.strict_side_margin_pct,
        strict_entry_rank_pct=args.strict_entry_rank_pct,
        strict_min_side_margin=args.strict_min_side_margin,
    )
    augmented = pd.concat([predictions, synthetic], ignore_index=True, sort=False)
    horizon_rows = build_horizon_rows(
        augmented,
        targets=targets,
        row_scopes=row_scopes,
        horizons=horizons,
    )
    strict_summary = summarize_gate(
        horizon_rows,
        prefix="strict",
        min_prob=args.strict_min_prob,
        min_pred_pnl=args.strict_min_pred_pnl,
        max_tail_prob=args.strict_max_tail_prob,
        require_model_used=True,
    )
    relaxed_summary = summarize_gate(
        horizon_rows,
        prefix="relaxed",
        min_prob=args.relaxed_min_prob,
        min_pred_pnl=args.relaxed_min_pred_pnl,
        max_tail_prob=args.relaxed_max_tail_prob,
        require_model_used=True,
    )
    target_summary = target_scope_summary(
        augmented,
        targets=targets,
        row_scopes=row_scopes,
        horizons=horizons,
        strict_summary=strict_summary,
        relaxed_summary=relaxed_summary,
        replay_summary=pd.DataFrame(),
    )
    selected_summary = selected_scope_summary(synthetic, horizons=horizons)

    run_dir = make_run_dir(args.output_root, args.run_label)
    target_summary.to_csv(
        run_dir / "selected_replacement_target_scope_summary.csv",
        index=False,
    )
    synthetic.to_csv(run_dir / "selected_replacement_rows.csv", index=False)
    selected_summary.to_csv(run_dir / "selected_replacement_scope_summary.csv", index=False)
    horizon_rows.to_csv(run_dir / "selected_replacement_horizon_rows.csv", index=False)
    strict_summary.to_csv(run_dir / "selected_replacement_strict_gate_summary.csv", index=False)
    relaxed_summary.to_csv(
        run_dir / "selected_replacement_relaxed_gate_summary.csv",
        index=False,
    )
    meta: dict[str, Any] = {
        "predictions": args.predictions,
        "targets": targets,
        "row_scopes": row_scopes,
        "horizons": horizons,
        "synthetic_scope": args.synthetic_scope,
        "selection_buckets": parse_csv(args.selection_buckets),
        "require_stateful_available": not args.allow_stateful_blocked,
        "require_target_support": not args.allow_non_target_support,
        "prefer_ranker_pnl": not args.use_base_pnl,
        "strict_stage_thresholds": {
            "score_floor": args.strict_score_floor,
            "score_pct": args.strict_score_pct,
            "side_margin_pct": args.strict_side_margin_pct,
            "entry_rank_pct": args.strict_entry_rank_pct,
            "min_side_margin": args.strict_min_side_margin,
        },
        "strict_gate": {
            "min_prob": args.strict_min_prob,
            "min_pred_pnl": args.strict_min_pred_pnl,
            "max_tail_prob": args.strict_max_tail_prob,
            "require_model_used": True,
        },
        "relaxed_gate": {
            "min_prob": args.relaxed_min_prob,
            "min_pred_pnl": args.relaxed_min_pred_pnl,
            "max_tail_prob": args.relaxed_max_tail_prob,
            "require_model_used": True,
        },
        "selected_replacement_row_count": int(len(synthetic)),
    }
    (run_dir / "selected_replacement_scope_meta.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2, default=local_json_default),
        encoding="utf-8",
    )
    print(run_dir)


if __name__ == "__main__":
    main()
