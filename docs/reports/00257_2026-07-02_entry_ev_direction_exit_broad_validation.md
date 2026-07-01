# Entry EV Direction Exit Broad Validation

日時: 2026-07-02 01:35 JST
更新日時: 2026-07-02 01:35 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00256の次アクションとして、fixed 2025 stressではなく、より広い月範囲へdirection / exit residual target診断を適用した。
- 対象は既存predictionでカバーできる `cal2024: 2024-01..02`, `fresh2024: 2024-03..12`, `refit2025: 2025-01..12`。
- `side_prior_pressure_s0p5` と `side_prior_pressure_s1` の2種類で同一候補を再生し、trade CSVを保存してenrichmentした。
- s0.5は215 selected trade rows、s1は108 rows。これは広域diagnosticであり、final holdoutではない。
- s0.5では `confidence_exit -> same_side_large_regret_loss_target` が chronological pooled AUC `0.6919`, `confidence_exit -> large_exit_regret_loss_target` が `0.6548`。
- s1でも `side_context -> same_side_large_regret_loss_target` が pooled AUC `0.7008`, `confidence_exit -> large_exit_regret_loss_target` が `0.6677`。
- pointwiseでは `selected_loss_first_prob` が両方で強く、same-side large regret AUCは s0.5 `0.7040`, s1 `0.8100`。
- 一方、direction error / profit-barrier missのchronological pooled AUCは弱い。s0.5で direction best `0.4569`, profit-barrier miss best `0.4758`; s1も direction best `0.4087`, profit-barrier miss best `0.4638`。
- 判断: broad validation diagnosticはaccepted。loss-first / confidence-exit / side-contextはexit-regret系auxiliary feature候補として昇格。direction/profit-barrier missは現bucketではまだpolicy featureにしない。標準policyはNoTrade。

## Artifacts

s0.5:

- Broad policy replay:
  - `data/reports/backtests/20260701_163114_20260702_entry_ev_side_prior_pressure_s0p5_broad_validation_trades_for_direction_exit_s1/`
- Enriched trades:
  - `data/reports/backtests/20260701_163245_20260702_entry_ev_side_prior_pressure_s0p5_broad_validation_trade_enrichment_for_direction_exit_s1/`
- Target diagnostic:
  - `data/reports/backtests/20260701_163300_20260702_entry_ev_direction_exit_residual_target_s0p5_broad_validation_s1/`

s1:

- Broad policy replay:
  - `data/reports/backtests/20260701_163328_20260702_entry_ev_side_prior_pressure_s1_broad_validation_trades_for_direction_exit_s1/`
- Enriched trades:
  - `data/reports/backtests/20260701_163453_20260702_entry_ev_side_prior_pressure_s1_broad_validation_trade_enrichment_for_direction_exit_s1/`
- Target diagnostic:
  - `data/reports/backtests/20260701_163503_20260702_entry_ev_direction_exit_residual_target_s1_broad_validation_s1/`

## Validation Span

```text
cal2024  : 2024-01..2024-02
fresh2024: 2024-03..2024-12
refit2025: 2025-01..2025-12
```

Important caveat:

- This uses available historical predictions to widen target support.
- It is not a new final test set.
- Any policy hook derived from these rows must still be replayed with prior-only / walk-forward rules and NoTrade-first selection.

## Policy Replay Snapshot

Overall broad replay:

| score | candidate | total PnL | worst family/role | trades | max DD | max side share |
|---|---|---:|---:|---:|---:|---:|
| s0.5 | q99 floor10 | `+1.0804` | `-7.4880` | `10` | `7.4880` | `0.7000` |
| s0.5 | q95 floor10 | `-39.7360` | `-28.4760` | `23` | `37.6890` | `0.6522` |
| s0.5 | q99 floor5 | `-142.3776` | `-162.1992` | `70` | `162.1992` | `0.6000` |
| s0.5 | q95 floor5 | `-84.1626` | `-233.2854` | `112` | `233.2854` | `0.6071` |
| s1 | q99 floor10 | `+1.0804` | `-7.4880` | `10` | `7.4880` | `0.7000` |
| s1 | q95 floor10 | `-18.7480` | `-9.4600` | `22` | `37.6890` | `0.6364` |
| s1 | q99 floor5 | `-46.3822` | `-57.2272` | `28` | `118.8072` | `0.7143` |
| s1 | q95 floor5 | `-68.6362` | `-64.3552` | `48` | `125.9352` | `0.7500` |

Reading:

- s1 reduces exposure and refit2025 loss versus s0.5.
- s1 also removes nearly all fresh2024 trades; this can hide failure rather than prove robustness.
- q99/q95 floor10 are near-flat because they barely trade.
- None of these is a standard policy candidate against NoTrade-first constraints.

## Target Support

Key targets:

| score | rows | target | count | rate | target PnL | false PnL |
|---|---:|---|---:|---:|---:|---:|
| s0.5 | `215` | `profit_barrier_miss_loss_target` | `97` | `0.4512` | `-1504.9716` | `+1239.7758` |
| s0.5 | `215` | `direction_error_loss_target` | `88` | `0.4093` | `-1421.8440` | `+1156.6482` |
| s0.5 | `215` | `large_exit_regret_loss_target` | `63` | `0.2930` | `-1375.6944` | `+1110.4986` |
| s0.5 | `215` | `same_side_missed_loss_target` | `90` | `0.4186` | `-976.6524` | `+711.4566` |
| s0.5 | `215` | `same_side_large_regret_loss_target` | `54` | `0.2512` | `-868.3380` | `+603.1422` |
| s1 | `108` | `profit_barrier_miss_loss_target` | `47` | `0.4352` | `-648.9432` | `+516.2572` |
| s1 | `108` | `large_exit_regret_loss_target` | `32` | `0.2963` | `-616.1220` | `+483.4360` |
| s1 | `108` | `direction_error_loss_target` | `42` | `0.3889` | `-585.9936` | `+453.3076` |
| s1 | `108` | `same_side_large_regret_loss_target` | `26` | `0.2407` | `-307.8276` | `+175.1416` |

Reading:

- broad validation provides enough rows to distinguish target families.
- Direction/profit-barrier miss cover the largest loss pools.
- Exit-regret targets are smaller but have clearer loss-first signal.

## Pointwise Scores

Top pointwise diagnostics:

| score | target | feature | predicted rows | AUC | Brier |
|---|---|---|---:|---:|---:|
| s0.5 | `same_side_large_regret_loss_target` | `selected_loss_first_prob` | `215` | `0.7040` | `0.1855` |
| s0.5 | `same_side_missed_loss_target` | `selected_loss_first_prob` | `215` | `0.6830` | `0.2230` |
| s0.5 | `large_exit_regret_loss_target` | `selected_loss_first_prob` | `215` | `0.6672` | `0.1986` |
| s0.5 | `direction_error_loss_target` | `selected_ev_overestimate_risk` | `158` | `0.5750` | `0.2460` |
| s1 | `same_side_large_regret_loss_target` | `selected_loss_first_prob` | `108` | `0.8100` | `0.1666` |
| s1 | `large_exit_regret_loss_target` | `selected_loss_first_prob` | `108` | `0.7183` | `0.1917` |
| s1 | `same_side_missed_loss_target` | `selected_loss_first_prob` | `108` | `0.6972` | `0.2274` |
| s1 | `hold_too_long_loss_target` | `pred_side_confidence_gap` | `108` | `0.6247` | `0.1290` |

Reading:

- `selected_loss_first_prob` is robust across s0.5 and s1 for exit-regret/capture targets.
- EV-overestimate risk does not dominate in the broad setting.
- Direction error is not solved by loss-first; it likely needs side/context/regime or sequence features.

## Chronological Calibration

Best row per target:

| score | target | best spec | predicted rows | pooled AUC | mean AUC | no-prior |
|---|---|---|---:|---:|---:|---:|
| s0.5 | `same_side_large_regret_loss_target` | `confidence_exit` | `158` | `0.6919` | `0.7239` | `0.2651` |
| s0.5 | `large_exit_regret_loss_target` | `confidence_exit` | `158` | `0.6548` | `0.6839` | `0.2651` |
| s0.5 | `same_side_missed_loss_target` | `profit_exit` | `158` | `0.5243` | `0.6266` | `0.2651` |
| s0.5 | `hold_too_long_loss_target` | `context_confidence` | `158` | `0.5194` | `0.5256` | `0.2651` |
| s0.5 | `direction_error_loss_target` | `profit_exit` | `158` | `0.4569` | `0.5376` | `0.2651` |
| s1 | `same_side_large_regret_loss_target` | `side_context` | `51` | `0.7008` | `0.6940` | `0.5278` |
| s1 | `large_exit_regret_loss_target` | `confidence_exit` | `51` | `0.6677` | `0.5833` | `0.5278` |
| s1 | `same_side_missed_loss_target` | `profit_exit` | `51` | `0.4338` | `0.4385` | `0.5278` |
| s1 | `direction_error_loss_target` | `side_context` | `51` | `0.4087` | `0.3767` | `0.5278` |

Reading:

- Exit-regret系では broad validationでも chronological signalが残る。
- s1はtrade countが減るため no-prior `0.5278` と高く、bucket calibration supportはs0.5より弱い。
- Direction/profit-barrier missは現bucket specsではchronologicalに弱い。

## Decision

Accepted:

- Broad validation replay/enrichment/target diagnostic workflow.
- `selected_loss_first_prob` as a robust feature candidate for exit-regret/capture residual targets.
- `confidence_exit` and `side_context` as low-capacity calibration specs for `large_exit_regret` and `same_side_large_regret`.
- s1 as an exposure-reduction diagnostic baseline.

Not accepted:

- Any broad-validation-derived hard block.
- s1 as a standard policy; it reduces exposure but still fails NoTrade-first robustness.
- Direction/profit-barrier miss bucket calibration as a policy feature.
- Treating q99/q95 floor10 near-flat result as profitable edge; trade support is too thin.

Standard policy remains NoTrade.

## Next

1. Build a prediction-row auxiliary input for exit-regret risk using only prior-month rows and the low-capacity `confidence_exit` / `side_context` specs.
2. First use it as a candidate-level selector/ranking feature, not a direct score penalty.
3. Compare against NoTrade, s0.5/s1 broad baselines, fixed 2025 stress, worst month, max DD, side share, and trade count.
4. For direction/profit-barrier miss, avoid the current bucket specs and try richer but still low-capacity features: side/context regime, side confidence, recent side drift, and sequence-derived direction stability.
5. Do not merge direction and exit into `direction_or_exit_loss_target`; it remains too broad and collapses to realized loss.

## Verification

- s0.5 broad policy replay with `--write-trades`: OK
- s0.5 multi-family enrichment: OK, prediction match share `1.0`
- s0.5 direction/exit residual diagnostic: OK
- s1 broad policy replay with `--write-trades`: OK
- s1 multi-family enrichment: OK, prediction match share `1.0`
- s1 direction/exit residual diagnostic: OK
- `python3 -m unittest tests.test_docs_reports`: OK
- `git diff --check`: OK
