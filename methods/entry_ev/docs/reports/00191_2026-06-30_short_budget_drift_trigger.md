# Short Budget Drift Trigger

日時: 2026-06-30 09:14 JST
更新日時: 2026-06-30 09:14 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- `scripts/experiments/short_budget_drift_trigger_selection.py` を追加した。
- 目的は、`gap0/budget0` を常時固定するのではなく、対象月より前のrecent deteriorationだけで defensive budget0 へ切り替えられるか確認すること。
- 代表ルールは「通常は `gap5/budget0`、直近3ヶ月の `gap5/budget0` short losing month count が1以上なら `gap0/budget0`」。
- min4ではこの低容量triggerが total `+232.2466`, worst `-46.0150`。`00190` の defensive_budget と同じ水準で、2025-05..08だけ `gap5/budget0`、2025-09..12は `gap0/budget0` を選んだ。
- min8では、2025-09時点ですでに直近prior deteriorationが見えているため、ほぼ常時 `gap0/budget0` になり total `-15.0104`。
- wide primary候補に `gap10/budget0` などを入れても `gap5/budget0 -> gap0/budget0` を上回らなかった。
- 標準採用はまだしない。これは性能改善というより、budget0発火をtarget-month-independentに説明する診断。

## Artifacts

- Trigger selector script: `scripts/experiments/short_budget_drift_trigger_selection.py`
- Narrow min4: `data/reports/backtests/short_budget_drift_trigger_selection_min4/`
- Narrow min8: `data/reports/backtests/short_budget_drift_trigger_selection_min8/`
- Wide min4: `data/reports/backtests/short_budget_drift_trigger_selection_min4_wide/`
- Wide min8: `data/reports/backtests/short_budget_drift_trigger_selection_min8_wide/`

Input sweep:

- `data/reports/backtests/20260630_000340_short_raw_gap_entry_budget_zero_p10_margin10/summary_by_run.csv`

## Method

The selector compares a primary candidate with a defensive candidate:

```text
primary:   short_gap_threshold=5, context_entry_budget=0
defensive: short_gap_threshold=0, context_entry_budget=0
```

For each target month:

1. use only months before the target month,
2. compute recent metrics for the primary candidate,
3. if a trigger condition is met, select defensive,
4. otherwise select primary,
5. score on the target month.

Tested trigger metrics:

- `recent_short_pnl`
- `recent_total_pnl`
- `recent_worst_month_pnl`
- `recent_short_worst_month_pnl`
- `recent_short_losing_months`
- `recent_total_losing_months`

This is still a diagnostic grid. The important question is not the best rule name, but whether a small prior-only rule can switch to budget0 before the late short regime loss.

## min_train_months=4

Top equivalent rules:

| primary | trigger | threshold | triggered months | total PnL | worst month | max DD | short PnL | selected pattern |
|---|---|---:|---:|---:|---:|---:|---:|---|
| `gap5/budget0` | `recent_short_losing_months >=` | `1` | `4` | `232.2466` | `-46.0150` | `129.7364` | `154.7572` | `gap5/budget0`, then `gap0/budget0` |
| `gap5/budget0` | `recent_short_pnl <` | `100` | `4` | `232.2466` | `-46.0150` | `129.7364` | `154.7572` | same |
| `gap5/budget0` | `recent_short_worst_month_pnl <` | `0` | `4` | `232.2466` | `-46.0150` | `129.7364` | `154.7572` | same |
| `gap5/budget1` | `recent_short_losing_months >=` | `1` | `4` | `206.7014` | `-63.8486` | `133.5398` | `129.2120` | `gap5/budget1`, then `gap0/budget0` |
| `gap10/budget0` | `recent_short_worst_month_pnl <` | `-50` | `4` | `223.1380` | `-79.0794` | `145.2258` | `145.6486` | `gap10/budget0`, then `gap0/budget0` |

Top rule month detail:

| target month | selected | trigger value | triggered | target PnL | short PnL | long PnL |
|---|---|---:|---|---:|---:|---:|
| 2025-05 | `gap5/budget0` | `0` | false | `47.3538` | `93.3608` | `-46.0070` |
| 2025-06 | `gap5/budget0` | `0` | false | `158.5812` | `30.1882` | `128.3930` |
| 2025-07 | `gap5/budget0` | `0` | false | `87.3370` | `83.7922` | `3.5448` |
| 2025-08 | `gap5/budget0` | `0` | false | `-46.0150` | `-23.9666` | `-22.0484` |
| 2025-09 | `gap0/budget0` | `1` | true | `-45.4774` | `-32.5054` | `-12.9720` |
| 2025-10 | `gap0/budget0` | `2` | true | `14.3800` | `4.3600` | `10.0200` |
| 2025-11 | `gap0/budget0` | `3` | true | `10.5510` | `-11.9880` | `22.5390` |
| 2025-12 | `gap0/budget0` | `3` | true | `5.5360` | `11.5160` | `-5.9800` |

Interpretation:

- The first target loss in 2025-08 is not avoided because there is no prior deterioration yet.
- After 2025-08, the trigger switches to defensive budget0 before 2025-09.
- This is materially better than selecting by active/short PnL maximization, and consistent with the risk-control mandate in `00190`.

## min_train_months=8

Top rows all collapse to `gap0/budget0`:

| selector family | target months | total PnL | worst month | max DD | short PnL |
|---|---:|---:|---:|---:|---:|
| always defensive / triggered defensive | `4` | `-15.0104` | `-45.4774` | `81.8860` | `-28.6174` |

At 2025-09, recent short PnL for `gap5/budget0` is already only `20.5130`, and the tested deterioration triggers select `gap0/budget0`. This matches `00190`: min8 tail is controlled, but total still does not beat NoTrade.

## Decision

- Keep `short_budget_drift_trigger_selection.py`.
- Use this as a diagnostic bridge between `gap5/budget0` return seeking and `gap0/budget0` defensive stay-flat.
- Do not promote to standard policy because min8 remains `-15.0104`.
- Do not broaden the primary candidate set based on this run; `gap10/budget0` did not improve the surface.

Next steps:

- Add prediction-share / label-share side-drift features to the trigger, not only realized PnL.
- Test on additional unseen months once comparable predictions are available.
- Investigate residual late-year losses under `gap0/budget0`; after short active context is suppressed, the remaining issue is very low trade count and residual long/short admission.

## Verification

- `python3 -m py_compile scripts/experiments/short_budget_drift_trigger_selection.py tests/test_short_budget_drift_trigger_selection.py`: OK
- `python3 -m unittest tests.test_short_budget_drift_trigger_selection tests.test_short_budget_guard_selection tests.test_backtest tests.test_context_drawdown_guard_selection tests.test_online_context_state_diagnostics tests.test_online_context_feature_model tests.test_side_context_interaction_guard_apply tests.test_docs_reports`: OK, 122 tests
- `git diff --check`: OK
