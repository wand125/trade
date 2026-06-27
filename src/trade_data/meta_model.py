from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from trade_data.modeling import selection_metrics


SIDE_COLUMNS = {
    "long": {
        "target": "long_best_adjusted_pnl",
        "opposite_target": "short_best_adjusted_pnl",
        "ev": "pred_long_best_adjusted_pnl",
        "opposite_ev": "pred_short_best_adjusted_pnl",
        "calibrated_ev": "pred_calibrated_long_best_adjusted_pnl",
        "opposite_calibrated_ev": "pred_calibrated_short_best_adjusted_pnl",
        "risk": "pred_long_max_adverse_pnl",
        "holding": "pred_long_best_holding_minutes",
        "wait_regret": "pred_long_wait_regret",
        "entry_rank": "pred_long_entry_local_rank",
        "entry_urgency": "pred_long_entry_urgency",
        "profit_barrier_hit": "pred_long_profit_barrier_hit",
        "wait_regret_quantile": "pred_long_wait_regret_quantile",
        "entry_rank_bin": "pred_long_entry_local_rank_bin",
    },
    "short": {
        "target": "short_best_adjusted_pnl",
        "opposite_target": "long_best_adjusted_pnl",
        "ev": "pred_short_best_adjusted_pnl",
        "opposite_ev": "pred_long_best_adjusted_pnl",
        "calibrated_ev": "pred_calibrated_short_best_adjusted_pnl",
        "opposite_calibrated_ev": "pred_calibrated_long_best_adjusted_pnl",
        "risk": "pred_short_max_adverse_pnl",
        "holding": "pred_short_best_holding_minutes",
        "wait_regret": "pred_short_wait_regret",
        "entry_rank": "pred_short_entry_local_rank",
        "entry_urgency": "pred_short_entry_urgency",
        "profit_barrier_hit": "pred_short_profit_barrier_hit",
        "wait_regret_quantile": "pred_short_wait_regret_quantile",
        "entry_rank_bin": "pred_short_entry_local_rank_bin",
    },
}

BASE_FEATURE_COLUMNS = [
    "side",
    "pred_side_ev",
    "pred_opposite_ev",
    "pred_side_calibrated_ev",
    "pred_opposite_calibrated_ev",
    "pred_side_gap",
    "pred_side_risk",
    "pred_side_holding",
    "pred_side_wait_regret",
    "pred_side_entry_rank",
    "pred_side_entry_urgency",
    "pred_side_profit_barrier_hit",
    "pred_side_wait_regret_quantile",
    "pred_side_entry_rank_bin",
    "pred_best_adjusted_pnl_quantile",
    "pred_side_score_quantile",
    "pred_label",
]


@dataclass(frozen=True)
class MetaModelConfig:
    max_iter: int
    learning_rate: float
    max_leaf_nodes: int
    min_samples_leaf: int
    l2_regularization: float
    random_seed: int
    target_clip_quantile: float
    entry_threshold: float


def make_run_dir(root: Path, label: str) -> Path:
    timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    for index in range(100):
        suffix = "" if index == 0 else f"_{index}"
        path = root / f"{timestamp}_{label}{suffix}"
        try:
            path.mkdir(parents=True, exist_ok=False)
            return path
        except FileExistsError:
            continue
    raise FileExistsError(f"could not create unique run directory for {label}")


def optional_column(df: pd.DataFrame, primary: str, fallback: str) -> pd.Series:
    if primary in df.columns:
        return df[primary]
    return df[fallback]


def side_examples(df: pd.DataFrame, side_name: str) -> pd.DataFrame:
    spec = SIDE_COLUMNS[side_name]
    side_value = 1.0 if side_name == "long" else -1.0
    side_ev = df[spec["ev"]].astype(float)
    opposite_ev = df[spec["opposite_ev"]].astype(float)
    output = pd.DataFrame(
        {
            "side": side_value,
            "pred_side_ev": side_ev,
            "pred_opposite_ev": opposite_ev,
            "pred_side_calibrated_ev": optional_column(
                df,
                spec["calibrated_ev"],
                spec["ev"],
            ).astype(float),
            "pred_opposite_calibrated_ev": optional_column(
                df,
                spec["opposite_calibrated_ev"],
                spec["opposite_ev"],
            ).astype(float),
            "pred_side_gap": side_ev - opposite_ev,
            "pred_side_risk": df[spec["risk"]].astype(float),
            "pred_side_holding": df[spec["holding"]].astype(float),
            "pred_side_wait_regret": df[spec["wait_regret"]].astype(float),
            "pred_side_entry_rank": df[spec["entry_rank"]].astype(float),
            "pred_side_entry_urgency": df[spec["entry_urgency"]].astype(float),
            "pred_side_profit_barrier_hit": df[spec["profit_barrier_hit"]].astype(float),
            "pred_side_wait_regret_quantile": df[spec["wait_regret_quantile"]].astype(float),
            "pred_side_entry_rank_bin": df[spec["entry_rank_bin"]].astype(float),
            "pred_best_adjusted_pnl_quantile": df["pred_best_adjusted_pnl_quantile"].astype(float),
            "pred_side_score_quantile": df["pred_side_score_quantile"].astype(float),
            "pred_label": df["pred_label"].astype(float),
            "target": df[spec["target"]].astype(float),
            "opposite_target": df[spec["opposite_target"]].astype(float),
        }
    )
    return output


def build_training_frame(df: pd.DataFrame) -> pd.DataFrame:
    frame = pd.concat(
        [side_examples(df, "long"), side_examples(df, "short")],
        ignore_index=True,
    )
    return frame.replace([np.inf, -np.inf], np.nan).dropna(subset=[*BASE_FEATURE_COLUMNS, "target"])


def as_matrix(df: pd.DataFrame) -> np.ndarray:
    return df[BASE_FEATURE_COLUMNS].astype("float32").to_numpy()


def clipped_target(values: pd.Series, clip_quantile: float) -> np.ndarray:
    target = values.astype(float)
    if clip_quantile >= 1.0:
        return target.to_numpy()
    if not 0.5 < clip_quantile <= 1.0:
        raise ValueError("target_clip_quantile must be in (0.5, 1.0]")
    lower = target.quantile(1.0 - clip_quantile)
    upper = target.quantile(clip_quantile)
    return target.clip(lower=lower, upper=upper).to_numpy()


def regression_metrics(y_true: pd.Series, y_pred: np.ndarray) -> dict[str, float]:
    return {
        "mae": float(mean_absolute_error(y_true, y_pred)),
        "rmse": float(mean_squared_error(y_true, y_pred) ** 0.5),
        "r2": float(r2_score(y_true, y_pred)),
    }


def train_model(frame: pd.DataFrame, config: MetaModelConfig) -> HistGradientBoostingRegressor:
    model = HistGradientBoostingRegressor(
        max_iter=config.max_iter,
        learning_rate=config.learning_rate,
        max_leaf_nodes=config.max_leaf_nodes,
        min_samples_leaf=config.min_samples_leaf,
        l2_regularization=config.l2_regularization,
        random_state=config.random_seed,
    )
    model.fit(as_matrix(frame), clipped_target(frame["target"], config.target_clip_quantile))
    return model


def add_meta_predictions(df: pd.DataFrame, model: HistGradientBoostingRegressor) -> pd.DataFrame:
    output = df.copy()
    for side_name, output_column in [
        ("long", "pred_meta_long_adjusted_pnl"),
        ("short", "pred_meta_short_adjusted_pnl"),
    ]:
        examples = side_examples(df, side_name)
        output[output_column] = model.predict(as_matrix(examples))
    return output


def split_meta_metrics(df: pd.DataFrame, entry_threshold: float) -> dict[str, object]:
    metrics = {
        "long": regression_metrics(df["long_best_adjusted_pnl"], df["pred_meta_long_adjusted_pnl"].to_numpy()),
        "short": regression_metrics(df["short_best_adjusted_pnl"], df["pred_meta_short_adjusted_pnl"].to_numpy()),
        "selection": selection_metrics(
            df,
            threshold=entry_threshold,
            long_column="pred_meta_long_adjusted_pnl",
            short_column="pred_meta_short_adjusted_pnl",
        ),
    }
    return metrics


def fit(args: argparse.Namespace) -> int:
    config = MetaModelConfig(
        max_iter=args.max_iter,
        learning_rate=args.learning_rate,
        max_leaf_nodes=args.max_leaf_nodes,
        min_samples_leaf=args.min_samples_leaf,
        l2_regularization=args.l2_regularization,
        random_seed=args.random_seed,
        target_clip_quantile=args.target_clip_quantile,
        entry_threshold=args.entry_threshold,
    )
    train_predictions = pd.read_parquet(args.train_predictions)
    apply_predictions = pd.read_parquet(args.apply_predictions)
    train_frame = build_training_frame(train_predictions)
    model = train_model(train_frame, config)
    train_output = add_meta_predictions(train_predictions, model)
    apply_output = add_meta_predictions(apply_predictions, model)

    run_dir = make_run_dir(args.output_dir, args.label)
    train_output.to_parquet(run_dir / "predictions_train_meta.parquet", index=False)
    apply_output.to_parquet(run_dir / "predictions_apply_meta.parquet", index=False)
    joblib.dump(model, run_dir / "meta_ev_regressor.joblib")
    metrics = {
        "config": asdict(config),
        "train_predictions": str(args.train_predictions),
        "apply_predictions": str(args.apply_predictions),
        "rows": {
            "train_predictions": int(len(train_predictions)),
            "train_side_examples": int(len(train_frame)),
            "apply_predictions": int(len(apply_predictions)),
        },
        "feature_columns": BASE_FEATURE_COLUMNS,
        "train": split_meta_metrics(train_output, args.entry_threshold),
        "apply": split_meta_metrics(apply_output, args.entry_threshold),
    }
    with (run_dir / "metrics.json").open("w", encoding="utf-8") as handle:
        json.dump(metrics, handle, ensure_ascii=False, indent=2)
    print(json.dumps(metrics["train"], indent=2))
    print(json.dumps(metrics["apply"], indent=2))
    print(f"artifacts: {run_dir}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fit second-stage meta models from prediction frames")
    subparsers = parser.add_subparsers(dest="command", required=True)

    fit_parser = subparsers.add_parser("fit", help="fit a meta EV model and apply it")
    fit_parser.add_argument("--train-predictions", type=Path, required=True)
    fit_parser.add_argument("--apply-predictions", type=Path, required=True)
    fit_parser.add_argument("--output-dir", type=Path, default=Path("experiments"))
    fit_parser.add_argument("--label", default="meta_ev")
    fit_parser.add_argument("--max-iter", type=int, default=80)
    fit_parser.add_argument("--learning-rate", type=float, default=0.03)
    fit_parser.add_argument("--max-leaf-nodes", type=int, default=15)
    fit_parser.add_argument("--min-samples-leaf", type=int, default=100)
    fit_parser.add_argument("--l2-regularization", type=float, default=0.2)
    fit_parser.add_argument("--random-seed", type=int, default=17)
    fit_parser.add_argument("--target-clip-quantile", type=float, default=0.99)
    fit_parser.add_argument("--entry-threshold", type=float, default=15.0)
    fit_parser.set_defaults(func=fit)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())
