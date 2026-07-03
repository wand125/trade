#!/usr/bin/env python3
"""Diagnose where contextual positive-PnL penalty rows sit in selection ranks."""

from __future__ import annotations

import argparse
import json
import math
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

from entry_ev_support_repair_pairwise_switch_diagnostics import (  # noqa: E402
    bool_series,
    numeric_series,
    parse_csv,
    text_series,
)


SCENARIO_COLUMNS = [
    "row_scope",
    "prob_threshold",
    "ev_threshold",
    "tail_prob_threshold",
    "require_model_used",
    "ranker_score_mode",
    "ranker_abstention_rule",
    "positive_pnl_gate_rule",
    "positive_pnl_penalty_label",
]
DEFAULT_QUOTA_COLUMNS = "scenario_key,role,month,side"
DEFAULT_RANK_SPECS = (
    "repair_score:desc,"
    "support_reduction_value:desc,"
    "repair_expected_pnl:desc,"
    "decision_timestamp:asc,"
    "entry_timestamp:asc,"
    "hv_chosen_horizon_minutes:asc"
)
IDENTITY_COLUMNS = [
    "role",
    "month",
    "side",
    "row_scope",
    "decision_timestamp_key",
    "entry_timestamp_key",
    "exit_timestamp_key",
    "hv_chosen_horizon_minutes",
]
CASE_COLUMNS = [
    "candidate_file",
    "positive_pnl_penalty_label",
    "ranker_score_mode",
    "ranker_abstention_rule",
    "role",
    "month",
    "side",
    "row_scope",
    "decision_timestamp",
    "hv_chosen_horizon_minutes",
    "quota_rank",
    "group_quota",
    "selected_boundary_rank",
    "rank_vs_selected_boundary",
    "selected_score_floor",
    "score_gap_to_selected_floor",
    "repair_score",
    "support_reduction_value",
    "repair_expected_pnl",
    "hv_chosen_pred_pnl",
    "hv_chosen_pred_tail_loss_prob",
    "hv_chosen_pred_harmful_overestimate_prob",
    "actual_pnl_at_hv_chosen_horizon",
    "positive_pnl_penalty_amount",
    "positive_pnl_penalty_signal",
    "positive_pnl_penalty_contextual_prior_pointwise_gate_delta",
    "positive_pnl_penalty_contextual_prior_loss_precision",
    "positive_pnl_penalty_contextual_prior_winner_damage_ratio",
    "positive_pnl_penalty_contextual_prior_observed_month_count",
    "positive_pnl_penalty_contextual_prior_flagged_month_count",
    "combined_regime",
    "session_regime",
    "near_miss_bucket",
    "selected_addition",
    "selection_outcome",
    "near_quota",
    "near_selected_boundary",
]
SELECTION_OUTCOME_PRIORITY = {
    "selected": 0,
    "overlap": 1,
    "quota_full": 2,
    "pred_pnl_floor": 3,
    "actual_pnl_floor": 4,
    "tail_prob_ceiling": 5,
    "not_in_selection_artifact": 9,
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


def parse_score_specs(value: str) -> list[tuple[str, bool]]:
    specs: list[tuple[str, bool]] = []
    for item in parse_csv(value):
        if ":" in item:
            column, direction = item.split(":", 1)
        else:
            column, direction = item, "desc"
        direction = direction.strip().lower()
        if direction not in {"asc", "desc"}:
            raise ValueError(f"rank direction must be asc or desc: {item}")
        specs.append((column.strip(), direction == "asc"))
    if not specs:
        raise ValueError("at least one rank spec is required")
    return specs


def value_key(value: Any) -> str:
    if isinstance(value, (bool, np.bool_)):
        return "true" if bool(value) else "false"
    if value is None:
        return "missing"
    if isinstance(value, float) and math.isnan(value):
        return "missing"
    if isinstance(value, (int, np.integer)):
        return str(int(value))
    if isinstance(value, (float, np.floating)):
        return f"{float(value):g}"
    text = str(value).strip()
    return "missing" if text == "" or text.lower() == "nan" else text


def timestamp_key(series: pd.Series) -> pd.Series:
    values = pd.to_datetime(series, utc=True, errors="coerce")
    return values.dt.strftime("%Y-%m-%dT%H:%M:%SZ").fillna("missing")


def scenario_key(frame: pd.DataFrame) -> pd.Series:
    return frame[SCENARIO_COLUMNS].apply(
        lambda row: "|".join(value_key(row[column]) for column in SCENARIO_COLUMNS),
        axis=1,
    )


def candidate_identity_key(frame: pd.DataFrame) -> pd.Series:
    return frame[IDENTITY_COLUMNS].apply(
        lambda row: "|".join(value_key(row[column]) for column in IDENTITY_COLUMNS),
        axis=1,
    )


def scenario_candidate_key(frame: pd.DataFrame) -> pd.Series:
    return frame["scenario_key"].astype(str) + "|" + frame["candidate_identity_key"].astype(str)


def normalize_replay_rows(frame: pd.DataFrame, *, source_name: str = "missing") -> pd.DataFrame:
    output = frame.copy()
    if "candidate_file" not in output.columns:
        output["candidate_file"] = source_name

    defaults: dict[str, Any] = {
        "row_scope": "available_candidates",
        "prob_threshold": 0.0,
        "ev_threshold": 0.0,
        "tail_prob_threshold": 0.0,
        "require_model_used": False,
        "ranker_score_mode": "missing",
        "ranker_abstention_rule": "none",
        "positive_pnl_gate_rule": "none",
        "positive_pnl_penalty_label": "none",
    }
    for column, default in defaults.items():
        if column not in output.columns:
            output[column] = default

    for column in [
        "candidate_file",
        "role",
        "month",
        "side",
        "row_scope",
        "ranker_score_mode",
        "ranker_abstention_rule",
        "positive_pnl_gate_rule",
        "positive_pnl_penalty_label",
        "combined_regime",
        "session_regime",
        "near_miss_bucket",
    ]:
        output[column] = text_series(output, column)
    output["month"] = output["month"].astype(str).str.slice(0, 7)

    for column in [
        "prob_threshold",
        "ev_threshold",
        "tail_prob_threshold",
        "hv_chosen_horizon_minutes",
        "hv_chosen_pred_pnl",
        "hv_chosen_pred_tail_loss_prob",
        "hv_chosen_pred_harmful_overestimate_prob",
        "actual_pnl_at_hv_chosen_horizon",
        "adjusted_pnl",
        "extra_side_needed",
        "repair_score",
        "support_reduction_value",
        "repair_expected_pnl",
        "positive_pnl_penalty_amount",
        "positive_pnl_penalty_signal",
        "positive_pnl_penalty_contextual_prior_pointwise_gate_delta",
        "positive_pnl_penalty_contextual_prior_loss_precision",
        "positive_pnl_penalty_contextual_prior_winner_damage_ratio",
        "positive_pnl_penalty_contextual_prior_observed_month_count",
        "positive_pnl_penalty_contextual_prior_flagged_month_count",
    ]:
        output[column] = numeric_series(output, column, default=0.0)
    output["hv_chosen_horizon_minutes"] = (
        output["hv_chosen_horizon_minutes"].round().astype(int)
    )
    output["require_model_used"] = bool_series(output, "require_model_used")

    output["decision_timestamp"] = pd.to_datetime(
        output.get("decision_timestamp"),
        utc=True,
        errors="coerce",
    )
    output["entry_timestamp"] = pd.to_datetime(
        output.get("entry_timestamp", output["decision_timestamp"]),
        utc=True,
        errors="coerce",
    )
    output["exit_timestamp"] = pd.to_datetime(
        output.get("exit_timestamp"),
        utc=True,
        errors="coerce",
    )
    missing_entry = output["entry_timestamp"].isna()
    if missing_entry.any():
        output.loc[missing_entry, "entry_timestamp"] = output.loc[
            missing_entry,
            "decision_timestamp",
        ]
    missing_exit = output["exit_timestamp"].isna()
    if missing_exit.any():
        output.loc[missing_exit, "exit_timestamp"] = output.loc[
            missing_exit,
            "entry_timestamp",
        ] + pd.to_timedelta(
            output.loc[missing_exit, "hv_chosen_horizon_minutes"],
            unit="m",
        )
    output = output[output["decision_timestamp"].notna()].copy()

    output["decision_timestamp_key"] = timestamp_key(output["decision_timestamp"])
    output["entry_timestamp_key"] = timestamp_key(output["entry_timestamp"])
    output["exit_timestamp_key"] = timestamp_key(output["exit_timestamp"])
    output["scenario_key"] = scenario_key(output)
    output["candidate_identity_key"] = candidate_identity_key(output)
    output["scenario_candidate_key"] = scenario_candidate_key(output)
    output["penalized"] = output["positive_pnl_penalty_amount"].gt(0.0)
    output["actual_loss"] = output["actual_pnl_at_hv_chosen_horizon"].lt(0.0)
    output["actual_win"] = output["actual_pnl_at_hv_chosen_horizon"].gt(0.0)
    return output.reset_index(drop=True)


def load_candidate_files(paths: list[Path]) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for path in paths:
        frame = pd.read_csv(path)
        frame = pd.concat(
            [frame, pd.Series(path.name, index=frame.index, name="candidate_file")],
            axis=1,
        ).copy()
        frames.append(frame)
    if not frames:
        raise ValueError("at least one candidate file is required")
    return pd.concat(frames, ignore_index=True, sort=False)


def resolve_candidate_paths(args: argparse.Namespace) -> list[Path]:
    paths = [Path(path) for path in args.candidate_files]
    for pattern in args.candidate_glob:
        paths.extend(sorted(Path().glob(pattern)))
    paths = sorted({path for path in paths})
    if not paths:
        raise ValueError("no candidate files matched")
    missing = [path for path in paths if not path.exists()]
    if missing:
        raise FileNotFoundError("missing candidate files: " + ", ".join(map(str, missing)))
    return paths


def attach_selected_additions(candidates: pd.DataFrame, additions: pd.DataFrame) -> pd.DataFrame:
    output = candidates.copy()
    selected = normalize_replay_rows(additions, source_name="additions")
    selected_keys = set(selected["scenario_candidate_key"].astype(str))
    output["selected_addition"] = output["scenario_candidate_key"].astype(str).isin(selected_keys)
    output["selection_outcome"] = np.where(
        output["selected_addition"],
        "selected",
        "not_in_selection_artifact",
    )
    return output


def load_rejection_rows(path: Path) -> pd.DataFrame:
    required = set(SCENARIO_COLUMNS + IDENTITY_COLUMNS)
    required.update(
        {
            "role",
            "month",
            "side",
            "row_scope",
            "decision_timestamp",
            "entry_timestamp",
            "exit_timestamp",
            "hv_chosen_horizon_minutes",
            "reject_reason",
        }
    )
    return pd.read_csv(path, usecols=lambda column: column in required)


def attach_selection_outcomes(
    candidates: pd.DataFrame,
    additions: pd.DataFrame,
    rejections: pd.DataFrame | None,
) -> pd.DataFrame:
    output = attach_selected_additions(candidates, additions)
    if rejections is None or rejections.empty:
        return output
    raw_rejections = rejections.copy()
    raw_rejections["reject_reason"] = text_series(raw_rejections, "reject_reason")
    rejected = normalize_replay_rows(raw_rejections, source_name="rejections")
    rejected["reject_reason"] = text_series(rejected, "reject_reason")
    reason_by_key = (
        rejected[["scenario_candidate_key", "reject_reason"]]
        .sort_values(
            "reject_reason",
            key=lambda values: values.map(
                lambda value: SELECTION_OUTCOME_PRIORITY.get(str(value), 8)
            ),
        )
        .groupby("scenario_candidate_key", dropna=False)["reject_reason"]
        .first()
    )
    rejected_reason = output["scenario_candidate_key"].map(reason_by_key)
    output["selection_outcome"] = np.where(
        output["selected_addition"],
        "selected",
        rejected_reason.fillna("not_in_selection_artifact"),
    )
    return output


def add_selection_rank_columns(
    frame: pd.DataFrame,
    *,
    quota_columns: list[str],
    rank_specs: list[tuple[str, bool]],
    near_rank_window: int,
) -> pd.DataFrame:
    output = frame.copy()
    for column in quota_columns:
        if column not in output.columns:
            raise ValueError(f"missing quota column: {column}")
    sort_columns = [column for column, _ in rank_specs if column in output.columns]
    ascending = [ascending for column, ascending in rank_specs if column in output.columns]
    if not sort_columns:
        sort_columns = ["decision_timestamp"]
        ascending = [True]

    sorted_index = output.sort_values(sort_columns, ascending=ascending).index
    ranks = pd.Series(np.arange(1, len(sorted_index) + 1), index=sorted_index)
    output["_global_sort_rank"] = ranks.reindex(output.index).astype(int)
    output = output.sort_values(quota_columns + ["_global_sort_rank"]).copy()
    output["quota_rank"] = output.groupby(quota_columns, dropna=False).cumcount() + 1

    group = output.groupby(quota_columns, dropna=False)
    output["group_row_count"] = group["candidate_identity_key"].transform("size").astype(int)
    quota = group["extra_side_needed"].transform(
        lambda values: max(0, int(np.ceil(float(pd.to_numeric(values).max()))))
    )
    output["group_quota"] = quota.astype(int)
    output["near_quota_rank_limit"] = output["group_quota"] + int(near_rank_window)
    output["near_quota"] = output["quota_rank"].le(output["near_quota_rank_limit"])
    output["within_quota"] = output["quota_rank"].le(output["group_quota"])

    selected = bool_series(output, "selected_addition")
    output["_selected_rank"] = output["quota_rank"].where(selected)
    output["_selected_score"] = output["repair_score"].where(selected)
    output["selected_count_in_group"] = group["selected_addition"].transform(
        lambda values: int(pd.Series(values).astype(bool).sum())
    )
    output["selected_rank_min"] = group["_selected_rank"].transform("min")
    output["selected_rank_max"] = group["_selected_rank"].transform("max")
    output["selected_score_floor"] = group["_selected_score"].transform("min")
    output["selected_score_ceiling"] = group["_selected_score"].transform("max")
    output["selected_boundary_rank"] = output["selected_rank_max"].where(
        output["selected_rank_max"].notna(),
        output["group_quota"],
    )
    output["rank_vs_selected_boundary"] = (
        output["quota_rank"] - output["selected_boundary_rank"]
    )
    output["near_selected_boundary"] = output["rank_vs_selected_boundary"].le(
        int(near_rank_window)
    )
    output["score_gap_to_selected_floor"] = (
        output["selected_score_floor"] - output["repair_score"]
    )
    return output.drop(columns=["_global_sort_rank", "_selected_rank", "_selected_score"])


def aggregate_penalty_scope(frame: pd.DataFrame, *, prefix: str = "") -> dict[str, Any]:
    penalized = bool_series(frame, "penalized")
    selected = bool_series(frame, "selected_addition")
    losses = bool_series(frame, "actual_loss")
    wins = bool_series(frame, "actual_win")
    pnl = numeric_series(frame, "actual_pnl_at_hv_chosen_horizon", default=0.0)
    rank = numeric_series(frame, "quota_rank", default=np.nan)
    rank_gap = numeric_series(frame, "rank_vs_selected_boundary", default=np.nan)
    score_gap = numeric_series(frame, "score_gap_to_selected_floor", default=np.nan)

    scoped = frame[penalized].copy()
    scoped_rank = rank[penalized].dropna()
    scoped_rank_gap = rank_gap[penalized].dropna()
    scoped_score_gap = score_gap[penalized].dropna()
    return {
        f"{prefix}row_count": int(len(frame)),
        f"{prefix}candidate_identity_count": int(frame["candidate_identity_key"].nunique())
        if len(frame)
        else 0,
        f"{prefix}selected_count": int(selected.sum()),
        f"{prefix}selected_pnl": float(pnl.where(selected, 0.0).sum()),
        f"{prefix}penalized_count": int(penalized.sum()),
        f"{prefix}penalized_candidate_identity_count": int(
            scoped["candidate_identity_key"].nunique()
        )
        if len(scoped)
        else 0,
        f"{prefix}penalized_pnl": float(pnl.where(penalized, 0.0).sum()),
        f"{prefix}penalized_loss_count": int((penalized & losses).sum()),
        f"{prefix}penalized_loss_pnl": float(pnl.where(penalized & losses, 0.0).sum()),
        f"{prefix}penalized_win_count": int((penalized & wins).sum()),
        f"{prefix}penalized_win_pnl": float(pnl.where(penalized & wins, 0.0).sum()),
        f"{prefix}selected_penalized_count": int((selected & penalized).sum()),
        f"{prefix}selected_penalized_pnl": float(pnl.where(selected & penalized, 0.0).sum()),
        f"{prefix}penalized_within_quota_count": int(
            (penalized & bool_series(frame, "within_quota")).sum()
        ),
        f"{prefix}penalized_near_quota_count": int(
            (penalized & bool_series(frame, "near_quota")).sum()
        ),
        f"{prefix}penalized_near_selected_boundary_count": int(
            (penalized & bool_series(frame, "near_selected_boundary")).sum()
        ),
        f"{prefix}penalized_rank_min": float(scoped_rank.min()) if len(scoped_rank) else np.nan,
        f"{prefix}penalized_rank_median": float(scoped_rank.median())
        if len(scoped_rank)
        else np.nan,
        f"{prefix}penalized_rank_p90": float(scoped_rank.quantile(0.90))
        if len(scoped_rank)
        else np.nan,
        f"{prefix}penalized_rank_gap_min": float(scoped_rank_gap.min())
        if len(scoped_rank_gap)
        else np.nan,
        f"{prefix}penalized_rank_gap_median": float(scoped_rank_gap.median())
        if len(scoped_rank_gap)
        else np.nan,
        f"{prefix}penalized_score_gap_min": float(scoped_score_gap.min())
        if len(scoped_score_gap)
        else np.nan,
        f"{prefix}penalized_score_gap_median": float(scoped_score_gap.median())
        if len(scoped_score_gap)
        else np.nan,
    }


def penalty_label_summary(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for label, group in frame.groupby("positive_pnl_penalty_label", dropna=False, sort=True):
        row = {"positive_pnl_penalty_label": label}
        row.update(aggregate_penalty_scope(group))
        rows.append(row)
    return pd.DataFrame(rows).sort_values(
        ["selected_penalized_count", "penalized_pnl", "penalized_count"],
        ascending=[False, True, False],
    ).reset_index(drop=True)


def score_mode_summary(frame: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    group_columns = [
        "positive_pnl_penalty_label",
        "ranker_score_mode",
        "ranker_abstention_rule",
    ]
    for key, group in frame.groupby(group_columns, dropna=False, sort=True):
        row = dict(zip(group_columns, key, strict=True))
        row.update(aggregate_penalty_scope(group))
        rows.append(row)
    return pd.DataFrame(rows).sort_values(
        ["penalized_pnl", "penalized_count"],
        ascending=[True, False],
    ).reset_index(drop=True)


def rejection_summary(frame: pd.DataFrame) -> pd.DataFrame:
    penalized_frame = frame[bool_series(frame, "penalized")].copy()
    if penalized_frame.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    group_columns = ["positive_pnl_penalty_label", "selection_outcome"]
    for key, group in penalized_frame.groupby(group_columns, dropna=False, sort=True):
        row = dict(zip(group_columns, key, strict=True))
        row.update(aggregate_penalty_scope(group))
        rows.append(row)
    return pd.DataFrame(rows).sort_values(
        ["positive_pnl_penalty_label", "penalized_pnl"],
        ascending=[True, True],
    ).reset_index(drop=True)


def quota_group_summary(frame: pd.DataFrame, *, quota_columns: list[str]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    group_columns = [column for column in quota_columns if column != "scenario_key"]
    group_columns.extend(
        [
            "positive_pnl_penalty_label",
            "ranker_score_mode",
            "ranker_abstention_rule",
            "role",
            "month",
            "side",
        ]
    )
    seen: set[str] = set()
    ordered_group_columns: list[str] = []
    for column in group_columns:
        if column in frame.columns and column not in seen:
            ordered_group_columns.append(column)
            seen.add(column)

    for key, group in frame.groupby(quota_columns, dropna=False, sort=False):
        key_values = key if isinstance(key, tuple) else (key,)
        base = dict(zip(quota_columns, key_values, strict=True))
        penalized = group[bool_series(group, "penalized")].copy()
        if penalized.empty:
            continue
        best_penalized = penalized.sort_values(
            ["quota_rank", "actual_pnl_at_hv_chosen_horizon"],
            ascending=[True, True],
        ).iloc[0]
        row = {column: base[column] for column in quota_columns if column != "scenario_key"}
        for column in ordered_group_columns:
            if column in group.columns and column not in row:
                row[column] = group[column].iloc[0]
        row.update(aggregate_penalty_scope(group))
        row.update(
            {
                "group_quota": int(numeric_series(group, "group_quota").max()),
                "group_row_count": int(len(group)),
                "best_penalized_rank": int(best_penalized["quota_rank"]),
                "best_penalized_rank_gap": float(best_penalized["rank_vs_selected_boundary"]),
                "best_penalized_repair_score": float(best_penalized["repair_score"]),
                "best_penalized_selected_score_gap": float(
                    best_penalized["score_gap_to_selected_floor"]
                )
                if pd.notna(best_penalized["score_gap_to_selected_floor"])
                else np.nan,
                "best_penalized_actual_pnl": float(
                    best_penalized["actual_pnl_at_hv_chosen_horizon"]
                ),
                "selected_boundary_rank": float(
                    numeric_series(group, "selected_boundary_rank").max()
                ),
                "selected_score_floor": float(
                    numeric_series(group, "selected_score_floor", default=np.nan).min()
                )
                if group["selected_score_floor"].notna().any()
                else np.nan,
            }
        )
        rows.append(row)
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(
        [
            "selected_penalized_count",
            "best_penalized_rank_gap",
            "penalized_pnl",
            "penalized_count",
        ],
        ascending=[False, True, True, False],
    ).reset_index(drop=True)


def near_selected_cases(frame: pd.DataFrame, *, limit: int) -> pd.DataFrame:
    penalized = frame[bool_series(frame, "penalized")].copy()
    columns = [column for column in CASE_COLUMNS if column in penalized.columns]
    if penalized.empty:
        return pd.DataFrame(columns=columns)
    return penalized.sort_values(
        [
            "selected_addition",
            "rank_vs_selected_boundary",
            "quota_rank",
            "actual_pnl_at_hv_chosen_horizon",
        ],
        ascending=[False, True, True, True],
    )[columns].head(limit).reset_index(drop=True)


def write_outputs(
    run_dir: Path,
    *,
    ranked: pd.DataFrame,
    label_summary: pd.DataFrame,
    mode_summary: pd.DataFrame,
    outcome_summary: pd.DataFrame,
    group_summary: pd.DataFrame,
    cases: pd.DataFrame,
) -> None:
    label_summary.to_csv(run_dir / "contextual_penalty_near_selected_label_summary.csv", index=False)
    mode_summary.to_csv(run_dir / "contextual_penalty_near_selected_score_mode_summary.csv", index=False)
    outcome_summary.to_csv(run_dir / "contextual_penalty_near_selected_outcome_summary.csv", index=False)
    group_summary.to_csv(run_dir / "contextual_penalty_near_selected_group_summary.csv", index=False)
    cases.to_csv(run_dir / "contextual_penalty_near_selected_cases.csv", index=False)
    penalized_columns = [column for column in CASE_COLUMNS if column in ranked.columns]
    ranked[bool_series(ranked, "penalized")][penalized_columns].to_csv(
        run_dir / "contextual_penalty_penalized_rows.csv",
        index=False,
    )


def run_diagnostics(args: argparse.Namespace) -> Path:
    candidate_paths = resolve_candidate_paths(args)
    candidates = normalize_replay_rows(load_candidate_files(candidate_paths))
    additions = pd.read_csv(args.additions)
    rejections = load_rejection_rows(args.rejections) if args.rejections else None
    attached = attach_selection_outcomes(candidates, additions, rejections)
    quota_columns = parse_csv(args.quota_columns)
    rank_specs = parse_score_specs(args.rank_specs)
    ranked = add_selection_rank_columns(
        attached,
        quota_columns=quota_columns,
        rank_specs=rank_specs,
        near_rank_window=args.near_rank_window,
    )

    label_summary = penalty_label_summary(ranked)
    mode_summary = score_mode_summary(ranked)
    outcome_summary = rejection_summary(ranked)
    group_summary = quota_group_summary(ranked, quota_columns=quota_columns)
    cases = near_selected_cases(ranked, limit=args.case_limit)

    run_dir = make_run_dir(args.output_dir, args.label)
    write_outputs(
        run_dir,
        ranked=ranked,
        label_summary=label_summary,
        mode_summary=mode_summary,
        outcome_summary=outcome_summary,
        group_summary=group_summary,
        cases=cases,
    )
    (run_dir / "config.json").write_text(
        json.dumps(
            {
                "candidate_files": [str(path) for path in candidate_paths],
                "additions": str(args.additions),
                "rejections": str(args.rejections) if args.rejections else None,
                "quota_columns": quota_columns,
                "rank_specs": [(column, "asc" if ascending else "desc") for column, ascending in rank_specs],
                "near_rank_window": args.near_rank_window,
                "case_limit": args.case_limit,
            },
            indent=2,
            sort_keys=True,
            default=local_json_default,
        )
        + "\n",
        encoding="utf-8",
    )

    print("Contextual penalty near-selected label summary:")
    print(label_summary.head(args.print_rows).to_string(index=False))
    print("\nScore mode summary:")
    print(mode_summary.head(args.print_rows).to_string(index=False))
    if not outcome_summary.empty:
        print("\nSelection outcome summary:")
        print(outcome_summary.head(args.print_rows).to_string(index=False))
    print("\nNear-selected cases:")
    print(cases.head(args.print_rows).to_string(index=False))
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-files", nargs="*", default=[])
    parser.add_argument("--candidate-glob", action="append", default=[])
    parser.add_argument("--additions", type=Path, required=True)
    parser.add_argument("--rejections", type=Path)
    parser.add_argument("--quota-columns", default=DEFAULT_QUOTA_COLUMNS)
    parser.add_argument("--rank-specs", default=DEFAULT_RANK_SPECS)
    parser.add_argument("--near-rank-window", type=int, default=3)
    parser.add_argument("--case-limit", type=int, default=500)
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="entry_ev_contextual_penalty_near_selected_diagnostics")
    parser.add_argument("--print-rows", type=int, default=20)
    return parser


def main(argv: list[str] | None = None) -> int:
    run_diagnostics(build_parser().parse_args(argv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
