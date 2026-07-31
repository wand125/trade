from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from analysis.dry_run_command import load_optional_json
from analysis.market_data import TIME_FORMAT


def build_audit(
    *,
    signal: dict[str, Any] | None,
    command: dict[str, Any] | None,
    trade_result: dict[str, Any] | None,
    max_age_seconds: int = 3600,
    now_epoch: int | None = None,
) -> dict[str, object]:
    now_epoch = int(time.time()) if now_epoch is None else now_epoch
    command_result = embedded_command_result(command)
    effective_result = command_result or (None if command_status(command) in {"rejected", "expired"} else trade_result)
    command_id = str(command.get("id", "")) if command else ""
    result_id = str(effective_result.get("id", "")) if effective_result else ""
    match = bool(command_id and result_id and command_id == result_id)
    outcome = classify_outcome(command, effective_result, match)
    dry_run_only = dry_run_safety_ok(command, effective_result)
    freshness = audit_freshness(command, effective_result, max_age_seconds=max_age_seconds, now_epoch=now_epoch)
    signal_command = signal_command_consistency(signal, command)
    return {
        "ok": True,
        "generated_at": datetime.now().strftime(TIME_FORMAT),
        "outcome": outcome,
        "dry_run_only": dry_run_only,
        "freshness": freshness,
        "signal_command": signal_command,
        "signal_command_match": signal_command["matched"],
        "signal": summarize_signal(signal),
        "command": summarize_command(command),
        "trade_result": summarize_trade_result(effective_result, command_id=command_id),
        "id_match": match,
        "risk_gate": command.get("risk_gate") if command else None,
        "notes": audit_notes(signal, command, effective_result, outcome, dry_run_only, match, freshness, signal_command),
    }


def classify_outcome(command: dict[str, Any] | None, result: dict[str, Any] | None, id_match: bool) -> str:
    if not command:
        return "missing_command"
    status = str(command.get("status", ""))
    if status == "rejected":
        return "blocked_before_ea"
    if status == "expired":
        return "command_expired_before_ea"
    if result and id_match:
        result_status = str(result.get("status", ""))
        if result_status == "dry_run_passed":
            return "ea_dry_run_passed"
        if result_status in {"rejected", "expired"}:
            return f"ea_{result_status}"
        return "ea_result_received"
    if result and not id_match:
        return "latest_result_unrelated"
    if status == "sent":
        return "sent_waiting_for_ea_result"
    if status == "pending":
        return "pending_ea_poll"
    return "unknown"


def command_status(command: dict[str, Any] | None) -> str:
    return str(command.get("status", "")).lower() if command else ""


def audit_notes(
    signal: dict[str, Any] | None,
    command: dict[str, Any] | None,
    result: dict[str, Any] | None,
    outcome: str,
    dry_run_only: bool,
    id_match: bool,
    freshness: dict[str, object],
    signal_command: dict[str, object],
) -> list[str]:
    notes: list[str] = []
    if signal and str(signal.get("action")) == "hold":
        notes.append("Signal is hold; no EA command should be sent.")
    if command and command.get("status") == "rejected":
        notes.append(f"Command was blocked before EA: {command.get('reason')}")
    if command and command.get("status") == "pending":
        notes.append("Command is waiting for EA polling.")
    if result and not id_match:
        notes.append("Latest EA result belongs to a different command id.")
    if not dry_run_only:
        notes.append("Dry-run safety failed; inspect command/result before proceeding.")
    if not freshness.get("fresh"):
        notes.append("Dry-run command/result is stale or missing timestamps.")
    if not signal_command.get("matched"):
        notes.append(f"Signal and command are not consistent: {signal_command.get('reason')}")
    if outcome == "ea_dry_run_passed":
        notes.append("EA validation passed and no order was sent.")
    return notes


def dry_run_safety_ok(command: dict[str, Any] | None, result: dict[str, Any] | None) -> bool:
    if command and command.get("dry_run") is not True:
        return False
    if result and result.get("dry_run") is not True:
        return False
    return True


def audit_freshness(
    command: dict[str, Any] | None,
    result: dict[str, Any] | None,
    *,
    max_age_seconds: int,
    now_epoch: int,
) -> dict[str, object]:
    command_time = latest_numeric_time(command, "received_at", "sent_at", "created_at") if command else None
    result_time = latest_numeric_time(result, "received_at") if result else None
    command_age = age_seconds(command_time, now_epoch)
    result_age = age_seconds(result_time, now_epoch)
    command_fresh = command_age is not None and 0 <= command_age <= max_age_seconds
    result_required = command_status(command) not in {"rejected", "expired"}
    result_fresh = result_age is not None and 0 <= result_age <= max_age_seconds
    return {
        "fresh": command_fresh and (result_fresh if result_required else True),
        "max_age_seconds": max_age_seconds,
        "now_epoch": now_epoch,
        "command_time": command_time,
        "command_age_seconds": command_age,
        "command_fresh": command_fresh,
        "result_required": result_required,
        "result_time": result_time,
        "result_age_seconds": result_age,
        "result_fresh": result_fresh,
    }


def signal_command_consistency(signal: dict[str, Any] | None, command: dict[str, Any] | None) -> dict[str, object]:
    if not signal:
        return {"matched": False, "reason": "missing signal"}
    if not command:
        return {"matched": False, "reason": "missing command"}
    signal_action = str(signal.get("action", "")).lower()
    command_action = str(command.get("action", "")).lower()
    command_status = str(command.get("status", "")).lower()
    if signal_action not in {"buy", "sell"}:
        matched = command_status == "rejected" and command_action in {"hold", signal_action, ""}
        return {
            "matched": matched,
            "reason": "non-tradable signal should not have a tradable EA command" if not matched else "non-tradable signal rejected",
            "signal_action": signal_action,
            "command_action": command_action,
            "command_status": command_status,
        }
    if command_action != signal_action:
        return {
            "matched": False,
            "reason": "action mismatch",
            "signal_action": signal_action,
            "command_action": command_action,
            "command_status": command_status,
        }
    signal_symbol = str(signal.get("symbol") or "")
    command_symbol = str(command.get("symbol") or "")
    if signal_symbol and command_symbol and signal_symbol != command_symbol:
        return {
            "matched": False,
            "reason": "symbol mismatch",
            "signal_action": signal_action,
            "command_action": command_action,
            "signal_symbol": signal_symbol,
            "command_symbol": command_symbol,
            "command_status": command_status,
        }
    source = command.get("source_signal")
    if isinstance(source, dict):
        source_time = str(source.get("candidate_time") or "")
        signal_time = str(signal.get("candidate_time") or "")
        if signal_time and source_time and signal_time != source_time:
            return {
                "matched": False,
                "reason": "candidate_time mismatch",
                "signal_candidate_time": signal_time,
                "command_candidate_time": source_time,
                "command_status": command_status,
            }
    return {
        "matched": True,
        "reason": "signal and command match",
        "signal_action": signal_action,
        "command_action": command_action,
        "signal_symbol": signal_symbol,
        "command_symbol": command_symbol,
        "command_status": command_status,
    }


def latest_numeric_time(payload: dict[str, Any] | None, *keys: str) -> int | None:
    if not payload:
        return None
    values: list[int] = []
    for key in keys:
        value = payload.get(key)
        if isinstance(value, bool) or value is None:
            continue
        try:
            values.append(int(float(value)))
        except (TypeError, ValueError):
            continue
    return max(values) if values else None


def age_seconds(timestamp: int | None, now_epoch: int) -> int | None:
    if timestamp is None:
        return None
    return now_epoch - timestamp


def summarize_signal(signal: dict[str, Any] | None) -> dict[str, object]:
    if not signal:
        return {"present": False}
    return {
        "present": True,
        "action": signal.get("action"),
        "mode": signal.get("mode"),
        "symbol": signal.get("symbol"),
        "score": signal.get("score"),
        "risk_reward": signal.get("risk_reward"),
        "pattern": signal.get("pattern"),
        "generated_at": signal.get("generated_at"),
        "valid_for_seconds": signal.get("valid_for_seconds"),
        "candidate_time": signal.get("candidate_time"),
        "latest_bar_time": signal.get("latest_bar_time"),
        "reason": signal.get("reason"),
    }


def summarize_command(command: dict[str, Any] | None) -> dict[str, object]:
    if not command:
        return {"present": False}
    source = command.get("source_signal") if isinstance(command.get("source_signal"), dict) else {}
    lot_policy = command.get("lot_policy") if isinstance(command.get("lot_policy"), dict) else {}
    return {
        "present": True,
        "id": command.get("id"),
        "status": command.get("status"),
        "action": command.get("action"),
        "symbol": command.get("symbol"),
        "volume": command.get("volume"),
        "sl": command.get("sl"),
        "tp": command.get("tp"),
        "max_spread_points": command.get("max_spread_points"),
        "dry_run": command.get("dry_run"),
        "created_at": command.get("created_at"),
        "expires_at": command.get("expires_at"),
        "reason": command.get("reason"),
        "lot_policy": lot_policy if lot_policy else None,
        "lot_policy_mode": lot_policy.get("mode") if lot_policy else None,
        "lot_policy_base_volume": lot_policy.get("base_volume") if lot_policy else None,
        "lot_policy_max_total_volume": lot_policy.get("max_total_volume") if lot_policy else None,
        "source_score": source.get("score"),
        "source_risk_reward": source.get("risk_reward"),
        "source_mode": source.get("mode"),
        "source_generated_at": source.get("generated_at"),
        "source_valid_for_seconds": source.get("valid_for_seconds"),
        "source_candidate_time": source.get("candidate_time"),
        "source_latest_bar_time": source.get("latest_bar_time"),
        "source_history_server_time": source.get("history_server_time"),
    }


def summarize_trade_result(result: dict[str, Any] | None, *, command_id: str) -> dict[str, object]:
    if not result:
        return {"present": False}
    return {
        "present": True,
        "id": result.get("id"),
        "matches_command": bool(command_id and str(result.get("id")) == command_id),
        "status": result.get("status"),
        "dry_run": result.get("dry_run"),
        "action": result.get("action"),
        "symbol": result.get("symbol"),
        "volume": result.get("volume"),
        "price": result.get("price"),
        "sl": result.get("sl"),
        "tp": result.get("tp"),
        "retcode": result.get("retcode"),
        "message": result.get("message"),
        "server_time": result.get("server_time"),
        "received_at": result.get("received_at"),
    }


def embedded_command_result(command: dict[str, Any] | None) -> dict[str, Any] | None:
    if command and isinstance(command.get("result"), dict):
        return command["result"]
    return None


def format_audit_markdown(audit: dict[str, object]) -> str:
    signal = audit.get("signal", {})
    command = audit.get("command", {})
    result = audit.get("trade_result", {})
    risk_gate = audit.get("risk_gate")
    notes = audit.get("notes", [])
    lines = [
        "# Dry-Run Audit",
        "",
        f"- Outcome: {audit.get('outcome')}",
        f"- Dry-run only: {audit.get('dry_run_only')}",
        f"- ID match: {audit.get('id_match')}",
        f"- Fresh: {audit.get('freshness', {}).get('fresh') if isinstance(audit.get('freshness'), dict) else ''}",
        f"- Signal/command match: {audit.get('signal_command_match')}",
        f"- Generated at: {audit.get('generated_at')}",
        "",
        "## Signal",
        f"- Action: {signal.get('action') if isinstance(signal, dict) else ''}",
        f"- Score/RR: {signal.get('score') if isinstance(signal, dict) else ''} / {signal.get('risk_reward') if isinstance(signal, dict) else ''}",
        f"- Pattern: {signal.get('pattern') if isinstance(signal, dict) else ''}",
        f"- Generated/valid: {signal.get('generated_at') if isinstance(signal, dict) else ''} / {signal.get('valid_for_seconds') if isinstance(signal, dict) else ''}",
        f"- Reason: {signal.get('reason') if isinstance(signal, dict) else ''}",
        "",
        "## Command",
        f"- ID: {command.get('id') if isinstance(command, dict) else ''}",
        f"- Status: {command.get('status') if isinstance(command, dict) else ''}",
        f"- Action: {command.get('action') if isinstance(command, dict) else ''}",
        f"- SL/TP: {command.get('sl') if isinstance(command, dict) else ''} / {command.get('tp') if isinstance(command, dict) else ''}",
        f"- Lot policy: {json.dumps(command.get('lot_policy'), ensure_ascii=False) if isinstance(command, dict) else ''}",
        f"- Source generated/valid: {command.get('source_generated_at') if isinstance(command, dict) else ''} / {command.get('source_valid_for_seconds') if isinstance(command, dict) else ''}",
        f"- Dry run: {command.get('dry_run') if isinstance(command, dict) else ''}",
        "",
        "## EA Result",
        f"- Present: {result.get('present') if isinstance(result, dict) else ''}",
        f"- Status: {result.get('status') if isinstance(result, dict) else ''}",
        f"- Message: {result.get('message') if isinstance(result, dict) else ''}",
        f"- Price: {result.get('price') if isinstance(result, dict) else ''}",
    ]
    if isinstance(risk_gate, dict):
        lines.extend(
            [
                "",
                "## Risk Gate",
                f"- Allowed: {risk_gate.get('allowed')}",
                f"- Reasons: {'; '.join(str(item) for item in risk_gate.get('reasons', []))}",
                f"- Metrics: {json.dumps(risk_gate.get('metrics', {}), ensure_ascii=False)}",
            ]
        )
    lines.extend(["", "## Notes"])
    if isinstance(notes, list) and notes:
        lines.extend(f"- {note}" for note in notes)
    else:
        lines.append("- No notes.")
    return "\n".join(lines) + "\n"


def write_audit(json_path: str | Path, md_path: str | Path, audit: dict[str, object]) -> None:
    output_json = Path(json_path)
    output_md = Path(md_path)
    output_json.parent.mkdir(parents=True, exist_ok=True)
    output_md.parent.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    output_md.write_text(format_audit_markdown(audit), encoding="utf-8")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Summarize signal, trade command, and EA dry-run result into an audit report.")
    parser.add_argument("--signal", default="runtime/latest_signal.json")
    parser.add_argument("--command", default="runtime/trade_command.json")
    parser.add_argument("--trade-result", default="runtime/latest_trade_result.json")
    parser.add_argument("--max-age-seconds", type=int, default=3600)
    parser.add_argument("--output-json", default="runtime/latest_dry_run_audit.json")
    parser.add_argument("--output-md", default="runtime/latest_dry_run_audit.md")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    audit = build_audit(
        signal=load_optional_json(args.signal),
        command=load_optional_json(args.command),
        trade_result=load_optional_json(args.trade_result),
        max_age_seconds=args.max_age_seconds,
    )
    write_audit(args.output_json, args.output_md, audit)
    print(json.dumps(audit, ensure_ascii=False, indent=2))
    print(f"wrote {args.output_json}")
    print(f"wrote {args.output_md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
