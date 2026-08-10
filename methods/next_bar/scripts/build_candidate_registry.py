from __future__ import annotations

import argparse
import json
from pathlib import Path

from trade_data.next_bar_registry import (
    DEFAULT_DEVELOPMENT_FOLDS,
    build_candidate_registry,
)


def comma_strings(value: str) -> tuple[str, ...]:
    output = tuple(item.strip() for item in value.split(",") if item.strip())
    if not output:
        raise argparse.ArgumentTypeError("value must contain at least one item")
    return output


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Recompute and rank fixed next-bar confidence candidates."
    )
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument(
        "--config-dir", type=Path, default=Path("methods/next_bar/config")
    )
    parser.add_argument("--baseline-dir", type=Path, action="append", required=True)
    parser.add_argument("--timeframe", type=int, default=15)
    parser.add_argument(
        "--development-folds",
        type=comma_strings,
        default=DEFAULT_DEVELOPMENT_FOLDS,
    )
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    project_root = args.project_root.resolve()
    config_dir = args.config_dir
    if not config_dir.is_absolute():
        config_dir = project_root / config_dir
    baseline_dirs = [
        path if path.is_absolute() else project_root / path
        for path in args.baseline_dir
    ]
    output = args.output
    if not output.is_absolute():
        output = project_root / output
    registry = build_candidate_registry(
        project_root=project_root,
        config_dir=config_dir,
        baseline_dirs=baseline_dirs,
        timeframe=args.timeframe,
        development_folds=args.development_folds,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(registry, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"output": str(output), "roles": registry["roles"]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
