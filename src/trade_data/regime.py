from __future__ import annotations

import numpy as np
import pandas as pd


REGIME_NUMERIC_COLUMNS = [
    "trend_score_240",
    "volatility_score_60",
]

REGIME_CATEGORY_COLUMNS = [
    "trend_regime",
    "volatility_regime",
    "session_regime",
    "gap_regime",
    "combined_regime",
]

REGIME_COLUMNS = [
    *REGIME_NUMERIC_COLUMNS,
    *REGIME_CATEGORY_COLUMNS,
]


def session_regime(timestamps: pd.Series) -> pd.Series:
    hour = pd.to_datetime(timestamps, utc=True).dt.hour
    values = np.select(
        [
            hour.between(0, 6),
            hour.between(7, 12),
            hour.between(13, 16),
            hour.between(17, 21),
        ],
        [
            "asia",
            "london",
            "ny_overlap",
            "ny_late",
        ],
        default="rollover",
    )
    return pd.Series(values, index=timestamps.index, dtype="string")


def add_regime_columns(
    frame: pd.DataFrame,
    timestamp_column: str = "decision_timestamp",
) -> pd.DataFrame:
    output = frame.copy()
    if "roll_return_240" in output.columns and "roll_vol_240" in output.columns:
        denominator = output["roll_vol_240"].astype(float) * np.sqrt(240)
        output["trend_score_240"] = output["roll_return_240"].astype(float) / denominator.replace(0, np.nan)
    else:
        output["trend_score_240"] = np.nan

    if "roll_vol_60" in output.columns:
        output["volatility_score_60"] = output["roll_vol_60"].astype(float)
    elif "atr_60" in output.columns and "close" in output.columns:
        output["volatility_score_60"] = output["atr_60"].astype(float) / output["close"].astype(float)
    else:
        output["volatility_score_60"] = np.nan

    trend_score = output["trend_score_240"].astype(float)
    output["trend_regime"] = pd.Series(
        np.select(
            [trend_score > 0.6, trend_score < -0.6, trend_score.notna()],
            ["up", "down", "range"],
            default="unknown",
        ),
        index=output.index,
        dtype="string",
    )

    volatility_score = output["volatility_score_60"].astype(float)
    output["volatility_regime"] = pd.Series(
        np.select(
            [volatility_score >= 0.00075, volatility_score <= 0.00025, volatility_score.notna()],
            ["high_vol", "low_vol", "normal_vol"],
            default="unknown",
        ),
        index=output.index,
        dtype="string",
    )

    if timestamp_column in output.columns:
        output["session_regime"] = session_regime(output[timestamp_column])
    else:
        output["session_regime"] = pd.Series("unknown", index=output.index, dtype="string")

    if "gap_minutes" in output.columns:
        gap_minutes = output["gap_minutes"].astype(float)
        output["gap_regime"] = pd.Series(
            np.select(
                [gap_minutes > 15, gap_minutes > 5, gap_minutes.notna()],
                ["gap", "micro_gap", "normal_gap"],
                default="unknown",
            ),
            index=output.index,
            dtype="string",
        )
    else:
        output["gap_regime"] = pd.Series("unknown", index=output.index, dtype="string")

    output["combined_regime"] = (
        output["trend_regime"].astype(str) + "_" + output["volatility_regime"].astype(str)
    ).astype("string")
    for column in REGIME_NUMERIC_COLUMNS:
        output[column] = output[column].astype("float32")
    return output
