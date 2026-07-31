# Entry EV Direction Exit Fixed 2025 Stress

日時: 2026-07-02 01:24 JST
更新日時: 2026-07-02 01:24 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00255のdirection / exit residual targetを、fixed 2025-03..12の `side_prior_pressure_s0p5` stress tradesへ適用した。
- これは新しいvalidation証拠ではなく、00244で崩れた固定2025期間の残差をtarget診断へ広げる圧力テストである。
- inputは `refit2025` の q95/q99 floor5 stress trades、合計 133 rows。
- q95は 80 trades / total `-160.8606`、q99は 53 trades / total `-177.3790`。
- no-prior shareは00255 validationの `0.7403` から fixed stressでは `0.1053` へ下がり、bucket support問題は大きく改善した。
- ただし chronological calibration のbest pooled AUCは `side_context -> same_side_large_regret_loss_target 0.5922`、`profit_exit -> large_exit_regret_loss_target 0.5621` 程度で、policy化には弱い。
- pointwiseでは `selected_loss_first_prob` が same-side / low-capture / exit-regret系targetに強く、`same_side_missed_loss_target` と `low_capture_loss_target` で AUC `0.7325`、`same_side_large_regret_loss_target` で `0.7182`。
- 00255では `selected_ev_overestimate_risk` が目立ったが、fixed stressでは loss-first 系が上に来た。これはfeature候補のwindow依存を示す。
- 判断: fixed 2025 stress diagnosticはaccepted。標準policyはNoTradeのまま。loss-first / exit-capture featureを次の広いchronological validationへ入れる価値はあるが、hard blockにはしない。

## Artifacts

- Enrichment artifact:
  - `data/reports/backtests/20260701_162239_20260702_entry_ev_side_prior_pressure_s0p5_fixed2025_trade_enrichment_for_direction_exit_s1/`
- Diagnostic artifact:
  - `data/reports/backtests/20260701_162254_20260702_entry_ev_direction_exit_residual_target_fixed2025_stress_s1/`
- Scripts:
  - `scripts/experiments/entry_ev_multifamily_policy_trade_enrichment.py`
  - `scripts/experiments/entry_ev_direction_exit_residual_target_diagnostics.py`

## Input

Fixed 2025 stress source:

```text
data/reports/backtests/20260701_131856_20260701_entry_ev_side_prior_pressure_s0p5_fixed2025_03_12_trades_s1
```

Prediction input:

```text
data/reports/backtests/20260630_232706_20260701_entry_ev_side_prior_pressure_policy_inputs_s1/enriched_predictions/refit2025_predictions_side_prior_pressure.parquet
```

This is a fixed-period stress run, not an out-of-sample validation selector result.

## Stress Trade Summary

| candidate | trades | total PnL | loss PnL | win PnL | direction error | profit miss | forced exit | exit regret sum | avg hold |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| q95 floor5 | `80` | `-160.8606` | `-811.8936` | `+651.0330` | `0.5125` | `0.5250` | `0.1375` | `2884.3816` | `695.31m` |
| q99 floor5 | `53` | `-177.3790` | `-631.9560` | `+454.5770` | `0.5283` | `0.6038` | `0.1887` | `1964.6050` | `875.62m` |

Reading:

- Direction error rate is near `0.52` in both q95 and q99.
- Profit barrier miss is also high, especially q99 `0.6038`.
- Forced exit alone is not the dominant failure.
- Exit regret is large, but many losses are direction/capture mixed rather than pure late-exit.

## Target Support

133 stress rows:

| target | count | rate | target PnL | false PnL | avg target PnL |
|---|---:|---:|---:|---:|---:|
| `realized_loss_target` | `75` | `0.5639` | `-1443.8496` | `+1105.6100` | `-19.2513` |
| `profit_barrier_miss_loss_target` | `66` | `0.4962` | `-1381.9356` | `+1043.6960` | `-20.9384` |
| `direction_error_loss_target` | `57` | `0.4286` | `-1298.5440` | `+960.3044` | `-22.7815` |
| `large_exit_regret_loss_target` | `51` | `0.3835` | `-1281.4632` | `+943.2236` | `-25.1267` |
| `hold_too_long_loss_target` | `29` | `0.2180` | `-868.0464` | `+529.8068` | `-29.9326` |
| `same_side_missed_loss_target` | `57` | `0.4286` | `-855.4932` | `+517.2536` | `-15.0087` |
| `same_side_large_regret_loss_target` | `42` | `0.3158` | `-774.1068` | `+435.8672` | `-18.4311` |

Reading:

- 00255の77-row validationよりtarget supportは増えた。
- `direction_or_exit_loss_target` はここでも `realized_loss_target` と同一になり、training labelとして広すぎる。
- `profit_barrier_miss_loss_target`, `direction_error_loss_target`, `large_exit_regret_loss_target` は損失PnLの大部分を覆う。
- `same_side_missed_loss_target` は同方向にoracle edgeがあるのに取り逃がした損失を拾うため、exit/capture head向き。

## Pointwise Scores

Top pointwise diagnostics:

| target | score | predicted rows | AUC | Brier | target PnL |
|---|---|---:|---:|---:|---:|
| `same_side_missed_loss_target` | `selected_loss_first_prob` | `133` | `0.7325` | `0.2166` | `-855.4932` |
| `low_capture_loss_target` | `selected_loss_first_prob` | `133` | `0.7325` | `0.2166` | `-855.4932` |
| `same_side_large_regret_loss_target` | `selected_loss_first_prob` | `133` | `0.7182` | `0.1987` | `-774.1068` |
| `large_exit_regret_loss_target` | `selected_loss_first_prob` | `133` | `0.6607` | `0.2197` | `-1281.4632` |
| `realized_loss_target` | `selected_loss_first_prob` | `133` | `0.6531` | `0.2611` | `-1443.8496` |
| `profit_barrier_miss_loss_target` | `selected_loss_first_prob` | `133` | `0.6223` | `0.2490` | `-1381.9356` |
| `direction_error_loss_target` | `selected_loss_first_prob` | `133` | `0.5965` | `0.2385` | `-1298.5440` |
| `hold_too_long_loss_target` | `selected_ev_overestimate_risk` | `133` | `0.5836` | `0.2216` | `-868.0464` |

Reading:

- fixed stressでは `selected_loss_first_prob` が、same-side missed / low-capture / large-exit-regretで一貫して上位。
- 00255 validationで強かった `selected_ev_overestimate_risk` は、fixed stressでは方向targetに AUC `0.5684` 程度まで落ちる。
- したがって EV-overestimate単独headに寄せすぎず、loss-first / profit-barrier / exit-hold featureを併用する必要がある。

## Chronological Calibration

Best row per target:

| target | best spec | target count | predicted rows | pooled AUC | mean AUC | bucket share | global share | no-prior share |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `same_side_large_regret_loss_target` | `side_context` | `42` | `119` | `0.5922` | `0.6054` | `0.3158` | `0.5789` | `0.1053` |
| `large_exit_regret_loss_target` | `profit_exit` | `51` | `119` | `0.5621` | `0.6780` | `0.3609` | `0.5338` | `0.1053` |
| `hold_too_long_loss_target` | `profit_exit` | `29` | `119` | `0.5030` | `0.4267` | `0.3609` | `0.5338` | `0.1053` |
| `same_side_missed_loss_target` | `profit_exit` | `57` | `119` | `0.4986` | `0.6360` | `0.3609` | `0.5338` | `0.1053` |
| `direction_error_loss_target` | `ev_exit` | `57` | `119` | `0.4332` | `0.5899` | `0.5038` | `0.3910` | `0.1053` |
| `profit_barrier_miss_loss_target` | `ev_exit` | `66` | `119` | `0.4202` | `0.5101` | `0.5038` | `0.3910` | `0.1053` |

Reading:

- no-prior share is now low enough to diagnose, but pooled AUC is still weak.
- The best target/spec combination is only `0.5922`; this is not enough for a hard selector.
- `mean_auc` can look better than pooled AUC because month support and class balance differ. Policy decisions should not use mean AUC alone.
- `direction_error_loss_target` and `profit_barrier_miss_loss_target` are not captured well by the current chronological bucket specs.

## Decision

Accepted:

- Applying direction/exit residual target diagnostics to fixed 2025 stress trades.
- Using the result as residual failure analysis for 00244/00245, not as validation evidence.
- Treating `selected_loss_first_prob` as a strong feature candidate for exit/capture residual targets.
- Keeping `selected_ev_overestimate_risk` as a feature candidate, but no longer treating it as the dominant signal across windows.

Not accepted:

- Any fixed 2025 stress-derived hard block.
- `direction_or_exit_loss_target` or broad `realized_loss_target` as a training label.
- Chronological bucket calibration from this stress run as policy evidence.
- Further same-window threshold tuning on fixed 2025.

Standard policy remains NoTrade.

## Next

1. Build a wider chronological validation set of enriched trades, not just fixed stress.
2. Add `selected_loss_first_prob`, profit-barrier bucket, exit-hold bucket, and selected EV-overestimate as separate auxiliary target features.
3. Keep direction/profit-barrier miss, same-side missed, large-exit-regret, and hold-too-long as separate targets.
4. Evaluate target heads with walk-forward / purged-style chronology before any policy replay.
5. If a policy hook is attempted later, use NoTrade-first selector, role/month support, worst-month floor, max DD, and trade-count floor.

## Verification

- fixed 2025 multi-family enrichment run: OK
- fixed 2025 direction/exit residual diagnostic run: OK
- `python3 -m unittest tests.test_docs_reports`: OK
- `git diff --check`: OK
