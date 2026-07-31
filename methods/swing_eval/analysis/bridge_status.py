from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analysis.market_data import TIME_FORMAT


DEFAULT_OUTPUT_JSON = "runtime/latest_bridge_status.json"
DEFAULT_OUTPUT_MD = "runtime/latest_bridge_status.md"
DEFAULT_STATE_DIR = "runtime"
DEFAULT_BASE_URL = "http://127.0.0.1:8765"
DEFAULT_HTTP_TIMEOUT_SECONDS = 3.0
DEFAULT_MAX_SNAPSHOT_AGE_SECONDS = 5 * 60
DEFAULT_MAX_HISTORY_REQUEST_PENDING_SECONDS = 180
BRIDGE_LOG_LINE_RE = re.compile(
    r'^(?P<timestamp>\d{1,2}/[A-Za-z]{3}/\d{4} \d{2}:\d{2}:\d{2}) - '
    r'"(?P<method>[A-Z]+) (?P<path>[^" ]+) [^"]+" (?P<status_code>\d+)'
)
SNAPSHOT_POST_PATHS = {"/snapshot", "/ingest", "/analyze"}
HISTORY_CHUNK_POST_PATHS = {"/history-chunk", "/history_chunk"}
DEAL_HISTORY_CHUNK_POST_PATHS = {"/deal-history-chunk", "/deal_history_chunk"}
EA_POST_PATHS = SNAPSHOT_POST_PATHS | HISTORY_CHUNK_POST_PATHS | DEAL_HISTORY_CHUNK_POST_PATHS


def load_json_if_present(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return payload if isinstance(payload, dict) else {}


def file_summary(path: Path, *, now_epoch: float) -> dict[str, Any]:
    if not path.exists():
        return {
            "exists": False,
            "path": str(path),
            "modified_at": "",
            "mtime_epoch": None,
            "age_seconds": None,
        }
    mtime_epoch = path.stat().st_mtime
    age_seconds = max(0.0, now_epoch - mtime_epoch)
    return {
        "exists": True,
        "path": str(path),
        "modified_at": datetime.fromtimestamp(mtime_epoch).strftime(TIME_FORMAT),
        "mtime_epoch": round(mtime_epoch, 3),
        "age_seconds": round(age_seconds, 1),
    }


def http_get_json(url: str, *, timeout_seconds: float) -> dict[str, Any]:
    try:
        with urlopen(url, timeout=timeout_seconds) as response:
            status = getattr(response, "status", None) or response.getcode()
            body = response.read().decode("utf-8")
    except HTTPError as exc:
        return {"ok": False, "url": url, "status": exc.code, "error": f"HTTP {exc.code}"}
    except URLError as exc:
        return {"ok": False, "url": url, "status": None, "error": str(exc.reason)}
    except OSError as exc:
        return {"ok": False, "url": url, "status": None, "error": str(exc)}
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return {"ok": False, "url": url, "status": status, "error": "invalid_json", "body_preview": body[:200]}
    if not isinstance(payload, dict):
        return {"ok": False, "url": url, "status": status, "error": "json_not_object"}
    return {"ok": bool(payload.get("ok")), "url": url, "status": status, "payload": payload}


def bridge_process_summary() -> dict[str, Any]:
    try:
        completed = subprocess.run(
            ["ps", "aux"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        return {"ok": False, "running": False, "error": str(exc), "matches": []}
    if completed.returncode != 0:
        return {
            "ok": False,
            "running": False,
            "returncode": completed.returncode,
            "stderr": completed.stderr.strip(),
            "matches": [],
        }
    matches = [
        line
        for line in completed.stdout.splitlines()
        if "src/bridge/mt5_ai_bridge.py" in line or "mt5_ai_bridge.py" in line
    ]
    matches = [line for line in matches if "bridge_status.py" not in line]
    return {"ok": True, "running": bool(matches), "matches": matches[:5], "match_count": len(matches)}


def mt5_terminal_process_summary() -> dict[str, Any]:
    try:
        completed = subprocess.run(
            ["ps", "aux"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError as exc:
        return {"ok": False, "running": False, "error": str(exc), "matches": []}
    if completed.returncode != 0:
        return {
            "ok": False,
            "running": False,
            "returncode": completed.returncode,
            "stderr": completed.stderr.strip(),
            "matches": [],
        }
    matches = [
        line
        for line in completed.stdout.splitlines()
        if "terminal64.exe" in line or "/Applications/MetaTrader 5.app/" in line
    ]
    matches = [line for line in matches if "bridge_status.py" not in line]
    return {"ok": True, "running": bool(matches), "matches": matches[:5], "match_count": len(matches)}


def history_request_summary(
    state_dir: Path,
    *,
    now_epoch: float,
    max_pending_seconds: int,
) -> dict[str, Any]:
    request_path = state_dir / "history_request.json"
    done_path = state_dir / "history_request.done.json"
    request_payload = load_json_if_present(request_path)
    done_payload = load_json_if_present(done_path)
    request_file = file_summary(request_path, now_epoch=now_epoch)
    done_file = file_summary(done_path, now_epoch=now_epoch)
    request_id = str(request_payload.get("id") or "")
    done_id = str(done_payload.get("id") or "")
    done_matches_request = bool(request_id and done_id and request_id == done_id)
    pending = bool(request_file["exists"] and request_payload.get("status") == "pending" and not done_matches_request)
    pending_age = request_file.get("age_seconds") if pending else None
    stale_pending = bool(pending and pending_age is not None and float(pending_age) > max_pending_seconds)
    return {
        "request": {
            **request_file,
            "id": request_id,
            "hours": request_payload.get("hours"),
            "status": request_payload.get("status", ""),
            "requested_at": request_payload.get("requested_at"),
        },
        "done": {
            **done_file,
            "id": done_id,
            "hours": done_payload.get("hours"),
            "source_server_time": done_payload.get("source_server_time", ""),
        },
        "pending": pending,
        "pending_age_seconds": pending_age,
        "stale_pending": stale_pending,
        "done_matches_request": done_matches_request,
        "max_pending_seconds": max_pending_seconds,
    }


def snapshot_summary(
    state_dir: Path,
    *,
    now_epoch: float,
    max_snapshot_age_seconds: int,
) -> dict[str, Any]:
    path = state_dir / "latest_snapshot.json"
    payload = load_json_if_present(path)
    summary = file_summary(path, now_epoch=now_epoch)
    age_seconds = summary.get("age_seconds")
    fresh = bool(summary["exists"] and age_seconds is not None and float(age_seconds) <= max_snapshot_age_seconds)
    return {
        **summary,
        "fresh": fresh,
        "max_age_seconds": max_snapshot_age_seconds,
        "server_time": payload.get("server_time", ""),
        "symbol": payload.get("symbol", ""),
        "history_request_id": payload.get("history_request_id", ""),
        "history_hours": payload.get("history_hours", ""),
    }


def parse_bridge_log_timestamp(value: str) -> float | None:
    try:
        return datetime.strptime(value, "%d/%b/%Y %H:%M:%S").timestamp()
    except ValueError:
        return None


def bridge_log_event(line: str, *, now_epoch: float) -> dict[str, Any] | None:
    match = BRIDGE_LOG_LINE_RE.search(line)
    if not match:
        return None
    epoch = parse_bridge_log_timestamp(match.group("timestamp"))
    age_seconds = round(max(0.0, now_epoch - epoch), 1) if epoch is not None else None
    return {
        "line": line,
        "timestamp": match.group("timestamp"),
        "epoch": round(epoch, 3) if epoch is not None else None,
        "age_seconds": age_seconds,
        "method": match.group("method"),
        "path": match.group("path"),
        "status_code": int(match.group("status_code")),
    }


def compact_log_event(event: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(event, dict):
        return {}
    return {
        "timestamp": event.get("timestamp", ""),
        "epoch": event.get("epoch"),
        "age_seconds": event.get("age_seconds"),
        "method": event.get("method", ""),
        "path": event.get("path", ""),
        "status_code": event.get("status_code"),
        "line": event.get("line", ""),
    }


def bridge_log_activity_summary(
    lines: list[str],
    *,
    now_epoch: float,
    max_snapshot_age_seconds: int,
) -> dict[str, Any]:
    last_http_get: dict[str, Any] | None = None
    last_config_get: dict[str, Any] | None = None
    last_ea_post: dict[str, Any] | None = None
    last_snapshot_post: dict[str, Any] | None = None
    last_history_chunk_post: dict[str, Any] | None = None
    last_deal_history_chunk_post: dict[str, Any] | None = None
    parsed_count = 0
    ea_post_count = 0

    for line in lines:
        event = bridge_log_event(line, now_epoch=now_epoch)
        if event is None:
            continue
        parsed_count += 1
        method = str(event.get("method") or "")
        path = str(event.get("path") or "")
        if method == "GET":
            last_http_get = event
            if path == "/config":
                last_config_get = event
        if method != "POST":
            continue
        if path not in EA_POST_PATHS:
            continue
        ea_post_count += 1
        last_ea_post = event
        if path in SNAPSHOT_POST_PATHS:
            last_snapshot_post = event
        elif path in HISTORY_CHUNK_POST_PATHS:
            last_history_chunk_post = event
        elif path in DEAL_HISTORY_CHUNK_POST_PATHS:
            last_deal_history_chunk_post = event

    snapshot_age = last_snapshot_post.get("age_seconds") if isinstance(last_snapshot_post, dict) else None
    ea_post_age = last_ea_post.get("age_seconds") if isinstance(last_ea_post, dict) else None
    config_get_age = last_config_get.get("age_seconds") if isinstance(last_config_get, dict) else None
    config_get_recent = bool(
        isinstance(config_get_age, int | float) and config_get_age <= max_snapshot_age_seconds
    )
    ea_post_recent = bool(
        isinstance(ea_post_age, int | float) and ea_post_age <= max_snapshot_age_seconds
    )
    config_get_recent_but_ea_post_stale = bool(config_get_recent and not ea_post_recent)
    if ea_post_recent:
        ea_liveness_signal = "ea_post_recent"
    elif config_get_recent_but_ea_post_stale:
        ea_liveness_signal = "config_get_only_not_liveness"
    else:
        ea_liveness_signal = "no_recent_ea_post"
    if not lines:
        status = "log_empty"
    elif not last_ea_post:
        status = "no_ea_post_seen"
    elif not last_snapshot_post:
        status = "ea_post_seen_no_snapshot_post"
    elif isinstance(snapshot_age, int | float) and snapshot_age <= max_snapshot_age_seconds:
        status = "ea_snapshot_post_recent"
    elif isinstance(ea_post_age, int | float) and ea_post_age <= max_snapshot_age_seconds:
        status = "ea_post_recent_snapshot_stale"
    else:
        status = "ea_post_stale"

    return {
        "status": status,
        "parsed_line_count": parsed_count,
        "ea_post_count": ea_post_count,
        "max_snapshot_age_seconds": max_snapshot_age_seconds,
        "last_http_get": compact_log_event(last_http_get),
        "last_config_get": compact_log_event(last_config_get),
        "last_ea_post": compact_log_event(last_ea_post),
        "last_snapshot_post": compact_log_event(last_snapshot_post),
        "last_history_chunk_post": compact_log_event(last_history_chunk_post),
        "last_deal_history_chunk_post": compact_log_event(last_deal_history_chunk_post),
        "config_get_recent": config_get_recent,
        "ea_post_recent": ea_post_recent,
        "config_get_recent_but_ea_post_stale": config_get_recent_but_ea_post_stale,
        "ea_liveness_signal": ea_liveness_signal,
        "config_get_note": "GET /config may be produced by status checks; use EA POST freshness for EA liveness.",
    }


def bridge_log_summary(
    state_dir: Path,
    *,
    now_epoch: float,
    max_snapshot_age_seconds: int = DEFAULT_MAX_SNAPSHOT_AGE_SECONDS,
) -> dict[str, Any]:
    path = state_dir / "bridge.log"
    summary = file_summary(path, now_epoch=now_epoch)
    if not path.exists():
        return {
            **summary,
            "tail": [],
            "activity": bridge_log_activity_summary(
                [],
                now_epoch=now_epoch,
                max_snapshot_age_seconds=max_snapshot_age_seconds,
            ),
        }
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        lines = []
    return {
        **summary,
        "tail": lines[-10:],
        "activity": bridge_log_activity_summary(
            lines,
            now_epoch=now_epoch,
            max_snapshot_age_seconds=max_snapshot_age_seconds,
        ),
    }


def format_log_event_line(label: str, event: dict[str, Any]) -> str:
    if not isinstance(event, dict) or not event:
        return f"- {label}: not seen"
    return (
        f"- {label}: {event.get('timestamp', '')} "
        f"age_seconds={event.get('age_seconds')} "
        f"{event.get('method', '')} {event.get('path', '')} "
        f"status={event.get('status_code')}"
    )


def build_bridge_status(
    *,
    state_dir: str | Path = DEFAULT_STATE_DIR,
    base_url: str = DEFAULT_BASE_URL,
    http_timeout_seconds: float = DEFAULT_HTTP_TIMEOUT_SECONDS,
    max_snapshot_age_seconds: int = DEFAULT_MAX_SNAPSHOT_AGE_SECONDS,
    max_history_request_pending_seconds: int = DEFAULT_MAX_HISTORY_REQUEST_PENDING_SECONDS,
    now_epoch: float | None = None,
) -> dict[str, Any]:
    effective_now = time.time() if now_epoch is None else now_epoch
    state = Path(state_dir)
    health = http_get_json(f"{base_url.rstrip('/')}/health", timeout_seconds=http_timeout_seconds)
    config = http_get_json(f"{base_url.rstrip('/')}/config", timeout_seconds=http_timeout_seconds)
    process = bridge_process_summary()
    mt5_terminal = mt5_terminal_process_summary()
    snapshot = snapshot_summary(
        state,
        now_epoch=effective_now,
        max_snapshot_age_seconds=max_snapshot_age_seconds,
    )
    history_request = history_request_summary(
        state,
        now_epoch=effective_now,
        max_pending_seconds=max_history_request_pending_seconds,
    )
    log = bridge_log_summary(
        state,
        now_epoch=effective_now,
        max_snapshot_age_seconds=max_snapshot_age_seconds,
    )
    health_ok = bool(health.get("ok"))
    config_ok = bool(config.get("ok"))
    process_running = bool(process.get("running"))
    snapshot_fresh = bool(snapshot.get("fresh"))
    stale_pending = bool(history_request.get("stale_pending"))
    if not health_ok or not config_ok:
        operational_status = "bridge_unreachable"
    elif not process_running:
        operational_status = "bridge_process_not_found"
    elif not snapshot_fresh or stale_pending:
        operational_status = "ea_not_posting"
    else:
        operational_status = "ready"
    ok = operational_status == "ready"
    activity = log.get("activity") if isinstance(log.get("activity"), dict) else {}
    ea_attention_required = bool(operational_status == "ea_not_posting")
    if ea_attention_required and mt5_terminal.get("running") is True:
        ea_attention_reason = "mt5_terminal_running_but_ea_post_stale"
    elif ea_attention_required:
        ea_attention_reason = "ea_post_stale_or_snapshot_stale"
    else:
        ea_attention_reason = ""
    if operational_status == "bridge_unreachable":
        next_action = "Start or restart src/bridge/mt5_ai_bridge.py and verify /health and /config."
    elif operational_status == "bridge_process_not_found":
        next_action = "Start python3 src/bridge/mt5_ai_bridge.py."
    elif operational_status == "ea_not_posting":
        if mt5_terminal.get("running") is True:
            next_action = (
                "MT5 terminal is running but EA POST is stale; attach/restart the MT5 AI Bridge EA on a live "
                "chart so it polls /config and posts /snapshot/history chunks."
            )
        else:
            next_action = (
                "Keep the bridge running and attach/restart MT5 plus the MT5 AI Bridge EA so it polls /config "
                "and posts /snapshot/history chunks."
            )
    else:
        next_action = "Bridge and EA posting look current."
    return {
        "ok": ok,
        "generated_at": datetime.now().strftime(TIME_FORMAT),
        "base_url": base_url,
        "operational_status": operational_status,
        "next_action": next_action,
        "health": health,
        "config": config,
        "process": process,
        "mt5_terminal": mt5_terminal,
        "ea_attention": {
            "required": ea_attention_required,
            "reason": ea_attention_reason,
            "log_activity_status": activity.get("status", ""),
            "ea_liveness_signal": activity.get("ea_liveness_signal", ""),
            "config_get_recent": activity.get("config_get_recent", ""),
            "ea_post_recent": activity.get("ea_post_recent", ""),
            "config_get_recent_but_ea_post_stale": activity.get(
                "config_get_recent_but_ea_post_stale",
                "",
            ),
            "terminal_running": mt5_terminal.get("running"),
            "terminal_match_count": mt5_terminal.get("match_count"),
        },
        "latest_snapshot": snapshot,
        "history_request": history_request,
        "bridge_log": log,
        "thresholds": {
            "http_timeout_seconds": http_timeout_seconds,
            "max_snapshot_age_seconds": max_snapshot_age_seconds,
            "max_history_request_pending_seconds": max_history_request_pending_seconds,
        },
    }


def format_markdown(status: dict[str, Any]) -> str:
    health = status.get("health") if isinstance(status.get("health"), dict) else {}
    config = status.get("config") if isinstance(status.get("config"), dict) else {}
    process = status.get("process") if isinstance(status.get("process"), dict) else {}
    mt5_terminal = status.get("mt5_terminal") if isinstance(status.get("mt5_terminal"), dict) else {}
    ea_attention = status.get("ea_attention") if isinstance(status.get("ea_attention"), dict) else {}
    snapshot = status.get("latest_snapshot") if isinstance(status.get("latest_snapshot"), dict) else {}
    history = status.get("history_request") if isinstance(status.get("history_request"), dict) else {}
    request = history.get("request") if isinstance(history.get("request"), dict) else {}
    done = history.get("done") if isinstance(history.get("done"), dict) else {}
    log = status.get("bridge_log") if isinstance(status.get("bridge_log"), dict) else {}
    activity = log.get("activity") if isinstance(log.get("activity"), dict) else {}
    config_payload = config.get("payload") if isinstance(config.get("payload"), dict) else {}
    lines = [
        "# MT5 AI Bridge Status",
        "",
        f"- Generated at: {status.get('generated_at', '')}",
        f"- OK: {status.get('ok')}",
        f"- Operational status: {status.get('operational_status', '')}",
        f"- Next action: {status.get('next_action', '')}",
        f"- Base URL: {status.get('base_url', '')}",
        "",
        "## HTTP",
        "",
        f"- Health: ok={health.get('ok')}, status={health.get('status')}, error={health.get('error', '')}",
        f"- Config: ok={config.get('ok')}, status={config.get('status')}, error={config.get('error', '')}",
        f"- Config history request: hours={config_payload.get('history_hours', '')}, id={config_payload.get('history_request_id', '')}",
        "",
        "## Process",
        "",
        f"- Running: {process.get('running')}",
        f"- Match count: {process.get('match_count', 0)}",
    ]
    for line in process.get("matches", []) if isinstance(process.get("matches"), list) else []:
        lines.append(f"- `{line}`")
    lines.extend(
        [
            "",
            "## MT5 Terminal / EA",
            "",
            f"- Terminal running: {mt5_terminal.get('running')}",
            f"- Terminal match count: {mt5_terminal.get('match_count', 0)}",
            f"- EA attention required: {ea_attention.get('required')}",
            f"- EA attention reason: {ea_attention.get('reason', '')}",
            f"- EA liveness signal: {ea_attention.get('ea_liveness_signal', '')}",
            f"- Config GET recent but EA POST stale: {ea_attention.get('config_get_recent_but_ea_post_stale', '')}",
        ]
    )
    for line in mt5_terminal.get("matches", []) if isinstance(mt5_terminal.get("matches"), list) else []:
        lines.append(f"- `{line}`")
    lines.extend(
        [
            "",
            "## Latest Snapshot",
            "",
            f"- Fresh: {snapshot.get('fresh')}",
            f"- Age seconds: {snapshot.get('age_seconds')}",
            f"- Server time: {snapshot.get('server_time', '')}",
            f"- Symbol: {snapshot.get('symbol', '')}",
            f"- Modified: {snapshot.get('modified_at', '')}",
            "",
            "## History Request",
            "",
            f"- Pending: {history.get('pending')}",
            f"- Stale pending: {history.get('stale_pending')}",
            f"- Pending age seconds: {history.get('pending_age_seconds')}",
            f"- Request: id={request.get('id', '')}, hours={request.get('hours', '')}, status={request.get('status', '')}, modified={request.get('modified_at', '')}",
            f"- Done: id={done.get('id', '')}, hours={done.get('hours', '')}, source_server_time={done.get('source_server_time', '')}, modified={done.get('modified_at', '')}",
            "",
            "## Bridge Log",
            "",
            f"- Exists: {log.get('exists')}",
            f"- Age seconds: {log.get('age_seconds')}",
            f"- Modified: {log.get('modified_at', '')}",
            f"- Activity status: {activity.get('status', '')}",
            f"- Parsed lines: {activity.get('parsed_line_count', '')}",
            f"- EA POST count: {activity.get('ea_post_count', '')}",
            f"- EA liveness signal: {activity.get('ea_liveness_signal', '')}",
            f"- Config GET recent: {activity.get('config_get_recent', '')}",
            f"- EA POST recent: {activity.get('ea_post_recent', '')}",
            f"- Config GET recent but EA POST stale: {activity.get('config_get_recent_but_ea_post_stale', '')}",
            format_log_event_line(
                "Last EA POST",
                activity.get("last_ea_post") if isinstance(activity.get("last_ea_post"), dict) else {},
            ),
            format_log_event_line(
                "Last snapshot POST",
                activity.get("last_snapshot_post") if isinstance(activity.get("last_snapshot_post"), dict) else {},
            ),
            format_log_event_line(
                "Last history chunk POST",
                activity.get("last_history_chunk_post")
                if isinstance(activity.get("last_history_chunk_post"), dict)
                else {},
            ),
            format_log_event_line(
                "Last config GET",
                activity.get("last_config_get") if isinstance(activity.get("last_config_get"), dict) else {},
            ),
            f"- Config GET note: {activity.get('config_get_note', '')}",
        ]
    )
    tail = log.get("tail") if isinstance(log.get("tail"), list) else []
    if tail:
        lines.extend(["", "```text"])
        lines.extend(str(line) for line in tail)
        lines.append("```")
    return "\n".join(lines) + "\n"


def write_json(path: str | Path, payload: dict[str, Any]) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text(path: str | Path, text: str) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize local MT5 AI Bridge and EA posting health.")
    parser.add_argument("--state-dir", default=DEFAULT_STATE_DIR)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--http-timeout-seconds", type=float, default=DEFAULT_HTTP_TIMEOUT_SECONDS)
    parser.add_argument("--max-snapshot-age-seconds", type=int, default=DEFAULT_MAX_SNAPSHOT_AGE_SECONDS)
    parser.add_argument(
        "--max-history-request-pending-seconds",
        type=int,
        default=DEFAULT_MAX_HISTORY_REQUEST_PENDING_SECONDS,
    )
    parser.add_argument("--output-json", default=DEFAULT_OUTPUT_JSON)
    parser.add_argument("--output-md", default=DEFAULT_OUTPUT_MD)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    status = build_bridge_status(
        state_dir=args.state_dir,
        base_url=args.base_url,
        http_timeout_seconds=args.http_timeout_seconds,
        max_snapshot_age_seconds=args.max_snapshot_age_seconds,
        max_history_request_pending_seconds=args.max_history_request_pending_seconds,
    )
    write_json(args.output_json, status)
    write_text(args.output_md, format_markdown(status))
    print(
        json.dumps(
            {
                "ok": status["ok"],
                "operational_status": status["operational_status"],
                "next_action": status["next_action"],
                "output_json": args.output_json,
                "output_md": args.output_md,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if status["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
