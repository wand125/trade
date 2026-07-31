from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analysis.mt5_tester_optimization_report import attach_set_pass_budget, write_markdown
from analysis.mt5_tester_run import resolve_expert_parameters_set, tester_config_metadata


def load_json(path: str | Path) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as handle:
        payload = json.load(handle)
    return payload if isinstance(payload, dict) else {}


def write_json(path: str | Path, payload: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def unwrap_summary_reference(payload: dict[str, Any]) -> dict[str, Any]:
    current = payload
    for _ in range(4):
        summary = current.get("summary")
        if not isinstance(summary, dict):
            break
        current = summary
    return current


def resolve_set_file_from_run(
    run_payload: dict[str, Any],
    *,
    explicit_set_file: str | Path | None = None,
    workspace_root: str | Path | None = None,
) -> Path | None:
    if explicit_set_file:
        return Path(explicit_set_file).expanduser()
    run_set_file = str(run_payload.get("set_file") or "").strip()
    if run_set_file:
        return Path(run_set_file).expanduser()
    config_path = str(run_payload.get("config_path") or "").strip()
    if not config_path:
        return None
    config = Path(config_path).expanduser()
    if not config.exists():
        return None
    root = workspace_root or run_payload.get("workspace_root") or config.parents[4]
    metadata = tester_config_metadata(config.read_text(encoding="utf-8"))
    return resolve_expert_parameters_set(
        workspace_root=root,
        config_path=config,
        expert_parameters=metadata.get("expert_parameters", ""),
    )


def backfill_pass_budget(
    optimization_payload: dict[str, Any],
    run_payload: dict[str, Any],
    *,
    set_file: str | Path | None = None,
    workspace_root: str | Path | None = None,
) -> dict[str, Any]:
    summary = unwrap_summary_reference(optimization_payload)
    if not summary:
        return optimization_payload
    run_summary = run_payload.get("optimization_summary")
    if "tester_xml" not in summary and isinstance(run_summary, dict) and isinstance(run_summary.get("tester_xml"), dict):
        summary["tester_xml"] = run_summary["tester_xml"]
    resolved_set = resolve_set_file_from_run(run_payload, explicit_set_file=set_file, workspace_root=workspace_root)
    attach_set_pass_budget(summary, resolved_set)
    return optimization_payload


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill MT5 optimization pass budget evidence into an existing report.")
    parser.add_argument("--optimization-json", required=True)
    parser.add_argument("--tester-run-json", required=True)
    parser.add_argument("--set-file", default="")
    parser.add_argument("--workspace-root", default="")
    parser.add_argument("--output-json", required=True)
    parser.add_argument("--output-md", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    optimization_payload = load_json(args.optimization_json)
    run_payload = load_json(args.tester_run_json)
    backfill_pass_budget(
        optimization_payload,
        run_payload,
        set_file=args.set_file or None,
        workspace_root=args.workspace_root or None,
    )
    summary = unwrap_summary_reference(optimization_payload)
    write_json(args.output_json, optimization_payload)
    write_markdown(args.output_md, summary)
    budget = summary.get("optimization_pass_budget") if isinstance(summary, dict) else {}
    print(
        json.dumps(
            {
                "ok": bool(isinstance(budget, dict) and budget.get("available")),
                "output_json": args.output_json,
                "output_md": args.output_md,
                "set_file": budget.get("set_file") if isinstance(budget, dict) else "",
                "estimated_full_factorial_passes": budget.get("estimated_full_factorial_passes")
                if isinstance(budget, dict)
                else None,
                "executed_tester_xml_rows": budget.get("executed_tester_xml_rows") if isinstance(budget, dict) else None,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
