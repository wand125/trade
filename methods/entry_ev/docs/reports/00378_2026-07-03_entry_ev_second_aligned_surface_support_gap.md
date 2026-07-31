# Entry EV Second Aligned Surface Support Gap

日時: 2026-07-03 21:54 JST
更新日時: 2026-07-03 21:54 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00377の再現確認として、00376の上位候補 `short_entryblock_replacement_holdext_block_overlay_s1` へ00318 configを合成した。
- variant familyは `loss_exit30_cd15__holdext_isolated_large_loss_long_t-5_h720`、entry blockは `holdext_long_range_normal_ny` に揃えた。
- 5 current-negative targetsを評価し、support-sufficient negative targetは `hgb2024_0306 2024-03` と `refit2025 2025-03` の2件に増えた。
- 非oracleでは `feature:ev_ge5_lossfirst_lt0p30` + `prior_actual_mean` がwinner-damage制約を通過した。
- ただし改善はまた `refit2025 2025-03` だけ。`hgb2024_0306 2024-03` はloss tradeを選べたがsupported replacement candidateが0で、月PnL `-17.6936` のまま残った。
- 判断: 00377のパターンは再現。追加support-sufficient targetは見つかったが、early-month prior不足でreplacement selectorが動けない。標準policyはNoTrade。

## Artifacts

Generated config:

- `data/reports/backtests/20260703_generated_surface_configs/00378_074738_long_tminus5_holdext_surface_config.json`

Selector surface:

- `data/reports/backtests/20260703_125327_20260703_entry_ev_00378_074738_aligned_current_negative_selector_surface/`

Replacement abstention:

- `data/reports/backtests/20260703_125337_20260703_entry_ev_00378_074738_aligned_current_negative_replacement_abstention/`

## Method

Generated config changes:

```text
current_trades = data/reports/backtests/20260702_074738_20260702_entry_ev_short_entryblock_replacement_holdext_block_overlay_s1/entry_block_overlay_trades.csv
variant_contains = loss_exit30_cd15__holdext_isolated_large_loss_long_t-5_h720
selector_variant_contains = loss_exit30_cd15__holdext_isolated_large_loss_long_t-5_h720__entryblock_holdext_long_range_normal_ny
entry_block_rule = holdext_long_range_normal_ny
```

Explicit targets:

```text
hgb2024_0306_external:2024-03:both
fresh2024_validation:2024-03:both
fresh2024_validation:2024-11:both
refit2025_validation:2025-03:both
refit2025_validation:2025-08:both
hybrid2025_0912_external:2025-11:both
```

The run evaluated 5 targets.

## Selector Result

| risk selector | score | prior count | targets | loss selected | winner selected | precision | after mean PnL | mean delta | pass |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| `feature:ev_ge5_lossfirst_lt0p30` | `prior_actual_mean` | 100 | 5 | 4 | 0 | `1.0000` | `-0.3246` | `+3.6479` | yes |
| `feature:ev_ge5_lossfirst_lt0p30` | `bias_corrected` | 100 | 5 | 4 | 0 | `1.0000` | `-2.3726` | `+1.5999` | yes |
| `feature:side_gap_ge0p15_lossfirst_lt0p30` | `prior_actual_mean` | 100 | 5 | 3 | 1 | `0.7500` | `+0.0770` | `+4.0494` | no |
| `combined:any_lossrisk` | `prior_actual_mean` | 100 | 5 | 3 | 2 | `0.6000` | `+3.5350` | `+7.5074` | no |

Oracle upper-bound:

| risk selector | score | targets | mean after | mean delta | pass |
|---|---|---:|---:|---:|---|
| `oracle:worst_loss` | `prior_actual_mean` | 5 | `+4.2790` | `+8.2514` | yes |

The oracle can repair `hybrid2025_0912 2025-11`, but still cannot repair `hgb2024_0306 2024-03` under the current support filter.

## Target Detail

Representative nonoracle row: `feature:ev_ge5_lossfirst_lt0p30` + `prior_actual_mean` + candidate prior count `>=100`.

| target | baseline | risk trade | supported candidates | after | delta | note |
|---|---:|---:|---:|---:|---:|---|
| `hgb2024_0306 2024-03` | `-17.6936` | loss `-0.3636` | 0 | `-17.6936` | `0.0000` | support-sufficient but early-month prior shortage |
| `fresh2024 2024-03` | `-0.3636` | loss `-0.3636` | 0 | `-0.3636` | `0.0000` | support-limited, no replacement |
| `fresh2024 2024-11` | `-0.6120` | loss `-0.6120` | 0 | `-0.6120` | `0.0000` | support-limited, no replacement |
| `refit2025 2025-03` | `-0.4730` | loss `-0.3324` | 151 | `+17.7664` | `+18.2394` | only effective nonoracle repair |
| `hybrid2025_0912 2025-11` | `-0.7200` | none | 0 | `-0.7200` | `0.0000` | no nonoracle risk trade |

Oracle row:

| target | baseline | risk trade | supported candidates | after | delta |
|---|---:|---:|---:|---:|---:|
| `hgb2024_0306 2024-03` | `-17.6936` | loss `-20.1840` | 0 | `-17.6936` | `0.0000` |
| `refit2025 2025-03` | `-0.4730` | loss `-2.3400` | 151 | `+19.7740` | `+20.2470` |
| `hybrid2025_0912 2025-11` | `-0.7200` | loss `-0.7200` | 4 | `+20.2900` | `+21.0100` |

This separates three issues:

- risk selector can find losses in several targets
- replacement selector cannot act when chronological prior support is absent
- oracle risk selection plus supported replacement has value in `hybrid2025_0912 2025-11`, but nonoracle risk selection does not reach it

## Decision

Accepted:

- second aligned artifact surface as stress infrastructure
- `hgb2024_0306 2024-03` as a real support-sufficient current-negative target
- treating early-month prior shortage as a first-class blocker

Rejected:

- interpreting nonoracle pass as policy readiness while mean after PnL remains negative
- counting selected loss without supported replacement as repair
- relaxing support filters globally without a separate early-month calibration design

Standard policy remains NoTrade.

## Next

1. Build an early-month replacement calibration lane for targets with candidate rows but no same-family prior support.
2. Test cross-family or regime-level prior carefully, with strict winner-damage and month-floor checks.
3. Add a target-level report that distinguishes:
   - risk trade selected but no supported candidate
   - supported candidate exists but wrong risk trade selected
   - both risk and replacement succeed

## Verification

- 00378 generated config: OK
- 00378 selector surface run: OK
- 00378 replacement abstention run: OK
