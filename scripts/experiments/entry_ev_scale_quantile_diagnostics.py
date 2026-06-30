#!/usr/bin/env python3
"""Compare entry-EV scale drift and quantile admission support across folds."""

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


SUMMARY_QUANTILES = (0.5, 0.9, 0.95, 0.99)
SCORE_DEFINITIONS = {
    "raw": (
        "pred_long_best_adjusted_pnl",
        "pred_short_best_adjusted_pnl",
    ),
    "calibrated": (
        "pred_calibrated_long_best_adjusted_pnl",
        "pred_calibrated_short_best_adjusted_pnl",
    ),
}
SCOPE_COLUMNS = {
    "month": ["family", "month"],
    "side_month": ["family", "month", "selected_side_name"],
    "side_regime_session_month": [
        "family",
        "month",
        "selected_side_name",
        "combined_regime",
        "session_regime",
    ],
}
BASE_PRINT_COLUMNS = [
    "score_kind",
    "family",
    "month",
    "row_count",
    "valid_count",
    "selected_long_share",
    "long_score_q95",
    "short_score_q95",
    "selected_score_q95",
    "side_gap_q95",
    "selected_rank_q95",
]
GATE_PRINT_COLUMNS = [
    "score_kind",
    "quantile_scope",
    "family",
    "score_quantile",
    "side_gap_quantile",
    "rank_quantile",
    "min_scope_rows",
    "scope_supported_count",
    "quantile_enter_count",
    "quantile_long_enter_count",
    "quantile_short_enter_count",
    "active_months",
    "min_monthly_enter_count",
    "max_monthly_enter_count",
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


def parse_family_predictions(values: list[str]) -> dict[str, Path]:
    families: dict[str, Path] = {}
    for value in values:
        if "=" not in value:
            raise argparse.ArgumentTypeError(
                "family predictions must use family=path"
            )
        family, path = value.split("=", 1)
        family = family.strip()
        if not family:
            raise argparse.ArgumentTypeError("family name must not be empty")
        families[family] = Path(path.strip())
    if not families:
        raise argparse.ArgumentTypeError("at least one family prediction is required")
    return families


def parse_float_csv(value: str) -> list[float]:
    return [float(part.strip()) for part in value.split(",") if part.strip()]


def parse_scope_csv(value: str) -> list[str]:
    scopes = [part.strip() for part in value.split(",") if part.strip()]
    unknown = sorted(set(scopes) - set(SCOPE_COLUMNS))
    if unknown:
        raise argparse.ArgumentTypeError(
            f"unknown quantile scopes: {','.join(unknown)}"
        )
    return scopes


def month_series(frame: pd.DataFrame) -> pd.Series:
    if "dataset_month" in frame.columns:
        return frame["dataset_month"].astype(str).str.slice(0, 7)
    if "month" in frame.columns:
        return frame["month"].astype(str).str.slice(0, 7)
    if "timestamp" in frame.columns:
        return pd.to_datetime(frame["timestamp"], utc=True).dt.strftime("%Y-%m")
    if "decision_timestamp" in frame.columns:
        return pd.to_datetime(frame["decision_timestamp"], utc=True).dt.strftime(
            "%Y-%m"
        )
    raise ValueError("prediction frame needs dataset_month, month, or timestamp")


def finite_numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        raise ValueError(f"missing prediction column: {column}")
    values = pd.to_numeric(frame[column], errors="coerce")
    return values.where(np.isfinite(values))


def existing_or_missing(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series("__missing__", index=frame.index, dtype="object")
    return frame[column].astype(str).fillna("__missing__")


def quantile_summary(values: pd.Series, prefix: str) -> dict[str, float]:
    clean = pd.to_numeric(values, errors="coerce").dropna()
    if clean.empty:
        return {
            f"{prefix}_q{int(q * 100):02d}": np.nan for q in SUMMARY_QUANTILES
        } | {f"{prefix}_max": np.nan, f"{prefix}_mean": np.nan}
    result = {
        f"{prefix}_q{int(q * 100):02d}": float(clean.quantile(q))
        for q in SUMMARY_QUANTILES
    }
    result[f"{prefix}_max"] = float(clean.max())
    result[f"{prefix}_mean"] = float(clean.mean())
    return result


def percentile_rank_by_group(
    frame: pd.DataFrame,
    *,
    value_column: str,
    group_columns: list[str],
) -> tuple[pd.Series, pd.Series]:
    grouped = frame.groupby(group_columns, dropna=False)[value_column]
    ranks = grouped.rank(method="average", pct=True)
    counts = grouped.transform("count")
    return ranks, counts


def build_score_frame(
    frame: pd.DataFrame,
    *,
    family: str,
    score_kind: str,
    long_score_column: str,
    short_score_column: str,
    long_rank_column: str,
    short_rank_column: str,
) -> pd.DataFrame:
    result = pd.DataFrame(index=frame.index)
    result["family"] = family
    result["month"] = month_series(frame)
    result["score_kind"] = score_kind
    result["combined_regime"] = existing_or_missing(frame, "combined_regime")
    result["session_regime"] = existing_or_missing(frame, "session_regime")
    result["long_score"] = finite_numeric(frame, long_score_column)
    result["short_score"] = finite_numeric(frame, short_score_column)
    result["long_rank"] = finite_numeric(frame, long_rank_column)
    result["short_rank"] = finite_numeric(frame, short_rank_column)
    result["valid_prediction"] = (
        result["long_score"].notna() & result["short_score"].notna()
    )
    result["selected_side"] = np.where(
        result["long_score"] >= result["short_score"],
        1,
        -1,
    )
    result.loc[~result["valid_prediction"], "selected_side"] = 0
    result["selected_side_name"] = np.select(
        [
            result["selected_side"].eq(1),
            result["selected_side"].eq(-1),
        ],
        ["long", "short"],
        default="none",
    )
    result["selected_score"] = np.where(
        result["selected_side"].eq(1),
        result["long_score"],
        result["short_score"],
    )
    result["selected_rank"] = np.where(
        result["selected_side"].eq(1),
        result["long_rank"],
        result["short_rank"],
    )
    result["side_gap"] = (result["long_score"] - result["short_score"]).abs()
    return result


def summarize_distribution_group(group: pd.DataFrame) -> dict[str, object]:
    valid = group["valid_prediction"].fillna(False)
    long_selected = group["selected_side"].eq(1)
    short_selected = group["selected_side"].eq(-1)
    result: dict[str, object] = {
        "row_count": int(len(group)),
        "valid_count": int(valid.sum()),
        "selected_long_count": int((valid & long_selected).sum()),
        "selected_short_count": int((valid & short_selected).sum()),
        "selected_long_share": float((valid & long_selected).sum() / valid.sum())
        if valid.sum()
        else 0.0,
    }
    for column, prefix in [
        ("long_score", "long_score"),
        ("short_score", "short_score"),
        ("selected_score", "selected_score"),
        ("side_gap", "side_gap"),
        ("selected_rank", "selected_rank"),
    ]:
        result.update(quantile_summary(group.loc[valid, column], prefix))
    return result


def build_distribution_summary(
    score_frames: list[pd.DataFrame],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    all_scores = pd.concat(score_frames, ignore_index=True)
    base_rows: list[dict[str, object]] = []
    for keys, group in all_scores.groupby(["score_kind", "family", "month"]):
        score_kind, family, month = keys
        base_rows.append(
            {
                "score_kind": score_kind,
                "family": family,
                "month": month,
                **summarize_distribution_group(group),
            }
        )
    group_rows: list[dict[str, object]] = []
    group_columns = [
        "score_kind",
        "family",
        "month",
        "selected_side_name",
        "combined_regime",
        "session_regime",
    ]
    for keys, group in all_scores.groupby(group_columns, dropna=False):
        group_rows.append(
            {
                **dict(zip(group_columns, keys, strict=True)),
                **summarize_distribution_group(group),
            }
        )
    base = pd.DataFrame(base_rows).sort_values(
        ["score_kind", "family", "month"]
    ).reset_index(drop=True)
    grouped = pd.DataFrame(group_rows).sort_values(
        [
            "score_kind",
            "family",
            "month",
            "selected_side_name",
            "combined_regime",
            "session_regime",
        ]
    ).reset_index(drop=True)
    return base, grouped


def add_scope_quantiles(
    frame: pd.DataFrame,
    *,
    scope_name: str,
) -> pd.DataFrame:
    if scope_name not in SCOPE_COLUMNS:
        raise ValueError(f"unknown quantile scope: {scope_name}")
    result = frame.copy()
    scope_columns = SCOPE_COLUMNS[scope_name]
    for column in scope_columns:
        if column not in result.columns:
            result[column] = "__missing__"
    for value_column, prefix in [
        ("selected_score", "selected_score"),
        ("side_gap", "side_gap"),
        ("selected_rank", "selected_rank"),
    ]:
        ranks, counts = percentile_rank_by_group(
            result,
            value_column=value_column,
            group_columns=scope_columns,
        )
        result[f"{prefix}_pct"] = ranks
        result[f"{prefix}_scope_count"] = counts
    result["quantile_scope"] = scope_name
    return result


def summarize_quantile_gate_group(
    group: pd.DataFrame,
    *,
    score_quantile: float,
    side_gap_quantile: float,
    rank_quantile: float,
    min_scope_rows: int,
) -> dict[str, object]:
    valid = group["valid_prediction"].fillna(False)
    supported = (
        valid
        & (group["selected_score_scope_count"] >= min_scope_rows)
        & (group["side_gap_scope_count"] >= min_scope_rows)
        & (group["selected_rank_scope_count"] >= min_scope_rows)
    )
    enter = (
        supported
        & (group["selected_score_pct"] >= score_quantile)
        & (group["side_gap_pct"] >= side_gap_quantile)
        & (group["selected_rank_pct"] >= rank_quantile)
    )
    result: dict[str, object] = {
        "score_quantile": score_quantile,
        "side_gap_quantile": side_gap_quantile,
        "rank_quantile": rank_quantile,
        "min_scope_rows": min_scope_rows,
        "valid_count": int(valid.sum()),
        "scope_supported_count": int(supported.sum()),
        "quantile_enter_count": int(enter.sum()),
        "quantile_long_enter_count": int(
            (enter & group["selected_side"].eq(1)).sum()
        ),
        "quantile_short_enter_count": int(
            (enter & group["selected_side"].eq(-1)).sum()
        ),
    }
    result.update(quantile_summary(group.loc[enter, "selected_score"], "enter_score"))
    result.update(quantile_summary(group.loc[enter, "side_gap"], "enter_side_gap"))
    result.update(quantile_summary(group.loc[enter, "selected_rank"], "enter_rank"))
    return result


def build_monthly_quantile_gate_summary(
    score_frames: list[pd.DataFrame],
    *,
    quantile_scopes: list[str],
    score_quantiles: list[float],
    side_gap_quantiles: list[float],
    rank_quantiles: list[float],
    min_scope_rows: int,
) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for frame in score_frames:
        for scope_name in quantile_scopes:
            scoped = add_scope_quantiles(frame, scope_name=scope_name)
            for keys, group in scoped.groupby(
                ["score_kind", "quantile_scope", "family", "month"],
                dropna=False,
            ):
                score_kind, quantile_scope, family, month = keys
                for score_quantile in score_quantiles:
                    for side_gap_quantile in side_gap_quantiles:
                        for rank_quantile in rank_quantiles:
                            rows.append(
                                {
                                    "score_kind": score_kind,
                                    "quantile_scope": quantile_scope,
                                    "family": family,
                                    "month": month,
                                    **summarize_quantile_gate_group(
                                        group,
                                        score_quantile=score_quantile,
                                        side_gap_quantile=side_gap_quantile,
                                        rank_quantile=rank_quantile,
                                        min_scope_rows=min_scope_rows,
                                    ),
                                }
                            )
    return pd.DataFrame(rows).sort_values(
        [
            "score_kind",
            "quantile_scope",
            "family",
            "month",
            "score_quantile",
            "side_gap_quantile",
            "rank_quantile",
        ]
    ).reset_index(drop=True)


def aggregate_family_quantile_gate_summary(monthly: pd.DataFrame) -> pd.DataFrame:
    group_columns = [
        "score_kind",
        "quantile_scope",
        "family",
        "score_quantile",
        "side_gap_quantile",
        "rank_quantile",
        "min_scope_rows",
    ]
    rows: list[dict[str, object]] = []
    for keys, group in monthly.groupby(group_columns, dropna=False):
        enter_count = int(group["quantile_enter_count"].sum())
        valid_count = int(group["valid_count"].sum())
        supported_count = int(group["scope_supported_count"].sum())
        rows.append(
            {
                **dict(zip(group_columns, keys, strict=True)),
                "months": ",".join(sorted(group["month"].astype(str).unique())),
                "month_count": int(group["month"].nunique()),
                "valid_count": valid_count,
                "scope_supported_count": supported_count,
                "quantile_enter_count": enter_count,
                "quantile_long_enter_count": int(
                    group["quantile_long_enter_count"].sum()
                ),
                "quantile_short_enter_count": int(
                    group["quantile_short_enter_count"].sum()
                ),
                "quantile_enter_share": float(enter_count / valid_count)
                if valid_count
                else 0.0,
                "scope_supported_share": float(supported_count / valid_count)
                if valid_count
                else 0.0,
                "active_months": int((group["quantile_enter_count"] > 0).sum()),
                "min_monthly_enter_count": int(group["quantile_enter_count"].min()),
                "max_monthly_enter_count": int(group["quantile_enter_count"].max()),
            }
        )
    return pd.DataFrame(rows).sort_values(
        [
            "score_kind",
            "quantile_scope",
            "family",
            "score_quantile",
            "side_gap_quantile",
            "rank_quantile",
        ]
    ).reset_index(drop=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--family-predictions", action="append", required=True)
    parser.add_argument("--score-quantiles", default="0.9,0.95,0.99")
    parser.add_argument("--side-gap-quantiles", default="0,0.9,0.95")
    parser.add_argument("--rank-quantiles", default="0,0.9")
    parser.add_argument(
        "--quantile-scopes",
        default="month,side_month,side_regime_session_month",
    )
    parser.add_argument("--min-scope-rows", type=int, default=20)
    parser.add_argument("--long-rank-column", default="pred_long_entry_local_rank")
    parser.add_argument("--short-rank-column", default="pred_short_entry_local_rank")
    parser.add_argument("--label", default="entry_ev_scale_quantile_diagnostics")
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    families = parse_family_predictions(args.family_predictions)
    score_frames: list[pd.DataFrame] = []
    for family, path in families.items():
        raw = pd.read_parquet(path)
        for score_kind, (long_column, short_column) in SCORE_DEFINITIONS.items():
            score_frames.append(
                build_score_frame(
                    raw,
                    family=family,
                    score_kind=score_kind,
                    long_score_column=long_column,
                    short_score_column=short_column,
                    long_rank_column=args.long_rank_column,
                    short_rank_column=args.short_rank_column,
                )
            )

    base_distribution, group_distribution = build_distribution_summary(score_frames)
    monthly_quantile = build_monthly_quantile_gate_summary(
        score_frames,
        quantile_scopes=parse_scope_csv(args.quantile_scopes),
        score_quantiles=parse_float_csv(args.score_quantiles),
        side_gap_quantiles=parse_float_csv(args.side_gap_quantiles),
        rank_quantiles=parse_float_csv(args.rank_quantiles),
        min_scope_rows=args.min_scope_rows,
    )
    family_quantile = aggregate_family_quantile_gate_summary(monthly_quantile)

    run_dir = make_run_dir(args.output_dir, args.label)
    base_distribution.to_csv(run_dir / "score_distribution_summary.csv", index=False)
    group_distribution.to_csv(run_dir / "group_distribution_summary.csv", index=False)
    monthly_quantile.to_csv(run_dir / "monthly_quantile_gate_summary.csv", index=False)
    family_quantile.to_csv(run_dir / "family_quantile_gate_summary.csv", index=False)
    manifest = {
        "mode": "entry_ev_scale_quantile_diagnostics",
        "families": {family: str(path) for family, path in families.items()},
        "score_definitions": SCORE_DEFINITIONS,
        "score_quantiles": parse_float_csv(args.score_quantiles),
        "side_gap_quantiles": parse_float_csv(args.side_gap_quantiles),
        "rank_quantiles": parse_float_csv(args.rank_quantiles),
        "quantile_scopes": parse_scope_csv(args.quantile_scopes),
        "min_scope_rows": args.min_scope_rows,
        "long_rank_column": args.long_rank_column,
        "short_rank_column": args.short_rank_column,
    }
    (run_dir / "diagnostics.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, default=local_json_default)
        + "\n",
        encoding="utf-8",
    )

    print(f"artifacts: {run_dir}")
    print(base_distribution[BASE_PRINT_COLUMNS].to_string(index=False))
    print(family_quantile[GATE_PRINT_COLUMNS].head(40).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
