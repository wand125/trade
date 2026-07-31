# MT5 Snapshot Analysis

## Inputs

`runtime/latest_snapshot.json` normally contains:

- `symbol`, `timeframe`, `server_time`
- `bid`, `ask`, `spread_points`, `digits`, `point`
- `indicators.rsi14`, `indicators.ema_fast`, `indicators.ema_slow`, `indicators.atr14`
- `bars[]` with `time`, `open`, `high`, `low`, `close`, `tick_volume`
- optional `timeframes.M1/M5/M15/M30` objects, each with `indicators` and `bars`
- `runtime/latest_history_24h.json` uses the same shape, with `history_hours: 24`
- `runtime/latest_account.json` contains account summary, open positions, and recent deals when available

## Calculations

For a quick read:

1. If `timeframes` exists, read M30 -> M15 -> M5 -> M1 in that order.
2. Use M30/M15 to define the broad intraday bias and major range.
3. Use M5 to confirm whether the short-term move agrees with the broad bias.
4. Use M1 for immediate momentum, pullback, and trigger-area behavior.
5. Compare the last 10 closes for immediate M1 direction.
6. Compare the first and last close across each timeframe's available bars for bias.
7. Get the recent high/low over the last 10, 20, and all available bars.
8. Count last 5-10 candle bodies:
   - mostly positive bodies means buy pressure
   - mostly negative bodies means sell pressure
   - alternating small bodies means range or digestion
9. Use EMA fast vs EMA slow:
   - fast above slow: short-term upward pressure
   - fast below slow: short-term downward pressure
   - nearly equal: direction is weak
10. Use RSI14:
   - 50-60: mild bullish momentum
   - 40-50: mild bearish momentum
   - above 70 or below 30: extended; wait for confirmation
11. Use ATR14 to avoid over-tight conclusions. On XAU/USD M1, a level inside about 0.5-1.0 ATR is noise unless confirmed.

## Multi-Timeframe Judgment

Use these labels:

- **Aligned bullish**: M30/M15 trend up, M5 up, M1 holding above support.
- **Aligned bearish**: M30/M15 trend down, M5 down, M1 failing rebounds.
- **Rebound inside bearish range**: M1/M5 up while M15/M30 still down.
- **Pullback inside bullish range**: M1/M5 down while M15/M30 still up.
- **Mixed/range**: timeframes disagree and price is between nearby support/resistance.

When lower timeframes conflict with higher timeframes, state that clearly and prefer "wait for break/hold confirmation" over a directional call.

## Level Selection

Choose levels from:

- latest bid/ask
- last 10/20-bar high and low
- available-session high and low from the snapshot
- EMA fast/slow zone
- round numbers near price

Use "if price holds above..." or "if price breaks below..." instead of unconditional trade calls.

## Response Style

Write in Japanese when the user writes in Japanese.

Example:

```text
今は短期反発中ですが、1時間の流れではまだ戻り売り警戒です。
4113-4114を維持する間は買い戻し継続、4117.3を上抜けると上方向が少し強くなります。
4113割れなら反発失敗、4108割れなら売り優勢に戻る見方です。
```
