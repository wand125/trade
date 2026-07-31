#!/usr/bin/env python3
"""Build hard selector scores from forced-exit-loss risk estimates."""

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
from entry_ev_scale_quantile_diagnostics import (  # noqa: E402
    add_scope_quantiles,
    build_score_frame,
    parse_scope_csv,
    quantile_column_name,
)


DEFAULT_RISK_NAME = "forced_exit_loss"
DEFAULT_RISK_SPECS = "exit_risk,ev_exit"
DEFAULT_SCORE_KIND_PREFIX = "forced_exit_selector"
DEFAULT_QUANTILE_SCOPES = "month,side_month,side_regime_session_month"
SIDE_GAP_QUANTILE_MODES = {"post_block", "pre_block"}

RISK_SPEC_LABELS = {
    "exit_risk": "exitrisk",
    "ev_exit": "evexit",
}


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


def parse_float_csv(value: str) -> list[float]:
    return [float(part) for part in parse_csv(value)]


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


def numeric_series(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    values = pd.to_numeric(frame[column], errors="coerce")
    return values.where(np.isfinite(values), default).fillna(default).astype(float)


def text_series(frame: pd.DataFrame, column: str, default: str = "missing") -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index)
    return (
        frame[column]
        .fillna(default)
        .astype(str)
        .str.strip()
        .replace({"": default, "nan": default, "None": default})
    )


def source_mask(source: pd.Series, mode: str) -> pd.Series:
    source = source.astype(str)
    if mode == "bucket":
        return source.eq("bucket")
    if mode == "bucket_or_global":
        return source.isin(["bucket", "global"])
    raise ValueError(f"unknown source mode: {mode}")


def source_mode_label(value: str) -> str:
    return value.replace("_or_", "or").replace("_", "")


def threshold_label(value: float) -> str:
    text = f"{value:.4f}".rstrip("0").rstrip(".")
    return "t" + text.replace("-", "m").replace(".", "p")


def score_kind_name(
    *,
    prefix: str,
    risk_spec: str,
    source_mode: str,
    threshold: float,
) -> str:
    spec_label = RISK_SPEC_LABELS.get(risk_spec, risk_spec.replace("_", ""))
    return f"{prefix}_{spec_label}_{source_mode_label(source_mode)}_{threshold_label(threshold)}"


def risk_columns(*, risk_name: str, risk_spec: str, side: str) -> tuple[str, str]:
    prefix = f"pred_{risk_name}_{risk_spec}_{side}"
    return (
        f"{prefix}_predicted_{risk_name}_risk",
        f"{prefix}_{risk_name}_prediction_source",
    )


def validate_columns(
    frame: pd.DataFrame,
    *,
    risk_name: str,
    risk_specs: list[str],
    long_column: str,
    short_column: str,
    long_rank_column: str,
    short_rank_column: str,
    replacement_guard_conf_gap_buckets: list[str],
) -> None:
    required = {long_column, short_column, long_rank_column, short_rank_column}
    for risk_spec in risk_specs:
        for side in ["long", "short"]:
            required.update(risk_columns(risk_name=risk_name, risk_spec=risk_spec, side=side))
            if replacement_guard_conf_gap_buckets:
                required.add(
                    f"pred_{risk_name}_{risk_spec}_{side}_side_confidence_gap_bucket"
                )
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"predictions missing columns: {', '.join(missing)}")


def side_block_mask(
    frame: pd.DataFrame,
    *,
    risk_name: str,
    risk_spec: str,
    side: str,
    source_mode: str,
    threshold: float,
) -> pd.Series:
    risk_column, source_column = risk_columns(
        risk_name=risk_name,
        risk_spec=risk_spec,
        side=side,
    )
    risk = numeric_series(frame, risk_column, default=np.nan).clip(0.0, 1.0)
    source = text_series(frame, source_column, default="no_prior")
    return source_mask(source, source_mode) & risk.notna() & risk.ge(threshold)


def side_conf_gap_mask(
    frame: pd.DataFrame,
    *,
    risk_name: str,
    risk_spec: str,
    side: str,
    buckets: list[str],
) -> pd.Series:
    if not buckets:
        return pd.Series(False, index=frame.index)
    column = f"pred_{risk_name}_{risk_spec}_{side}_side_confidence_gap_bucket"
    return text_series(frame, column).isin(set(buckets))


def overwrite_side_gap_quantiles_from_pre_block_scores(
    output: pd.DataFrame,
    *,
    family: str,
    score_kind: str,
    long_base: pd.Series,
    short_base: pd.Series,
    long_rank_column: str,
    short_rank_column: str,
    quantile_scopes: list[str],
) -> pd.DataFrame:
    result = output.copy()
    long_temp = f"__{score_kind}_preblock_long_score"
    short_temp = f"__{score_kind}_preblock_short_score"
    quantile_input = result.copy()
    quantile_input[long_temp] = long_base.to_numpy()
    quantile_input[short_temp] = short_base.to_numpy()
    score_frame = build_score_frame(
        quantile_input,
        family=family,
        score_kind=score_kind,
        long_score_column=long_temp,
        short_score_column=short_temp,
        long_rank_column=long_rank_column,
        short_rank_column=short_rank_column,
    )
    for scope_name in quantile_scopes:
        scoped = add_scope_quantiles(score_frame, scope_name=scope_name)
        result[
            quantile_column_name(
                score_kind=score_kind,
                source_column="side_gap",
                scope_name=scope_name,
            )
        ] = scoped["side_gap_pct"].to_numpy()
    return result


def add_selector_scores(
    predictions: pd.DataFrame,
    *,
    family: str,
    risk_name: str,
    risk_specs: list[str],
    score_kind_prefix: str,
    source_modes: list[str],
    risk_thresholds: list[float],
    long_column: str,
    short_column: str,
    long_rank_column: str,
    short_rank_column: str,
    blocked_score: float,
    quantile_scopes: list[str],
    side_gap_quantile_mode: str,
    replacement_guard_conf_gap_buckets: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    if side_gap_quantile_mode not in SIDE_GAP_QUANTILE_MODES:
        raise ValueError(f"unknown side_gap_quantile_mode: {side_gap_quantile_mode}")
    output = predictions.copy()
    long_base = numeric_series(output, long_column, default=np.nan)
    short_base = numeric_series(output, short_column, default=np.nan)
    base_side = pd.Series(np.where(long_base >= short_base, "long", "short"), index=output.index)
    rows: list[dict[str, Any]] = []

    for risk_spec in risk_specs:
        for source_mode in source_modes:
            for threshold in risk_thresholds:
                score_kind = score_kind_name(
                    prefix=score_kind_prefix,
                    risk_spec=risk_spec,
                    source_mode=source_mode,
                    threshold=threshold,
                )
                long_blocked = side_block_mask(
                    output,
                    risk_name=risk_name,
                    risk_spec=risk_spec,
                    side="long",
                    source_mode=source_mode,
                    threshold=threshold,
                )
                short_blocked = side_block_mask(
                    output,
                    risk_name=risk_name,
                    risk_spec=risk_spec,
                    side="short",
                    source_mode=source_mode,
                    threshold=threshold,
                )
                long_risk_blocked = long_blocked.copy()
                short_risk_blocked = short_blocked.copy()
                long_replacement_guard_blocked = (
                    side_conf_gap_mask(
                        output,
                        risk_name=risk_name,
                        risk_spec=risk_spec,
                        side="long",
                        buckets=replacement_guard_conf_gap_buckets,
                    )
                    & short_risk_blocked
                    & ~long_risk_blocked
                )
                short_replacement_guard_blocked = (
                    side_conf_gap_mask(
                        output,
                        risk_name=risk_name,
                        risk_spec=risk_spec,
                        side="short",
                        buckets=replacement_guard_conf_gap_buckets,
                    )
                    & long_risk_blocked
                    & ~short_risk_blocked
                )
                long_blocked = long_risk_blocked | long_replacement_guard_blocked
                short_blocked = short_risk_blocked | short_replacement_guard_blocked
                long_output_column = f"pred_{score_kind}_long_best_adjusted_pnl"
                short_output_column = f"pred_{score_kind}_short_best_adjusted_pnl"
                output[long_output_column] = long_base.where(~long_blocked, blocked_score)
                output[short_output_column] = short_base.where(~short_blocked, blocked_score)
                output[f"pred_{score_kind}_long_forced_exit_blocked"] = long_blocked
                output[f"pred_{score_kind}_short_forced_exit_blocked"] = short_blocked
                output[f"pred_{score_kind}_long_risk_blocked"] = long_risk_blocked
                output[f"pred_{score_kind}_short_risk_blocked"] = short_risk_blocked
                output[f"pred_{score_kind}_long_replacement_guard_blocked"] = (
                    long_replacement_guard_blocked
                )
                output[f"pred_{score_kind}_short_replacement_guard_blocked"] = (
                    short_replacement_guard_blocked
                )
                output = add_executable_quantile_columns(
                    output,
                    family=family,
                    score_kind=score_kind,
                    long_output_column=long_output_column,
                    short_output_column=short_output_column,
                    long_rank_column=long_rank_column,
                    short_rank_column=short_rank_column,
                    quantile_scopes=quantile_scopes,
                )
                if side_gap_quantile_mode == "pre_block":
                    output = overwrite_side_gap_quantiles_from_pre_block_scores(
                        output,
                        family=family,
                        score_kind=score_kind,
                        long_base=long_base,
                        short_base=short_base,
                        long_rank_column=long_rank_column,
                        short_rank_column=short_rank_column,
                        quantile_scopes=quantile_scopes,
                    )
                selector_side = pd.Series(
                    np.where(
                        output[long_output_column].astype(float)
                        >= output[short_output_column].astype(float),
                        "long",
                        "short",
                    ),
                    index=output.index,
                )
                base_selected_blocked = (
                    base_side.eq("long") & long_blocked
                ) | (base_side.eq("short") & short_blocked)
                both_blocked = long_blocked & short_blocked
                one_side_blocked = long_blocked ^ short_blocked
                rows.append(
                    {
                        "family": family,
                        "score_kind": score_kind,
                        "risk_spec": risk_spec,
                        "source_mode": source_mode,
                        "risk_threshold": threshold,
                        "side_gap_quantile_mode": side_gap_quantile_mode,
                        "replacement_guard_conf_gap_buckets": ",".join(
                            replacement_guard_conf_gap_buckets
                        ),
                        "long_risk_block_share": float(long_risk_blocked.mean()),
                        "short_risk_block_share": float(short_risk_blocked.mean()),
                        "long_replacement_guard_block_share": float(
                            long_replacement_guard_blocked.mean()
                        ),
                        "short_replacement_guard_block_share": float(
                            short_replacement_guard_blocked.mean()
                        ),
                        "any_replacement_guard_block_share": float(
                            (
                                long_replacement_guard_blocked
                                | short_replacement_guard_blocked
                            ).mean()
                        ),
                        "long_block_share": float(long_blocked.mean()),
                        "short_block_share": float(short_blocked.mean()),
                        "any_side_block_share": float((long_blocked | short_blocked).mean()),
                        "one_side_block_share": float(one_side_blocked.mean()),
                        "both_side_block_share": float(both_blocked.mean()),
                        "base_selected_block_share": float(base_selected_blocked.mean()),
                        "selected_side_changed_share": float(selector_side.ne(base_side).mean()),
                        "long_blocked_base_score_mean": float(long_base[long_blocked].mean())
                        if bool(long_blocked.any())
                        else float("nan"),
                        "short_blocked_base_score_mean": float(short_base[short_blocked].mean())
                        if bool(short_blocked.any())
                        else float("nan"),
                    }
                )
    return output, pd.DataFrame(rows)


def build_selector_inputs(args: argparse.Namespace) -> Path:
    family_predictions = parse_family_predictions(args.family_predictions)
    risk_specs = parse_csv(args.risk_specs)
    source_modes = parse_csv(args.source_modes)
    risk_thresholds = parse_float_csv(args.risk_thresholds)
    quantile_scopes = parse_scope_csv(args.quantile_scopes)
    side_gap_quantile_mode = getattr(args, "side_gap_quantile_mode", "post_block")
    if side_gap_quantile_mode not in SIDE_GAP_QUANTILE_MODES:
        raise ValueError(f"unknown side_gap_quantile_mode: {side_gap_quantile_mode}")
    replacement_guard_conf_gap_buckets = parse_csv(args.replacement_guard_conf_gap_buckets)
    if not risk_specs:
        raise ValueError("--risk-specs must not be empty")
    if not source_modes:
        raise ValueError("--source-modes must not be empty")
    if not risk_thresholds:
        raise ValueError("--risk-thresholds must not be empty")

    run_dir = make_run_dir(args.output_dir, args.label)
    enriched_dir = run_dir / "enriched_predictions"
    enriched_dir.mkdir(parents=True, exist_ok=True)

    summary_frames: list[pd.DataFrame] = []
    for family, prediction_path in family_predictions.items():
        predictions = pd.read_parquet(prediction_path)
        validate_columns(
            predictions,
            risk_name=args.risk_name,
            risk_specs=risk_specs,
            long_column=args.long_column,
            short_column=args.short_column,
            long_rank_column=args.long_rank_column,
            short_rank_column=args.short_rank_column,
            replacement_guard_conf_gap_buckets=replacement_guard_conf_gap_buckets,
        )
        enriched, summary = add_selector_scores(
            predictions,
            family=family,
            risk_name=args.risk_name,
            risk_specs=risk_specs,
            score_kind_prefix=args.score_kind_prefix,
            source_modes=source_modes,
            risk_thresholds=risk_thresholds,
            long_column=args.long_column,
            short_column=args.short_column,
            long_rank_column=args.long_rank_column,
            short_rank_column=args.short_rank_column,
            blocked_score=args.blocked_score,
            quantile_scopes=quantile_scopes,
            side_gap_quantile_mode=side_gap_quantile_mode,
            replacement_guard_conf_gap_buckets=replacement_guard_conf_gap_buckets,
        )
        output_path = enriched_dir / f"{family}_predictions_forced_exit_selector.parquet"
        enriched.to_parquet(output_path, index=False)
        summary_frames.append(summary)

    summary = pd.concat(summary_frames, ignore_index=True)
    summary.to_csv(run_dir / "selector_block_summary.csv", index=False)
    config = {
        "family_predictions": family_predictions,
        "risk_name": args.risk_name,
        "risk_specs": risk_specs,
        "score_kind_prefix": args.score_kind_prefix,
        "source_modes": source_modes,
        "risk_thresholds": risk_thresholds,
        "long_column": args.long_column,
        "short_column": args.short_column,
        "long_rank_column": args.long_rank_column,
        "short_rank_column": args.short_rank_column,
        "blocked_score": args.blocked_score,
        "quantile_scopes": quantile_scopes,
        "side_gap_quantile_mode": side_gap_quantile_mode,
        "replacement_guard_conf_gap_buckets": replacement_guard_conf_gap_buckets,
    }
    (run_dir / "config.json").write_text(
        json.dumps(config, indent=2, default=local_json_default),
        encoding="utf-8",
    )
    print("Selector block summary:")
    print(summary.to_string(index=False))
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--family-predictions", action="append", required=True)
    parser.add_argument("--risk-name", default=DEFAULT_RISK_NAME)
    parser.add_argument("--risk-specs", default=DEFAULT_RISK_SPECS)
    parser.add_argument("--score-kind-prefix", default=DEFAULT_SCORE_KIND_PREFIX)
    parser.add_argument("--source-modes", default="bucket")
    parser.add_argument("--risk-thresholds", default="0.05,0.10,0.15,0.20,0.30")
    parser.add_argument(
        "--long-column",
        default="pred_direction_inversion_bucket_s0p1_long_best_adjusted_pnl",
    )
    parser.add_argument(
        "--short-column",
        default="pred_direction_inversion_bucket_s0p1_short_best_adjusted_pnl",
    )
    parser.add_argument("--long-rank-column", default="pred_long_entry_local_rank")
    parser.add_argument("--short-rank-column", default="pred_short_entry_local_rank")
    parser.add_argument("--blocked-score", type=float, default=-1000000000.0)
    parser.add_argument("--quantile-scopes", default=DEFAULT_QUANTILE_SCOPES)
    parser.add_argument(
        "--side-gap-quantile-mode",
        choices=sorted(SIDE_GAP_QUANTILE_MODES),
        default="post_block",
        help=(
            "Use post-block selector scores or pre-block base scores for "
            "side-gap quantile columns."
        ),
    )
    parser.add_argument(
        "--replacement-guard-conf-gap-buckets",
        default="",
        help=(
            "comma-separated side_confidence_gap_bucket values that block an "
            "otherwise unblocked side when the opposite side is risk-blocked"
        ),
    )
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="entry_ev_forced_exit_selector_inputs")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    build_selector_inputs(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
