# Entry EV Canonical Support-Sufficient Selector Surface

日時: 2026-07-03 17:07 JST
更新日時: 2026-07-03 17:07 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00370のinventoryを使い、`entry_ev_support_sufficient_selector_surface_diagnostics.py` に `--targets-inventory` を追加した。
- `support_negative_month_target_summary.csv` からsupport-sufficient config数 `>=50`、metric parent数 `>=5` のcanonical target setを作り、00368/00369のselector surfaceを複数targetへ広げた。
- inventory上のtargetは11件、現00314/00318 configで評価できたtargetは10件。`refit2025 2025-08` は現configのunblocked current tradesがなく、surface評価から落ちた。
- 評価対象10件の現config baselineは、9件が既にpositive monthで、negativeは `refit2025 2025-03` の1件だけ。baseline meanは `+20.9330`、minは `-0.4730`。
- non-oracle bestは `combined:any_lossrisk` + `bias_corrected` + prior count `>=100` / prior months `>=2` / prior actual mean `>=0` で、mean month PnL `+33.2963`、mean delta `+12.3633`、positive months `9/10`。ただしloss trade selectedは3件、winner selectedは7件で、winner damageが大きい。
- 00368で有望だった `feature:side_gap_ge0p15_lossfirst_lt0p30` + `bias_corrected` もmean delta `+5.3253` まで残るが、loss trade selected 2件 / winner selected 5件で、`hgb2024_0306 2024-05` を `+0.9578 -> -19.3690` へ悪化させる。
- 判断: canonical target injectionはaccepted infrastructure。複数target stressでは、現loss-risk selectorは標準policy化できない。標準policyはNoTrade。

## Artifacts

Updated script:

- `scripts/experiments/entry_ev_support_sufficient_selector_surface_diagnostics.py`

Updated tests:

- `tests/test_entry_ev_support_sufficient_selector_surface_diagnostics.py`

Run:

- `data/reports/backtests/20260703_080722_20260703_entry_ev_00371_canonical_support_sufficient_selector_surface/`

Inputs:

- `data/reports/backtests/20260703_075023_20260703_entry_ev_00370_support_negative_month_inventory/support_negative_month_target_summary.csv`
- `data/reports/backtests/20260702_111114_20260702_entry_ev_00318_thin_month_opposite_candidates_00314_w5_s2/config.json`

Outputs:

- `support_sufficient_selector_surface_choices.csv`
- `support_sufficient_selector_surface_summary.csv`
- `support_sufficient_selector_surface_targets.csv`
- `support_sufficient_selector_surface_target_inventory.csv`
- `support_sufficient_selector_surface_risk_trades.csv`
- `support_sufficient_selector_surface_risk_hits.csv`
- `support_sufficient_selector_surface_candidates.csv`
- `support_sufficient_selector_surface_meta.json`

## Method

Target source:

```text
--targets-inventory support_negative_month_target_summary.csv
--inventory-min-support-sufficient-configs 50
--inventory-min-metric-parents 5
--inventory-target-side both
```

Focused surface:

```text
risk selectors:
  feature:side_gap_ge0p15_lossfirst_lt0p30
  feature:ev_ge5_lossfirst_lt0p30
  combined:any_lossrisk
  oracle:worst_loss

replacement score modes:
  prior_actual_mean
  bias_corrected

support filters:
  calibration_min_context_count = 50
  candidate_min_prior_count = 50,100
  candidate_min_prior_month_count = 2
  candidate_min_prior_actual_mean = 0
```

`oracle:worst_loss` is diagnostic ceiling only. Candidate realized PnL remains evaluation-only.

## Target Set

| role | family | month | inventory best PnL | current baseline | evaluated | trades | losses |
|---|---|---|---:|---:|---|---:|---:|
| `refit2025_validation` | `refit2025` | `2025-03` | `-0.4730` | `-0.4730` | yes | 9 | 4 |
| `refit2025_validation` | `refit2025` | `2025-09` | `-0.4374` | `+25.5186` | yes | 8 | 3 |
| `refit2025_validation` | `refit2025` | `2025-06` | `-0.3744` | `+14.8104` | yes | 4 | 2 |
| `refit2025_validation` | `refit2025` | `2025-05` | `-9.3634` | `+1.4766` | yes | 15 | 6 |
| `refit2025_validation` | `refit2025` | `2025-08` | `-0.8832` | n/a | no | n/a | n/a |
| `refit2025_validation` | `refit2025` | `2025-12` | `-1.2210` | `+23.5450` | yes | 9 | 4 |
| `refit2025_validation` | `refit2025` | `2025-02` | `-0.0120` | `+7.6160` | yes | 9 | 5 |
| `refit2025_validation` | `refit2025` | `2025-04` | `-0.3000` | `+107.8580` | yes | 23 | 7 |
| `hgb2024_0306_external` | `hgb2024_0306` | `2024-05` | `-0.6352` | `+0.9578` | yes | 21 | 10 |
| `refit2025_validation` | `refit2025` | `2025-10` | `-0.0046` | `+27.7980` | yes | 7 | 2 |
| `hgb2024_0306_external` | `hgb2024_0306` | `2024-03` | `-2.0850` | `+0.2224` | yes | 22 | 11 |

This means the run is a cross-artifact stress test, not a pure current-branch negative-month repair test. Most target identities are negative somewhere in artifact history but already positive in the current 00314/00318 path.

## Surface Result

Best rows:

| risk selector | score | candidate prior | mean PnL | min PnL | mean delta | selected losses | selected winners | positive months |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `oracle:worst_loss` | `bias_corrected` | `>=100` | `+40.4309` | `-11.7730` | `+19.4980` | 10 | 0 | 9 |
| `combined:any_lossrisk` | `bias_corrected` | `>=100` | `+33.2963` | `-19.3690` | `+12.3633` | 3 | 7 | 9 |
| `feature:ev_ge5_lossfirst_lt0p30` | `bias_corrected` | `>=100` | `+29.1371` | `-19.3690` | `+8.2042` | 5 | 4 | 9 |
| `feature:side_gap_ge0p15_lossfirst_lt0p30` | `bias_corrected` | `>=100` | `+26.2583` | `-19.3690` | `+5.3253` | 2 | 5 | 9 |
| `combined:any_lossrisk` | `prior_actual_mean` | `>=100` | `+13.1204` | `-26.8140` | `-7.8126` | 3 | 7 | 8 |

The apparent positive mean is not enough:

- `combined:any_lossrisk` selects winner trades in 7/10 targets.
- `feature:side_gap_ge0p15_lossfirst_lt0p30` selects winner trades in 5/7 selected targets.
- The min month remains negative because `hgb2024_0306 2024-05` is damaged by the replacement path.
- Even `oracle:worst_loss` has min `-11.7730`, so replacement selection/calibration still fails in at least one target.

## Failure Detail

For `feature:side_gap_ge0p15_lossfirst_lt0p30` + `bias_corrected` + prior count `>=100`:

| target | baseline | selected trade | replacement | after | delta |
|---|---:|---|---|---:|---:|
| `hgb2024_0306 2024-05` | `+0.9578` | loss `-3.8520` | chosen bad | `-19.3690` | `-20.3268` |
| `refit2025 2025-03` | `-0.4730` | loss `-2.3400` | chosen good | `+9.5340` | `+10.0070` |
| `refit2025 2025-10` | `+27.7980` | winner `+7.5600` | chosen good | `+76.5980` | `+48.8000` |
| `refit2025 2025-12` | `+23.5450` | winner `+4.0370` | chosen good | `+30.9780` | `+7.4330` |

So the replacement selector can compensate for a bad risk selection in some months, but that is not evidence that the risk selector is robust. It remains possible to improve mean PnL by deleting winners when the replacement is even better, which is not a stable loss-risk policy.

## Decision

Accepted:

- `--targets-inventory`
- inventory filters for canonical support-sufficient target selection
- `evaluated_by_surface` / current baseline annotation in target inventory output

Rejected as standard policy:

- `combined:any_lossrisk`
- `feature:side_gap_ge0p15_lossfirst_lt0p30`
- interpreting mean PnL improvement on mostly-positive baseline months as loss-risk success

Standard policy remains NoTrade.

## Next

1. Split the next evaluation into two reports:
   - current-branch negative repair: only targets that are negative in the evaluated path
   - cross-artifact robustness: target identities that were negative somewhere else
2. Add winner-damage constraints to the selector objective before using replacement improvement as evidence.
3. Diagnose `hgb2024_0306 2024-05` replacement failure, because even oracle loss selection can leave a negative month.

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_support_sufficient_selector_surface_diagnostics.py tests/test_entry_ev_support_sufficient_selector_surface_diagnostics.py`: OK
- `uv run python -m unittest tests.test_entry_ev_support_sufficient_selector_surface_diagnostics`: OK
- 00371 canonical support-sufficient selector surface run: OK
