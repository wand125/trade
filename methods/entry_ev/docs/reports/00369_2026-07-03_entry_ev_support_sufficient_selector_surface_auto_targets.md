# Entry EV Support-Sufficient Selector Surface Auto Targets

日時: 2026-07-03 16:42 JST
更新日時: 2026-07-03 16:42 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00368の次アクションとして、support-sufficient negative monthを手動指定ではなくcurrent trades / repair targetsからauto抽出できるようにした。
- `entry_ev_support_sufficient_selector_surface_diagnostics.py` に `--targets auto_support_sufficient_negative` を追加し、target inventoryを `support_sufficient_selector_surface_target_inventory.csv` に出力する。
- 現00314/00318 branchのnegative monthは4件あるが、support-sufficient negative monthは `refit2025_validation 2025-03` の1件だけだった。
- 他のnegative monthsは `fresh2024 2024-03`, `fresh2024 2024-11`, `hybrid2025_0912 2025-11` で、いずれも `extra_long_needed` または `extra_short_needed` が1のsupport-limited negative month。
- auto runのselector surface結果は00368と同じ。これは00368が過剰に狭いtarget指定だったというより、現branch上のsupport-sufficient target母集団自体が1件しかないことを意味する。
- 判断: auto target inventory / auto runはaccepted infrastructure。selector surfaceを複数targetで評価するには、support-limited laneとは別に、他branch・他variant・より広いcandidate stageでsupport-sufficient negative monthを増やす必要がある。標準policyはNoTrade。

## Artifacts

Updated script:

- `scripts/experiments/entry_ev_support_sufficient_selector_surface_diagnostics.py`

Updated tests:

- `tests/test_entry_ev_support_sufficient_selector_surface_diagnostics.py`

Run:

- `data/reports/backtests/20260703_074225_20260703_entry_ev_00369_support_sufficient_selector_surface_auto_targets/`

New output:

- `support_sufficient_selector_surface_target_inventory.csv`

Existing outputs:

- `support_sufficient_selector_surface_choices.csv`
- `support_sufficient_selector_surface_summary.csv`
- `support_sufficient_selector_surface_targets.csv`
- `support_sufficient_selector_surface_risk_trades.csv`
- `support_sufficient_selector_surface_risk_hits.csv`
- `support_sufficient_selector_surface_candidates.csv`
- `support_sufficient_selector_surface_meta.json`

## Method

Auto target definition:

```text
month_pnl < 0
repair target exists
extra_long_needed == 0
extra_short_needed == 0
```

Support-limited negative definition:

```text
month_pnl < 0
repair target exists
extra_long_needed > 0 OR extra_short_needed > 0
```

Target side is inferred from losing trades by the larger absolute loss sum. This is for reporting and compatibility with existing target strings; selector behavior does not use target-side actual PnL as a feature.

## Target Inventory

Negative months in the current branch:

| role | family | month | month PnL | trades | losses | extra long | extra short | class |
|---|---|---|---:|---:|---:|---:|---:|---|
| `hybrid2025_0912_external` | `hybrid2025_0912` | `2025-11` | `-0.7200` | `1` | `1` | `0` | `1` | support-limited |
| `fresh2024_validation` | `fresh2024` | `2024-11` | `-0.6120` | `1` | `1` | `1` | `0` | support-limited |
| `refit2025_validation` | `refit2025` | `2025-03` | `-0.4730` | `9` | `4` | `0` | `0` | support-sufficient |
| `fresh2024_validation` | `fresh2024` | `2024-03` | `-0.3636` | `1` | `1` | `1` | `0` | support-limited |

Auto-selected target:

```text
refit2025_validation:2025-03:short
```

This confirms that the 00368 target was the only support-sufficient negative target available in this branch.

## Surface Result

Since the auto target set has one target, the best rows are the same as 00368.

Stricter support result with min prior month `2`, candidate prior count `>=50`, prior actual mean `>=0`:

| risk selector | score | selected trade | candidate | candidate actual | candidate prior | month PnL |
|---|---|---|---|---:|---:|---:|
| `feature:side_gap_ge0p15_lossfirst_lt0p30` | `bias_corrected` | `2025-03-21 14:00 short -2.3400` | `2025-03-27 23:58 long` | `+20.6300` | count `254`, months `2`, prior actual `+23.0083` | `+22.4970` |
| `feature:side_gap_ge0p15_lossfirst_lt0p30` | `prior_actual_mean` | `2025-03-21 14:00 short -2.3400` | `2025-03-11 06:39 long` | `+17.9070` | count `157`, months `2`, prior actual `+29.7708` | `+19.7740` |
| `feature:ev_ge5_lossfirst_lt0p30` | `bias_corrected` | `2025-03-21 14:29 short -0.3324` | `2025-03-27 23:58 long` | `+20.6300` | count `254`, months `2`, prior actual `+23.0083` | `+20.4894` |

Failure mode remains:

- `combined:any_lossrisk`, `score:loss_first_prob`, and `prior:direction,combined_regime:prior_count_ge5_lossrate_ge0p50` select the winner `2025-03-31 03:40 short +1.3800`.
- A strong replacement can still make the resulting month PnL positive, but that is not evidence that the risk selector is safe.

## Decision

Accepted:

- `auto_support_sufficient_negative` target mode
- target inventory output
- auto target test coverage

Not accepted as policy:

- standardizing the selector surface from this branch alone
- treating the current support-sufficient lane as multi-target evidence
- merging support-limited negative months into this lane without a separate side/trade support objective

Standard policy remains NoTrade.

## Next

1. Add a sibling auto mode for support-limited negative months, but keep it separate from support-sufficient replacement.
2. Search other variants/branches for additional support-sufficient negative months before training a loss-risk selector.
3. If target count remains 1, treat support-sufficient selector work as infrastructure and move model improvement toward broader loss-risk / horizon-abstention labels.

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_support_sufficient_selector_surface_diagnostics.py tests/test_entry_ev_support_sufficient_selector_surface_diagnostics.py`: OK
- `uv run python -m unittest tests.test_entry_ev_support_sufficient_selector_surface_diagnostics`: OK
- 00369 auto support-sufficient selector surface run: OK
