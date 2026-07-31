# Entry EV Common Loss Target Diagnostics

日時: 2026-07-01 22:40 JST
更新日時: 2026-07-01 22:40 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00245の次アクションとして、baseと `side_prior_pressure_s0p5` が同じentryを選んだcommon tradeを1行にペア化し、共通entry損失targetを作る `scripts/experiments/entry_ev_common_loss_target_diagnostics.py` を追加した。
- common-entry 90 rows の side-prior側 total は `-202.1978`。`direction_side_inversion_target` は 50 rows / target PnL `-592.5618` を拾い、selected risk単体AUC `0.6755`、chronological `risk_pressure` spec AUC `0.6865` と相対的に良い。
- `common_large_loss_target` は 15 rows / `-573.1764` を拾うが、chronological `risk_pressure` AUC `0.3639` で弱い。大損を直接targetにするより、direction inversionを先に分ける方が良い。
- `exit_capture_failure_target` は 72 rows / target rate `0.8000` と広すぎ、chronological AUCも弱い。現定義のまま単独headにはしない。
- `common_low_risk_large_loss_target` は 3 rows / `-145.8552` と希少だが重要。全てlongで、direction inversionとexit failureも同時に立っているため、EV-overestimate riskではなくdirection/exit側で拾うべき残差。
- replacement 43 rows でも direction inversion が 19 rows / `-524.9992` を拾う。replacement損失もまずdirection-side inversion targetで説明するのが自然。
- 判断: common/replacement target generationはaccepted。次の本流は `direction_side_inversion_target` を低容量chronological headとしてprediction rowへ戻すこと。`common_failure_target` と `exit_capture_failure_target` の現定義は広すぎるため標準targetにしない。

## Artifacts

- Script: `scripts/experiments/entry_ev_common_loss_target_diagnostics.py`
- Test: `tests/test_entry_ev_common_loss_target_diagnostics.py`
- Input:
  - `data/reports/backtests/20260701_132922_20260701_entry_ev_side_prior_pressure_fixed2025_failure_diagnostics_s2/combined_enriched_trades.csv`
- Diagnostic run:
  - `data/reports/backtests/20260701_133922_20260701_entry_ev_common_loss_target_diagnostics_s1/`

## Method

Input rows:

```text
common: base and side_prior share candidate + month + direction + entry_decision_timestamp
replacement: side_prior-only trades
```

Common-entry target columns:

| Target | Definition |
|---|---|
| `common_realized_loss_target` | side-prior common trade PnL < 0 |
| `common_large_loss_target` | side-prior common trade PnL <= `-20` |
| `common_degraded_target` | side-prior PnL - base PnL <= `-5` |
| `direction_side_inversion_target` | selected side differs from actual best side |
| `exit_capture_failure_target` | exit regret >= `20`, or same-side oracle edge exists but capture ratio <= `0.25` |
| `common_low_risk_large_loss_target` | selected risk <= `0.25` and large loss |
| `common_failure_target` | large loss OR degraded OR direction inversion OR exit failure |

Chronological calibration uses only prior months:

```text
target month = 2025-03..2025-12
train = months earlier than target month
prior_strength = 5
min_group_support = 3
```

Specs:

| spec | columns |
|---|---|
| `side_context` | direction + combined_regime + session_regime |
| `risk_pressure` | direction + selected_risk_bucket + support_bucket + pressure_bucket |
| `score_hold` | direction + selected_risk_bucket + score_delta_bucket + predicted hold bucket + predicted rank bucket |
| `side_context_risk` | direction + combined_regime + session_regime + selected_risk_bucket |

## Common Target Summary

| target | rows | target rows | target rate | target PnL | selected-risk AUC | note |
|---|---:|---:|---:|---:|---:|---|
| `common_realized_loss_target` | `90` | `55` | `0.6111` | `-908.5668` | `0.5036` | 損失は拾うがrisk単体では分離不能 |
| `direction_side_inversion_target` | `90` | `50` | `0.5556` | `-592.5618` | `0.6755` | 最も有望 |
| `common_large_loss_target` | `90` | `15` | `0.1667` | `-573.1764` | `0.4769` | 金額は大きいが直接予測は弱い |
| `exit_capture_failure_target` | `90` | `72` | `0.8000` | `-419.6260` | `0.5073` | 広すぎる |
| `common_failure_target` | `90` | `86` | `0.9556` | `-328.3048` | `0.6933` | binary targetとして粗すぎる |
| `common_degraded_target` | `90` | `13` | `0.1444` | `-274.0152` | `0.6064` | 補助target候補 |
| `common_low_risk_large_loss_target` | `90` | `3` | `0.0333` | `-145.8552` | `0.0862` | riskでは逆方向、direction/exitで拾う |

## Chronological Calibration

| spec | target | mean AUC | target PnL | bucket share | reading |
|---|---|---:|---:|---:|---|
| `risk_pressure` | `direction_side_inversion_target` | `0.6865` | `-592.5618` | `0.5333` | 最有力 |
| `score_hold` | `direction_side_inversion_target` | `0.5804` | `-592.5618` | `0.3889` | 補助候補 |
| `side_context` | `common_degraded_target` | `0.5575` | `-274.0152` | `0.2000` | 弱いが残す |
| `risk_pressure` | `common_degraded_target` | `0.5463` | `-274.0152` | `0.5333` | 補助候補 |
| `risk_pressure` | `common_large_loss_target` | `0.3639` | `-573.1764` | `0.5333` | 直接large-loss headは弱い |

`risk_pressure` + direction inversion の high predicted bucket:

| source | predicted >= 0.6 | rows | target rate | pnl | predicted mean |
|---|---:|---:|---:|---:|---:|
| bucket | yes | `21` | `0.6667` | `-196.2284` | `0.7165` |
| bucket | no | `27` | `0.4074` | `+1.0740` | `0.4068` |
| global | yes | `28` | `0.5357` | `+50.5532` | `0.7360` |

Important: high predicted `global` rows are not loss-selective. The next head should distinguish bucket-supported estimates from global fallback instead of treating every high predicted rate equally.

## Low-Risk Large Loss

Only 3 common rows satisfy selected risk <= `0.25` and PnL <= `-20`:

| candidate | month | side | context | pnl | base pnl | risk | direction inversion | exit failure |
|---|---|---|---|---:|---:|---:|---|---|
| q99/floor5 | 2025-10 | long | range_normal_vol / ny_overlap | `-55.9080` | `-50.8320` | `0.173913` | true | true |
| q95/floor5 | 2025-10 | long | range_normal_vol / ny_overlap | `-55.9080` | `-50.8320` | `0.173913` | true | true |
| q95/floor5 | 2025-04 | long | up_normal_vol / asia | `-34.0392` | `-34.0392` | `0.173913` | true | true |

This confirms the 00245 suspicion: EV-overestimate risk can be low while actual trade quality is bad. These rows should not drive a new EV-risk penalty; they belong to direction/exit targets.

## Replacement Targets

Replacement side-prior-only rows:

| target | rows | target rows | target PnL | selected-risk AUC | reading |
|---|---:|---:|---:|---:|---|
| `replacement_realized_loss_target` | `43` | `20` | `-535.2828` | `0.3978` | risk単体は逆方向 |
| `replacement_direction_side_inversion_target` | `43` | `19` | `-524.9992` | `0.4989` | context/side headが必要 |
| `replacement_large_loss_target` | `43` | `9` | `-445.6800` | `0.4232` | direct large-lossは弱い |
| `replacement_exit_capture_failure_target` | `43` | `26` | `-427.8876` | `0.3812` | 広い |
| `replacement_positive_quality_target` | `43` | `23` | `+399.2410` | `0.6022` | replacement quality head候補 |

Worst replacement contexts are mainly short `down_normal_vol / asia` and `down_normal_vol / london`, again direction-side inversion is central.

## Decision

Accepted:

- common-entry pair target generation.
- replacement-only target generation.
- chronological low-capacity calibration for common targets.
- `direction_side_inversion_target` as the next primary target candidate.

Not accepted:

- `common_failure_target` as a direct training label because target rate is `0.9556`.
- broad `exit_capture_failure_target` as a standalone label in the current definition.
- direct `common_large_loss_target` as the next main head; it is valuable for evaluation but weak as a chronological predictor.
- EV-overestimate risk penalty tuning to catch low-risk losses.

Standard policy remains NoTrade.

## Next

1. Build a low-capacity chronological `direction_side_inversion` calibration head and attach it to prediction rows.
2. Keep `prediction_source` / bucket support explicit; do not treat global fallback predictions as equally reliable.
3. Score usage should be conservative: use the new direction inversion risk as a ranking/selector feature first, not as a hard block.
4. Keep `replacement_positive_quality_target` as a secondary head for only-side-prior replacement quality.
5. Split exit capture into narrower targets before using it: e.g. same-side missed profit, forced-exit loss, predicted hold mismatch.

## Verification

- `python3 -m py_compile scripts/experiments/entry_ev_common_loss_target_diagnostics.py tests/test_entry_ev_common_loss_target_diagnostics.py`: OK
- `python3 -m unittest tests.test_entry_ev_common_loss_target_diagnostics`: OK
- Common loss target diagnostic run: OK
