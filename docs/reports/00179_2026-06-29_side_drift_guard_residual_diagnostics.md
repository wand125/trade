# Side Drift Guard Residual Diagnostics

日時: 2026-06-29 23:20 JST
更新日時: 2026-06-29 23:20 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- `p10 + admission margin10` の残存失敗を `model-trade-exposure-diagnostics` と新規 `residual_trade_failure_diagnostics.py` で分解した。
- 対象policyの全体は total PnL `-90.1378`, trades `949`。負け月は `2025-08`, `2025-09`, `2025-10`, `2025-11`, `2025-12` で、合計 `-725.1116`。
- 負け月274 tradesのうち、short 155 tradesが `-716.6702`。long 119 tradesは `-8.4414` で、残存損失のほぼ全てはshort側。
- 最大の文脈は `2025-09 short/range_low_vol/ny_overlap` 5 trades `-144.2160`。direction error `0.8000`, actual profit-barrier hit `0.0000`, EV overestimate mean `50.9439`。
- `short/range_low_vol` は side gap が大きいほど安全、という形ではなかった。`2025-09 short/range_low_vol/ny_overlap` の `pred_side_gap > 10` だけで `-89.6280`。
- confidence thresholdだけでも解けない。最大損失は `0.4-0.55` bucketが多いが、`0.55-0.7` bucketにも `2025-09 short/range_low_vol/ny_overlap -54.2040` と `2025-11 short/range_low_vol/ny_overlap -47.5900` が残る。

## Artifacts

- exposure diagnostics: `data/reports/backtests/20260629_141513_side_drift_guard_admission_margin10_residual_diagnostics/`
- residual focus diagnostics: `data/reports/backtests/20260629_141828_side_drift_guard_admission_margin10_residual_focus/`
- reusable script: `scripts/experiments/residual_trade_failure_diagnostics.py`
- tests: `tests/test_residual_trade_failure_diagnostics.py`

## Direction Split

負け月のみ:

| direction | trades | PnL | avg | large losses | direction error |
|---|---:|---:|---:|---:|---:|
| short | `155` | `-716.6702` | `-4.6237` | `21` | `0.7097` |
| long | `119` | `-8.4414` | `-0.0709` | `6` | `0.3361` |

Interpretation:

- ここでlong側の追加hard blockを増やす優先度は低い。
- side drift guard後も、shortが「強く見える」局面で逆方向に壊れている。
- `stay flat` を増やすなら、対象は全体ではなく `short/range_low_vol` とその近傍に絞るべき。

## Worst Contexts

| month | direction | context | session | trades | PnL | dir error | EV over | side gap | actual hit | pred hit |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| 2025-09 | short | range_low_vol | ny_overlap | `5` | `-144.2160` | `0.8000` | `50.9439` | `9.1561` | `0.0000` | `0.0000` |
| 2025-11 | short | range_low_vol | asia | `8` | `-72.8640` | `1.0000` | `39.8793` | `14.9119` | `0.2500` | `0.1250` |
| 2025-10 | short | range_low_vol | rollover | `4` | `-65.7444` | `1.0000` | `43.2598` | `12.7429` | `0.0000` | `0.5000` |
| 2025-12 | short | range_low_vol | rollover | `3` | `-65.4840` | `1.0000` | `47.1295` | `9.9583` | `0.3333` | `0.3333` |
| 2025-11 | short | range_low_vol | ny_overlap | `2` | `-47.5900` | `1.0000` | `43.2398` | `6.8310` | `0.0000` | `0.0000` |

The residual failure is not simply low confidence. It is a directional reversal / EV overestimate failure where the model still sees enough short edge.

## Time Pattern

Worst entry-hour contexts:

| month | context | hour | trades | PnL |
|---|---|---:|---:|---:|
| 2025-09 short/range_low_vol/ny_overlap | `13` | `5` | `-144.2160` |
| 2025-10 short/range_low_vol/rollover | `23` | `4` | `-65.7444` |
| 2025-12 short/range_low_vol/rollover | `23` | `3` | `-65.4840` |
| 2025-11 short/range_low_vol/asia | `0` | `2` | `-53.3280` |
| 2025-11 short/range_low_vol/ny_overlap | `13` | `2` | `-47.5900` |

This suggests a stateful exposure problem rather than a global session block. A static `ny_overlap` or `rollover` block would be too blunt and likely reintroduce NoTrade-like behavior.

## Decision

- Do not standardize `p10 + margin10` yet. It is a useful diagnostic baseline, not a final policy.
- Keep the new residual diagnostics script. Future candidate policies should be passed through the same negative-month decomposition before promotion.
- Next experiment should use only information available at decision time:
  - online context drawdown guard: track realized PnL by `direction + combined_regime + session_regime` within the current month or rolling recent trades;
  - if short/range-low-vol context drawdown breaches a threshold, require extra admission margin or stay flat for a cooldown;
  - compare against a prior-only version so we can separate true live adaptation from post-hoc overfitting.

## Verification

- `python3 -m py_compile scripts/experiments/residual_trade_failure_diagnostics.py`: OK
- `python3 -m unittest tests.test_residual_trade_failure_diagnostics`: OK, 2 tests
