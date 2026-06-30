# Entry EV Side Balance Downside Composite Selector

日時: 2026-06-30 19:54 JST
更新日時: 2026-06-30 19:54 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00237の次アクションとして、coverage/support、side-balance/downside pressure、direction error、exit regret、expected PnL overestimateを同じcandidate gateへ入れる `scripts/experiments/entry_ev_side_balance_downside_composite_selector.py` を追加した。
- missing required roleは低riskではなくunknown/high riskとして扱い、role欠損時は composite risk `1.0`、direction/exit/EV overestimate componentも `1.0` にする。
- strict composite gateでは全候補NoTrade。
- PnL床だけ緩めたrelaxed composite gateでも全候補NoTrade。
- relaxed sensitivity 288条件も全てNoTrade。
- floor10系は fresh role欠損により composite riskが `1.0`。floor5系は3 role coverageを満たすが、fresh tail、cal2024 prior-zero、direction error、EV過大評価で落ちる。
- 判断: composite selector diagnosticsはaccepted。現候補は採用しない。次はこのcompositeをhard gateとして固定するのではなく、missing-support indicator、direction/exit failure、executable EV calibrationを学習feature/targetへ分解する。

## Artifacts

- Script: `scripts/experiments/entry_ev_side_balance_downside_composite_selector.py`
- Test: `tests/test_entry_ev_side_balance_downside_composite_selector.py`
- Strict composite selector:
  - `data/reports/backtests/20260630_105344_20260630_entry_ev_side_balance_downside_composite_strict_s1/`
- Relaxed composite selector:
  - `data/reports/backtests/20260630_105357_20260630_entry_ev_side_balance_downside_composite_relaxed_s1/`
- Input:
  - `data/reports/backtests/20260630_101914_20260630_entry_ev_side_balance_downside_interaction_s1/enriched_side_balance_downside_trades.csv`

## Method

Required roles:

```text
cal2024_calibration_validation
fresh2024_validation
refit2025_validation
```

Role-level composite risk:

```text
composite_preflight_risk =
  0.20 * feature_pressure_score
  0.20 * prior_zero_share
  0.20 * direction_error_rate
  0.15 * large_exit_regret_rate
  0.10 * no_edge_rate
  0.10 * ev_overestimate_component
  0.05 * support_gap
```

`feature_pressure_score` は00236と同じ:

```text
0.35 * risk_high_share
+ 0.30 * interaction_high_share
+ 0.20 * prior_downside_risk_score_mean
+ 0.15 * prior_zero_share
```

EV過大評価と実PnL floorはvalidation calibration diagnosticであり、model-time input featureではない。modelへ戻す場合は、対象月より前だけで作ったcapture calibration、missing-support flag、direction/exit failure targetへ分解する。

## Strict Composite Gate

Gate:

```text
min active required roles = 3
min required role trades = 1
min total PnL = 0
min required role total PnL = 0
min required month PnL = 0
max required role prior zero share = 0.75
max required role feature pressure = 0.50
max required role composite risk = 0.50
max required role direction error = 0.75
max required role large exit regret = 0.75
```

Result: NoTrade.

## Relaxed Composite Gate

Relaxed gate only loosens realized PnL floors:

```text
min required role total PnL = -15
min required month PnL = -10
coverage/support/composite gates unchanged
```

Result: NoTrade.

Feature sensitivity:

- 288 grid rows.
- 288 rows selected NoTrade.
- 0 rows selected a policy.

## Candidate Findings

Relaxed gate:

| candidate | active roles | missing roles | total | min role | min month | prior zero max | pressure max | composite max | direction max | exit max | overestimate max | blockers |
|---|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| q99 floor10 | `2` | fresh2024 | `+1.1920` | `-7.3764` | `-7.3764` | `1.0000` | `1.0000` | `1.0000` | `1.0000` | `1.0000` | `1.0000` | missing/active/trades/zero/pressure/composite/direction/exit |
| q95 floor10 | `2` | fresh2024 | `+15.5736` | `-11.2600` | `-9.4600` | `1.0000` | `1.0000` | `1.0000` | `1.0000` | `1.0000` | `1.0000` | missing/active/trades/zero/pressure/composite/direction/exit |
| q99 floor5 | `3` | none | `-10.2286` | `-38.3550` | `-35.7120` | `0.9231` | `0.4666` | `0.5205` | `0.8333` | `0.7000` | `0.6639` | total/role/month/zero/composite/direction |
| q95 floor5 | `3` | none | `+14.6138` | `-82.2428` | `-46.5308` | `0.8846` | `0.4596` | `0.5231` | `0.8750` | `0.7368` | `0.6260` | role/month/zero/composite/direction |

## Role-Level Findings

| candidate | role | present | trades | role PnL | min month | prior zero | pressure | composite | direction | exit | overestimate |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| q95 floor10 | cal2024 | true | `21` | `-11.2600` | `-9.4600` | `1.0000` | `0.1500` | `0.5477` | `0.6667` | `0.4286` | `0.7010` |
| q95 floor10 | fresh2024 | false | `0` | `0.0000` | `0.0000` | `1.0000` | `1.0000` | `1.0000` | `1.0000` | `1.0000` | `1.0000` |
| q95 floor10 | refit2025 | true | `2` | `+26.8336` | `+26.8336` | `0.0000` | `0.7355` | `0.3521` | `0.0000` | `1.0000` | `0.5000` |
| q95 floor5 | cal2024 | true | `26` | `+2.8654` | `+0.1014` | `0.8846` | `0.1696` | `0.4940` | `0.5769` | `0.3846` | `0.6243` |
| q95 floor5 | fresh2024 | true | `8` | `-82.2428` | `-46.5308` | `0.3750` | `0.4213` | `0.5231` | `0.8750` | `0.6250` | `0.6260` |
| q95 floor5 | refit2025 | true | `19` | `+93.9912` | `+9.5300` | `0.3684` | `0.4596` | `0.4290` | `0.4211` | `0.7368` | `0.3917` |
| q99 floor10 | fresh2024 | false | `0` | `0.0000` | `0.0000` | `1.0000` | `1.0000` | `1.0000` | `1.0000` | `1.0000` | `1.0000` |
| q99 floor5 | cal2024 | true | `13` | `-2.1072` | `-6.3230` | `0.9231` | `0.1631` | `0.5205` | `0.5385` | `0.5385` | `0.6639` |
| q99 floor5 | fresh2024 | true | `6` | `-38.3550` | `-35.7120` | `0.3333` | `0.4666` | `0.4837` | `0.8333` | `0.5000` | `0.5207` |

The result separates two failure classes:

1. floor10 candidates are not validated in fresh2024, so low average pressure must not be read as safety.
2. floor5 candidates have coverage, but the weak role/month tail remains and coincides with high direction error plus EV overestimate.

## Decision

Accepted:

- Composite selector script.
- Required-role coverage + composite preflight risk summary.
- Missing required role as unknown/high risk.
- Direction/exit/EV overestimate as validation calibration diagnostics.

Not accepted:

- Any current q95/q99 floor candidate as a policy.
- Treating composite risk as a frozen production hard gate before more chronological windows.
- Using validation-realized EV overestimate directly as a model-time feature.

Standard policy remains NoTrade.

## Next

1. Add missing-support indicators to training features so early/fresh no-prior contexts are learned as unknown risk.
2. Split composite into modelable targets: direction-side inversion, exit capture failure, executable EV overestimate, and side-balance/downside pressure.
3. Re-run the composite selector after adding additional chronological validation windows; do not promote candidates from the current 3-role artifact alone.
4. Use composite score as a ranking/selector feature, not as another narrow threshold search.

## Verification

- `python3 -m py_compile scripts/experiments/entry_ev_side_balance_downside_composite_selector.py tests/test_entry_ev_side_balance_downside_composite_selector.py`: OK
- `python3 -m unittest tests.test_entry_ev_side_balance_downside_composite_selector`: OK
- Strict composite selector: OK
- Relaxed composite selector: OK
