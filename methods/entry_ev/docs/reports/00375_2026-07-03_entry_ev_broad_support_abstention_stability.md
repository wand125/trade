# Entry EV Broad Support Abstention Stability

日時: 2026-07-03 21:28 JST
更新日時: 2026-07-03 21:28 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00374の `prior_actual_mean >=25` / `prior_margin >=0` 系abstentionが、00371/00373の11-target setに過適合していないかを見るため、00370 inventoryの条件を `support_sufficient_config_count >=1`、`metric_parent_count >=2` へ緩めた。
- target inventoryは14件、現00314/00318 configで評価できたtargetは13件。00371比で `hgb2024_0306 2024-06`、`hgb2025_08 2025-08`、`cal2024 2024-01` が追加評価された。
- 広いsurfaceでもwinner-damage ranking単体は通過0件。non-oracleのloss precisionはむしろ低下し、`ev_ge5_lossfirst_lt0p30` は `0.5556 -> 0.4545`、`side_gap_ge0p15_lossfirst_lt0p30` は `0.2857 -> 0.2222`。
- 00374のabstention sweepを広いsurfaceへ適用すると、代表nonoracle row `feature:side_gap_ge0p15_lossfirst_lt0p30` + `prior_actual_mean` + candidate prior count `>=100` + abstention `prior_actual_mean >=25` は引き続き制約通過した。
- ただし介入は依然 `refit2025 2025-03` の1件だけ。追加3targetは介入せずbaseline維持。mean deltaは `+2.0247` から `+1.5575` へ薄まった。
- 判断: abstention gateは広いsupport-sufficient target setでも壊れなかったが、複数targetで効いた証拠ではない。`prior_actual_mean >=25` 系はdiagnostic candidateに留め、標準policyはNoTrade。

## Artifacts

Broad selector surface run:

- `data/reports/backtests/20260703_122750_20260703_entry_ev_00375_broad_support_sufficient_selector_surface/`

Broad abstention run:

- `data/reports/backtests/20260703_122759_20260703_entry_ev_00375_broad_support_replacement_abstention/`

Outputs:

- `support_sufficient_selector_surface_choices.csv`
- `support_sufficient_selector_surface_summary.csv`
- `support_sufficient_selector_surface_target_inventory.csv`
- `replacement_abstention_surface_choices.csv`
- `replacement_abstention_surface_summary.csv`
- `replacement_abstention_gate_summary.csv`

## Method

Changed target source filter:

```text
--targets-inventory support_negative_month_target_summary.csv
--inventory-min-support-sufficient-configs 1
--inventory-min-metric-parents 2
--inventory-target-side both
```

Kept the same focused selector/replacement grid as 00373:

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

Then applied the 00374 replacement abstention surface without changing its gates.

## Target Set

| target | evaluated | baseline | support sufficient configs | metric parents | inventory best | current trades | losses |
|---|---|---:|---:|---:|---:|---:|---:|
| `refit2025 2025-03` | yes | `-0.4730` | 1250 | 17 | `-0.4730` | 9 | 4 |
| `refit2025 2025-09` | yes | `+25.5186` | 1118 | 16 | `-0.4374` | 8 | 3 |
| `refit2025 2025-06` | yes | `+14.8104` | 756 | 17 | `-0.3744` | 4 | 2 |
| `refit2025 2025-05` | yes | `+1.4766` | 429 | 17 | `-9.3634` | 15 | 6 |
| `refit2025 2025-08` | no | n/a | 406 | 15 | `-0.8832` | n/a | n/a |
| `refit2025 2025-12` | yes | `+23.5450` | 345 | 13 | `-1.2210` | 9 | 4 |
| `refit2025 2025-02` | yes | `+7.6160` | 308 | 13 | `-0.0120` | 9 | 5 |
| `refit2025 2025-04` | yes | `+107.8580` | 163 | 11 | `-0.3000` | 23 | 7 |
| `hgb2024_0306 2024-05` | yes | `+0.9578` | 135 | 5 | `-0.6352` | 21 | 10 |
| `refit2025 2025-10` | yes | `+27.7980` | 72 | 8 | `-0.0046` | 7 | 2 |
| `hgb2024_0306 2024-03` | yes | `+0.2224` | 66 | 7 | `-2.0850` | 22 | 11 |
| `hgb2024_0306 2024-06` | yes | `+1.2246` | 11 | 2 | `-1.4284` | 16 | 9 |
| `hgb2025_08 2025-08` | yes | `+0.5354` | 5 | 2 | `-0.1760` | 11 | 4 |
| `cal2024 2024-01` | yes | `+6.9988` | 1 | 2 | `-0.3984` | 31 | 15 |

Only `refit2025 2025-03` is current-negative in the evaluated path. The added targets are cross-artifact negative identities that are positive in the current path.

## Broad Surface Result

Winner-damage ranking without abstention still fails all rows:

| risk selector | score | prior count | targets | loss precision | selected losses | selected winners | baseline-positive degraded | current-negative min delta | mean delta | pass |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `oracle:worst_loss` | `bias_corrected` | 100 | 13 | `1.0000` | 13 | 0 | 1 | `+10.0070` | `+15.8505` | no |
| `oracle:worst_loss` | `prior_actual_mean` | 100 | 13 | `1.0000` | 13 | 0 | 3 | `+20.2470` | `-0.2199` | no |
| `feature:ev_ge5_lossfirst_lt0p30` | `bias_corrected` | 100 | 13 | `0.4545` | 5 | 6 | 2 | `+7.9994` | `+6.7694` | no |
| `combined:any_lossrisk` | `bias_corrected` | 100 | 13 | `0.2308` | 3 | 10 | 1 | `+6.2870` | `+9.9441` | no |
| `feature:side_gap_ge0p15_lossfirst_lt0p30` | `bias_corrected` | 100 | 13 | `0.2222` | 2 | 7 | 1 | `+10.0070` | `+4.3800` | no |

The broader target set makes observable risk selection look weaker, not stronger.

## Abstention Stability

Representative nonoracle passing row after broadening:

| gate | risk selector | score | prior count | targets | interventions | loss interventions | winner interventions | baseline-positive degraded | current-negative delta | mean delta | pass |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `prior_actual_mean_ge_25` | `feature:side_gap_ge0p15_lossfirst_lt0p30` | `prior_actual_mean` | 100 | 13 | 1 | 1 | 0 | 0 | `+20.2470` | `+1.5575` | yes |
| `prior_margin_ge_0` | `feature:side_gap_ge0p15_lossfirst_lt0p30` | `prior_actual_mean` | 100 | 13 | 1 | 1 | 0 | 0 | `+20.2470` | `+1.5575` | yes |
| `prior_actual_mean_ge_20` | `feature:ev_ge5_lossfirst_lt0p30` | `prior_actual_mean` | 100 | 13 | 2 | 2 | 0 | 0 | `+18.2394` | `+5.0478` | yes |

Target detail for `prior_actual_mean_ge_25` + `side_gap`:

| target | baseline | risk trade | gate passed | after | delta |
|---|---:|---:|---|---:|---:|
| `refit2025 2025-03` | `-0.4730` | loss `-2.3400` | yes | `+19.7740` | `+20.2470` |
| `hgb2024_0306 2024-05` | `+0.9578` | loss `-3.8520` | no | `+0.9578` | `0.0000` |
| `hgb2024_0306 2024-06` | `+1.2246` | winner `+2.7130` | no | `+1.2246` | `0.0000` |
| `hgb2025_08 2025-08` | `+0.5354` | none | no | `+0.5354` | `0.0000` |
| `cal2024 2024-01` | `+6.9988` | winner `+0.7300` | no | `+6.9988` | `0.0000` |

The gate did not damage the added targets, but it also did not repair them. Its useful action remains the same single `refit2025 2025-03` intervention.

## Decision

Accepted:

- broad support-sufficient target-set stress for selector/abstention surfaces
- using broader target stress to distinguish "does not break" from "works on multiple targets"

Diagnostic candidate, not standard:

- `prior_actual_mean >=25` / `prior_margin >=0` replacement abstention

Rejected as standard evidence:

- interpreting broad-set pass with one intervention as multi-target robustness
- improving mean delta through no-intervention rows
- relaxing support-sufficient target filters and treating variant inventory rows as independent samples

Standard policy remains NoTrade.

## Next

1. Build a target split that contains more current-negative evaluated targets, not only cross-artifact negative identities that are currently positive.
2. Stress `prior_actual_mean >=25` / `prior_margin >=0` on a different branch/artifact config if available.
3. If no additional current-negative support-sufficient targets exist in current artifacts, move the gate into a diagnostic first-class score mode but keep policy admission at NoTrade.

## Verification

- 00375 broad support-sufficient selector surface run: OK
- 00375 broad support replacement abstention run: OK
