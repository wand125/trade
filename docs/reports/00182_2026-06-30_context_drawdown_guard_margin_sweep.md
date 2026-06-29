# Context Drawdown Guard Margin Sweep

日時: 2026-06-30 07:05 JST
更新日時: 2026-06-30 07:06 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- online context drawdown guard に `context_drawdown_guard_min_entry_margin` を追加した。
- 既定値 `inf` は従来通り、drawdown breach後の同一side/context entryをhard blockする。
- 有限値を指定した場合は、breach済みcontextでも `selected_score - normal_entry_threshold >= min_entry_margin` のentryだけ許可する。
- `context_drawdown_guard_apply.py` は threshold と min-entry-margin の2次元gridを再適用できるようにした。
- `context_drawdown_guard_selection.py` は `--candidate-columns` を追加し、threshold + margin のような複数列候補をprior-onlyで選べるようにした。

## Artifacts

- Margin sweep: `data/reports/backtests/20260629_150417_context_drawdown_guard_side_month_margin_sweep/`
- Prior-only selection min4: `data/reports/backtests/context_drawdown_guard_side_month_margin_selection_min4/`
- Prior-only selection min8: `data/reports/backtests/context_drawdown_guard_side_month_margin_selection_min8/`

Input is the same `p10 + margin10` monthly run set used by `00180` / `00181`, with `context_columns=dataset_month`, profit `1.0`, loss `1.20`, and coststress spread/slippage/delay.

## All-Window Sweep

This is not a promotion criterion because it sees all 2025 months. It is a shape check.

| threshold | min entry margin | trades | total PnL | worst month | max monthly DD | short PnL | long PnL |
|---:|---:|---:|---:|---:|---:|---:|---:|
| `60` | `20` | `842` | `142.9750` | `-153.6646` | `153.6646` | `-146.5528` | `289.5278` |
| `60` | `inf` | `841` | `135.6350` | `-153.6646` | `153.6646` | `-153.8928` | `289.5278` |
| `60` | `15` | `861` | `128.8662` | `-153.6646` | `153.6646` | `-160.6616` | `289.5278` |
| `40` | `15` | `721` | `112.5786` | `-151.4654` | `151.4654` | `-59.6802` | `172.2588` |
| `40` | `20` | `693` | `107.9040` | `-138.4960` | `138.4960` | `-64.3548` | `172.2588` |
| `40` | `inf` | `692` | `100.5640` | `-138.4960` | `138.4960` | `-71.6948` | `172.2588` |

Interpretation:

- `threshold=60, margin=20` adds one extra high-margin trade over hard block and improves total by `+7.3400`.
- Low margins (`0/5/10`) often re-admit bad short exposure and collapse toward the no-guard path.
- The useful region, if any, is high margin (`15/20`) after breach, not a soft low-margin relaxation.

## Prior-Only Selection

`min_train_months=4`, target 2025-05..12:

| selection | target months | trades | total PnL | worst month | max monthly DD | selected candidates |
|---|---:|---:|---:|---:|---:|---|
| `worst` | `8` | `450` | `69.9374` | `-116.4516` | `129.1668` | `20/0`, `20/20` |
| `total` | `8` | `551` | `-250.1610` | `-289.0056` | `289.0056` | `20/0`, `60/15` |

`min_train_months=8`, target 2025-09..12:

| selection | target months | trades | total PnL | worst month | max monthly DD | selected candidates |
|---|---:|---:|---:|---:|---:|---|
| `worst` | `4` | `56` | `-199.4438` | `-116.4516` | `116.4516` | `20/20` |
| `total` | `4` | `157` | `-519.5422` | `-289.0056` | `289.0056` | `20/0`, `60/15` |

For comparison, threshold-only `worst` in `00181` was:

- min4: total `63.3054`, worst `-116.4516`, trades `448`
- min8: total `-206.0758`, worst `-116.4516`, trades `54`

So margin-aware candidates improve total slightly, but not enough to change the central conclusion.

## Decision

- Keep `context_drawdown_guard_min_entry_margin` infrastructure.
- Do not promote all-window `60/20`; it is still selected with hindsight.
- The only defensible prior-only family remains `worst` objective, now usually `20/20` after tail evidence appears.
- The result supports a risk mandate, not a profit-maximizing policy:
  - before tail evidence: loose/no effective drawdown guard can look best;
  - after tail evidence: `threshold=20`, high re-entry margin `20` is the stable defensive choice.
- Next direction: evaluate whether a pre-registered `worst` mandate can be applied to additional months/data, or replace hard month-level side drawdown with a smaller live state feature for model learning.

## Verification

- `python3 -m py_compile src/trade_data/backtest.py scripts/experiments/context_drawdown_guard_apply.py scripts/experiments/context_drawdown_guard_selection.py`: OK
- `python3 -m unittest tests.test_backtest tests.test_context_drawdown_guard_selection`: OK, 96 tests
- `python3 -m unittest tests.test_backtest tests.test_context_drawdown_guard_selection tests.test_docs_reports`: OK, 99 tests
