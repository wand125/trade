from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable, Sequence

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression

from trade_data.next_bar import context_diagnostics, evaluate_probabilities
from trade_data.next_bar_overlay import read_prediction_sets


META_CONFIDENCE_THRESHOLDS = (
    0.50,
    0.505,
    0.51,
    0.515,
    0.52,
    0.53,
    0.54,
    0.55,
    0.60,
)


@dataclass(frozen=True)
class CrossTimeframeMetaConfig:
    target_timeframe: int = 15
    context_timeframes: tuple[int, ...] = (5, 1)
    asof_context_timeframes: tuple[int, ...] = ()
    asof_max_age_minutes: int = 15
    regularization_c: float = 0.10
    meta_weight: float = 0.25
    random_seed: int = 42


def _logit(values: pd.Series) -> np.ndarray:
    probability = np.clip(values.to_numpy(dtype="float64"), 1e-6, 1 - 1e-6)
    return np.log(probability / (1 - probability))


def build_cross_timeframe_frame(
    target: pd.DataFrame,
    contexts: dict[int, pd.DataFrame],
    config: CrossTimeframeMetaConfig,
) -> tuple[pd.DataFrame, list[str]]:
    required = {
        "decision_timestamp",
        "target_timestamp",
        "target_up",
        "probability_up",
        "fold",
    }
    missing = sorted(required - set(target.columns))
    if missing:
        raise ValueError(f"target predictions are missing: {', '.join(missing)}")
    frame = target.copy()
    frame["decision_timestamp"] = pd.to_datetime(frame["decision_timestamp"], utc=True)
    frame = frame.rename(columns={"probability_up": "target_probability_up"})
    feature_columns = [f"logit_m{config.target_timeframe}"]
    frame[feature_columns[0]] = _logit(frame["target_probability_up"])
    overlap = set(config.context_timeframes) & set(config.asof_context_timeframes)
    if overlap:
        joined = ", ".join(f"M{value}" for value in sorted(overlap))
        raise ValueError(f"context timeframes cannot be both exact and as-of: {joined}")
    all_context_timeframes = (
        *config.context_timeframes,
        *config.asof_context_timeframes,
    )
    if len(set(all_context_timeframes)) != len(all_context_timeframes):
        raise ValueError("context timeframes must not contain duplicates")
    if config.target_timeframe in all_context_timeframes:
        raise ValueError("target timeframe cannot also be a context timeframe")
    if config.asof_max_age_minutes < 0:
        raise ValueError("asof_max_age_minutes must not be negative")
    for timeframe in config.context_timeframes:
        if timeframe not in contexts:
            raise ValueError(f"missing M{timeframe} context predictions")
        context = contexts[timeframe].copy()
        context["decision_timestamp"] = pd.to_datetime(
            context["decision_timestamp"], utc=True
        )
        if context["decision_timestamp"].duplicated().any():
            raise ValueError(f"M{timeframe} context contains duplicate decision timestamps")
        probability_column = f"m{timeframe}_probability_up"
        frame = frame.merge(
            context[["decision_timestamp", "probability_up"]].rename(
                columns={"probability_up": probability_column}
            ),
            on="decision_timestamp",
            how="inner",
            validate="one_to_one",
        )
        feature = f"logit_m{timeframe}"
        frame[feature] = _logit(frame[probability_column])
        feature_columns.append(feature)
    for timeframe in config.asof_context_timeframes:
        if timeframe not in contexts:
            raise ValueError(f"missing M{timeframe} as-of context predictions")
        context = contexts[timeframe].copy()
        context["decision_timestamp"] = pd.to_datetime(
            context["decision_timestamp"], utc=True
        )
        if context["decision_timestamp"].duplicated().any():
            raise ValueError(f"M{timeframe} context contains duplicate decision timestamps")
        probability_column = f"m{timeframe}_probability_up"
        timestamp_column = f"m{timeframe}_decision_timestamp"
        right = context[["decision_timestamp", "probability_up"]].rename(
            columns={
                "decision_timestamp": timestamp_column,
                "probability_up": probability_column,
            }
        )
        frame = pd.merge_asof(
            frame.sort_values("decision_timestamp"),
            right.sort_values(timestamp_column),
            left_on="decision_timestamp",
            right_on=timestamp_column,
            direction="backward",
            tolerance=pd.Timedelta(minutes=config.asof_max_age_minutes),
        )
        frame = frame.dropna(subset=[probability_column, timestamp_column]).copy()
        age_minutes = (
            frame["decision_timestamp"] - frame[timestamp_column]
        ) / pd.Timedelta(minutes=1)
        if age_minutes.lt(0).any():
            raise ValueError(f"M{timeframe} as-of context contains a future prediction")
        frame[f"m{timeframe}_prediction_age_minutes"] = age_minutes.astype("float64")
        feature = f"logit_m{timeframe}"
        frame[feature] = _logit(frame[probability_column])
        feature_columns.append(feature)
    return frame.sort_values("decision_timestamp").reset_index(drop=True), feature_columns


def apply_meta_blend(
    frame: pd.DataFrame,
    meta_probability: np.ndarray,
    meta_weight: float,
) -> pd.DataFrame:
    if not 0 <= meta_weight <= 1:
        raise ValueError("meta_weight must be between 0 and 1")
    output = frame.copy()
    output["meta_probability_up"] = np.asarray(meta_probability, dtype="float64")
    output["probability_up"] = (
        (1 - meta_weight) * output["target_probability_up"]
        + meta_weight * output["meta_probability_up"]
    )
    output["predicted_up"] = output["probability_up"].ge(0.5).astype("int8")
    output["predicted_direction"] = np.where(
        output["predicted_up"].eq(1), "up", "down"
    )
    output["confidence"] = np.maximum(
        output["probability_up"], 1 - output["probability_up"]
    )
    output["correct"] = output["predicted_up"].eq(output["target_up"].astype("int8"))
    output["meta_weight"] = meta_weight
    return output


def _metric_set(frame: pd.DataFrame, probability_column: str) -> dict[str, object]:
    return evaluate_probabilities(
        frame["target_up"].to_numpy(dtype="int8"),
        frame[probability_column].to_numpy(dtype="float64"),
        thresholds=META_CONFIDENCE_THRESHOLDS,
    )


def resolve_prediction_sources(
    prediction_dirs: Sequence[Path],
    target_prediction_dirs: Sequence[Path],
    context_prediction_dirs: Sequence[Path],
) -> tuple[tuple[Path, ...], tuple[Path, ...]]:
    """Resolve legacy shared sources or explicit target/context sources."""
    legacy = tuple(prediction_dirs)
    target = tuple(target_prediction_dirs)
    context = tuple(context_prediction_dirs)
    if legacy and (target or context):
        raise ValueError(
            "--predictions-dir cannot be combined with explicit target/context sources"
        )
    if legacy:
        return legacy, legacy
    if not target or not context:
        raise ValueError(
            "provide --predictions-dir, or both --target-predictions-dir and "
            "--context-predictions-dir"
        )
    return target, context


def run_cross_timeframe_meta(
    prediction_dirs: Sequence[Path],
    output_dir: Path,
    config: CrossTimeframeMetaConfig,
    *,
    target_prediction_dirs: Sequence[Path] = (),
    context_prediction_dirs: Sequence[Path] = (),
) -> dict[str, object]:
    target_dirs, context_dirs = resolve_prediction_sources(
        prediction_dirs,
        target_prediction_dirs,
        context_prediction_dirs,
    )
    target = read_prediction_sets(target_dirs, config.target_timeframe)
    all_context_timeframes = (
        *config.context_timeframes,
        *config.asof_context_timeframes,
    )
    contexts = {
        timeframe: read_prediction_sets(context_dirs, timeframe)
        for timeframe in all_context_timeframes
    }
    frame, feature_columns = build_cross_timeframe_frame(target, contexts, config)
    fold_order = [
        str(fold)
        for fold in frame.groupby("fold", sort=False)["decision_timestamp"].min().sort_values().index
    ]
    output_dir.mkdir(parents=True, exist_ok=True)
    predictions = []
    fold_reports = []
    model_entries = []
    for position in range(1, len(fold_order)):
        train_folds = fold_order[:position]
        test_fold = fold_order[position]
        train = frame.loc[frame["fold"].astype(str).isin(train_folds)]
        test = frame.loc[frame["fold"].astype(str).eq(test_fold)]
        model = LogisticRegression(
            C=config.regularization_c,
            max_iter=1_000,
            random_state=config.random_seed,
        )
        model.fit(train[feature_columns], train["target_up"].astype("int8"))
        meta_probability = model.predict_proba(test[feature_columns])[:, 1]
        predicted = apply_meta_blend(test, meta_probability, config.meta_weight)
        baseline_metrics = _metric_set(predicted, "target_probability_up")
        meta_metrics = _metric_set(predicted, "meta_probability_up")
        blend_metrics = _metric_set(predicted, "probability_up")
        fold_reports.append(
            {
                "test_fold": test_fold,
                "train_folds": train_folds,
                "rows": len(predicted),
                "baseline": baseline_metrics,
                "meta": meta_metrics,
                "blend": blend_metrics,
                "blend_accuracy_delta": blend_metrics["accuracy"]
                - baseline_metrics["accuracy"],
                "coefficients": {
                    feature: float(value)
                    for feature, value in zip(
                        feature_columns, model.coef_[0], strict=True
                    )
                },
                "intercept": float(model.intercept_[0]),
            }
        )
        model_name = f"m{config.target_timeframe}_{test_fold}_cross_tf_meta.joblib"
        joblib.dump(
            {
                "model": model,
                "config": asdict(config),
                "feature_columns": feature_columns,
                "train_folds": train_folds,
                "test_fold": test_fold,
            },
            output_dir / model_name,
        )
        predicted["meta_test_fold"] = test_fold
        predictions.append(predicted)
        model_entries.append({"test_fold": test_fold, "model": model_name})
    if not predictions:
        raise ValueError("cross-timeframe meta model requires at least two folds")
    combined = pd.concat(predictions, ignore_index=True)
    baseline_metrics = _metric_set(combined, "target_probability_up")
    meta_metrics = _metric_set(combined, "meta_probability_up")
    blend_metrics = _metric_set(combined, "probability_up")
    name = f"M{config.target_timeframe}"
    resolved_sources = tuple(dict.fromkeys((*target_dirs, *context_dirs)))
    report = {
        "created_at": datetime.now(UTC).isoformat(),
        "config": asdict(config),
        "source_predictions": [str(path) for path in resolved_sources],
        "target_source_predictions": [str(path) for path in target_dirs],
        "context_source_predictions": [str(path) for path in context_dirs],
        "timeframes": {
            name: {
                "rows": len(combined),
                "baseline": baseline_metrics,
                "meta": meta_metrics,
                "blend": blend_metrics,
                "blend_accuracy_delta": blend_metrics["accuracy"]
                - baseline_metrics["accuracy"],
                "blend_balanced_accuracy_delta": blend_metrics["balanced_accuracy"]
                - baseline_metrics["balanced_accuracy"],
                "improved_folds": int(
                    sum(row["blend_accuracy_delta"] > 0 for row in fold_reports)
                ),
                "folds": fold_reports,
                "context_diagnostics": context_diagnostics(combined),
            }
        },
    }
    prediction_name = f"m{config.target_timeframe}_cross_tf_meta_predictions.parquet"
    combined.to_parquet(output_dir / prediction_name, index=False)
    final_model = LogisticRegression(
        C=config.regularization_c,
        max_iter=1_000,
        random_state=config.random_seed,
    )
    final_model.fit(frame[feature_columns], frame["target_up"].astype("int8"))
    final_model_name = f"m{config.target_timeframe}_cross_tf_meta_final.joblib"
    joblib.dump(
        {
            "model": final_model,
            "config": asdict(config),
            "feature_columns": feature_columns,
            "train_folds": fold_order,
            "deployment_status": "forward_candidate",
        },
        output_dir / final_model_name,
    )
    first_manifest = json.loads(
        (target_dirs[0] / "manifest.json").read_text(encoding="utf-8")
    )
    base_entry = first_manifest["timeframes"][name]
    manifest = {
        "format_version": 1,
        "created_at": report["created_at"],
        "kind": "next_bar_cross_timeframe_meta",
        "timeframes": {
            name: {
                "minutes": config.target_timeframe,
                "features": list(base_entry["features"]),
                "meta_features": feature_columns,
                "models": model_entries,
                "deployment_model": final_model_name,
                "predictions": prediction_name,
            }
        },
    }
    (output_dir / "meta_metrics.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Train a chronological target direction meta model from multi-timeframe OOS probabilities."
    )
    parser.add_argument("--predictions-dir", type=Path, action="append", default=[])
    parser.add_argument(
        "--target-predictions-dir",
        type=Path,
        action="append",
        default=[],
        help="M15 target-model OOS directories when target and context are stored separately.",
    )
    parser.add_argument(
        "--context-predictions-dir",
        type=Path,
        action="append",
        default=[],
        help="M1/M5/M30 context-model OOS directories when stored separately.",
    )
    parser.add_argument("--target-timeframe", type=int, default=15)
    parser.add_argument(
        "--context-timeframes",
        default="5,1",
        help="Comma-separated context timeframes joined at the exact target decision timestamp.",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--regularization-c", type=float, default=0.10)
    parser.add_argument("--meta-weight", type=float, default=0.25)
    parser.add_argument(
        "--asof-context-timeframes",
        default="",
        help="Comma-separated context timeframes joined from the latest prediction at or before the target decision.",
    )
    parser.add_argument("--asof-max-age-minutes", type=int, default=15)
    return parser


def _parse_timeframes(value: str) -> tuple[int, ...]:
    if not value.strip():
        return ()
    values = tuple(int(item.strip()) for item in value.split(",") if item.strip())
    if any(item <= 0 for item in values):
        raise ValueError("timeframes must be positive integers")
    if len(set(values)) != len(values):
        raise ValueError("timeframes must not contain duplicates")
    return values


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    report = run_cross_timeframe_meta(
        args.predictions_dir,
        args.output_dir,
        CrossTimeframeMetaConfig(
            target_timeframe=args.target_timeframe,
            context_timeframes=_parse_timeframes(args.context_timeframes),
            asof_context_timeframes=_parse_timeframes(
                args.asof_context_timeframes
            ),
            asof_max_age_minutes=args.asof_max_age_minutes,
            regularization_c=args.regularization_c,
            meta_weight=args.meta_weight,
        ),
        target_prediction_dirs=args.target_predictions_dir,
        context_prediction_dirs=args.context_predictions_dir,
    )
    print(json.dumps(report["timeframes"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
