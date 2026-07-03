#!/usr/bin/env python3
"""Diagnose target-local confidence features for support-repair horizon rows."""

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
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from trade_data.backtest import json_default, make_run_dir  # noqa: E402


DEFAULT_TARGETS = "fresh2024_validation:2024-03:long"
DEFAULT_ROW_SCOPES = "available_candidates"
DEFAULT_NUMERIC_FEATURES = (
    "entry_hour,side_score,side_margin,score_pct,side_margin_pct,entry_rank_pct,"
    "pred_executable_prob,pred_pnl,pred_tail_loss_prob"
)
DEFAULT_HIGH_FEATURES = (
    "entry_hour,side_score,side_margin,score_pct,side_margin_pct,entry_rank_pct,"
    "pred_executable_prob,pred_pnl"
)
DEFAULT_LOW_FEATURES = "pred_tail_loss_prob"
REQUIRED_COLUMNS = {
    "role",
    "month",
    "side",
    "decision_timestamp",
    "row_scope",
    "horizon_minutes",
    "actual_pnl",
    "pred_executable_prob",
    "pred_pnl",
    "pred_tail_loss_prob",
    "pred_model_used",
}


@dataclass(frozen=True)
class RuleSpec:
    rule: str
    horizon_minutes: float | None
    feature: str | None = None
    operator: str | None = None
    threshold: float | None = None


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
    return [item.strip() for item in str(value).split(",") if item.strip()]


def parse_targets(value: str) -> list[tuple[str, str, str]]:
    targets: list[tuple[str, str, str]] = []
    for item in parse_csv(value):
        parts = item.split(":")
        if len(parts) != 3:
            raise ValueError(f"target must be role:YYYY-MM:side: {item}")
        role, month, side = parts
        if not role or not month or not side:
            raise ValueError(f"target must be role:YYYY-MM:side: {item}")
        targets.append((role, month[:7], side))
    return targets


def numeric_series(frame: pd.DataFrame, column: str, default: float = np.nan) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    return (
        pd.to_numeric(frame[column], errors="coerce")
        .replace([np.inf, -np.inf], np.nan)
        .fillna(default)
        .astype(float)
    )


def bool_series(frame: pd.DataFrame, column: str, default: bool = False) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=bool)
    values = frame[column]
    if pd.api.types.is_bool_dtype(values):
        return values.fillna(default).astype(bool)
    if pd.api.types.is_numeric_dtype(values):
        return values.fillna(float(default)).astype(float).ne(0.0)
    return (
        values.fillna(str(default))
        .astype(str)
        .str.lower()
        .str.strip()
        .isin({"true", "1", "yes", "y"})
    )


def text_series(frame: pd.DataFrame, column: str, default: str = "") -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=object)
    return frame[column].fillna(default).astype(str)


def normalize_horizon_rows(frame: pd.DataFrame) -> pd.DataFrame:
    missing = sorted(REQUIRED_COLUMNS - set(frame.columns))
    if missing:
        raise ValueError("horizon rows missing columns: " + ", ".join(missing))
    output = frame.copy()
    for column in ["family", "role", "side", "needed_side", "row_scope", "selection_bucket"]:
        output[column] = text_series(output, column)
    output["month"] = output["month"].astype(str).str.slice(0, 7)
    output["decision_timestamp"] = pd.to_datetime(
        output["decision_timestamp"],
        utc=True,
        errors="coerce",
    )
    output = output[output["decision_timestamp"].notna()].copy()
    for column in [
        "horizon_minutes",
        "actual_pnl",
        "pred_executable_prob",
        "pred_pnl",
        "pred_tail_loss_prob",
        "entry_hour",
        "side_score",
        "side_margin",
        "score_pct",
        "side_margin_pct",
        "entry_rank_pct",
        "target_fixed_best_adjusted_pnl",
        "target_fixed_best_horizon_minutes",
    ]:
        output[column] = numeric_series(output, column)
    output["pred_model_used"] = bool_series(output, "pred_model_used")
    output["actual_positive_label"] = output["actual_pnl"].gt(0.0)
    output["actual_tail_loss_label"] = output["actual_pnl"].le(-5.0)
    output["fallback_non_model_label"] = ~output["pred_model_used"]
    output["target_key"] = (
        output["role"].astype(str)
        + "|"
        + output["month"].astype(str)
        + "|"
        + output["side"].astype(str)
    )
    output["candidate_key"] = (
        output["target_key"]
        + "|"
        + output["decision_timestamp"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        + "|"
        + output["horizon_minutes"].round().astype(int).astype(str)
    )
    return output.reset_index(drop=True)


def filter_targets(
    frame: pd.DataFrame,
    *,
    targets: list[tuple[str, str, str]],
    row_scopes: list[str],
) -> pd.DataFrame:
    output = frame.copy()
    if targets:
        target_index = pd.MultiIndex.from_tuples(targets, names=["role", "month", "side"])
        current_index = pd.MultiIndex.from_frame(output[["role", "month", "side"]])
        output = output[current_index.isin(target_index)].copy()
    if row_scopes:
        output = output[output["row_scope"].isin(row_scopes)].copy()
    return output.reset_index(drop=True)


def quantile_thresholds(values: pd.Series, *, max_thresholds: int) -> list[float]:
    valid = pd.to_numeric(values, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if valid.empty:
        return []
    quantiles = np.linspace(0.0, 1.0, num=max(2, max_thresholds))
    thresholds = sorted({float(valid.quantile(q)) for q in quantiles})
    if len(thresholds) > max_thresholds:
        step = max(1, len(thresholds) // max_thresholds)
        thresholds = thresholds[::step][:max_thresholds]
    return thresholds


def build_rule_specs(
    frame: pd.DataFrame,
    *,
    numeric_features: list[str],
    high_features: list[str],
    low_features: list[str],
    max_thresholds_per_feature: int,
) -> list[RuleSpec]:
    specs: list[RuleSpec] = [RuleSpec(rule="all", horizon_minutes=None)]
    horizons = sorted(numeric_series(frame, "horizon_minutes").dropna().unique().tolist())
    for horizon in horizons:
        specs.append(RuleSpec(rule=f"horizon_eq_{int(horizon)}", horizon_minutes=float(horizon)))
    for horizon in horizons:
        for feature in numeric_features:
            if feature not in frame.columns:
                continue
            thresholds = quantile_thresholds(
                numeric_series(frame, feature),
                max_thresholds=max_thresholds_per_feature,
            )
            if feature in high_features:
                for threshold in thresholds:
                    specs.append(
                        RuleSpec(
                            rule=f"horizon_eq_{int(horizon)}__{feature}_ge_{threshold:g}",
                            horizon_minutes=float(horizon),
                            feature=feature,
                            operator=">=",
                            threshold=float(threshold),
                        )
                    )
            if feature in low_features:
                for threshold in thresholds:
                    specs.append(
                        RuleSpec(
                            rule=f"horizon_eq_{int(horizon)}__{feature}_le_{threshold:g}",
                            horizon_minutes=float(horizon),
                            feature=feature,
                            operator="<=",
                            threshold=float(threshold),
                        )
                    )
    return specs


def rule_mask(frame: pd.DataFrame, spec: RuleSpec) -> pd.Series:
    mask = pd.Series(True, index=frame.index, dtype=bool)
    if spec.horizon_minutes is not None:
        mask &= numeric_series(frame, "horizon_minutes").round().eq(round(spec.horizon_minutes))
    if spec.feature is not None and spec.operator is not None and spec.threshold is not None:
        values = numeric_series(frame, spec.feature)
        if spec.operator == ">=":
            mask &= values.ge(spec.threshold)
        elif spec.operator == "<=":
            mask &= values.le(spec.threshold)
        else:
            raise ValueError(f"unsupported operator: {spec.operator}")
    return mask


def summarize_selected(frame: pd.DataFrame, *, prefix: str) -> dict[str, Any]:
    actual = numeric_series(frame, "actual_pnl")
    positive = actual.gt(0.0)
    tail = actual.le(-5.0)
    return {
        f"{prefix}_count": int(len(frame)),
        f"{prefix}_actual_sum": float(actual.sum()) if len(frame) else 0.0,
        f"{prefix}_actual_mean": float(actual.mean()) if len(frame) else np.nan,
        f"{prefix}_actual_min": float(actual.min()) if len(frame) else np.nan,
        f"{prefix}_actual_max": float(actual.max()) if len(frame) else np.nan,
        f"{prefix}_positive_count": int(positive.sum()) if len(frame) else 0,
        f"{prefix}_positive_rate": float(positive.mean()) if len(frame) else np.nan,
        f"{prefix}_tail_loss_count": int(tail.sum()) if len(frame) else 0,
        f"{prefix}_tail_loss_rate": float(tail.mean()) if len(frame) else np.nan,
        f"{prefix}_model_used_count": int(bool_series(frame, "pred_model_used").sum())
        if len(frame)
        else 0,
        f"{prefix}_fallback_non_model_count": int(
            bool_series(frame, "fallback_non_model_label").sum()
        )
        if len(frame)
        else 0,
    }


def rule_surface(frame: pd.DataFrame, specs: list[RuleSpec]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if frame.empty:
        return pd.DataFrame()
    total_positive = int(bool_series(frame, "actual_positive_label").sum())
    for spec in specs:
        selected = frame[rule_mask(frame, spec)].copy()
        row: dict[str, Any] = {
            "rule": spec.rule,
            "horizon_minutes": spec.horizon_minutes,
            "feature": spec.feature or "",
            "operator": spec.operator or "",
            "threshold": spec.threshold,
            "target_count": int(len(frame)),
            "target_positive_count": total_positive,
        }
        row.update(summarize_selected(selected, prefix="selected"))
        row["positive_capture_rate"] = (
            float(row["selected_positive_count"] / total_positive)
            if total_positive
            else np.nan
        )
        row["rule_quality_score"] = (
            float(row["selected_actual_sum"])
            - 5.0 * float(row["selected_tail_loss_count"])
            + 2.0 * float(row["selected_positive_count"])
        )
        rows.append(row)
    return pd.DataFrame(rows).sort_values(
        ["rule_quality_score", "selected_actual_sum", "selected_positive_rate", "selected_count"],
        ascending=[False, False, False, True],
        kind="mergesort",
    )


def feature_bins(frame: pd.DataFrame, *, numeric_features: list[str], bins: int) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for feature in numeric_features:
        if feature not in frame.columns:
            continue
        values = numeric_series(frame, feature)
        valid = frame[values.notna()].copy()
        if valid.empty:
            continue
        valid[feature] = values.loc[valid.index]
        try:
            valid["feature_bin"] = pd.qcut(
                valid[feature],
                q=min(bins, max(1, valid[feature].nunique())),
                duplicates="drop",
            ).astype(str)
        except ValueError:
            valid["feature_bin"] = "all"
        for (horizon, feature_bin), group in valid.groupby(
            ["horizon_minutes", "feature_bin"],
            dropna=False,
            sort=False,
        ):
            row: dict[str, Any] = {
                "feature": feature,
                "horizon_minutes": horizon,
                "feature_bin": feature_bin,
                "feature_min": float(numeric_series(group, feature).min()),
                "feature_max": float(numeric_series(group, feature).max()),
            }
            row.update(summarize_selected(group, prefix="bin"))
            rows.append(row)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(
        ["feature", "horizon_minutes", "feature_min"],
        kind="mergesort",
    )


def target_summary(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for target_key, group in frame.groupby("target_key", dropna=False, sort=False):
        row: dict[str, Any] = {
            "target_key": target_key,
            "role": group.iloc[0]["role"],
            "family": group.iloc[0]["family"],
            "month": group.iloc[0]["month"],
            "side": group.iloc[0]["side"],
            "row_scope_count": int(group["row_scope"].nunique()),
            "decision_count": int(group["decision_timestamp"].nunique()),
            "horizon_count": int(group["horizon_minutes"].nunique()),
        }
        row.update(summarize_selected(group, prefix="all_rows"))
        for horizon, horizon_group in group.groupby("horizon_minutes", dropna=False):
            prefix = f"h{int(float(horizon))}"
            row.update(summarize_selected(horizon_group, prefix=prefix))
        rows.append(row)
    return pd.DataFrame(rows)


def candidate_examples(
    frame: pd.DataFrame,
    *,
    rule_summary: pd.DataFrame,
    top_n: int,
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    if frame.empty:
        return pd.DataFrame()
    oracle = frame.sort_values(
        ["actual_pnl", "decision_timestamp"],
        ascending=[False, True],
        kind="mergesort",
    ).head(top_n)
    oracle = oracle.copy()
    oracle.insert(0, "example_set", "oracle_actual_top")
    frames.append(oracle)

    pred_top = frame.sort_values(
        ["pred_pnl", "pred_executable_prob", "decision_timestamp"],
        ascending=[False, False, True],
        kind="mergesort",
    ).head(top_n)
    pred_top = pred_top.copy()
    pred_top.insert(0, "example_set", "observable_pred_pnl_top")
    frames.append(pred_top)

    if not rule_summary.empty:
        horizon_value = rule_summary.iloc[0]["horizon_minutes"]
        feature_value = rule_summary.iloc[0]["feature"]
        operator_value = rule_summary.iloc[0]["operator"]
        threshold_value = rule_summary.iloc[0]["threshold"]
        best_rule = str(rule_summary.iloc[0]["rule"])
        spec = RuleSpec(
            rule=best_rule,
            horizon_minutes=float(horizon_value) if pd.notna(horizon_value) else None,
            feature=str(feature_value) if pd.notna(feature_value) and str(feature_value) else None,
            operator=str(operator_value)
            if pd.notna(operator_value) and str(operator_value)
            else None,
            threshold=float(threshold_value) if pd.notna(threshold_value) else None,
        )
        best = frame[rule_mask(frame, spec)].copy().head(top_n)
        best.insert(0, "example_set", "posthoc_rule_top")
        frames.append(best)
    output = pd.concat(frames, ignore_index=True, sort=False)
    columns = [
        "example_set",
        "target_key",
        "candidate_key",
        "family",
        "role",
        "month",
        "side",
        "row_scope",
        "selection_bucket",
        "selected_any",
        "decision_timestamp",
        "horizon_minutes",
        "actual_pnl",
        "actual_positive_label",
        "actual_tail_loss_label",
        "pred_model_used",
        "pred_pnl",
        "pred_executable_prob",
        "pred_tail_loss_prob",
        "entry_hour",
        "side_score",
        "side_margin",
        "score_pct",
        "side_margin_pct",
        "entry_rank_pct",
    ]
    return output[[column for column in columns if column in output.columns]]


def run_diagnostics(args: argparse.Namespace) -> Path:
    rows = normalize_horizon_rows(pd.read_csv(args.horizon_rows))
    filtered = filter_targets(
        rows,
        targets=parse_targets(args.targets),
        row_scopes=parse_csv(args.row_scopes),
    )
    numeric_features = parse_csv(args.numeric_features)
    specs = build_rule_specs(
        filtered,
        numeric_features=numeric_features,
        high_features=parse_csv(args.high_features),
        low_features=parse_csv(args.low_features),
        max_thresholds_per_feature=args.max_thresholds_per_feature,
    )
    rules = rule_surface(filtered, specs)
    bins = feature_bins(filtered, numeric_features=numeric_features, bins=args.feature_bins)
    targets = target_summary(filtered)
    examples = candidate_examples(filtered, rule_summary=rules, top_n=args.top_n)

    run_dir = make_run_dir(args.output_dir, args.label)
    filtered.to_csv(run_dir / "target_local_confidence_rows.csv", index=False)
    targets.to_csv(run_dir / "target_local_confidence_target_summary.csv", index=False)
    rules.to_csv(run_dir / "target_local_confidence_rule_surface.csv", index=False)
    bins.to_csv(run_dir / "target_local_confidence_feature_bins.csv", index=False)
    examples.to_csv(run_dir / "target_local_confidence_examples.csv", index=False)
    (run_dir / "config.json").write_text(
        json.dumps(
            {
                "horizon_rows": args.horizon_rows,
                "targets": args.targets,
                "row_scopes": args.row_scopes,
                "numeric_features": numeric_features,
                "high_features": parse_csv(args.high_features),
                "low_features": parse_csv(args.low_features),
                "max_thresholds_per_feature": args.max_thresholds_per_feature,
                "feature_bins": args.feature_bins,
                "top_n": args.top_n,
            },
            indent=2,
            sort_keys=True,
            default=local_json_default,
        )
        + "\n",
        encoding="utf-8",
    )

    print("Support repair target-local confidence diagnostics:")
    print(f"rows: {len(filtered)}")
    print(targets.to_string(index=False))
    print(rules.head(10).to_string(index=False) if not rules.empty else "no rules")
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--horizon-rows", type=Path, required=True)
    parser.add_argument("--targets", default=DEFAULT_TARGETS)
    parser.add_argument("--row-scopes", default=DEFAULT_ROW_SCOPES)
    parser.add_argument("--numeric-features", default=DEFAULT_NUMERIC_FEATURES)
    parser.add_argument("--high-features", default=DEFAULT_HIGH_FEATURES)
    parser.add_argument("--low-features", default=DEFAULT_LOW_FEATURES)
    parser.add_argument("--max-thresholds-per-feature", type=int, default=6)
    parser.add_argument("--feature-bins", type=int, default=4)
    parser.add_argument("--top-n", type=int, default=12)
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="entry_ev_support_repair_target_local_confidence")
    return parser


def main(argv: list[str] | None = None) -> int:
    run_diagnostics(build_parser().parse_args(argv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
