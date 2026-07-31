#!/usr/bin/env python3
"""Diagnose replacement abstention gates on selector surface outputs."""

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
for path in (SRC, SCRIPT_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from trade_data.backtest import make_run_dir  # noqa: E402

from entry_ev_candidate_generation_gap_audit import local_json_default  # noqa: E402
from entry_ev_thin_month_opposite_candidate_diagnostics import (  # noqa: E402
    bool_series,
    numeric_series,
)


DEFAULT_SURFACE_RUN_DIR = (
    ROOT
    / "data/reports/backtests"
    / "20260703_082714_20260703_entry_ev_00373_winner_damage_ranked_selector_surface"
)
GROUP_COLUMNS = [
    "risk_selector",
    "replacement_score_mode",
    "calibration_min_context_count",
    "candidate_min_prior_count",
    "candidate_min_prior_month_count",
    "candidate_min_prior_actual_mean",
]


@dataclass(frozen=True)
class GateSpec:
    gate_name: str
    gate_family: str
    keep_mask: pd.Series
    threshold: float | None = None
    uses_actual: bool = False


def resolve_path(value: str | Path, *, base: Path = ROOT) -> Path:
    path = Path(value)
    return path if path.is_absolute() else base / path


def safe_rate(numerator: float, denominator: float) -> float:
    return float(numerator / denominator) if denominator else np.nan


def load_choices(run_dir: Path) -> pd.DataFrame:
    return pd.read_csv(run_dir / "support_sufficient_selector_surface_choices.csv")


def add_abstention_features(choices: pd.DataFrame) -> pd.DataFrame:
    output = choices.copy()
    output["prior_margin"] = numeric_series(output, "prior_actual_mean", default=np.nan) - numeric_series(
        output,
        "prior_mae",
        default=np.nan,
    )
    output["selection_mae_margin"] = numeric_series(output, "selection_score", default=np.nan) - numeric_series(
        output,
        "prior_mae",
        default=np.nan,
    )
    output["pred_mae_margin"] = numeric_series(output, "candidate_pred_pnl", default=np.nan) - numeric_series(
        output,
        "prior_mae",
        default=np.nan,
    )
    return output


def ge_gate(frame: pd.DataFrame, column: str, threshold: float) -> pd.Series:
    return numeric_series(frame, column, default=np.nan).ge(float(threshold)).fillna(False)


def le_gate(frame: pd.DataFrame, column: str, threshold: float) -> pd.Series:
    return numeric_series(frame, column, default=np.nan).le(float(threshold)).fillna(False)


def build_gate_specs(choices: pd.DataFrame) -> list[GateSpec]:
    frame = add_abstention_features(choices)
    specs: list[GateSpec] = [
        GateSpec(
            gate_name="keep_all_replacements",
            gate_family="baseline",
            keep_mask=pd.Series(True, index=frame.index),
        ),
        GateSpec(
            gate_name="abstain_all_replacements",
            gate_family="baseline",
            keep_mask=pd.Series(False, index=frame.index),
        ),
    ]
    ge_thresholds: dict[str, list[float]] = {
        "candidate_pred_pnl": [0.0, 1.0, 2.0, 5.0, 10.0],
        "selection_score": [0.0, 5.0, 10.0, 15.0, 20.0, 25.0, 30.0],
        "prior_actual_mean": [0.0, 10.0, 15.0, 20.0, 25.0, 30.0],
        "prior_margin": [-10.0, -5.0, 0.0, 5.0, 10.0],
        "selection_mae_margin": [-30.0, -20.0, -10.0, 0.0, 5.0],
        "pred_mae_margin": [-30.0, -20.0, -10.0, 0.0],
        "prior_count": [50.0, 100.0, 150.0, 200.0, 300.0],
        "prior_month_count": [2.0, 3.0, 4.0, 6.0],
    }
    for column, thresholds in ge_thresholds.items():
        for threshold in thresholds:
            specs.append(
                GateSpec(
                    gate_name=f"{column}_ge_{threshold:g}",
                    gate_family=column,
                    keep_mask=ge_gate(frame, column, threshold),
                    threshold=threshold,
                )
            )
    le_thresholds: dict[str, list[float]] = {
        "prior_mae": [10.0, 15.0, 20.0, 25.0, 30.0],
    }
    for column, thresholds in le_thresholds.items():
        for threshold in thresholds:
            specs.append(
                GateSpec(
                    gate_name=f"{column}_le_{threshold:g}",
                    gate_family=column,
                    keep_mask=le_gate(frame, column, threshold),
                    threshold=threshold,
                )
            )
    specs.extend(
        [
            GateSpec(
                gate_name="prior_margin_ge_0_and_months_ge_3",
                gate_family="combined",
                keep_mask=ge_gate(frame, "prior_margin", 0.0) & ge_gate(frame, "prior_month_count", 3.0),
            ),
            GateSpec(
                gate_name="pred_pnl_ge_2_and_prior_margin_ge_0",
                gate_family="combined",
                keep_mask=ge_gate(frame, "candidate_pred_pnl", 2.0) & ge_gate(frame, "prior_margin", 0.0),
            ),
            GateSpec(
                gate_name="pred_pnl_ge_2_and_months_ge_3",
                gate_family="combined",
                keep_mask=ge_gate(frame, "candidate_pred_pnl", 2.0) & ge_gate(frame, "prior_month_count", 3.0),
            ),
            GateSpec(
                gate_name="oracle_actual_nonnegative",
                gate_family="oracle",
                keep_mask=ge_gate(frame, "candidate_actual_at_pred_horizon", 0.0),
                threshold=0.0,
                uses_actual=True,
            ),
        ]
    )
    return specs


def simulate_gate_choices(choices: pd.DataFrame, spec: GateSpec) -> pd.DataFrame:
    frame = add_abstention_features(choices)
    keep_mask = spec.keep_mask.reindex(frame.index).fillna(False)
    replacement = bool_series(frame, "replacement_chosen", default=False)
    risk_selected = bool_series(frame, "risk_trade_selected", default=False)
    intervention = replacement & risk_selected & keep_mask
    baseline = numeric_series(frame, "baseline_month_pnl", default=np.nan)
    original_after = numeric_series(frame, "month_pnl_after_replacement", default=np.nan)
    output = frame.copy()
    output["abstention_gate"] = spec.gate_name
    output["abstention_gate_family"] = spec.gate_family
    output["abstention_threshold"] = spec.threshold
    output["abstention_uses_actual"] = spec.uses_actual
    output["replacement_gate_passed"] = replacement & keep_mask
    output["replacement_intervened"] = intervention
    output["simulated_month_pnl_after_abstention"] = original_after.where(intervention, baseline)
    output["simulated_delta_vs_baseline"] = output["simulated_month_pnl_after_abstention"] - baseline
    return output


def summarize_group(
    group: pd.DataFrame,
    *,
    min_loss_precision: float,
    max_winner_interventions: int,
    max_baseline_positive_degraded: int,
    min_current_negative_delta: float,
) -> dict[str, Any]:
    intervention = bool_series(group, "replacement_intervened", default=False)
    risk_loss = bool_series(group, "risk_trade_is_loss", default=False)
    replacement = bool_series(group, "replacement_chosen", default=False)
    baseline = numeric_series(group, "baseline_month_pnl", default=np.nan)
    after = numeric_series(group, "simulated_month_pnl_after_abstention", default=np.nan)
    delta = numeric_series(group, "simulated_delta_vs_baseline", default=0.0)
    current_negative = baseline.lt(0.0)
    current_nonnegative = baseline.ge(0.0)
    loss_interventions = int((intervention & risk_loss).sum())
    winner_interventions = int((intervention & ~risk_loss).sum())
    intervention_count = int(intervention.sum())
    precision = safe_rate(loss_interventions, intervention_count)
    baseline_positive_degraded = int((current_nonnegative & delta.lt(0.0)).sum())
    current_negative_delta = delta[current_negative]
    if int(current_negative.sum()) == 0:
        current_negative_min_delta = np.nan
        passes_current_negative_delta = True
    else:
        current_negative_min_delta = float(current_negative_delta.min())
        passes_current_negative_delta = bool(
            np.isfinite(current_negative_min_delta)
            and current_negative_min_delta >= float(min_current_negative_delta)
        )
    passes_loss_precision = True if intervention_count == 0 else bool(
        np.isfinite(precision) and precision >= float(min_loss_precision)
    )
    passes_winner_interventions = bool(winner_interventions <= int(max_winner_interventions))
    passes_baseline_positive_degradation = bool(
        baseline_positive_degraded <= int(max_baseline_positive_degraded)
    )
    violation_count = int(
        (not passes_loss_precision)
        + (not passes_winner_interventions)
        + (not passes_baseline_positive_degradation)
        + (not passes_current_negative_delta)
    )
    return {
        "target_count": int(len(group)),
        "replacement_available_count": int(replacement.sum()),
        "replacement_intervention_count": intervention_count,
        "replacement_abstained_count": int((replacement & ~intervention).sum()),
        "loss_intervention_count": loss_interventions,
        "winner_intervention_count": winner_interventions,
        "intervention_loss_precision": precision,
        "mean_simulated_month_pnl": float(after.mean()) if len(after) else np.nan,
        "min_simulated_month_pnl": float(after.min()) if len(after) else np.nan,
        "mean_simulated_delta": float(delta.mean()) if len(delta) else np.nan,
        "min_simulated_delta": float(delta.min()) if len(delta) else np.nan,
        "positive_after_count": int(after.gt(0.0).sum()),
        "baseline_positive_degraded_count": baseline_positive_degraded,
        "baseline_positive_flipped_negative_count": int((current_nonnegative & after.lt(0.0)).sum()),
        "current_negative_target_count": int(current_negative.sum()),
        "current_negative_mean_delta": float(current_negative_delta.mean())
        if len(current_negative_delta)
        else np.nan,
        "current_negative_min_delta": current_negative_min_delta,
        "current_negative_positive_after_count": int((current_negative & after.gt(0.0)).sum()),
        "passes_loss_precision": passes_loss_precision,
        "passes_winner_interventions": passes_winner_interventions,
        "passes_baseline_positive_degradation": passes_baseline_positive_degradation,
        "passes_current_negative_delta": passes_current_negative_delta,
        "abstention_constraint_violation_count": violation_count,
        "passes_abstention_constraints": bool(violation_count == 0),
    }


def summarize_gate_surface(
    simulated: pd.DataFrame,
    *,
    min_loss_precision: float,
    max_winner_interventions: int,
    max_baseline_positive_degraded: int,
    min_current_negative_delta: float,
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    group_cols = ["abstention_gate", "abstention_gate_family", "abstention_threshold", "abstention_uses_actual"] + GROUP_COLUMNS
    for keys, group in simulated.groupby(group_cols, dropna=False):
        row = dict(zip(group_cols, keys, strict=True))
        row.update(
            summarize_group(
                group,
                min_loss_precision=min_loss_precision,
                max_winner_interventions=max_winner_interventions,
                max_baseline_positive_degraded=max_baseline_positive_degraded,
                min_current_negative_delta=min_current_negative_delta,
            )
        )
        rows.append(row)
    return pd.DataFrame(rows).sort_values(
        [
            "passes_abstention_constraints",
            "abstention_uses_actual",
            "current_negative_mean_delta",
            "mean_simulated_delta",
            "abstention_constraint_violation_count",
            "winner_intervention_count",
        ],
        ascending=[False, True, False, False, True, True],
    )


def summarize_gate_overall(surface_summary: pd.DataFrame) -> pd.DataFrame:
    if surface_summary.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    group_cols = ["abstention_gate", "abstention_gate_family", "abstention_threshold", "abstention_uses_actual"]
    for keys, group in surface_summary.groupby(group_cols, dropna=False):
        passes = bool_series(group, "passes_abstention_constraints", default=False)
        rows.append(
            {
                **dict(zip(group_cols, keys, strict=True)),
                "surface_row_count": int(len(group)),
                "passing_surface_row_count": int(passes.sum()),
                "best_current_negative_mean_delta": float(
                    numeric_series(group, "current_negative_mean_delta", default=np.nan).max()
                ),
                "best_mean_simulated_delta": float(
                    numeric_series(group, "mean_simulated_delta", default=np.nan).max()
                ),
                "min_violation_count": int(
                    numeric_series(group, "abstention_constraint_violation_count", default=0.0).min()
                ),
                "min_winner_intervention_count": int(
                    numeric_series(group, "winner_intervention_count", default=0.0).min()
                ),
                "min_baseline_positive_degraded_count": int(
                    numeric_series(group, "baseline_positive_degraded_count", default=0.0).min()
                ),
            }
        )
    return pd.DataFrame(rows).sort_values(
        [
            "passing_surface_row_count",
            "abstention_uses_actual",
            "best_current_negative_mean_delta",
            "best_mean_simulated_delta",
            "min_violation_count",
        ],
        ascending=[False, True, False, False, True],
    )


def run_diagnostics(args: argparse.Namespace) -> Path:
    surface_run_dir = resolve_path(args.surface_run_dir)
    choices = load_choices(surface_run_dir)
    simulated_frames = [simulate_gate_choices(choices, spec) for spec in build_gate_specs(choices)]
    simulated = pd.concat(simulated_frames, ignore_index=True, sort=False)
    surface_summary = summarize_gate_surface(
        simulated,
        min_loss_precision=float(args.min_loss_precision),
        max_winner_interventions=int(args.max_winner_interventions),
        max_baseline_positive_degraded=int(args.max_baseline_positive_degraded),
        min_current_negative_delta=float(args.min_current_negative_delta),
    )
    gate_summary = summarize_gate_overall(surface_summary)

    run_dir = make_run_dir(resolve_path(args.output_root), args.run_label)
    simulated.to_csv(run_dir / "replacement_abstention_surface_choices.csv", index=False)
    surface_summary.to_csv(run_dir / "replacement_abstention_surface_summary.csv", index=False)
    gate_summary.to_csv(run_dir / "replacement_abstention_gate_summary.csv", index=False)
    meta = {
        "surface_run_dir": surface_run_dir,
        "min_loss_precision": args.min_loss_precision,
        "max_winner_interventions": args.max_winner_interventions,
        "max_baseline_positive_degraded": args.max_baseline_positive_degraded,
        "min_current_negative_delta": args.min_current_negative_delta,
        "note": (
            "This diagnostic simulates abstaining from a replacement candidate. If a "
            "candidate is abstained, the target is left at baseline rather than skip-only. "
            "Gate columns marked abstention_uses_actual are diagnostic-only leaks."
        ),
    }
    (run_dir / "replacement_abstention_meta.json").write_text(
        json.dumps(meta, indent=2, default=local_json_default) + "\n",
        encoding="utf-8",
    )
    print("Replacement abstention gate summary:")
    print(gate_summary.head(int(args.print_rows)).to_string(index=False))
    print("\nReplacement abstention surface summary:")
    columns = [
        "abstention_gate",
        "risk_selector",
        "replacement_score_mode",
        "candidate_min_prior_count",
        "replacement_intervention_count",
        "loss_intervention_count",
        "winner_intervention_count",
        "intervention_loss_precision",
        "baseline_positive_degraded_count",
        "current_negative_mean_delta",
        "mean_simulated_delta",
        "passes_abstention_constraints",
    ]
    print(surface_summary[[column for column in columns if column in surface_summary.columns]].head(int(args.print_rows)).to_string(index=False))
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--surface-run-dir", type=Path, default=DEFAULT_SURFACE_RUN_DIR)
    parser.add_argument("--min-loss-precision", type=float, default=0.5)
    parser.add_argument("--max-winner-interventions", type=int, default=0)
    parser.add_argument("--max-baseline-positive-degraded", type=int, default=0)
    parser.add_argument("--min-current-negative-delta", type=float, default=0.0)
    parser.add_argument("--output-root", type=Path, default=ROOT / "data/reports/backtests")
    parser.add_argument(
        "--run-label",
        default="entry_ev_replacement_abstention_surface_diagnostics",
    )
    parser.add_argument("--print-rows", type=int, default=20)
    return parser


def main(argv: list[str] | None = None) -> int:
    run_diagnostics(build_parser().parse_args(argv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
