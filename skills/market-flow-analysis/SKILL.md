---
name: market-flow-analysis
description: Analyze live or recent MT5 market snapshots saved by the MT5 AI Bridge, especially XAU/USD and TitanFX symbols, to summarize short-term market situation, multi-timeframe flow, key levels, momentum, invalidation points, and scenarios. Use when the user asks to check 相場状況, 流れ, 短期, 数分足, M1, M5, M15, M30, XAU/USD, gold, latest_context.md, latest_snapshot.json, or runtime market data.
---

# Market Flow Analysis

## Workflow

1. Read the freshest available project data in this order:
   - `runtime/latest_history_24h.json` when the user asks for past 24 hours or a time older than the current snapshot
   - `runtime/latest_snapshot.json` as the primary source for normal acquisition
   - `runtime/latest_account.json` when the user asks about current trades, positions, account, P/L, or deal history
   - `runtime/latest_context.md` only as a readable summary
   - `runtime/latest_signal.json` only for bridge save/analyze status, not market judgment
   - `runtime/events.jsonl` for recent history when needed
2. If the user asks for historical data that is not saved yet, run `python3 bridge/request_history.py 24`, wait for the next MT5 EA post, then read `runtime/latest_history_24h.json`.
3. If `latest_snapshot.json` exists, analyze the raw bars instead of relying only on the markdown summary.
4. If runtime files are missing or stale, say that MT5 data is not available and ask the user to start `python3 bridge/mt5_ai_bridge.py` and attach the EA.
5. Keep the answer focused on market flow, not automated execution. Do not claim certainty.

## Analysis Method

Use `references/mt5-snapshot-analysis.md` for the calculation and response pattern.

Default priorities:

- Current Bid/Ask and spread
- M1 for immediate flow and entry-area behavior
- M5 for short-term trend confirmation
- M15 and M30 for the broader intraday direction and major range
- EMA fast/slow relationship
- RSI14 direction and extremes
- ATR14 for realistic stop/level distance
- Recent swing high/low, round numbers, and failed break levels

## Output Pattern

Prefer this concise structure unless the user asks for more detail:

- Current condition: one short paragraph
- Multi-timeframe flow: M1, M5, M15, M30 alignment or conflict
- Key levels: support, resistance, invalidation
- Scenarios: what changes if price breaks up or down
- Practical note: whether the current area is chaseable or better to wait

Avoid:

- Direct account advice such as lot size unless the user provides account/risk details.
- Saying the model "knows" future price movement.
- Treating mock bridge signals as real AI analysis.
- Treating `latest_signal.json` as the normal acquisition source.
- Ignoring open positions when the user asks about current trades.
