#!/usr/bin/env python3
"""Diagnose prior-only short-horizon overestimate uncertainty for entry-EV trades."""

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
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from trade_data.backtest import json_default, make_run_dir  # noqa: E402


DEFAULT_GROUP_SPECS = (
    "direction,session_regime;"
    "direction,combined_regime;"
    "combined_regime,session_regime;"
    "direction,combined_regime,session_regime;"
    "family,direction,combined_regime,session_regime;"
    "role,direction,combined_regime,session_regime"
)

TEXT_COLUMNS = [
    "source",
    "role",
    "family",
    "variant",
    "candidate",
    "month",
    "direction",
    "entry_timestamp",
    "combined_regime",
    "session_regime",
    "trend_regime",
    "volatility_regime",
    "gap_regime",
    "selector_variant",
    "entry_block_rule",
]


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


def parse_csv(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def parse_group_specs(value: str) -> list[list[str]]:
    specs: list[list[str]] = []
    for raw_spec in value.split(";"):
        columns = parse_csv(raw_spec)
        if columns:
            specs.append(columns)
    return specs


def read_trade_frames(paths: list[Path]) -> pd.DataFrame:
    if not paths:
        raise ValueError("at least one --trades path is required")
    frames = [pd.read_csv(path) for path in paths]
    return pd.concat(frames, ignore_index=True)


def numeric_series(frame: pd.DataFrame, column: str, default: float = np.nan) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    values = pd.to_numeric(frame[column], errors="coerce")
    return values.where(np.isfinite(values), default).fillna(default).astype(float)


def text_series(frame: pd.DataFrame, column: str, default: str = "missing") -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype="string")
    return (
        frame[column]
        .astype("string")
        .fillna(default)
        .str.strip()
        .replace({"": default, "nan": default, "None": default})
    )


def horizon_column_names(horizon_minutes: int) -> tuple[str, str]:
    suffix = f"{horizon_minutes}m"
    return f"selected_fixed_{suffix}_pred_pnl", f"selected_fixed_{suffix}_actual_pnl"


def normalize_trades(
    frame: pd.DataFrame,
    *,
    horizon_minutes: int,
    entry_block_rule: str | None,
    selector_variant_contains: str | None,
) -> pd.DataFrame:
    output = frame.copy()
    if entry_block_rule is not None and "entry_block_rule" in output.columns:
        output = output[output["entry_block_rule"].astype(str).eq(entry_block_rule)].copy()
    if selector_variant_contains:
        if "selector_variant" not in output.columns:
            raise ValueError("selector_variant_contains requires selector_variant column")
        output = output[
            output["selector_variant"]
            .astype(str)
            .str.contains(selector_variant_contains, regex=False, na=False)
        ].copy()

    pred_column, actual_column = horizon_column_names(horizon_minutes)
    required = {"month", "adjusted_pnl", "direction", pred_column, actual_column}
    missing = sorted(required - set(output.columns))
    if missing:
        raise ValueError(f"trade frame missing columns: {', '.join(missing)}")

    for column in TEXT_COLUMNS:
        output[column] = text_series(output, column)
    output["month"] = output["month"].astype(str).str.slice(0, 7)
    output["direction"] = output["direction"].astype(str).str.lower()
    output["adjusted_pnl"] = numeric_series(output, "adjusted_pnl", default=0.0)
    output["fixed_pred_pnl"] = numeric_series(output, pred_column)
    output["fixed_actual_pnl"] = numeric_series(output, actual_column)
    output["fixed_horizon_minutes"] = int(horizon_minutes)
    return output.reset_index(drop=True)


def add_short_horizon_targets(frame: pd.DataFrame) -> pd.DataFrame:
    output = frame.copy()
    output["fixed_error"] = output["fixed_pred_pnl"] - output["fixed_actual_pnl"]
    output["fixed_abs_error"] = output["fixed_error"].abs()
    output["fixed_overestimate"] = output["fixed_error"].clip(lower=0.0)
    output["fixed_pred_positive"] = output["fixed_pred_pnl"].gt(0.0)
    output["fixed_actual_negative"] = output["fixed_actual_pnl"].lt(0.0)
    output["fixed_false_positive"] = (
        output["fixed_pred_positive"] & output["fixed_actual_negative"]
    )
    output["is_loss"] = output["adjusted_pnl"].lt(0.0)
    return output


def make_group_key(frame: pd.DataFrame, columns: list[str]) -> pd.Series:
    if not columns:
        return pd.Series("all", index=frame.index, dtype="string")
    return frame[columns].astype(str).agg("|".join, axis=1)


def _zero_prior_columns(frame: pd.DataFrame) -> None:
    for column in [
        "prior_trade_count",
        "prior_month_count",
        "prior_adjusted_pnl_sum",
        "prior_adjusted_loss_count",
        "prior_fixed_pred_sum",
        "prior_fixed_actual_sum",
        "prior_fixed_error_sum",
        "prior_fixed_abs_error_sum",
        "prior_fixed_overestimate_sum",
        "prior_fixed_pred_positive_count",
        "prior_fixed_actual_negative_count",
        "prior_fixed_false_positive_count",
    ]:
        frame[column] = 0.0


def _safe_rate(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    output = pd.Series(np.nan, index=numerator.index, dtype=float)
    mask = denominator.astype(float).gt(0.0)
    output.loc[mask] = numerator.loc[mask].astype(float) / denominator.loc[mask].astype(float)
    return output


def add_prior_stats_for_group_spec(
    frame: pd.DataFrame,
    *,
    group_columns: list[str],
) -> pd.DataFrame:
    available = [column for column in group_columns if column in frame.columns]
    output = frame.copy()
    output["group_spec"] = ",".join(available) if available else "all"
    output["group_key"] = make_group_key(output, available)
    _zero_prior_columns(output)

    for _, group in output.groupby("group_key", sort=False, dropna=False):
        months = sorted(group["month"].astype(str).unique())
        prior = {
            "trade_count": 0.0,
            "month_count": 0.0,
            "adjusted_pnl_sum": 0.0,
            "adjusted_loss_count": 0.0,
            "fixed_pred_sum": 0.0,
            "fixed_actual_sum": 0.0,
            "fixed_error_sum": 0.0,
            "fixed_abs_error_sum": 0.0,
            "fixed_overestimate_sum": 0.0,
            "fixed_pred_positive_count": 0.0,
            "fixed_actual_negative_count": 0.0,
            "fixed_false_positive_count": 0.0,
        }
        for month in months:
            idx = group.index[group["month"].astype(str).eq(month)]
            output.loc[idx, "prior_trade_count"] = prior["trade_count"]
            output.loc[idx, "prior_month_count"] = prior["month_count"]
            output.loc[idx, "prior_adjusted_pnl_sum"] = prior["adjusted_pnl_sum"]
            output.loc[idx, "prior_adjusted_loss_count"] = prior["adjusted_loss_count"]
            output.loc[idx, "prior_fixed_pred_sum"] = prior["fixed_pred_sum"]
            output.loc[idx, "prior_fixed_actual_sum"] = prior["fixed_actual_sum"]
            output.loc[idx, "prior_fixed_error_sum"] = prior["fixed_error_sum"]
            output.loc[idx, "prior_fixed_abs_error_sum"] = prior["fixed_abs_error_sum"]
            output.loc[idx, "prior_fixed_overestimate_sum"] = prior[
                "fixed_overestimate_sum"
            ]
            output.loc[idx, "prior_fixed_pred_positive_count"] = prior[
                "fixed_pred_positive_count"
            ]
            output.loc[idx, "prior_fixed_actual_negative_count"] = prior[
                "fixed_actual_negative_count"
            ]
            output.loc[idx, "prior_fixed_false_positive_count"] = prior[
                "fixed_false_positive_count"
            ]

            current = output.loc[idx]
            prior["trade_count"] += float(len(current))
            prior["month_count"] += 1.0
            prior["adjusted_pnl_sum"] += float(current["adjusted_pnl"].sum())
            prior["adjusted_loss_count"] += float(current["is_loss"].astype(bool).sum())
            prior["fixed_pred_sum"] += float(current["fixed_pred_pnl"].sum())
            prior["fixed_actual_sum"] += float(current["fixed_actual_pnl"].sum())
            prior["fixed_error_sum"] += float(current["fixed_error"].sum())
            prior["fixed_abs_error_sum"] += float(current["fixed_abs_error"].sum())
            prior["fixed_overestimate_sum"] += float(current["fixed_overestimate"].sum())
            prior["fixed_pred_positive_count"] += float(
                current["fixed_pred_positive"].astype(bool).sum()
            )
            prior["fixed_actual_negative_count"] += float(
                current["fixed_actual_negative"].astype(bool).sum()
            )
            prior["fixed_false_positive_count"] += float(
                current["fixed_false_positive"].astype(bool).sum()
            )

    count = output["prior_trade_count"].astype(float)
    pred_positive_count = output["prior_fixed_pred_positive_count"].astype(float)
    output["prior_adjusted_pnl_mean"] = _safe_rate(
        output["prior_adjusted_pnl_sum"],
        count,
    )
    output["prior_adjusted_loss_rate"] = _safe_rate(
        output["prior_adjusted_loss_count"],
        count,
    )
    output["prior_fixed_pred_mean"] = _safe_rate(output["prior_fixed_pred_sum"], count)
    output["prior_fixed_actual_mean"] = _safe_rate(output["prior_fixed_actual_sum"], count)
    output["prior_fixed_error_mean"] = _safe_rate(output["prior_fixed_error_sum"], count)
    output["prior_fixed_abs_error_mean"] = _safe_rate(
        output["prior_fixed_abs_error_sum"],
        count,
    )
    output["prior_fixed_overestimate_mean"] = _safe_rate(
        output["prior_fixed_overestimate_sum"],
        count,
    )
    output["prior_fixed_pred_positive_rate"] = _safe_rate(
        output["prior_fixed_pred_positive_count"],
        count,
    )
    output["prior_fixed_actual_negative_rate"] = _safe_rate(
        output["prior_fixed_actual_negative_count"],
        count,
    )
    output["prior_fixed_false_positive_trade_rate"] = _safe_rate(
        output["prior_fixed_false_positive_count"],
        count,
    )
    output["prior_fixed_false_positive_rate"] = _safe_rate(
        output["prior_fixed_false_positive_count"],
        pred_positive_count,
    )

    fp_rate = output["prior_fixed_false_positive_rate"].fillna(0.0).clip(lower=0.0)
    actual_neg_rate = output["prior_fixed_actual_negative_rate"].fillna(0.0).clip(lower=0.0)
    overestimate_mean = output["prior_fixed_overestimate_mean"].fillna(0.0).clip(lower=0.0)
    negative_pnl_mean = (-output["prior_adjusted_pnl_mean"].fillna(0.0)).clip(lower=0.0)
    output["prior_fixed_uncertainty_pressure"] = (
        fp_rate + actual_neg_rate + overestimate_mean + negative_pnl_mean
    ) * np.log1p(count)
    return output


def build_prior_rows(frame: pd.DataFrame, group_specs: list[list[str]]) -> pd.DataFrame:
    rows = [
        add_prior_stats_for_group_spec(frame, group_columns=group_columns)
        for group_columns in group_specs
    ]
    if not rows:
        raise ValueError("at least one group spec is required")
    return pd.concat(rows, ignore_index=True)


def discovery_mask(
    frame: pd.DataFrame,
    *,
    roles: list[str],
    families: list[str],
    sources: list[str],
) -> pd.Series:
    mask = pd.Series(False, index=frame.index)
    if roles:
        mask |= frame["role"].astype(str).isin(roles)
    if families:
        mask |= frame["family"].astype(str).isin(families)
    if sources:
        mask |= frame["source"].astype(str).isin(sources)
    return mask


def add_scope_rows(
    frame: pd.DataFrame,
    *,
    roles: list[str],
    families: list[str],
    sources: list[str],
) -> pd.DataFrame:
    all_rows = frame.copy()
    all_rows["scope"] = "all"
    if not roles and not families and not sources:
        return all_rows
    discovery = discovery_mask(frame, roles=roles, families=families, sources=sources)
    discovery_rows = frame[discovery].copy()
    discovery_rows["scope"] = "discovery"
    holdout_rows = frame[~discovery].copy()
    holdout_rows["scope"] = "holdout"
    return pd.concat([all_rows, discovery_rows, holdout_rows], ignore_index=True)


def build_rule_masks(frame: pd.DataFrame) -> dict[str, pd.Series]:
    count = frame["prior_trade_count"].astype(float)
    pnl = frame["prior_adjusted_pnl_sum"].fillna(0.0).astype(float)
    fp_rate = frame["prior_fixed_false_positive_rate"].fillna(0.0).astype(float)
    actual_neg_rate = frame["prior_fixed_actual_negative_rate"].fillna(0.0).astype(float)
    overestimate_mean = frame["prior_fixed_overestimate_mean"].fillna(0.0).astype(float)
    pressure = frame["prior_fixed_uncertainty_pressure"].fillna(0.0).astype(float)
    return {
        "prior_count_ge3_fp_rate_ge0p5": count.ge(3.0) & fp_rate.ge(0.5),
        "prior_count_ge5_fp_rate_ge0p4": count.ge(5.0) & fp_rate.ge(0.4),
        "prior_count_ge5_fp_rate_ge0p4_overmean_gt1": count.ge(5.0)
        & fp_rate.ge(0.4)
        & overestimate_mean.gt(1.0),
        "prior_count_ge5_actual_neg_rate_ge0p5": count.ge(5.0)
        & actual_neg_rate.ge(0.5),
        "prior_count_ge5_pnl_neg_fp_rate_ge0p4": count.ge(5.0)
        & pnl.lt(0.0)
        & fp_rate.ge(0.4),
        "prior_count_ge5_overmean_gt2": count.ge(5.0) & overestimate_mean.gt(2.0),
        "prior_count_ge10_fp_rate_ge0p4": count.ge(10.0) & fp_rate.ge(0.4),
        "prior_count_ge5_pressure_ge4": count.ge(5.0) & pressure.ge(4.0),
    }


def summarize_rule_frame(frame: pd.DataFrame, mask: pd.Series) -> dict[str, Any]:
    flagged = frame[mask]
    false_positive = frame[frame["fixed_false_positive"].fillna(False).astype(bool)]
    final_losses = frame[frame["is_loss"].fillna(False).astype(bool)]
    flagged_fp = flagged[flagged["fixed_false_positive"].fillna(False).astype(bool)]
    flagged_losses = flagged[flagged["is_loss"].fillna(False).astype(bool)]
    total_pnl = float(frame["adjusted_pnl"].sum()) if len(frame) else 0.0
    flagged_pnl = float(flagged["adjusted_pnl"].sum()) if len(flagged) else 0.0
    return {
        "trade_count": int(len(frame)),
        "total_pnl": total_pnl,
        "false_positive_count": int(len(false_positive)),
        "final_loss_count": int(len(final_losses)),
        "flagged_trade_count": int(len(flagged)),
        "flagged_trade_share": float(len(flagged) / len(frame)) if len(frame) else 0.0,
        "flagged_pnl": flagged_pnl,
        "kept_pnl_if_removed": total_pnl - flagged_pnl,
        "block_delta_if_removed": -flagged_pnl,
        "flagged_false_positive_count": int(len(flagged_fp)),
        "false_positive_precision": float(len(flagged_fp) / len(flagged))
        if len(flagged)
        else 0.0,
        "false_positive_recall": float(len(flagged_fp) / len(false_positive))
        if len(false_positive)
        else 0.0,
        "flagged_final_loss_count": int(len(flagged_losses)),
        "final_loss_precision": float(len(flagged_losses) / len(flagged))
        if len(flagged)
        else 0.0,
        "final_loss_recall": float(len(flagged_losses) / len(final_losses))
        if len(final_losses)
        else 0.0,
        "flagged_fixed_actual_pnl_sum": float(flagged["fixed_actual_pnl"].sum())
        if len(flagged)
        else 0.0,
        "flagged_prior_count_mean": float(flagged["prior_trade_count"].mean())
        if len(flagged)
        else 0.0,
        "flagged_prior_fp_rate_mean": float(
            flagged["prior_fixed_false_positive_rate"].mean()
        )
        if len(flagged)
        else 0.0,
        "flagged_prior_pressure_mean": float(
            flagged["prior_fixed_uncertainty_pressure"].mean()
        )
        if len(flagged)
        else 0.0,
    }


def summarize_rules(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for keys, group in frame.groupby(["scope", "group_spec"], dropna=False):
        scope, group_spec = keys
        masks = build_rule_masks(group)
        for rule_name, mask in masks.items():
            row: dict[str, Any] = {
                "scope": scope,
                "group_spec": group_spec,
                "rule": rule_name,
            }
            row.update(summarize_rule_frame(group, mask))
            rows.append(row)
    return pd.DataFrame(rows).sort_values(
        [
            "scope",
            "block_delta_if_removed",
            "flagged_false_positive_count",
            "flagged_trade_count",
        ],
        ascending=[True, False, False, False],
    )


def summarize_contexts(frame: pd.DataFrame, group_specs: list[list[str]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for group_columns in group_specs:
        available = [column for column in group_columns if column in frame.columns]
        if not available:
            continue
        group_spec = ",".join(available)
        for keys, group in frame.groupby(available, dropna=False):
            if not isinstance(keys, tuple):
                keys = (keys,)
            fp = group[group["fixed_false_positive"].fillna(False).astype(bool)]
            losses = group[group["is_loss"].fillna(False).astype(bool)]
            row: dict[str, Any] = {
                "group_spec": group_spec,
                "group_key": "|".join(str(value) for value in keys),
                "trade_count": int(len(group)),
                "total_pnl": float(group["adjusted_pnl"].sum()),
                "false_positive_count": int(len(fp)),
                "false_positive_pnl": float(fp["adjusted_pnl"].sum()) if len(fp) else 0.0,
                "false_positive_rate": float(len(fp) / len(group)) if len(group) else 0.0,
                "final_loss_count": int(len(losses)),
                "final_loss_rate": float(len(losses) / len(group)) if len(group) else 0.0,
                "fixed_pred_positive_count": int(group["fixed_pred_positive"].sum()),
                "fixed_actual_negative_count": int(group["fixed_actual_negative"].sum()),
                "fixed_error_mean": float(group["fixed_error"].mean()) if len(group) else 0.0,
                "fixed_overestimate_mean": float(group["fixed_overestimate"].mean())
                if len(group)
                else 0.0,
            }
            for column, value in zip(available, keys):
                row[column] = value
            rows.append(row)
    return pd.DataFrame(rows).sort_values(
        ["false_positive_pnl", "false_positive_count", "trade_count"],
        ascending=[True, False, False],
    )


def target_rows(frame: pd.DataFrame, *, top_n: int) -> pd.DataFrame:
    columns = [
        "source",
        "role",
        "family",
        "month",
        "direction",
        "entry_timestamp",
        "adjusted_pnl",
        "fixed_pred_pnl",
        "fixed_actual_pnl",
        "fixed_error",
        "fixed_overestimate",
        "combined_regime",
        "session_regime",
        "selected_loss_first_prob",
        "pred_side_confidence_gap",
        "pred_taken_entry_local_rank",
        "pred_taken_ev",
        "selector_variant",
    ]
    available = [column for column in columns if column in frame.columns]
    rows = frame[frame["fixed_false_positive"].fillna(False).astype(bool)].copy()
    return rows.sort_values(["adjusted_pnl", "fixed_actual_pnl"]).head(top_n)[available]


def worst_prior_rows(frame: pd.DataFrame, *, top_n: int) -> pd.DataFrame:
    columns = [
        "scope",
        "group_spec",
        "group_key",
        "source",
        "role",
        "family",
        "month",
        "direction",
        "entry_timestamp",
        "adjusted_pnl",
        "fixed_pred_pnl",
        "fixed_actual_pnl",
        "fixed_false_positive",
        "combined_regime",
        "session_regime",
        "prior_trade_count",
        "prior_month_count",
        "prior_adjusted_pnl_sum",
        "prior_fixed_false_positive_rate",
        "prior_fixed_actual_negative_rate",
        "prior_fixed_overestimate_mean",
        "prior_fixed_uncertainty_pressure",
    ]
    available = [column for column in columns if column in frame.columns]
    return frame.sort_values(
        [
            "prior_fixed_uncertainty_pressure",
            "prior_trade_count",
            "adjusted_pnl",
        ],
        ascending=[False, False, True],
    ).head(top_n)[available]


def build_diagnostics(args: argparse.Namespace) -> Path:
    raw = read_trade_frames(args.trades)
    normalized = normalize_trades(
        raw,
        horizon_minutes=args.horizon_minutes,
        entry_block_rule=args.entry_block_rule,
        selector_variant_contains=args.selector_variant_contains,
    )
    targets = add_short_horizon_targets(normalized)
    group_specs = parse_group_specs(args.group_specs)
    prior_rows = build_prior_rows(targets, group_specs)
    scoped_rows = add_scope_rows(
        prior_rows,
        roles=parse_csv(args.discovery_roles),
        families=parse_csv(args.discovery_families),
        sources=parse_csv(args.discovery_sources),
    )
    rule_summary = summarize_rules(scoped_rows)
    context_summary = summarize_contexts(targets, group_specs)
    current_target_rows = target_rows(targets, top_n=args.top_n)
    worst_rows = worst_prior_rows(scoped_rows, top_n=args.top_n)

    run_dir = make_run_dir(args.output_dir, args.label)
    targets.to_csv(run_dir / "short_horizon_prior_uncertainty_base_rows.csv", index=False)
    prior_rows.to_csv(run_dir / "short_horizon_prior_uncertainty_rows.csv", index=False)
    rule_summary.to_csv(
        run_dir / "short_horizon_prior_uncertainty_rule_summary.csv",
        index=False,
    )
    context_summary.to_csv(
        run_dir / "short_horizon_prior_uncertainty_context_summary.csv",
        index=False,
    )
    current_target_rows.to_csv(
        run_dir / "short_horizon_prior_uncertainty_target_rows.csv",
        index=False,
    )
    worst_rows.to_csv(
        run_dir / "short_horizon_prior_uncertainty_worst_rows.csv",
        index=False,
    )
    config = {
        "trades": args.trades,
        "label": args.label,
        "horizon_minutes": args.horizon_minutes,
        "entry_block_rule": args.entry_block_rule,
        "selector_variant_contains": args.selector_variant_contains,
        "group_specs": args.group_specs,
        "discovery_roles": args.discovery_roles,
        "discovery_families": args.discovery_families,
        "discovery_sources": args.discovery_sources,
        "row_count": int(len(targets)),
        "prior_row_count": int(len(prior_rows)),
    }
    (run_dir / "config.json").write_text(
        json.dumps(config, indent=2, sort_keys=True, default=local_json_default),
        encoding="utf-8",
    )

    print(f"Wrote short-horizon prior uncertainty diagnostics to {run_dir}")
    print("\nTop rule summary:")
    print(rule_summary.head(args.top_n).to_string(index=False))
    print("\nWorst current fixed-horizon false positives:")
    print(current_target_rows.head(args.top_n).to_string(index=False))
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trades", type=Path, action="append", required=True)
    parser.add_argument(
        "--label",
        default="entry_ev_short_horizon_prior_uncertainty",
    )
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--horizon-minutes", type=int, default=60)
    parser.add_argument("--entry-block-rule", default="none")
    parser.add_argument("--selector-variant-contains")
    parser.add_argument("--group-specs", default=DEFAULT_GROUP_SPECS)
    parser.add_argument("--discovery-roles", default="")
    parser.add_argument("--discovery-families", default="")
    parser.add_argument("--discovery-sources", default="")
    parser.add_argument("--top-n", type=int, default=40)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    build_diagnostics(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
