# Entry EV Rank Refit 2025 Fold

日時: 2026-06-30 13:58 JST
更新日時: 2026-06-30 13:58 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00210の次アクションとして、同じ calibrated entry EV + MLP exit timing + `min_entry_rank` grid を追加chronological model-refit foldへ適用した。
- Foldは train `2024-01..2024-12`, validation `2025-01..2025-02`, test `2025-03..2025-12`。
- validationでは support gateが `entry12/short3/min_rank0.0` を選ぶ。validation total `+209.4234`, worst `+71.1950`, trades `170`, active months `2`。
- しかし固定testでは同rowが total `-1002.1534`, worst `-294.1980`, trades `1147`, max DD `332.4446` へ崩れ、NoTrade `0` に大きく負けた。
- Test hindsight topは `entry14/short9/min_rank0.7` の total `+324.5040`, worst `-38.0640`, trades `17` だが、validationでは取引ゼロのnear-NoTrade診断rowであり、testを見ない限り選べない。
- 判断: 2025-refit foldでは、rank gateの有効性よりも validation設計の弱さが露呈した。2ヶ月validationで高support positiveでも未来10ヶ月のregime変化に耐えない。標準policyはNoTradeのまま。

## Artifacts

- HGB model: `experiments/20260630_045055_policy_combined_side_exit_chrono_2025_03_12`
- MLP exit model: `experiments/20260630_044926_shared_mlp_hgb_split_chrono_2025_03_12`
- Hybrid predictions:
  - `data/reports/modeling/20260630_chrono_hgb_mlp_exit_2025_03_12/predictions_hgb_entry_mlp_exit_2025_valid.parquet`
  - `data/reports/modeling/20260630_chrono_hgb_mlp_exit_2025_03_12/predictions_hgb_entry_mlp_exit_2025_test.parquet`
  - `data/reports/modeling/20260630_chrono_hgb_mlp_exit_2025_03_12/predictions_hgb_entry_mlp_exit_2025_01_12.parquet`
- Validation sweeps: `data/reports/backtests/20260630_entry_evcal_rank_refit2025_validation_calibrated/`
- Selector outputs:
  - `data/reports/backtests/20260630_entry_evcal_rank_refit2025_selector_support10_worst0/20260630_045443_refit2025_support10_worst0`
  - `data/reports/backtests/20260630_entry_evcal_rank_refit2025_selector_min1/20260630_045443_refit2025_min1`
- Fixed test sweeps: `data/reports/backtests/20260630_entry_evcal_rank_refit2025_test_calibrated/`

## Model Diagnostics

Dataset: `data/processed/datasets/xauusd_m1_p1_l1p2_policy_combined`

HGB configは00207/00210と同じ保守設定を維持した。`max_iter=80`, `learning_rate=0.05`, `max_leaf_nodes=15`, `max_depth=4`, `min_samples_leaf=100`, `l2_regularization=0.2`, `max_features=0.8`, `sample_weighting=month_label`, `target_set=policy`。

HGB metrics:

| split | long EV R2 | short EV R2 | long exit R2 | short exit R2 | calibrated side accuracy |
|---|---:|---:|---:|---:|---:|
| validation | `0.0219` | `-0.0304` | `0.3434` | `0.3953` | `0.6517` |
| test | `-0.2772` | `-0.0240` | `0.2158` | `0.2153` | `0.5365` |

MLP exit metrics:

| split | long exit R2 | short exit R2 |
|---|---:|---:|
| validation | `0.3369` | `0.3867` |
| test | `0.2771` | `0.2649` |

Interpretation: exit timingは一定の汎化があるが、entry EVはtestで特にlong側が崩れる。validationのcalibrated side accuracy `0.6517` は、testでは `0.5365` まで落ちた。

## Validation Selection

Validation months: `2025-01, 2025-02`。

| entry | short offset | min rank | validation total | worst | trades | active months | max DD | long PnL | short PnL |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `12` | `3` | `0.0` | `+209.4234` | `+71.1950` | `170` | `2` | `87.4572` | `+165.5018` | `+43.9216` |
| `8` | `6` | `0.0` | `+208.6534` | `+70.4250` | `170` | `2` | `87.4572` | `+165.5018` | `+43.1516` |
| `10` | `3` | `0.0` | `+208.6534` | `+70.4250` | `170` | `2` | `87.4572` | `+165.5018` | `+43.1516` |
| `12` | `3` | `0.5` | `+198.1734` | `+59.3442` | `165` | `2` | `82.3412` | `+154.9918` | `+43.1816` |
| `14` | `9` | `0.0` | `+176.8018` | `+38.5734` | `167` | `2` | `91.9488` | `+169.9418` | `+6.8600` |

Selector outcome:

| gate | selected | validation evidence |
|---|---|---|
| `min_trades=10`, `active_months>=2`, `worst>=0` | `entry12/short3/min_rank0.0` | total `+209.4234`, worst `+71.1950`, trades `170` |
| diagnostic near-NoTrade | `entry14/short9/min_rank0.7` | validation total `0.0000`, trades `0`; diagnostic only |

Unlike 00210, support不足ではない。むしろsupport gateを通った候補が未来で壊れたため、問題は「2ヶ月validationのrepresentativeness」に移った。

## Fixed Test

Test months: `2025-03..2025-12`。validation-selected row:

| entry | short offset | min rank | test total | worst | active months | trades | max DD | long PnL | short PnL |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `12` | `3` | `0.0` | `-1002.1534` | `-294.1980` | `10` | `1147` | `332.4446` | `-424.4576` | `-577.6958` |

Monthly breakdown:

| month | PnL | trades | max DD | long PnL | short PnL | direction error |
|---|---:|---:|---:|---:|---:|---:|
| 2025-03 | `+100.5408` | `84` | `64.8052` | `+133.0168` | `-32.4760` | `0.3571` |
| 2025-04 | `-212.9412` | `144` | `314.7888` | `-128.5420` | `-84.3992` | `0.5208` |
| 2025-05 | `-195.9204` | `127` | `273.6848` | `-133.5518` | `-62.3686` | `0.5039` |
| 2025-06 | `-294.1980` | `104` | `316.7986` | `-179.9420` | `-114.2560` | `0.5577` |
| 2025-07 | `-138.1228` | `100` | `185.5154` | `-127.2828` | `-10.8400` | `0.4800` |
| 2025-08 | `-11.6414` | `84` | `71.7168` | `-17.0022` | `+5.3608` | `0.4167` |
| 2025-09 | `+66.9778` | `100` | `108.5322` | `+132.6052` | `-65.6274` | `0.4200` |
| 2025-10 | `-253.4868` | `135` | `316.8468` | `-128.8592` | `-124.6276` | `0.5185` |
| 2025-11 | `-248.1828` | `138` | `332.4446` | `-82.3438` | `-165.8390` | `0.5362` |
| 2025-12 | `+184.8214` | `131` | `106.5532` | `+107.4442` | `+77.3772` | `0.3893` |

The failure is broad, not one isolated month. Both sides lose over the full test, and four months are below `-190`.

## Test Hindsight

Test-only top rows:

| entry | short offset | min rank | test total | worst | active months | trades | max DD | long PnL | short PnL |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `14` | `9` | `0.7` | `+324.5040` | `-38.0640` | `5` | `17` | `38.0640` | `0.0000` | `+324.5040` |
| `12` | `9` | `0.7` | `+244.8754` | `-54.0240` | `5` | `21` | `54.0240` | `0.0000` | `+244.8754` |
| `8` | `9` | `0.7` | `+235.7858` | `-54.0240` | `5` | `21` | `54.0240` | `0.0000` | `+235.7858` |
| `14` | `9` | `0.6` | `+98.9868` | `-133.6912` | `10` | `113` | `138.0052` | `+33.3250` | `+65.6618` |

`entry14/short9/min_rank0.7` monthly:

| month | PnL | trades | note |
|---|---:|---:|---|
| 2025-03 | `0.0000` | `0` | no trade |
| 2025-04 | `+80.6400` | `3` | short only |
| 2025-05 | `-38.0640` | `2` | short only |
| 2025-06 | `0.0000` | `0` | no trade |
| 2025-07 | `0.0000` | `0` | no trade |
| 2025-08 | `0.0000` | `0` | no trade |
| 2025-09 | `0.0000` | `0` | no trade |
| 2025-10 | `+127.6140` | `7` | short only |
| 2025-11 | `+100.0364` | `3` | short only |
| 2025-12 | `+54.2776` | `2` | short only |

This is useful diagnostically, but cannot be promoted. The row had validation total `0` and no validation trades, so selecting it would be direct test leakage.

## Decision

No standard policy is promoted.

Accepted:

- The refit fold is a valid stress test for the current admission layer.
- The support gate infrastructure is doing what it was asked to do; it picked a high-support validation-positive row.
- The failure shows that `2025-01..02` alone is not a sufficient validation proxy for `2025-03..12`.

Rejected for standard adoption:

- `entry12/short3/min_rank0.0`: validation-selected but test `-1002.1534`.
- `entry12/short3/min_rank0.5`: also collapses at test `-947.1618`.
- `entry14/short9/min_rank0.7`: test-positive but validation had zero trades, so it is hindsight only.

Implication:

The next improvement should not be another threshold tweak on this fold. We need multi-window validation or CPCV/purged walk-forward style selection for entry admission, with regime and side stability constraints. A candidate should clear more than two adjacent validation months before it can override NoTrade.

## Next

1. Build a fold-level admission selector that can evaluate several chronological validation windows before one fixed future test, not only `2 months -> 10 months`.
2. Add selector constraints for side balance, side/regime worst bucket, and validation/test-like trade frequency. Total PnL alone is insufficient.
3. Treat `entry14/short9/min_rank0.7` as a diagnostic clue for high-rank short-only sparse entries, but do not use it as a selected policy.
4. Re-check whether entry EV calibration should be side/regime-specific; global calibration failed to keep the 2025 validation signal stable.
5. Keep NoTrade as the standard fallback until validation across multiple regimes beats `0` with enough support.

## Verification

- HGB train `2024 -> 2025`: OK
- MLP exit train `2024 -> 2025`: OK
- Hybrid prediction merge valid/test: OK, missing MLP exit rows `0`
- Validation rank sweeps `2025-01..02`: OK
- Selector support gate: OK
- Fixed test sweeps `2025-03..12`: OK
- Aggregation check: OK
