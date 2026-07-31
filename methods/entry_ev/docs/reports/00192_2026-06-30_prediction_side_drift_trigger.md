# Prediction Side Drift Trigger

日時: 2026-06-30 09:23 JST
更新日時: 2026-06-30 09:23 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- `short_budget_drift_trigger_selection.py` に prediction month summary を読ませ、prior window の side prediction drift をtrigger metricとして使えるようにした。
- 追加metricは `recent_pred_short_bias_mean/max`, `recent_pred_short_share_mean`, `recent_actual_short_share_mean`, `recent_pred_match_rate_mean`, `recent_pred_side_score_mean`。
- 目的は、実現PnLが悪化する前に prediction side drift だけで `gap5/budget0` から defensive `gap0/budget0` へ落とせるか確認すること。
- 結果は否定的。月次平均のprediction-share triggerは発火が早すぎ、多くは常時defensive化して min4 total `+150.3206` に落ちた。
- 例外的に `recent_actual_short_share_mean < 0.45` は min4 total `+210.3068` まで出たが、00191 の realized trigger `+232.2466` には届かない。
- min8ではどのprediction系triggerも defensive `gap0/budget0` に潰れ、total `-15.0104` のまま。
- 実装は残すが、prediction-share月次平均triggerは標準採用しない。次は context/session単位のside drift alert、または realized first-loss triggerとのAND条件を試す。

## Artifacts

- Script: `scripts/experiments/short_budget_drift_trigger_selection.py`
- min4 output: `data/reports/backtests/short_budget_prediction_drift_trigger_selection_min4/`
- min8 output: `data/reports/backtests/short_budget_prediction_drift_trigger_selection_min8/`

Prediction month summaries:

- `data/reports/modeling/20260629_133501_side_drift_reference_2025_01_08_coststress_260/prediction_month_summary.csv`
- `data/reports/modeling/20260629_133440_side_drift_fresh_2025_09_12_coststress_260/prediction_month_summary.csv`

Input sweep:

- `data/reports/backtests/20260630_000340_short_raw_gap_entry_budget_zero_p10_margin10/summary_by_run.csv`

## Method

The selector still uses only months before the target month.

Prediction summary rows are merged by month, then recent prior months are summarized into trigger metrics. The tested family was:

```text
primary candidates:   gap5/budget0, gap5/budget1, gap0/budget1, gap10/budget0
defensive candidate:  gap0/budget0
recent window:        3 prior months
```

This checks whether prediction side drift can be a leading alert before realized short PnL deteriorates.

## Results

### min_train_months=4

Top rows:

| trigger metric | threshold | triggered months | trades | total PnL | worst month | max DD | short PnL |
|---|---:|---:|---:|---:|---:|---:|---:|
| `recent_actual_short_share_mean <` | `0.45` | `6` | `341` | `210.3068` | `-46.0150` | `129.7364` | `132.8174` |
| `recent_actual_short_share_mean <` | `0.45` | `6` | `347` | `191.1992` | `-63.8486` | `133.5398` | `113.7098` |
| `recent_actual_short_share_mean <` | `0.45` | `6` | `354` | `187.6472` | `-79.0794` | `145.2258` | `110.1578` |
| always defensive / prediction over-trigger | `n/a` | `8` | `303` | `150.3206` | `-45.4774` | `126.7826` | `72.8312` |

For comparison, 00191 realized trigger `gap5/budget0 -> gap0/budget0` with `recent_short_losing_months >= 1` was:

| source | total PnL | worst month | max DD | short PnL |
|---|---:|---:|---:|---:|
| 00191 realized trigger | `232.2466` | `-46.0150` | `129.7364` | `154.7572` |
| best prediction/label-share trigger here | `210.3068` | `-46.0150` | `129.7364` | `132.8174` |
| common prediction-share over-trigger | `150.3206` | `-45.4774` | `126.7826` | `72.8312` |

The best `actual_short_share_mean < 0.45` rule selects defensive budget0 in 2025-05/06, returns to `gap5/budget0` in 2025-07/08, then selects defensive again from 2025-09.

| target month | selected | trigger value | triggered | total PnL | short PnL | long PnL |
|---|---|---:|---|---:|---:|---:|
| 2025-05 | `gap0/budget0` | `0.404250` | true | `19.7334` | `65.7404` | `-46.0070` |
| 2025-06 | `gap0/budget0` | `0.424596` | true | `164.2618` | `35.8688` | `128.3930` |
| 2025-07 | `gap5/budget0` | `0.506772` | false | `87.3370` | `83.7922` | `3.5448` |
| 2025-08 | `gap5/budget0` | `0.490035` | false | `-46.0150` | `-23.9666` | `-22.0484` |
| 2025-09 | `gap0/budget0` | `0.428701` | true | `-45.4774` | `-32.5054` | `-12.9720` |
| 2025-10 | `gap0/budget0` | `0.360173` | true | `14.3800` | `4.3600` | `10.0200` |
| 2025-11 | `gap0/budget0` | `0.357063` | true | `10.5510` | `-11.9880` | `22.5390` |
| 2025-12 | `gap0/budget0` | `0.385931` | true | `5.5360` | `11.5160` | `-5.9800` |

Pure prediction share examples such as `recent_pred_short_bias_mean >= 0.15` trigger every target month, making the policy always defensive:

| target month | selected | trigger value | total PnL |
|---|---|---:|---:|
| 2025-05 | `gap0/budget0` | `0.252134` | `19.7334` |
| 2025-06 | `gap0/budget0` | `0.275125` | `164.2618` |
| 2025-07 | `gap0/budget0` | `0.281634` | `13.3882` |
| 2025-08 | `gap0/budget0` | `0.219194` | `-32.0524` |
| 2025-09 | `gap0/budget0` | `0.185638` | `-45.4774` |
| 2025-10 | `gap0/budget0` | `0.240161` | `14.3800` |
| 2025-11 | `gap0/budget0` | `0.336221` | `10.5510` |
| 2025-12 | `gap0/budget0` | `0.419476` | `5.5360` |

### min_train_months=8

The 2025-09..12 target window collapses to defensive `gap0/budget0` for all useful prediction triggers:

| trigger family | target months | total PnL | worst month | max DD | short PnL |
|---|---:|---:|---:|---:|---:|
| always defensive / realized fallback | `4` | `-15.0104` | `-45.4774` | `81.8860` | `-28.6174` |
| prediction-share triggers | `4` | `-15.0104` | `-45.4774` | `81.8860` | `-28.6174` |
| actual label-share trigger | `4` | `-15.0104` | `-45.4774` | `81.8860` | `-28.6174` |

## Interpretation

- Monthly prediction drift is real, but too coarse as a direct trigger.
- `pred_short_bias` and `pred_match_rate` already look bad before 2025-05, so they push the model into defensive mode too early.
- `actual_short_share_mean < 0.45` is closer, but it still reduces early profitable short exposure and loses to the realized-PnL trigger.
- This supports the current view that side drift is context-specific. Monthly averages flatten the signal and cannot separate profitable early short regimes from late harmful short regimes.

## Decision

- Keep optional `--prediction-month-summaries` support and the new trigger metrics.
- Do not promote prediction-share monthly triggers to standard policy.
- Do not replace 00191 realized trigger with this family.
- Treat this as a negative diagnostic: the next detector should be lower-granularity than all-month averages and should combine prediction drift with realized first-loss or active context state.

Next steps:

- Build context/session-level prediction drift summaries instead of month-level averages.
- Test AND triggers such as `pred_short_bias high` plus `recent_short_losing_months >= 1`.
- Reuse prediction drift features as selector diagnostics, not direct hard triggers, until they show prior-only improvement over realized trigger.

## Verification

- `python3 -m py_compile scripts/experiments/short_budget_drift_trigger_selection.py tests/test_short_budget_drift_trigger_selection.py`: OK
- `python3 -m unittest tests.test_short_budget_drift_trigger_selection tests.test_short_budget_guard_selection tests.test_backtest tests.test_context_drawdown_guard_selection tests.test_online_context_state_diagnostics tests.test_online_context_feature_model tests.test_side_context_interaction_guard_apply tests.test_docs_reports`: OK, 123 tests
- `git diff --check`: OK
