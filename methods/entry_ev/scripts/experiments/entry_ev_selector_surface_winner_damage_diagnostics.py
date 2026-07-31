#!/usr/bin/env python3
"""Diagnose winner damage in support-sufficient selector surface outputs."""

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
from entry_ev_thin_month_opposite_candidate_diagnostics import (  # noqa: E402
    bool_series,
    numeric_series,
)


DEFAULT_SURFACE_RUN_DIR = (
    ROOT
    / "data/reports/backtests"
    / "20260703_080722_20260703_entry_ev_00371_canonical_support_sufficient_selector_surface"
)
GROUP_COLUMNS = [
    "risk_selector",
    "replacement_score_mode",
    "calibration_min_context_count",
    "candidate_min_prior_count",
    "candidate_min_prior_month_count",
    "candidate_min_prior_actual_mean",
]


def resolve_path(value: str | Path, *, base: Path = ROOT) -> Path:
    path = Path(value)
    return path if path.is_absolute() else base / path


def load_surface_run(run_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    choices = pd.read_csv(run_dir / "support_sufficient_selector_surface_choices.csv")
    targets = pd.read_csv(run_dir / "support_sufficient_selector_surface_targets.csv")
    inventory_path = run_dir / "support_sufficient_selector_surface_target_inventory.csv"
    inventory = pd.read_csv(inventory_path) if inventory_path.exists() else pd.DataFrame()
    return choices, targets, inventory


def annotate_choices(choices: pd.DataFrame) -> pd.DataFrame:
    if choices.empty:
        return choices.copy()
    output = choices.copy()
    baseline = numeric_series(output, "baseline_month_pnl", default=np.nan)
    after = numeric_series(output, "month_pnl_after_replacement", default=np.nan)
    delta = numeric_series(output, "delta_vs_baseline", default=0.0)
    risk_selected = bool_series(output, "risk_trade_selected", default=False)
    risk_loss = bool_series(output, "risk_trade_is_loss", default=False)
    risk_pnl = numeric_series(output, "risk_trade_adjusted_pnl", default=np.nan)
    output["baseline_bucket"] = np.where(
        baseline.lt(0.0),
        "current_negative",
        "current_nonnegative",
    )
    output["risk_selected_loss"] = risk_selected & risk_loss
    output["risk_selected_winner"] = risk_selected & ~risk_loss
    output["risk_selected_positive_pnl"] = risk_selected & risk_pnl.gt(0.0)
    output["target_improved"] = delta.gt(0.0)
    output["target_degraded"] = delta.lt(0.0)
    output["target_positive_after"] = after.gt(0.0)
    output["baseline_positive_degraded"] = baseline.ge(0.0) & delta.lt(0.0)
    output["baseline_positive_flipped_negative"] = baseline.ge(0.0) & after.lt(0.0)
    output["current_negative_improved"] = baseline.lt(0.0) & delta.gt(0.0)
    output["current_negative_positive_after"] = baseline.lt(0.0) & after.gt(0.0)
    output["winner_selected_and_degraded"] = output["risk_selected_winner"] & delta.lt(0.0)
    return output


def _safe_rate(numerator: float, denominator: float) -> float:
    return float(numerator / denominator) if denominator else np.nan


def summarize_group(group: pd.DataFrame, *, prefix: str = "") -> dict[str, Any]:
    risk_selected = bool_series(group, "risk_trade_selected", default=False)
    selected_loss = bool_series(group, "risk_selected_loss", default=False)
    selected_winner = bool_series(group, "risk_selected_winner", default=False)
    replacement = bool_series(group, "replacement_chosen", default=False)
    target_improved = bool_series(group, "target_improved", default=False)
    target_degraded = bool_series(group, "target_degraded", default=False)
    after = numeric_series(group, "month_pnl_after_replacement", default=np.nan)
    delta = numeric_series(group, "delta_vs_baseline", default=0.0)
    baseline = numeric_series(group, "baseline_month_pnl", default=np.nan)
    risk_pnl = numeric_series(group, "risk_trade_adjusted_pnl", default=0.0)
    selected_count = int(risk_selected.sum())
    loss_count = int(selected_loss.sum())
    winner_count = int(selected_winner.sum())
    return {
        f"{prefix}target_count": int(len(group)),
        f"{prefix}risk_selected_count": selected_count,
        f"{prefix}loss_selected_count": loss_count,
        f"{prefix}winner_selected_count": winner_count,
        f"{prefix}loss_selection_precision": _safe_rate(loss_count, selected_count),
        f"{prefix}replacement_count": int(replacement.sum()),
        f"{prefix}improved_count": int(target_improved.sum()),
        f"{prefix}degraded_count": int(target_degraded.sum()),
        f"{prefix}positive_after_count": int(after.gt(0.0).sum()),
        f"{prefix}mean_baseline_pnl": float(baseline.mean()) if len(group) else np.nan,
        f"{prefix}mean_after_pnl": float(after.mean()) if len(group) else np.nan,
        f"{prefix}min_after_pnl": float(after.min()) if len(group) else np.nan,
        f"{prefix}mean_delta": float(delta.mean()) if len(group) else np.nan,
        f"{prefix}min_delta": float(delta.min()) if len(group) else np.nan,
        f"{prefix}selected_winner_pnl_sum": float(risk_pnl.where(selected_winner, 0.0).sum()),
        f"{prefix}selected_loss_pnl_sum": float(risk_pnl.where(selected_loss, 0.0).sum()),
        f"{prefix}winner_selected_and_degraded_count": int(
            bool_series(group, "winner_selected_and_degraded", default=False).sum()
        ),
        f"{prefix}baseline_positive_degraded_count": int(
            bool_series(group, "baseline_positive_degraded", default=False).sum()
        ),
        f"{prefix}baseline_positive_flipped_negative_count": int(
            bool_series(group, "baseline_positive_flipped_negative", default=False).sum()
        ),
        f"{prefix}current_negative_improved_count": int(
            bool_series(group, "current_negative_improved", default=False).sum()
        ),
        f"{prefix}current_negative_positive_after_count": int(
            bool_series(group, "current_negative_positive_after", default=False).sum()
        ),
    }


def summarize_winner_damage(
    choices: pd.DataFrame,
    *,
    min_loss_precision: float,
    max_winner_selected: int,
    max_baseline_positive_degraded: int,
    min_current_negative_delta: float,
) -> pd.DataFrame:
    annotated = annotate_choices(choices)
    if annotated.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for keys, group in annotated.groupby(GROUP_COLUMNS, dropna=False):
        row = dict(zip(GROUP_COLUMNS, keys, strict=True))
        row.update(summarize_group(group))
        negative = group[group["baseline_bucket"].eq("current_negative")]
        nonnegative = group[group["baseline_bucket"].eq("current_nonnegative")]
        row.update(summarize_group(negative, prefix="current_negative_"))
        row.update(summarize_group(nonnegative, prefix="current_nonnegative_"))
        precision = row["loss_selection_precision"]
        row["passes_loss_precision"] = bool(
            np.isfinite(precision) and precision >= float(min_loss_precision)
        )
        row["passes_winner_selected"] = bool(
            row["winner_selected_count"] <= int(max_winner_selected)
        )
        row["passes_baseline_positive_degradation"] = bool(
            row["baseline_positive_degraded_count"] <= int(max_baseline_positive_degraded)
        )
        current_negative_delta = row["current_negative_min_delta"]
        if row["current_negative_target_count"] == 0:
            row["passes_current_negative_delta"] = True
        else:
            row["passes_current_negative_delta"] = bool(
                np.isfinite(current_negative_delta)
                and current_negative_delta >= float(min_current_negative_delta)
            )
        row["passes_winner_damage_constraints"] = bool(
            row["passes_loss_precision"]
            and row["passes_winner_selected"]
            and row["passes_baseline_positive_degradation"]
            and row["passes_current_negative_delta"]
        )
        rows.append(row)
    return pd.DataFrame(rows).sort_values(
        [
            "passes_winner_damage_constraints",
            "loss_selection_precision",
            "winner_selected_count",
            "mean_delta",
        ],
        ascending=[False, False, True, False],
    )


def target_coverage(inventory: pd.DataFrame, targets: pd.DataFrame) -> pd.DataFrame:
    if inventory.empty:
        return targets.copy()
    output = inventory.copy()
    if "evaluated_by_surface" not in output.columns and not targets.empty:
        keys = set(zip(targets["role"].astype(str), targets["family"].astype(str), targets["month"].astype(str)))
        output["evaluated_by_surface"] = [
            (str(row["role"]), str(row["family"]), str(row["month"])) in keys
            for _, row in output.iterrows()
        ]
    return output


def run_diagnostics(args: argparse.Namespace) -> Path:
    surface_run_dir = resolve_path(args.surface_run_dir)
    choices, targets, inventory = load_surface_run(surface_run_dir)
    annotated = annotate_choices(choices)
    summary = summarize_winner_damage(
        annotated,
        min_loss_precision=float(args.min_loss_precision),
        max_winner_selected=int(args.max_winner_selected),
        max_baseline_positive_degraded=int(args.max_baseline_positive_degraded),
        min_current_negative_delta=float(args.min_current_negative_delta),
    )
    coverage = target_coverage(inventory, targets)

    run_dir = make_run_dir(resolve_path(args.output_root), args.run_label)
    annotated.to_csv(run_dir / "selector_surface_winner_damage_choices.csv", index=False)
    summary.to_csv(run_dir / "selector_surface_winner_damage_summary.csv", index=False)
    coverage.to_csv(run_dir / "selector_surface_winner_damage_target_coverage.csv", index=False)
    meta = {
        "surface_run_dir": surface_run_dir,
        "min_loss_precision": args.min_loss_precision,
        "max_winner_selected": args.max_winner_selected,
        "max_baseline_positive_degraded": args.max_baseline_positive_degraded,
        "min_current_negative_delta": args.min_current_negative_delta,
        "note": (
            "This is a post-process diagnostic for selector surfaces. It separates "
            "current-negative repair from cross-artifact target robustness and treats "
            "winner selection as risk-selector damage even when replacement improves PnL."
        ),
    }
    (run_dir / "selector_surface_winner_damage_meta.json").write_text(
        json.dumps(meta, indent=2, default=local_json_default) + "\n",
        encoding="utf-8",
    )

    print("Winner-damage constrained summary:")
    columns = [
        "risk_selector",
        "replacement_score_mode",
        "candidate_min_prior_count",
        "target_count",
        "loss_selected_count",
        "winner_selected_count",
        "loss_selection_precision",
        "baseline_positive_degraded_count",
        "current_negative_min_delta",
        "mean_delta",
        "min_delta",
        "passes_winner_damage_constraints",
    ]
    print(summary[columns].head(int(args.print_rows)).to_string(index=False))
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--surface-run-dir", type=Path, default=DEFAULT_SURFACE_RUN_DIR)
    parser.add_argument("--min-loss-precision", type=float, default=0.5)
    parser.add_argument("--max-winner-selected", type=int, default=0)
    parser.add_argument("--max-baseline-positive-degraded", type=int, default=0)
    parser.add_argument("--min-current-negative-delta", type=float, default=0.0)
    parser.add_argument("--output-root", type=Path, default=ROOT / "data/reports/backtests")
    parser.add_argument(
        "--run-label",
        default="entry_ev_selector_surface_winner_damage_diagnostics",
    )
    parser.add_argument("--print-rows", type=int, default=20)
    return parser


def main(argv: list[str] | None = None) -> int:
    run_diagnostics(build_parser().parse_args(argv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
