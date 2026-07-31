# Alert Context Budget Admission

日時: 2026-06-30 09:57 JST
更新日時: 2026-06-30 09:57 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- `side_context_interaction_guard_apply.py` に `prior_side_drift_alert` match modeを追加した。
- 目的は、00193で「月全体のbudget0」へ倒していた介入を、対象月より前の `side_drift_alerts.csv` に出ている `combined_regime + session_regime` のshort alert contextだけへ限定すること。
- 同時に `--active-min-entry-margins` を追加し、alert context内だけに追加entry marginを掛ける診断も試した。
- 結果は、context限定 `budget0` が baseline `-90.1378` を `+6.0170` まで改善した。ただし 00190/00191 の global `gap0/budget0` 系や drift trigger min4 `+232.2466` には届かない。
- active margin filterは、弱いalert context tradeを消す一方でreplacement tradeを増やし、total `-130..-299` へ悪化した。
- prior-only selectionでも min4 best `-316.4554`, min8 best `-542.9034` で、実運用的な選択としては壊れている。
- 結論: hookは残すが標準採用しない。alert contextだけへの単純budget/admissionではlate 2025のshort driftを抑えきれない。次はcontext-specific first-loss capや、alert contextでの現在月realized PnLを使ったfast stopを検証する。

## Artifacts

- Script: `scripts/experiments/side_context_interaction_guard_apply.py`
- Tests: `tests/test_side_context_interaction_guard_apply.py`
- Alert-context sweep: `data/reports/backtests/20260630_005421_short_alert_context_budget_margin_recent3/`
- Prior-only selection min4: `data/reports/backtests/short_alert_context_budget_margin_selection_min4/`
- Prior-only selection min8: `data/reports/backtests/short_alert_context_budget_margin_selection_min8/`

Inputs:

- Baseline runs: `data/reports/backtests/20260629_140836_side_drift_guard_admission_margin_isolated_2025_01_12_coststress_260/coststress_side_guard_p10_replm10`
- Data: `data/processed/histdata/xauusd/xauusd_m1.parquet`
- Alert files:
  - `data/reports/modeling/20260629_133501_side_drift_reference_2025_01_08_coststress_260/side_drift_alerts.csv`
  - `data/reports/modeling/20260629_133440_side_drift_fresh_2025_09_12_coststress_260/side_drift_alerts.csv`

## Implementation

Added:

- `read_side_drift_alerts_from_frame()` / `read_side_drift_alerts()`
- `match_mode=prior_side_drift_alert`
- `--side-drift-alerts`
- `--alert-recent-month-count`
- `--alert-sides`
- `--active-min-entry-margins`
- `raw_desired_position` in `interaction_signal_context.csv`

`prior_side_drift_alert` uses only rows where:

1. `side_drift_alerts.month < target_month`,
2. `is_alert=true`,
3. `side` is included in `--alert-sides`,
4. the prediction row has the same configured context key,
5. the current desired signal is the same side as the alert.

For this run, context columns were `combined_regime,session_regime`, `--alert-recent-month-count 3`, and `--alert-sides short`.

## Results

### Aggregate sweep

| active min entry margin | context entry budget | trades | total PnL | worst month | max DD | short PnL | active trades | active trade PnL |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `-inf` | `0` | `880` | `+6.0170` | `-268.9572` | `268.9572` | `-338.2390` | `0` | `0.0000` |
| `-inf` | `1` | `897` | `-102.7872` | `-285.1952` | `285.1952` | `-447.0432` | `52` | `-84.5202` |
| `-inf` | `inf` | `949` | `-90.1378` | `-289.0056` | `289.0056` | `-434.3938` | `211` | `-218.5658` |
| `10` | `0` | `1249` | `-130.2372` | `-224.2718` | `224.2718` | `-474.4932` | `0` | `0.0000` |
| `10` | `1` | `1276` | `-172.5202` | `-232.5684` | `232.5684` | `-516.7762` | `32` | `-37.6630` |
| `10` | `inf` | `1461` | `-299.3786` | `-291.8702` | `291.8702` | `-643.6346` | `242` | `-292.1102` |
| `20` | `0` | `1331` | `-130.2368` | `-209.9814` | `209.9814` | `-474.4928` | `0` | `0.0000` |
| `20` | `1` | `1333` | `-134.1176` | `-211.9454` | `211.9454` | `-478.3736` | `2` | `-3.8808` |
| `20` | `inf` | `1338` | `-132.9616` | `-211.9454` | `211.9454` | `-477.2176` | `7` | `-2.7248` |

Baseline is the `active_min_entry_margin=-inf`, `context_entry_budget=inf` row.
Context-limited budget0 improves `-90.1378 -> +6.0170`, but still leaves large 2025-09..12 losses.

### Monthly shape

With `active_min_entry_margin=-inf` and `context_entry_budget=0`:

| month | total PnL | short PnL | long PnL | max DD |
|---|---:|---:|---:|---:|
| 2025-01 | `+101.4088` | `+30.8668` | `+70.5420` | `56.3844` |
| 2025-02 | `+75.0192` | `+44.4944` | `+30.5248` | `66.8408` |
| 2025-03 | `+11.2296` | `-62.3012` | `+73.5308` | `90.5444` |
| 2025-04 | `+161.7600` | `+69.5910` | `+92.1690` | `135.5436` |
| 2025-05 | `+67.9352` | `+113.9422` | `-46.0070` | `65.8240` |
| 2025-06 | `+212.6432` | `+84.2502` | `+128.3930` | `44.7212` |
| 2025-07 | `+60.9752` | `+57.4304` | `+3.5448` | `132.2886` |
| 2025-08 | `-99.4196` | `-77.3712` | `-22.0484` | `125.7344` |
| 2025-09 | `-268.9572` | `-255.9852` | `-12.9720` | `268.9572` |
| 2025-10 | `-36.4018` | `-46.4218` | `+10.0200` | `111.2140` |
| 2025-11 | `-120.9492` | `-143.4882` | `+22.5390` | `127.7032` |
| 2025-12 | `-159.2264` | `-153.2464` | `-5.9800` | `160.8184` |

The intervention is too narrow. It removes some known alert-context shorts, but late-year replacement and non-alert short exposure still dominate.

### Prior-only selection

`context_drawdown_guard_selection.py` was run with candidate columns:

- `active_min_entry_margin`
- `context_entry_budget`

min_train_months=4:

| selection | target months | total PnL | worst month | max DD | selected candidates |
|---|---:|---:|---:|---:|---|
| `worst` | `8` | `-316.4554` | `-224.2718` | `224.2718` | `margin10/budget0`, `margin20/budget0`, `margin=-inf/budget=inf` |
| `total` | `8` | `-343.4006` | `-268.9572` | `268.9572` | `margin=-inf/budget0` |
| risk variants | `8` | `-402.2598` to `-404.3140` | `-268.9572` | `268.9572` | mixed `margin20/budget0` and `margin=-inf/budget0` |

min_train_months=8:

| selection | target months | total PnL | worst month | max DD | selected candidates |
|---|---:|---:|---:|---:|---|
| `worst` | `4` | `-542.9034` | `-224.2718` | `224.2718` | `margin10/budget0`, `margin20/budget0` |
| `total` | `4` | `-585.5346` | `-268.9572` | `268.9572` | `margin=-inf/budget0` |
| risk variants | `4` | `-585.5346` to `-587.5888` | `-268.9572` | `268.9572` | mixed `margin20/budget0` and `margin=-inf/budget0` |

The selector sees early months where context-limited suppression looks acceptable, but it has no way to infer that non-alert short exposure will dominate late 2025.

## Interpretation

- 00193の「alert contextだけに介入する」という仮説は、global month switchより過学習しにくそうだったが、今回は容量が狭すぎた。
- `context_entry_budget=0` on prior alert contexts is directionally useful, because it improves the baseline by about `+96.1548`.
- However, the remaining short loss is still large: `short_adjusted_pnl -338.2390`.
- Finite `active_min_entry_margin` is not enough. It removes weak active rows, but the one-position constraint then allows many replacement trades, and those replacements are worse.
- Prior-only selection is negative under both min4 and min8, so this cannot be promoted as a live rule.

## Decision

- Keep the infrastructure:
  - `prior_side_drift_alert` mode
  - alert file loading
  - alert side/context matching
  - active-context-only entry margin filter
- Do not promote alert-context budget/admission to standard policy.
- Treat it as a diagnostic proving that context alert explains part, but not all, of late short failure.

Next steps:

- Test context-specific first-loss cap: allow first trade in alert context, then block the same side/context after realized loss.
- Rebuild side drift alerts from the exact p10 + margin10 budget candidate family to remove source mismatch.
- Add current-month realized context PnL / active loss breach into the alert-context hook instead of relying only on prior-month alert membership.
- Compare against fixed global `gap0/budget0` and NoTrade before considering any promotion.

## Verification

- `python3 -m py_compile scripts/experiments/side_context_interaction_guard_apply.py tests/test_side_context_interaction_guard_apply.py`: OK
- `python3 -m unittest tests.test_side_context_interaction_guard_apply`: OK, 5 tests
- `python3 -m unittest tests.test_side_context_interaction_guard_apply tests.test_backtest tests.test_context_drawdown_guard_selection tests.test_docs_reports tests.test_short_budget_drift_trigger_selection`: OK, 119 tests
- `git diff --check`: OK
