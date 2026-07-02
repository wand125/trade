#!/usr/bin/env python3
"""Apply observable confidence gates to an existing overlay trade path."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from trade_data.backtest import make_run_dir  # noqa: E402

from entry_ev_month_warmup_overlay import (  # noqa: E402
    bool_series,
    filter_values,
    local_json_default,
    parse_csv,
    safe_max_drawdown_from_trades,
)


DEFAULT_CONFIDENCE_RULES = (
    "none,"
    "rank_ge0p55,rank_ge0p60,rank_ge0p65,"
    "sidegap_ge0,sidegap_ge0p10,sidegap_ge0p25,"
    "lossprob_le0p30,lossprob_le0p35,lossprob_le0p40,"
    "taken_ev_ge8,taken_ev_ge10,taken_ev_ge12,"
    "fixed240_pred_ge0,fixed720_pred_ge0,fixed720_pred_ge2,"
    "rank_ge0p55_sidegap_ge0p10,"
    "rank_ge0p55_lossprob_le0p35,"
    "sidegap_ge0p10_lossprob_le0p35,"
    "rank_ge0p55_fixed720_pred_ge0"
)
REQUIRED_COLUMNS = {
    "role",
    "month",
    "candidate",
    "direction",
    "entry_decision_timestamp",
    "adjusted_pnl",
}
GROUP_COLUMNS = ["source", "role", "family", "selector_variant", "candidate", "month"]
RULE_COLUMNS = {
    "rank_ge": "pred_taken_entry_local_rank",
    "sidegap_ge": "pred_side_confidence_gap",
    "lossprob_le": "selected_loss_first_prob",
    "taken_ev_ge": "pred_taken_ev",
    "fixed240_pred_ge": "selected_fixed_240m_pred_pnl",
    "fixed720_pred_ge": "selected_fixed_720m_pred_pnl",
}


def numeric_series(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    values = pd.to_numeric(frame[column], errors="coerce")
    return values.replace([np.inf, -np.inf], np.nan).fillna(default).astype(float)


def parse_threshold(value: str) -> float:
    return float(value.replace("p", "."))


def read_overlay_trades(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    missing = sorted(REQUIRED_COLUMNS - set(frame.columns))
    if missing:
        raise ValueError(f"{path} missing columns: {', '.join(missing)}")
    output = frame.copy()
    if "selector_variant" not in output.columns:
        if "variant" not in output.columns:
            raise ValueError(f"{path} missing columns: selector_variant or variant")
        output["selector_variant"] = output["variant"]
    for column, fallback in [("source", "unknown"), ("family", "unknown")]:
        if column not in output.columns:
            output[column] = fallback
    output["source"] = output["source"].astype(str)
    output["role"] = output["role"].astype(str)
    output["family"] = output["family"].astype(str)
    output["selector_variant"] = output["selector_variant"].astype(str)
    output["candidate"] = output["candidate"].astype(str)
    output["month"] = output["month"].astype(str).str.slice(0, 7)
    output["direction"] = output["direction"].astype(str).str.lower()
    output["adjusted_pnl"] = numeric_series(output, "adjusted_pnl")
    output["entry_blocked"] = bool_series(output, "entry_blocked")
    for column in ["entry_decision_timestamp", "entry_timestamp", "exit_timestamp"]:
        if column in output.columns:
            output[column] = pd.to_datetime(output[column], utc=True, errors="coerce")
    return output.sort_values(GROUP_COLUMNS + ["entry_decision_timestamp"]).reset_index(drop=True)


def confidence_variant(selector_variant: str, rule: str) -> str:
    return f"{selector_variant}__confgate_{rule}"


def atomic_pass_mask(frame: pd.DataFrame, atom: str) -> pd.Series:
    for prefix, column in RULE_COLUMNS.items():
        if atom.startswith(prefix):
            if column not in frame.columns:
                raise ValueError(f"rule {atom} requires missing column: {column}")
            threshold = parse_threshold(atom.removeprefix(prefix))
            values = numeric_series(frame, column, default=np.nan)
            if prefix.endswith("_ge"):
                return values.ge(threshold)
            if prefix.endswith("_le"):
                return values.le(threshold)
    raise ValueError(f"unknown confidence gate atom: {atom}")


def confidence_pass_mask(frame: pd.DataFrame, rule: str) -> pd.Series:
    rule = rule.strip()
    if rule == "none":
        return pd.Series(True, index=frame.index, dtype=bool)
    atoms = rule.split("_")
    combined_atoms: list[str] = []
    index = 0
    while index < len(atoms):
        if index + 1 >= len(atoms):
            raise ValueError(f"invalid confidence gate rule: {rule}")
        if atoms[index] == "rank":
            combined_atoms.append("rank_" + atoms[index + 1])
            index += 2
        elif atoms[index] == "sidegap":
            combined_atoms.append("sidegap_" + atoms[index + 1])
            index += 2
        elif atoms[index] == "lossprob":
            combined_atoms.append("lossprob_" + atoms[index + 1])
            index += 2
        elif atoms[index] == "taken" and index + 2 < len(atoms) and atoms[index + 1] == "ev":
            combined_atoms.append("taken_ev_" + atoms[index + 2])
            index += 3
        elif atoms[index] == "fixed240" and index + 2 < len(atoms) and atoms[index + 1] == "pred":
            combined_atoms.append("fixed240_pred_" + atoms[index + 2])
            index += 3
        elif atoms[index] == "fixed720" and index + 2 < len(atoms) and atoms[index + 1] == "pred":
            combined_atoms.append("fixed720_pred_" + atoms[index + 2])
            index += 3
        else:
            raise ValueError(f"invalid confidence gate rule: {rule}")

    passed = pd.Series(True, index=frame.index, dtype=bool)
    for atom in combined_atoms:
        passed &= atomic_pass_mask(frame, atom)
    return passed


def apply_confidence_gate_rule(group: pd.DataFrame, rule: str) -> pd.DataFrame:
    frame = group.sort_values("entry_decision_timestamp").copy()
    eligible = ~frame["entry_blocked"].fillna(False).astype(bool)
    passed = confidence_pass_mask(frame, rule)
    frame["confidence_gate_rule"] = rule
    frame["confidence_gate_passed"] = passed
    frame["confidence_gate_blocked"] = eligible & ~passed
    frame["final_blocked"] = frame["entry_blocked"].astype(bool) | frame["confidence_gate_blocked"]
    frame["input_selector_variant"] = frame["selector_variant"]
    frame["variant"] = frame["selector_variant"].map(lambda value: confidence_variant(value, rule))
    return frame


def summarize_confidence_gate(
    trades: pd.DataFrame,
    rules: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    annotated_frames: list[pd.DataFrame] = []
    monthly_rows: list[dict[str, Any]] = []
    for rule in rules:
        annotated = pd.concat(
            [
                apply_confidence_gate_rule(group, rule)
                for _, group in trades.groupby(GROUP_COLUMNS, dropna=False, sort=False)
            ],
            ignore_index=True,
        )
        annotated_frames.append(annotated)
        for key, group in annotated.groupby(
            GROUP_COLUMNS + ["variant", "confidence_gate_rule"],
            dropna=False,
        ):
            key_columns = GROUP_COLUMNS + ["variant", "confidence_gate_rule"]
            key_row = dict(zip(key_columns, key, strict=True))
            input_available = group[~group["entry_blocked"].astype(bool)]
            kept = group[~group["final_blocked"].astype(bool)]
            gate_blocked = group[group["confidence_gate_blocked"].astype(bool)]
            long_count = int(kept["direction"].eq("long").sum()) if len(kept) else 0
            short_count = int(kept["direction"].eq("short").sum()) if len(kept) else 0
            trade_count = int(len(kept))
            monthly_rows.append(
                {
                    "source": key_row["source"],
                    "role": key_row["role"],
                    "family": key_row["family"],
                    "variant": key_row["variant"],
                    "candidate": key_row["candidate"],
                    "month": key_row["month"],
                    "confidence_gate_rule": key_row["confidence_gate_rule"],
                    "input_selector_variant": key_row["selector_variant"],
                    "total_adjusted_pnl": float(kept["adjusted_pnl"].sum())
                    if trade_count
                    else 0.0,
                    "trade_count": trade_count,
                    "input_available_trade_count": int(len(input_available)),
                    "confidence_blocked_trade_count": int(len(gate_blocked)),
                    "confidence_blocked_adjusted_pnl": float(gate_blocked["adjusted_pnl"].sum())
                    if len(gate_blocked)
                    else 0.0,
                    "input_total_adjusted_pnl": float(input_available["adjusted_pnl"].sum())
                    if len(input_available)
                    else 0.0,
                    "pnl_delta_vs_input": float(
                        (kept["adjusted_pnl"].sum() if trade_count else 0.0)
                        - (input_available["adjusted_pnl"].sum() if len(input_available) else 0.0)
                    ),
                    "long_trade_count": long_count,
                    "short_trade_count": short_count,
                    "max_side_trade_share": float(max(long_count, short_count) / trade_count)
                    if trade_count
                    else 0.0,
                    "max_drawdown": safe_max_drawdown_from_trades(kept),
                }
            )
    annotated_trades = pd.concat(annotated_frames, ignore_index=True)
    monthly = pd.DataFrame(monthly_rows)
    if monthly.empty:
        return annotated_trades, monthly
    monthly = monthly.sort_values(
        ["confidence_gate_rule", "variant", "candidate", "role", "month"]
    )
    return annotated_trades.reset_index(drop=True), monthly.reset_index(drop=True)


def summarize_selection(monthly: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    if monthly.empty:
        return pd.DataFrame()
    for key, group in monthly.groupby(["variant", "candidate", "confidence_gate_rule"], dropna=False):
        variant, candidate, rule = key
        role_group = group.groupby("role", dropna=False).agg(
            role_total_pnl=("total_adjusted_pnl", "sum"),
            role_trade_count=("trade_count", "sum"),
        )
        rows.append(
            {
                "variant": variant,
                "candidate": candidate,
                "confidence_gate_rule": rule,
                "total_adjusted_pnl_sum": float(group["total_adjusted_pnl"].sum()),
                "input_total_adjusted_pnl_sum": float(group["input_total_adjusted_pnl"].sum()),
                "pnl_delta_vs_input_sum": float(group["pnl_delta_vs_input"].sum()),
                "trade_count_sum": int(group["trade_count"].sum()),
                "confidence_blocked_trade_count_sum": int(
                    group["confidence_blocked_trade_count"].sum()
                ),
                "confidence_blocked_adjusted_pnl_sum": float(
                    group["confidence_blocked_adjusted_pnl"].sum()
                ),
                "month_pnl_min": float(group["total_adjusted_pnl"].min()),
                "role_total_pnl_min": float(role_group["role_total_pnl"].min())
                if len(role_group)
                else 0.0,
                "positive_role_count": int((role_group["role_total_pnl"] > 0).sum())
                if len(role_group)
                else 0,
                "role_count": int(len(role_group)),
                "max_side_trade_share": float(group["max_side_trade_share"].max()),
                "max_drawdown_max": float(group["max_drawdown"].max()),
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["month_pnl_min", "total_adjusted_pnl_sum"],
        ascending=[False, False],
    )


def summarize_feature_bins(trades: pd.DataFrame, *, bin_count: int) -> pd.DataFrame:
    eligible = trades[~trades["entry_blocked"].astype(bool)].copy()
    rows: list[dict[str, Any]] = []
    feature_columns = [
        "selected_loss_first_prob",
        "pred_side_confidence_gap",
        "pred_taken_entry_local_rank",
        "pred_taken_ev",
        "selected_fixed_240m_pred_pnl",
        "selected_fixed_720m_pred_pnl",
    ]
    for column in feature_columns:
        if column not in eligible.columns:
            continue
        values = numeric_series(eligible, column, default=np.nan)
        valid = eligible[values.notna()].copy()
        if valid.empty:
            continue
        valid[column] = values.loc[valid.index]
        try:
            valid["feature_bin"] = pd.qcut(
                valid[column].rank(method="first"),
                q=min(bin_count, len(valid)),
                labels=False,
                duplicates="drop",
            )
        except ValueError:
            continue
        for bin_id, group in valid.groupby("feature_bin", dropna=True):
            losses = group[group["adjusted_pnl"].lt(0.0)]
            rows.append(
                {
                    "feature": column,
                    "bin": int(bin_id),
                    "trade_count": int(len(group)),
                    "value_min": float(group[column].min()),
                    "value_max": float(group[column].max()),
                    "total_adjusted_pnl": float(group["adjusted_pnl"].sum()),
                    "mean_adjusted_pnl": float(group["adjusted_pnl"].mean()),
                    "loss_rate": float(len(losses) / len(group)) if len(group) else 0.0,
                }
            )
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(["feature", "bin"]).reset_index(drop=True)


def run_overlay(args: argparse.Namespace) -> Path:
    trades = read_overlay_trades(args.overlay_trades)
    trades = filter_values(trades, "selector_variant", parse_csv(args.selector_variants))
    trades = filter_values(trades, "candidate", parse_csv(args.candidates))
    if trades.empty:
        raise ValueError("no trades left after filters")
    rules = parse_csv(args.confidence_rules)
    run_dir = make_run_dir(args.output_dir, args.label)
    annotated_trades, monthly = summarize_confidence_gate(trades, rules)
    selection = summarize_selection(monthly)
    feature_bins = summarize_feature_bins(trades, bin_count=args.bin_count)

    annotated_trades.to_csv(run_dir / "confidence_gate_overlay_trades.csv", index=False)
    monthly.to_csv(run_dir / "confidence_gate_overlay_monthly_metrics.csv", index=False)
    monthly.to_csv(run_dir / "confidence_gate_overlay_selector_monthly_metrics.csv", index=False)
    selection.to_csv(run_dir / "confidence_gate_overlay_selection_summary.csv", index=False)
    feature_bins.to_csv(run_dir / "confidence_feature_bins.csv", index=False)
    (run_dir / "config.json").write_text(
        json.dumps(
            {
                "overlay_trades": args.overlay_trades,
                "confidence_rules": rules,
                "selector_variants": parse_csv(args.selector_variants),
                "candidates": parse_csv(args.candidates),
                "bin_count": args.bin_count,
            },
            indent=2,
            default=local_json_default,
        ),
        encoding="utf-8",
    )

    print("Confidence gate overlay selection summary:")
    if selection.empty:
        print("<empty>")
    else:
        print(
            selection[
                [
                    "confidence_gate_rule",
                    "total_adjusted_pnl_sum",
                    "pnl_delta_vs_input_sum",
                    "month_pnl_min",
                    "role_total_pnl_min",
                    "trade_count_sum",
                    "confidence_blocked_trade_count_sum",
                    "confidence_blocked_adjusted_pnl_sum",
                    "max_side_trade_share",
                ]
            ]
            .head(args.print_top)
            .to_string(index=False)
        )
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--overlay-trades", type=Path, required=True)
    parser.add_argument("--confidence-rules", default=DEFAULT_CONFIDENCE_RULES)
    parser.add_argument("--selector-variants", default="")
    parser.add_argument("--candidates", default="")
    parser.add_argument("--bin-count", type=int, default=5)
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="entry_ev_confidence_gate_overlay")
    parser.add_argument("--print-top", type=int, default=20)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    run_overlay(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
