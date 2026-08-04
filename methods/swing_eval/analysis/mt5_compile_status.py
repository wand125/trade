from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analysis.market_data import TIME_FORMAT


DEFAULT_OUTPUT_JSON = "runtime/latest_mt5_compile_status.json"
DEFAULT_OUTPUT_MD = "runtime/latest_mt5_compile_status.md"


def default_mt5_root() -> Path:
    return (
        Path.home()
        / "Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5"
    )


def default_items() -> list[dict[str, str]]:
    return [
        {
            "kind": "expert",
            "name": "AI_Bridge_Advisor",
            "workspace_source": "methods/swing_eval/mt5/Experts/AI_Bridge_Advisor.mq5",
            "mt5_source": "MQL5/Experts/AI_Bridge_Advisor.mq5",
            "mt5_binary": "MQL5/Experts/AI_Bridge_Advisor.ex5",
        },
        {
            "kind": "expert",
            "name": "Swing_Evaluation_Trader",
            "workspace_source": "methods/swing_eval/mt5/Experts/Swing_Evaluation_Trader.mq5",
            "mt5_source": "MQL5/Experts/Swing_Evaluation_Trader.mq5",
            "mt5_binary": "MQL5/Experts/Swing_Evaluation_Trader.ex5",
        },
        {
            "kind": "indicator",
            "name": "Swing_Evaluation_Predictor",
            "workspace_source": "methods/swing_eval/mt5/Indicators/Swing_Evaluation_Predictor.mq5",
            "mt5_source": "MQL5/Indicators/Swing_Evaluation_Predictor.mq5",
            "mt5_binary": "MQL5/Indicators/Swing_Evaluation_Predictor.ex5",
        },
    ]


def compile_status(
    *,
    workspace_root: str | Path = ".",
    mt5_root: str | Path | None = None,
    items: list[dict[str, str]] | None = None,
    tester_set_items: list[str | Path] | None = None,
    tester_config_items: list[str | Path] | None = None,
) -> dict[str, Any]:
    workspace = Path(workspace_root).resolve()
    mt5 = Path(mt5_root).expanduser() if mt5_root else default_mt5_root()
    rows = [compile_item_status(workspace, mt5, item) for item in (items or default_items())]
    tester_sets = [
        tester_set_status(workspace, mt5, item)
        for item in (tester_set_items if tester_set_items is not None else default_tester_set_items(workspace))
    ]
    tester_configs = [
        tester_config_status(workspace, mt5, item)
        for item in (
            tester_config_items if tester_config_items is not None else default_tester_config_items(workspace)
        )
    ]
    tester_config_references = [
        tester_config_reference_status(workspace, mt5, item)
        for item in (
            tester_config_items if tester_config_items is not None else default_tester_config_items(workspace)
        )
    ]
    return {
        "generated_at": datetime.now().strftime(TIME_FORMAT),
        "workspace_root": str(workspace),
        "mt5_root": str(mt5),
        "all_sources_synced": all(bool(row.get("source_synced")) for row in rows),
        "all_compiled_fresh": all(bool(row.get("compiled_fresh")) for row in rows),
        "all_tester_sets_synced": all(bool(row.get("synced")) for row in tester_sets),
        "all_tester_configs_synced": all(bool(row.get("synced")) for row in tester_configs),
        "all_required_tester_config_references_ready": all(
            bool(row.get("ready")) or bool(row.get("generated_set_missing"))
            for row in tester_config_references
        ),
        "items": rows,
        "tester_sets": tester_sets,
        "tester_configs": tester_configs,
        "tester_config_references": tester_config_references,
    }


def default_tester_set_items(workspace_root: str | Path = ".") -> list[Path]:
    tester_sets_dir = Path(workspace_root) / "methods" / "swing_eval" / "mt5" / "TesterSets"
    if not tester_sets_dir.exists():
        return []
    return sorted(tester_sets_dir.glob("*.set"))


def default_tester_config_items(workspace_root: str | Path = ".") -> list[Path]:
    tester_configs_dir = Path(workspace_root) / "methods" / "swing_eval" / "mt5" / "TesterConfigs"
    if not tester_configs_dir.exists():
        return []
    return sorted(tester_configs_dir.glob("*.ini"))


def compile_item_status(workspace_root: Path, mt5_root: Path, item: dict[str, str]) -> dict[str, Any]:
    workspace_source = workspace_root / item["workspace_source"]
    mt5_source = mt5_root / item["mt5_source"]
    mt5_binary = mt5_root / item["mt5_binary"]
    workspace_info = path_info(workspace_source)
    mt5_source_info = path_info(mt5_source)
    binary_info = path_info(mt5_binary)
    source_synced = (
        workspace_info.get("exists") is True
        and mt5_source_info.get("exists") is True
        and workspace_info.get("sha256") == mt5_source_info.get("sha256")
    )
    newest_source_mtime = max(
        float(workspace_info.get("mtime_epoch") or 0.0),
        float(mt5_source_info.get("mtime_epoch") or 0.0),
    )
    binary_mtime = float(binary_info.get("mtime_epoch") or 0.0)
    compiled_fresh = binary_info.get("exists") is True and newest_source_mtime > 0.0 and binary_mtime >= newest_source_mtime
    status = item_status(
        workspace_exists=workspace_info.get("exists") is True,
        mt5_source_exists=mt5_source_info.get("exists") is True,
        binary_exists=binary_info.get("exists") is True,
        source_synced=source_synced,
        compiled_fresh=compiled_fresh,
    )
    return {
        "kind": item["kind"],
        "name": item["name"],
        "status": status,
        "source_synced": source_synced,
        "compiled_fresh": compiled_fresh,
        "stale_seconds": round(max(newest_source_mtime - binary_mtime, 0.0), 1) if binary_mtime else None,
        "workspace_source": workspace_info,
        "mt5_source": mt5_source_info,
        "mt5_binary": binary_info,
    }


def tester_set_status(workspace_root: Path, mt5_root: Path, item: str | Path) -> dict[str, Any]:
    raw = Path(item)
    workspace_set = raw if raw.is_absolute() else workspace_root / raw
    if not workspace_set.exists() and raw.parent == Path("."):
        workspace_set = workspace_root / "methods" / "swing_eval" / "mt5" / "TesterSets" / raw.name
    mt5_set = mt5_root / "MQL5" / "Profiles" / "Tester" / workspace_set.name
    workspace_info = path_info(workspace_set)
    mt5_info = path_info(mt5_set)
    synced = (
        workspace_info.get("exists") is True
        and mt5_info.get("exists") is True
        and workspace_info.get("sha256") == mt5_info.get("sha256")
    )
    return {
        "kind": "tester_set",
        "name": workspace_set.name,
        "status": tester_set_item_status(
            workspace_exists=workspace_info.get("exists") is True,
            mt5_exists=mt5_info.get("exists") is True,
            synced=synced,
        ),
        "synced": synced,
        "workspace_set": workspace_info,
        "mt5_set": mt5_info,
    }


def tester_config_status(workspace_root: Path, mt5_root: Path, item: str | Path) -> dict[str, Any]:
    raw = Path(item)
    workspace_config = raw if raw.is_absolute() else workspace_root / raw
    if not workspace_config.exists() and raw.parent == Path("."):
        workspace_config = workspace_root / "methods" / "swing_eval" / "mt5" / "TesterConfigs" / raw.name
    mt5_config = mt5_root / "MQL5" / "Profiles" / "Tester" / workspace_config.name
    workspace_info = path_info(workspace_config)
    mt5_info = path_info(mt5_config)
    synced = (
        workspace_info.get("exists") is True
        and mt5_info.get("exists") is True
        and workspace_info.get("sha256") == mt5_info.get("sha256")
    )
    return {
        "kind": "tester_config",
        "name": workspace_config.name,
        "status": tester_config_item_status(
            workspace_exists=workspace_info.get("exists") is True,
            mt5_exists=mt5_info.get("exists") is True,
            synced=synced,
        ),
        "synced": synced,
        "workspace_config": workspace_info,
        "mt5_config": mt5_info,
    }


def get_ini_value(text: str, section: str, key: str) -> str:
    current = ""
    target_section = section.lower()
    target_key = key.lower()
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("[") and line.endswith("]"):
            current = line[1:-1].strip().lower()
            continue
        if current == target_section and line.lower().startswith(f"{target_key}="):
            return line.split("=", 1)[1].strip()
    return ""


def generated_tester_set_name(name: str) -> bool:
    return name in {
        "Swing_Evaluation_Trader_buy_score_weight_refit.set",
        "Swing_Evaluation_Trader_sell_score_weight_refit.set",
    }


def resolve_config_expert_parameters_set(workspace_root: Path, workspace_config: Path, expert_parameters: str) -> Path:
    raw = Path(str(expert_parameters or "").strip()).expanduser()
    if raw.is_absolute():
        return raw
    candidates = [
        workspace_root / "methods" / "swing_eval" / "mt5" / "TesterSets" / raw.name,
        workspace_config.parent / raw.name,
        workspace_root / raw.name,
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def tester_config_reference_status(workspace_root: Path, mt5_root: Path, item: str | Path) -> dict[str, Any]:
    raw = Path(item)
    workspace_config = raw if raw.is_absolute() else workspace_root / raw
    if not workspace_config.exists() and raw.parent == Path("."):
        workspace_config = workspace_root / "methods" / "swing_eval" / "mt5" / "TesterConfigs" / raw.name
    config_info = path_info(workspace_config)
    expert_parameters = ""
    if config_info.get("exists") is True:
        try:
            expert_parameters = get_ini_value(workspace_config.read_text(encoding="utf-8"), "Tester", "ExpertParameters")
        except OSError:
            expert_parameters = ""
    set_name = Path(expert_parameters).name if expert_parameters else ""
    workspace_set = (
        resolve_config_expert_parameters_set(workspace_root, workspace_config, expert_parameters)
        if expert_parameters
        else None
    )
    mt5_set = mt5_root / "MQL5" / "Profiles" / "Tester" / set_name if set_name else None
    workspace_info = path_info(workspace_set) if workspace_set else {"exists": False, "path": ""}
    mt5_info = path_info(mt5_set) if mt5_set else {"exists": False, "path": ""}
    synced = (
        workspace_info.get("exists") is True
        and mt5_info.get("exists") is True
        and workspace_info.get("sha256") == mt5_info.get("sha256")
    )
    generated_missing = (
        bool(set_name)
        and generated_tester_set_name(set_name)
        and workspace_info.get("exists") is not True
    )
    status = tester_config_reference_item_status(
        config_exists=config_info.get("exists") is True,
        expert_parameters=expert_parameters,
        workspace_exists=workspace_info.get("exists") is True,
        mt5_exists=mt5_info.get("exists") is True,
        synced=synced,
        generated_missing=generated_missing,
    )
    return {
        "kind": "tester_config_reference",
        "name": workspace_config.name,
        "status": status,
        "ready": status == "ready",
        "generated_set_missing": generated_missing,
        "expert_parameters": expert_parameters,
        "workspace_config": config_info,
        "workspace_set": workspace_info,
        "mt5_set": mt5_info,
        "synced": synced,
    }


def tester_set_item_status(*, workspace_exists: bool, mt5_exists: bool, synced: bool) -> str:
    if not workspace_exists:
        return "missing_workspace_set"
    if not mt5_exists:
        return "missing_mt5_set"
    if not synced:
        return "set_not_synced"
    return "ready"


def tester_config_item_status(*, workspace_exists: bool, mt5_exists: bool, synced: bool) -> str:
    if not workspace_exists:
        return "missing_workspace_config"
    if not mt5_exists:
        return "missing_mt5_config"
    if not synced:
        return "config_not_synced"
    return "ready"


def tester_config_reference_item_status(
    *,
    config_exists: bool,
    expert_parameters: str,
    workspace_exists: bool,
    mt5_exists: bool,
    synced: bool,
    generated_missing: bool,
) -> str:
    if not config_exists:
        return "missing_workspace_config"
    if not expert_parameters:
        return "missing_expert_parameters"
    if generated_missing:
        return "generated_set_missing"
    if not workspace_exists:
        return "missing_workspace_set"
    if not mt5_exists:
        return "missing_mt5_set"
    if not synced:
        return "set_not_synced"
    return "ready"


def item_status(
    *,
    workspace_exists: bool,
    mt5_source_exists: bool,
    binary_exists: bool,
    source_synced: bool,
    compiled_fresh: bool,
) -> str:
    if not workspace_exists:
        return "missing_workspace_source"
    if not mt5_source_exists:
        return "missing_mt5_source"
    if not source_synced:
        return "source_not_synced"
    if not binary_exists:
        return "missing_binary"
    if not compiled_fresh:
        return "stale_binary"
    return "ready"


def path_info(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"path": str(path), "exists": False}
    stat = path.stat()
    return {
        "path": str(path),
        "exists": True,
        "size": stat.st_size,
        "mtime": datetime.fromtimestamp(stat.st_mtime).strftime(TIME_FORMAT),
        "mtime_epoch": stat.st_mtime,
        "sha256": sha256(path),
    }


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: str | Path, summary: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"ok": True, "summary": summary}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_markdown(path: str | Path, summary: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(format_markdown(summary), encoding="utf-8")


def format_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# MT5 Compile Status",
        "",
        f"- Generated at: {summary.get('generated_at')}",
        f"- Workspace: {summary.get('workspace_root')}",
        f"- MT5 root: {summary.get('mt5_root')}",
        f"- Sources synced: {summary.get('all_sources_synced')}",
        f"- Compiled fresh: {summary.get('all_compiled_fresh')}",
        f"- Tester sets synced: {summary.get('all_tester_sets_synced')}",
        f"- Tester configs synced: {summary.get('all_tester_configs_synced')}",
        f"- Required tester config references ready: {summary.get('all_required_tester_config_references_ready')}",
        "",
        "| kind | name | status | source synced | compiled fresh | source mtime | binary mtime | stale seconds |",
        "|---|---|---|---:|---:|---|---|---:|",
    ]
    for row in summary.get("items", []):
        if not isinstance(row, dict):
            continue
        mt5_source = row.get("mt5_source") if isinstance(row.get("mt5_source"), dict) else {}
        binary = row.get("mt5_binary") if isinstance(row.get("mt5_binary"), dict) else {}
        lines.append(
            f"| {row.get('kind')} | {row.get('name')} | {row.get('status')} | "
            f"{row.get('source_synced')} | {row.get('compiled_fresh')} | "
            f"{mt5_source.get('mtime', '')} | {binary.get('mtime', '')} | {row.get('stale_seconds')} |"
        )
    lines.extend(
        [
            "",
            "## Tester Sets",
            "",
            "| name | status | synced | workspace mtime | MT5 mtime |",
            "|---|---|---:|---|---|",
        ]
    )
    for row in summary.get("tester_sets", []):
        if not isinstance(row, dict):
            continue
        workspace_set = row.get("workspace_set") if isinstance(row.get("workspace_set"), dict) else {}
        mt5_set = row.get("mt5_set") if isinstance(row.get("mt5_set"), dict) else {}
        lines.append(
            f"| {row.get('name')} | {row.get('status')} | {row.get('synced')} | "
            f"{workspace_set.get('mtime', '')} | {mt5_set.get('mtime', '')} |"
        )
    lines.extend(
        [
            "",
            "## Tester Configs",
            "",
            "| name | status | synced | workspace mtime | MT5 mtime |",
            "|---|---|---:|---|---|",
        ]
    )
    for row in summary.get("tester_configs", []):
        if not isinstance(row, dict):
            continue
        workspace_config = row.get("workspace_config") if isinstance(row.get("workspace_config"), dict) else {}
        mt5_config = row.get("mt5_config") if isinstance(row.get("mt5_config"), dict) else {}
        lines.append(
            f"| {row.get('name')} | {row.get('status')} | {row.get('synced')} | "
            f"{workspace_config.get('mtime', '')} | {mt5_config.get('mtime', '')} |"
        )
    lines.extend(
        [
            "",
            "## Tester Config ExpertParameters",
            "",
            "| config | ExpertParameters | status | ready | generated missing | synced | workspace set mtime | MT5 set mtime |",
            "|---|---|---|---:|---:|---:|---|---|",
        ]
    )
    for row in summary.get("tester_config_references", []):
        if not isinstance(row, dict):
            continue
        workspace_set = row.get("workspace_set") if isinstance(row.get("workspace_set"), dict) else {}
        mt5_set = row.get("mt5_set") if isinstance(row.get("mt5_set"), dict) else {}
        lines.append(
            f"| {row.get('name')} | {row.get('expert_parameters', '')} | {row.get('status')} | "
            f"{row.get('ready')} | {row.get('generated_set_missing')} | {row.get('synced')} | "
            f"{workspace_set.get('mtime', '')} | {mt5_set.get('mtime', '')} |"
        )
    return "\n".join(lines) + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check whether MT5 .ex5 binaries are fresh for the current .mq5 sources.")
    parser.add_argument("--workspace-root", default=".")
    parser.add_argument("--mt5-root", default=str(default_mt5_root()))
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", default=DEFAULT_OUTPUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    summary = compile_status(workspace_root=args.workspace_root, mt5_root=args.mt5_root)
    write_json(args.output_json, summary)
    write_markdown(args.output_md, summary)
    print(
        json.dumps(
            {
                "ok": True,
                "all_sources_synced": summary["all_sources_synced"],
                "all_compiled_fresh": summary["all_compiled_fresh"],
                "all_tester_sets_synced": summary["all_tester_sets_synced"],
                "all_tester_configs_synced": summary["all_tester_configs_synced"],
                "all_required_tester_config_references_ready": summary[
                    "all_required_tester_config_references_ready"
                ],
                "output_json": args.output_json,
                "output_md": args.output_md,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return (
        0
        if summary["all_sources_synced"]
        and summary["all_compiled_fresh"]
        and summary["all_tester_sets_synced"]
        and summary["all_tester_configs_synced"]
        and summary["all_required_tester_config_references_ready"]
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
