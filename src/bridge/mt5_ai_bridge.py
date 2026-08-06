#!/usr/bin/env python3
"""Local HTTP bridge for saving MT5 snapshots and optional AI analysis.

Normal Codex acquisition uses /snapshot and reads runtime/latest_snapshot.json.
The /analyze endpoint is only for explicit provider-backed signal tests.
The MT5 EA owns all execution controls.
"""

from __future__ import annotations

import csv
import json
import os
import re
import time
import uuid
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, urlopen


ACTION_VALUES = {"buy", "sell", "hold"}
TRADE_COMMAND_ACTIONS = {
    "buy",
    "sell",
    "buy_limit",
    "sell_limit",
    "buy_stop",
    "sell_stop",
    "modify",
    "cancel",
    "close",
    "close_all",
}

SIGNAL_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "action": {"type": "string", "enum": ["buy", "sell", "hold"]},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
        "reason": {"type": "string"},
        "entry_low": {"type": ["number", "null"]},
        "entry_high": {"type": ["number", "null"]},
        "stop_loss": {"type": ["number", "null"]},
        "take_profit": {"type": ["number", "null"]},
        "valid_for_seconds": {"type": "integer", "minimum": 10, "maximum": 300},
        "risk_notes": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "action",
        "confidence",
        "reason",
        "entry_low",
        "entry_high",
        "stop_loss",
        "take_profit",
        "valid_for_seconds",
        "risk_notes",
    ],
}

SYSTEM_PROMPT = """You are a conservative intraday market-analysis engine for MT5.

Analyze only the provided market snapshot. Return one strict JSON object matching
the requested schema. Do not include prose outside JSON.

Rules:
- This is analysis, not a guarantee. Prefer hold when the edge is unclear.
- Use buy/sell only when momentum, levels, and volatility agree.
- Confidence must be realistic. Use >=0.70 only for clear setups.
- Always include a stop_loss and take_profit for buy/sell.
- For hold, stop_loss and take_profit must be null.
- Make valid_for_seconds short for M1/M5 snapshots.
- Keep reason under 220 characters.
- Mention spread, level failure, and volatility risks in risk_notes when relevant.
"""


@dataclass(frozen=True)
class Settings:
    provider: str
    host: str
    port: int
    token: str
    timeout_seconds: int
    max_model_tokens: int
    state_dir: str
    openai_api_key: str
    openai_model: str
    openai_base_url: str
    anthropic_api_key: str
    anthropic_model: str
    anthropic_base_url: str
    anthropic_version: str


def load_settings() -> Settings:
    provider = os.getenv("AI_PROVIDER", "").strip().lower()
    openai_key = os.getenv("OPENAI_API_KEY", "").strip()
    anthropic_key = os.getenv("ANTHROPIC_API_KEY", "").strip()

    if not provider:
        if openai_key:
            provider = "openai"
        elif anthropic_key:
            provider = "anthropic"
        else:
            provider = "mock"

    return Settings(
        provider=provider,
        host=os.getenv("BRIDGE_HOST", "127.0.0.1"),
        port=int(os.getenv("BRIDGE_PORT", "8765")),
        token=os.getenv("BRIDGE_TOKEN", ""),
        timeout_seconds=int(os.getenv("REQUEST_TIMEOUT_SECONDS", "20")),
        max_model_tokens=int(os.getenv("MAX_MODEL_TOKENS", "900")),
        state_dir=os.getenv("STATE_DIR", "runtime"),
        openai_api_key=openai_key,
        openai_model=os.getenv("OPENAI_MODEL", "gpt-5.2"),
        openai_base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
        anthropic_api_key=anthropic_key,
        anthropic_model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5"),
        anthropic_base_url=os.getenv("ANTHROPIC_BASE_URL", "https://api.anthropic.com").rstrip("/"),
        anthropic_version=os.getenv("ANTHROPIC_VERSION", "2023-06-01"),
    )


def http_json(
    url: str,
    payload: dict[str, Any],
    headers: dict[str, str],
    timeout_seconds: int,
) -> dict[str, Any]:
    data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    req = Request(url, data=data, headers=headers, method="POST")
    try:
        with urlopen(req, timeout=timeout_seconds) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body)
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} from provider: {body[:1000]}") from exc
    except URLError as exc:
        raise RuntimeError(f"Provider request failed: {exc}") from exc


def compact_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    snapshot = dict(snapshot)
    bars = snapshot.get("bars")
    if isinstance(bars, list) and len(bars) > 80:
        snapshot["bars"] = bars[-80:]
    timeframes = snapshot.get("timeframes")
    if isinstance(timeframes, dict):
        compact_timeframes: dict[str, Any] = {}
        for key, value in timeframes.items():
            if not isinstance(value, dict):
                compact_timeframes[key] = value
                continue
            tf_value = dict(value)
            tf_bars = tf_value.get("bars")
            if isinstance(tf_bars, list) and len(tf_bars) > 80:
                tf_value["bars"] = tf_bars[-80:]
            compact_timeframes[key] = tf_value
        snapshot["timeframes"] = compact_timeframes
    return snapshot


def call_openai(snapshot: dict[str, Any], settings: Settings) -> dict[str, Any]:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is required when AI_PROVIDER=openai")

    payload = {
        "model": settings.openai_model,
        "input": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "Return JSON for this MT5 snapshot:\n"
                    + json.dumps(compact_snapshot(snapshot), separators=(",", ":"))
                ),
            },
        ],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "mt5_trade_signal",
                "strict": True,
                "schema": SIGNAL_SCHEMA,
            }
        },
        "max_output_tokens": settings.max_model_tokens,
    }
    response = http_json(
        f"{settings.openai_base_url}/responses",
        payload,
        {
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        },
        settings.timeout_seconds,
    )
    return parse_signal_text(extract_text(response))


def call_anthropic(snapshot: dict[str, Any], settings: Settings) -> dict[str, Any]:
    if not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is required when AI_PROVIDER=anthropic")

    payload = {
        "model": settings.anthropic_model,
        "max_tokens": settings.max_model_tokens,
        "system": SYSTEM_PROMPT,
        "messages": [
            {
                "role": "user",
                "content": (
                    "Return only one JSON object matching this JSON Schema:\n"
                    + json.dumps(SIGNAL_SCHEMA, separators=(",", ":"))
                    + "\nMT5 snapshot:\n"
                    + json.dumps(compact_snapshot(snapshot), separators=(",", ":"))
                ),
            }
        ],
    }
    response = http_json(
        f"{settings.anthropic_base_url}/v1/messages",
        payload,
        {
            "x-api-key": settings.anthropic_api_key,
            "anthropic-version": settings.anthropic_version,
            "Content-Type": "application/json",
        },
        settings.timeout_seconds,
    )
    return parse_signal_text(extract_text(response))


def mock_signal(snapshot: dict[str, Any]) -> dict[str, Any]:
    bid = as_float(snapshot.get("bid"))
    ask = as_float(snapshot.get("ask"))
    mid = None
    if bid is not None and ask is not None:
        mid = round((bid + ask) / 2, int(snapshot.get("digits", 2)))
    return {
        "action": "hold",
        "confidence": 0.0,
        "reason": "Mock mode: no provider API key configured.",
        "entry_low": mid,
        "entry_high": mid,
        "stop_loss": None,
        "take_profit": None,
        "valid_for_seconds": 30,
        "risk_notes": ["Set AI_PROVIDER and an API key to enable model analysis."],
    }


def extract_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        parts = [extract_text(item) for item in value]
        return "\n".join(part for part in parts if part)
    if isinstance(value, dict):
        if isinstance(value.get("output_text"), str):
            return value["output_text"]
        if value.get("type") in {"output_text", "text"} and isinstance(value.get("text"), str):
            return value["text"]
        if isinstance(value.get("content"), list):
            text = extract_text(value["content"])
            if text:
                return text
        if isinstance(value.get("output"), list):
            text = extract_text(value["output"])
            if text:
                return text
        if isinstance(value.get("content"), str):
            return value["content"]
    return ""


def parse_signal_text(text: str) -> dict[str, Any]:
    text = text.strip()
    if not text:
        raise ValueError("Provider returned no text")
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, flags=re.DOTALL)
        if not match:
            raise
        parsed = json.loads(match.group(0))
    if not isinstance(parsed, dict):
        raise ValueError("Provider response JSON must be an object")
    return parsed


def as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def validate_snapshot(snapshot: dict[str, Any]) -> None:
    for key in ("symbol", "timeframe", "bid", "ask"):
        if key not in snapshot:
            raise ValueError(f"Missing snapshot field: {key}")
    if as_float(snapshot.get("bid")) is None or as_float(snapshot.get("ask")) is None:
        raise ValueError("bid and ask must be numbers")
    bars = snapshot.get("bars", [])
    if bars is not None and not isinstance(bars, list):
        raise ValueError("bars must be a list")


def requested_history_hours(settings: Settings) -> int:
    request = load_history_request(settings)
    if not request:
        return 0
    return int(request["hours"])


def load_history_request(settings: Settings) -> dict[str, Any]:
    path = Path(settings.state_dir) / "history_request.json"
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    hours = payload.get("hours", 0)
    try:
        hours = int(hours)
    except (TypeError, ValueError):
        return {}
    hours = max(0, min(168, hours))
    if hours <= 0:
        return {}
    if "id" not in payload:
        return {}
    return {
        "id": str(payload["id"]),
        "hours": hours,
        "requested_at": payload.get("requested_at"),
        "status": payload.get("status", "pending"),
    }


def load_deal_history_request(settings: Settings) -> dict[str, Any]:
    path = Path(settings.state_dir) / "deal_history_request.json"
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict) or "id" not in payload:
        return {}

    days = payload.get("days", 0)
    if isinstance(days, str) and days.lower() == "all":
        days = 0
    try:
        days = int(days)
    except (TypeError, ValueError):
        return {}
    days = max(0, min(3650, days))

    max_deals = payload.get("max_deals", 0)
    try:
        max_deals = int(max_deals)
    except (TypeError, ValueError):
        max_deals = 0
    max_deals = max(0, max_deals)

    chunk_size = payload.get("chunk_size", 500)
    try:
        chunk_size = int(chunk_size)
    except (TypeError, ValueError):
        chunk_size = 500
    chunk_size = max(1, min(2000, chunk_size))

    return {
        "id": str(payload["id"]),
        "days": days,
        "max_deals": max_deals,
        "chunk_size": chunk_size,
        "requested_at": payload.get("requested_at"),
        "status": payload.get("status", "pending"),
    }


def next_deal_history_chunk_index(request_id: str, settings: Settings) -> int:
    request_id = safe_name(request_id)
    chunk_dir = Path(settings.state_dir) / "deal_history_chunks" / request_id
    if not chunk_dir.exists():
        return 0

    chunks: dict[int, dict[str, Any]] = {}
    for path in chunk_dir.glob("*.json"):
        try:
            chunk = json.loads(path.read_text(encoding="utf-8"))
            chunks[int(chunk.get("chunk_index", -1))] = chunk
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            continue

    if not chunks:
        return 0

    chunk_count = max(int(chunk.get("chunk_count", 0) or 0) for chunk in chunks.values())
    if chunk_count <= 0:
        return max(chunks) + 1

    for index in range(chunk_count):
        if index not in chunks:
            return index
    return chunk_count


def normalize_signal(signal: dict[str, Any]) -> dict[str, Any]:
    action = str(signal.get("action", "hold")).lower().strip()
    if action not in ACTION_VALUES:
        action = "hold"

    confidence = as_float(signal.get("confidence"))
    if confidence is None:
        confidence = 0.0
    confidence = max(0.0, min(1.0, confidence))

    reason = str(signal.get("reason") or "No reason supplied.")[:300]
    risk_notes = signal.get("risk_notes")
    if not isinstance(risk_notes, list):
        risk_notes = []
    risk_notes = [str(note)[:180] for note in risk_notes[:6]]

    stop_loss = as_float(signal.get("stop_loss"))
    take_profit = as_float(signal.get("take_profit"))
    if action == "hold":
        stop_loss = None
        take_profit = None

    valid_for = signal.get("valid_for_seconds", 30)
    try:
        valid_for = int(valid_for)
    except (TypeError, ValueError):
        valid_for = 30
    valid_for = max(10, min(300, valid_for))

    return {
        "action": action,
        "confidence": round(confidence, 4),
        "reason": reason,
        "entry_low": as_float(signal.get("entry_low")),
        "entry_high": as_float(signal.get("entry_high")),
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "valid_for_seconds": valid_for,
        "risk_notes": risk_notes,
    }


def analyze(snapshot: dict[str, Any], settings: Settings) -> dict[str, Any]:
    validate_snapshot(snapshot)
    provider = settings.provider
    if provider == "openai":
        signal = call_openai(snapshot, settings)
        model = settings.openai_model
    elif provider in {"anthropic", "claude"}:
        signal = call_anthropic(snapshot, settings)
        provider = "anthropic"
        model = settings.anthropic_model
    elif provider == "mock":
        signal = mock_signal(snapshot)
        model = "mock"
    else:
        raise ValueError(f"Unsupported AI_PROVIDER: {settings.provider}")

    normalized = normalize_signal(signal)
    normalized.update(
        {
            "ok": True,
            "request_id": str(uuid.uuid4()),
            "provider": provider,
            "model": model,
            "received_at": int(time.time()),
        }
    )
    return normalized


def save_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    validate_snapshot(snapshot)
    return {
        "ok": True,
        "request_id": str(uuid.uuid4()),
        "provider": "local",
        "model": "save-only",
        "received_at": int(time.time()),
        "action": "hold",
        "confidence": 0.0,
        "reason": "Saved locally. Codex reads runtime files for judgment.",
        "entry_low": None,
        "entry_high": None,
        "stop_loss": None,
        "take_profit": None,
        "valid_for_seconds": 30,
        "risk_notes": ["Capture and Codex judgment are separated."],
    }


def sanitize_symbol(symbol: Any) -> str:
    if not isinstance(symbol, str):
        return ""
    return "".join(c for c in symbol if c.isalnum() or c in "-_")


def persist_state(snapshot: dict[str, Any], signal: dict[str, Any], settings: Settings) -> None:
    if not settings.state_dir:
        return

    state_dir = Path(settings.state_dir)
    state_dir.mkdir(parents=True, exist_ok=True)

    write_json(state_dir / "latest_snapshot.json", snapshot)
    write_json(state_dir / "latest_signal.json", signal)
    write_text(state_dir / "latest_context.md", format_context(snapshot, signal))

    # 銘柄ごとにも保存する。共有ファイルは各EAが交互に上書きするため、
    # 片方の銘柄のバー・指標が常に失われていた。
    symbol_slug = sanitize_symbol(snapshot.get("symbol"))
    if symbol_slug:
        write_json(state_dir / f"latest_snapshot_{symbol_slug}.json", snapshot)
        write_text(state_dir / f"latest_context_{symbol_slug}.md", format_context(snapshot, signal))
    account = snapshot.get("account")
    if isinstance(account, dict):
        account_snapshot = {
            "symbol": snapshot.get("symbol"),
            "server_time": snapshot.get("server_time"),
            "bid": snapshot.get("bid"),
            "ask": snapshot.get("ask"),
            "account": account,
        }
        write_json(state_dir / "latest_account.json", account_snapshot)
        write_text(state_dir / "latest_account.md", format_account_context(account_snapshot))
        if symbol_slug:
            write_text(
                state_dir / f"latest_account_{symbol_slug}.md",
                format_account_context(account_snapshot),
            )

    trade_result = snapshot.get("trade_result")
    if isinstance(trade_result, dict):
        persist_trade_result(trade_result, settings)

    requested_hours = requested_history_hours(settings)
    snapshot_history_hours = snapshot.get("history_hours", 0)
    try:
        snapshot_history_hours = int(snapshot_history_hours)
    except (TypeError, ValueError):
        snapshot_history_hours = 0
    if requested_hours > 0 and snapshot_history_hours >= requested_hours:
        write_json(state_dir / f"latest_history_{requested_hours}h.json", snapshot)
        write_text(state_dir / f"latest_history_{requested_hours}h_context.md", format_context(snapshot, signal))
        request_file = state_dir / "history_request.json"
        done_file = state_dir / "history_request.done.json"
        done_payload = {
            "hours": requested_hours,
            "completed_at": int(time.time()),
            "source_server_time": snapshot.get("server_time"),
            "symbol": snapshot.get("symbol"),
        }
        write_json(done_file, done_payload)
        try:
            request_file.unlink()
        except FileNotFoundError:
            pass

    event = {
        "request_id": signal.get("request_id"),
        "received_at": signal.get("received_at"),
        "symbol": snapshot.get("symbol"),
        "timeframe": snapshot.get("timeframe"),
        "bid": snapshot.get("bid"),
        "ask": snapshot.get("ask"),
        "action": signal.get("action"),
        "confidence": signal.get("confidence"),
        "reason": signal.get("reason"),
        "provider": signal.get("provider"),
        "model": signal.get("model"),
    }
    with (state_dir / "events.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False, separators=(",", ":")) + "\n")


def persist_history_chunk(chunk: dict[str, Any], settings: Settings) -> dict[str, Any]:
    required = ("history_request_id", "history_hours", "symbol", "timeframe_key", "chunk_index", "chunk_count", "bars")
    for key in required:
        if key not in chunk:
            raise ValueError(f"Missing history chunk field: {key}")

    request_id = safe_name(str(chunk["history_request_id"]))
    timeframe_key = safe_name(str(chunk["timeframe_key"]))
    chunk_index = int(chunk["chunk_index"])
    chunk_count = int(chunk["chunk_count"])
    if chunk_index < 0 or chunk_count <= 0 or chunk_index >= chunk_count:
        raise ValueError("Invalid chunk index/count")
    if not isinstance(chunk.get("bars"), list):
        raise ValueError("bars must be a list")

    state_dir = Path(settings.state_dir)
    chunk_dir = state_dir / "history_chunks" / request_id
    chunk_dir.mkdir(parents=True, exist_ok=True)
    write_json(chunk_dir / f"{timeframe_key}_{chunk_index:04d}.json", chunk)
    result = assemble_history_if_complete(request_id, settings)
    return {"ok": True, "complete": result.get("complete", False), "request_id": request_id}


def safe_name(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", value)[:120] or "unknown"


def assemble_history_if_complete(request_id: str, settings: Settings) -> dict[str, Any]:
    state_dir = Path(settings.state_dir)
    chunk_dir = state_dir / "history_chunks" / request_id
    if not chunk_dir.exists():
        return {"complete": False}

    expected_timeframes = ("M1", "M5", "M15", "M30")
    chunks_by_tf: dict[str, list[dict[str, Any]]] = {}
    for timeframe in expected_timeframes:
        files = sorted(chunk_dir.glob(f"{timeframe}_*.json"))
        if not files:
            return {"complete": False}
        chunks = [json.loads(path.read_text(encoding="utf-8")) for path in files]
        chunk_count = int(chunks[0].get("chunk_count", 0))
        if len(chunks) < chunk_count:
            return {"complete": False}
        chunks_by_tf[timeframe] = sorted(chunks, key=lambda item: int(item.get("chunk_index", 0)))

    first_chunk = chunks_by_tf["M1"][0]
    timeframes: dict[str, Any] = {}
    for timeframe, chunks in chunks_by_tf.items():
        bars: list[dict[str, Any]] = []
        for chunk in chunks:
            bars.extend(chunk.get("bars", []))
        timeframes[timeframe] = {
            "label": timeframe,
            "timeframe": chunks[0].get("timeframe"),
            "indicators": chunks[0].get("indicators", {}),
            "bars": bars,
        }

    m1_bars = timeframes["M1"]["bars"]
    snapshot = {
        "symbol": first_chunk.get("symbol"),
        "timeframe": "PERIOD_M1",
        "server_time": first_chunk.get("server_time"),
        "history_hours": int(first_chunk.get("history_hours", 24)),
        "bid": first_chunk.get("bid"),
        "ask": first_chunk.get("ask"),
        "spread_points": first_chunk.get("spread_points"),
        "digits": first_chunk.get("digits"),
        "point": first_chunk.get("point"),
        "indicators": timeframes["M1"].get("indicators", {}),
        "bars": m1_bars[-80:],
        "timeframes": timeframes,
    }
    hours = int(snapshot["history_hours"])
    signal = mock_signal(snapshot)
    signal.update({"ok": True, "request_id": request_id, "provider": "history", "model": "none", "received_at": int(time.time())})
    write_json(state_dir / f"latest_history_{hours}h.json", snapshot)
    write_text(state_dir / f"latest_history_{hours}h_context.md", format_context(snapshot, signal))
    write_json(
        state_dir / "history_request.done.json",
        {
            "id": request_id,
            "hours": hours,
            "completed_at": int(time.time()),
            "source_server_time": snapshot.get("server_time"),
            "symbol": snapshot.get("symbol"),
            "bars": {key: len(value.get("bars", [])) for key, value in timeframes.items()},
        },
    )

    request_file = state_dir / "history_request.json"
    try:
        request_payload = json.loads(request_file.read_text(encoding="utf-8"))
        if str(request_payload.get("id") or request_payload.get("requested_at")) == request_id:
            request_file.unlink()
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        pass
    return {"complete": True, "hours": hours}


def persist_deal_history_chunk(chunk: dict[str, Any], settings: Settings) -> dict[str, Any]:
    required = ("deal_history_request_id", "chunk_index", "chunk_count", "total_deals", "deals")
    for key in required:
        if key not in chunk:
            raise ValueError(f"Missing deal history chunk field: {key}")

    request_id = safe_name(str(chunk["deal_history_request_id"]))
    chunk_index = int(chunk["chunk_index"])
    chunk_count = int(chunk["chunk_count"])
    if chunk_index < 0 or chunk_count <= 0 or chunk_index >= chunk_count:
        raise ValueError("Invalid deal history chunk index/count")
    if not isinstance(chunk.get("deals"), list):
        raise ValueError("deals must be a list")

    state_dir = Path(settings.state_dir)
    chunk_dir = state_dir / "deal_history_chunks" / request_id
    chunk_dir.mkdir(parents=True, exist_ok=True)
    write_json(chunk_dir / f"{chunk_index:04d}.json", chunk)
    result = assemble_deal_history_if_complete(request_id, settings)
    return {"ok": True, "complete": result.get("complete", False), "request_id": request_id}


def assemble_deal_history_if_complete(request_id: str, settings: Settings) -> dict[str, Any]:
    state_dir = Path(settings.state_dir)
    chunk_dir = state_dir / "deal_history_chunks" / request_id
    if not chunk_dir.exists():
        return {"complete": False}

    files = sorted(chunk_dir.glob("*.json"))
    if not files:
        return {"complete": False}
    chunks = [json.loads(path.read_text(encoding="utf-8")) for path in files]
    chunk_count = int(chunks[0].get("chunk_count", 0))
    if len(chunks) < chunk_count:
        return {"complete": False}
    chunks = sorted(chunks, key=lambda item: int(item.get("chunk_index", 0)))

    deals: list[dict[str, Any]] = []
    seen_tickets: set[str] = set()
    for chunk in chunks:
        for deal in chunk.get("deals", []):
            if not isinstance(deal, dict):
                continue
            ticket = str(deal.get("ticket", ""))
            if ticket and ticket in seen_tickets:
                continue
            if ticket:
                seen_tickets.add(ticket)
            deals.append(deal)

    first_chunk = chunks[0]
    history = {
        "id": request_id,
        "symbol": first_chunk.get("symbol"),
        "account_login": first_chunk.get("account_login"),
        "currency": first_chunk.get("currency"),
        "server_time": first_chunk.get("server_time"),
        "days": first_chunk.get("days", 0),
        "max_deals": first_chunk.get("max_deals", 0),
        "total_deals_available": first_chunk.get("total_deals", len(deals)),
        "deal_count": len(deals),
        "completed_at": int(time.time()),
        "deals": deals,
    }
    write_json(state_dir / "latest_deal_history.json", history)
    write_text(state_dir / "latest_deal_history.md", format_deal_history_context(history))
    write_deal_history_csv(state_dir / "latest_deal_history.csv", deals)
    write_json(
        state_dir / "deal_history_request.done.json",
        {
            "id": request_id,
            "days": history["days"],
            "max_deals": history["max_deals"],
            "completed_at": history["completed_at"],
            "source_server_time": history["server_time"],
            "symbol": history["symbol"],
            "deal_count": len(deals),
            "total_deals_available": history["total_deals_available"],
        },
    )

    request_file = state_dir / "deal_history_request.json"
    try:
        request_payload = json.loads(request_file.read_text(encoding="utf-8"))
        if str(request_payload.get("id") or request_payload.get("requested_at")) == request_id:
            request_file.unlink()
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        pass
    return {"complete": True, "deal_count": len(deals)}


DEAL_CSV_FIELDS = [
    "ticket",
    "time",
    "symbol",
    "type",
    "entry",
    "volume",
    "price",
    "profit",
    "commission",
    "swap",
    "magic",
]


def write_deal_history_csv(path: Path, deals: list[dict[str, Any]]) -> None:
    tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    with tmp.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=DEAL_CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        for deal in deals:
            writer.writerow({field: deal.get(field, "") for field in DEAL_CSV_FIELDS})
    tmp.replace(path)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    write_text(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def write_text(path: Path, text: str) -> None:
    tmp = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def load_trade_command(settings: Settings) -> dict[str, Any]:
    path = Path(settings.state_dir) / "trade_command.json"
    if not path.exists():
        return {}
    try:
        command = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(command, dict):
        return {}
    if command.get("status") != "pending":
        return {}
    if str(command.get("action", "")).lower() not in TRADE_COMMAND_ACTIONS:
        return {}
    expires_at = command.get("expires_at", 0)
    try:
        expires_at = int(expires_at)
    except (TypeError, ValueError):
        expires_at = 0
    if expires_at and expires_at < int(time.time()):
        command["status"] = "expired"
        command["expired_at"] = int(time.time())
        write_json(path, command)
        return {}
    return command


def mark_trade_command_sent(command: dict[str, Any], settings: Settings) -> None:
    path = Path(settings.state_dir) / "trade_command.json"
    command = dict(command)
    command["status"] = "sent"
    command["sent_at"] = int(time.time())
    write_json(path, command)


def serve_trade_command(settings: Settings, requester_symbol: str | None = None) -> dict[str, Any]:
    """Serve the pending command to a polling EA, routing by symbol.

    A requester that reports its chart symbol only receives commands for that
    symbol; a mismatched command stays pending for the matching EA. Requests
    without a symbol (older EA builds) receive any pending command.
    """
    command = load_trade_command(settings)
    if not command:
        return {}
    command_symbol = str(command.get("symbol", ""))
    if requester_symbol and command_symbol and requester_symbol != command_symbol:
        return {}
    mark_trade_command_sent(command, settings)
    return command


def persist_trade_result(result: dict[str, Any], settings: Settings) -> dict[str, Any]:
    state_dir = Path(settings.state_dir)
    state_dir.mkdir(parents=True, exist_ok=True)
    result = dict(result)
    result.setdefault("received_at", int(time.time()))
    write_json(state_dir / "latest_trade_result.json", result)
    write_text(state_dir / "latest_trade_result.md", format_trade_result(result))

    command_file = state_dir / "trade_command.json"
    try:
        command = json.loads(command_file.read_text(encoding="utf-8"))
        if isinstance(command, dict) and str(command.get("id")) == str(result.get("id")):
            command["status"] = result.get("status", "result")
            command["result"] = result
            write_json(command_file, command)
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        pass
    return {"ok": True}


def format_trade_result(result: dict[str, Any]) -> str:
    lines = [
        "# Latest Trade Command Result",
        "",
        f"- ID: {result.get('id')}",
        f"- Status: {result.get('status')}",
        f"- Dry run: {result.get('dry_run')}",
        f"- Action: {result.get('action')}",
        f"- Symbol: {result.get('symbol')}",
        f"- Volume: {result.get('volume')}",
        f"- Price: {result.get('price')}",
        f"- SL/TP: {result.get('sl')} / {result.get('tp')}",
        f"- Ticket/order/deal: {result.get('ticket')} / {result.get('order')} / {result.get('deal')}",
        f"- Retcode: {result.get('retcode')}",
        f"- Message: {result.get('message')}",
        f"- Server time: {result.get('server_time')}",
        f"- Received at: {result.get('received_at')}",
        "",
    ]
    return "\n".join(lines)


def format_context(snapshot: dict[str, Any], signal: dict[str, Any]) -> str:
    indicators = snapshot.get("indicators")
    if not isinstance(indicators, dict):
        indicators = {}
    risk_notes = signal.get("risk_notes")
    if not isinstance(risk_notes, list):
        risk_notes = []

    lines = [
        "# Latest MT5 AI Bridge Context",
        "",
        f"- Symbol: {snapshot.get('symbol')}",
        f"- Timeframe: {snapshot.get('timeframe')}",
        f"- Server time: {snapshot.get('server_time')}",
        f"- Bid/Ask: {snapshot.get('bid')} / {snapshot.get('ask')}",
        f"- Spread points: {snapshot.get('spread_points')}",
        f"- RSI14: {indicators.get('rsi14')}",
        f"- EMA fast/slow: {indicators.get('ema_fast')} / {indicators.get('ema_slow')}",
        f"- ATR14: {indicators.get('atr14')}",
        "",
        "## Signal",
        "",
        f"- Action: {signal.get('action')}",
        f"- Confidence: {signal.get('confidence')}",
        f"- Stop loss: {signal.get('stop_loss')}",
        f"- Take profit: {signal.get('take_profit')}",
        f"- Valid for seconds: {signal.get('valid_for_seconds')}",
        f"- Reason: {signal.get('reason')}",
        f"- Provider/model: {signal.get('provider')} / {signal.get('model')}",
        "",
        "## Risk Notes",
        "",
    ]
    if risk_notes:
        lines.extend(f"- {note}" for note in risk_notes)
    else:
        lines.append("- None")
    timeframes = snapshot.get("timeframes")
    if isinstance(timeframes, dict) and timeframes:
        lines.extend(["", "## Timeframes", ""])
        for key in ("M1", "M5", "M15", "M30", "H1", "H4"):
            value = timeframes.get(key)
            if not isinstance(value, dict):
                continue
            bars = value.get("bars")
            if isinstance(bars, list) and bars:
                first = bars[0]
                last = bars[-1]
                highs = [as_float(bar.get("high")) for bar in bars if isinstance(bar, dict)]
                lows = [as_float(bar.get("low")) for bar in bars if isinstance(bar, dict)]
                highs = [item for item in highs if item is not None]
                lows = [item for item in lows if item is not None]
                indicators = value.get("indicators")
                if not isinstance(indicators, dict):
                    indicators = {}
                lines.append(
                    f"- {key}: {first.get('time')} -> {last.get('time')}, "
                    f"close {first.get('close')} -> {last.get('close')}, "
                    f"range {min(lows) if lows else None}-{max(highs) if highs else None}, "
                    f"RSI {indicators.get('rsi14')}, "
                    f"EMA {indicators.get('ema_fast')}/{indicators.get('ema_slow')}, "
                    f"ATR {indicators.get('atr14')}"
                )
    lines.append("")
    return "\n".join(lines)


def format_account_context(account_snapshot: dict[str, Any]) -> str:
    account = account_snapshot.get("account")
    if not isinstance(account, dict):
        account = {}
    positions = account.get("positions")
    if not isinstance(positions, list):
        positions = []
    deals = account.get("deals")
    if not isinstance(deals, list):
        deals = []

    lines = [
        "# Latest MT5 Account Context",
        "",
        f"- Symbol: {account_snapshot.get('symbol')}",
        f"- Server time: {account_snapshot.get('server_time')}",
        f"- Bid/Ask: {account_snapshot.get('bid')} / {account_snapshot.get('ask')}",
        f"- Login: {account.get('login')}",
        f"- Currency: {account.get('currency')}",
        f"- Balance: {account.get('balance')}",
        f"- Equity: {account.get('equity')}",
        f"- Margin/free margin: {account.get('margin')} / {account.get('free_margin')}",
        f"- Margin level: {account.get('margin_level')}",
        "",
        "## Open Positions",
        "",
    ]
    if positions:
        for position in positions:
            if not isinstance(position, dict):
                continue
            lines.append(
                "- "
                f"ticket {position.get('ticket')} "
                f"{position.get('symbol')} {position.get('type')} "
                f"{position.get('volume')} @ {position.get('open_price')} "
                f"current {position.get('current_price')} "
                f"P/L {position.get('profit')} "
                f"SL {position.get('sl')} TP {position.get('tp')} "
                f"opened {position.get('open_time')}"
            )
    else:
        lines.append("- None")

    lines.extend(["", "## Recent Deals", ""])
    if deals:
        for deal in deals[:20]:
            if not isinstance(deal, dict):
                continue
            lines.append(
                "- "
                f"{deal.get('time')} {deal.get('symbol')} "
                f"{deal.get('entry')} {deal.get('type')} "
                f"{deal.get('volume')} @ {deal.get('price')} "
                f"P/L {deal.get('profit')} "
                f"commission {deal.get('commission')} swap {deal.get('swap')}"
            )
    else:
        lines.append("- None")
    lines.append("")
    return "\n".join(lines)


def format_deal_history_context(history: dict[str, Any]) -> str:
    deals = history.get("deals")
    if not isinstance(deals, list):
        deals = []

    times = sorted(str(deal.get("time")) for deal in deals if isinstance(deal, dict) and deal.get("time"))
    realized_entries = {"out", "inout", "out_by"}
    realized_deals = [
        deal
        for deal in deals
        if isinstance(deal, dict) and str(deal.get("entry", "")).lower() in realized_entries
    ]
    profit = sum(as_float(deal.get("profit")) or 0.0 for deal in realized_deals)
    commission = sum(as_float(deal.get("commission")) or 0.0 for deal in realized_deals)
    swap = sum(as_float(deal.get("swap")) or 0.0 for deal in realized_deals)
    net = profit + commission + swap

    lines = [
        "# Latest MT5 Deal History",
        "",
        f"- Symbol: {history.get('symbol')}",
        f"- Account: {history.get('account_login')}",
        f"- Currency: {history.get('currency')}",
        f"- Server time: {history.get('server_time')}",
        f"- Range days: {history.get('days')} (0 means all available history)",
        f"- Deals: {history.get('deal_count')} / available {history.get('total_deals_available')}",
        f"- Time range: {times[0] if times else None} -> {times[-1] if times else None}",
        f"- Realized P/L: profit {round(profit, 2)}, commission {round(commission, 2)}, swap {round(swap, 2)}, net {round(net, 2)}",
        "",
        "## Recent Deals",
        "",
    ]
    if deals:
        for deal in deals[:30]:
            if not isinstance(deal, dict):
                continue
            lines.append(
                "- "
                f"{deal.get('time')} {deal.get('symbol')} "
                f"{deal.get('entry')} {deal.get('type')} "
                f"{deal.get('volume')} @ {deal.get('price')} "
                f"P/L {deal.get('profit')} "
                f"commission {deal.get('commission')} swap {deal.get('swap')} "
                f"ticket {deal.get('ticket')}"
            )
    else:
        lines.append("- None")
    lines.append("")
    return "\n".join(lines)


class BridgeHandler(BaseHTTPRequestHandler):
    server_version = "MT5AIBridge/0.1"

    @property
    def settings(self) -> Settings:
        return self.server.settings  # type: ignore[attr-defined]

    def do_GET(self) -> None:
        if self.path == "/health":
            self.send_json(
                {
                    "ok": True,
                    "provider": self.settings.provider,
                    "openai_model": self.settings.openai_model,
                    "anthropic_model": self.settings.anthropic_model,
                }
            )
            return
        if self.path == "/config":
            if self.settings.token:
                token = self.headers.get("X-Bridge-Token", "")
                if token != self.settings.token:
                    self.send_error_json(HTTPStatus.UNAUTHORIZED, "unauthorized")
                    return
            history_request = load_history_request(self.settings)
            deal_history_request = load_deal_history_request(self.settings)
            self.send_json(
                {
                    "ok": True,
                    "history_hours": int(history_request["hours"]) if history_request else 0,
                    "history_request_id": str(history_request["id"]) if history_request else "",
                    "history_chunk_size": 240,
                    "deal_history_days": int(deal_history_request["days"]) if deal_history_request else 0,
                    "deal_history_request_id": (
                        str(deal_history_request["id"]) if deal_history_request else ""
                    ),
                    "deal_history_max_deals": (
                        int(deal_history_request["max_deals"]) if deal_history_request else 0
                    ),
                    "deal_history_chunk_size": (
                        int(deal_history_request["chunk_size"]) if deal_history_request else 500
                    ),
                    "deal_history_next_chunk": (
                        next_deal_history_chunk_index(str(deal_history_request["id"]), self.settings)
                        if deal_history_request
                        else 0
                    ),
                }
            )
            return
        parsed = urlsplit(self.path)
        if parsed.path in {"/trade-command", "/trade_command"}:
            if self.settings.token:
                token = self.headers.get("X-Bridge-Token", "")
                if token != self.settings.token:
                    self.send_error_json(HTTPStatus.UNAUTHORIZED, "unauthorized")
                    return
            query = parse_qs(parsed.query)
            requester_symbol = query.get("symbol", [""])[0] or None
            command = serve_trade_command(self.settings, requester_symbol)
            self.send_json({"ok": True, "command": command or None})
            return
        self.send_error_json(HTTPStatus.NOT_FOUND, "not_found")

    def do_POST(self) -> None:
        if self.path in {"/history-chunk", "/history_chunk"}:
            self.handle_history_chunk()
            return
        if self.path in {"/deal-history-chunk", "/deal_history_chunk"}:
            self.handle_deal_history_chunk()
            return
        if self.path in {"/trade-result", "/trade_result"}:
            self.handle_trade_result()
            return
        if self.path not in {"/analyze", "/snapshot", "/ingest"}:
            self.send_error_json(HTTPStatus.NOT_FOUND, "not_found")
            return
        if self.settings.token:
            token = self.headers.get("X-Bridge-Token", "")
            if token != self.settings.token:
                self.send_error_json(HTTPStatus.UNAUTHORIZED, "unauthorized")
                return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8")
            payload = json.loads(body)
            if not isinstance(payload, dict):
                raise ValueError("Request JSON must be an object")
            if "deal_history_request_id" in payload and "deals" in payload:
                result = persist_deal_history_chunk(payload, self.settings)
                self.send_json(result)
                return
            if "history_request_id" in payload and "bars" in payload:
                result = persist_history_chunk(payload, self.settings)
                self.send_json(result)
                return

            embedded_deal_history_chunk = payload.pop("embedded_deal_history_chunk", None)
            if embedded_deal_history_chunk is not None:
                if not isinstance(embedded_deal_history_chunk, dict):
                    raise ValueError("embedded_deal_history_chunk must be an object")
                persist_deal_history_chunk(embedded_deal_history_chunk, self.settings)

            embedded_history_chunk = payload.pop("embedded_history_chunk", None)
            if embedded_history_chunk is not None:
                if not isinstance(embedded_history_chunk, dict):
                    raise ValueError("embedded_history_chunk must be an object")
                persist_history_chunk(embedded_history_chunk, self.settings)

            snapshot = payload
            if self.path == "/analyze":
                result = analyze(snapshot, self.settings)
            else:
                result = save_snapshot(snapshot)
            persist_state(snapshot, result, self.settings)
            self.send_json(result)
        except Exception as exc:  # noqa: BLE001 - server must return JSON errors.
            self.send_error_json(HTTPStatus.BAD_REQUEST, str(exc))

    def handle_history_chunk(self) -> None:
        if self.settings.token:
            token = self.headers.get("X-Bridge-Token", "")
            if token != self.settings.token:
                self.send_error_json(HTTPStatus.UNAUTHORIZED, "unauthorized")
                return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8")
            chunk = json.loads(body)
            if not isinstance(chunk, dict):
                raise ValueError("Request JSON must be an object")
            result = persist_history_chunk(chunk, self.settings)
            self.send_json(result)
        except Exception as exc:  # noqa: BLE001 - server must return JSON errors.
            self.send_error_json(HTTPStatus.BAD_REQUEST, str(exc))

    def handle_deal_history_chunk(self) -> None:
        if self.settings.token:
            token = self.headers.get("X-Bridge-Token", "")
            if token != self.settings.token:
                self.send_error_json(HTTPStatus.UNAUTHORIZED, "unauthorized")
                return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8")
            chunk = json.loads(body)
            if not isinstance(chunk, dict):
                raise ValueError("Request JSON must be an object")
            result = persist_deal_history_chunk(chunk, self.settings)
            self.send_json(result)
        except Exception as exc:  # noqa: BLE001 - server must return JSON errors.
            self.send_error_json(HTTPStatus.BAD_REQUEST, str(exc))

    def handle_trade_result(self) -> None:
        if self.settings.token:
            token = self.headers.get("X-Bridge-Token", "")
            if token != self.settings.token:
                self.send_error_json(HTTPStatus.UNAUTHORIZED, "unauthorized")
                return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length).decode("utf-8")
            result = json.loads(body)
            if not isinstance(result, dict):
                raise ValueError("Request JSON must be an object")
            self.send_json(persist_trade_result(result, self.settings))
        except Exception as exc:  # noqa: BLE001 - server must return JSON errors.
            self.send_error_json(HTTPStatus.BAD_REQUEST, str(exc))

    def log_message(self, fmt: str, *args: Any) -> None:
        print("%s - %s" % (self.log_date_time_string(), fmt % args))

    def send_json(self, payload: dict[str, Any], status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def send_error_json(self, status: HTTPStatus, message: str) -> None:
        self.send_json({"ok": False, "error": message}, status)


class BridgeServer(ThreadingHTTPServer):
    def __init__(self, address: tuple[str, int], settings: Settings):
        super().__init__(address, BridgeHandler)
        self.settings = settings


def main() -> None:
    settings = load_settings()
    server = BridgeServer((settings.host, settings.port), settings)
    print(
        f"MT5 AI bridge listening on http://{settings.host}:{settings.port} "
        f"provider={settings.provider}"
    )
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
