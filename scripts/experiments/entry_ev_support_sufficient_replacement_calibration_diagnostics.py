#!/usr/bin/env python3
"""Diagnose calibrated replacement scoring for support-sufficient negative months."""

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

from entry_ev_candidate_generation_gap_audit import parse_targets  # noqa: E402
from entry_ev_support_sufficient_negative_month_repair_diagnostics import (  # noqa: E402
    DEFAULT_CONFIG,
    DEFAULT_TARGETS,
    HORIZONS,
    add_candidate_gate_columns,
    add_current_trade_repair_columns,
    add_side_pred_fixed_columns,
    candidate_pool_for_loss,
    load_extended_side_rows,
)
from entry_ev_thin_month_opposite_candidate_diagnostics import (  # noqa: E402
    bool_series,
    build_side_rows,
    local_json_default,
    month_series,
    numeric_series,
    parquet_columns,
    parse_side_penalty_rules,
    read_current_trades,
)
from entry_ev_upstream_universe_coverage_diagnostics import (  # noqa: E402
    filter_repair_targets,
    resolve_path,
    role_to_family,
    select_repair_row,
)


DEFAULT_CONTEXT_SPECS = (
    "side,candidate_pred_fixed_best_horizon_minutes,combined_regime,session_regime;"
    "side,combined_regime,session_regime;"
    "side,candidate_pred_fixed_best_horizon_minutes,session_regime;"
    "side,candidate_pred_fixed_best_horizon_minutes;"
    "side,session_regime;"
    "side"
)
SCORE_COLUMNS = {
    "side_score": "side_score",
    "raw_pred_fixed": "candidate_pred_fixed_best_pred_pnl",
    "bias_corrected": "calibrated_bias_corrected_pred_pnl",
    "downside_bias_corrected": "calibrated_downside_bias_corrected_pred_pnl",
    "conservative": "calibrated_conservative_pred_pnl",
    "prior_actual_mean": "calibrated_prior_actual_mean",
}


def parse_csv(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def parse_context_specs(value: str) -> list[list[str]]:
    specs: list[list[str]] = []
    for raw_spec in value.split(";"):
        columns = parse_csv(raw_spec)
        if columns:
            specs.append(columns)
    if not specs:
        raise argparse.ArgumentTypeError("at least one context spec is required")
    return specs


def context_spec_name(columns: list[str]) -> str:
    return ",".join(columns) if columns else "all"


def text_key(value: Any) -> str:
    if pd.isna(value):
        return "missing"
    text = str(value).strip()
    return text if text else "missing"


def frame_context_key(frame: pd.DataFrame, columns: list[str]) -> pd.Series:
    if not columns:
        return pd.Series("all", index=frame.index, dtype="string")
    key = pd.Series("", index=frame.index, dtype="string")
    for column in columns:
        part = frame[column].map(text_key).astype("string")
        key = part if key.eq("").all() else key + "|" + part
    return key


def row_context_key(row: pd.Series, columns: list[str]) -> str:
    if not columns:
        return "all"
    return "|".join(text_key(row.get(column, "missing")) for column in columns)


def prior_metric_row(frame: pd.DataFrame) -> dict[str, Any]:
    count = int(len(frame))
    pred = numeric_series(frame, "candidate_pred_fixed_best_pred_pnl")
    actual = numeric_series(frame, "candidate_actual_at_pred_fixed_best_horizon")
    valid = pred.notna() & actual.notna() & np.isfinite(pred) & np.isfinite(actual)
    pred = pred[valid]
    actual = actual[valid]
    error = actual - pred
    month_count = int(frame.loc[valid, "month"].astype(str).nunique()) if count else 0
    return {
        "prior_count": int(valid.sum()),
        "prior_month_count": month_count,
        "prior_pred_mean": float(pred.mean()) if len(pred) else np.nan,
        "prior_actual_mean": float(actual.mean()) if len(actual) else np.nan,
        "prior_bias_mean": float(error.mean()) if len(error) else np.nan,
        "prior_mae": float(error.abs().mean()) if len(error) else np.nan,
        "prior_rmse": float(np.sqrt((error**2).mean())) if len(error) else np.nan,
        "prior_win_rate": float(actual.gt(0.0).mean()) if len(actual) else np.nan,
        "prior_actual_sum": float(actual.sum()) if len(actual) else 0.0,
        "prior_overestimate_rate": float(error.lt(0.0).mean()) if len(error) else np.nan,
    }


def build_prior_metric_maps(
    prior_rows: pd.DataFrame,
    context_specs: list[list[str]],
) -> dict[str, dict[str, dict[str, Any]]]:
    maps: dict[str, dict[str, dict[str, Any]]] = {}
    for columns in context_specs:
        available = [column for column in columns if column in prior_rows.columns]
        spec = context_spec_name(available)
        if not available:
            grouped = [("all", prior_rows)]
        else:
            prior = prior_rows.copy()
            prior["_context_key"] = frame_context_key(prior, available)
            grouped = list(prior.groupby("_context_key", dropna=False))
        maps[spec] = {str(key): prior_metric_row(group) for key, group in grouped}
    return maps


def best_prior_for_row(
    row: pd.Series,
    *,
    metric_maps: dict[str, dict[str, dict[str, Any]]],
    context_specs: list[list[str]],
    min_prior_count: int,
) -> dict[str, Any]:
    fallback: dict[str, Any] | None = None
    for columns in context_specs:
        available = [column for column in columns if column in row.index]
        spec = context_spec_name(available)
        key = row_context_key(row, available)
        metrics = metric_maps.get(spec, {}).get(key)
        if metrics is None:
            continue
        candidate = {"calibration_context_spec": spec, "calibration_context_key": key, **metrics}
        if fallback is None:
            fallback = candidate
        if int(metrics.get("prior_count", 0)) >= int(min_prior_count):
            return candidate
    if fallback is not None:
        fallback = dict(fallback)
        fallback["calibration_context_insufficient"] = True
        return fallback
    return {
        "calibration_context_spec": "none",
        "calibration_context_key": "",
        "calibration_context_insufficient": True,
        **prior_metric_row(pd.DataFrame()),
    }


def add_prior_calibration(
    candidates: pd.DataFrame,
    *,
    prior_rows: pd.DataFrame,
    context_specs: list[list[str]],
    min_prior_count: int,
) -> pd.DataFrame:
    if candidates.empty:
        return candidates.copy()
    metric_maps = build_prior_metric_maps(prior_rows, context_specs)
    metric_rows = [
        best_prior_for_row(
            row,
            metric_maps=metric_maps,
            context_specs=context_specs,
            min_prior_count=min_prior_count,
        )
        for _, row in candidates.iterrows()
    ]
    metrics = pd.DataFrame(metric_rows, index=candidates.index)
    output = pd.concat([candidates.copy(), metrics], axis=1)
    raw_pred = numeric_series(output, "candidate_pred_fixed_best_pred_pnl")
    bias = numeric_series(output, "prior_bias_mean")
    mae = numeric_series(output, "prior_mae", default=0.0)
    actual_mean = numeric_series(output, "prior_actual_mean")
    output["calibrated_bias_corrected_pred_pnl"] = raw_pred + bias
    output["calibrated_downside_bias_corrected_pred_pnl"] = raw_pred + bias.clip(upper=0.0)
    output["calibrated_conservative_pred_pnl"] = (
        output["calibrated_downside_bias_corrected_pred_pnl"] - mae
    )
    output["calibrated_prior_actual_mean"] = actual_mean
    output["calibration_context_insufficient"] = output.get(
        "calibration_context_insufficient",
        pd.Series(False, index=output.index),
    ).fillna(False)
    return output


def add_candidate_horizon_columns_fast(rows: pd.DataFrame) -> pd.DataFrame:
    output = rows.copy()
    pred_columns = [f"side_pred_fixed_{horizon}m_adjusted_pnl" for horizon in HORIZONS]
    actual_columns = [f"side_fixed_{horizon}m_adjusted_pnl" for horizon in HORIZONS]
    pred = output.reindex(columns=pred_columns).apply(pd.to_numeric, errors="coerce")
    actual = output.reindex(columns=actual_columns).apply(pd.to_numeric, errors="coerce")
    pred_values = pred.to_numpy(dtype=float)
    actual_values = actual.to_numpy(dtype=float)
    pred_filled = np.where(np.isfinite(pred_values), pred_values, -np.inf)
    actual_filled = np.where(np.isfinite(actual_values), actual_values, -np.inf)
    pred_index = np.argmax(pred_filled, axis=1) if len(output) else np.array([], dtype=int)
    actual_index = np.argmax(actual_filled, axis=1) if len(output) else np.array([], dtype=int)
    horizons = np.array(HORIZONS, dtype=int)
    row_index = np.arange(len(output))
    pred_all_missing = np.isneginf(pred_filled).all(axis=1) if len(output) else np.array([])
    actual_all_missing = np.isneginf(actual_filled).all(axis=1) if len(output) else np.array([])
    output["candidate_pred_fixed_best_horizon_minutes"] = np.where(
        pred_all_missing,
        int(HORIZONS[0]),
        horizons[pred_index],
    )
    output["candidate_pred_fixed_best_pred_pnl"] = np.where(
        pred_all_missing,
        np.nan,
        pred_values[row_index, pred_index],
    )
    output["candidate_actual_at_pred_fixed_best_horizon"] = np.where(
        pred_all_missing,
        np.nan,
        actual_values[row_index, pred_index],
    )
    output["candidate_fixed_best_horizon_minutes_oracle"] = np.where(
        actual_all_missing,
        int(HORIZONS[0]),
        horizons[actual_index],
    )
    output["candidate_fixed_best_actual_pnl_oracle"] = np.where(
        actual_all_missing,
        np.nan,
        actual_values[row_index, actual_index],
    )
    return output


def load_family_side_rows(
    *,
    prediction_path: Path,
    family: str,
    config: dict[str, Any],
) -> pd.DataFrame:
    side_penalty_rules = parse_side_penalty_rules(config.get("side_ev_penalty_rules", ""))
    needed_columns = [
        "decision_timestamp",
        "entry_timestamp",
        "dataset_month",
        "month",
        "combined_regime",
        "session_regime",
        config["long_column"],
        config["short_column"],
        config.get("long_holding_column", "pred_mlp_long_exit_event_minutes"),
        config.get("short_holding_column", "pred_mlp_short_exit_event_minutes"),
        "pred_long_entry_local_rank",
        "pred_short_entry_local_rank",
        "long_best_adjusted_pnl",
        "short_best_adjusted_pnl",
        "long_best_holding_minutes",
        "short_best_holding_minutes",
        "long_fixed_60m_adjusted_pnl",
        "short_fixed_60m_adjusted_pnl",
        "long_fixed_240m_adjusted_pnl",
        "short_fixed_240m_adjusted_pnl",
        "long_fixed_720m_adjusted_pnl",
        "short_fixed_720m_adjusted_pnl",
        "pred_long_fixed_60m_adjusted_pnl",
        "pred_short_fixed_60m_adjusted_pnl",
        "pred_long_fixed_240m_adjusted_pnl",
        "pred_short_fixed_240m_adjusted_pnl",
        "pred_long_fixed_720m_adjusted_pnl",
        "pred_short_fixed_720m_adjusted_pnl",
        *[rule[1] for rule in side_penalty_rules],
    ]
    columns = parquet_columns(prediction_path)
    read_columns = [column for column in dict.fromkeys(needed_columns) if column in columns]
    predictions = pd.read_parquet(prediction_path, columns=read_columns)
    predictions["month"] = month_series(predictions)
    side_rows = build_side_rows(
        predictions,
        family=family,
        long_column=config["long_column"],
        short_column=config["short_column"],
        long_holding_column=config.get("long_holding_column", "pred_mlp_long_exit_event_minutes"),
        short_holding_column=config.get("short_holding_column", "pred_mlp_short_exit_event_minutes"),
        min_valid_predicted_hold_minutes=float(
            config.get("min_valid_predicted_hold_minutes", 30.0)
        ),
        max_predicted_hold_minutes=float(config.get("max_predicted_hold_minutes", 720.0)),
        side_penalty_rules=side_penalty_rules,
    )
    side_rows = add_side_pred_fixed_columns(side_rows, predictions)
    side_rows = add_candidate_gate_columns(side_rows, config=config)
    side_rows = add_candidate_horizon_columns_fast(side_rows)
    side_rows["entry_key"] = (
        pd.to_datetime(side_rows["decision_timestamp"], utc=True, errors="coerce").dt.strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        + "|"
        + side_rows["side"].astype(str)
    )
    return side_rows


def choose_top_candidate(
    pool: pd.DataFrame,
    *,
    score_mode: str,
) -> pd.Series | None:
    score_column = SCORE_COLUMNS[score_mode]
    if pool.empty or score_column not in pool.columns:
        return None
    ranked = pool.copy()
    ranked["_selection_score"] = numeric_series(ranked, score_column, default=-np.inf)
    ranked = ranked[np.isfinite(ranked["_selection_score"])]
    if ranked.empty:
        return None
    return ranked.sort_values(
        ["_selection_score", "side_score", "score_pct", "side_margin_pct", "entry_rank_pct"],
        ascending=[False, False, False, False, False],
    ).iloc[0]


def choice_row(
    *,
    month_pnl: float,
    loss_trade: pd.Series,
    score_mode: str,
    candidate: pd.Series | None,
) -> dict[str, Any]:
    base = {
        "score_mode": score_mode,
        "loss_trade_id": str(loss_trade["trade_id"]),
        "loss_trade_direction": str(loss_trade["direction"]),
        "loss_trade_entry_decision_timestamp": str(loss_trade["entry_decision_timestamp"]),
        "loss_trade_adjusted_pnl": float(loss_trade["adjusted_pnl"]),
    }
    if candidate is None:
        return {
            **base,
            "chosen": False,
            "candidate_side": "",
            "candidate_timestamp": "",
            "candidate_stage": "",
            "selection_score": np.nan,
            "candidate_pred_horizon": 0,
            "candidate_pred_pnl": np.nan,
            "candidate_actual_at_pred_horizon": np.nan,
            "candidate_oracle_fixed_best_actual": np.nan,
            "month_pnl_at_pred_horizon": np.nan,
            "month_pnl_at_oracle_horizon": np.nan,
        }
    score_column = SCORE_COLUMNS[score_mode]
    actual_at_pred = float(candidate["candidate_actual_at_pred_fixed_best_horizon"])
    oracle_actual = float(candidate["candidate_fixed_best_actual_pnl_oracle"])
    return {
        **base,
        "chosen": True,
        "candidate_side": str(candidate["side"]),
        "candidate_timestamp": str(candidate["decision_timestamp"]),
        "candidate_stage": str(candidate["candidate_stage"]),
        "selection_score": float(candidate.get(score_column, np.nan)),
        "side_score": float(candidate.get("side_score", np.nan)),
        "candidate_pred_horizon": int(candidate["candidate_pred_fixed_best_horizon_minutes"]),
        "candidate_pred_pnl": float(candidate["candidate_pred_fixed_best_pred_pnl"]),
        "candidate_actual_at_pred_horizon": actual_at_pred,
        "candidate_oracle_fixed_best_actual": oracle_actual,
        "calibration_context_spec": str(candidate.get("calibration_context_spec", "")),
        "calibration_context_key": str(candidate.get("calibration_context_key", "")),
        "prior_count": int(candidate.get("prior_count", 0)),
        "prior_bias_mean": float(candidate.get("prior_bias_mean", np.nan)),
        "prior_mae": float(candidate.get("prior_mae", np.nan)),
        "prior_actual_mean": float(candidate.get("prior_actual_mean", np.nan)),
        "month_pnl_at_pred_horizon": float(
            month_pnl - float(loss_trade["adjusted_pnl"]) + actual_at_pred
        ),
        "month_pnl_at_oracle_horizon": float(
            month_pnl - float(loss_trade["adjusted_pnl"]) + oracle_actual
        ),
    }


def summarize_choices(choices: pd.DataFrame) -> pd.DataFrame:
    if choices.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for score_mode, group in choices.groupby("score_mode", dropna=False):
        chosen = group[bool_series(group, "chosen")]
        rows.append(
            {
                "score_mode": score_mode,
                "choice_count": int(len(chosen)),
                "mean_month_pnl_at_pred_horizon": float(
                    numeric_series(chosen, "month_pnl_at_pred_horizon").mean()
                )
                if len(chosen)
                else np.nan,
                "best_month_pnl_at_pred_horizon": float(
                    numeric_series(chosen, "month_pnl_at_pred_horizon").max()
                )
                if len(chosen)
                else np.nan,
                "worst_month_pnl_at_pred_horizon": float(
                    numeric_series(chosen, "month_pnl_at_pred_horizon").min()
                )
                if len(chosen)
                else np.nan,
                "mean_actual_at_pred_horizon": float(
                    numeric_series(chosen, "candidate_actual_at_pred_horizon").mean()
                )
                if len(chosen)
                else np.nan,
                "positive_choice_count": int(
                    numeric_series(chosen, "candidate_actual_at_pred_horizon").gt(0.0).sum()
                )
                if len(chosen)
                else 0,
                "onefail_choice_count": int(
                    chosen["candidate_stage"].astype(str).eq("one_failed_strict_stage").sum()
                )
                if len(chosen)
                else 0,
                "strict_choice_count": int(chosen["candidate_stage"].astype(str).eq("strict").sum())
                if len(chosen)
                else 0,
                "relaxed_choice_count": int(
                    chosen["candidate_stage"].astype(str).eq("relaxed").sum()
                )
                if len(chosen)
                else 0,
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["best_month_pnl_at_pred_horizon", "mean_month_pnl_at_pred_horizon"],
        ascending=[False, False],
    )


def run_diagnostics(args: argparse.Namespace) -> Path:
    config_path = resolve_path(args.config)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    repair_targets = filter_repair_targets(
        pd.read_csv(resolve_path(config["repair_targets"])),
        candidate=config["candidate"],
        variant_contains=config.get("variant_contains", ""),
        entry_block_rule=config.get("entry_block_rule", ""),
    )
    current = read_current_trades(
        resolve_path(config["current_trades"]),
        candidate=config["candidate"],
        selector_variant_contains=config.get("selector_variant_contains", ""),
        entry_block_rule=config.get("entry_block_rule", ""),
    )
    family_predictions = {
        str(family): resolve_path(path)
        for family, path in dict(config["family_predictions"]).items()
    }
    context_specs = parse_context_specs(args.context_specs)

    all_candidate_frames: list[pd.DataFrame] = []
    choice_rows: list[dict[str, Any]] = []
    target_rows: list[dict[str, Any]] = []
    prior_cache: dict[str, pd.DataFrame] = {}

    for role, month, _side in parse_targets(args.targets):
        family = role_to_family(role)
        repair_row = select_repair_row(repair_targets, role=role, month=month)
        if repair_row is not None:
            family = str(repair_row.get("family", family))
        current_target = current[
            current["role"].astype(str).eq(role)
            & current["family"].astype(str).eq(family)
            & current["month"].astype(str).eq(month)
        ].copy()
        if current_target.empty:
            continue
        current_target = add_current_trade_repair_columns(current_target)
        prediction_path = family_predictions.get(family)
        if prediction_path is None:
            raise ValueError(f"missing prediction path for family {family}")
        target_side_rows = load_extended_side_rows(
            prediction_path=prediction_path,
            family=family,
            month=month,
            config=config,
        )
        if family not in prior_cache:
            prior_cache[family] = load_family_side_rows(
                prediction_path=prediction_path,
                family=family,
                config=config,
            )
        prior_rows = prior_cache[family][prior_cache[family]["month"].astype(str).lt(month)].copy()
        prior_rows = prior_rows[
            prior_rows["candidate_stage"].astype(str).ne("non_candidate")
        ].copy()
        month_pnl = float(numeric_series(current_target, "adjusted_pnl", default=0.0).sum())
        losses = current_target[bool_series(current_target, "is_loss_trade")].copy()
        target_candidate_count = 0
        for _, loss_trade in losses.iterrows():
            pool = candidate_pool_for_loss(
                side_rows=target_side_rows,
                current_trades=current_target,
                loss_trade=loss_trade,
                include_non_candidate_top_score=args.include_non_candidate_top_score,
            )
            pool = add_prior_calibration(
                pool,
                prior_rows=prior_rows,
                context_specs=context_specs,
                min_prior_count=args.min_prior_count,
            )
            target_candidate_count += len(pool)
            if not pool.empty:
                all_candidate_frames.append(pool)
            for score_mode in SCORE_COLUMNS:
                choice_rows.append(
                    choice_row(
                        month_pnl=month_pnl,
                        loss_trade=loss_trade,
                        score_mode=score_mode,
                        candidate=choose_top_candidate(pool, score_mode=score_mode),
                    )
                )
        target_rows.append(
            {
                "role": role,
                "family": family,
                "month": month,
                "month_pnl": month_pnl,
                "loss_trade_count": int(len(losses)),
                "candidate_rows": int(target_candidate_count),
                "prior_rows": int(len(prior_rows)),
                "prior_month_count": int(prior_rows["month"].astype(str).nunique())
                if len(prior_rows)
                else 0,
            }
        )

    candidates = (
        pd.concat(all_candidate_frames, ignore_index=True)
        if all_candidate_frames
        else pd.DataFrame()
    )
    choices = pd.DataFrame(choice_rows)
    score_summary = summarize_choices(choices)
    targets = pd.DataFrame(target_rows)

    run_dir = make_run_dir(resolve_path(args.output_root), args.run_label)
    candidates.to_csv(
        run_dir / "support_sufficient_replacement_calibrated_candidates.csv",
        index=False,
    )
    choices.to_csv(
        run_dir / "support_sufficient_replacement_calibration_choices.csv",
        index=False,
    )
    score_summary.to_csv(
        run_dir / "support_sufficient_replacement_calibration_score_summary.csv",
        index=False,
    )
    targets.to_csv(
        run_dir / "support_sufficient_replacement_calibration_targets.csv",
        index=False,
    )
    meta = {
        "config": config_path,
        "targets": parse_targets(args.targets),
        "context_specs": context_specs,
        "min_prior_count": args.min_prior_count,
        "include_non_candidate_top_score": args.include_non_candidate_top_score,
        "score_modes": SCORE_COLUMNS,
        "note": (
            "Calibration uses only prior months. Target-month realized fixed-horizon PnL "
            "is used only for evaluation."
        ),
    }
    (run_dir / "support_sufficient_replacement_calibration_meta.json").write_text(
        json.dumps(meta, indent=2, default=local_json_default) + "\n",
        encoding="utf-8",
    )

    print("Support-sufficient replacement calibration score summary:")
    print(score_summary.to_string(index=False))
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--targets", default=DEFAULT_TARGETS)
    parser.add_argument("--context-specs", default=DEFAULT_CONTEXT_SPECS)
    parser.add_argument("--min-prior-count", type=int, default=20)
    parser.add_argument("--output-root", type=Path, default=ROOT / "data/reports/backtests")
    parser.add_argument(
        "--run-label",
        default="entry_ev_support_sufficient_replacement_calibration_diagnostics",
    )
    parser.add_argument(
        "--include-non-candidate-top-score",
        action="store_true",
        help="Include holding-ok rows even if they fail strict/relaxed/one-fail gates.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    run_diagnostics(build_parser().parse_args(argv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
