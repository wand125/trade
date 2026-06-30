# Early-2024 Chronological Risk OOF

日時: 2026-06-30 12:38 JST
更新日時: 2026-06-30 12:38 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00205の次アクションとして、早期2024のHGB+MLP hybrid predictionを生成し、stateful risk OOFを `2024-05` まで前倒しした。
- 漏洩を抑えるため、HGB/MLPは `2023-01..12` だけでfitし、`2024-01..02` をvalidation、`2024-03..06` をtestにした。これは既存same-familyより保守的なchronological preflightであり、完全な同一family比較ではない。
- early side-penalty delta examplesを既存stateful examplesに追加し、session context walk-forward stressを12ヶ月へ拡張した。
- stateful risk OOFは `2024-05, 2024-06, 2024-07, 2024-09, 2024-11, 2024-12, 2025-01..04` に出力できた。OOF AUCは `0.6800`。
- 純2024の利用可能6ヶ月固定比較では、source p10/replm10が合計 `+21.6688` と最良だが、no-side-penaltyは worst month `-74.9020`、max DD `112.0964` と最も防御的。side-penalty系は合計改善とtail悪化が混在する。
- 結論: 早期2024 risk列生成の道は開けたが、side penalty / sourceを標準採用する根拠にはならない。むしろ、side hook追加よりside/EV calibrationとtail mandateの分離が必要。

## Artifacts

- HGB model: `experiments/20260630_032926_policy_combined_side_exit_chrono_2024_03_06/`
- MLP model: `experiments/20260630_032949_shared_mlp_hgb_split_chrono_2024_03_06/`
- Hybrid predictions: `data/reports/modeling/20260630_chrono_hgb_mlp_exit_2024_03_06/predictions_hgb_entry_mlp_exit_2024_03_06.parquet`
- Early + existing 8m predictions: `data/reports/modeling/20260630_chrono_early2024_plus_8m_predictions/predictions_hgb_entry_mlp_exit_early2024_plus_8m.parquet`
- Early side-penalty delta: `data/reports/backtests/20260630_033419_chrono_early2024_side_penalty_delta/`
- Expanded walk-forward stress examples: `data/reports/backtests/20260630_033443_stateful_examples_session_context_walkforward_stress_early2024/`
- Stateful risk OOF: `experiments/20260630_033548_stateful_risk_early2024_session_floor_lowered_oof/`
- Fixed comparisons:
  - risk5 side penalty: `data/reports/backtests/20260630_033629_chrono_early2024_risk5_max260_fixed/`
  - risk0 side penalty: `data/reports/backtests/20260630_033703_chrono_early2024_risk0_sidepenalty_max260_fixed/`
  - risk0 no side penalty: `data/reports/backtests/20260630_033703_chrono_early2024_risk0_nosidepenalty_max260_fixed/`
  - source p10/replm10: `data/reports/backtests/20260630_033732_chrono_early2024_source_p10_replm10_max260_fixed/`

## Prediction Generation

Chronological split:

| split | months |
|---|---|
| train | `2023-01..2023-12` |
| validation | `2024-01, 2024-02` |
| test | `2024-03, 2024-04, 2024-05, 2024-06` |

Hybrid output:

| item | value |
|---|---:|
| rows | `116,918` |
| months | `2024-03..2024-06` |
| columns | `170` |
| MLP merge missing rows | `0` |
| forced target missing rows | `0` |

MLP exit timing:

| split | long exit minutes R2 | short exit minutes R2 |
|---|---:|---:|
| validation `2024-01..02` | `0.3046` | `0.3452` |
| test `2024-03..06` | `0.1807` | `0.2056` |

The MLP again emitted a convergence warning at `max_iter=40`. The test R2 is weaker than validation, so this artifact should be treated as a chronological preflight, not a model-quality upgrade.

## Early Stateful Examples

The first early examples compare:

- base: no side EV penalty
- candidate: existing side EV penalty rules `short:down_low_vol:5`, `short:up_low_vol:10`
- common policy: coststress, `maxhold=260`, risk penalty `0`, entry `12`, short offset `6`, side margin `5`

Side-penalty candidate vs no-side base:

| month | base PnL | candidate PnL | delta |
|---|---:|---:|---:|
| 2024-03 | `-42.7274` | `+9.4938` | `+52.2212` |
| 2024-04 | `-76.1968` | `-156.8664` | `-80.6696` |
| 2024-05 | `-40.2318` | `-127.6350` | `-87.4032` |
| 2024-06 | `-3.3658` | `-28.0244` | `-24.6586` |

Worst candidate stateful groups:

| month | group | candidate stateful net |
|---|---|---:|
| 2024-05 | `only_candidate long down_low_vol` | `-98.6348` |
| 2024-04 | `only_candidate long down_low_vol` | `-61.9822` |
| 2024-04 | `only_candidate short range_normal_vol` | `-44.4220` |
| 2024-06 | `only_candidate short up_normal_vol` | `-37.7316` |
| 2024-06 | `only_candidate long down_low_vol` | `-37.2814` |

This is another warning that side hooks can create long-side replacement losses, not only short-side cleanup.

## Expanded Risk OOF

Walk-forward stress examples:

| item | value |
|---|---:|
| rows | `1,903` |
| months | `12` |
| profiled months | `10` |
| stress flag count | `261` |
| target mean | `0.2955` |
| stress-adjusted mean | `-0.7762` |

Stateful risk OOF:

| item | value |
|---|---:|
| validation prediction rows | `346,294` |
| OOF prediction rows | `288,406` |
| OOF months | `2024-05, 2024-06, 2024-07, 2024-09, 2024-11, 2024-12, 2025-01..04` |
| target prevalence | `0.2726` |
| predicted mean | `0.1677` |
| bias | `-0.1049` |
| brier | `0.1945` |
| AUC | `0.6800` |

The earlier months work as intended: with `min_train_months=2`, `2024-03` and `2024-04` are skipped, and `2024-05` is the first scored month.

## Pure-2024 Fixed Comparison

Evaluation months: `2024-05, 2024-06, 2024-07, 2024-09, 2024-11, 2024-12`.

Common settings:

- coststress: spread `0.2`, slippage `0.1`, delay `1`
- profit multiplier `1.0`, loss multiplier `1.20`
- `max_predicted_hold_minutes=260`
- entry `12`, short offset `6`, side margin `5`

Aggregate:

| policy | trades | total PnL | worst month | max DD | long PnL | short PnL | direction error | EV over realized |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| source p10/replm10 | `513` | `+21.6688` | `-107.9646` | `123.1386` | `-31.3974` | `+53.0662` | `0.4404` | `16.1427` |
| risk0 no-side-penalty | `232` | `+12.0322` | `-74.9020` | `112.0964` | `-60.3904` | `+72.4226` | `0.3960` | `18.7339` |
| risk5 side-penalty | `559` | `+2.1998` | `-127.6350` | `142.8090` | `-49.7254` | `+51.9252` | `0.4362` | `15.8341` |
| risk0 side-penalty | `584` | `-20.0128` | `-127.6350` | `142.8090` | `-66.7800` | `+46.7672` | `0.4389` | `15.7367` |

Monthly PnL:

| month | no-side | risk0 side | risk5 side | source p10/replm10 |
|---|---:|---:|---:|---:|
| 2024-05 | `-40.6918` | `-127.6350` | `-127.6350` | `-107.9646` |
| 2024-06 | `-3.3658` | `-28.0244` | `-20.3262` | `-13.8766` |
| 2024-07 | `+10.0144` | `+88.4636` | `+64.8436` | `+101.3926` |
| 2024-09 | `+30.4652` | `+76.2632` | `+57.6646` | `+52.0320` |
| 2024-11 | `+90.5122` | `+2.2056` | `+62.4042` | `-17.3652` |
| 2024-12 | `-74.9020` | `-31.2858` | `-34.7514` | `+7.4506` |

## Interpretation

- The early-2024 check does not validate adding more side hooks. The source policy has the best total, but its worst month is worse than no-side.
- The no-side policy has far fewer trades and better tail metrics, which suggests that admission volume is still part of the problem.
- Risk5 helps the side-penalty policy versus risk0 on total (`-20.0128 -> +2.1998`) but does not improve worst month (`-127.6350` unchanged).
- The side-penalty candidate created major `long/down_low_vol` replacement losses in early 2024. This matches 00205's warning that short-only fixes can move residual risk into long exposure.
- Because this run uses a 2023-only base model for 2024-03..06 while older 2024-07+ predictions come from the existing family, the comparison is a bridge artifact. It is useful for chronological risk coverage and failure discovery, not for final policy promotion.

## Decision

- Do not promote source p10/replm10 or risk5 side-penalty from this result.
- Keep the new early-2024 risk OOF as a diagnostic artifact and as the starting point for wider pure-2024 checks.
- Before testing `gap0/gap5/budget0` on pure2024, decide whether to keep this mixed-family bridge or regenerate all 2024 months with one chronological training protocol.
- The next modeling direction remains side/EV calibration and admission control, not adding another short-only hook.

## Verification

- HGB chronological train: OK
- MLP chronological train: OK, with convergence warning at `max_iter=40`
- Hybrid merge: OK, MLP missing rows `0`
- Forced target columns in hybrid frame: OK
- Early side-penalty delta examples: OK
- Expanded walk-forward stress target: OK
- Stateful risk OOF: OK, first scored month `2024-05`
- Fixed pure-2024 comparison: OK
