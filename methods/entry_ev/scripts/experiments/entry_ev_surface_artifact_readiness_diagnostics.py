#!/usr/bin/env python3
"""Diagnose which negative-month artifacts are ready for selector-surface replay."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
SCRIPT_DIR = Path(__file__).resolve().parent
for path in (SRC, SCRIPT_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from trade_data.backtest import make_run_dir  # noqa: E402

from entry_ev_supervised_shrinkage_policy_inputs import local_json_default  # noqa: E402
from entry_ev_thin_month_opposite_candidate_diagnostics import numeric_series  # noqa: E402


DEFAULT_INVENTORY_DIR = (
    ROOT
    / "data/reports/backtests"
    / "20260703_075023_20260703_entry_ev_00370_support_negative_month_inventory"
)
SURFACE_CONFIG_KEYS = {"current_trades", "family_predictions", "candidate"}
SURFACE_TRADE_COLUMNS = {
    "role",
    "family",
    "month",
    "candidate",
    "selector_variant",
    "entry_block_rule",
    "entry_blocked",
    "entry_decision_timestamp",
    "exit_decision_timestamp",
}


def resolve_path(value: str | Path, *, base: Path = ROOT) -> Path:
    path = Path(value)
    return path if path.is_absolute() else base / path


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_inventory(inventory_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    config_summary = pd.read_csv(inventory_dir / "support_negative_month_config_summary.csv")
    inventory = pd.read_csv(inventory_dir / "support_negative_month_inventory.csv", low_memory=False)
    return config_summary, inventory


def candidate_trade_files(parent_dir: Path) -> list[Path]:
    if not parent_dir.exists():
        return []
    files = sorted(parent_dir.glob("*trades.csv"))
    return [path for path in files if "skipped" not in path.name]


def inspect_trade_file(path: Path) -> dict[str, Any]:
    try:
        columns = list(pd.read_csv(path, nrows=0).columns)
        missing = sorted(SURFACE_TRADE_COLUMNS - set(columns))
        return {
            "trade_file": str(path),
            "trade_file_name": path.name,
            "trade_schema_status": "ok" if not missing else "missing_required_columns",
            "trade_missing_required_columns": ";".join(missing),
            "trade_column_count": int(len(columns)),
            "surface_trade_schema_ready": not missing,
            "trade_read_error": "",
        }
    except Exception as exc:  # pragma: no cover - diagnostic inventory should keep scanning.
        return {
            "trade_file": str(path),
            "trade_file_name": path.name,
            "trade_schema_status": "error",
            "trade_missing_required_columns": "",
            "trade_column_count": 0,
            "surface_trade_schema_ready": False,
            "trade_read_error": str(exc),
        }


def inspect_config(parent_dir: Path) -> dict[str, Any]:
    config_path = parent_dir / "config.json"
    config = read_json(config_path)
    config_keys = set(config)
    missing_surface_keys = sorted(SURFACE_CONFIG_KEYS - config_keys)
    return {
        "config_path": str(config_path),
        "config_exists": config_path.exists(),
        "config_surface_ready": bool(config and not missing_surface_keys),
        "config_missing_surface_keys": ";".join(missing_surface_keys),
        "config_has_scored_trades": "scored_trades" in config,
        "config_candidate": str(config.get("candidate", "")),
        "config_variant_contains": str(config.get("variant_contains", "")),
        "config_selector_variant_contains": str(config.get("selector_variant_contains", "")),
        "config_entry_block_rule": str(config.get("entry_block_rule", "")),
        "config_current_trades": str(config.get("current_trades", "")),
        "config_family_prediction_count": len(dict(config.get("family_predictions", {})))
        if isinstance(config.get("family_predictions", {}), dict)
        else 0,
    }


def summarize_parent_targets(inventory: pd.DataFrame) -> pd.DataFrame:
    if inventory.empty:
        return pd.DataFrame()
    frame = inventory.copy()
    frame["month"] = frame["month"].astype(str).str.slice(0, 7)
    frame["support_sufficient_negative_month"] = frame[
        "support_sufficient_negative_month"
    ].astype(bool)
    negative = frame[frame["support_sufficient_negative_month"]].copy()
    if negative.empty:
        return pd.DataFrame()
    rows: list[dict[str, Any]] = []
    for metric_parent, group in negative.groupby("metric_parent", dropna=False):
        target_keys = (
            group["role"].astype(str)
            + "|"
            + group["family"].astype(str)
            + "|"
            + group["month"].astype(str)
        )
        rows.append(
            {
                "metric_parent": str(metric_parent),
                "support_sufficient_target_row_count": int(len(group)),
                "support_sufficient_target_identity_count": int(target_keys.nunique()),
                "support_sufficient_target_identities": ";".join(sorted(target_keys.unique())),
                "min_support_sufficient_month_pnl": float(
                    numeric_series(group, "month_pnl", default=0.0).min()
                ),
                "max_support_sufficient_month_pnl": float(
                    numeric_series(group, "month_pnl", default=0.0).max()
                ),
            }
        )
    return pd.DataFrame(rows)


def parent_summary(config_summary: pd.DataFrame, inventory: pd.DataFrame) -> pd.DataFrame:
    target_summary = summarize_parent_targets(inventory)
    rows: list[dict[str, Any]] = []
    group_cols = ["metric_parent", "metric_path"]
    for (metric_parent, metric_path), group in config_summary.groupby(group_cols, dropna=False):
        metric_path_obj = resolve_path(str(metric_path))
        parent_dir = metric_path_obj.parent
        trade_files = candidate_trade_files(parent_dir)
        config_info = inspect_config(parent_dir)
        trade_infos = [inspect_trade_file(path) for path in trade_files]
        surface_trade_ready = any(info["surface_trade_schema_ready"] for info in trade_infos)
        rows.append(
            {
                "metric_parent": str(metric_parent),
                "metric_path": str(metric_path),
                "artifact_dir": str(parent_dir),
                "config_row_count": int(len(group)),
                "max_negative_month_count": int(
                    numeric_series(group, "negative_month_count", default=0.0).max()
                ),
                "max_support_sufficient_negative_count": int(
                    numeric_series(group, "support_sufficient_negative_count", default=0.0).max()
                ),
                "max_support_limited_negative_count": int(
                    numeric_series(group, "support_limited_negative_count", default=0.0).max()
                ),
                "min_month_pnl": float(numeric_series(group, "min_month_pnl", default=0.0).min()),
                "best_total_adjusted_pnl_sum": float(
                    numeric_series(group, "total_adjusted_pnl_sum", default=0.0).max()
                ),
                "trade_file_count": int(len(trade_infos)),
                "surface_trade_schema_ready": bool(surface_trade_ready),
                "surface_trade_files": ";".join(
                    info["trade_file_name"]
                    for info in trade_infos
                    if info["surface_trade_schema_ready"]
                ),
                "trade_schema_statuses": ";".join(
                    sorted(set(info["trade_schema_status"] for info in trade_infos))
                ),
                "trade_missing_required_columns_any": ";".join(
                    sorted(
                        set(
                            part
                            for info in trade_infos
                            for part in str(info["trade_missing_required_columns"]).split(";")
                            if part
                        )
                    )
                ),
                **config_info,
            }
        )
    output = pd.DataFrame(rows)
    if not target_summary.empty:
        output = output.merge(target_summary, on="metric_parent", how="left")
    for column in [
        "support_sufficient_target_row_count",
        "support_sufficient_target_identity_count",
    ]:
        if column in output.columns:
            output[column] = numeric_series(output, column, default=0.0).astype(int)
    output["surface_ready_without_conversion"] = (
        output["config_surface_ready"].astype(bool)
        & output["surface_trade_schema_ready"].astype(bool)
    )
    output["needs_trade_schema_conversion"] = (
        output["trade_file_count"].gt(0)
        & ~output["surface_trade_schema_ready"].astype(bool)
    )
    output["needs_surface_config"] = ~output["config_surface_ready"].astype(bool)
    return output.sort_values(
        [
            "surface_ready_without_conversion",
            "max_support_sufficient_negative_count",
            "support_sufficient_target_identity_count",
            "trade_file_count",
            "best_total_adjusted_pnl_sum",
        ],
        ascending=[False, False, False, False, False],
    )


def trade_file_summary(config_summary: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, row in config_summary[["metric_parent", "metric_path"]].drop_duplicates().iterrows():
        parent_dir = resolve_path(str(row["metric_path"])).parent
        for trade_file in candidate_trade_files(parent_dir):
            info = inspect_trade_file(trade_file)
            rows.append(
                {
                    "metric_parent": str(row["metric_parent"]),
                    "artifact_dir": str(parent_dir),
                    **info,
                }
            )
    return pd.DataFrame(rows)


def target_rows(inventory: pd.DataFrame) -> pd.DataFrame:
    frame = inventory.copy()
    frame["support_sufficient_negative_month"] = frame[
        "support_sufficient_negative_month"
    ].astype(bool)
    keep = frame[frame["support_sufficient_negative_month"]].copy()
    columns = [
        "metric_parent",
        "metric_path",
        "role",
        "family",
        "month",
        "variant",
        "candidate",
        "entry_block_rule",
        "month_pnl",
        "trade_count",
        "long_trade_count",
        "short_trade_count",
        "extra_trades_needed",
    ]
    return keep[[column for column in columns if column in keep.columns]].sort_values(
        ["metric_parent", "month_pnl", "role", "month"]
    )


def run_diagnostics(args: argparse.Namespace) -> Path:
    inventory_dir = resolve_path(args.inventory_dir)
    config_summary, inventory = load_inventory(inventory_dir)
    parents = parent_summary(config_summary, inventory)
    trades = trade_file_summary(config_summary)
    targets = target_rows(inventory)

    run_dir = make_run_dir(resolve_path(args.output_root), args.run_label)
    parents.to_csv(run_dir / "surface_artifact_readiness_parent_summary.csv", index=False)
    trades.to_csv(run_dir / "surface_artifact_readiness_trade_files.csv", index=False)
    targets.to_csv(run_dir / "surface_artifact_readiness_support_targets.csv", index=False)
    meta = {
        "inventory_dir": inventory_dir,
        "surface_config_keys": sorted(SURFACE_CONFIG_KEYS),
        "surface_trade_columns": sorted(SURFACE_TRADE_COLUMNS),
        "note": (
            "This diagnostic finds artifacts with support-sufficient negative months and "
            "checks whether their nearby config/trade files can be used directly by the "
            "support-sufficient selector surface. It does not run a policy."
        ),
    }
    (run_dir / "surface_artifact_readiness_meta.json").write_text(
        json.dumps(meta, indent=2, default=local_json_default) + "\n",
        encoding="utf-8",
    )

    print("Surface artifact readiness parent summary:")
    display = [
        "metric_parent",
        "max_support_sufficient_negative_count",
        "support_sufficient_target_identity_count",
        "trade_file_count",
        "surface_trade_schema_ready",
        "config_surface_ready",
        "surface_ready_without_conversion",
        "needs_trade_schema_conversion",
        "needs_surface_config",
        "trade_missing_required_columns_any",
    ]
    print(parents[[column for column in display if column in parents.columns]].head(int(args.print_rows)).to_string(index=False))
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory-dir", type=Path, default=DEFAULT_INVENTORY_DIR)
    parser.add_argument("--output-root", type=Path, default=ROOT / "data/reports/backtests")
    parser.add_argument(
        "--run-label",
        default="entry_ev_surface_artifact_readiness_diagnostics",
    )
    parser.add_argument("--print-rows", type=int, default=20)
    return parser


def main(argv: list[str] | None = None) -> int:
    run_diagnostics(build_parser().parse_args(argv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
