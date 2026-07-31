# Entry EV External Hybrid Loss Target Insight

日時: 2026-07-02 07:57 JST
更新日時: 2026-07-02 07:57 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00270でrejectした外部HGB+MLP hybrid `2025-09..12` のq99/q95損失を、blacklist tuningではなく教師/特徴量設計の材料として分解した。
- `entry_ev_multifamily_policy_trade_enrichment.py` でq99/q95の実行tradeをprior-guard predictionへjoinした。
- q99は6 trades / total `-28.3940`。方向誤り率 `0.6667`、平均EV過大 `30.7672`、exit regret合計 `177.5340`。
- q95は10 trades / total `+0.0820`。方向誤り率 `0.6000`、平均EV過大 `28.8171`、exit regret合計 `356.6480`。
- 損失月 `2025-09,2025-12` に絞ると、q99は4 trades / total `-37.5540`、q95は5 trades / total `-33.7840`。どちらも `no_edge_entry=0` で、全tradeに同方向oracle利益余地がある。
- 外部hybrid fold全体16 tradeでは `same_side_missed_loss_target`, `low_capture_loss_target`, `late_exit_regret_loss_target` が7件 / target PnL `-82.5360`、false側は `+54.2240`。
- 判断: 00270の失敗はentry候補が完全に無価値というより、同方向oracle利益を実行exitで取り逃すexit-capture failureと、EVの実現可能性過大評価が中心。次はentry hard blockではなく、exit capture / executable EV / direction-side robustnessの教師を分けて学習側へ戻す。

## Artifacts

- Trade enrichment:
  - `data/reports/backtests/20260701_225551_20260702_entry_ev_external_hybrid_2025_0912_trade_enrichment_s1/`
- q99 loss residual:
  - `data/reports/backtests/20260701_225604_20260702_entry_ev_external_hybrid_2025_0912_q99_loss_residual_s1/`
- q95 loss residual:
  - `data/reports/backtests/20260701_225604_20260702_entry_ev_external_hybrid_2025_0912_q95_loss_residual_s1/`
- Exit target insight:
  - `data/reports/backtests/20260701_225714_20260702_entry_ev_external_hybrid_2025_0912_exit_target_insight_s1/`

## Enrichment

| candidate | trades | total pnl | loss pnl | win rate | direction error | exit regret sum | EV overestimate mean | exit capture ratio mean |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| q99/floor5/rank90 | `6` | `-28.3940` | `-45.7440` | `0.3333` | `0.6667` | `177.5340` | `30.7672` | `0.1473` |
| q95/floor5/rank90 | `10` | `+0.0820` | `-47.6880` | `0.5000` | `0.6000` | `356.6480` | `28.8171` | `0.1356` |

Reading:

- q95のtotalはほぼflatだが、loss pnlとexit regretは大きい。
- q99/q95ともdirection errorは高いが、同方向oracle利益余地も残っている。
- したがって単純なdirection blockerではなく、方向判断とexit captureを別targetに分ける必要がある。

## Loss Months

q99, months `2025-09,2025-12`:

| metric | value |
|---|---:|
| trades | `4` |
| total pnl | `-37.5540` |
| loss pnl | `-45.0240` |
| same-side oracle total | `77.6700` |
| actual best total | `174.6900` |
| exit regret sum | `115.2240` |
| best side regret sum | `212.2440` |
| direction error rate | `0.7500` |
| no edge rate | `0.0000` |
| EV overestimate positive rate | `1.0000` |

q95, months `2025-09,2025-12`:

| metric | value |
|---|---:|
| trades | `5` |
| total pnl | `-33.7840` |
| loss pnl | `-45.0240` |
| same-side oracle total | `104.4930` |
| actual best total | `214.3900` |
| exit regret sum | `138.2770` |
| best side regret sum | `248.1740` |
| direction error rate | `0.8000` |
| no edge rate | `0.0000` |
| EV overestimate positive rate | `1.0000` |

The loss-month rows are not no-edge entries. They are mostly executable-capture failures under high EV overestimate.

## Loss Trade Patterns

Largest repeated loss rows:

| month | side | context | pnl | same-side oracle | opposite oracle | direction error | exit regret | oracle hold gap |
|---|---|---|---:|---:|---:|---|---:|---:|
| 2025-12 | short | `down_high_vol/rollover` | `-26.7600` | `17.2400` | `23.0700` | true | `44.0000` | `611.0` |
| 2025-09 | short | `range_low_vol/ny_late` | `-12.8160` | `40.3900` | `37.6800` | false | `53.2060` | `445.0` |
| 2025-09 | short | `down_low_vol/ny_overlap` | `-5.4480` | `3.7900` | `34.2000` | true | `9.2380` | `-59.0` |

Reading:

- `range_low_vol/ny_late` is not a side error; same-side oracle is best, but exit captures none of it.
- `down_high_vol/rollover` is both side-regret and same-side capture failure.
- `down_low_vol/ny_overlap` is a smaller loss where the oracle indicates earlier exit.
- This supports a two-head design: direction-side robustness and exit-capture/executable-EV calibration should be trained separately.

## Exit Targets

Across q99/q95 enriched trades, 16 rows:

| target | count | rate | target pnl | false pnl |
|---|---:|---:|---:|---:|
| `profit_barrier_miss_loss_target` | `6` | `0.3750` | `-90.0480` | `+61.7360` |
| `same_side_missed_loss_target` | `7` | `0.4375` | `-82.5360` | `+54.2240` |
| `low_capture_loss_target` | `7` | `0.4375` | `-82.5360` | `+54.2240` |
| `late_exit_regret_loss_target` | `7` | `0.4375` | `-82.5360` | `+54.2240` |
| `hold_too_long_loss_target` | `2` | `0.1250` | `-10.8960` | `-17.4160` |
| `exit_shortening_residual_target` | `0` | `0.0000` | `0.0000` | `-28.3120` |
| `forced_exit_loss_target` | `0` | `0.0000` | `0.0000` | `-28.3120` |

Chronological calibration on this tiny fold is diagnostic only. `exit_plan` gave pooled AUC `0.7429` for same-side missed / low-capture / late-exit-regret, but bucket support is too small to promote a policy.

## Decision

Accepted:

- loss-target insight for external hybrid 2025-09..12
- `same_side_missed_loss`, `low_capture_loss`, `late_exit_regret_loss`, and `profit_barrier_miss_loss` as next teacher-design axes

Rejected:

- using these loss rows as static context blacklists
- reviving q99/q95 prior guard as a policy candidate
- treating tiny-fold chronological AUC as policy evidence

Standard policy remains NoTrade.

## Next

1. Build a dense or selected-candidate exit-capture target that predicts realized executable capture, not oracle best EV alone.
2. Add an EV calibration layer that discounts `pred_taken_ev` by predicted capture probability / capture ratio.
3. Keep direction-side inversion as a separate head; do not collapse it into a broad no-trade label.
4. Evaluate these heads through prior-only / walk-forward admission, not same-window threshold rescue.

## Verification

- q99/q95 trade enrichment: OK
- q99 loss residual diagnostics: OK
- q95 loss residual diagnostics: OK
- exit target insight diagnostics: OK
