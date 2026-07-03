#!/usr/bin/env python3
"""Summarize target-level outcomes for selector surface choices."""

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
from entry_ev_thin_month_opposite_candidate_diagnostics import (  # noqa: E402
    bool_series,
    numeric_series,
)


DEFAULT_SURFACE_RUN_DIR = (
    ROOT
    / "data/reports/backtests"
    / "20260703_125327_20260703_entry_ev_00378_074738_aligned_current_negative_selector_surface"
)


def resolve_path(value: str | Path, *, base: Path = ROOT) -> Path:
    path = Path(value)
    return path if path.is_absolute() else base / path


def load_choices(run_dir: Path) -> pd.DataFrame:
    return pd.read_csv(run_dir / "support_sufficient_selector_surface_choices.csv")


def classify_outcomes(choices: pd.DataFrame) -> pd.DataFrame:
    output = choices.copy()
    risk_selected = bool_series(output, "risk_trade_selected", default=False)
    risk_loss = bool_series(output, "risk_trade_is_loss", default=False)
    replacement = bool_series(output, "replacement_chosen", default=False)
    supported = numeric_series(output, "supported_candidate_rows", default=0.0).gt(0.0)
    delta = numeric_series(output, "delta_vs_baseline", default=0.0)
    after = numeric_series(output, "month_pnl_after_replacement", default=np.nan)
    category = pd.Series("unknown", index=output.index, dtype=object)
    category.loc[~risk_selected] = "no_risk_trade"
    category.loc[risk_selected & ~risk_loss] = "risk_trade_winner"
    category.loc[risk_selected & risk_loss & ~supported] = "loss_selected_no_supported_candidate"
    category.loc[risk_selected & risk_loss & supported & ~replacement] = "loss_selected_no_replacement"
    category.loc[risk_selected & risk_loss & replacement & delta.lt(0.0)] = "loss_replacement_degrades"
    category.loc[
        risk_selected
        & risk_loss
        & replacement
        & delta.ge(0.0)
        & after.lt(0.0)
    ] = "loss_replacement_improves_but_still_negative"
    category.loc[
        risk_selected
        & risk_loss
        & replacement
        & delta.ge(0.0)
        & after.ge(0.0)
    ] = "loss_replacement_repairs_month"
    output["target_outcome_category"] = category
    output["target_outcome_success"] = category.eq("loss_replacement_repairs_month")
    output["target_outcome_candidate_gap"] = category.eq("loss_selected_no_supported_candidate")
    output["target_outcome_risk_gap"] = category.isin(["no_risk_trade", "risk_trade_winner"])
    output["target_outcome_replacement_gap"] = category.isin(
        [
            "loss_selected_no_replacement",
            "loss_replacement_degrades",
            "loss_replacement_improves_but_still_negative",
        ]
    )
    return output


def summarize_outcomes(choices: pd.DataFrame) -> pd.DataFrame:
    if choices.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    group_columns = [column for column in GROUP_COLUMNS if column in choices.columns]
    for key, group in choices.groupby(group_columns, dropna=False):
        key_tuple = key if isinstance(key, tuple) else (key,)
        row = dict(zip(group_columns, key_tuple))
        baseline = numeric_series(group, "baseline_month_pnl", default=np.nan)
        after = numeric_series(group, "month_pnl_after_replacement", default=np.nan)
        delta = numeric_series(group, "delta_vs_baseline", default=0.0)
        categories = group["target_outcome_category"].astype(str)
        row.update(
            {
                "target_count": int(len(group)),
                "baseline_negative_count": int(baseline.lt(0.0).sum()),
                "success_count": int((categories == "loss_replacement_repairs_month").sum()),
                "candidate_gap_count": int(
                    (categories == "loss_selected_no_supported_candidate").sum()
                ),
                "risk_gap_count": int(categories.isin(["no_risk_trade", "risk_trade_winner"]).sum()),
                "replacement_gap_count": int(
                    categories.isin(
                        [
                            "loss_selected_no_replacement",
                            "loss_replacement_degrades",
                            "loss_replacement_improves_but_still_negative",
                        ]
                    ).sum()
                ),
                "winner_risk_count": int((categories == "risk_trade_winner").sum()),
                "no_risk_trade_count": int((categories == "no_risk_trade").sum()),
                "mean_after_pnl": float(after.mean()) if len(after) else np.nan,
                "min_after_pnl": float(after.min()) if len(after) else np.nan,
                "mean_delta": float(delta.mean()) if len(delta) else np.nan,
                "min_delta": float(delta.min()) if len(delta) else np.nan,
                "category_counts": ";".join(
                    f"{name}:{count}" for name, count in categories.value_counts().sort_index().items()
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
    choices = classify_outcomes(load_choices(surface_run_dir))
    summary = summarize_outcomes(choices)
    run_dir = make_run_dir(resolve_path(args.output_root), args.run_label)
    choices.to_csv(run_dir / "surface_target_outcome_choices.csv", index=False)
    summary.to_csv(run_dir / "surface_target_outcome_summary.csv", index=False)
    meta = {
        "surface_run_dir": surface_run_dir,
        "note": (
            "Classifies each target outcome within a selector surface row. "
            "It separates risk-selection gaps, candidate-support gaps, and replacement gaps."
        ),
    }
    (run_dir / "surface_target_outcome_meta.json").write_text(
        json.dumps(meta, indent=2, default=local_json_default) + "\n",
        encoding="utf-8",
    )
    print("Surface target outcome summary:")
    display = [
        "risk_selector",
        "replacement_score_mode",
        "candidate_min_prior_count",
        "target_count",
        "success_count",
        "candidate_gap_count",
        "risk_gap_count",
        "replacement_gap_count",
        "winner_risk_count",
        "mean_after_pnl",
        "mean_delta",
        "category_counts",
    ]
    print(summary[[column for column in display if column in summary.columns]].head(int(args.print_rows)).to_string(index=False))
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--surface-run-dir", type=Path, default=DEFAULT_SURFACE_RUN_DIR)
    parser.add_argument("--output-root", type=Path, default=ROOT / "data/reports/backtests")
    parser.add_argument(
        "--run-label",
        default="entry_ev_surface_target_outcome_diagnostics",
    )
    parser.add_argument("--print-rows", type=int, default=20)
    return parser


def main(argv: list[str] | None = None) -> int:
    run_diagnostics(build_parser().parse_args(argv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
