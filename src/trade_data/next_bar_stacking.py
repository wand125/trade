from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable, Mapping, Sequence

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from trade_data.next_bar import context_diagnostics, evaluate_probabilities
from trade_data.next_bar_registry import read_prediction_sets


@dataclass(frozen=True)
class ChronologicalStackingConfig:
    timeframe: int = 15
    regularization_c: float = 0.10
    stack_weight: float = 0.25
    preserve_baseline_direction: bool = False
    random_seed: int = 42


def _logit(values: pd.Series) -> np.ndarray:
    probability = np.clip(values.to_numpy(dtype="float64"), 1e-6, 1 - 1e-6)
    return np.log(probability / (1 - probability))


def build_stacking_frame(
    baseline: pd.DataFrame, experts: Mapping[str, pd.DataFrame]
) -> tuple[pd.DataFrame, list[str]]:
    if not experts:
        raise ValueError("chronological stacking requires at least one expert")
    keys = ["fold", "timestamp"]
    alignment_columns = [
        *keys,
        "decision_timestamp",
        "target_timestamp",
        "target_up",
    ]
    missing = sorted(
        {*alignment_columns, "probability_up"} - set(baseline.columns)
    )
    if missing:
        raise ValueError(f"baseline predictions are missing: {', '.join(missing)}")
    if baseline.duplicated(keys).any():
        raise ValueError("baseline predictions contain duplicate fold/timestamp rows")
    frame = baseline.copy()
    frame["baseline_probability_up"] = frame["probability_up"].astype("float64")
    feature_columns = ["logit_baseline"]
    frame[feature_columns[0]] = _logit(frame["baseline_probability_up"])
    for name, expert in experts.items():
        if not name or not name.replace("_", "").isalnum():
            raise ValueError(f"invalid expert name: {name!r}")
        missing = sorted(
            {*alignment_columns, "probability_up"} - set(expert.columns)
        )
        if missing:
            raise ValueError(
                f"{name} predictions are missing: {', '.join(missing)}"
            )
        if expert.duplicated(keys).any():
            raise ValueError(
                f"{name} predictions contain duplicate fold/timestamp rows"
            )
        renamed = {
            column: f"{name}_{column}" for column in alignment_columns[2:]
        }
        renamed["probability_up"] = f"{name}_probability_up"
        columns = [*alignment_columns, "probability_up"]
        frame = frame.merge(
            expert[columns].rename(columns=renamed),
            on=keys,
            how="inner",
            validate="one_to_one",
        )
        if len(frame) != len(baseline) or len(expert) != len(baseline):
            raise ValueError(
                f"{name} predictions do not contain identical fold/timestamp rows"
            )
        for baseline_column in alignment_columns[2:]:
            expert_column = renamed[baseline_column]
            if not frame[baseline_column].astype(str).equals(
                frame[expert_column].astype(str)
            ):
                raise ValueError(f"{name} source mismatch: {baseline_column}")
            frame = frame.drop(columns=expert_column)
        feature = f"logit_{name}"
        frame[feature] = _logit(frame[f"{name}_probability_up"])
        feature_columns.append(feature)
    return frame, feature_columns


def _new_model(config: ChronologicalStackingConfig) -> Pipeline:
    if config.regularization_c <= 0:
        raise ValueError("regularization_c must be positive")
    return Pipeline(
        [
            ("scale", StandardScaler()),
            (
                "logistic",
                LogisticRegression(
                    C=config.regularization_c,
                    max_iter=1_000,
                    random_state=config.random_seed,
                ),
            ),
        ]
    )


def apply_stacking_blend(
    frame: pd.DataFrame,
    stack_probability: np.ndarray,
    config: ChronologicalStackingConfig,
) -> pd.DataFrame:
    if not 0 <= config.stack_weight <= 1:
        raise ValueError("stack_weight must be between 0 and 1")
    output = frame.copy()
    output["stack_probability_up"] = np.asarray(
        stack_probability, dtype="float64"
    )
    blended = (
        (1 - config.stack_weight) * output["baseline_probability_up"]
        + config.stack_weight * output["stack_probability_up"]
    )
    if config.preserve_baseline_direction:
        baseline_sign = np.where(
            output["baseline_probability_up"].ge(0.5), 1.0, -1.0
        )
        aligned_edge = baseline_sign * (blended - 0.5)
        blended = 0.5 + baseline_sign * np.maximum(
            aligned_edge, np.finfo("float64").eps
        )
    output["probability_up"] = blended
    output["predicted_up"] = output["probability_up"].ge(0.5).astype("int8")
    output["predicted_direction"] = np.where(
        output["predicted_up"].eq(1), "up", "down"
    )
    output["confidence"] = np.maximum(
        output["probability_up"], 1 - output["probability_up"]
    )
    output["correct"] = output["predicted_up"].eq(
        output["target_up"].astype("int8")
    )
    output["stack_weight"] = config.stack_weight
    output["stack_preserve_baseline_direction"] = (
        config.preserve_baseline_direction
    )
    return output


def chronological_stack_predictions(
    frame: pd.DataFrame,
    feature_columns: Sequence[str],
    config: ChronologicalStackingConfig,
) -> tuple[pd.DataFrame, list[dict[str, object]], list[dict[str, object]]]:
    if not feature_columns:
        raise ValueError("feature_columns must not be empty")
    fold_order = [
        str(fold)
        for fold in frame.groupby("fold", sort=False)["decision_timestamp"]
        .min()
        .sort_values()
        .index
    ]
    if len(fold_order) < 2:
        raise ValueError("chronological stacking requires at least two folds")
    predictions: list[pd.DataFrame] = []
    reports: list[dict[str, object]] = []
    models: list[dict[str, object]] = []
    for position, test_fold in enumerate(fold_order):
        test = frame.loc[frame["fold"].astype(str).eq(test_fold)].copy()
        train_folds = fold_order[:position]
        if not train_folds:
            stack_probability = test["baseline_probability_up"].to_numpy(
                dtype="float64"
            )
            model = None
            coefficients = None
            intercept = None
            mode = "baseline_fallback_no_prior_oos"
        else:
            train = frame.loc[frame["fold"].astype(str).isin(train_folds)]
            model = _new_model(config)
            model.fit(train[list(feature_columns)], train["target_up"].astype("int8"))
            stack_probability = model.predict_proba(test[list(feature_columns)])[:, 1]
            logistic = model.named_steps["logistic"]
            coefficients = {
                feature: float(value)
                for feature, value in zip(
                    feature_columns, logistic.coef_[0], strict=True
                )
            }
            intercept = float(logistic.intercept_[0])
            mode = "prior_oos_logistic"
        predicted = apply_stacking_blend(test, stack_probability, config)
        baseline_metrics = evaluate_probabilities(
            predicted["target_up"].to_numpy(dtype="int8"),
            predicted["baseline_probability_up"].to_numpy(dtype="float64"),
        )
        stack_metrics = evaluate_probabilities(
            predicted["target_up"].to_numpy(dtype="int8"),
            predicted["stack_probability_up"].to_numpy(dtype="float64"),
        )
        blend_metrics = evaluate_probabilities(
            predicted["target_up"].to_numpy(dtype="int8"),
            predicted["probability_up"].to_numpy(dtype="float64"),
        )
        reports.append(
            {
                "test_fold": test_fold,
                "train_folds": train_folds,
                "mode": mode,
                "rows": len(predicted),
                "baseline": baseline_metrics,
                "stack": stack_metrics,
                "blend": blend_metrics,
                "blend_accuracy_delta": (
                    blend_metrics["accuracy"] - baseline_metrics["accuracy"]
                ),
                "coefficients_scaled_features": coefficients,
                "intercept": intercept,
            }
        )
        predicted["stack_test_fold"] = test_fold
        predicted["stack_train_fold_count"] = len(train_folds)
        predictions.append(predicted)
        models.append(
            {
                "test_fold": test_fold,
                "train_folds": train_folds,
                "model": model,
            }
        )
    combined = pd.concat(predictions, ignore_index=True)
    return combined, reports, models


def run_chronological_stacking(
    baseline_dirs: Sequence[Path],
    expert_dirs: Mapping[str, Path],
    output_dir: Path,
    config: ChronologicalStackingConfig,
) -> dict[str, object]:
    baseline = read_prediction_sets(baseline_dirs, config.timeframe)
    experts = {
        name: read_prediction_sets([directory], config.timeframe)
        for name, directory in expert_dirs.items()
    }
    frame, feature_columns = build_stacking_frame(baseline, experts)
    combined, fold_reports, models = chronological_stack_predictions(
        frame, feature_columns, config
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    model_entries = []
    for entry in models:
        if entry["model"] is None:
            model_entries.append(
                {
                    "test_fold": entry["test_fold"],
                    "train_folds": entry["train_folds"],
                    "model": None,
                }
            )
            continue
        model_name = f"m{config.timeframe}_{entry['test_fold']}_stack.joblib"
        joblib.dump(
            {
                "model": entry["model"],
                "config": asdict(config),
                "feature_columns": list(feature_columns),
                "expert_names": list(expert_dirs),
                "train_folds": entry["train_folds"],
                "test_fold": entry["test_fold"],
            },
            output_dir / model_name,
        )
        model_entries.append(
            {
                "test_fold": entry["test_fold"],
                "train_folds": entry["train_folds"],
                "model": model_name,
            }
        )
    final_model = _new_model(config)
    final_model.fit(frame[list(feature_columns)], frame["target_up"].astype("int8"))
    final_model_name = f"m{config.timeframe}_stack_research_final.joblib"
    joblib.dump(
        {
            "model": final_model,
            "config": asdict(config),
            "feature_columns": list(feature_columns),
            "expert_names": list(expert_dirs),
            "train_folds": [str(fold) for fold in frame["fold"].drop_duplicates()],
            "deployment_status": "research_only",
        },
        output_dir / final_model_name,
    )
    aggregate = {
        "baseline": evaluate_probabilities(
            combined["target_up"].to_numpy(dtype="int8"),
            combined["baseline_probability_up"].to_numpy(dtype="float64"),
        ),
        "stack": evaluate_probabilities(
            combined["target_up"].to_numpy(dtype="int8"),
            combined["stack_probability_up"].to_numpy(dtype="float64"),
        ),
        "blend": evaluate_probabilities(
            combined["target_up"].to_numpy(dtype="int8"),
            combined["probability_up"].to_numpy(dtype="float64"),
        ),
    }
    created_at = datetime.now(UTC).isoformat()
    report = {
        "created_at": created_at,
        "config": asdict(config),
        "baseline_dirs": [str(path) for path in baseline_dirs],
        "expert_dirs": {name: str(path) for name, path in expert_dirs.items()},
        "feature_columns": list(feature_columns),
        "rows": len(combined),
        "aggregate": aggregate,
        "improved_folds": int(
            sum(row["blend_accuracy_delta"] > 0 for row in fold_reports)
        ),
        "folds": fold_reports,
        "context_diagnostics": context_diagnostics(combined),
    }
    prediction_name = f"m{config.timeframe}_walk_forward_predictions.parquet"
    combined.to_parquet(output_dir / prediction_name, index=False)
    first_manifest = json.loads(
        (baseline_dirs[0] / "manifest.json").read_text(encoding="utf-8")
    )
    name = f"M{config.timeframe}"
    base_entry = first_manifest["timeframes"][name]
    manifest = {
        "format_version": 1,
        "created_at": created_at,
        "kind": "next_bar_chronological_expert_stacking",
        "timeframes": {
            name: {
                "minutes": config.timeframe,
                "features": list(base_entry["features"]),
                "stack_features": list(feature_columns),
                "models": model_entries,
                "research_final_model": final_model_name,
                "predictions": prediction_name,
            }
        },
    }
    (output_dir / "stacking_metrics.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return report


def parse_expert(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("expert must use NAME=PATH")
    name, path = value.split("=", 1)
    name = name.strip()
    path = path.strip()
    if not name or not path:
        raise argparse.ArgumentTypeError("expert must use non-empty NAME=PATH")
    return name, Path(path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Learn expert probability weights from prior OOS folds only."
    )
    parser.add_argument("--baseline-dir", type=Path, action="append", required=True)
    parser.add_argument("--expert", type=parse_expert, action="append", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--timeframe", type=int, default=15)
    parser.add_argument("--regularization-c", type=float, default=0.10)
    parser.add_argument("--stack-weight", type=float, default=0.25)
    parser.add_argument("--preserve-baseline-direction", action="store_true")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    expert_dirs = dict(args.expert)
    if len(expert_dirs) != len(args.expert):
        raise ValueError("expert names must be unique")
    report = run_chronological_stacking(
        baseline_dirs=args.baseline_dir,
        expert_dirs=expert_dirs,
        output_dir=args.output_dir,
        config=ChronologicalStackingConfig(
            timeframe=args.timeframe,
            regularization_c=args.regularization_c,
            stack_weight=args.stack_weight,
            preserve_baseline_direction=args.preserve_baseline_direction,
        ),
    )
    print(
        json.dumps(
            {
                "rows": report["rows"],
                "aggregate": report["aggregate"],
                "improved_folds": report["improved_folds"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
