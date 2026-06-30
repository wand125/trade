# Entry EV Overestimate Risk Selector

日時: 2026-07-01 03:11 JST
更新日時: 2026-07-01 03:11 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00240で相対的に残った `executable_ev_overestimate_target` を、hard gateではなく候補selector featureとして評価する `scripts/experiments/entry_ev_overestimate_risk_selector.py` を追加した。
- `support_bucket + pressure_bucket` から対象月より前だけで `predicted_ev_overestimate_risk` を作り、candidate / role / month に集約した。
- strict gateも、PnL床を `min role -15`, `min month -10` へ緩めたrelaxed gateも、選択はNoTrade。risk sensitivity 480条件も全てNoTradeだった。
- pointwiseには q95 floor5 の high-risk rows が 24 trades / `-35.7612` を拾い、kept totalを `+14.6138 -> +50.3750` へ改善する。ただしこれはpost-trade screenであり、stateful replacementは未評価。
- 同じrisk featureは q95 floor5のrefit勝ちroleにも high-risk 11/19 trades / `+46.1476` を出すため、hard blockへ戻すと利益も削る。
- 判断: EV-overestimate risk selector diagnosticsはaccepted。現featureで候補昇格はしない。次はEV overestimateをrisk blockerではなく、entry ranking / calibration head / downside-weighted targetとして使う。

## Artifacts

- Script: `scripts/experiments/entry_ev_overestimate_risk_selector.py`
- Test: `tests/test_entry_ev_overestimate_risk_selector.py`
- Input:
  - `data/reports/backtests/20260630_145606_20260630_entry_ev_composite_target_decomposition_s1/component_trade_targets.csv`
- Strict artifact:
  - `data/reports/backtests/20260630_173608_20260701_entry_ev_overestimate_risk_selector_strict_s1/`
- Relaxed artifact:
  - `data/reports/backtests/20260630_173608_20260701_entry_ev_overestimate_risk_selector_relaxed_s1/`

Outputs:

```text
ev_overestimate_risk_trades.csv
role_month_ev_overestimate_risk.csv
candidate_ev_overestimate_risk_summary.csv
candidate_ev_overestimate_risk_selection.csv
risk_selector_sensitivity.csv
pointwise_risk_screen_effects.csv
blocker_summary.csv
selected_policy.json
config.json
```

## Method

The target is:

```text
executable_ev_overestimate_target
```

The model-time grouping is:

```text
support_bucket + pressure_bucket
```

The predicted feature is fitted chronologically:

```text
target month rows use only rows with month < target month
prior_strength = 5
min_group_support = 3
risk_threshold = 0.50
```

Selector gates are NoTrade-first. Strict gates require all validation roles to be active/positive and role/month PnL floors to be non-negative. Relaxed gates lower only PnL floors:

```text
min_role_total_pnl = -15
min_month_pnl = -10
max_risk_mean = 0.55
max_high_risk_share = 0.60
max_no_prior_share = 0.50
min_prediction_coverage = 0.50
```

The sensitivity grid tests:

```text
max_risk_mean: inf, 0.65, 0.60, 0.55, 0.50, 0.45
max_high_risk_share: inf, 0.75, 0.60, 0.45, 0.30
max_no_prior_share: inf, 0.75, 0.50, 0.25
min_prediction_coverage: 0, 0.25, 0.50, 0.75
```

## Candidate Selector Result

Strict selection:

| candidate | total | min role | min month | target rate | pred risk | high risk | coverage | no prior | blockers |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| q99 floor10 | `+1.1920` | `-7.3764` | `-7.3764` | `0.7000` | `0.4760` | `0.1000` | `0.2000` | `0.8000` | roles, positive roles, active roles, role/month PnL |
| q95 floor10 | `+15.5736` | `-11.2600` | `-9.4600` | `0.6087` | `0.4066` | `0.0435` | `0.1304` | `0.8696` | roles, positive roles, active roles, role/month PnL |
| q99 floor5 | `-10.2286` | `-38.3550` | `-35.7120` | `0.4483` | `0.5458` | `0.5517` | `0.6897` | `0.3103` | positive roles, total/role/month PnL |
| q95 floor5 | `+14.6138` | `-82.2428` | `-46.5308` | `0.4151` | `0.5237` | `0.4528` | `0.6226` | `0.3774` | positive roles, role/month PnL |

Relaxed selection:

- All four candidates remain ineligible.
- floor10 candidates are blocked by missing role / low prediction coverage / high no-prior share.
- floor5 candidates are blocked by positive role, role floor, month floor; q99 floor5 is also blocked by total PnL.
- `risk_selector_sensitivity.csv` has `480 / 480` NoTrade selections.

## Role-Level Reading

| candidate | role | trades | total | target rate | pred risk | high risk | coverage | high-risk pnl |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| q95 floor5 | cal2024 | `26` | `+2.8654` | `0.5385` | `0.6842` | `0.2308` | `0.2308` | `+2.7640` |
| q95 floor5 | fresh2024 | `8` | `-82.2428` | `0.3750` | `0.5657` | `0.8750` | `1.0000` | `-84.6728` |
| q95 floor5 | refit2025 | `19` | `+93.9912` | `0.2632` | `0.4553` | `0.5789` | `1.0000` | `+46.1476` |
| q99 floor5 | fresh2024 | `6` | `-38.3550` | `0.1667` | `0.5506` | `0.8333` | `1.0000` | `-40.7850` |
| q99 floor5 | refit2025 | `10` | `+30.2336` | `0.4000` | `0.4876` | `0.7000` | `1.0000` | `+34.0160` |

Important reading:

- q95/q99 floor5 のfresh lossesは high-risk rows と強く重なる。
- しかしrefit winnersにも high-risk rowsが多く、high-risk blockは利益も削る。
- prediction coverageはfloor10で低すぎる。低riskに見えるのは、安全ではなくpriorがないため。

## Pointwise Screen Effects

Risk threshold `0.50`:

| candidate | screen | removed trades | removed pnl | kept total | kept min role | kept min month |
|---|---|---:|---:|---:|---:|---:|
| q95 floor5 | predicted high only | `24` | `-35.7612` | `+50.3750` | `+0.1014` | `+0.1014` |
| q95 floor5 | high or no-prior | `44` | `-35.6598` | `+50.2736` | `+2.4300` | `+2.4300` |
| q99 floor5 | predicted high only | `16` | `-13.0920` | `+2.8634` | `-3.7824` | `-3.7824` |
| q99 floor5 | high or no-prior | `25` | `-8.8762` | `-1.3524` | `-3.7824` | `-3.7824` |
| q95 floor10 | predicted high only | `1` | `-1.8000` | `+17.3736` | `-9.4600` | `-9.4600` |
| q99 floor10 | high or no-prior | `9` | `+8.5684` | `-7.3764` | `-7.3764` | `-7.3764` |

This is diagnostic only. Removing selected trades does not simulate replacement under the one-position constraint. The result says the feature is useful for explaining selected-trade loss, not that it can be promoted as a policy gate.

## Decision

Accepted:

- EV-overestimate risk selector diagnostics.
- Chronological predicted EV-overestimate risk as a low-capacity selector/ranking feature.
- Prediction coverage and no-prior share as mandatory companion features.
- Pointwise screen effects as diagnostic preflight.

Not accepted:

- Promoting any candidate from the EV-overestimate risk selector.
- Treating low predicted risk with low coverage as safe.
- Hard-blocking high predicted EV-overestimate risk.
- Treating pointwise kept PnL as a stateful policy result.

Standard policy remains NoTrade.

## Next

1. Move EV-overestimate risk from hard selector gates into a ranking/calibration head that can change entry ordering without deleting all high-risk trades.
2. Combine EV-overestimate risk with side/context features to separate fresh high-risk losses from refit high-risk winners.
3. Generate component targets for more chronological windows; current early months have high no-prior share.
4. When using pointwise screens, always follow with stateful one-position replay or replacement-aware diagnostics.

## Verification

- `python3 -m py_compile scripts/experiments/entry_ev_overestimate_risk_selector.py tests/test_entry_ev_overestimate_risk_selector.py`: OK
- `python3 -m unittest tests.test_entry_ev_overestimate_risk_selector`: OK
- Strict diagnostic run: OK
- Relaxed diagnostic run: OK
