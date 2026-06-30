# Triggered Profit-Miss Same-Family Check

日時: 2026-06-30 11:51 JST
更新日時: 2026-06-30 11:51 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00202 の `signal_short_raw_gap_or_triggered_profit_miss` を、条件再探索なしで同一列familyの別期間へ固定適用した。
- 利用できた完全同一risk列は `2024-11, 2024-12, 2025-01..04`。純2024だけで `min_prior_months=4` を満たすには2024前半の同一risk列が不足しているため、今回は「2024-11/12を含む same-family smoke」として扱う。
- baseline `coststress_maxhold_260` は 6ヶ月 total `+258.9936`, worst `-26.2112`。
- side drift `p10 + replm10` は total `+209.8370`, worst `-36.9134`。
- `gap5/budget0` は total `+445.8266`, worst `-39.0766` まで改善した。
- 00202の triggered profit-miss min4 は total `+367.8768`, worst `-39.0766`。2025-03/04で発火し、どちらも勝ちを削った。
- 結論: 00202の triggered profit-miss はこの same-family smoke では汎化せず、標準候補から一段下げる。現時点では `gap5/budget0` 単体の方が強い。

## Artifacts

- Holding max baseline: `data/reports/backtests/20260630_024935_20260630_114900_holding_max260_samefamily_2024_11_2025_04/`
- Side drift p10/replm10: `data/reports/backtests/20260630_025000_20260630_115000_side_drift_p10_replm10_samefamily_2024_11_2025_04/`
- Short raw-gap budget: `data/reports/backtests/20260630_025026_20260630_115100_short_raw_gap_budget_samefamily_2024_11_2025_04/`
- Triggered hook fixed apply: `data/reports/backtests/20260630_025050_20260630_115200_triggered_profit_miss_samefamily_2024_11_2025_04/`

Inputs:

- Prediction frame: `data/reports/modeling/20260629_132211_stateful_risk_mean_match_session_floor_lowered_apply_2025_09_12/predictions_validation_oof_stateful_risk_model.parquet`
- Base config: `data/reports/backtests/20260629_exit_shortening_failure_policy/stateful_p5/20260629_121701_model_timed_ev_2025-01/config.json`
- Data: `data/processed/histdata/xauusd/xauusd_m1.parquet`

## Method

Fixed conditions copied from 00202:

```text
source policy: coststress 260 + stateful risk5 + side drift p10 + replacement margin10
short budget: signal_short_raw_gap, short_gap_threshold=5, context_entry_budget=0
replacement hook: signal_short_raw_gap_or_triggered_profit_miss
trigger source: gap5/budget0 summary_by_run
trigger: recent 3 prior months, short losing month count >= 1
min_prior_months: 4
profit_miss: pred_short_profit_barrier_hit < 0.5
```

No threshold or trigger parameter was changed after seeing this range.

## Aggregate Results

| variant | months | trades | total PnL | worst month | max DD | short PnL | long PnL |
|---|---:|---:|---:|---:|---:|---:|---:|
| `coststress_maxhold_260` baseline | `6` | `641` | `+258.9936` | `-26.2112` | `220.9196` | `+77.8462` | `+181.1474` |
| `p10 + replm10` source | `6` | `566` | `+209.8370` | `-36.9134` | `203.0236` | `+86.4632` | `+123.3738` |
| `gap0/budget0` | `6` | `397` | `+190.6394` | `-50.5156` | `109.0260` | `+67.2656` | `+123.3738` |
| `gap5/budget0` | `6` | `495` | `+445.8266` | `-39.0766` | `125.3028` | `+322.4528` | `+123.3738` |
| triggered low-EV min4 | `6` | `494` | `+441.0746` | `-39.0766` | `125.3028` | `+317.7008` | `+123.3738` |
| triggered profit-miss min4 | `6` | `466` | `+367.8768` | `-39.0766` | `125.3028` | `+244.5030` | `+123.3738` |

## Monthly Results

| month | gap5/budget0 | triggered profit-miss | trigger active | note |
|---|---:|---:|---|---|
| 2024-11 | `-39.0766` | `-39.0766` | no | no prior |
| 2024-12 | `-25.0670` | `-25.0670` | no | prior months `< 4` |
| 2025-01 | `+65.1106` | `+65.1106` | no | prior months `< 4` |
| 2025-02 | `+108.4552` | `+108.4552` | no | prior months `< 4` |
| 2025-03 | `+69.1790` | `+33.6446` | yes | hook removed profitable short exposure |
| 2025-04 | `+267.2254` | `+224.8100` | yes | hook removed profitable short exposure |

The fixed `gap5 -> gap0` switch would also be worse on the triggered months: `2025-03` gap0 is `+13.8738` vs gap5 `+69.1790`, and `2025-04` gap0 is `+119.2760` vs gap5 `+267.2254`.

## Interpretation

- The 00202 improvement was not robust under this same-family smoke. The same trigger fired after one prior short losing month, but here the subsequent `profit_miss` rows were not bad replacement trades.
- `gap5/budget0` is the more stable rule in this range. It improves over the source p10/replm10 by `+235.9896` and over holding max baseline by `+186.8330`, despite slightly worse worst month than baseline.
- `gap0/budget0` is too defensive here. It suppresses many profitable shorts and underperforms both source and gap5.
- This does not fully invalidate 00202 because pure 2024 pre-2024-11 same-risk columns are missing, but it is enough to stop treating triggered profit-miss as the strongest candidate.

## Decision

- Downgrade triggered profit-miss from strongest candidate to diagnostic candidate.
- Keep `signal_short_raw_gap_or_triggered_profit_miss` infrastructure because it is useful for controlled fixed checks.
- Promote `gap5/budget0` as the current best candidate to validate next.
- Do not change 00202 thresholds to fit this range. The failed fixed apply is evidence against the rule, not a tuning prompt.

## Next

1. Build a wider same-risk prediction frame for 2024-07/09/11/12 or other earlier months, so `min_prior_months=4` can be tested inside pure 2024 without borrowing 2025.
2. Fixed-apply `gap5/budget0` itself to additional same-family windows; it is the stable winner in both 2025 all-window and this smoke.
3. Revisit profit-miss only after `pred_short_profit_barrier_hit` is available as a calibrated probability, not only a 0/1 class.

## Verification

- Holding max baseline artifact generated: OK
- Side drift p10/replm10 artifact generated: OK
- Short raw-gap budget artifact generated: OK
- Triggered hook fixed apply artifact generated: OK
