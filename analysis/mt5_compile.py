from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path

if Path(sys.path[0] if sys.path else "").resolve() == Path(__file__).resolve().parent:
    sys.path.pop(0)

import subprocess
from datetime import datetime
from typing import Any

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analysis.market_data import TIME_FORMAT
from analysis.mt5_compile_status import compile_status, default_items, default_mt5_root


DEFAULT_OUTPUT_JSON = "runtime/latest_mt5_compile_run.json"
DEFAULT_OUTPUT_MD = "runtime/latest_mt5_compile_run.md"
DEFAULT_STATUS_JSON = "runtime/latest_mt5_compile_status.json"
DEFAULT_STATUS_MD = "runtime/latest_mt5_compile_status.md"


def default_wine_path() -> Path:
    return Path("/Applications/MetaTrader 5.app/Contents/SharedSupport/wine/bin/wine")


def default_wineprefix() -> Path:
    return Path.home() / "Library/Application Support/net.metaquotes.wine.metatrader5"


def mt5_root_to_drive_c(mt5_root: Path) -> Path:
    mt5_root = mt5_root.expanduser().resolve()
    for parent in (mt5_root, *mt5_root.parents):
        if parent.name.lower() == "drive_c":
            return parent
    raise ValueError(f"MT5 root is not inside a drive_c prefix: {mt5_root}")


def windows_path(path: str | Path, *, drive_c_root: str | Path) -> str:
    raw = Path(path).expanduser().resolve()
    drive_c = Path(drive_c_root).expanduser().resolve()
    try:
        relative = raw.relative_to(drive_c)
    except ValueError as exc:
        raise ValueError(f"{raw} is not under {drive_c}") from exc
    return "C:\\" + "\\".join(relative.parts)


def mt5_relative_windows_path(path: str | Path, *, mt5_root: str | Path) -> str:
    raw = Path(path).expanduser().resolve()
    root = Path(mt5_root).expanduser().resolve()
    try:
        relative = raw.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"{raw} is not under {root}") from exc
    return "\\".join(relative.parts)


def build_metaeditor_command(
    *,
    wine_path: str | Path,
    mt5_root: str | Path,
    source_path: str | Path,
    log_path: str | Path,
) -> list[str]:
    mt5 = Path(mt5_root).expanduser()
    drive_c = mt5_root_to_drive_c(mt5)
    metaeditor = windows_path(mt5 / "metaeditor64.exe", drive_c_root=drive_c)
    source = mt5_relative_windows_path(source_path, mt5_root=mt5)
    log = mt5_relative_windows_path(log_path, mt5_root=mt5)
    return [
        str(Path(wine_path).expanduser()),
        metaeditor,
        f"/compile:{source}",
        f"/log:{log}",
    ]


def selected_items(names: list[str] | None) -> list[dict[str, str]]:
    items = default_items()
    if not names:
        return items
    requested = {name.lower() for name in names}
    selected = [item for item in items if item["name"].lower() in requested or item["kind"].lower() in requested]
    missing = requested - {item["name"].lower() for item in selected} - {item["kind"].lower() for item in selected}
    if missing:
        raise ValueError(f"unknown compile item(s): {', '.join(sorted(missing))}")
    return selected


def file_mtime(path: Path) -> float | None:
    return path.stat().st_mtime if path.exists() else None


def latest_metaeditor_lines(log_path: Path, needle: str, *, limit: int = 8) -> list[str]:
    if not log_path.exists():
        return []
    data = log_path.read_bytes()
    text = data.decode("utf-16le", errors="ignore")
    lines = [line for line in text.splitlines() if needle in line or "Compile" in line and needle.replace(".mq5", "") in line]
    return lines[-limit:]


def metaeditor_log_candidates(*, compile_log: Path, mt5_root: Path) -> list[dict[str, Any]]:
    candidates = [
        ("compile_log", compile_log),
        ("metaeditor_log", mt5_root / "logs" / "metaeditor.log"),
    ]
    return [
        {
            "kind": kind,
            "path": str(path),
            "exists": path.exists(),
        }
        for kind, path in candidates
    ]


def run_compile(
    *,
    workspace_root: str | Path = ".",
    mt5_root: str | Path | None = None,
    wine_path: str | Path | None = None,
    wineprefix: str | Path | None = None,
    item_names: list[str] | None = None,
    timeout_seconds: int = 90,
    dry_run: bool = False,
) -> dict[str, Any]:
    workspace = Path(workspace_root).resolve()
    mt5 = Path(mt5_root).expanduser() if mt5_root else default_mt5_root()
    wine = Path(wine_path).expanduser() if wine_path else default_wine_path()
    prefix = Path(wineprefix).expanduser() if wineprefix else default_wineprefix()
    items = selected_items(item_names)
    started_at = time.time()
    runs: list[dict[str, Any]] = []

    for item in items:
        workspace_source = workspace / item["workspace_source"]
        mt5_source = mt5 / item["mt5_source"]
        mt5_binary = mt5 / item["mt5_binary"]
        log_path = mt5 / "logs" / f"compile_{item['name']}.log"
        before_mtime = file_mtime(mt5_binary)
        command = build_metaeditor_command(
            wine_path=wine,
            mt5_root=mt5,
            source_path=mt5_source,
            log_path=log_path,
        )
        run_payload: dict[str, Any] = {
            "kind": item["kind"],
            "name": item["name"],
            "source": str(mt5_source),
            "workspace_source": str(workspace_source),
            "binary": str(mt5_binary),
            "log": str(log_path),
            "command": command,
            "before_binary_mtime": datetime.fromtimestamp(before_mtime).strftime(TIME_FORMAT)
            if before_mtime
            else None,
            "before_binary_mtime_epoch": before_mtime,
        }
        if workspace_source.exists():
            if dry_run:
                run_payload["source_sync"] = "dry_run_skipped"
            else:
                mt5_source.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(workspace_source, mt5_source)
                run_payload["source_sync"] = "copied"
        else:
            run_payload["source_sync"] = "missing_workspace_source"
        if dry_run:
            run_payload.update({"skipped": True, "returncode": None})
        else:
            env = os.environ.copy()
            env["WINEPREFIX"] = str(prefix)
            try:
                process = subprocess.run(
                    command,
                    cwd=str(mt5),
                    env=env,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=timeout_seconds,
                    check=False,
                )
                run_payload.update(
                    {
                        "skipped": False,
                        "returncode": process.returncode,
                        "stdout_tail": process.stdout[-2000:],
                        "stderr_tail": process.stderr[-4000:],
                    }
                )
            except subprocess.TimeoutExpired as exc:
                run_payload.update(
                    {
                        "skipped": False,
                        "returncode": None,
                        "timeout": True,
                        "stdout_tail": (exc.stdout or "")[-2000:] if isinstance(exc.stdout, str) else "",
                        "stderr_tail": (exc.stderr or "")[-4000:] if isinstance(exc.stderr, str) else "",
                    }
                )
        after_mtime = file_mtime(mt5_binary)
        metaeditor_log_path = mt5 / "logs" / "metaeditor.log"
        run_payload.update(
            {
                "after_binary_mtime": datetime.fromtimestamp(after_mtime).strftime(TIME_FORMAT)
                if after_mtime
                else None,
                "after_binary_mtime_epoch": after_mtime,
                "binary_updated": after_mtime is not None and before_mtime is not None and after_mtime > before_mtime,
                "metaeditor_log_candidates": metaeditor_log_candidates(compile_log=log_path, mt5_root=mt5),
                "compile_log_lines": latest_metaeditor_lines(log_path, mt5_source.name),
                "metaeditor_log_lines": latest_metaeditor_lines(metaeditor_log_path, mt5_source.name),
            }
        )
        runs.append(run_payload)

    status = compile_status(workspace_root=workspace, mt5_root=mt5, items=items)
    return {
        "generated_at": datetime.now().strftime(TIME_FORMAT),
        "workspace_root": str(workspace),
        "mt5_root": str(mt5),
        "wine": str(wine),
        "wineprefix": str(prefix),
        "dry_run": dry_run,
        "elapsed_seconds": round(time.time() - started_at, 2),
        "runs": runs,
        "status": status,
        "ok": bool(status.get("all_sources_synced")) and bool(status.get("all_compiled_fresh")),
    }


def write_json(path: str | Path, payload: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_markdown(path: str | Path, payload: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(format_markdown(payload), encoding="utf-8")


def write_status_files(json_path: str | Path, md_path: str | Path, status: dict[str, Any]) -> None:
    from analysis.mt5_compile_status import write_json as write_status_json
    from analysis.mt5_compile_status import write_markdown as write_status_markdown

    write_status_json(json_path, status)
    write_status_markdown(md_path, status)


def format_markdown(payload: dict[str, Any]) -> str:
    status = payload.get("status") if isinstance(payload.get("status"), dict) else {}
    lines = [
        "# MT5 Compile Run",
        "",
        f"- Generated at: {payload.get('generated_at')}",
        f"- OK: {payload.get('ok')}",
        f"- Dry run: {payload.get('dry_run')}",
        f"- MT5 root: {payload.get('mt5_root')}",
        f"- Wine: {payload.get('wine')}",
        f"- Sources synced: {status.get('all_sources_synced')}",
        f"- Compiled fresh: {status.get('all_compiled_fresh')}",
        "",
        "| kind | name | returncode | updated | before | after |",
        "|---|---|---:|---:|---|---|",
    ]
    for row in payload.get("runs", []):
        if not isinstance(row, dict):
            continue
        lines.append(
            f"| {row.get('kind')} | {row.get('name')} | {row.get('returncode')} | "
            f"{row.get('binary_updated')} | {row.get('before_binary_mtime')} | {row.get('after_binary_mtime')} |"
        )
    lines.extend(["", "## Compile Log Evidence", ""])
    for row in payload.get("runs", []):
        if not isinstance(row, dict):
            continue
        candidates = row.get("metaeditor_log_candidates") if isinstance(row.get("metaeditor_log_candidates"), list) else []
        candidate_text = ", ".join(
            f"{item.get('kind')}={'yes' if item.get('exists') else 'no'}"
            for item in candidates
            if isinstance(item, dict)
        )
        lines.append(
            f"- {row.get('name')}: log={row.get('log')}, candidates={candidate_text or 'missing'}, "
            f"compile_log_lines={len(row.get('compile_log_lines', [])) if isinstance(row.get('compile_log_lines'), list) else 0}, "
            f"metaeditor_log_lines={len(row.get('metaeditor_log_lines', [])) if isinstance(row.get('metaeditor_log_lines'), list) else 0}"
        )
    lines.extend(["", "## Notes", ""])
    if payload.get("ok"):
        lines.append("- Compiled binaries are fresh enough for Strategy Tester.")
    else:
        lines.append("- Compile verification failed. Do not run optimization until `Compiled fresh` is true, unless diagnosing with `--allow-stale-compile`.")
    return "\n".join(lines) + "\n"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run MetaEditor compile and verify MT5 .ex5 freshness.")
    parser.add_argument("--workspace-root", default=".")
    parser.add_argument("--mt5-root", default=str(default_mt5_root()))
    parser.add_argument("--wine", default=str(default_wine_path()))
    parser.add_argument("--wineprefix", default=str(default_wineprefix()))
    parser.add_argument("--item", action="append", default=None, help="Item kind/name to compile. Defaults to all.")
    parser.add_argument("--timeout-seconds", type=int, default=90)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", default=DEFAULT_OUTPUT_MD)
    parser.add_argument("--status-output-json", default=DEFAULT_STATUS_JSON)
    parser.add_argument("--status-output-md", default=DEFAULT_STATUS_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = run_compile(
        workspace_root=args.workspace_root,
        mt5_root=args.mt5_root,
        wine_path=args.wine,
        wineprefix=args.wineprefix,
        item_names=args.item,
        timeout_seconds=args.timeout_seconds,
        dry_run=args.dry_run,
    )
    write_json(args.output_json, payload)
    write_markdown(args.output_md, payload)
    write_status_files(args.status_output_json, args.status_output_md, payload["status"])
    print(
        json.dumps(
            {
                "ok": payload["ok"],
                "compiled_fresh": payload["status"].get("all_compiled_fresh"),
                "output_json": args.output_json,
                "output_md": args.output_md,
                "status_output_json": args.status_output_json,
                "status_output_md": args.status_output_md,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if payload["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
