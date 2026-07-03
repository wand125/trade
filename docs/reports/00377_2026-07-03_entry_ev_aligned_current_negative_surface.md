# Entry EV Aligned Current-Negative Surface

日時: 2026-07-03 21:47 JST
更新日時: 2026-07-03 21:47 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00376の次アクションとして、schema-ready artifact `00310_position_quality_proxy_overlay_s1` に既存00318 configのprediction/repair target設定を合成し、variant familyを揃えたcurrent-negative surfaceを実行した。
- `selector_variant_contains` は `loss_exit30_cd15__holdext_isolated_large_loss_long_t-5_h720__entryblock_long_range_normal_ny_fixed60_pred_gt0`、`entry_block_rule` は `long_range_normal_ny_fixed60_pred_gt0` に固定した。
- 明示指定target 5件中、評価できたcurrent-negative targetは4件。
- 非oracleでは `feature:side_gap_ge0p15_lossfirst_lt0p30` + `prior_actual_mean` と `feature:ev_ge5_lossfirst_lt0p30` + `prior_actual_mean` がwinner-damage制約を通過した。
- ただし改善は実質 `refit2025 2025-03` の1件だけ。`fresh2024 2024-03` と `fresh2024 2024-11` はloss tradeを選べたがsupported replacement candidateが0、`hybrid2025_0912 2025-11` はrisk trade選択なしでbaseline維持だった。
- 判断: aligned surfaceは有用なstressだが、multi-target repair evidenceではない。support-limited月の候補不足が再確認された。標準policyはNoTrade。

## Artifacts

Generated config:

- `data/reports/backtests/20260703_generated_surface_configs/00377_00310_long_tminus5_fixed60_surface_config.json`

Selector surface:

- `data/reports/backtests/20260703_124711_20260703_entry_ev_00377_00310_aligned_current_negative_selector_surface/`

Replacement abstention:

- `data/reports/backtests/20260703_124725_20260703_entry_ev_00377_00310_aligned_current_negative_replacement_abstention/`

## Method

Built a generated config by taking the 00318 surface config and replacing:

```text
current_trades = data/reports/backtests/20260702_082037_20260702_entry_ev_00310_position_quality_proxy_overlay_s1/entry_block_overlay_trades.csv
variant_contains = loss_exit30_cd15__holdext_isolated_large_loss_long_t-5_h720
selector_variant_contains = loss_exit30_cd15__holdext_isolated_large_loss_long_t-5_h720__entryblock_long_range_normal_ny_fixed60_pred_gt0
entry_block_rule = long_range_normal_ny_fixed60_pred_gt0
```

Explicit targets:

```text
fresh2024_validation:2024-03:both
fresh2024_validation:2024-11:both
refit2025_validation:2025-03:both
refit2025_validation:2025-08:both
hybrid2025_0912_external:2025-11:both
```

The run evaluated 4 targets. `refit2025 2025-08` was not evaluated in this aligned surface path.

## Selector Result

Top nonoracle rows:

| risk selector | score | prior count | targets | loss selected | winner selected | precision | current-negative min delta | mean delta | pass |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| `feature:side_gap_ge0p15_lossfirst_lt0p30` | `prior_actual_mean` | 100 | 4 | 3 | 0 | `1.0000` | `0.0000` | `+5.0618` | yes |
| `feature:ev_ge5_lossfirst_lt0p30` | `prior_actual_mean` | 100 | 4 | 3 | 0 | `1.0000` | `0.0000` | `+4.5599` | yes |
| `feature:side_gap_ge0p15_lossfirst_lt0p30` | `bias_corrected` | 100 | 4 | 3 | 0 | `1.0000` | `0.0000` | `+2.5018` | yes |
| `combined:any_lossrisk` | `prior_actual_mean` | 100 | 4 | 3 | 1 | `0.7500` | `0.0000` | `+9.3843` | no |

The `combined:any_lossrisk` row has higher mean delta but still selects one winner, so it remains rejected by the winner-damage constraint.

## Target Detail

Representative row: `feature:side_gap_ge0p15_lossfirst_lt0p30` + `prior_actual_mean` + candidate prior count `>=100`.

| target | baseline | risk trade | supported candidates | after | delta | note |
|---|---:|---:|---:|---:|---:|---|
| `fresh2024 2024-03` | `-0.3636` | loss `-0.3636` | 0 | `-0.3636` | `0.0000` | support-limited, no replacement |
| `fresh2024 2024-11` | `-0.6120` | loss `-0.6120` | 0 | `-0.6120` | `0.0000` | support-limited, no replacement |
| `refit2025 2025-03` | `-0.4730` | loss `-2.3400` | 151 | `+19.7740` | `+20.2470` | same repair as 00374/00375 |
| `hybrid2025_0912 2025-11` | `-0.7200` | none | 0 | `-0.7200` | `0.0000` | no risk trade selected |

The pass is therefore a "no damage plus one useful intervention" result, not broad multi-target repair.

## Abstention Result

Replacement abstention did not change the main interpretation:

- `keep_all_replacements` for the representative nonoracle row intervened only on `refit2025 2025-03`.
- `fresh2024 2024-03`, `fresh2024 2024-11`, and `hybrid2025_0912 2025-11` stayed at baseline.
- gates such as `pred_mae_margin >= -10` passed all rows, but that is mostly because non-intervention rows are harmless.

## Decision

Accepted:

- generated config synthesis for schema-ready artifact
- aligned current-negative surface as stress infrastructure
- nonoracle loss selection signal in the aligned path as a diagnostic signal

Rejected:

- treating this as multi-target replacement success
- treating support-limited no-candidate baseline preservation as repair
- using `combined:any_lossrisk` despite higher mean delta, because it still selects a winner

Standard policy remains NoTrade.

## Next

1. Split the next work into two lanes:
   - support-sufficient current-negative repair: keep using `refit2025 2025-03` and search other aligned artifacts where extra trades needed are 0.
   - support-limited current-negative repair: solve candidate generation for `fresh2024 2024-03`, `fresh2024 2024-11`, and `hybrid2025_0912 2025-11`.
2. For support-limited targets, do not count baseline preservation as success. Require at least one supported candidate or a separate entry-generation repair.
3. Try another schema-ready artifact from 00376, especially `short_entryblock_replacement_holdext_block_overlay_s1`, to see whether the no-candidate pattern persists.

## Verification

- 00377 generated config: OK
- 00377 selector surface run: OK
- 00377 replacement abstention run: OK
