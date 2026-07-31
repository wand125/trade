#!/usr/bin/env python3
"""Split entry-block overlay effects into discovery and holdout cohorts."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from trade_data.backtest import json_default, make_run_dir  # noqa: E402


REQUIRED_COLUMNS = {
    "source",
    "role",
    "family",
    "selector_variant",
    "entry_block_rule",
    "entry_blocked",
    "month",
    "direction",
    "adjusted_pnl",
}
SUMMARY_COLUMNS = [
    "base_variant",
    "candidate",
    "entry_block_rule",
    "scope",
    "input_trade_count",
    "trade_count",
    "blocked_trade_count",
    "blocked_loss_count",
    "blocked_win_count",
    "input_adjusted_pnl",
    "total_adjusted_pnl",
    "blocked_adjusted_pnl",
    "pnl_delta_vs_input",
    "affected_role_count",
    "affected_family_count",
    "affected_month_count",
]


def parse_csv(value: str) -> list[str]:
    return [part.strip() for part in value.split(",") if part.strip()]


def local_json_default(value: Any) -> Any:
    try:
        return json_default(value)
    except TypeError:
        pass
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, np.bool_):
        return bool(value)
    raise TypeError(f"cannot serialize {type(value).__name__}")


def bool_series(values: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(values):
        return values.fillna(False).astype(bool)
    text = values.fillna(False).astype(str).str.lower()
    return text.isin({"1", "true", "yes", "y"})


def numeric_series(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    values = pd.to_numeric(frame[column], errors="coerce")
    return values.replace([np.inf, -np.inf], np.nan).fillna(default).astype(float)


def derive_base_variant(selector_variant: str, entry_block_rule: str) -> str:
    suffix = f"__entryblock_{entry_block_rule}"
    if selector_variant.endswith(suffix):
        return selector_variant[: -len(suffix)]
    return selector_variant


def read_overlay_trades(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    missing = sorted(REQUIRED_COLUMNS - set(frame.columns))
    if missing:
        raise ValueError(f"{path} missing columns: {', '.join(missing)}")
    output = frame.copy()
    for column in ["source", "role", "family", "selector_variant", "entry_block_rule"]:
        output[column] = output[column].fillna("").astype(str)
    if "candidate" in output.columns:
        output["candidate"] = output["candidate"].fillna("").astype(str)
    else:
        output["candidate"] = ""
    output["month"] = output["month"].fillna("").astype(str).str.slice(0, 7)
    output["direction"] = output["direction"].fillna("").astype(str)
    output["entry_blocked"] = bool_series(output["entry_blocked"])
    output["adjusted_pnl"] = numeric_series(output, "adjusted_pnl", default=0.0)
    output["base_variant"] = [
        derive_base_variant(selector_variant, rule)
        for selector_variant, rule in zip(
            output["selector_variant"],
            output["entry_block_rule"],
            strict=True,
        )
    ]
    return output


def filter_overlay(
    frame: pd.DataFrame,
    rules: list[str],
    selector_variant_contains: list[str],
) -> pd.DataFrame:
    output = frame.copy()
    if rules:
        output = output[output["entry_block_rule"].isin(rules)].copy()
    for pattern in selector_variant_contains:
        output = output[
            output["selector_variant"].str.contains(pattern, regex=False, na=False)
        ].copy()
    return output.reset_index(drop=True)


def discovery_mask(
    frame: pd.DataFrame,
    roles: list[str],
    families: list[str],
    sources: list[str],
) -> pd.Series:
    mask = pd.Series(False, index=frame.index, dtype=bool)
    if roles:
        mask |= frame["role"].isin(roles)
    if families:
        mask |= frame["family"].isin(families)
    if sources:
        mask |= frame["source"].isin(sources)
    if not roles and not families and not sources:
        raise ValueError("at least one discovery role, family, or source is required")
    return mask


def summarize_one_scope(frame: pd.DataFrame, scope: str) -> dict[str, Any]:
    blocked = frame[frame["entry_blocked"]].copy()
    kept = frame[~frame["entry_blocked"]].copy()
    input_total = float(frame["adjusted_pnl"].sum())
    kept_total = float(kept["adjusted_pnl"].sum()) if len(kept) else 0.0
    return {
        "scope": scope,
        "input_trade_count": int(len(frame)),
        "trade_count": int(len(kept)),
        "blocked_trade_count": int(len(blocked)),
        "blocked_loss_count": int((blocked["adjusted_pnl"] < 0.0).sum()) if len(blocked) else 0,
        "blocked_win_count": int((blocked["adjusted_pnl"] > 0.0).sum()) if len(blocked) else 0,
        "input_adjusted_pnl": input_total,
        "total_adjusted_pnl": kept_total,
        "blocked_adjusted_pnl": float(blocked["adjusted_pnl"].sum()) if len(blocked) else 0.0,
        "pnl_delta_vs_input": float(kept_total - input_total),
        "affected_role_count": int(blocked["role"].nunique()) if len(blocked) else 0,
        "affected_family_count": int(blocked["family"].nunique()) if len(blocked) else 0,
        "affected_month_count": int(blocked["month"].nunique()) if len(blocked) else 0,
    }


def summarize_holdout_support(frame: pd.DataFrame, discovery: pd.Series) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    group_columns = ["base_variant", "candidate", "entry_block_rule"]
    for key, group in frame.groupby(group_columns, dropna=False, sort=False):
        base_variant, candidate, rule = key
        group_discovery = discovery.loc[group.index]
        for scope, scoped in [
            ("all", group),
            ("discovery", group[group_discovery]),
            ("holdout", group[~group_discovery]),
        ]:
            summary = summarize_one_scope(scoped, scope)
            rows.append(
                {
                    "base_variant": base_variant,
                    "candidate": candidate,
                    "entry_block_rule": rule,
                    **summary,
                }
            )
    if not rows:
        return pd.DataFrame(columns=SUMMARY_COLUMNS)
    return pd.DataFrame(rows)[SUMMARY_COLUMNS].sort_values(
        ["base_variant", "entry_block_rule", "scope"]
    )


def summarize_by_role(frame: pd.DataFrame, discovery: pd.Series) -> pd.DataFrame:
    work = frame.copy()
    work["scope"] = np.where(discovery, "discovery", "holdout")
    rows: list[dict[str, Any]] = []
    group_columns = ["base_variant", "candidate", "entry_block_rule", "scope", "role", "family"]
    for key, group in work.groupby(group_columns, dropna=False, sort=False):
        base_variant, candidate, rule, scope, role, family = key
        summary = summarize_one_scope(group, scope)
        rows.append(
            {
                "base_variant": base_variant,
                "candidate": candidate,
                "entry_block_rule": rule,
                "scope": scope,
                "role": role,
                "family": family,
                **{
                    key_name: summary[key_name]
                    for key_name in [
                        "input_trade_count",
                        "trade_count",
                        "blocked_trade_count",
                        "blocked_loss_count",
                        "blocked_win_count",
                        "input_adjusted_pnl",
                        "total_adjusted_pnl",
                        "blocked_adjusted_pnl",
                        "pnl_delta_vs_input",
                    ]
                },
            }
        )
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values(
        ["base_variant", "entry_block_rule", "scope", "role", "family"]
    )


def blocked_trades(frame: pd.DataFrame, discovery: pd.Series) -> pd.DataFrame:
    output = frame[frame["entry_blocked"]].copy()
    if output.empty:
        return output
    output["scope"] = np.where(discovery.loc[output.index], "discovery", "holdout")
    preferred = [
        "base_variant",
        "candidate",
        "entry_block_rule",
        "scope",
        "source",
        "role",
        "family",
        "month",
        "entry_timestamp",
        "direction",
        "adjusted_pnl",
        "combined_regime",
        "session_regime",
        "selected_fixed_60m_pred_pnl",
        "selected_fixed_60m_actual_pnl",
        "selected_loss_first_prob",
        "pred_side_confidence_gap",
        "pred_taken_ev",
    ]
    columns = [column for column in preferred if column in output.columns]
    return output[columns].sort_values(
        ["entry_block_rule", "scope", "role", "month", "adjusted_pnl"]
    )


def run_diagnostics(args: argparse.Namespace) -> Path:
    overlay = read_overlay_trades(args.overlay_trades)
    rules = parse_csv(args.rules)
    selector_variant_contains = parse_csv(args.selector_variant_contains)
    filtered = filter_overlay(overlay, rules, selector_variant_contains)
    discovery = discovery_mask(
        filtered,
        parse_csv(args.discovery_roles),
        parse_csv(args.discovery_families),
        parse_csv(args.discovery_sources),
    )
    summary = summarize_holdout_support(filtered, discovery)
    by_role = summarize_by_role(filtered, discovery)
    blocked = blocked_trades(filtered, discovery)

    run_dir = make_run_dir(args.output_dir, args.label)
    summary.to_csv(run_dir / "entry_block_holdout_support_summary.csv", index=False)
    by_role.to_csv(run_dir / "entry_block_holdout_support_by_role.csv", index=False)
    blocked.to_csv(run_dir / "entry_block_holdout_blocked_trades.csv", index=False)
    (run_dir / "config.json").write_text(
        json.dumps(
            {
                "overlay_trades": args.overlay_trades,
                "rules": rules,
                "selector_variant_contains": selector_variant_contains,
                "discovery_roles": parse_csv(args.discovery_roles),
                "discovery_families": parse_csv(args.discovery_families),
                "discovery_sources": parse_csv(args.discovery_sources),
            },
            indent=2,
            default=local_json_default,
        ),
        encoding="utf-8",
    )

    print("Entry-block holdout support summary:")
    print(summary.head(args.print_top).to_string(index=False))
    print(f"artifacts: {run_dir}")
    return run_dir


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--overlay-trades", type=Path, required=True)
    parser.add_argument("--rules", default="")
    parser.add_argument("--selector-variant-contains", default="")
    parser.add_argument("--discovery-roles", default="")
    parser.add_argument("--discovery-families", default="")
    parser.add_argument("--discovery-sources", default="")
    parser.add_argument("--output-dir", type=Path, default=Path("data/reports/backtests"))
    parser.add_argument("--label", default="entry_ev_entry_block_holdout_support_diagnostics")
    parser.add_argument("--print-top", type=int, default=30)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    run_diagnostics(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
