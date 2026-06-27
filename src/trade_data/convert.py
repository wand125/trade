from __future__ import annotations

import argparse
import sys
import zipfile
from datetime import timedelta, timezone
from pathlib import Path
from typing import Iterable

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq


HISTDATA_EST = timezone(timedelta(hours=-5), name="EST")
M1_COLUMNS = ["timestamp_raw", "open", "high", "low", "close", "volume"]
TICK_COLUMNS = ["timestamp_raw", "bid", "ask", "volume"]


def csv_member(zip_path: Path) -> str:
    with zipfile.ZipFile(zip_path) as archive:
        names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
    if len(names) != 1:
        raise ValueError(f"expected one CSV in {zip_path}, found {len(names)}")
    return names[0]


def parse_est_to_utc(values: pd.Series, fmt: str) -> pd.Series:
    timestamps = pd.to_datetime(values, format=fmt, errors="raise")
    return timestamps.dt.tz_localize(HISTDATA_EST).dt.tz_convert("UTC")


def read_m1_zip(zip_path: Path) -> pd.DataFrame:
    member = csv_member(zip_path)
    with zipfile.ZipFile(zip_path) as archive:
        with archive.open(member) as handle:
            df = pd.read_csv(
                handle,
                sep=";",
                header=None,
                names=M1_COLUMNS,
                dtype={
                    "open": "float64",
                    "high": "float64",
                    "low": "float64",
                    "close": "float64",
                    "volume": "int64",
                },
            )
    df.insert(0, "timestamp", parse_est_to_utc(df.pop("timestamp_raw"), "%Y%m%d %H%M%S"))
    return df


def parquet_kwargs(compression: str) -> dict[str, str]:
    return {"compression": compression}


def convert_m1(args: argparse.Namespace) -> int:
    raw_dir = args.raw_dir or Path("data/raw") / "histdata" / args.pair.lower() / "m1"
    output_dir = args.output_dir or Path("data/processed") / "histdata" / args.pair.lower()
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = args.output or output_dir / f"{args.pair.lower()}_m1.parquet"

    zip_paths = sorted(raw_dir.glob("*.zip"))
    if not zip_paths:
        print(f"no M1 zips found in {raw_dir}")
        return 1

    frames = []
    for zip_path in zip_paths:
        print(f"read: {zip_path}")
        frames.append(read_m1_zip(zip_path))
    df = pd.concat(frames, ignore_index=True)
    df = clean_ohlcv(df)
    df.to_parquet(output_path, index=False, **parquet_kwargs(args.compression))
    print(f"wrote: {output_path} ({len(df):,} rows)")

    if args.also_m5:
        m5 = resample_ohlcv(df, "5min")
        m5_path = output_dir / f"{args.pair.lower()}_m5.parquet"
        m5.to_parquet(m5_path, index=False, **parquet_kwargs(args.compression))
        print(f"wrote: {m5_path} ({len(m5):,} rows)")
    return 0


def clean_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    df = df.dropna(subset=["timestamp", "open", "high", "low", "close"])
    df = df.drop_duplicates(subset=["timestamp"], keep="last")
    df = df.sort_values("timestamp").reset_index(drop=True)
    return df


def resample_ohlcv(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    source = df.set_index("timestamp").sort_index()
    output = source.resample(rule, label="left", closed="left").agg(
        {
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        }
    )
    output = output.dropna(subset=["open", "high", "low", "close"]).reset_index()
    return output


def convert_tick(args: argparse.Namespace) -> int:
    raw_dir = args.raw_dir or Path("data/raw") / "histdata" / args.pair.lower() / "tick"
    output_dir = (
        args.output_dir
        or Path("data/processed") / "histdata" / args.pair.lower() / "tick"
    )
    zip_paths = sorted(raw_dir.glob("*.zip"))
    if args.max_files is not None:
        zip_paths = zip_paths[: args.max_files]
    if not zip_paths:
        print(f"no tick zips found in {raw_dir}")
        return 1

    for zip_path in zip_paths:
        period = extract_period_key(zip_path)
        year, month = period[:4], period[4:6]
        target = output_dir / f"year={year}" / f"month={month}" / f"{zip_path.stem}.parquet"
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and not args.force:
            print(f"skip existing: {target}")
            continue
        print(f"convert: {zip_path}")
        write_tick_zip(zip_path, target, args.chunksize, args.compression)
        print(f"wrote: {target}")
    return 0


def extract_period_key(zip_path: Path) -> str:
    stem = zip_path.stem
    value = stem.rsplit("_", maxsplit=1)[-1]
    if len(value) != 6 or not value.isdigit():
        raise ValueError(f"cannot extract YYYYMM period from {zip_path.name}")
    return value


def write_tick_zip(
    zip_path: Path,
    output_path: Path,
    chunksize: int,
    compression: str,
) -> None:
    member = csv_member(zip_path)
    writer: pq.ParquetWriter | None = None
    rows = 0
    try:
        with zipfile.ZipFile(zip_path) as archive:
            with archive.open(member) as handle:
                reader = pd.read_csv(
                    handle,
                    sep=",",
                    header=None,
                    names=TICK_COLUMNS,
                    dtype={"bid": "float64", "ask": "float64", "volume": "int64"},
                    chunksize=chunksize,
                )
                for chunk in reader:
                    chunk.insert(
                        0,
                        "timestamp",
                        parse_est_to_utc(chunk.pop("timestamp_raw"), "%Y%m%d %H%M%S%f"),
                    )
                    chunk["spread"] = chunk["ask"] - chunk["bid"]
                    chunk = chunk.dropna(subset=["timestamp", "bid", "ask"])
                    chunk = chunk.sort_values("timestamp")
                    table = pa.Table.from_pandas(chunk, preserve_index=False)
                    if writer is None:
                        writer = pq.ParquetWriter(
                            output_path,
                            table.schema,
                            compression=compression,
                        )
                    writer.write_table(table)
                    rows += len(chunk)
    finally:
        if writer is not None:
            writer.close()
    print(f"rows: {rows:,}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Convert HistData ZIP files to Parquet")
    subparsers = parser.add_subparsers(dest="command", required=True)

    m1 = subparsers.add_parser("m1", help="convert M1 ZIPs into one Parquet file")
    m1.add_argument("--pair", default="XAUUSD")
    m1.add_argument("--raw-dir", type=Path, default=None)
    m1.add_argument("--output-dir", type=Path, default=None)
    m1.add_argument("--output", type=Path, default=None)
    m1.add_argument("--compression", default="zstd")
    m1.add_argument("--also-m5", action="store_true")
    m1.set_defaults(func=convert_m1)

    tick = subparsers.add_parser("tick", help="convert monthly tick ZIPs to Parquet")
    tick.add_argument("--pair", default="XAUUSD")
    tick.add_argument("--raw-dir", type=Path, default=None)
    tick.add_argument("--output-dir", type=Path, default=None)
    tick.add_argument("--compression", default="zstd")
    tick.add_argument("--chunksize", type=int, default=1_000_000)
    tick.add_argument("--max-files", type=int, default=None)
    tick.add_argument("--force", action="store_true")
    tick.set_defaults(func=convert_tick)

    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    sys.exit(main())

