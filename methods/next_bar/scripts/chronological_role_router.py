#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path

from trade_data.next_bar_router import run_chronological_role_router


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Select fixed confidence candidates from prior OOS folds by role."
    )
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--baseline-dir", type=Path, action="append", required=True)
    parser.add_argument("--timeframe", type=int, default=15)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    project_root = args.project_root.resolve()
    registry = args.registry
    if not registry.is_absolute():
        registry = project_root / registry
    baseline_dirs = [
        path if path.is_absolute() else project_root / path
        for path in args.baseline_dir
    ]
    output_dir = args.output_dir
    if not output_dir.is_absolute():
        output_dir = project_root / output_dir
    report = run_chronological_role_router(
        project_root,
        registry,
        baseline_dirs,
        output_dir,
        args.timeframe,
    )
    summary = {
        role: {
            "static_champion": values["static_champion"],
            "confirmation": values["periods"].get("confirmation"),
        }
        for role, values in report["roles"].items()
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
