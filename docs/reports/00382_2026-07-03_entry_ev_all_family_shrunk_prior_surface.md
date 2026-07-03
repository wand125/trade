# Entry EV All-Family Shrunk Prior Surface

日時: 2026-07-03 22:33 JST
更新日時: 2026-07-03 22:33 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00379の `--prior-scope all_families_prior_months` をselector surface本体へ接続した。
- replacement calibrationへ `shrunk_prior_actual_mean` を追加した。`prior_actual_mean` に `prior_count` と `prior_month_count` の両方から作るshrink weightを掛け、薄いcross-family contextの過大評価を抑える。
- 00381と同じ00378 aligned surface条件を、all-family prior + `shrunk_prior_actual_mean,prior_actual_mean,side_score,bias_corrected` で再実行した。
- 48 surface rows中、旧winner-damage制約は20行が通過したが、target outcome制約は0行だった。
- all-family priorはcandidate gapを少し減らした。非oracle `feature:ev_ge5_lossfirst_lt0p30` はcandidate gap `3 -> 2`、oracleは `3 -> 2`。
- ただし `shrunk_prior_actual_mean` はraw `prior_actual_mean` と同じ選択になり、target outcome passには届かなかった。
- 判断: all-family prior / shrunk prior infrastructureはaccepted。direct all-family replacement policyはreject。標準policyはNoTrade。

## Artifacts

Run:

- `data/reports/backtests/20260703_133252_20260703_entry_ev_00382_all_family_shrunk_prior_surface_00378/`

Code:

- `scripts/experiments/entry_ev_support_sufficient_replacement_calibration_diagnostics.py`
- `scripts/experiments/entry_ev_support_sufficient_selector_surface_diagnostics.py`
- `tests/test_entry_ev_support_sufficient_replacement_calibration_diagnostics.py`
- `tests/test_entry_ev_support_sufficient_selector_surface_diagnostics.py`

## Method

00378 aligned surface configを使用:

```text
config: data/reports/backtests/20260703_generated_surface_configs/00378_074738_long_tminus5_holdext_surface_config.json
targets:
  hgb2024_0306_external:2024-03:both
  fresh2024_validation:2024-03:both
  fresh2024_validation:2024-11:both
  refit2025_validation:2025-03:both
  refit2025_validation:2025-08:both
  hybrid2025_0912_external:2025-11:both
prior scope: all_families_prior_months
score modes: shrunk_prior_actual_mean,prior_actual_mean,side_score,bias_corrected
risk selectors:
  feature:side_gap_ge0p15_lossfirst_lt0p30
  feature:ev_ge5_lossfirst_lt0p30
  combined:any_lossrisk
  oracle:worst_loss
candidate prior counts: 20,50,100
candidate prior month count: 2
```

Shrink definition:

```text
count_weight = prior_count / (prior_count + prior_shrinkage_count)
month_weight = prior_month_count / (prior_month_count + prior_shrinkage_month_count)
prior_shrink_weight = min(count_weight, month_weight)
shrunk_prior_actual_mean = prior_actual_mean * prior_shrink_weight

default:
  prior_shrinkage_count = 100
  prior_shrinkage_month_count = 3
```

The surface now records `prior_scope`, shrinkage parameters, `prior_family_count`, and choice-level `prior_shrink_weight`.

## Result

| metric | value |
|---|---:|
| surface rows | 48 |
| old winner-damage pass | 20 |
| target outcome pass | 0 |
| minimum candidate gap count | 1 |
| maximum success count | 3 |
| minimum risk gap count | 0 |

Top rows by the new ranking:

| risk selector | score | prior count | old pass | outcome pass | success | candidate gap | risk gap | mean after | mean delta |
|---|---|---:|---|---|---:|---:|---:|---:|---:|
| `oracle:worst_loss` | `side_score` | 20 | yes | no | 3 | 2 | 0 | `+10.8766` | `+14.8490` |
| `oracle:worst_loss` | `bias_corrected` | 20 | yes | no | 3 | 2 | 0 | `+2.5858` | `+6.5582` |
| `oracle:worst_loss` | `prior_actual_mean` | 100 | yes | no | 3 | 2 | 0 | `+1.8132` | `+5.7856` |
| `oracle:worst_loss` | `shrunk_prior_actual_mean` | 20 | yes | no | 3 | 2 | 0 | `+1.8132` | `+5.7856` |
| `feature:ev_ge5_lossfirst_lt0p30` | `side_score` | 20 | yes | no | 2 | 2 | 1 | `+5.3544` | `+9.3269` |
| `feature:ev_ge5_lossfirst_lt0p30` | `bias_corrected` | 20 | yes | no | 2 | 2 | 1 | `+0.7342` | `+4.7067` |
| `feature:ev_ge5_lossfirst_lt0p30` | `prior_actual_mean` | 100 | yes | no | 2 | 2 | 1 | `-0.0384` | `+3.9341` |
| `feature:ev_ge5_lossfirst_lt0p30` | `shrunk_prior_actual_mean` | 20 | yes | no | 2 | 2 | 1 | `-0.0384` | `+3.9341` |

The important comparison with 00381:

| selector | prior scope | success | candidate gap | risk gap | mean after |
|---|---|---:|---:|---:|---:|
| nonoracle `ev_ge5` + `prior_actual_mean` | same family | 1 | 3 | 1 | `-0.3246` |
| nonoracle `ev_ge5` + `shrunk_prior_actual_mean` | all families | 2 | 2 | 1 | `-0.0384` |
| oracle `worst_loss` + `prior_actual_mean` | same family | 2 | 3 | 0 | `+4.2790` |
| oracle `worst_loss` + `shrunk_prior_actual_mean` | all families | 3 | 2 | 0 | `+1.8132` |

All-family prior helps support, but shrinkage does not yet improve ranking enough to pass target outcome constraints.

## Representative Detail

Nonoracle row:

```text
risk_selector = feature:ev_ge5_lossfirst_lt0p30
replacement_score_mode = shrunk_prior_actual_mean
candidate_min_prior_count = 20
```

| target | outcome | supported candidates | chosen | prior count | prior months | shrink weight | shrunk prior mean | after | delta |
|---|---|---:|---|---:|---:|---:|---:|---:|---:|
| `hgb2024_0306 2024-03` | `loss_selected_no_supported_candidate` | 0 | no | 0 | 0 | n/a | n/a | `-17.6936` | `0.0000` |
| `fresh2024 2024-03` | `loss_selected_no_supported_candidate` | 0 | no | 0 | 0 | n/a | n/a | `-0.3636` | `0.0000` |
| `fresh2024 2024-11` | `loss_replacement_repairs_month` | 24 | short 720m | 285 | 6 | `0.6667` | `+6.3806` | `+0.8190` | `+1.4310` |
| `refit2025 2025-03` | `loss_replacement_repairs_month` | 331 | long 720m | 438 | 7 | `0.7000` | `+10.8044` | `+17.7664` | `+18.2394` |
| `hybrid2025_0912 2025-11` | `no_risk_trade` | 0 | no | n/a | n/a | n/a | n/a | `-0.7200` | `0.0000` |

Reading:

- all-family prior made `fresh2024 2024-11` repairable under the nonoracle selector.
- `hgb2024_0306 2024-03` and `fresh2024 2024-03` still have no supported replacement in this risk/score row.
- `hybrid2025_0912 2025-11` remains a risk-selection miss for nonoracle `ev_ge5`.
- `side_score` improves mean PnL more than shrunk prior, but it is not a calibrated EV score and remains unsafe as direct policy evidence.

## Decision

Accepted:

- `shrunk_prior_actual_mean` score mode
- shrink parameter plumbing in replacement calibration and selector surface
- all-family prior scope in selector surface
- choice-level shrink observability (`prior_shrink_weight`, `shrunk_prior_actual_mean`)

Rejected:

- direct all-family prior adoption as replacement policy
- treating shrinkage as sufficient calibration
- choosing by `side_score` just because it improves this surface mean PnL
- reading reduced candidate gap as target outcome readiness while pass count remains 0

Standard policy remains NoTrade.

## Next

1. Split the next evaluation into two lanes:
   - support-limited candidate generation: why `hgb2024_0306 2024-03` / `fresh2024 2024-03` still have no supported replacement under this row.
   - support-sufficient replacement calibration: among targets with candidates, improve ranking without `side_score` shortcut.
2. Add per-target support gap diagnostics under `all_families_prior_months`: distinguish no risk trade, selected loss with no candidate, and supported candidate filtered out by prior floors.
3. Try replacement score mixtures that keep observable calibration:
   - `shrunk_prior_actual_mean` plus a capped side-score tie-break
   - horizon penalty for unstable 720m cross-family candidates
   - context family diversity floors before trusting all-family prior.

## Verification

- 00382 all-family shrunk prior selector surface run: OK
- Choices artifact includes `prior_shrink_weight` / `shrunk_prior_actual_mean`: OK
