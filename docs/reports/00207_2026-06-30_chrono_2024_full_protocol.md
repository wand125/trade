# Chrono 2024 Full Protocol

日時: 2026-06-30 12:54 JST
更新日時: 2026-06-30 12:54 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00206の混合family bridge問題を閉じるため、2024-03..12をすべて同一chronological protocolで再生成した。HGB/MLPは `2023-01..12` だけでfitし、`2024-01..02` をvalidation、`2024-03..12` をtestにした。
- hybrid predictionは `296,756` rows、`2024-03..12`、MLP exit merge missing `0`、forced target欠損 `0`。00206の `2024-03..06` bridgeと、既存2024後半familyを混ぜる必要はなくなった。
- HGBのentry/EV回帰は弱く、validation `long_best_adjusted_pnl R2=-0.0757`, `short_best_adjusted_pnl R2=-0.0311`。一方、exit timingはHGB/MLPともR2が正で、MLP test `long_exit_event_minutes R2=0.2038`, `short_exit_event_minutes R2=0.2153`。これは「exit timingは使えるが、entry EVがまだ弱い」という状態。
- raw 10ヶ月では no-side risk0 `-260.3458`、side-penalty risk0 `-180.1554`。side penaltyは総損益を改善したが、worst month `-156.8664`、max DD `220.3144` へtailを悪化させた。
- 2024だけのside-penalty deltaから新しいstateful examplesを作り、session context walk-forward stress、stateful risk OOFを作った。risk OOFは `2024-05..12` に出力され、AUC `0.6689`。
- OOF 8ヶ月固定比較では source p10/replm10 が最良だが total `-3.1736` でNoTrade `0` に届かない。risk5 side penalty `-10.4618`、risk0 side penalty `-32.7828`、risk0 no-side `-141.8816`。
- 結論: 00206の混合family懸念は解消したが、標準採用できる2024 policyはまだない。source/risk5は診断上の比較対象として残すが、採用判断は「NoTradeを超え、worst/DDが許容できる」まで保留する。

## Artifacts

- HGB model: `experiments/20260630_034818_policy_combined_side_exit_chrono_2024_03_12/`
- MLP model: `experiments/20260630_034839_shared_mlp_hgb_split_chrono_2024_03_12/`
- Hybrid predictions: `data/reports/modeling/20260630_chrono_hgb_mlp_exit_2024_03_12/predictions_hgb_entry_mlp_exit_2024_03_12.parquet`
- Raw 10m no-side risk0: `data/reports/backtests/20260630_035026_chrono_2024_full_risk0_nosidepenalty_max260_fixed/`
- Raw 10m side-penalty risk0: `data/reports/backtests/20260630_035026_chrono_2024_full_risk0_sidepenalty_max260_fixed/`
- Side-penalty delta examples: `data/reports/backtests/20260630_035112_chrono_2024_full_side_penalty_delta/`
- Walk-forward stress examples: `data/reports/backtests/20260630_035120_stateful_examples_session_context_walkforward_stress_chrono_2024_full/`
- Stateful risk OOF: `experiments/20260630_035147_stateful_risk_chrono_2024_full_session_floor_lowered_oof/`
- OOF fixed comparisons:
  - no-side risk0: `data/reports/backtests/20260630_035226_chrono_2024_full_risk0_nosidepenalty_oof_max260_fixed/`
  - side-penalty risk0: `data/reports/backtests/20260630_035226_chrono_2024_full_risk0_sidepenalty_oof_max260_fixed/`
  - side-penalty risk5: `data/reports/backtests/20260630_035226_chrono_2024_full_risk5_sidepenalty_oof_max260_fixed/`
  - source p10/replm10: `data/reports/backtests/20260630_035227_chrono_2024_full_source_p10_replm10_oof_max260_fixed/`
- Compact comparison tables: `data/reports/backtests/20260630_035300_chrono_2024_full_oof_policy_compare/`

## Prediction Generation

Chronological split:

| split | months |
|---|---|
| train | `2023-01..2023-12` |
| validation | `2024-01, 2024-02` |
| test | `2024-03..2024-12` |

Hybrid output:

| item | value |
|---|---:|
| rows | `296,756` |
| months | `2024-03..2024-12` |
| columns | `170` |
| MLP exit missing rows | `0` |
| forced target missing rows | `0` |

Key model diagnostics:

| model / split | long EV R2 | short EV R2 | long exit minutes R2 | short exit minutes R2 | side score R2 |
|---|---:|---:|---:|---:|---:|
| HGB validation | `-0.0757` | `-0.0311` | `0.2845` | `0.2739` | `-0.0745` |
| HGB test | `-0.1116` | `0.0445` | `0.3071` | `0.3017` | `-0.0222` |
| MLP validation | `-0.2114` | `-0.1003` | `0.3046` | `0.3452` | `-0.2567` |
| MLP test | `-0.3504` | `-0.3155` | `0.2038` | `0.2153` | `-0.4441` |

The MLP again emitted the expected `max_iter=40` convergence warning. The important point is not that MLP is a better EV model; it is only used here for exit timing columns.

HGB calibrated selection was also a warning: validation selected `0` rows after calibration, while test selected `8,768` rows. The entry EV calibration is not stable enough to use as a direct admission signal without additional validation-time calibration.

## Raw 10-Month Side Penalty Check

Common settings:

- coststress: spread `0.2`, slippage `0.1`, delay `1`
- profit multiplier `1.0`, loss multiplier `1.20`
- `max_predicted_hold_minutes=260`
- entry `12`, short offset `6`, side margin `5`

Aggregate:

| policy | months | trades | total PnL | worst month | max DD | long PnL | short PnL |
|---|---:|---:|---:|---:|---:|---:|---:|
| raw10 no-side risk0 | `10` | `426` | `-260.3458` | `-81.0202` | `134.7892` | `-10.0876` | `-250.2582` |
| raw10 side-penalty risk0 | `10` | `926` | `-180.1554` | `-156.8664` | `220.3144` | `+5.7216` | `-185.8770` |

Side penalty reduces short loss but increases trade count and worsens tail. This is not an adoption signal; it is a source of candidate examples.

Monthly side-penalty delta:

| month | no-side PnL | side-penalty PnL | delta |
|---|---:|---:|---:|
| 2024-03 | `-42.7274` | `+9.4938` | `+52.2212` |
| 2024-04 | `-76.1968` | `-156.8664` | `-80.6696` |
| 2024-05 | `-40.2318` | `-127.6350` | `-87.4032` |
| 2024-06 | `-3.3658` | `-28.0244` | `-24.6586` |
| 2024-07 | `-28.7832` | `+12.6224` | `+41.4056` |
| 2024-08 | `-81.0202` | `-108.4514` | `-27.4312` |
| 2024-09 | `-76.0666` | `+22.7178` | `+98.7844` |
| 2024-10 | `-21.0610` | `+102.5526` | `+123.6136` |
| 2024-11 | `+172.2896` | `+213.8106` | `+41.5210` |
| 2024-12 | `-63.1826` | `-120.3754` | `-57.1928` |

The regime dependence is strong: 2024-10/11 make the side-penalty path look useful, but 2024-04/05/12 are large failures.

## Stateful Risk OOF

Walk-forward stress examples:

| item | value |
|---|---:|
| rows | `926` |
| months | `10` |
| profiled months | `8` |
| stress flag count | `93` |
| target mean | `-0.1076` |
| stress-adjusted mean | `-0.4196` |

Stateful risk OOF:

| item | value |
|---|---:|
| prediction rows | `238,868` |
| OOF months | `2024-05..2024-12` |
| candidate count | `736` |
| target prevalence | `0.2717` |
| predicted mean | `0.1400` |
| bias | `-0.1318` |
| brier | `0.2019` |
| AUC | `0.6689` |

The model has rank signal, but probability is under-calibrated. This is consistent with earlier stateful-risk behavior: useful as a risk feature, not enough as a direct policy selector.

## OOF Fixed Comparison

Evaluation months: `2024-05..2024-12`.

| policy | trades | total PnL | worst month | max DD | forced | long PnL | short PnL | direction error | EV over realized |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| risk0 no-side | `332` | `-141.8816` | `-81.0202` | `109.1586` | `2` | `+6.5628` | `-148.4444` | `0.4669` | `19.2348` |
| risk0 side-penalty | `736` | `-32.7828` | `-127.6350` | `152.3730` | `2` | `+36.8856` | `-69.6684` | `0.4443` | `15.4806` |
| risk5 side-penalty | `626` | `-10.4618` | `-127.6350` | `142.8090` | `2` | `+12.1086` | `-22.5704` | `0.4585` | `16.0841` |
| source p10/replm10 | `599` | `-3.1736` | `-107.9646` | `123.1386` | `2` | `+24.6224` | `-27.7960` | `0.4591` | `16.2584` |

Monthly PnL:

| month | no-side risk0 | side risk0 | side risk5 | source p10/replm10 |
|---|---:|---:|---:|---:|
| 2024-05 | `-40.6918` | `-127.6350` | `-127.6350` | `-107.9646` |
| 2024-06 | `-3.3658` | `-28.0244` | `-20.3262` | `-13.8766` |
| 2024-07 | `-28.7832` | `+12.6224` | `-11.9352` | `+18.1632` |
| 2024-08 | `-81.0202` | `-108.4514` | `-75.0936` | `-82.9640` |
| 2024-09 | `-76.0666` | `+22.7178` | `+43.2232` | `+28.7038` |
| 2024-10 | `-21.0610` | `+102.5526` | `-4.5126` | `-8.4240` |
| 2024-11 | `+172.2896` | `+213.8106` | `+186.2098` | `+187.2742` |
| 2024-12 | `-63.1826` | `-120.3754` | `-0.3922` | `-24.0856` |

Source p10/replm10 is the best of this comparison, but it is still slightly negative and relies heavily on `2024-11`. `2024-05` and `2024-08` remain unresolved.

## Decision

No standard policy is promoted.

The full chronological 2024 protocol resolves the artifact issue from 00206, but it weakens the practical conclusion: when prediction family is held constant and OOF months are aligned, the best policy still fails to beat NoTrade. The improvement path is therefore not another side hook on this same signal family.

Keep as diagnostics:

- source p10/replm10 as the current best 2024 OOF comparison policy, not a standard policy
- risk5 side-penalty as a risk-feature sensitivity check
- side-penalty delta examples for stateful-risk target generation
- full 2024 hybrid prediction as the canonical 2024 chronological artifact

Next:

1. Treat entry EV calibration as the main weakness. Validation selected `0` HGB rows after calibration, yet test selected thousands, so admission thresholds and EV scale are not stable.
2. Compare policies against NoTrade first, not only against each other. Any candidate with negative total PnL remains diagnostic.
3. Before adding more side-specific hooks, build a calibration/admission layer that reduces overestimated entry EV and checks month/regime support.
4. If `gap0/gap5/budget0` is tested on this full 2024 family, frame it as a diagnostic stress test, not an adoption path, unless it beats NoTrade with acceptable worst/DD.
5. Consider broader training history and purged walk-forward folds for entry EV, because 2023-only training did not generalize strongly to 2024 entry selection.

## Verification

- HGB train: OK
- MLP train: OK, expected `max_iter=40` convergence warning
- hybrid merge: OK, missing MLP exit rows `0`, forced target missing `0`
- raw 10m fixed backtests: OK
- side-penalty delta examples: OK
- walk-forward stress examples: OK
- stateful risk OOF: OK
- OOF fixed comparisons: OK
