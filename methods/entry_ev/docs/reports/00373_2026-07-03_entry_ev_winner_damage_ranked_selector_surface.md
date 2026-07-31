# Entry EV Winner-Damage Ranked Selector Surface

日時: 2026-07-03 17:27 JST
更新日時: 2026-07-03 17:27 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00372のpost-process制約を `entry_ev_support_sufficient_selector_surface_diagnostics.py` 本体へ入れ、selector surface summaryのrankingがwinner-damage制約を直接見るようにした。
- 追加した制約は `loss_selection_precision >= 0.5`、winner trade selected 0、baseline-positive degradation 0、current-negative delta `>=0`。
- 00371と同じcanonical target setで再実行したところ、16 rows中 `passes_winner_damage_constraints=True` は0件のまま。
- 最小違反は `oracle:worst_loss` 系で、loss precision 1.0 / winner selected 0 / current-negative delta positiveだが、baseline-positive degradationが1-3件残る。
- non-oracleでは `feature:ev_ge5_lossfirst_lt0p30` がloss precision `0.5556` を満たすがwinner selected 4件で落ちる。`combined:any_lossrisk` はwinner selected 7件、loss precision `0.3000`。`side_gap_ge0p15_lossfirst_lt0p30` はwinner selected 5件、loss precision `0.2857`。
- 判断: winner-damage constrained rankingはaccepted infrastructure。結論は00372と同じで、現risk selector / replacement selectorは標準policy化しない。標準policyはNoTrade。

## Artifacts

Updated script:

- `scripts/experiments/entry_ev_support_sufficient_selector_surface_diagnostics.py`

Updated tests:

- `tests/test_entry_ev_support_sufficient_selector_surface_diagnostics.py`

Run:

- `data/reports/backtests/20260703_082714_20260703_entry_ev_00373_winner_damage_ranked_selector_surface/`

Outputs:

- `support_sufficient_selector_surface_choices.csv`
- `support_sufficient_selector_surface_summary.csv`
- `support_sufficient_selector_surface_targets.csv`
- `support_sufficient_selector_surface_target_inventory.csv`
- `support_sufficient_selector_surface_risk_trades.csv`
- `support_sufficient_selector_surface_risk_hits.csv`
- `support_sufficient_selector_surface_candidates.csv`
- `support_sufficient_selector_surface_meta.json`

## Method Change

`summarize_surface()` に以下の列を追加した。

- `loss_selection_precision`
- `baseline_positive_degraded_count`
- `baseline_positive_flipped_negative_count`
- `current_negative_target_count`
- `current_negative_mean_delta`
- `current_negative_min_delta`
- `current_negative_positive_after_count`
- `current_nonnegative_target_count`
- `current_nonnegative_mean_delta`
- `current_nonnegative_min_delta`
- `passes_loss_selection_precision`
- `passes_winner_trade_selected`
- `passes_baseline_positive_degradation`
- `passes_current_negative_delta`
- `winner_damage_constraint_violation_count`
- `passes_winner_damage_constraints`

The summary is now sorted first by:

```text
passes_winner_damage_constraints desc
winner_damage_constraint_violation_count asc
passes_winner_trade_selected desc
passes_baseline_positive_degradation desc
passes_current_negative_delta desc
loss_selection_precision desc
```

Then it falls back to mean/min PnL and mean delta.

## Run Configuration

```text
--targets-inventory data/reports/backtests/20260703_075023_20260703_entry_ev_00370_support_negative_month_inventory/support_negative_month_target_summary.csv
--inventory-min-support-sufficient-configs 50
--inventory-min-metric-parents 5
--inventory-target-side both
--risk-selectors feature:side_gap_ge0p15_lossfirst_lt0p30;feature:ev_ge5_lossfirst_lt0p30;combined:any_lossrisk;oracle:worst_loss
--score-modes prior_actual_mean,bias_corrected
--calibration-min-context-counts 50
--candidate-min-prior-counts 50,100
--candidate-min-prior-month-counts 2
--candidate-min-prior-actual-means 0
--min-loss-selection-precision 0.5
--max-winner-trade-selected 0
--max-baseline-positive-degraded 0
--min-current-negative-delta 0
```

## Result

Top ranked rows after adding winner-damage constraints:

| risk selector | score | prior count | loss precision | selected losses | selected winners | baseline-positive degraded | current-negative min delta | mean PnL | mean delta | violations | pass |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `oracle:worst_loss` | `bias_corrected` | `100` | `1.0000` | 10 | 0 | 1 | `+10.0070` | `+40.4309` | `+19.4980` | 1 | no |
| `oracle:worst_loss` | `prior_actual_mean` | `100` | `1.0000` | 10 | 0 | 3 | `+20.2470` | `+20.2550` | `-0.6779` | 1 | no |
| `oracle:worst_loss` | `bias_corrected` | `50` | `1.0000` | 10 | 0 | 2 | `+10.0070` | `+12.7607` | `-8.1723` | 1 | no |
| `oracle:worst_loss` | `prior_actual_mean` | `50` | `1.0000` | 10 | 0 | 3 | `+20.2470` | `+7.1114` | `-13.8215` | 1 | no |
| `feature:ev_ge5_lossfirst_lt0p30` | `bias_corrected` | `100` | `0.5556` | 5 | 4 | 2 | `+7.9994` | `+29.1371` | `+8.2042` | 2 | no |
| `combined:any_lossrisk` | `bias_corrected` | `100` | `0.3000` | 3 | 7 | 1 | `+6.2870` | `+33.2963` | `+12.3633` | 3 | no |
| `feature:side_gap_ge0p15_lossfirst_lt0p30` | `bias_corrected` | `100` | `0.2857` | 2 | 5 | 1 | `+10.0070` | `+26.2583` | `+5.3253` | 3 | no |

The ranking now makes the failure mode explicit:

- If we require no winner damage, only oracle loss selection gets close.
- If we use observable non-oracle selectors, they still delete too many winners.
- Even perfect loss identification does not make the replacement selector safe, because baseline-positive months can be degraded.

## Decision

Accepted:

- winner-damage constrained columns in the canonical selector surface summary
- CLI thresholds for loss precision, winner selection, baseline-positive degradation, and current-negative delta
- ranking by constraint pass/violation count before mean PnL

Rejected as standard policy:

- choosing rows by mean PnL when winner damage constraints fail
- treating replacement compensation after deleting winners as loss-risk success
- treating oracle loss selection as sufficient when replacement can damage positive months

Standard policy remains NoTrade.

## Next

1. Diagnose replacement abstention/calibration on the baseline-positive degradation cases, especially `hgb2024_0306 2024-05`.
2. Split current-branch negative repair from cross-artifact robustness in future surface runs.
3. Keep winner-damage constraints in the surface summary before considering any selector as a policy candidate.

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_support_sufficient_selector_surface_diagnostics.py tests/test_entry_ev_support_sufficient_selector_surface_diagnostics.py`: OK
- `uv run python -m unittest tests.test_entry_ev_support_sufficient_selector_surface_diagnostics`: OK
- 00373 winner-damage ranked selector surface run: OK
