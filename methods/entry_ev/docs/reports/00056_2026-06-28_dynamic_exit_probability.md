# Dynamic Exit Probability Thresholds

日時: 2026-06-28 19:01 JST
更新日時: 2026-06-28 19:25 JST

## Summary

- Experiment ID: `dynamic_exit_probability`
- Status: validated, not promoted
- Main result: 保有中に `time_exit` / `loss_first` probabilityを再評価し、閾値を超えたら途中決済するdynamic / hazard-like exitを追加した。validation 4foldではbasic eligible候補が増え、top-minは entry penalty + holding shrink referenceの min pnl `80.0648` を `81.1178` へ少し改善した。`actual_profit_barrier_miss_rate_smoothed` 基準のstrict eligibleは残るが、`predicted_profit_barrier_miss_rate_smoothed` は高く、2024-12反証月ではdynamic topが adjusted pnl `-162.9304` とNoTradeに大きく負け、no-dynamic combo `-159.0158` よりもわずかに悪い。標準policyには昇格しない。
- Report numbering note: this file is numbered from the internal file `日時`, not filesystem mtime or `更新日時`.

## Implementation

`ModelPolicyConfig` とCLIへ追加:

- `time_exit_exit_threshold`
- `loss_first_exit_threshold`
- `model-policy --time-exit-exit-threshold`
- `model-policy --loss-first-exit-threshold`
- `model-sweep --time-exit-exit-thresholds`
- `model-sweep --loss-first-exit-thresholds`

動作:

- `timed_ev` / `fixed_horizon_ev` 系のstateful signal生成中、position保有中の各decision timestampで、現在sideの `pred_*_exit_event_prob_0` / `pred_*_exit_event_prob_2` を見る。
- 閾値がfiniteで、現在sideのprobabilityが閾値以上なら `current=0` にして予定exit時刻を消す。
- これはentry gateではなく、保有中の早期手仕舞いsignalである。実際の約定は既存backtestと同じく次足open。
- 閾値が `inf` の場合は従来挙動と互換。

## Setup

Predictions:

- validation: `experiments/20260628_064332_policy_exit_event_prob_p1_l1p2/predictions_valid.parquet`
- 2024-12 diagnostic: `experiments/20260628_064332_policy_exit_event_prob_p1_l1p2/predictions_test.parquet`

Validation grid:

- policy: `timed_ev`
- entry threshold: `10`
- short offset: `8`
- side margin: `1`
- holding columns: `pred_long_exit_event_minutes`, `pred_short_exit_event_minutes`
- min entry rank: `0.5`
- max predicted hold minutes: `480,720`
- time-exit penalty: `0,6`
- loss-first penalty: `0,6`
- time-exit holding shrink: `0,0.25`
- loss-first holding shrink: `0`
- time-exit exit threshold: `inf,0.75,0.90`
- loss-first exit threshold: `inf,0.50,0.75`
- profit-barrier hard gate: disabled
- extra side margins: `session_regime=asia:5,session_regime=rollover:5`

Artifacts:

- validation sweeps: `data/reports/backtests/dynamic_exit_probability/`
- validation summary: `data/reports/backtests/20260628_dynamic_exit_probability_summary.csv`
- 2024-12 fixed diagnostics: `data/reports/backtests/dynamic_exit_probability/fixed_2024_12/`
- 2024-12 fixed summary: `data/reports/backtests/20260628_dynamic_exit_probability_2024_12_fixed.csv`

Eligibility definition:

- all 4 folds present
- each fold adjusted pnl `>= 0`
- each fold trades `>= 10`
- forced exit max `<= 0.05`
- drawdown max `<= 100`
- strict additionally requires side share max `<= 0.85` and smoothed actual barrier miss max `<= 0.55`

## Validation 4fold

Strict eligible count using actual miss: `40`

Strict eligible count using predicted miss as an additional diagnostic gate: `0`

Basic eligible count: `96`

Top and references:

| label | time penalty | loss penalty | time shrink | time exit threshold | loss exit threshold | max hold | basic | min pnl | total pnl | min trades | forced max | drawdown max | smoothed miss max |
|---|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|
| dynamic top min-pnl | `6` | `6` | `0.25` | `0.90` | `0.75` | `720` | `true` | `81.1178` | `528.8282` | `36` | `0.000000` | `83.8800` | `0.928571` |
| dynamic top total | `6` | `6` | `0.00` | `0.90` | `0.75` | `720` | `true` | `76.2212` | `543.3552` | `36` | `0.000000` | `85.6920` | `0.928571` |
| combo no-dynamic reference | `6` | `6` | `0.25` | `inf` | `inf` | `720` | `true` | `80.0648` | `513.3876` | `36` | `0.023256` | `83.8800` | `0.928571` |
| entry penalty reference | `6` | `6` | `0.00` | `inf` | `inf` | `720` | `true` | `75.1682` | `531.6246` | `36` | `0.000000` | `85.6920` | `0.928571` |
| no-penalty dynamic high-turnover | `0` | `0` | `0.25` | `0.75` | `0.50` | `720` | `true` | `72.1134` | `377.7014` | `174` | `0.000000` | `65.3306` | `0.983607` |
| no-penalty no-dynamic reference | `0` | `0` | `0.00` | `inf` | `inf` | `720` | `false` | `12.5636` | `287.8596` | `37` | `0.055556` | `77.0800` | `0.962963` |

Interpretation:

- Dynamic exit thresholdは、entry penalty + holding shrinkのvalidation min pnlを `80.0648` から `81.1178` へ微改善した。
- total pnlでは `time_exit_exit_threshold=0.90` が entry penalty referenceの `531.6246` を `543.3552` へ上げた。
- ただし多くの候補で predicted miss max が `0.55` を大きく超える。これはモデル側のprofit-barrier確信が弱く、predicted missをhard gateにすると過剰に候補を落とすことを示す。
- no-penalty dynamicは取引数を増やしつつbasic gateに残ったが、side shareとsmoothed missが悪く、安定したedgeとは見なしにくい。

## 2024-12 Diagnostic

Fixed diagnostics:

| label | time penalty | loss penalty | time shrink | time exit threshold | loss exit threshold | adjusted pnl | raw pnl | trades | profit factor | max drawdown | forced exits | direction error | smoothed miss | avg holding |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| no-penalty dynamic high-turnover | `0` | `0` | `0.25` | `0.75` | `0.50` | `-104.0014` | `-42.6550` | `171` | `0.7174` | `151.3056` | `2` | `0.6316` | `0.9075` | `129.2105` |
| combo no-dynamic reference | `6` | `6` | `0.25` | `inf` | `inf` | `-159.0158` | `-103.6750` | `46` | `0.5211` | `197.5966` | `2` | `0.5870` | `0.9167` | `542.1087` |
| dynamic top min-pnl | `6` | `6` | `0.25` | `0.90` | `0.75` | `-162.9304` | `-106.9850` | `46` | `0.5146` | `195.9686` | `2` | `0.5870` | `0.9167` | `539.9783` |
| entry penalty reference | `6` | `6` | `0.00` | `inf` | `inf` | `-172.7944` | `-115.6510` | `46` | `0.4960` | `209.0240` | `2` | `0.5870` | `0.8958` | `544.4783` |
| dynamic top total | `6` | `6` | `0.00` | `0.90` | `0.75` | `-176.3334` | `-118.6480` | `46` | `0.4905` | `207.3960` | `2` | `0.5870` | `0.8958` | `541.8478` |
| no-penalty no-dynamic reference | `0` | `0` | `0.00` | `inf` | `inf` | `-227.4118` | `-158.4170` | `63` | `0.4507` | `246.1494` | `3` | `0.5397` | `0.9077` | `461.0000` |

Key diagnostics:

- 2024-12では全候補がNoTradeに負けた。
- `penalty=6/6`, `time shrink=0.25` にdynamic thresholdを足すと、validationでは微改善したが、2024-12では `-159.0158` から `-162.9304` へわずかに悪化した。
- no-penalty dynamic high-turnoverは `-104.0014` まで損失を縮めたが、direction error `0.6316`、smoothed miss `0.9075` で、未来月に壊れにくいとは言えない。
- dynamic exitは保有時間を短くしてdrawdownを少し抑えることはあるが、方向選択ミスとprofit-barrier missを解決できていない。

## Decision

- `time_exit_exit_threshold` / `loss_first_exit_threshold` は実装として残す。
- validation-onlyで選ぶとactual miss基準のstrict候補は残るが、predicted miss診断と2024-12反証に耐えないため標準policyへ昇格しない。
- 今回の結果は「exit timingだけではなく、entry side calibrationとprofit-barrier miss calibrationを同時に扱う必要がある」という反証として扱う。
- 次はdynamic exit単独の深掘りではなく、side/entry calibration、group-loss soft ranking、profit-barrier/exit-event signalの組み合わせを、NoTradeへ近づけすぎない範囲で比較する。

## Next Actions

1. dynamic exit thresholdは探索軸として残すが、標準候補の必須部品にはしない。
2. no-penalty dynamic high-turnoverは参考値として残し、未知月でのdirection errorとmiss率を追加holdoutで確認する。
3. side/entry calibrationとprofit-barrier missの同時制御へ戻る。exit制御だけで負け月を救う方向には寄せすぎない。
