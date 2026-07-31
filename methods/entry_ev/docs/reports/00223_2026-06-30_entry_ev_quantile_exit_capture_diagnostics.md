# Entry EV Quantile Exit Capture Diagnostics

日時: 2026-06-30 16:21 JST
更新日時: 2026-06-30 16:21 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00222で分けた課題のうち、exit captureを診断した。
- `scripts/experiments/entry_ev_quantile_exit_capture_diagnostics.py` を追加した。00222の `enriched_trades.csv` を読み、policyで使った `pred_mlp_*_exit_event_minutes`、実holding、oracle best holding、exit regretをrole/candidate/context別に集計する。
- 対象はvalidation roleのq95/q99候補だけ。q90 relaxationは00222でfreshの悪いshort contextを増やすと分かったため除外した。
- q95/q99では `pred_mlp_*_exit_event_minutes` のraw平均が `816..1410m` と非常に長く、policyの `max_predicted_hold=260m` にほぼ張り付く。
- しかしoracle best holding平均は `497..930m` と260mよりさらに長い。early exit vs oracle rateは `0.75..1.00`。
- つまり、現q95/q99候補はentry時点でoracle潜在値を持つtradeが多いが、`260m` capで利益を取り逃している。
- 一方、負けcontextの一部はdirection errorやoracleより遅いexitも含むため、単純にcapを伸ばすだけでは危険。
- 判断: exit capture診断はaccepted infrastructure。標準policyはNoTradeのまま。次はcap延長ではなく、context-side inversion gateとexit hold extensionを分けてvalidationする。

## Artifacts

- Script: `scripts/experiments/entry_ev_quantile_exit_capture_diagnostics.py`
- Tests: `tests/test_entry_ev_quantile_exit_capture_diagnostics.py`
- Input enriched trades:
  - `data/reports/backtests/20260630_entry_ev_quantile_trade_diagnostics/20260630_071126_entry_ev_quantile_trade_diagnostics/enriched_trades.csv`
- Output:
  - `data/reports/backtests/20260630_entry_ev_quantile_exit_capture_diagnostics/20260630_072113_entry_ev_quantile_exit_capture_diagnostics/`

## Role Candidate Summary

| role | candidate | trades | total pnl | exit regret | loss with oracle edge | early exit | policy cap hit | policy hold - oracle |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `fresh2024_validation` | `q95_floor5` | `38` | `+1.9920` | `831.8140` | `0.4474` | `0.7895` | `0.9474` | `-412.0192` |
| `fresh2024_validation` | `q95_floor10` | `38` | `+3.9784` | `829.8276` | `0.4211` | `0.7895` | `0.9474` | `-412.0192` |
| `refit2025_validation` | `q95_floor5` | `29` | `-23.2338` | `572.9860` | `0.4483` | `0.7931` | `0.9310` | `-675.9972` |
| `refit2025_validation` | `q95_floor10` | `28` | `-23.6438` | `572.3960` | `0.4643` | `0.7857` | `0.9286` | `-593.6399` |
| `refit2025_validation` | `q99_floor10` | `18` | `-27.9456` | `388.8138` | `0.4444` | `0.8333` | `0.8333` | `-513.7471` |
| `fresh2024_validation` | `q99_floor10` | `12` | `+34.2940` | `252.5360` | `0.4167` | `0.7500` | `0.9167` | `-385.9503` |
| `cal2024_calibration_validation` | `q99_floor10` | `13` | `+10.1348` | `128.6122` | `0.4615` | `1.0000` | `1.0000` | `-442.3077` |

Additional holding facts:

- q95 fresh raw policy hold mean is `957.6394m`, effective policy hold mean `252.3755m`, realized hold mean `166.2632..170.8947m`, oracle hold mean `664.3947m`.
- q95 refit raw policy hold mean is `876.7018..938.5718m`, effective hold mean `253.8244..254.0373m`, realized hold mean `376.5862..380.7143m`, oracle hold mean `847.4643..930.0345m`.
- q99 cal has early exit rate `1.0` and cap hit `1.0`, meaning all selected trades are capped below oracle holding.

## Top Exit-Regret Contexts

| role | candidate | direction | context | trades | total pnl | exit regret | loss with oracle edge | early exit | policy hold - oracle |
|---|---|---|---|---:|---:|---:|---:|---:|---:|
| `fresh2024_validation` | `q95_floor10` | short | `up_normal_vol / london` | `2` | `-17.4924` | `83.4554` | `1.0` | `0.5` | `-89.5000` |
| `fresh2024_validation` | `q95_floor10` | long | `range_low_vol / london` | `2` | `-0.4758` | `73.5168` | `0.5` | `1.0` | `-523.5000` |
| `refit2025_validation` | `q95_floor10` | short | `down_low_vol / rollover` | `2` | `+0.7480` | `63.5780` | `0.5` | `1.0` | `-420.0000` |
| `fresh2024_validation` | `q95_floor10` | short | `up_low_vol / asia` | `3` | `-8.7840` | `52.7740` | `1.0` | `1.0` | `-677.3333` |
| `refit2025_validation` | `q95_floor10` | long | `range_normal_vol / asia` | `1` | `-11.2320` | `50.6120` | `1.0` | `1.0` | `-584.0000` |

## Interpretation

- `max_predicted_hold=260m` is a binding cap for q95/q99. Most raw MLP hold predictions exceed the cap.
- The cap often exits earlier than oracle best holding. This explains why fresh q95 can have positive role PnL but huge exit regret.
- Refit q95/q99 also has large exit regret, but role PnL is negative because direction/context errors remain.
- Therefore, increasing hold cap could improve exit capture for some trades, but it must be gated by context-side inversion risk. Otherwise it can deepen wrong-side losses.

## Decision

Accepted:

- Exit capture diagnostic script.
- `loss_with_oracle_edge_rate`, `early_exit_vs_oracle_rate`, `policy_hold_clipped_to_max_rate`, and `policy_hold_minus_oracle_mean` as standard selected-trade diagnostics.

Not accepted:

- Blindly increasing `max_predicted_hold` above `260m`.
- Promoting q95/q99 floor candidates to standard policy.

Current standard remains NoTrade.

## Next

1. Run a pre-registered q95/q99 hold-cap sensitivity for validation roles only, e.g. `260/480/720/1440`, while preserving NoTrade-first selector.
2. Add context-side inversion guard to reject contexts with high direction-error concentration before testing longer holds.
3. If longer holds help only when direction error is low, turn this into a two-stage policy: admission by quantile/rank, then context-aware hold extension.

## Verification

- `python3 -m unittest tests.test_entry_ev_quantile_exit_capture_diagnostics`: OK, `2` tests
- `python3 -m py_compile scripts/experiments/entry_ev_quantile_exit_capture_diagnostics.py tests/test_entry_ev_quantile_exit_capture_diagnostics.py`: OK
- exit capture diagnostics run: OK
