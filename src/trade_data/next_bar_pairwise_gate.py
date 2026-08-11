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
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from trade_data.next_bar import context_diagnostics, evaluate_probabilities
from trade_data.next_bar_registry import read_prediction_sets


@dataclass(frozen=True)
class PairwiseCorrectnessGateConfig:
    timeframe: int = 1
    regularization_c: float = 0.10
    random_seed: int = 42


PAIRWISE_GATE_FEATURES = (
    "logit_baseline",
    "logit_path_candidate",
    "logit_shift_candidate",
    "path_blend_edge",
    "shift_blend_edge",
    "signed_candidate_gap",
    "path_predicted_up_feature",
    "volatility_20_feature",
    "minute_sin",
    "minute_cos",
    "weekday_sin",
    "weekday_cos",
    "regime_low",
    "regime_normal",
    "regime_high",
)


def _logit(values: pd.Series) -> np.ndarray:
    probability = np.clip(values.to_numpy(dtype="float64"), 1e-6, 1 - 1e-6)
    return np.log(probability / (1 - probability))


def build_pairwise_gate_frame(
    path_predictions: pd.DataFrame, shift_predictions: pd.DataFrame
) -> pd.DataFrame:
    keys = ["fold", "timestamp"]
    alignment_columns = [
        "decision_timestamp",
        "target_timestamp",
        "target_up",
        "baseline_probability_up",
        "volatility_regime",
        "volatility_20",
    ]
    source_columns = [
        *keys,
        *alignment_columns,
        "next_bar_body",
        "body_ratio",
        "probability_up",
        "candidate_probability_up",
        "predicted_up",
    ]
    required = set(source_columns)
    for name, predictions in (
        ("path", path_predictions),
        ("shift", shift_predictions),
    ):
        missing = sorted(required - set(predictions.columns))
        if missing:
            raise ValueError(f"{name} predictions are missing: {', '.join(missing)}")
        if predictions.duplicated(keys).any():
            raise ValueError(
                f"{name} predictions contain duplicate fold/timestamp rows"
            )

    path = path_predictions[source_columns].copy().rename(
        columns={
            "probability_up": "path_probability_up",
            "candidate_probability_up": "path_candidate_probability_up",
            "predicted_up": "path_predicted_up",
        }
    )
    shift_columns = [
        *keys,
        *alignment_columns,
        "probability_up",
        "candidate_probability_up",
        "predicted_up",
    ]
    renamed_alignment = {
        column: f"shift_{column}" for column in alignment_columns
    }
    shift = shift_predictions[shift_columns].copy().rename(
        columns={
            **renamed_alignment,
            "probability_up": "shift_probability_up",
            "candidate_probability_up": "shift_candidate_probability_up",
            "predicted_up": "shift_predicted_up",
        }
    )
    frame = path.merge(shift, on=keys, how="inner", validate="one_to_one")
    if len(frame) != len(path_predictions) or len(frame) != len(shift_predictions):
        raise ValueError("path and shift predictions do not contain identical rows")

    for column in alignment_columns:
        other = f"shift_{column}"
        if pd.api.types.is_numeric_dtype(frame[column]):
            aligned = np.allclose(
                frame[column].to_numpy(dtype="float64"),
                frame[other].to_numpy(dtype="float64"),
                equal_nan=True,
            )
        else:
            aligned = frame[column].astype(str).equals(frame[other].astype(str))
        if not aligned:
            raise ValueError(f"shift source mismatch: {column}")
        frame = frame.drop(columns=other)

    decision = pd.to_datetime(frame["decision_timestamp"], utc=True)
    minute = decision.dt.hour.to_numpy(dtype="float64") * 60 + decision.dt.minute
    weekday = decision.dt.dayofweek.to_numpy(dtype="float64")
    frame["logit_baseline"] = _logit(frame["baseline_probability_up"])
    frame["logit_path_candidate"] = _logit(
        frame["path_candidate_probability_up"]
    )
    frame["logit_shift_candidate"] = _logit(
        frame["shift_candidate_probability_up"]
    )
    frame["path_blend_edge"] = np.abs(frame["path_probability_up"] - 0.5)
    frame["shift_blend_edge"] = np.abs(frame["shift_probability_up"] - 0.5)
    frame["signed_candidate_gap"] = (
        frame["path_candidate_probability_up"]
        - frame["shift_candidate_probability_up"]
    )
    frame["path_predicted_up_feature"] = frame["path_predicted_up"].astype(
        "float64"
    )
    frame["volatility_20_feature"] = frame["volatility_20"].astype("float64")
    frame["minute_sin"] = np.sin(2 * np.pi * minute / (24 * 60))
    frame["minute_cos"] = np.cos(2 * np.pi * minute / (24 * 60))
    frame["weekday_sin"] = np.sin(2 * np.pi * weekday / 7)
    frame["weekday_cos"] = np.cos(2 * np.pi * weekday / 7)
    regime = frame["volatility_regime"].astype(str)
    for name in ("low", "normal", "high"):
        frame[f"regime_{name}"] = regime.eq(name).astype("float64")
    frame["experts_disagree"] = frame["path_predicted_up"].ne(
        frame["shift_predicted_up"]
    )
    frame["path_correct"] = frame["path_predicted_up"].eq(
        frame["target_up"].astype("int8")
    )
    if not np.isfinite(frame[list(PAIRWISE_GATE_FEATURES)].to_numpy()).all():
        raise ValueError("pairwise gate features must be finite")
    return frame


def _new_model(config: PairwiseCorrectnessGateConfig) -> Pipeline:
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


def _apply_gate(
    test: pd.DataFrame,
    gate_probability_path_correct: np.ndarray,
    mode: str,
) -> pd.DataFrame:
    output = test.copy()
    output["gate_probability_path_correct"] = np.asarray(
        gate_probability_path_correct, dtype="float64"
    )
    choose_path = (~output["experts_disagree"]) | output[
        "gate_probability_path_correct"
    ].ge(0.5)
    output["gate_selected_candidate"] = np.where(choose_path, "path", "shift")
    output["probability_up"] = np.where(
        choose_path,
        output["path_probability_up"],
        output["shift_probability_up"],
    )
    output["probability_down"] = 1 - output["probability_up"]
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
    output["pairwise_gate_mode"] = mode
    return output


def _probability_metrics(frame: pd.DataFrame, column: str) -> dict[str, float | int]:
    return evaluate_probabilities(
        frame["target_up"].to_numpy(dtype="int8"),
        frame[column].to_numpy(dtype="float64"),
    )


def chronological_pairwise_gate_predictions(
    frame: pd.DataFrame,
    config: PairwiseCorrectnessGateConfig,
) -> tuple[pd.DataFrame, list[dict[str, object]], list[dict[str, object]]]:
    fold_order = [
        str(fold)
        for fold in frame.groupby("fold", sort=False)["decision_timestamp"]
        .min()
        .sort_values()
        .index
    ]
    if len(fold_order) < 2:
        raise ValueError("pairwise gate requires at least two folds")

    predictions: list[pd.DataFrame] = []
    reports: list[dict[str, object]] = []
    models: list[dict[str, object]] = []
    for position, test_fold in enumerate(fold_order):
        test = frame.loc[frame["fold"].astype(str).eq(test_fold)].copy()
        train_folds = fold_order[:position]
        train = frame.loc[
            frame["fold"].astype(str).isin(train_folds) & frame["experts_disagree"]
        ]
        coefficients = None
        intercept = None
        if not train_folds:
            gate_probability = np.ones(len(test), dtype="float64")
            model = None
            mode = "path_fallback_no_prior_oos"
        elif train["path_correct"].nunique() < 2:
            constant = float(train["path_correct"].mean())
            gate_probability = np.full(len(test), constant, dtype="float64")
            model = None
            mode = "prior_oos_constant"
        else:
            model = _new_model(config)
            model.fit(
                train[list(PAIRWISE_GATE_FEATURES)],
                train["path_correct"].astype("int8"),
            )
            gate_probability = model.predict_proba(
                test[list(PAIRWISE_GATE_FEATURES)]
            )[:, 1]
            logistic = model.named_steps["logistic"]
            coefficients = {
                feature: float(value)
                for feature, value in zip(
                    PAIRWISE_GATE_FEATURES, logistic.coef_[0], strict=True
                )
            }
            intercept = float(logistic.intercept_[0])
            mode = "prior_oos_pairwise_logistic"

        predicted = _apply_gate(test, gate_probability, mode)
        disagreement = predicted.loc[predicted["experts_disagree"]]
        path_metrics = _probability_metrics(predicted, "path_probability_up")
        shift_metrics = _probability_metrics(predicted, "shift_probability_up")
        gate_metrics = _probability_metrics(predicted, "probability_up")
        reports.append(
            {
                "test_fold": test_fold,
                "train_folds": train_folds,
                "mode": mode,
                "rows": len(predicted),
                "train_disagreement_rows": len(train),
                "test_disagreement_rows": len(disagreement),
                "test_disagreement_rate": len(disagreement) / len(predicted),
                "selected_path_rows": int(
                    predicted["gate_selected_candidate"].eq("path").sum()
                ),
                "selected_shift_rows": int(
                    predicted["gate_selected_candidate"].eq("shift").sum()
                ),
                "path": path_metrics,
                "shift": shift_metrics,
                "gate": gate_metrics,
                "gate_minus_path_accuracy": (
                    gate_metrics["accuracy"] - path_metrics["accuracy"]
                ),
                "gate_minus_shift_accuracy": (
                    gate_metrics["accuracy"] - shift_metrics["accuracy"]
                ),
                "disagreement_path_accuracy": (
                    float(disagreement["path_correct"].mean())
                    if len(disagreement)
                    else None
                ),
                "disagreement_gate_accuracy": (
                    float(disagreement["correct"].mean())
                    if len(disagreement)
                    else None
                ),
                "coefficients_scaled_features": coefficients,
                "intercept": intercept,
            }
        )
        predicted["pairwise_gate_train_fold_count"] = len(train_folds)
        predictions.append(predicted)
        models.append(
            {
                "test_fold": test_fold,
                "train_folds": train_folds,
                "model": model,
                "mode": mode,
            }
        )
    return pd.concat(predictions, ignore_index=True), reports, models


def run_pairwise_correctness_gate(
    path_dir: Path,
    shift_dir: Path,
    output_dir: Path,
    config: PairwiseCorrectnessGateConfig,
) -> dict[str, object]:
    path_predictions = read_prediction_sets([path_dir], config.timeframe)
    shift_predictions = read_prediction_sets([shift_dir], config.timeframe)
    frame = build_pairwise_gate_frame(path_predictions, shift_predictions)
    combined, fold_reports, models = chronological_pairwise_gate_predictions(
        frame, config
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    model_entries: list[dict[str, object]] = []
    for entry in models:
        model = entry["model"]
        if model is None:
            model_entries.append(
                {
                    "test_fold": entry["test_fold"],
                    "train_folds": entry["train_folds"],
                    "mode": entry["mode"],
                    "model": None,
                }
            )
            continue
        model_name = f"m{config.timeframe}_{entry['test_fold']}_pairwise_gate.joblib"
        joblib.dump(
            {
                "model": model,
                "config": asdict(config),
                "feature_columns": list(PAIRWISE_GATE_FEATURES),
                "train_folds": entry["train_folds"],
                "test_fold": entry["test_fold"],
            },
            output_dir / model_name,
        )
        model_entries.append(
            {
                "test_fold": entry["test_fold"],
                "train_folds": entry["train_folds"],
                "mode": entry["mode"],
                "model": model_name,
            }
        )

    disagreement = frame.loc[frame["experts_disagree"]]
    final_model = _new_model(config)
    final_model.fit(
        disagreement[list(PAIRWISE_GATE_FEATURES)],
        disagreement["path_correct"].astype("int8"),
    )
    final_model_name = f"m{config.timeframe}_pairwise_gate_research_final.joblib"
    joblib.dump(
        {
            "model": final_model,
            "config": asdict(config),
            "feature_columns": list(PAIRWISE_GATE_FEATURES),
            "train_folds": [str(fold) for fold in frame["fold"].drop_duplicates()],
            "deployment_status": "research_only",
        },
        output_dir / final_model_name,
    )

    aggregate = {
        "path": _probability_metrics(combined, "path_probability_up"),
        "shift": _probability_metrics(combined, "shift_probability_up"),
        "gate": _probability_metrics(combined, "probability_up"),
    }
    created_at = datetime.now(UTC).isoformat()
    report = {
        "created_at": created_at,
        "config": asdict(config),
        "path_dir": str(path_dir),
        "shift_dir": str(shift_dir),
        "feature_columns": list(PAIRWISE_GATE_FEATURES),
        "rows": len(combined),
        "disagreement_rows": int(combined["experts_disagree"].sum()),
        "disagreement_rate": float(combined["experts_disagree"].mean()),
        "aggregate": aggregate,
        "gate_accuracy_wins_vs_path": int(
            sum(row["gate_minus_path_accuracy"] > 0 for row in fold_reports)
        ),
        "gate_accuracy_wins_vs_shift": int(
            sum(row["gate_minus_shift_accuracy"] > 0 for row in fold_reports)
        ),
        "folds": fold_reports,
        "context_diagnostics": context_diagnostics(combined),
    }
    prediction_name = f"m{config.timeframe}_walk_forward_predictions.parquet"
    combined.to_parquet(output_dir / prediction_name, index=False)
    manifest = {
        "format_version": 1,
        "created_at": created_at,
        "kind": "next_bar_chronological_pairwise_correctness_gate",
        "timeframes": {
            f"M{config.timeframe}": {
                "minutes": config.timeframe,
                "features": list(PAIRWISE_GATE_FEATURES),
                "models": model_entries,
                "research_final_model": final_model_name,
                "predictions": prediction_name,
            }
        },
    }
    (output_dir / "pairwise_gate_metrics.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Select Path or Distribution Shift only on disagreements using "
            "prior OOS correctness."
        )
    )
    parser.add_argument("--path-dir", type=Path, required=True)
    parser.add_argument("--shift-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--timeframe", type=int, default=1)
    parser.add_argument("--regularization-c", type=float, default=0.10)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    report = run_pairwise_correctness_gate(
        path_dir=args.path_dir,
        shift_dir=args.shift_dir,
        output_dir=args.output_dir,
        config=PairwiseCorrectnessGateConfig(
            timeframe=args.timeframe,
            regularization_c=args.regularization_c,
        ),
    )
    print(
        json.dumps(
            {
                "rows": report["rows"],
                "disagreement_rows": report["disagreement_rows"],
                "aggregate": report["aggregate"],
                "gate_accuracy_wins_vs_path": report[
                    "gate_accuracy_wins_vs_path"
                ],
                "gate_accuracy_wins_vs_shift": report[
                    "gate_accuracy_wins_vs_shift"
                ],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
