# Context Entry Budget Zero

日時: 2026-06-30 09:05 JST
更新日時: 2026-06-30 09:05 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- `context_entry_budget=0` を許可した。
- `entry_budget_context` が欠損しているrowはbudget対象外にした。
- `side_context_interaction_guard_apply.py` は active context だけをbudget対象にし、inactive rowは欠損budget contextとして渡すようにした。
- これで `signal_short_raw_gap` active short contextを完全にstay-flat化する `budget0` 診断が可能になった。
- all-windowでは `gap5/budget0` が total `+508.9838`、`gap0/budget0` が worst month `-45.4774`。
- prior-only selectionでも改善し、min4 `defensive_budget` は total `+232.2466`、min8 `defensive_budget` は total `-15.0104`。
- ただし min8 はまだNoTradeを下回るため標準採用は保留する。次の候補は固定 `gap0/budget0` mandateと、これを発火させるprior side-drift検知。

## Artifacts

- Budget-zero sweep: `data/reports/backtests/20260630_000340_short_raw_gap_entry_budget_zero_p10_margin10/`
- Prior-only selection min4: `data/reports/backtests/short_budget_zero_selection_min4/`
- Prior-only selection min8: `data/reports/backtests/short_budget_zero_selection_min8/`

Input source:

- `data/reports/backtests/20260629_140836_side_drift_guard_admission_margin_isolated_2025_01_12_coststress_260/coststress_side_guard_p10_replm10`

## Implementation

Before this change, finite `context_entry_budget` had to be positive. That made `budget=1` possible, but not a complete block.

The new behavior is:

- finite budget must be a non-negative integer,
- `context_entry_budget=0` blocks every budgeted context entry,
- missing `entry_budget_context` means the row is not budgeted,
- the wrapper passes budget context only for `active_mask == true`.

This distinction matters because inactive rows use unique drawdown contexts, but a zero budget would still block them if they were budgeted. Missing budget context avoids that and keeps the control scoped to active short drift contexts.

## All-Window Budget-Zero Sweep

Drawdown guard was disabled with `threshold=inf`; this isolates entry budget.

| short gap | budget | trades | total PnL | worst month | max DD | short PnL | long PnL | active trades | active PnL |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `5` | `0` | `738` | `508.9838` | `-215.1172` | `215.1172` | `164.7278` | `344.2560` | `0` | `0.0000` |
| `0` | `0` | `558` | `418.2596` | `-45.4774` | `126.7826` | `74.0036` | `344.2560` | `0` | `0.0000` |
| `5` | `1` | `783` | `369.3640` | `-202.8332` | `202.8332` | `25.1080` | `344.2560` | `82` | `-79.2034` |
| `5` | `2` | `819` | `332.9380` | `-183.2732` | `195.7228` | `-11.3180` | `344.2560` | `155` | `-147.3666` |
| `0` | `1` | `628` | `281.8854` | `-118.5098` | `128.6044` | `-62.3706` | `344.2560` | `85` | `-90.5052` |

Interpretation:

- `gap5/budget0` is the return top, but still has a large 2025-09 loss.
- `gap0/budget0` is the defensive top: it trades much less and caps the worst month to `-45.4774`.
- Active trade PnL is zero by design because active contexts are not entered.

Monthly `gap0/budget0` late-regime check:

| month | trades | total PnL | short PnL | long PnL | max DD |
|---|---:|---:|---:|---:|---:|
| 2025-08 | `74` | `-32.0524` | `-10.0040` | `-22.0484` | `104.5876` |
| 2025-09 | `44` | `-45.4774` | `-32.5054` | `-12.9720` | `81.8860` |
| 2025-10 | `5` | `14.3800` | `4.3600` | `10.0200` | `0.0000` |
| 2025-11 | `6` | `10.5510` | `-11.9880` | `22.5390` | `12.9456` |
| 2025-12 | `6` | `5.5360` | `11.5160` | `-5.9800` | `24.3240` |

## Prior-Only Selection

### min_train_months=4

| selector | target months | trades | total PnL | worst month | max DD | short PnL | active trades | selected pattern |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| recent_active_stability | `8` | `356` | `240.1686` | `-45.4774` | `129.7364` | `162.6792` | `25` | `gap0/budget0`, `gap5/budget2` |
| defensive_budget | `8` | `374` | `232.2466` | `-46.0150` | `129.7364` | `154.7572` | `0` | `gap0/budget0`, `gap5/budget0` |
| active_stability | `8` | `416` | `-30.4328` | `-215.1172` | `215.1172` | `-107.9222` | `0` | `gap5/budget0` |
| defensive_score | `8` | `464` | `-86.2344` | `-195.7808` | `204.1828` | `-163.7238` | `94` | includes `gap5/budget0..3` |

Compared with `00189`, `defensive_budget` moved from total `-4.8828` to `+232.2466`.

### min_train_months=8

| selector | target months | trades | total PnL | worst month | max DD | short PnL | active trades | selected pattern |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| defensive_budget | `4` | `61` | `-15.0104` | `-45.4774` | `81.8860` | `-28.6174` | `0` | `gap0/budget0` |
| recent_active_stability | `4` | `61` | `-15.0104` | `-45.4774` | `81.8860` | `-28.6174` | `0` | `gap0/budget0` |
| active_stability | `4` | `103` | `-277.6898` | `-215.1172` | `215.1172` | `-291.2968` | `0` | `gap5/budget0` |
| defensive_score | `4` | `120` | `-310.4882` | `-195.7808` | `204.1828` | `-324.0952` | `32` | includes `gap5/budget0/2/3` |

Compared with `00189`, min8 `defensive_budget` moved from total `-226.5946` to `-15.0104`, and worst month improved from `-118.5098` to `-45.4774`.

## Decision

- Keep `context_entry_budget=0` support.
- Treat `gap0/budget0` as the current defensive candidate for this family.
- Do not promote it to standard policy yet because min8 still does not beat NoTrade.
- Do not select `gap5/budget0` by return alone; it has high all-window total but still leaves a large 2025-09 tail.

Next steps:

- Build a prior-only drift detector that can choose budget `0` only when short-side prior deterioration is visible.
- Test fixed `gap0/budget0` and `gap0/budget1` on additional unseen months when predictions are available.
- Combine budget0 with a separate long-side/low-trade-count admission rule, because late-year total is now dominated by very few residual trades.

## Verification

- `python3 -m py_compile src/trade_data/backtest.py scripts/experiments/side_context_interaction_guard_apply.py tests/test_backtest.py tests/test_side_context_interaction_guard_apply.py`: OK
- `python3 -m unittest tests.test_short_budget_guard_selection tests.test_backtest tests.test_context_drawdown_guard_selection tests.test_online_context_state_diagnostics tests.test_online_context_feature_model tests.test_side_context_interaction_guard_apply tests.test_docs_reports`: OK, 119 tests
- `git diff --check`: OK
