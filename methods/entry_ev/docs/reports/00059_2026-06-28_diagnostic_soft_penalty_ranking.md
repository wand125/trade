# Diagnostic Soft Penalty Ranking

日時: 2026-06-28 19:52 JST
更新日時: 2026-06-28 19:52 JST

## 目的

candidate selectionで、PnLだけではなく複合診断の悪さもsoft penaltyとして順位へ反映する。

- direction errorが閾値を超えた分
- actual profit barrier miss率が閾値を超えた分
- predicted EVの実現PnLに対する過大評価が閾値を超えた分

を合算し、eligible候補のrobust scoreを下げる。hard gateで候補を全滅させず、tie-breakとして使えるかを検証する。

Report numbering note: this file is numbered from the internal file `日時`, not filesystem mtime or `更新日時`. Latest-report checks and renumbering must use the internal `日時`.

## 実装

`model-candidate-selection` に以下を追加した。

- `--diagnostic-penalty-weight`
- `--diagnostic-direction-error-rate-threshold`
- `--diagnostic-actual-profit-barrier-miss-rate-threshold`
- `--diagnostic-ev-overestimate-vs-realized-mean-threshold`
- `--diagnostic-direction-error-rate-scale`
- `--diagnostic-actual-profit-barrier-miss-rate-scale`
- `--diagnostic-ev-overestimate-vs-realized-mean-scale`

候補ごとに次を保存する。

- `diagnostic_direction_error_rate_excess`
- `diagnostic_actual_profit_barrier_miss_rate_excess`
- `diagnostic_ev_overestimate_vs_realized_mean_excess`
- `diagnostic_penalty`
- `robust_total_adjusted_pnl_min_cost`
- `robust_total_adjusted_pnl_min_base`

`group_loss_penalty` と同じく、eligible判定自体は壊さず、順位用のsoft penaltyとして扱う。

## Validation Ranking

入力は `combined_side_miss_joint` の4fold sweepを再利用した。base/costとも同じCSVを渡し、diagnostic rankingの影響だけを切り分けた。

diagnostic penalty条件:

- direction error threshold: `0.40`
- actual profit barrier miss smoothed threshold: `0.50`
- EV overestimate threshold: `15.0`
- diagnostic penalty weight: `1.0`

| candidate | time/loss penalty | time shrink | min side conf | validation min pnl | validation total pnl | direction error max | actual miss smoothed max | EV over-realized max | diagnostic penalty | robust min pnl |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline top, holding shrink | `6/6` | `0.25` | `0.00` | `80.0648` | `513.3876` | `0.463415` | `0.534884` | `16.530874` | `11.360710` | `68.704090` |
| diagnostic top, no shrink | `6/6` | `0.00` | `0.00` | `75.1682` | `531.6246` | `0.425000` | `0.523810` | `15.987300` | `5.868253` | `69.299947` |
| min side confidence | `6/6` | `0.00` | `0.55` | `65.0410` | `375.9450` | `0.413793` | `0.516129` | `14.760797` | `2.992214` | `62.048786` |

soft penaltyにより、validation topはholding shrink `0.25` から no-shrink entry penalty候補へ変わった。ただし、validation min pnlは `80.0648` から `75.1682` へ下がる。

## 2024-12 Fixed Check

diagnostic ranking topを2024-12反証月へ固定適用した。

| policy | 2024-12 adjusted pnl | raw pnl | trades | profit factor | max drawdown | forced exits |
|---|---:|---:|---:|---:|---:|---:|
| diagnostic top, no shrink | `-172.7944` | `-115.6510` | `46` | `0.4960` | `209.0240` | `2` |
| prior holding shrink combo | `-159.0158` | `-103.6750` | `46` | `0.5211` | `197.5966` | `2` |
| min side confidence diagnostic | `-91.9786` | `-54.0030` | `33` | `0.5963` | `139.2716` | `2` |

diagnostic soft penaltyで選ばれた候補は、2024-12ではprior holding shrink comboより悪化した。NoTradeにも届かない。

## 判断

diagnostic soft penaltyのインフラは有用なので残す。候補選定で、PnLが近い候補を比較するtie-breakや、過大評価・direction miss・barrier missの複合診断に使える。

ただし今回の閾値設定は標準policyへ昇格しない。validation上の診断値改善は2024-12 holdout改善に直結せず、単純なpost-hoc penaltyで反証月を救う方向は袋小路になりやすい。

次はこのsoft penaltyを主目的にせず、side/entry calibration、profit-barrier miss、regime別壊れ方の診断へ戻す。採用判定は引き続きwalk-forward / blind monthを優先する。

## Artifacts

- baseline selection: `data/reports/backtests/diagnostic_soft_penalty_baseline/20260628_104916_model_candidate_selection/`
- diagnostic selection: `data/reports/backtests/diagnostic_soft_penalty_validation/20260628_104938_model_candidate_selection/`
- diagnostic top fixed 2024-12: `data/reports/backtests/diagnostic_soft_penalty_validation/fixed_2024_12/20260628_105024_model_timed_ev_2024-12/`
