#!/usr/bin/env python3
"""Walk-forward diagnostics for context-aware holding-cap exclusions."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
SCRIPT_DIR = Path(__file__).resolve().parent
for path in (SRC, SCRIPT_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from holding_cap_target_diagnostics import (  # noqa: E402
    add_derived_columns,
    expand_delta_paths,
    parse_csv_paths,
    read_delta_rows,
)
from trade_data.backtest import json_default, make_run_dir  # noqa: E402


def parse_csv_strings(value: str) -> list[str]:
    values = [part.strip() for part in value.split(",") if part.strip()]
    if not values:
        raise argparse.ArgumentTypeError("at least one value is required")
    return values


def context_id(frame: pd.DataFrame, context_columns: list[str]) -> pd.Series:
    missing = sorted(set(context_columns) - set(frame.columns))
    if missing:
        raise ValueError(f"missing context columns: {', '.join(missing)}")
    return frame[context_columns].astype("string").fillna("__missing__").agg(":".join, axis=1)


def prepare_direct_cap_examples(
    deltas: pd.DataFrame,
    *,
    focus_side: str,
    focus_regime: str | None,
    min_abs_cap_value: float = 1e-9,
) -> pd.DataFrame:
    frame = add_derived_columns(deltas)
    mask = (
        frame["delta_status"].astype(str).eq("common")
        & frame["direction"].astype(str).eq(focus_side)
        & frame["cap_delta_minutes"].gt(0)
        & frame["cap_value"].notna()
        & frame["cap_value"].abs().gt(min_abs_cap_value)
    )
    if focus_regime:
        mask &= frame["combined_regime"].astype(str).eq(focus_regime)
    examples = frame[mask].copy()
    examples["month"] = examples["month"].astype(str)
    return examples.sort_values(["month", "case_label", "entry_decision_timestamp"]).reset_index(drop=True)


def summarize_context_values(
    frame: pd.DataFrame,
    *,
    context_columns: list[str],
    prefix: str,
) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame(columns=[*context_columns, f"{prefix}_support"])
    working = frame.copy()
    for column in context_columns:
        working[column] = working[column].astype("string").fillna("__missing__")
    summary = (
        working.groupby(context_columns, observed=True, dropna=False)
        .agg(
            support=("cap_value", "size"),
            month_count=("month", "nunique"),
            cap_value_sum=("cap_value", "sum"),
            cap_value_mean=("cap_value", "mean"),
            beneficial_rate=("cap_beneficial", "mean"),
            harmful_rate=("cap_harmful", "mean"),
        )
        .reset_index()
    )
    return summary.rename(
        columns={
            "support": f"{prefix}_support",
            "month_count": f"{prefix}_month_count",
            "cap_value_sum": f"{prefix}_cap_value_sum",
            "cap_value_mean": f"{prefix}_cap_value_mean",
            "beneficial_rate": f"{prefix}_beneficial_rate",
            "harmful_rate": f"{prefix}_harmful_rate",
        }
    )


def select_prior_harmful_contexts(
    prior_profile: pd.DataFrame,
    *,
    min_prior_support: int,
    min_prior_months: int,
    max_prior_mean: float,
    max_prior_sum: float,
) -> pd.DataFrame:
    if prior_profile.empty:
        return prior_profile.copy()
    selected = prior_profile[
        prior_profile["prior_support"].ge(min_prior_support)
        & prior_profile["prior_month_count"].ge(min_prior_months)
        & prior_profile["prior_cap_value_mean"].lt(max_prior_mean)
        & prior_profile["prior_cap_value_sum"].lt(max_prior_sum)
    ].copy()
    return selected.sort_values(
        ["prior_cap_value_sum", "prior_cap_value_mean", "prior_support"],
        ascending=[True, True, False],
    ).reset_index(drop=True)


def _scope_frame(frame: pd.DataFrame, scope_column: str | None, scope_value: str) -> pd.DataFrame:
    if scope_column is None:
        return frame
    return frame[frame[scope_column].astype(str).eq(scope_value)].copy()


def walkforward_context_exclusions(
    examples: pd.DataFrame,
    *,
    context_columns: list[str],
    scope_column: str | None,
    min_prior_support: int,
    min_prior_months: int,
    max_prior_mean: float,
    max_prior_sum: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if examples.empty:
        return pd.DataFrame(), pd.DataFrame()
    months = sorted(examples["month"].astype(str).unique())
    month_rows: list[dict[str, object]] = []
    selected_rows: list[pd.DataFrame] = []
    scope_values = ["pooled"] if scope_column is None else sorted(examples[scope_column].astype(str).unique())

    for target_month in months:
        prior_all = examples[examples["month"].astype(str) < target_month].copy()
        holdout_all = examples[examples["month"].astype(str).eq(target_month)].copy()
        if prior_all.empty or holdout_all.empty:
            continue
        for scope_value in scope_values:
            prior = _scope_frame(prior_all, scope_column, scope_value)
            holdout = _scope_frame(holdout_all, scope_column, scope_value)
            if prior.empty or holdout.empty:
                continue

            prior_profile = summarize_context_values(
                prior,
                context_columns=context_columns,
                prefix="prior",
            )
            holdout_profile = summarize_context_values(
                holdout,
                context_columns=context_columns,
                prefix="holdout",
            )
            selected = select_prior_harmful_contexts(
                prior_profile,
                min_prior_support=min_prior_support,
                min_prior_months=min_prior_months,
                max_prior_mean=max_prior_mean,
                max_prior_sum=max_prior_sum,
            )
            selected = selected.merge(holdout_profile, on=context_columns, how="left")
            selected["target_month"] = target_month
            selected["scope"] = scope_value
            selected["selection_scope"] = scope_column or "pooled"
            if not selected.empty:
                selected["context_id"] = context_id(selected, context_columns)
                selected["holdout_support"] = selected["holdout_support"].fillna(0).astype(int)
                selected["holdout_cap_value_sum"] = selected["holdout_cap_value_sum"].fillna(0.0)
                selected["holdout_cap_value_mean"] = selected["holdout_cap_value_mean"].fillna(0.0)
                selected["excluded_would_help"] = selected["holdout_cap_value_sum"].lt(0.0)
                selected_rows.append(selected)
                selected_keys = set(selected["context_id"].astype(str))
            else:
                selected_keys = set()

            holdout = holdout.copy()
            holdout["context_id"] = context_id(holdout, context_columns)
            holdout["selected_for_exclusion"] = holdout["context_id"].astype(str).isin(selected_keys)
            base_cap_value_sum = float(holdout["cap_value"].sum())
            excluded_cap_value_sum = float(
                holdout.loc[holdout["selected_for_exclusion"], "cap_value"].sum()
            )
            kept_cap_value_sum = base_cap_value_sum - excluded_cap_value_sum
            month_rows.append(
                {
                    "target_month": target_month,
                    "selection_scope": scope_column or "pooled",
                    "scope": scope_value,
                    "prior_months": int(prior["month"].nunique()),
                    "prior_examples": int(len(prior)),
                    "holdout_examples": int(len(holdout)),
                    "selected_context_count": int(len(selected_keys)),
                    "excluded_holdout_examples": int(holdout["selected_for_exclusion"].sum()),
                    "base_cap_value_sum": base_cap_value_sum,
                    "excluded_cap_value_sum": excluded_cap_value_sum,
                    "kept_cap_value_sum": kept_cap_value_sum,
                    "exclusion_delta": kept_cap_value_sum - base_cap_value_sum,
                    "selected_contexts": ";".join(sorted(selected_keys)),
                }
            )

    month_summary = pd.DataFrame(month_rows)
    selected_contexts = pd.concat(selected_rows, ignore_index=True) if selected_rows else pd.DataFrame()
    if not selected_contexts.empty:
        order = [
            "target_month",
            "selection_scope",
            "scope",
            "context_id",
            *context_columns,
        ]
        other_columns = [column for column in selected_contexts.columns if column not in order]
        selected_contexts = selected_contexts[order + other_columns].sort_values(
            ["target_month", "selection_scope", "scope", "prior_cap_value_sum", "context_id"]
        )
    return month_summary, selected_contexts


def aggregate_walkforward(month_summary: pd.DataFrame) -> pd.DataFrame:
    if month_summary.empty:
        return pd.DataFrame()
    return (
        month_summary.groupby(["selection_scope", "scope"], dropna=False, observed=True)
        .agg(
            months=("target_month", "nunique"),
            prior_examples=("prior_examples", "sum"),
            holdout_examples=("holdout_examples", "sum"),
            selected_context_months=("selected_context_count", lambda series: int((series > 0).sum())),
            excluded_holdout_examples=("excluded_holdout_examples", "sum"),
            base_cap_value_sum=("base_cap_value_sum", "sum"),
            excluded_cap_value_sum=("excluded_cap_value_sum", "sum"),
            kept_cap_value_sum=("kept_cap_value_sum", "sum"),
            exclusion_delta=("exclusion_delta", "sum"),
        )
        .reset_index()
        .sort_values(["exclusion_delta", "kept_cap_value_sum"], ascending=[False, False])
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--delta-runs", type=parse_csv_paths, required=True)
    parser.add_argument("--focus-side", default="short")
    parser.add_argument("--focus-regime", default="range_low_vol")
    parser.add_argument("--context-columns", type=parse_csv_strings, default=["combined_regime", "session_regime"])
    parser.add_argument("--min-prior-support", type=int, default=3)
    parser.add_argument("--min-prior-months", type=int, default=2)
    parser.add_argument("--max-prior-mean", type=float, default=0.0)
    parser.add_argument("--max-prior-sum", type=float, default=0.0)
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="holding_cap_context_walkforward")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    run_dir = make_run_dir(args.output_dir, args.label)
    deltas = read_delta_rows(args.delta_runs)
    examples = prepare_direct_cap_examples(
        deltas,
        focus_side=args.focus_side,
        focus_regime=args.focus_regime,
    )
    examples.to_csv(run_dir / "direct_cap_target_examples.csv", index=False)

    pooled_month, pooled_selected = walkforward_context_exclusions(
        examples,
        context_columns=args.context_columns,
        scope_column=None,
        min_prior_support=args.min_prior_support,
        min_prior_months=args.min_prior_months,
        max_prior_mean=args.max_prior_mean,
        max_prior_sum=args.max_prior_sum,
    )
    by_case_month, by_case_selected = walkforward_context_exclusions(
        examples,
        context_columns=args.context_columns,
        scope_column="case_label",
        min_prior_support=args.min_prior_support,
        min_prior_months=args.min_prior_months,
        max_prior_mean=args.max_prior_mean,
        max_prior_sum=args.max_prior_sum,
    )
    month_summary = pd.concat([pooled_month, by_case_month], ignore_index=True)
    selected_contexts = pd.concat([pooled_selected, by_case_selected], ignore_index=True)
    aggregate = aggregate_walkforward(month_summary)

    month_summary.to_csv(run_dir / "walkforward_month_summary.csv", index=False)
    selected_contexts.to_csv(run_dir / "walkforward_selected_contexts.csv", index=False)
    aggregate.to_csv(run_dir / "walkforward_aggregate.csv", index=False)

    metrics = {
        "mode": "holding_cap_context_walkforward",
        "delta_runs": [str(path) for path in args.delta_runs],
        "expanded_delta_paths": [str(path) for path in expand_delta_paths(args.delta_runs)],
        "focus_side": args.focus_side,
        "focus_regime": args.focus_regime,
        "context_columns": args.context_columns,
        "selection": {
            "min_prior_support": args.min_prior_support,
            "min_prior_months": args.min_prior_months,
            "max_prior_mean": args.max_prior_mean,
            "max_prior_sum": args.max_prior_sum,
        },
        "rows": {
            "all_delta_rows": int(len(deltas)),
            "direct_cap_target_examples": int(len(examples)),
            "walkforward_month_rows": int(len(month_summary)),
            "walkforward_selected_context_rows": int(len(selected_contexts)),
        },
        "aggregate": aggregate.to_dict(orient="records"),
        "outputs": {
            "direct_cap_target_examples": str(run_dir / "direct_cap_target_examples.csv"),
            "walkforward_month_summary": str(run_dir / "walkforward_month_summary.csv"),
            "walkforward_selected_contexts": str(run_dir / "walkforward_selected_contexts.csv"),
            "walkforward_aggregate": str(run_dir / "walkforward_aggregate.csv"),
        },
    }
    with (run_dir / "metrics.json").open("w", encoding="utf-8") as handle:
        json.dump(metrics, handle, ensure_ascii=False, indent=2, default=json_default)

    print(json.dumps(metrics, ensure_ascii=False, indent=2, default=json_default))
    print("artifacts:", run_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
