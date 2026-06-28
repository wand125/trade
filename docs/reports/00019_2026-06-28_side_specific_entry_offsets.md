# Side Specific Entry Offsets

日時: 2026-06-28 08:38 JST
更新日時: 2026-06-28 08:43 JST

## 目的

前回候補は 2025-02 のshort側が弱く、わずかなslippageでNoTrade以下になった。

そこで long / short でentry thresholdを分け、特にshort側だけ参入条件を厳しくできるようにする。

注意:

- validationで選ぶ。
- fixed test 2024-12 / 2025-02 は診断に使い、test結果を見た後の採用選択はしない。
- 評価倍率は profit `1.0` / loss `1.20`。

## 実装

`trade_data.backtest` に以下を追加した。

- `ModelPolicyConfig.long_entry_threshold_offset`
- `ModelPolicyConfig.short_entry_threshold_offset`
- `model-policy --long-entry-threshold-offset`
- `model-policy --short-entry-threshold-offset`
- `model-sweep --long-entry-threshold-offsets`
- `model-sweep --short-entry-threshold-offsets`

実効entry threshold:

```text
long_entry_threshold = entry_threshold + long_entry_threshold_offset
short_entry_threshold = entry_threshold + short_entry_threshold_offset
```

`stateless_ev`, `stateful_ev`, `timed_ev`, `fixed_horizon_ev` のentry判定に適用する。保有中のflip判定では、反対sideのthresholdを使う。

## Validation

Model:

- `experiments/20260627_231921_full_fixed_horizon_targets_p1_l1p2/`

共通policy:

- policy: `fixed_horizon_ev`
- max wait regret: `4`
- min entry rank: `0.5`
- require profit barrier: false
- extra side margin: `session_regime=asia:5,session_regime=rollover:5`

Grid:

- entry threshold: `0,2,4`
- long offset: `0`
- short offset: `0,2,4,6,8`
- side margin: `1,2,3`

Validation months:

- 2024-07
- 2024-09
- 2024-11
- 2025-01

### No-Cost Summary

Artifact:

- `data/reports/backtests/20260627_233509_model_sweep_summary/`

Top by min-pnl:

| entry | short offset | side margin | mean pnl | min pnl | min trades | max DD | forced exit max |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 4 | 2 | 49.8759 | 34.2132 | 47 | 48.4680 | 0.0213 |
| 2 | 2 | 2 | 36.2206 | 25.0338 | 34 | 47.1960 | 0.0294 |
| 0 | 8 | 2 | 41.1605 | 23.7572 | 44 | 42.9312 | 0.0227 |

### Cost-Aware Summary

Cost-aware validation:

- spread points: `0.1`
- slippage points: `0.05`
- execution delay bars: `0`

Artifact:

- `data/reports/backtests/20260627_233552_model_sweep_summary/`

Top by min-pnl:

| entry | short offset | side margin | mean pnl | min pnl | min trades | max DD | forced exit max |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 4 | 2 | 38.6210 | 22.9272 | 47 | 50.2162 | 0.0213 |
| 2 | 2 | 2 | 27.4498 | 17.5938 | 34 | 48.8760 | 0.0294 |
| 0 | 8 | 2 | 31.2031 | 13.7412 | 44 | 45.1312 | 0.0227 |

no-cost / cost-aware ともに、単純なtop-min基準では `entry=0`, `short offset=4`, `side margin=2` が選ばれる。

## Fixed Test

### Validation Top-Min Candidate

Policy:

- entry threshold: `0`
- long offset: `0`
- short offset: `4`
- side margin: `2`

Artifacts:

- `data/reports/backtests/20260627_233606_model_fixed_horizon_ev_2024-12/`
- `data/reports/backtests/20260627_233606_model_fixed_horizon_ev_2025-02/`

| month | adjusted pnl | raw pnl | trades | win rate | profit factor | max DD | forced exits | long pnl | short pnl |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2024-12 | 22.7102 | 40.1860 | 67 | 0.5075 | 1.2166 | 43.9546 | 2 | 32.3996 | -9.6894 |
| 2025-02 | 0.3502 | 31.5620 | 71 | 0.4930 | 1.0019 | 103.9020 | 0 | 5.3460 | -4.9958 |

前回候補よりvalidationは強いが、fixed testでは2025-02のedgeがさらに薄くなった。

### Validation Rank-3 Diagnostic Candidate

Policy:

- entry threshold: `0`
- long offset: `0`
- short offset: `8`
- side margin: `2`

Artifacts:

- `data/reports/backtests/20260627_233636_model_fixed_horizon_ev_2024-12/`
- `data/reports/backtests/20260627_233637_model_fixed_horizon_ev_2025-02_1/`

| month | adjusted pnl | raw pnl | trades | win rate | profit factor | max DD | forced exits | long pnl | short pnl |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2024-12 | 27.4184 | 42.0730 | 58 | 0.5172 | 1.3118 | 48.2654 | 2 | 32.2696 | -4.8512 |
| 2025-02 | 26.8074 | 53.5140 | 61 | 0.5902 | 1.1673 | 100.0446 | 0 | 6.5754 | 20.2320 |

この候補はfixed test上では前回候補より良いが、test結果を見た後の採用はしない。次のblind holdoutまたは事前登録したvalidation基準で再確認する。

## Cost Sensitivity

`short offset=8` 診断候補のcost sensitivity。

Artifacts:

- `data/reports/backtests/20260627_233703_model_cost_sensitivity_2024-12/`
- `data/reports/backtests/20260627_233703_model_cost_sensitivity_2025-02/`

主要点:

| month | spread | slippage | delay bars | adjusted pnl | max DD |
|---|---:|---:|---:|---:|---:|
| 2024-12 | 0.0 | 0.00 | 0 | 27.4184 | 48.2654 |
| 2024-12 | 0.1 | 0.05 | 0 | 14.6984 | 52.1054 |
| 2024-12 | 0.2 | 0.10 | 1 | -7.0904 | 56.1084 |
| 2025-02 | 0.0 | 0.00 | 0 | 26.8074 | 100.0446 |
| 2025-02 | 0.1 | 0.05 | 0 | 13.6074 | 102.6046 |
| 2025-02 | 0.2 | 0.10 | 1 | 16.8146 | 100.3442 |

2024-12はcostとdelayでedgeが消えやすい。2025-02はdelay 1barで改善する組み合わせがあり、約定時刻仮定への感度が残る。

## Failure Analysis

Artifacts:

- `data/reports/backtests/20260627_233729_analyze_fixed_horizon_short_offset8_2024-12/`
- `data/reports/backtests/20260627_233729_analyze_fixed_horizon_short_offset8_2025-02/`

Summary:

| month | direction error | predicted side error | exit regret sum | EV overestimate vs realized | long pnl | short pnl |
|---|---:|---:|---:|---:|---:|---:|
| 2024-12 | 0.6034 | 0.6034 | 621.8296 | 3.0697 | 32.2696 | -4.8512 |
| 2025-02 | 0.4754 | 0.4754 | 1189.8406 | 4.7225 | 6.5754 | 20.2320 |

Regime notes:

- 2024-12: `low_vol` が `-4.1576`、`normal_vol` が `+31.5760`。short tradeは `-4.8512` で、short direction error `0.8182`。
- 2025-02: `london` が `+31.4860`、`ny_overlap` が `+23.7540`、`ny_late` が `-18.6224`、`asia` が `-7.7186`。
- 2025-02: actual best side が short のtradeは `+68.4936` だが、actual best side が long のtradeは `-41.6862`。

## 判断

short専用entry threshold offsetは有効な調整軸。

ただし、`short offset=4` のvalidation top-min候補はfixed testで弱く、`short offset=8` はfixed testで良いがtestを見てから選んだ診断候補になる。

今後の選択基準は、単純なvalidation min pnlだけではなく次を含める。

- cost-aware validation min pnl
- 周辺offsetでも成績が残る台地
- side別PnLの片側崩れ
- regime/session別の損失集中
- max drawdown
- execution delayへの感度

## 次

1. `short offset=8` は現行fixed testでは採用せず、次の事前登録validation基準で再検証する。
2. 新しい未使用holdout月を追加し、2024-12/2025-02に合わせ込まない。
3. exit regretが大きいため、hazard-like close probabilityまたはbarrier hit probability calibrationを追加する。
4. cost-aware validationを標準の候補選択条件へ昇格する。
