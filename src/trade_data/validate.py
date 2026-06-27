from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable

import pandas as pd


def validate_parquet(path: Path) -> int:
    df = pd.read_parquet(path)
    if "timestamp" not in df.columns:
        raise SystemExit(f"{path} has no timestamp column")

    df = df.sort_values("timestamp").reset_index(drop=True)
    print(f"file: {path}")
    print(f"rows: {len(df):,}")
    print(f"columns: {', '.join(df.columns)}")
    print(f"start: {df['timestamp'].min()}")
    print(f"end: {df['timestamp'].max()}")
    print(f"duplicate timestamps: {df['timestamp'].duplicated().sum():,}")
    print(f"null cells: {int(df.isna().sum().sum()):,}")

    if {"open", "high", "low", "close"}.issubset(df.columns):
        invalid_ohlc = (
            (df["high"] < df[["open", "close", "low"]].max(axis=1))
            | (df["low"] > df[["open", "close", "high"]].min(axis=1))
        )
        print(f"invalid OHLC rows: {int(invalid_ohlc.sum()):,}")
        gap_report(df, "timestamp")

    if {"bid", "ask"}.issubset(df.columns):
        crossed = (df["ask"] < df["bid"]).sum()
        print(f"crossed bid/ask rows: {int(crossed):,}")
        if "spread" in df.columns:
            print(f"spread min: {df['spread'].min():.6f}")
            print(f"spread p50: {df['spread'].quantile(0.5):.6f}")
            print(f"spread p99: {df['spread'].quantile(0.99):.6f}")
        gap_report(df, "timestamp")
    return 0


def gap_report(df: pd.DataFrame, column: str) -> None:
    diffs = df[column].diff().dropna()
    if diffs.empty:
        return
    print(f"median gap: {diffs.median()}")
    print(f"max gap: {diffs.max()}")
    large_gaps = diffs[diffs > pd.Timedelta(minutes=5)]
    print(f"gaps > 5min: {len(large_gaps):,}")
    if not large_gaps.empty:
        print("largest gaps:")
        for idx, delta in large_gaps.sort_values(ascending=False).head(10).items():
            before = df.loc[idx - 1, column] if idx > 0 else None
            after = df.loc[idx, column]
            print(f"  {before} -> {after}: {delta}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate prepared Parquet market data")
    parser.add_argument("path", type=Path)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return validate_parquet(args.path)


if __name__ == "__main__":
    sys.exit(main())
