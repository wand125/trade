# Entry EV Exit Capture Target Diagnostics

日時: 2026-06-30 17:40 JST
更新日時: 2026-06-30 17:44 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00227の結論を受け、同方向oracle利益余地を実現できないtradeをtarget化する `scripts/experiments/entry_ev_exit_capture_target_diagnostics.py` を追加した。
- targetは `same_side_missed_loss`, `low_exit_capture`, `large_exit_regret`, `exit_capture_failure`。さらに対象月より前の同一 `direction + combined_regime + session_regime` だけから `prior_exit_capture_risk_score` を作る。
- 結論: exit-capture targetは有効な失敗ラベル。validation q95/q99でも fresh q95/720でも failure prevalence は高い。ただし `prior_exit_capture_risk_score` をhard blockに直結すると、fresh q95/720 fixedで大きく利益を削る。
- validation横断では `risk>=0.20` が68 trades / `-23.1116` を拾うが、fresh q95/720 fixedでは同thresholdが77 trades / `+225.3034` を消す。よってhard blockは不採用。
- 標準policyはNoTradeのまま。exit-capture targetは次にexit timing model / realized-executable EV calibration / selector featureへ戻す。

## Artifacts

- Script: `scripts/experiments/entry_ev_exit_capture_target_diagnostics.py`
- Test: `tests/test_entry_ev_exit_capture_target_diagnostics.py`
- Validation q95/q99:
  - `data/reports/backtests/20260630_entry_ev_exit_capture_target_diagnostics/20260630_083912_entry_ev_exit_capture_targets_validation_q95q99/`
- Validation q95/q99 threshold `0.20` sensitivity:
  - `data/reports/backtests/20260630_entry_ev_exit_capture_target_diagnostics/20260630_084006_entry_ev_exit_capture_targets_validation_q95q99_thr020/`
- Fresh q95_floor5 / 720m:
  - `data/reports/backtests/20260630_entry_ev_exit_capture_target_diagnostics/20260630_083924_entry_ev_exit_capture_targets_fresh_q95_720/`
- Fresh q95_floor5 / 720m threshold `0.20` sensitivity:
  - `data/reports/backtests/20260630_entry_ev_exit_capture_target_diagnostics/20260630_084006_entry_ev_exit_capture_targets_fresh_q95_720_thr020/`

## Target Definition

```text
same_side_oracle_edge = actual_taken_best_adjusted_pnl > 0
same_side_missed_loss = adjusted_pnl < 0 and same_side_oracle_edge
exit_capture_ratio   = adjusted_pnl / actual_taken_best_adjusted_pnl
low_exit_capture     = same_side_oracle_edge and exit_capture_ratio < 0.25
large_exit_regret    = exit_regret >= 10
exit_capture_failure = same_side_missed_loss or low_exit_capture or large_exit_regret
```

`prior_exit_capture_risk_score` は対象月より前の同一context実績だけで作る:

```text
support_weight = clip(prior_exit_trade_count / 4, 0, 1)
risk_score = support_weight * (
  0.30 * prior_exit_capture_failure_rate
  + 0.25 * prior_low_exit_capture_rate
  + 0.20 * prior_same_side_missed_loss_rate
  + 0.15 * prior_large_exit_regret_rate
  + 0.10 * max(prior_exit_regret_component, prior_shortfall_component)
)
```

This score is diagnostic. It is not optimized and is not a promotion rule.

## Validation q95/q99

対象: `cal2024_calibration_validation`, `fresh2024_validation`, `refit2025_validation` の q95/q99 floor5/floor10。

| role / candidate | trades | PnL | failure count | failure rate | same-side missed loss | large regret | exit regret sum | prior risk mean |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| refit q99 floor10 | `18` | `-27.9456` | `16` | `0.8889` | `8` | `14` | `388.8138` | `0.1556` |
| refit q99 floor5 | `18` | `-27.9456` | `16` | `0.8889` | `8` | `14` | `388.8138` | `0.1556` |
| refit q95 floor10 | `28` | `-23.6438` | `25` | `0.8929` | `13` | `21` | `572.3960` | `0.1727` |
| refit q95 floor5 | `29` | `-23.2338` | `25` | `0.8621` | `13` | `21` | `572.9860` | `0.1667` |
| fresh q95 floor5 | `38` | `+1.9920` | `32` | `0.8421` | `17` | `29` | `831.8140` | `0.1308` |
| fresh q95 floor10 | `38` | `+3.9784` | `32` | `0.8421` | `16` | `29` | `829.8276` | `0.1308` |
| cal q95 floor5 | `30` | `+15.5444` | `20` | `0.6667` | `14` | `11` | `251.7336` | `0.0260` |
| fresh q99 floor5 | `12` | `+34.2940` | `11` | `0.9167` | `5` | `10` | `252.5360` | `0.0774` |

Interpretation:

- exit-capture failureは、負けroleだけでなく勝っているfresh/calにも多い。
- これはtargetとしては重要だが、failureラベルをそのまま「取引禁止」へ変換すると利益tradeも削る可能性が高い。

## Prior Risk Thresholds

Validation q95/q99:

| threshold | flagged trades | flagged PnL | removal delta | failure precision | failure recall |
|---|---:|---:|---:|---:|---:|
| `>=0.20` | `68` | `-23.1116` | `+23.1116` | `0.9118` | `0.2731` |
| `>=0.25` | `42` | `+62.7204` | `-62.7204` | `0.9048` | `0.1674` |
| `>=0.50` | `4` | `-13.0560` | `+13.0560` | `1.0000` | `0.0176` |

Role split shows why this is not stable:

| role / candidate | threshold | flagged trades | flagged PnL | removal delta | recall |
|---|---:|---:|---:|---:|---:|
| refit q99 floor10 | `0.20` | `6` | `-29.7762` | `+29.7762` | `0.3750` |
| refit q95 floor10 | `0.20` | `10` | `-24.0596` | `+24.0596` | `0.4000` |
| fresh q95 floor5 | `0.25` | `6` | `+16.5110` | `-16.5110` | `0.1875` |
| cal q95 floor5 | `0.20` | `2` | `+2.5170` | `-2.5170` | `0.0500` |

`0.20` is helpful for refit in this validation view, but `0.25` already deletes profitable fresh/cal trades.

## Fresh q95_floor5 / 720m

対象: `fresh2024_validation` + `fresh2024_fixed_diagnostic`, q95_floor5 / 720m。

| role | trades | PnL | failure count | failure rate | same-side missed loss | large regret | exit regret sum | prior risk mean |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| fresh validation | `36` | `+76.2204` | `26` | `0.7222` | `12` | `24` | `669.2946` | `0.1152` |
| fresh fixed | `127` | `+325.8914` | `101` | `0.7953` | `51` | `83` | `2284.8400` | `0.2682` |

Monthly view:

| month | role | PnL | failure count | same-side missed loss | large regret | prior risk mean |
|---|---|---:|---:|---:|---:|---:|
| `2024-03` | validation | `-9.1718` | `14` | `7` | `13` | `0.0663` |
| `2024-04` | validation | `+85.3922` | `12` | `5` | `11` | `0.1640` |
| `2024-08` | fixed | `+4.2806` | `20` | `11` | `18` | `0.2313` |
| `2024-09` | fixed | `+1.3594` | `10` | `4` | `9` | `0.2593` |
| `2024-11` | fixed | `+192.8188` | `15` | `5` | `12` | `0.2346` |

Fresh q95/720 prior risk thresholds:

| threshold | flagged trades | flagged PnL | removal delta | failure precision | failure recall |
|---|---:|---:|---:|---:|---:|
| `>=0.20` | `77` | `+225.3034` | `-225.3034` | `0.7922` | `0.4803` |
| `>=0.25` | `60` | `+218.1610` | `-218.1610` | `0.8167` | `0.3858` |
| `>=0.50` | `32` | `+26.4952` | `-26.4952` | `0.8750` | `0.2205` |

This is decisive against hard blocking. The score has high target precision because the target is common, but it does not identify negative EV trades. Many flagged trades still contribute positive realized PnL.

## 2024-03 Residual Check

For the 00227 residual month:

| side / context | PnL | same-side oracle | capture ratio | target flags | prior exit risk |
|---|---:|---:|---:|---|---:|
| short `down_low_vol/asia` | `-21.1560` | `+0.4600` | `-45.9913` | missed loss / low capture / large regret | `0.3857` |
| short `up_normal_vol/london` | `-11.9196` | `+4.9500` | `-2.4080` | missed loss / low capture / large regret | `0.0027` |
| short `range_low_vol/london` | `-11.8200` | `+1.1800` | `-10.0169` | missed loss / low capture / large regret | `0.2405` |
| short `up_low_vol/asia` | `-5.4360` | `+2.7900` | `-1.9484` | missed loss / low capture | `0.0000` |
| long `range_normal_vol/ny_late` | `-0.7428` | `+21.3610` | `-0.0348` | missed loss / low capture / large regret | `0.0000` |
| long `range_normal_vol/london` | `-0.5040` | `+13.3800` | `-0.0377` | missed loss / low capture / large regret | `0.0000` |
| long `up_low_vol/ny_late` | `-0.4764` | `+30.4000` | `-0.0157` | missed loss / low capture / large regret | `0.0000` |

The target catches the residual failure mechanically. The prior score only catches part of it. Therefore the next step should not be a threshold block; it should be a model target or calibration feature.

## Decision

Accepted:

- Exit-capture target diagnostic script.
- `same_side_missed_loss`, `low_exit_capture`, `large_exit_regret`, `exit_capture_failure` as training/diagnostic labels.
- prior-only exit-capture context score as a feature candidate.

Not accepted:

- Hard blocking by `prior_exit_capture_risk_score`.
- Lowering threshold to `0.20` as a standard rule.
- Treating exit-capture failure as equivalent to negative EV. It often occurs in profitable months and profitable trades.

Standard policy remains NoTrade.

## Next

1. Use `exit_capture_failure` and continuous `exit_capture_shortfall` as exit timing / realized EV calibration targets.
2. Distinguish "loss with same-side oracle edge" from "profitable but low capture". The first is a risk target; the second may be an exit improvement target.
3. Feed `prior_exit_capture_risk_score` into selector/ranking as a soft feature, not a hard block.
4. Build an executable EV calibration target: predicted oracle EV should be discounted by expected capture ratio under the current exit policy.

## Verification

- `python3 -m unittest tests.test_entry_ev_exit_capture_target_diagnostics tests.test_entry_ev_residual_month_loss_diagnostics tests.test_entry_ev_prior_context_risk_diagnostics tests.test_entry_ev_quantile_exit_capture_diagnostics tests.test_docs_reports`: OK, `13` tests
- `python3 -m py_compile scripts/experiments/entry_ev_exit_capture_target_diagnostics.py tests/test_entry_ev_exit_capture_target_diagnostics.py`: OK
- validation q95/q99 diagnostic runs: OK
- fresh q95_floor5 / 720m diagnostic runs: OK
- `git diff --check`: OK
