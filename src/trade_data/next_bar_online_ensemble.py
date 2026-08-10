from __future__ import annotations

import argparse
import json
from collections import deque
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
import pandas as pd

from trade_data.next_bar import context_diagnostics, evaluate_probabilities
from trade_data.next_bar_disagreement import aligned_prediction_matrix
from trade_data.next_bar_overlay import read_prediction_sets


DEFAULT_HISTORY_ROWS = 2_000


def _binary_log_losses(probabilities: np.ndarray, target_up: int) -> np.ndarray:
    clipped = np.clip(probabilities, 1e-6, 1 - 1e-6)
    if target_up:
        return -np.log(clipped)
    return -np.log1p(-clipped)


def combine_online_experts(
    baseline: pd.DataFrame,
    candidates: Sequence[pd.DataFrame],
    history_rows: int = DEFAULT_HISTORY_ROWS,
    preserve_baseline_direction: bool = False,
) -> pd.DataFrame:
    if history_rows < 1:
        raise ValueError("history_rows must be positive")
    output, probabilities = aligned_prediction_matrix(baseline, candidates)
    order = np.argsort(
        output["decision_timestamp"].to_numpy(dtype="datetime64[ns]"),
        kind="stable",
    )
    output = output.iloc[order].reset_index(drop=True)
    probabilities = probabilities[order]

    decisions = pd.to_datetime(output["decision_timestamp"], utc=True).array
    target_times = pd.to_datetime(output["target_timestamp"], utc=True).array
    if any(target_times[index] < target_times[index - 1] for index in range(1, len(output))):
        raise ValueError("target timestamps must be chronological after decision sorting")
    if any(target_time <= decision for target_time, decision in zip(target_times, decisions)):
        raise ValueError("each target timestamp must be after its decision timestamp")
    targets = output["target_up"].to_numpy(dtype="int8")
    model_count = probabilities.shape[1]
    rolling_losses: deque[np.ndarray] = deque()
    loss_sums = np.zeros(model_count, dtype="float64")
    weights = np.empty_like(probabilities)
    history_counts = np.zeros(len(output), dtype="int32")
    reveal_index = 0

    for row_index, decision_timestamp in enumerate(decisions):
        while (
            reveal_index < row_index
            and target_times[reveal_index] <= decision_timestamp
        ):
            revealed_loss = _binary_log_losses(
                probabilities[reveal_index], int(targets[reveal_index])
            )
            if len(rolling_losses) == history_rows:
                loss_sums -= rolling_losses.popleft()
            rolling_losses.append(revealed_loss)
            loss_sums += revealed_loss
            reveal_index += 1

        log_weights = -loss_sums
        unnormalized = np.exp(log_weights - log_weights.max())
        weights[row_index] = unnormalized / unnormalized.sum()
        history_counts[row_index] = len(rolling_losses)

    weighted_probability = np.sum(weights * probabilities, axis=1)
    baseline_probability = probabilities[:, 0]
    if preserve_baseline_direction:
        baseline_sign = np.where(baseline_probability >= 0.5, 1.0, -1.0)
        aligned_edge = baseline_sign * (weighted_probability - 0.5)
        probability_up = 0.5 + baseline_sign * np.maximum(
            aligned_edge, np.finfo("float64").eps
        )
    else:
        probability_up = weighted_probability

    output["baseline_probability_up"] = baseline_probability
    output["probability_up"] = np.clip(probability_up, 1e-6, 1 - 1e-6)
    output["probability_down"] = 1 - output["probability_up"]
    output["predicted_up"] = output["probability_up"].ge(0.5).astype("int8")
    output["predicted_direction"] = np.where(
        output["predicted_up"].eq(1), "up", "down"
    )
    output["class_confidence"] = np.maximum(
        output["probability_up"], 1 - output["probability_up"]
    )
    output["confidence"] = output["class_confidence"]
    output["correct"] = output["predicted_up"].eq(targets)
    output["online_model_count"] = model_count
    output["online_history_limit"] = history_rows
    output["online_history_rows"] = history_counts
    output["online_preserve_baseline_direction"] = preserve_baseline_direction
    output["online_weight_max"] = weights.max(axis=1)
    output["online_effective_model_count"] = 1 / np.sum(np.square(weights), axis=1)
    for model_index in range(model_count):
        output[f"online_weight_{model_index}"] = weights[:, model_index]
    return output


def build_online_ensemble(
    baseline_dirs: Sequence[Path],
    candidate_dirs: Sequence[Path],
    output_dir: Path,
    timeframe: int = 15,
    history_rows: int = DEFAULT_HISTORY_ROWS,
    preserve_baseline_direction: bool = False,
) -> dict[str, object]:
    baseline = read_prediction_sets(baseline_dirs, timeframe)
    candidates = [read_prediction_sets([directory], timeframe) for directory in candidate_dirs]
    combined = combine_online_experts(
        baseline,
        candidates,
        history_rows,
        preserve_baseline_direction,
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    prediction_name = f"m{timeframe}_walk_forward_predictions.parquet"
    combined.to_parquet(output_dir / prediction_name, index=False)
    aggregate = evaluate_probabilities(
        combined["target_up"].to_numpy(dtype="int8"),
        combined["probability_up"].to_numpy(dtype="float64"),
    )
    folds = []
    for fold, group in combined.groupby("fold", sort=False):
        values = evaluate_probabilities(
            group["target_up"].to_numpy(dtype="int8"),
            group["probability_up"].to_numpy(dtype="float64"),
        )
        folds.append(
            {
                "fold": str(fold),
                **values,
                "mean_max_weight": float(group["online_weight_max"].mean()),
                "mean_effective_model_count": float(
                    group["online_effective_model_count"].mean()
                ),
            }
        )
    created_at = datetime.now(UTC).isoformat()
    report = {
        "created_at": created_at,
        "timeframe": f"M{timeframe}",
        "baseline_dirs": [str(path) for path in baseline_dirs],
        "candidate_dirs": [str(path) for path in candidate_dirs],
        "model_count": 1 + len(candidate_dirs),
        "history_rows": history_rows,
        "preserve_baseline_direction": preserve_baseline_direction,
        "aggregate": aggregate,
        "weight_diagnostics": {
            "mean_max_weight": float(combined["online_weight_max"].mean()),
            "mean_effective_model_count": float(
                combined["online_effective_model_count"].mean()
            ),
            "mean_weights": [
                float(combined[f"online_weight_{index}"].mean())
                for index in range(1 + len(candidate_dirs))
            ],
            "final_weights": [
                float(combined[f"online_weight_{index}"].iloc[-1])
                for index in range(1 + len(candidate_dirs))
            ],
        },
        "folds": folds,
        "context_diagnostics": context_diagnostics(combined),
    }
    manifest = {
        "format_version": 1,
        "created_at": created_at,
        "kind": "next_bar_online_expert_ensemble",
        "sources": {
            "baseline": [str(path) for path in baseline_dirs],
            "candidates": [str(path) for path in candidate_dirs],
        },
        "formula": {
            "history_rows": history_rows,
            "learning_rate": 1.0,
            "initial_weights": "equal",
            "loss": "binary log loss",
            "eligible_history": "target_timestamp <= current decision_timestamp",
            "preserve_baseline_direction": preserve_baseline_direction,
        },
        "timeframes": {
            f"M{timeframe}": {
                "minutes": timeframe,
                "predictions": prediction_name,
            }
        },
    }
    (output_dir / "online_ensemble_metrics.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Combine aligned OOS models using causal rolling log-loss weights."
    )
    parser.add_argument("--baseline-dir", type=Path, action="append", required=True)
    parser.add_argument("--candidate-dir", type=Path, action="append", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--timeframe", type=int, default=15)
    parser.add_argument("--history-rows", type=int, default=DEFAULT_HISTORY_ROWS)
    parser.add_argument("--preserve-baseline-direction", action="store_true")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    report = build_online_ensemble(
        args.baseline_dir,
        args.candidate_dir,
        args.output_dir,
        args.timeframe,
        args.history_rows,
        args.preserve_baseline_direction,
    )
    summary = {
        "aggregate": report["aggregate"],
        "weight_diagnostics": report["weight_diagnostics"],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
