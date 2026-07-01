#!/usr/bin/env python3
"""Diagnose harmful only-candidate replacements in entry-EV policy deltas."""

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


KEY_COLUMNS = ["family", "month", "candidate", "direction", "entry_decision_timestamp"]


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


def parse_named_paths(values: list[str]) -> dict[str, Path]:
    paths: dict[str, Path] = {}
    for value in values:
        if "=" in value:
            name, path_text = value.split("=", 1)
            name = name.strip()
            path = Path(path_text.strip())
        else:
            path = Path(value)
            name = path.stem
        if not name:
            raise argparse.ArgumentTypeError("path label must not be empty")
        paths[name] = path
    if not paths:
        raise argparse.ArgumentTypeError("at least one path is required")
    return paths


def resolve_file(path: Path, filename: str) -> Path:
    if path.is_dir():
        return path / filename
    return path


def normalize_keys(frame: pd.DataFrame) -> pd.DataFrame:
    output = frame.copy()
    missing = [column for column in KEY_COLUMNS if column not in output.columns]
    if missing:
        raise ValueError("frame missing key columns: " + ", ".join(missing))
    output["entry_decision_timestamp"] = pd.to_datetime(
        output["entry_decision_timestamp"],
        utc=True,
    )
    for column in ["family", "month", "candidate", "direction"]:
        output[column] = output[column].astype(str)
    output["month"] = output["month"].str.slice(0, 7)
    output["direction"] = output["direction"].str.lower()
    return output


def read_delta_runs(paths: dict[str, Path]) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for name, path in paths.items():
        file_path = resolve_file(path, "trade_delta_rows.csv")
        frame = pd.read_csv(file_path)
        frame.insert(0, "delta_run_name", name)
        frames.append(frame)
    if not frames:
        return pd.DataFrame()
    return normalize_keys(pd.concat(frames, ignore_index=True))


def read_enriched_trades(paths: dict[str, Path]) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for name, path in paths.items():
        file_path = resolve_file(path, "residual_enriched_trades.csv")
        frame = pd.read_csv(file_path)
        frame.insert(0, "enriched_run_name", name)
        frames.append(frame)
    if not frames:
        return pd.DataFrame()
    output = normalize_keys(pd.concat(frames, ignore_index=True))
    duplicated = output.duplicated(KEY_COLUMNS, keep=False)
    if duplicated.any():
        duplicate_keys = output.loc[duplicated, KEY_COLUMNS].drop_duplicates().head(5)
        raise ValueError(
            "enriched trades have duplicate keys: "
            + duplicate_keys.to_dict(orient="records").__repr__()
        )
    return output


def numeric_series(frame: pd.DataFrame, column: str, default: float = np.nan) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    values = pd.to_numeric(frame[column], errors="coerce")
    return values.where(np.isfinite(values), default).astype(float)


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


def selected_numeric(
    frame: pd.DataFrame,
    *,
    long_column: str,
    short_column: str,
    default: float = np.nan,
) -> pd.Series:
    direction = frame["direction"].astype(str).str.lower()
    long_values = numeric_series(frame, long_column, default=default)
    short_values = numeric_series(frame, short_column, default=default)
    return pd.Series(np.where(direction.eq("long"), long_values, short_values), index=frame.index)


def selected_text(
    frame: pd.DataFrame,
    *,
    long_column: str,
    short_column: str,
    default: str = "missing",
) -> pd.Series:
    direction = frame["direction"].astype(str).str.lower()
    long_values = text_series(frame, long_column, default=default)
    short_values = text_series(frame, short_column, default=default)
    return pd.Series(np.where(direction.eq("long"), long_values, short_values), index=frame.index)


def add_selected_replacement_features(
    frame: pd.DataFrame,
    *,
    exit_regret_prefix: str,
    selector_prefix: str,
    side_prior_prefix: str,
) -> pd.DataFrame:
    output = frame.copy()
    output["selected_exit_regret_risk"] = selected_numeric(
        output,
        long_column=f"{exit_regret_prefix}_long_predicted_exit_regret_risk",
        short_column=f"{exit_regret_prefix}_short_predicted_exit_regret_risk",
    )
    output["selected_exit_regret_support"] = selected_numeric(
        output,
        long_column=f"{exit_regret_prefix}_long_exit_regret_prediction_support",
        short_column=f"{exit_regret_prefix}_short_exit_regret_prediction_support",
        default=0.0,
    )
    output["selected_exit_regret_source"] = selected_text(
        output,
        long_column=f"{exit_regret_prefix}_long_exit_regret_prediction_source",
        short_column=f"{exit_regret_prefix}_short_exit_regret_prediction_source",
    )
    output["selected_conf_gap_bucket"] = selected_text(
        output,
        long_column=f"{exit_regret_prefix}_long_side_confidence_gap_bucket",
        short_column=f"{exit_regret_prefix}_short_side_confidence_gap_bucket",
    )
    output["selected_loss_first_bucket"] = selected_text(
        output,
        long_column=f"{exit_regret_prefix}_long_loss_first_prob_bucket",
        short_column=f"{exit_regret_prefix}_short_loss_first_prob_bucket",
    )
    output["selected_time_exit_bucket"] = selected_text(
        output,
        long_column=f"{exit_regret_prefix}_long_time_exit_prob_bucket",
        short_column=f"{exit_regret_prefix}_short_time_exit_prob_bucket",
    )
    output["selected_selector_blocked"] = selected_numeric(
        output,
        long_column=f"{selector_prefix}_long_forced_exit_blocked",
        short_column=f"{selector_prefix}_short_forced_exit_blocked",
        default=0.0,
    ).fillna(0.0).ne(0.0)
    output["selected_selector_score"] = selected_numeric(
        output,
        long_column=f"{selector_prefix}_long_best_adjusted_pnl",
        short_column=f"{selector_prefix}_short_best_adjusted_pnl",
    )
    output["selected_side_prior_risk"] = selected_numeric(
        output,
        long_column=f"{side_prior_prefix}_long_predicted_ev_overestimate_risk",
        short_column=f"{side_prior_prefix}_short_predicted_ev_overestimate_risk",
    )
    output["selected_side_prior_source"] = selected_text(
        output,
        long_column=f"{side_prior_prefix}_long_ev_overestimate_prediction_source",
        short_column=f"{side_prior_prefix}_short_ev_overestimate_prediction_source",
    )
    output["selected_profit_barrier_hit"] = selected_numeric(
        output,
        long_column="pred_long_profit_barrier_hit",
        short_column="pred_short_profit_barrier_hit",
        default=0.0,
    )
    output["selected_fixed_720m_adjusted_pnl"] = selected_numeric(
        output,
        long_column="pred_long_fixed_720m_adjusted_pnl",
        short_column="pred_short_fixed_720m_adjusted_pnl",
    )
    for column in [
        f"{selector_prefix}_selected_score_pct_side_regime_session_month",
        f"{selector_prefix}_side_gap_pct_side_regime_session_month",
        f"{selector_prefix}_selected_entry_rank_pct_side_regime_session_month",
    ]:
        if column in output.columns:
            output[column.replace(f"{selector_prefix}_", "selected_")] = numeric_series(
                output,
                column,
            )
    return output


def add_replacement_targets(frame: pd.DataFrame) -> pd.DataFrame:
    output = frame.copy()
    output["candidate_pnl"] = numeric_series(output, "candidate_adjusted_pnl", default=0.0)
    output["candidate_blocked_base_pnl"] = numeric_series(
        output,
        "candidate_blocked_base_adjusted_pnl",
        default=0.0,
    )
    output["candidate_blocked_positive_pnl"] = numeric_series(
        output,
        "candidate_blocked_base_positive_pnl",
        default=0.0,
    )
    output["candidate_blocked_negative_pnl"] = numeric_series(
        output,
        "candidate_blocked_base_negative_pnl",
        default=0.0,
    )
    if "candidate_stateful_net_adjusted_pnl" in output.columns:
        output["replacement_stateful_net"] = numeric_series(
            output,
            "candidate_stateful_net_adjusted_pnl",
            default=0.0,
        )
    else:
        output["replacement_stateful_net"] = (
            output["candidate_pnl"] - output["candidate_blocked_positive_pnl"]
        )
    output["positive_replacement_regret"] = (
        output["candidate_blocked_positive_pnl"] - output["candidate_pnl"]
    )
    output["replacement_harm_target"] = output["replacement_stateful_net"].lt(0.0)
    output["direct_loss_target"] = output["candidate_pnl"].lt(0.0)
    output["positive_blocking_harm_target"] = (
        output["candidate_blocked_positive_pnl"].gt(0.0)
        & output["replacement_stateful_net"].lt(0.0)
    )
    return output


def summarize_group(frame: pd.DataFrame, group_columns: list[str]) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    working = frame.copy()
    grouped = working.groupby(group_columns, dropna=False)
    summary = grouped.agg(
        rows=("candidate", "size"),
        harmful_rows=("replacement_harm_target", "sum"),
        direct_loss_rows=("direct_loss_target", "sum"),
        positive_blocking_harm_rows=("positive_blocking_harm_target", "sum"),
        candidate_pnl=("candidate_pnl", "sum"),
        replacement_stateful_net=("replacement_stateful_net", "sum"),
        blocked_positive_pnl=("candidate_blocked_positive_pnl", "sum"),
        positive_replacement_regret=("positive_replacement_regret", "sum"),
        avg_exit_regret_risk=("selected_exit_regret_risk", "mean"),
        avg_side_prior_risk=("selected_side_prior_risk", "mean"),
    ).reset_index()
    return summary.sort_values(
        ["replacement_stateful_net", "harmful_rows", "rows"],
        ascending=[True, False, False],
    ).reset_index(drop=True)


def screen_masks(frame: pd.DataFrame) -> dict[str, pd.Series]:
    conf_gap = text_series(frame, "selected_conf_gap_bucket")
    source = text_series(frame, "selected_exit_regret_source")
    profit_hit = numeric_series(frame, "selected_profit_barrier_hit", default=0.0).fillna(0.0)
    loss_first = text_series(frame, "selected_loss_first_bucket")
    return {
        "conf_gap_extreme": conf_gap.isin({"strong", "nonpositive"}),
        "conf_gap_strong": conf_gap.eq("strong"),
        "conf_gap_nonpositive": conf_gap.eq("nonpositive"),
        "exit_regret_global_source": source.ne("bucket"),
        "profit_barrier_miss": profit_hit.le(0.0),
        "conf_gap_extreme_or_global_source": conf_gap.isin({"strong", "nonpositive"})
        | source.ne("bucket"),
        "conf_gap_extreme_and_profit_miss": conf_gap.isin({"strong", "nonpositive"})
        & profit_hit.le(0.0),
        "loss_first_medium_or_higher": loss_first.isin({"medium", "high", "very_high"}),
    }


def summarize_screens(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for name, mask in screen_masks(frame).items():
        flagged = frame[mask].copy()
        kept = frame[~mask].copy()
        flagged_nonharm = flagged[~flagged["replacement_harm_target"]]
        rows.append(
            {
                "screen": name,
                "flagged_rows": int(len(flagged)),
                "flagged_harmful_rows": int(flagged["replacement_harm_target"].sum()),
                "flagged_direct_loss_rows": int(flagged["direct_loss_target"].sum()),
                "flagged_positive_blocking_harm_rows": int(
                    flagged["positive_blocking_harm_target"].sum()
                ),
                "flagged_candidate_pnl": float(flagged["candidate_pnl"].sum()),
                "flagged_stateful_net": float(flagged["replacement_stateful_net"].sum()),
                "flagged_nonharm_stateful_net": float(
                    flagged_nonharm["replacement_stateful_net"].sum()
                ),
                "kept_rows": int(len(kept)),
                "kept_harmful_rows": int(kept["replacement_harm_target"].sum()),
                "kept_stateful_net": float(kept["replacement_stateful_net"].sum()),
                "approx_stateful_improvement_if_suppressed": float(
                    -flagged["replacement_stateful_net"].sum()
                ),
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["approx_stateful_improvement_if_suppressed", "flagged_harmful_rows"],
        ascending=[False, False],
    ).reset_index(drop=True)


def build_replacement_risk_diagnostics(args: argparse.Namespace) -> Path:
    delta_paths = parse_named_paths(args.delta_run)
    enriched_paths = parse_named_paths(args.enriched_trades)
    delta = read_delta_runs(delta_paths)
    enriched = read_enriched_trades(enriched_paths)
    only_candidate = delta[delta["delta_status"].astype(str).eq("only_candidate")].copy()
    merged = only_candidate.merge(
        enriched,
        how="left",
        on=KEY_COLUMNS,
        suffixes=("", "_enriched"),
        indicator="enrichment_merge_status",
    )
    merged = add_selected_replacement_features(
        merged,
        exit_regret_prefix=args.exit_regret_prefix,
        selector_prefix=args.selector_prefix,
        side_prior_prefix=args.side_prior_prefix,
    )
    merged = add_replacement_targets(merged)

    run_dir = make_run_dir(args.output_dir, args.label)
    merged.to_csv(run_dir / "replacement_rows.csv", index=False)
    group_specs = {
        "candidate": ["candidate"],
        "candidate_direction": ["candidate", "direction"],
        "candidate_conf_gap": ["candidate", "selected_conf_gap_bucket"],
        "conf_gap": ["selected_conf_gap_bucket"],
        "exit_regret_source": ["selected_exit_regret_source"],
        "profit_barrier_hit": ["selected_profit_barrier_hit"],
        "loss_first_bucket": ["selected_loss_first_bucket"],
        "time_exit_bucket": ["selected_time_exit_bucket"],
        "combined_session": ["combined_regime", "session_regime"],
        "month_candidate": ["month", "candidate"],
    }
    summaries: dict[str, pd.DataFrame] = {}
    for name, columns in group_specs.items():
        existing = [column for column in columns if column in merged.columns]
        summaries[name] = summarize_group(merged, existing) if existing else pd.DataFrame()
        summaries[name].to_csv(run_dir / f"group_by_{name}.csv", index=False)

    screen_summary = summarize_screens(merged)
    screen_summary.to_csv(run_dir / "screen_summary.csv", index=False)

    match_summary = (
        merged.groupby(
            ["delta_run_name", "enrichment_merge_status"],
            dropna=False,
            observed=False,
        )
        .size()
        .reset_index(name="rows")
    )
    match_summary.to_csv(run_dir / "enrichment_match_summary.csv", index=False)
    config = {
        "delta_runs": delta_paths,
        "enriched_trades": enriched_paths,
        "exit_regret_prefix": args.exit_regret_prefix,
        "selector_prefix": args.selector_prefix,
        "side_prior_prefix": args.side_prior_prefix,
        "note": "diagnostic only; screen improvements are pointwise suppression estimates, not stateful replays",
    }
    (run_dir / "config.json").write_text(
        json.dumps(config, indent=2, default=local_json_default),
        encoding="utf-8",
    )

    print("Replacement summary by candidate:")
    print(summaries["candidate"].to_string(index=False))
    print("\nScreen summary:")
    print(screen_summary.to_string(index=False))
    print("\nEnrichment match summary:")
    print(match_summary.to_string(index=False))
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--delta-run", action="append", required=True)
    parser.add_argument("--enriched-trades", action="append", required=True)
    parser.add_argument(
        "--exit-regret-prefix",
        default="pred_exit_regret_confidence_exit",
    )
    parser.add_argument(
        "--selector-prefix",
        default="pred_exit_regret_selector_confidenceexit_bucket_t0p4",
    )
    parser.add_argument("--side-prior-prefix", default="pred_side_prior_pressure")
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="entry_ev_replacement_risk_delta_diagnostics")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    build_replacement_risk_diagnostics(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
