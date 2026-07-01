# Entry EV Exit Shortening Target Diagnostics

日時: 2026-07-01 23:49 JST
更新日時: 2026-07-01 23:49 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00250の次アクションとして、exit capture failureをより狭いexit timing targetへ分解する `scripts/experiments/entry_ev_exit_shortening_target_diagnostics.py` を追加した。
- 入力は 00250 の `residual_enriched_trades.csv`。q95/q99両候補のselected trades 123件、および q99単体 50件で診断した。
- target定義には実現後情報を使うが、chronological OOF calibrationのgroup featureには decision-time で見える regime、予測hold、exit確率、loss-first確率、pred fixed PnL slope、direction risk bucket、EV overestimate bucket だけを使った。
- q99では `hold_too_long_loss_target` が 11 trades / target PnL `-322.7892`、`hold_prediction_too_long_loss_target` が 13 trades / `-353.0376` を覆う。exitを短縮すべき残差は確かに存在する。
- ただし、狭い `exit_shortening_residual_target` は q99で 5 trades / `-125.9172` に縮む。損失説明としては鋭いが、学習targetとしてはsupport不足。
- q99 chronological OOFでは、`hold_too_long_loss_target` の最良 pooled AUC は `exit_risk 0.5016`、`exit_shortening_residual_target` の最良 pooled AUC は `exit_plan 0.4487`。現featureだけでは標準化できる予測headとは言えない。
- 例外的に `forced_exit_loss_target` は q99で 4 trades / `-152.5164` と少数ながら、`exit_risk` pooled AUC `0.7561`、`ev_exit` `0.6870`。forced-exit loss は独立targetとして次に試す価値がある。
- 判断: exit-shortening target generationとOOF calibrationはaccepted diagnostics。`hold_too_long` はtarget候補として残すが、現featureのままpolicy scoreへ入れない。次は forced-exit loss と late-exit-regret を別head化し、stateful replayで「exit shortener」ではなく「entry suppression / hold cap adjustment」として検証する。

## Artifacts

- Script: `scripts/experiments/entry_ev_exit_shortening_target_diagnostics.py`
- Test: `tests/test_entry_ev_exit_shortening_target_diagnostics.py`
- Input residual trades:
  - `data/reports/backtests/20260701_143603_20260701_entry_ev_direction_s0p1_residual_loss_diagnostics_s1/residual_enriched_trades.csv`
- All q95/q99 diagnostic:
  - `data/reports/backtests/20260701_144816_20260701_entry_ev_exit_shortening_target_diagnostics_s1/`
- q99-only diagnostic:
  - `data/reports/backtests/20260701_144830_20260701_entry_ev_exit_shortening_target_diagnostics_q99_s1/`

## Targets

| target | definition |
|---|---|
| `hold_too_long_loss_target` | realized loss, oracle same-side hold at least 30 minutes shorter, and positive exit regret |
| `exit_shortening_residual_target` | `hold_too_long_loss_target`, oracle edge >= 5, and exit regret >= 20 |
| `hold_prediction_too_long_loss_target` | realized loss, selected predicted MLP exit hold at least 30 minutes longer than actual oracle hold, and positive exit regret |
| `same_side_missed_loss_target` | realized loss while same-side oracle edge >= 5 |
| `low_capture_loss_target` | same-side missed loss and realized/oracle capture ratio <= 0.25 |
| `late_exit_regret_loss_target` | realized loss and exit regret >= 20 |
| `forced_exit_loss_target` | forced exit and realized loss |
| `profit_barrier_miss_loss_target` | actual taken-side profit barrier missed and realized loss |
| `large_exit_shortening_loss_target` | large loss and `exit_shortening_residual_target` |

Calibration specs deliberately avoid actual/oracle columns:

| spec | features |
|---|---|
| `side_context` | direction, combined regime, session regime |
| `exit_plan` | direction, predicted exit hold bucket, predicted hold gap bucket, time-exit probability bucket |
| `exit_risk` | direction, loss-first probability bucket, predicted profit-barrier bucket, predicted fixed 60m to 720m slope bucket |
| `direction_exit` | direction, direction-risk bucket, predicted exit hold bucket, session regime |
| `ev_exit` | direction, EV-overestimate bucket, predicted fixed slope bucket, predicted 720m PnL bucket |

## q99 Target Coverage

| target | count | rate | target PnL | non-target PnL |
|---|---:|---:|---:|---:|
| `profit_barrier_miss_loss_target` | `27` | `0.5400` | `-530.6412` | `+383.3098` |
| `late_exit_regret_loss_target` | `20` | `0.4000` | `-495.1092` | `+347.7778` |
| `same_side_missed_loss_target` | `24` | `0.4800` | `-360.1236` | `+212.7922` |
| `low_capture_loss_target` | `24` | `0.4800` | `-360.1236` | `+212.7922` |
| `hold_prediction_too_long_loss_target` | `13` | `0.2600` | `-353.0376` | `+205.7062` |
| `hold_too_long_loss_target` | `11` | `0.2200` | `-322.7892` | `+175.4578` |
| `forced_exit_loss_target` | `4` | `0.0800` | `-152.5164` | `+5.1850` |
| `exit_shortening_residual_target` | `5` | `0.1000` | `-125.9172` | `-21.4142` |
| `large_exit_shortening_loss_target` | `4` | `0.0800` | `-108.7968` | `-38.5346` |

Reading:

- Broad exit labels (`profit_barrier_miss`, `late_exit_regret`, `low_capture`) explain much more loss, but they are too broad for direct hard blocks.
- `hold_too_long` and `hold_prediction_too_long` isolate a meaningful subset. The issue is not whether the failure exists; it is whether it can be predicted before entry.
- The narrow `exit_shortening_residual_target` is cleaner but sparse.

## q99 Chronological OOF

Selected calibration rows:

| target | best spec | pooled AUC | mean AUC | predicted count | bucket share | global share |
|---|---|---:|---:|---:|---:|---:|
| `forced_exit_loss_target` | `exit_risk` | `0.7561` | `0.8571` | `44` | `0.2200` | `0.6600` |
| `forced_exit_loss_target` | `ev_exit` | `0.6870` | `0.8016` | `44` | `0.3000` | `0.5800` |
| `late_exit_regret_loss_target` | `exit_plan` | `0.5484` | `0.6192` | `44` | `0.3600` | `0.5200` |
| `hold_too_long_loss_target` | `exit_risk` | `0.5016` | `0.7242` | `44` | `0.2200` | `0.6600` |
| `hold_prediction_too_long_loss_target` | `exit_risk` | `0.4835` | `0.6701` | `44` | `0.2200` | `0.6600` |
| `exit_shortening_residual_target` | `exit_plan` | `0.4487` | `0.5278` | `44` | `0.3600` | `0.5200` |

Reading:

- Mean AUC can look decent in tiny folds, but pooled AUC is weak for hold/shortening targets.
- Bucket prediction share is low, especially in q99-only (`0.02..0.36` depending on spec). Much of the score falls back to global priors.
- Therefore this is not yet a deployable exit-shortening head.
- `forced_exit_loss_target` is the only exit target with strong pooled AUC, even though support is only four q99 trades.

## q99 Contexts

Worst `hold_too_long_loss_target` contexts:

| side | context | rows | target count | target PnL |
|---|---|---:|---:|---:|
| short | down_normal_vol / london | `2` | `1` | `-77.0520` |
| short | range_normal_vol / london | `5` | `2` | `-62.6448` |
| long | down_normal_vol / rollover | `2` | `2` | `-60.1368` |
| long | range_normal_vol / ny_overlap | `4` | `1` | `-55.9080` |
| short | down_high_vol / ny_late | `1` | `1` | `-23.3556` |

Worst `exit_shortening_residual_target` contexts:

| side | context | rows | target count | target PnL |
|---|---|---:|---:|---:|
| long | down_normal_vol / rollover | `2` | `2` | `-60.1368` |
| short | range_normal_vol / london | `5` | `1` | `-25.3044` |
| short | down_high_vol / ny_late | `1` | `1` | `-23.3556` |
| short | up_low_vol / london | `1` | `1` | `-17.1204` |

Important examples:

- 2025-05 short/down_normal_vol/london: `-77.0520`, forced exit, oracle hold 6m vs realized hold 3485m. It is hold-too-long and forced-exit loss, but not `exit_shortening_residual_target` because same-side oracle edge is negative.
- 2025-10 long/range_normal_vol/ny_overlap: `-55.9080`, hold-too-long and low direction risk. This remains difficult for direction risk and exit shortening alike.
- 2025-04/05 long/down_normal_vol/rollover: two losses, both narrow exit-shortening residuals. This context is a concrete candidate for a future hold-cap adjustment or entry suppression test.

## Decision

Accepted:

- Exit-shortening residual target generation.
- Chronological OOF calibration over decision-time-only feature buckets.
- q99-only and q95/q99 combined diagnostics.

Not accepted:

- Directly adding `hold_too_long` or `exit_shortening_residual` score to policy ranking.
- Using actual/oracle holding gap as a feature.
- Treating broad `profit_barrier_miss` or `low_capture` as hard block labels.

Standard policy remains NoTrade.

## Next

1. Build a forced-exit-loss head because it has the best q99 OOF signal despite sparse support.
2. Test entry suppression or hold-cap adjustment for concrete contexts:
   - `long/down_normal_vol/rollover`
   - `short/range_normal_vol/london`
   - `short/down_high_vol/ny_late`
3. Keep `hold_too_long` as an auxiliary exit label, not a primary selector, unless broader OOF windows improve pooled AUC.
4. Re-run with more months before training a deep model on this target; 50 q99 rows is too small for model selection.

## Verification

- `python3 -m py_compile scripts/experiments/entry_ev_exit_shortening_target_diagnostics.py tests/test_entry_ev_exit_shortening_target_diagnostics.py`: OK
- `python3 -m unittest tests.test_entry_ev_exit_shortening_target_diagnostics`: OK
- q95/q99 chronological OOF diagnostic run: OK
- q99-only chronological OOF diagnostic run: OK
