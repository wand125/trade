# Entry EV NoTrade Selector Fresh Fold

日時: 2026-06-30 13:20 JST
更新日時: 2026-06-30 13:34 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00208の反省として、NoTrade tieやnear-tieをtest結果で都合よく選ばないためのselectorを実装した。
- `scripts/experiments/entry_ev_admission_selection.py` は validation sweepだけを読み、標準selectorと診断selectorを分ける。
- 標準selectorは NoTrade first: validation totalが `0` を超える候補がなければNoTradeを返す。
- 診断selectorは near-NoTrade conservative: `±2.0` PnL以内かつ `10` trades以下の低頻度候補だけを診断候補として拾い、高いentry/short thresholdを優先する。
- Fresh foldとして `2024-03..04` をvalidation、`2024-05..12` をtestにした。標準selectorは best validation total `-1.8610` のためNoTradeを選んだ。
- 診断selectorは calibrated `entry12/short6` を選び、fixed test `2024-05..12` では `+65.4014`, worst `-37.8326`, max DD `37.8326`, trades `19`。
- 判断: 標準policyはNoTrade。`cal12/short6` は低頻度diagnostic candidateとして残すが、validation totalが負なので標準採用しない。
- 訂正: 2026-06-30 13:34 JST時点で、上記fixed testは保存済みfixed config上の `min_entry_rank=0.5` を含んでいたことを確認した。fresh validation表の `cal12/short6` は `min_entry_rank=0.0` なので、fixed test `+65.4014` は pure absolute EV threshold ではなく `cal12/short6/min_rank0.5` と読む。詳細は `docs/reports/00210_2026-06-30_entry_ev_rank_gate_support_audit.md`。

## Artifacts

- Selector script: `scripts/experiments/entry_ev_admission_selection.py`
- Tests: `tests/test_entry_ev_admission_selection.py`
- Fresh validation calibrated sweeps:
  - `data/reports/backtests/20260630_entry_evcal_fresh0304_calibrated/20260630_041554_model_sweep_2024-03/metrics.csv`
  - `data/reports/backtests/20260630_entry_evcal_fresh0304_calibrated/20260630_041634_model_sweep_2024-04/metrics.csv`
- Fresh validation raw sweeps:
  - `data/reports/backtests/20260630_entry_evcal_fresh0304_raw/20260630_041634_model_sweep_2024-03/metrics.csv`
  - `data/reports/backtests/20260630_entry_evcal_fresh0304_raw/20260630_041636_model_sweep_2024-04/metrics.csv`
- Selector output: `data/reports/backtests/20260630_041909_20260630_entry_evcal_fresh0304_selector/`
- Diagnostic fixed test: `data/reports/backtests/20260630_041944_20260630_entry_evcal_fresh0304_selected_cal12_short6_test_2024_05_12/`

## Selector Rule

Standard selector:

```text
If no validation row has validation_total > 0 after gates, select NoTrade.
Otherwise select the eligible row with highest validation_total, then worst month, then lower drawdown/trade count.
```

Diagnostic selector:

```text
If a low-frequency row is within +/-2.0 PnL of NoTrade and has <=10 validation trades,
select the most conservative row by entry_threshold and short_entry_threshold_offset.
This is diagnostic only and never promotes a standard policy by itself.
```

The diagnostic selector exists because a low-frequency candidate can be useful for stress testing, but it must not override the standard NoTrade decision.

## Fresh Validation

Validation months: `2024-03, 2024-04`.

| selector | selected | reason | best validation total |
|---|---|---|---:|
| standard NoTrade first | NoTrade | no validation row exceeded NoTrade | `-1.8610` |
| diagnostic near-NoTrade conservative | calibrated `entry12/short6` | low-frequency row near NoTrade | `-1.8610` |

Top validation rows:

| family | entry | short offset | validation total | worst | trades | max DD | short PnL |
|---|---:|---:|---:|---:|---:|---:|---:|
| calibrated | `12` | `6` | `-1.8610` | `-16.3290` | `7` | `21.4080` | `-2.5840` |
| calibrated | `10` | `6` | `-47.4616` | `-37.1650` | `19` | `51.5828` | `-48.1846` |
| raw | `12` | `6` | `-115.7246` | `-68.3872` | `98` | `134.7892` | `-96.5786` |
| calibrated | `10` | `3` | `-117.3198` | `-102.9588` | `50` | `106.5488` | `-118.0428` |
| calibrated | `12` | `3` | `-129.8448` | `-118.6710` | `29` | `118.6710` | `-130.5678` |

This is stricter than 00208. The same `cal12/short6` candidate is no longer a pure NoTrade tie; it loses slightly on fresh validation. Therefore the standard selector must choose NoTrade.

## Diagnostic Fixed Test

The diagnostic `calibrated entry12/short6` candidate was fixed to `2024-05..12`.

Correction note, 2026-06-30 13:34 JST: this fixed test used the stored fixed config with `min_entry_rank=0.5`. The fresh validation row shown above used `min_entry_rank=0.0`. Therefore this fixed test should be read as rank-gated `cal12/short6/min_rank0.5`, not as a pure absolute EV threshold.

| policy | selected by | test total | worst | max DD | trades | forced |
|---|---|---:|---:|---:|---:|---:|
| standard NoTrade | standard selector | `0.0000` | `0.0000` | `0.0000` | `0` | `0` |
| calibrated `entry12/short6/min_rank0.5` | diagnostic selector | `+65.4014` | `-37.8326` | `37.8326` | `19` | `0` |

Monthly diagnostic PnL:

| month | PnL | trades |
|---|---:|---:|
| 2024-05 | `-37.8326` | `4` |
| 2024-06 | `+29.5300` | `1` |
| 2024-07 | `0.0000` | `0` |
| 2024-08 | `+37.0940` | `3` |
| 2024-09 | `0.0000` | `0` |
| 2024-10 | `-11.4600` | `1` |
| 2024-11 | `+52.0300` | `9` |
| 2024-12 | `-3.9600` | `1` |

The diagnostic candidate still has useful shape: low trade count, no forced exits, and positive fixed-test PnL. But since the standard selector did not select it, this result is not a promotion signal.

Coverage note: `holding_max_grid --require-post-coverage` fails for `2024-05` and `2024-12` on this prediction parquet because post-exit prediction rows are absent at those month boundaries. This does not block this fixed test because the policy uses entry-time predicted holding minutes and OHLCV prices for exits; the run uses the same evaluation style as the earlier full-2024 fixed tests.

## Decision

No standard policy is promoted.

What improved:

- NoTrade tie handling is now executable, not just a prose rule.
- The standard and diagnostic paths are separated.
- Fresh validation `2024-03..04` no longer lets us claim calibrated high-threshold was selected as a trading policy.

What remains useful:

- `cal12/short6` remains the lower-risk diagnostic candidate for future folds.
- `cal10/short6` is less attractive under fresh validation because it loses `-47.4616` and has `19` validation trades.
- Raw EV admission remains refuted: raw best on fresh validation is already deeply negative.

Next:

1. Run the same selector on additional chronological folds, ideally with model re-fit rather than only reusing the 2023-fit prediction family.
2. Add a stronger admission feature that makes `cal12/short6` positive on validation before considering standard adoption.
3. Keep NoTrade as the standard result whenever validation total is non-positive.
4. Evaluate side/regime calibrated EV quantiles or ranks rather than absolute EV thresholds.

## Verification

- Fresh validation raw/calibrated sweeps: OK
- Selector artifact generation: OK
- Diagnostic fixed test `2024-05..12`: OK
- `python3 -m unittest tests.test_entry_ev_admission_selection tests.test_docs_reports`: OK
- `python3 -m py_compile scripts/experiments/entry_ev_admission_selection.py tests/test_entry_ev_admission_selection.py`: OK
- `git diff --check`: OK
