# Entry EV Composite Target Decomposition

日時: 2026-06-30 23:56 JST
更新日時: 2026-06-30 23:56 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00238の反省に沿って、composite gateを増やすのではなく、trade単位で model-time feature と training/evaluation target に分解する `scripts/experiments/entry_ev_composite_target_decomposition.py` を追加した。
- 出力は `component_trade_targets.csv`, candidate/role/month summary, feature bucket summary, target overlap summary。
- 対象は00235/00238と同じ selected trades 115件、4 candidates、3 roles、6 months。
- 各candidateの `composite_failure_target_rate` は `0.8621..0.9130` と高い。ただし、targetが立っても利益になるoverlapがあり、hard blockに戻す根拠にはならない。
- `none` target overlapは 14 trades / `+176.8770`。一方、direction + exit + EV overestimate + realized lossが重なるoverlapは 11 trades / `-96.4764`、direction + large exit regret + EV overestimate + realized lossは 8 trades / `-146.2824`。
- 判断: target decompositionはaccepted。次はこのframeを使って、target別の低容量classifier/regressor、downside-weighted dense target、rank/selector featureへ接続する。

## Artifacts

- Script: `scripts/experiments/entry_ev_composite_target_decomposition.py`
- Test: `tests/test_entry_ev_composite_target_decomposition.py`
- Diagnostic artifact:
  - `data/reports/backtests/20260630_145606_20260630_entry_ev_composite_target_decomposition_s1/`
- Input:
  - `data/reports/backtests/20260630_101914_20260630_entry_ev_side_balance_downside_interaction_s1/enriched_side_balance_downside_trades.csv`

## Method

Model-time feature columns are prior/context or prediction-time values:

```text
prior_trade_count
prior_month_count
prior_downside_support_weight
prior_downside_risk_score
side_balance_signed_drift_for_trade
side_balance_abs_signed_drift_for_trade
side_balance_downside_interaction_score
selected_side_overrepresented_feature
selected_side_underrepresented_feature
missing_prior_support_feature
low_prior_support_feature
prior_zero_feature
feature_pressure_score
support_gap_feature
```

Training/evaluation targets use realized labels:

```text
direction_side_inversion_target
large_exit_regret_target
low_exit_capture_target
exit_capture_failure_target
executable_ev_overestimate_target
realized_loss_target
composite_failure_target
```

Definitions:

```text
missing_prior_support = prior_trade_count <= 0 or support_weight <= 0
low_prior_support = support_weight < 0.10
large_exit_regret = exit_regret >= 10
low_exit_capture = actual_taken_best_adjusted_pnl >= 5
                   and max(adjusted_pnl, 0) / actual_taken_best_adjusted_pnl <= 0.50
executable_ev_overestimate = ev_overestimate_vs_realized >= 10
composite_failure = OR(component targets + realized_loss)
```

`composite_failure_target` is not a policy blocker. It is a multi-target activity flag showing where at least one training target fires.

## Candidate Summary

| candidate | trades | total | prior zero | missing support | pressure | direction | exit capture | EV overestimate | composite target |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| q95 floor10 | `23` | `+15.5736` | `0.9130` | `0.9130` | `0.2009` | `0.6087` | `0.6957` | `0.6087` | `0.9130` |
| q95 floor5 | `53` | `+14.6138` | `0.6226` | `0.6226` | `0.3116` | `0.5660` | `0.6981` | `0.4151` | `0.8679` |
| q99 floor10 | `10` | `+1.1920` | `0.9000` | `0.9000` | `0.2040` | `0.5000` | `0.8000` | `0.7000` | `0.9000` |
| q99 floor5 | `29` | `-10.2286` | `0.6207` | `0.6207` | `0.3001` | `0.5862` | `0.7241` | `0.4483` | `0.8621` |

## Role Findings

| candidate | role | trades | total | missing support | pressure | direction | exit capture | EV overestimate | loss | composite |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| q95 floor10 | cal2024 | `21` | `-11.2600` | `1.0000` | `0.1500` | `0.6667` | `0.6667` | `0.6190` | `0.5238` | `0.9048` |
| q95 floor10 | refit2025 | `2` | `+26.8336` | `0.0000` | `0.7355` | `0.0000` | `1.0000` | `0.5000` | `0.5000` | `1.0000` |
| q95 floor5 | cal2024 | `26` | `+2.8654` | `0.8846` | `0.1696` | `0.5769` | `0.5769` | `0.5385` | `0.5000` | `0.7692` |
| q95 floor5 | fresh2024 | `8` | `-82.2428` | `0.3750` | `0.4213` | `0.8750` | `0.7500` | `0.3750` | `0.7500` | `1.0000` |
| q95 floor5 | refit2025 | `19` | `+93.9912` | `0.3684` | `0.4596` | `0.4211` | `0.8421` | `0.2632` | `0.3684` | `0.9474` |
| q99 floor5 | fresh2024 | `6` | `-38.3550` | `0.3333` | `0.4666` | `0.8333` | `0.6667` | `0.1667` | `0.6667` | `1.0000` |

Important reading:

- Fresh failures have high direction target rates (`0.8333..0.8750`) and high loss rates.
- Refit winners can still have high exit-capture target rates (`0.8000..0.8421`), so exit-capture target is an improvement target, not a no-trade blocker.
- Missing support is common even in profitable rows: the `none` overlap has prior zero share `0.7143` and total `+176.8770`. Missing support should be an uncertainty feature, not an automatic rejection.

## Target Overlap Findings

| overlap | trades | total | win rate | prior zero | pressure |
|---|---:|---:|---:|---:|---:|
| none | `14` | `+176.8770` | `1.0000` | `0.7143` | `0.1986` |
| large exit + low capture + EV overestimate + realized loss | `16` | `-51.1200` | `0.0000` | `0.6250` | `0.3159` |
| direction + large exit + low capture + EV overestimate + realized loss | `11` | `-96.4764` | `0.0000` | `0.8182` | `0.2490` |
| direction + large exit + EV overestimate + realized loss | `8` | `-146.2824` | `0.0000` | `0.8750` | `0.1838` |
| large exit + low capture only | `13` | `+72.4700` | `1.0000` | `0.4615` | `0.4054` |
| direction + low capture only | `10` | `+28.4200` | `1.0000` | `0.8000` | `0.1840` |

The negative overlaps are concentrated when realized loss and EV overestimate combine with direction and/or exit targets. Component targets without realized loss can describe missed upside or imperfect execution while still being profitable.

## Decision

Accepted:

- Component target decomposition script.
- Explicit separation of model-time features and realized training/evaluation targets.
- `component_trade_targets.csv` as the next input for target-specific modeling.
- Target overlap summary as a guard against converting targets back into hard blockers.

Not accepted:

- Using `composite_failure_target` as a single binary no-trade label.
- Treating missing support as an automatic block.
- Treating exit-capture target alone as a negative trade label.

Standard policy remains NoTrade.

## Next

1. Train or diagnose low-capacity target heads separately: direction-side inversion, exit capture, executable EV overestimate, realized loss.
2. Use missing-support and pressure features as explanatory variables, not gate-only blockers.
3. Add target-specific calibration summary by chronological month/role before any new policy use.
4. Prefer multi-task or stacked target design over compressing back to long/short/stay-flat.

## Verification

- `python3 -m py_compile scripts/experiments/entry_ev_composite_target_decomposition.py tests/test_entry_ev_composite_target_decomposition.py`: OK
- `python3 -m unittest tests.test_entry_ev_composite_target_decomposition`: OK
- Component decomposition diagnostic run: OK
