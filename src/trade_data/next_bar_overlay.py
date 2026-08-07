from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class OverlayConfig:
    timestamp_column: str = "entry_decision_timestamp"
    side_column: str = "direction"
    pnl_column: str = "candidate_adjusted_pnl"
    present_column: str | None = "candidate_present"
    confidence_threshold: float = 0.54
    loss_multiplier: float = 1.00
    opposed_size: float = 0.50


def read_prediction_sets(
    prediction_dirs: Sequence[Path], timeframe_minutes: int
) -> pd.DataFrame:
    name = f"M{timeframe_minutes}"
    frames = []
    for directory in prediction_dirs:
        manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        if name not in manifest["timeframes"]:
            continue
        entry = manifest["timeframes"][name]
        frames.append(pd.read_parquet(directory / entry["predictions"]))
    if not frames:
        raise ValueError(f"prediction manifests do not contain {name}")
    predictions = pd.concat(frames, ignore_index=True)
    required = {
        "decision_timestamp",
        "target_timestamp",
        "predicted_direction",
        "confidence",
        "fold",
    }
    missing = sorted(required - set(predictions.columns))
    if missing:
        raise ValueError(f"next-bar predictions are missing: {', '.join(missing)}")
    predictions["decision_timestamp"] = pd.to_datetime(
        predictions["decision_timestamp"], utc=True
    ).astype("datetime64[ns, UTC]")
    predictions["target_timestamp"] = pd.to_datetime(
        predictions["target_timestamp"], utc=True
    ).astype("datetime64[ns, UTC]")
    duplicate = predictions.duplicated("decision_timestamp", keep=False)
    if duplicate.any():
        raise ValueError("prediction sets contain duplicate decision timestamps")
    return predictions.sort_values("decision_timestamp").reset_index(drop=True)


def attach_next_bar_overlay(
    trades: pd.DataFrame,
    predictions: pd.DataFrame,
    config: OverlayConfig,
) -> pd.DataFrame:
    required_trades = {
        config.timestamp_column,
        config.side_column,
        config.pnl_column,
    }
    if config.present_column:
        required_trades.add(config.present_column)
    missing = sorted(required_trades - set(trades.columns))
    if missing:
        raise ValueError(f"trade rows are missing: {', '.join(missing)}")
    frame = trades.copy()
    if config.present_column:
        frame = frame.loc[frame[config.present_column].astype(bool)].copy()
    frame[config.timestamp_column] = pd.to_datetime(
        frame[config.timestamp_column], utc=True
    ).astype("datetime64[ns, UTC]")
    predictions = predictions.copy()
    predictions["decision_timestamp"] = pd.to_datetime(
        predictions["decision_timestamp"], utc=True
    ).astype("datetime64[ns, UTC]")
    predictions["target_timestamp"] = pd.to_datetime(
        predictions["target_timestamp"], utc=True
    ).astype("datetime64[ns, UTC]")
    frame = frame.loc[frame[config.pnl_column].notna()].copy()
    prediction_columns = [
        "decision_timestamp",
        "target_timestamp",
        "predicted_direction",
        "confidence",
        "fold",
    ]
    output = pd.merge_asof(
        frame.sort_values(config.timestamp_column),
        predictions[prediction_columns].sort_values("decision_timestamp"),
        left_on=config.timestamp_column,
        right_on="decision_timestamp",
        direction="backward",
        allow_exact_matches=True,
    )
    active = output[config.timestamp_column] < output["target_timestamp"]
    output["next_bar_available"] = active.fillna(False)
    output.loc[~output["next_bar_available"], prediction_columns[1:]] = np.nan
    side = (
        output[config.side_column]
        .astype(str)
        .str.lower()
        .replace({"long": "up", "short": "down", "buy": "up", "sell": "down"})
    )
    predicted_side = output["predicted_direction"].astype(str).str.lower()
    output["next_bar_aligned"] = output["next_bar_available"] & side.eq(predicted_side)
    output["next_bar_high_confidence"] = (
        output["next_bar_available"]
        & output["confidence"].ge(config.confidence_threshold)
    )
    output["next_bar_high_confidence_opposed"] = (
        output["next_bar_high_confidence"] & ~output["next_bar_aligned"]
    )
    output["trade_direction_probability"] = np.where(
        output["next_bar_aligned"],
        output["confidence"],
        1 - output["confidence"],
    )
    output.loc[
        ~output["next_bar_available"], "trade_direction_probability"
    ] = np.nan
    output["trade_direction_odds"] = (
        output["trade_direction_probability"]
        / (1 - output["trade_direction_probability"])
    )
    return output.sort_values(config.timestamp_column).reset_index(drop=True)


def _maximum_drawdown(pnl: pd.Series) -> float:
    if pnl.empty:
        return 0.0
    equity = pnl.cumsum()
    return float((equity.cummax() - equity).max())


def summarize_overlay(
    frame: pd.DataFrame,
    multiplier: pd.Series | np.ndarray,
    config: OverlayConfig,
) -> dict[str, object]:
    size = np.asarray(multiplier, dtype="float64")
    pnl = frame[config.pnl_column].astype("float64") * size
    selected = size > 0
    selected_pnl = pnl.loc[selected]
    selected_rows = frame.loc[selected]
    risk_adjusted = selected_pnl.where(
        selected_pnl >= 0, selected_pnl * config.loss_multiplier
    )
    if "month" in frame.columns:
        month = frame["month"].astype(str)
    else:
        month = frame[config.timestamp_column].dt.strftime("%Y-%m")
    monthly = (
        pd.DataFrame({"month": month, "pnl": pnl})
        .groupby("month", sort=True)["pnl"]
        .sum()
    )
    return {
        "rows": int(selected.sum()),
        "coverage": float(selected.mean()) if len(selected) else 0.0,
        "total_pnl": float(selected_pnl.sum()),
        "mean_pnl": float(selected_pnl.mean()) if len(selected_pnl) else None,
        "win_rate": (
            float((selected_pnl > 0).mean()) if len(selected_pnl) else None
        ),
        "risk_adjusted_total": float(risk_adjusted.sum()),
        "risk_adjusted_mean": (
            float(risk_adjusted.mean()) if len(risk_adjusted) else None
        ),
        "positive_months": int((monthly > 0).sum()),
        "months": int(len(monthly)),
        "worst_month_pnl": float(monthly.min()) if len(monthly) else None,
        "max_drawdown": _maximum_drawdown(pnl),
        "mean_trade_direction_probability": (
            float(selected_rows["trade_direction_probability"].mean())
            if len(selected_rows)
            else None
        ),
        "monthly_pnl": {str(key): float(value) for key, value in monthly.items()},
    }


def evaluate_overlay_policies(
    frame: pd.DataFrame, config: OverlayConfig
) -> dict[str, object]:
    available = frame["next_bar_available"].to_numpy(dtype=bool)
    high = frame["next_bar_high_confidence"].to_numpy(dtype=bool)
    aligned = frame["next_bar_aligned"].to_numpy(dtype=bool)
    opposed = frame["next_bar_high_confidence_opposed"].to_numpy(dtype=bool)
    policies = {
        "baseline": np.ones(len(frame)),
        "covered_only": available.astype(float),
        "veto_high_confidence_opposed": (~opposed).astype(float),
        "require_high_confidence_aligned": (high & aligned).astype(float),
        "half_size_high_confidence_opposed": np.where(
            opposed, config.opposed_size, 1.0
        ),
    }
    return {
        name: summarize_overlay(frame, multiplier, config)
        for name, multiplier in policies.items()
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Evaluate next-bar direction as a no-replacement trade overlay."
    )
    parser.add_argument("--trades", type=Path, required=True)
    parser.add_argument("--predictions-dir", type=Path, action="append", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--timeframe", type=int, default=15)
    parser.add_argument("--timestamp-column", default="entry_decision_timestamp")
    parser.add_argument("--side-column", default="direction")
    parser.add_argument("--pnl-column", default="candidate_adjusted_pnl")
    parser.add_argument("--present-column", default="candidate_present")
    parser.add_argument("--confidence-threshold", type=float, default=0.54)
    parser.add_argument("--loss-multiplier", type=float, default=1.00)
    parser.add_argument("--opposed-size", type=float, default=0.50)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    config = OverlayConfig(
        timestamp_column=args.timestamp_column,
        side_column=args.side_column,
        pnl_column=args.pnl_column,
        present_column=args.present_column or None,
        confidence_threshold=args.confidence_threshold,
        loss_multiplier=args.loss_multiplier,
        opposed_size=args.opposed_size,
    )
    trades = pd.read_csv(args.trades)
    predictions = read_prediction_sets(args.predictions_dir, args.timeframe)
    enriched = attach_next_bar_overlay(trades, predictions, config)
    policies = evaluate_overlay_policies(enriched, config)
    report = {
        "created_at": datetime.now(UTC).isoformat(),
        "config": asdict(config),
        "timeframe": f"M{args.timeframe}",
        "source_trades": str(args.trades),
        "source_predictions": [str(path) for path in args.predictions_dir],
        "semantics": "no-replacement skip/size counterfactual on existing trades",
        "rows": len(enriched),
        "prediction_coverage": float(enriched["next_bar_available"].mean()),
        "policies": policies,
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    enriched.to_parquet(args.output_dir / "overlay_rows.parquet", index=False)
    (args.output_dir / "metrics.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
