# Short Budget Selection

日時: 2026-06-30 08:53 JST
更新日時: 2026-06-30 08:53 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- `scripts/experiments/short_budget_guard_selection.py` を追加した。
- 目的は `00188` の entry budget候補を、total/worst集計だけでなく prior short PnL / active short PnL / losing month count で選ぶこと。
- 結果として、active/short PnLを直接最大化するselectorは悪化した。
- 最も良かったのは `defensive_budget`: まず `context_entry_budget` を小さくし、その範囲で prior worst month を最大化するmandate。
- budget-only min4では `defensive_budget` が total `-4.8828`, worst `-118.5098` まで改善した。`00188` の汎用worst selector `-15.9692` より少し良い。
- min8では `defensive_budget` でも total `-226.5946`。2025-09..12のlate short regimeはまだ防ぎ切れない。
- 標準採用はしないが、次の候補は `defensive_budget` と固定 `gap0/budget1` mandate。

## Artifacts

- Budget-only short-focused min4: `data/reports/backtests/short_budget_guard_short_focus_selection_min4_v2/`
- Budget-only short-focused min8: `data/reports/backtests/short_budget_guard_short_focus_selection_min8_v2/`
- Budget + drawdown short-focused min4: `data/reports/backtests/short_budget_guard_short_focus_drawdown_selection_min4/`
- Budget + drawdown short-focused min8: `data/reports/backtests/short_budget_guard_short_focus_drawdown_selection_min8/`

Input sweeps:

- Budget-only: `data/reports/backtests/20260629_233936_short_raw_gap_entry_budget_p10_margin10/summary_by_run.csv`
- Budget + drawdown: `data/reports/backtests/20260629_234124_short_raw_gap_entry_budget_drawdown_p10_margin10/summary_by_run.csv`

## Selection Objectives

The new selector reads `summary_by_run.csv` and groups by candidate columns such as:

```text
short_gap_threshold,
context_entry_budget
```

It computes prior-only metrics:

- validation total PnL
- validation worst month PnL
- validation max monthly drawdown
- validation short PnL / short worst month / short losing-month count
- validation active PnL / active worst month / active losing-month count
- recent active PnL / recent active losing-month count

Tested objectives:

| objective | intent |
|---|---|
| `active_total` | maximize prior active short PnL |
| `short_total` | maximize prior total short PnL |
| `active_stability` | minimize active losing months, then active worst month |
| `short_stability` | minimize short losing months, then short worst month |
| `recent_active_stability` | same as active stability but recent-window-first |
| `defensive_score` | weighted total/short/active/worst/drawdown/loss-count score |
| `defensive_budget` | prefer the smallest entry budget, then best prior worst month |

## Budget-Only Results

### min_train_months=4

| selector | target months | trades | total PnL | worst month | max DD | short PnL | active PnL | selected pattern |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| defensive_budget | `8` | `418` | `-4.8828` | `-118.5098` | `133.5398` | `-82.3722` | `-164.0226` | `gap0/budget1`, `gap5/budget1` |
| active_stability | `8` | `466` | `-121.3414` | `-140.4244` | `151.1784` | `-198.8308` | `-256.2766` | `gap0/budget2`, `gap5/budget2`, `gap5/budget3` |
| defensive_score | `8` | `481` | `-231.5018` | `-195.7808` | `204.1828` | `-308.9912` | `-305.7028` | `gap5/budget1/2/3` |
| short_stability | `8` | `465` | `-250.4942` | `-202.8332` | `202.8332` | `-327.9836` | `-251.3294` | `gap5/budget1/2` |
| short_total | `8` | `490` | `-285.1334` | `-195.7808` | `204.1828` | `-362.6228` | `-437.4400` | `gap5/budget1/3` |
| active_total | `8` | `481` | `-353.1440` | `-289.0056` | `289.0056` | `-430.6334` | `-366.4110` | includes `gap5/budgetinf` |
| recent_active_stability | `8` | `518` | `-380.9460` | `-276.0890` | `276.0890` | `-458.4354` | `-333.9920` | includes `gap10` and `budgetinf` |

Interpretation:

- Directly maximizing active or short PnL overfits the early positive short months and reopens late short exposure.
- `defensive_budget` is not a clever score; it is a mandate to use a small repeated-short budget first.
- That mandate is currently more robust than trying to rank short edge.

### min_train_months=8

| selector | target months | trades | total PnL | worst month | max DD | short PnL | active PnL | selected pattern |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| defensive_budget | `4` | `90` | `-226.5946` | `-118.5098` | `128.6044` | `-240.2016` | `-178.3242` | `gap0/budget1` |
| active_stability | `4` | `126` | `-401.5110` | `-140.4244` | `151.1784` | `-415.1180` | `-291.2150` | `gap0/budget2`, `gap5/budget2` |
| defensive_score | `4` | `137` | `-455.7556` | `-195.7808` | `204.1828` | `-469.3626` | `-292.3320` | `gap5/budget1/2/3` |
| short_stability | `4` | `137` | `-472.2060` | `-202.8332` | `202.8332` | `-485.8130` | `-265.6310` | `gap5/budget1/2` |
| short_total | `4` | `146` | `-509.3872` | `-195.7808` | `204.1828` | `-522.9942` | `-424.0692` | `gap5/budget3` |

Interpretation:

- With 8 prior months, the defensive budget selector collapses to `gap0/budget1`.
- This improves over generic worst selection min8 (`-240.2230`) only slightly.
- Late-year losses remain because even one repeated active short per month/regime can still be large in 2025-09.

## Budget + Drawdown Selection

Adding drawdown threshold to the candidate columns:

```text
short_gap_threshold,
context_entry_budget,
context_drawdown_guard_loss_threshold
```

did not change the best target aggregate:

| selector | min train | target months | total PnL | worst month | selected pattern |
|---|---:|---:|---:|---:|---|
| defensive_budget | `4` | `8` | `-4.8828` | `-118.5098` | `gap0/budget1/th20`, `gap5/budget1/th20` |
| defensive_budget | `8` | `4` | `-226.5946` | `-118.5098` | `gap0/budget1/th20` |

Strict budget already limits repeated entries before drawdown can add much value.

## Decision

- Keep `short_budget_guard_selection.py`.
- Treat `defensive_budget` as the current best selection rule for this family.
- Do not promote to standard policy because target-period total still does not beat NoTrade.
- Do not use active/short PnL maximization as a selector; it selected candidates that looked good in early prior months but failed in the late short regime.

Next steps:

- Test fixed defensive mandates (`gap0/budget1`, possibly `gap0/budget2`) on additional unseen months/data.
- Add a per-trade loss cap or fast stop logic for the first short in a bad month/regime, because budget=1 still allows a large first loss.
- Add regime drift detection that can force budget `0` when prior side label/prediction share has inverted.

## Verification

- `python3 -m py_compile scripts/experiments/short_budget_guard_selection.py tests/test_short_budget_guard_selection.py`: OK
- `python3 -m unittest tests.test_short_budget_guard_selection tests.test_backtest tests.test_context_drawdown_guard_selection tests.test_online_context_state_diagnostics tests.test_online_context_feature_model tests.test_side_context_interaction_guard_apply tests.test_docs_reports`: OK, 115 tests
- `git diff --check`: OK
