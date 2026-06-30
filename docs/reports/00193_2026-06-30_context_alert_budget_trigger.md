# Context Alert Budget Trigger

日時: 2026-06-30 09:32 JST
更新日時: 2026-06-30 09:32 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- `short_budget_drift_trigger_selection.py` に `--side-drift-alerts` を追加した。
- 目的は、00192で粗すぎた月次prediction-share平均の代わりに、`combined_regime + session_regime` 単位の side drift alert を budget0 trigger に使うこと。
- alert単独metricは早すぎる。min4では `recent_short_side_drift_alert_count`, `recent_short_side_drift_loss_bias_sum`, `recent_short_side_drift_min_pnl` などがほぼ常時 defensive `gap0/budget0` へ倒れ、total `+150.3206` 止まり。
- composite metric `recent_short_alert_and_short_losing_months >= 1` は min4 total `+232.2466`, worst `-46.0150` で、00191 realized triggerと同じ成績になった。
- min8はどのcontext alert系でも total `-15.0104`, worst `-45.4774` のまま。
- 結論: context alertは単独triggerとしては採用しない。ただし `alert AND primary short losing month` は00191と同じ発火を、context drift付きの損失として説明できる。次は月全体のbudget0ではなく、alert contextだけのentry budget / admission marginを試す。

## Artifacts

- Script: `scripts/experiments/short_budget_drift_trigger_selection.py`
- min4 output: `data/reports/backtests/short_budget_context_alert_trigger_selection_min4/`
- min8 output: `data/reports/backtests/short_budget_context_alert_trigger_selection_min8/`

Side drift alert inputs:

- `data/reports/modeling/20260629_133501_side_drift_reference_2025_01_08_coststress_260/side_drift_alerts.csv`
- `data/reports/modeling/20260629_133440_side_drift_fresh_2025_09_12_coststress_260/side_drift_alerts.csv`

Backtest candidate input:

- `data/reports/backtests/20260630_000340_short_raw_gap_entry_budget_zero_p10_margin10/summary_by_run.csv`

## Implementation

Added trigger metrics:

- `recent_side_drift_alert_count`
- `recent_short_side_drift_alert_count`
- `recent_short_side_drift_alert_months`
- `recent_short_side_drift_loss_bias_sum`
- `recent_short_side_drift_min_pnl`
- `recent_short_alert_and_short_losing_months`

The composite metric counts recent months where both are true:

1. at least one prior `side_drift_alerts.csv` row has `side=short` and `is_alert=true`,
2. the primary short-budget candidate has `short_adjusted_pnl < 0` in that same month.

This avoids using target-month alerts and keeps the trigger candidate-specific.

## Results

### min_train_months=4

Top rows:

| trigger metric | threshold | triggered months | trades | total PnL | worst month | max DD | short PnL |
|---|---:|---:|---:|---:|---:|---:|---:|
| `recent_short_alert_and_short_losing_months >=` | `1` | `4` | `374` | `232.2466` | `-46.0150` | `129.7364` | `154.7572` |
| `recent_short_alert_and_short_losing_months >=` | `1` | `4` | `389` | `206.7014` | `-63.8486` | `133.5398` | `129.2120` |
| `recent_short_alert_and_short_losing_months >=` | `1` | `6` | `354` | `187.6472` | `-79.0794` | `145.2258` | `110.1578` |
| always defensive / alert-only over-trigger | `n/a` | `8` | `303` | `150.3206` | `-45.4774` | `126.7826` | `72.8312` |

For `gap5/budget0 -> gap0/budget0` with composite threshold `>= 1`:

| target month | selected | composite value | triggered | recent short losing months | recent short alerts | total PnL | short PnL |
|---|---|---:|---|---:|---:|---:|---:|
| 2025-05 | `gap5/budget0` | `0` | false | `0` | `7` | `47.3538` | `93.3608` |
| 2025-06 | `gap5/budget0` | `0` | false | `0` | `10` | `158.5812` | `30.1882` |
| 2025-07 | `gap5/budget0` | `0` | false | `0` | `11` | `87.3370` | `83.7922` |
| 2025-08 | `gap5/budget0` | `0` | false | `0` | `10` | `-46.0150` | `-23.9666` |
| 2025-09 | `gap0/budget0` | `1` | true | `1` | `7` | `-45.4774` | `-32.5054` |
| 2025-10 | `gap0/budget0` | `2` | true | `2` | `7` | `14.3800` | `4.3600` |
| 2025-11 | `gap0/budget0` | `3` | true | `3` | `8` | `10.5510` | `-11.9880` |
| 2025-12 | `gap0/budget0` | `3` | true | `3` | `7` | `5.5360` | `11.5160` |

Pure context alert metrics were not selective. For `gap5/budget0`, recent short alert counts were already `7..11` in early target months, and loss-bias sums were already above `100` before 2025-05. Therefore they pushed the model to always defensive and removed profitable early short exposure.

### min_train_months=8

| trigger family | target months | total PnL | worst month | max DD | short PnL |
|---|---:|---:|---:|---:|---:|
| context alert composite / always defensive | `4` | `-15.0104` | `-45.4774` | `81.8860` | `-28.6174` |

The late target window remains controlled but does not beat NoTrade.

## Interpretation

- Context/session alerts are more meaningful than month-level prediction averages, but alert presence alone is still too broad.
- The useful signal is not "short alert exists"; it is "short alert exists and this candidate has already started losing on short".
- This explains 00191 rather than improving it. It says the realized trigger was not a naked PnL heuristic; the first short loss occurs in a prior window that already had many short side-drift alerts.
- The next improvement should not be another global month-level trigger. It should act on the alert context itself.

## Decision

- Keep `--side-drift-alerts` and context-alert metrics as diagnostics.
- Do not promote context alert count / loss-bias trigger to standard policy.
- Treat `recent_short_alert_and_short_losing_months >= 1` as an explanatory equivalent of 00191, not an improvement.

Next steps:

- Apply budget0 or stricter admission only to alert contexts, instead of switching the entire month to `gap0/budget0`.
- Rebuild side drift alerts from the same p10+margin/budget candidate family if exact source alignment is needed.
- Test whether a context-specific first-loss cap can avoid 2025-08's first loss without suppressing early profitable short exposure.

## Verification

- `python3 -m py_compile scripts/experiments/short_budget_drift_trigger_selection.py tests/test_short_budget_drift_trigger_selection.py`: OK
- `python3 -m unittest tests.test_short_budget_drift_trigger_selection tests.test_short_budget_guard_selection tests.test_backtest tests.test_context_drawdown_guard_selection tests.test_online_context_state_diagnostics tests.test_online_context_feature_model tests.test_side_context_interaction_guard_apply tests.test_docs_reports`: OK, 124 tests
- `git diff --check`: OK
