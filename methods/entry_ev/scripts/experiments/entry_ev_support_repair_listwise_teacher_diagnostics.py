#!/usr/bin/env python3
"""Diagnose whether listwise support-repair oracle labels are teachable."""

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

from entry_ev_support_repair_listwise_cluster_diagnostics import (  # noqa: E402
    DEFAULT_OVERLAP_COLUMNS,
    DEFAULT_QUOTA_COLUMNS,
    greedy_select_with_quotas,
)
from entry_ev_support_repair_pairwise_switch_diagnostics import (  # noqa: E402
    numeric_series,
    parse_csv,
    text_series,
)


DEFAULT_SCORE_SPECS = (
    "repair_score:desc,"
    "hv_chosen_score:desc,"
    "hv_chosen_pred_pnl:desc,"
    "repair_expected_pnl:desc,"
    "hv_chosen_pred_executable_prob:desc,"
    "hv_chosen_pred_tail_loss_prob:asc,"
    "hv_chosen_pred_harmful_overestimate_prob:asc,"
    "repair_support_success_proxy:desc,"
    "hv_chosen_horizon_minutes:asc"
)


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


def parse_score_specs(value: str) -> list[tuple[str, bool]]:
    specs: list[tuple[str, bool]] = []
    for raw_item in parse_csv(value):
        if ":" in raw_item:
            column, direction = raw_item.split(":", 1)
        else:
            column, direction = raw_item, "desc"
        direction = direction.strip().lower()
        if direction not in {"asc", "desc"}:
            raise ValueError(f"score spec direction must be asc or desc: {raw_item}")
        specs.append((column.strip(), direction == "asc"))
    return specs


def rank_auc(labels: pd.Series, scores: pd.Series) -> float:
    valid = labels.notna() & scores.notna()
    label_values = labels[valid].astype(bool).to_numpy()
    score_values = scores[valid].astype(float).to_numpy()
    positives = int(label_values.sum())
    negatives = int(len(label_values) - positives)
    if positives == 0 or negatives == 0:
        return float("nan")
    ranks = pd.Series(score_values).rank(method="average").to_numpy()
    rank_sum_positive = float(ranks[label_values].sum())
    return float(
        (rank_sum_positive - positives * (positives + 1) / 2)
        / (positives * negatives)
    )


def prepare_teacher_examples(
    frame: pd.DataFrame,
    *,
    quota_columns: list[str],
) -> pd.DataFrame:
    output = frame.copy()
    if "candidate_id" not in output.columns:
        output["candidate_id"] = np.arange(len(output), dtype=int)
    candidate_id = pd.to_numeric(output["candidate_id"], errors="coerce")
    fallback_id = pd.Series(np.arange(len(output), dtype=int), index=output.index)
    output["candidate_id"] = candidate_id.where(candidate_id.notna(), fallback_id)
    output["candidate_id"] = output["candidate_id"].astype(int)
    output["decision_timestamp"] = pd.to_datetime(
        output["decision_timestamp"],
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
    missing_exit = output["exit_timestamp"].isna()
    if missing_exit.any():
        output.loc[missing_exit, "exit_timestamp"] = output.loc[
            missing_exit,
            "decision_timestamp",
        ] + pd.to_timedelta(
            numeric_series(output.loc[missing_exit], "hv_chosen_horizon_minutes"),
            unit="m",
        )

    for column in quota_columns:
        output[column] = text_series(output, column)
    output["actual_pnl_at_hv_chosen_horizon"] = numeric_series(
        output,
        "actual_pnl_at_hv_chosen_horizon",
    )
    output["extra_side_needed"] = numeric_series(output, "extra_side_needed")
    output["current_replay_selected"] = bool_series(output, "current_replay_selected")
    if "actual_oracle_greedy_selected" in output.columns:
        output["oracle_teacher_selected"] = bool_series(
            output,
            "actual_oracle_greedy_selected",
        )
    else:
        quota = output.groupby(quota_columns, dropna=False)["extra_side_needed"].transform(
            lambda values: max(0, int(np.ceil(float(pd.to_numeric(values).max())))),
        )
        actual_rank = output.groupby(quota_columns, dropna=False)[
            "actual_pnl_at_hv_chosen_horizon"
        ].rank(method="first", ascending=False)
        output["oracle_teacher_selected"] = actual_rank.le(quota)

    group_sizes = output.groupby(quota_columns, dropna=False)["candidate_id"].transform("size")
    group_quota = output.groupby(quota_columns, dropna=False)["extra_side_needed"].transform(
        lambda values: max(0, int(np.ceil(float(pd.to_numeric(values).max())))),
    )
    output["quota_group_row_count"] = group_sizes.astype(int)
    output["quota_group_quota"] = group_quota.astype(int)
    output["quota_group_is_singleton"] = output["quota_group_row_count"].le(
        output["quota_group_quota"],
    )
    output["quota_group_has_choice"] = ~output["quota_group_is_singleton"]
    output["actual_positive"] = output["actual_pnl_at_hv_chosen_horizon"].gt(0.0)
    output["actual_loss"] = output["actual_pnl_at_hv_chosen_horizon"].lt(0.0)
    output["actual_tail_loss"] = output["actual_pnl_at_hv_chosen_horizon"].le(-5.0)
    return output.reset_index(drop=True)


def quota_teacher_summary(
    frame: pd.DataFrame,
    *,
    quota_columns: list[str],
) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for key, group in frame.groupby(quota_columns, dropna=False, sort=False):
        key_values = key if isinstance(key, tuple) else (key,)
        row: dict[str, Any] = {
            column: value for column, value in zip(quota_columns, key_values, strict=True)
        }
        quota = int(max(0, np.ceil(numeric_series(group, "extra_side_needed").max())))
        current = group[group["current_replay_selected"]]
        oracle = group[group["oracle_teacher_selected"]]
        current_actual = numeric_series(current, "actual_pnl_at_hv_chosen_horizon")
        oracle_actual = numeric_series(oracle, "actual_pnl_at_hv_chosen_horizon")
        group_actual = numeric_series(group, "actual_pnl_at_hv_chosen_horizon")
        current_ids = set(current["candidate_id"].astype(int))
        oracle_ids = set(oracle["candidate_id"].astype(int))
        row.update(
            {
                "row_count": int(len(group)),
                "quota": quota,
                "is_singleton_group": bool(len(group) <= quota),
                "current_selected_count": int(len(current)),
                "oracle_selected_count": int(len(oracle)),
                "current_actual_sum": float(current_actual.sum()) if len(current) else 0.0,
                "oracle_actual_sum": float(oracle_actual.sum()) if len(oracle) else 0.0,
                "oracle_delta_vs_current": float(
                    (oracle_actual.sum() if len(oracle) else 0.0)
                    - (current_actual.sum() if len(current) else 0.0),
                ),
                "current_loss_count": int(current_actual.lt(0.0).sum()) if len(current) else 0,
                "oracle_loss_count": int(oracle_actual.lt(0.0).sum()) if len(oracle) else 0,
                "group_actual_max": float(group_actual.max()) if len(group) else np.nan,
                "group_actual_min": float(group_actual.min()) if len(group) else np.nan,
                "oracle_equals_current": current_ids == oracle_ids,
                "singleton_negative_current": bool(
                    len(group) <= quota and len(current) > 0 and current_actual.sum() < 0.0,
                ),
            }
        )
        rows.append(row)
    return pd.DataFrame(rows)


def summarize_selected(
    frame: pd.DataFrame,
    *,
    selector: str,
    selected_ids: set[int],
    current_actual_sum: float,
    oracle_actual_sum: float,
) -> dict[str, Any]:
    selected = frame[frame["candidate_id"].astype(int).isin(selected_ids)].copy()
    actual = numeric_series(selected, "actual_pnl_at_hv_chosen_horizon")
    oracle_selected = frame["oracle_teacher_selected"].astype(bool)
    selected_oracle_overlap = int(
        frame[
            frame["candidate_id"].astype(int).isin(selected_ids) & oracle_selected
        ]["candidate_id"].nunique()
    )
    oracle_count = int(oracle_selected.sum())
    selected_count = int(len(selected))
    return {
        "selector": selector,
        "selected_count": selected_count,
        "actual_pnl_sum": float(actual.sum()) if selected_count else 0.0,
        "actual_pnl_mean": float(actual.mean()) if selected_count else np.nan,
        "actual_pnl_min": float(actual.min()) if selected_count else np.nan,
        "loss_count": int(actual.lt(0.0).sum()) if selected_count else 0,
        "tail_loss_count": int(actual.le(-5.0).sum()) if selected_count else 0,
        "delta_vs_current": float((actual.sum() if selected_count else 0.0) - current_actual_sum),
        "delta_vs_oracle": float((actual.sum() if selected_count else 0.0) - oracle_actual_sum),
        "oracle_overlap_count": selected_oracle_overlap,
        "oracle_precision": (
            float(selected_oracle_overlap / selected_count) if selected_count else np.nan
        ),
        "oracle_recall": float(selected_oracle_overlap / oracle_count) if oracle_count else np.nan,
    }


def feature_selector_summary(
    frame: pd.DataFrame,
    *,
    score_specs: list[tuple[str, bool]],
    quota_columns: list[str],
    overlap_columns: list[str],
) -> pd.DataFrame:
    current_actual_sum = float(
        numeric_series(
            frame[frame["current_replay_selected"]],
            "actual_pnl_at_hv_chosen_horizon",
        ).sum()
    )
    oracle_actual_sum = float(
        numeric_series(
            frame[frame["oracle_teacher_selected"]],
            "actual_pnl_at_hv_chosen_horizon",
        ).sum()
    )
    rows: list[dict[str, Any]] = []
    current_ids = set(
        frame[frame["current_replay_selected"]]["candidate_id"].astype(int).tolist()
    )
    oracle_ids = set(
        frame[frame["oracle_teacher_selected"]]["candidate_id"].astype(int).tolist()
    )
    rows.append(
        summarize_selected(
            frame,
            selector="current_replay",
            selected_ids=current_ids,
            current_actual_sum=current_actual_sum,
            oracle_actual_sum=oracle_actual_sum,
        )
    )
    rows.append(
        summarize_selected(
            frame,
            selector="actual_oracle_teacher",
            selected_ids=oracle_ids,
            current_actual_sum=current_actual_sum,
            oracle_actual_sum=oracle_actual_sum,
        )
    )
    for column, ascending in score_specs:
        if column not in frame.columns:
            rows.append(
                {
                    "selector": f"{column}_{'asc' if ascending else 'desc'}",
                    "missing_score_column": True,
                }
            )
            continue
        selected_ids = greedy_select_with_quotas(
            frame,
            sort_columns=[column, "decision_timestamp", "entry_timestamp"],
            ascending=[ascending, True, True],
            quota_columns=quota_columns,
            overlap_columns=overlap_columns,
        )
        score = numeric_series(frame, column, default=np.nan)
        if ascending:
            auc_score = -score
        else:
            auc_score = score
        actual = numeric_series(frame, "actual_pnl_at_hv_chosen_horizon")
        row = summarize_selected(
            frame,
            selector=f"{column}_{'asc' if ascending else 'desc'}",
            selected_ids=selected_ids,
            current_actual_sum=current_actual_sum,
            oracle_actual_sum=oracle_actual_sum,
        )
        row.update(
            {
                "missing_score_column": False,
                "score_column": column,
                "score_direction": "asc" if ascending else "desc",
                "score_spearman_actual": float(score.corr(actual, method="spearman"))
                if score.notna().sum() >= 2
                else np.nan,
                "oracle_selected_auc": rank_auc(
                    frame["oracle_teacher_selected"].astype(bool),
                    auc_score,
                ),
                "score_mean_oracle_selected": float(
                    score[frame["oracle_teacher_selected"]].mean()
                )
                if frame["oracle_teacher_selected"].any()
                else np.nan,
                "score_mean_non_oracle": float(
                    score[~frame["oracle_teacher_selected"]].mean()
                )
                if (~frame["oracle_teacher_selected"]).any()
                else np.nan,
            }
        )
        rows.append(row)
    return pd.DataFrame(rows)


def overview_summary(
    frame: pd.DataFrame,
    group_summary: pd.DataFrame,
    selector_summary: pd.DataFrame,
) -> pd.DataFrame:
    current = selector_summary[selector_summary["selector"].eq("current_replay")].iloc[0]
    oracle = selector_summary[
        selector_summary["selector"].eq("actual_oracle_teacher")
    ].iloc[0]
    singleton = group_summary[group_summary["is_singleton_group"]]
    learnable = group_summary[~group_summary["is_singleton_group"]]
    rows = [
        {
            "row_count": int(len(frame)),
            "quota_group_count": int(len(group_summary)),
            "learnable_group_count": int(len(learnable)),
            "singleton_group_count": int(len(singleton)),
            "current_actual_sum": float(current["actual_pnl_sum"]),
            "oracle_actual_sum": float(oracle["actual_pnl_sum"]),
            "oracle_delta_vs_current": float(
                oracle["actual_pnl_sum"] - current["actual_pnl_sum"],
            ),
            "current_loss_count": int(current["loss_count"]),
            "oracle_loss_count": int(oracle["loss_count"]),
            "singleton_negative_group_count": int(
                group_summary["singleton_negative_current"].sum(),
            ),
            "singleton_negative_actual_sum": float(
                singleton[singleton["singleton_negative_current"]][
                    "current_actual_sum"
                ].sum()
            )
            if not singleton.empty
            else 0.0,
            "learnable_oracle_delta_sum": float(
                learnable["oracle_delta_vs_current"].sum(),
            )
            if not learnable.empty
            else 0.0,
        },
    ]
    return pd.DataFrame(rows)


def run_diagnostics(args: argparse.Namespace) -> Path:
    raw = pd.read_csv(args.candidate_examples)
    quota_columns = parse_csv(args.quota_columns)
    overlap_columns = parse_csv(args.overlap_columns)
    score_specs = parse_score_specs(args.score_specs)
    examples = prepare_teacher_examples(raw, quota_columns=quota_columns)
    group_summary = quota_teacher_summary(examples, quota_columns=quota_columns)
    selectors = feature_selector_summary(
        examples,
        score_specs=score_specs,
        quota_columns=quota_columns,
        overlap_columns=overlap_columns,
    )
    overview = overview_summary(examples, group_summary, selectors)

    run_dir = make_run_dir(args.output_dir, args.label)
    examples.to_csv(run_dir / "support_repair_listwise_teacher_examples.csv", index=False)
    group_summary.to_csv(
        run_dir / "support_repair_listwise_teacher_group_summary.csv",
        index=False,
    )
    selectors.to_csv(
        run_dir / "support_repair_listwise_teacher_feature_summary.csv",
        index=False,
    )
    overview.to_csv(
        run_dir / "support_repair_listwise_teacher_overview.csv",
        index=False,
    )
    (run_dir / "config.json").write_text(
        json.dumps(
            {
                "candidate_examples": args.candidate_examples,
                "quota_columns": quota_columns,
                "overlap_columns": overlap_columns,
                "score_specs": args.score_specs,
            },
            indent=2,
            sort_keys=True,
            default=local_json_default,
        )
        + "\n",
        encoding="utf-8",
    )

    print("Support repair listwise teacher diagnostics:")
    print(overview.to_string(index=False))
    print(selectors.to_string(index=False))
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-examples", type=Path, required=True)
    parser.add_argument("--quota-columns", default=DEFAULT_QUOTA_COLUMNS)
    parser.add_argument("--overlap-columns", default=DEFAULT_OVERLAP_COLUMNS)
    parser.add_argument("--score-specs", default=DEFAULT_SCORE_SPECS)
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="entry_ev_support_repair_listwise_teacher")
    return parser


def main(argv: list[str] | None = None) -> int:
    run_diagnostics(build_parser().parse_args(argv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
