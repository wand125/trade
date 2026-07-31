# Side Drift Guard Walk-Forward

日時: 2026-06-29 22:47 JST
更新日時: 2026-06-29 22:47 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- Added `scripts/experiments/side_drift_guard_walkforward.py`.
- Goal: convert prior-only side drift diagnostics into soft `side_ev_penalty_rules`.
- Target policy: `stateful_p5`, `max_predicted_hold_minutes=260`, cost stress.
- Evaluation months: 2025-01..2025-12.
- Result: guard can reduce the fresh failure, but it is not stable enough for standard policy.
- Broad guard p5 improves max drawdown and worst month, but only small total improvement.
- Strict short-only p10 improves total PnL more, but does not improve worst month / drawdown.

## Method

For each target month:

1. Use only months before the target month.
2. Compare prediction-side share with dense label-side share by `combined_regime + session_regime`.
3. Join prior selected trade PnL for the same side/context.
4. Select a guard rule only when the prior context has:
   - enough prediction rows,
   - enough prior months,
   - predicted side share above actual label side share,
   - enough selected trades,
   - selected-side PnL below zero.
5. Apply `side_ev_penalty_rules` to the target month.

This is not a fresh-window hard block. The target month is not used to choose its own rules.

## Broad Guard

Command highlights:

- sides: `short,long`
- context: `combined_regime,session_regime`
- min prior months: `3`
- min prediction rows: `100`
- min prediction months: `2`
- min side bias: `0.20`
- min selected trades: `5`
- min selected months: `2`
- penalties: `0,5,10,15`

Aggregate:

| variant | penalty | months | trades | total PnL | worst month | max DD | forced exits | total rule count |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| no guard | `0` | `12` | `1153` | `-419.0574` | `-370.8744` | `376.0724` | `1` | `0` |
| broad guard | `5` | `12` | `1187` | `-394.7214` | `-308.3412` | `308.3412` | `1` | `67` |
| broad guard | `10` | `12` | `1247` | `-412.6676` | `-297.3218` | `297.3218` | `1` | `67` |
| broad guard | `15` | `12` | `1482` | `-475.4864` | `-255.9218` | `298.0792` | `1` | `67` |

Broad p5 gives the best total among broad settings and improves drawdown materially. Broad p10/p15 improve worst-month and drawdown more, but p15 overreacts and loses total PnL.

Important p5 month deltas:

| month | delta vs no guard |
|---|---:|
| 2025-04 | `+84.3056` |
| 2025-05 | `-82.6614` |
| 2025-06 | `-75.2754` |
| 2025-07 | `+17.8564` |
| 2025-08 | `-42.7270` |
| 2025-09 | `+81.8860` |
| 2025-10 | `-53.8984` |
| 2025-11 | `+53.5660` |
| 2025-12 | `+41.2842` |

This is not stable enough. It helps the fresh tail but damages earlier positive months.

## Strict Short-Only Guard

Command highlights:

- sides: `short`
- min prediction rows: `500`
- min prediction months: `3`
- min side bias: `0.30`
- min selected trades: `10`
- min selected months: `3`

Aggregate:

| variant | penalty | months | trades | total PnL | worst month | max DD | forced exits | total rule count |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| no guard | `0` | `12` | `1153` | `-419.0574` | `-370.8744` | `376.0724` | `1` | `0` |
| strict short | `5` | `12` | `1140` | `-396.1942` | `-377.4252` | `382.6232` | `1` | `30` |
| strict short | `10` | `12` | `1146` | `-317.4998` | `-364.5482` | `369.7462` | `1` | `30` |
| strict short | `15` | `12` | `1254` | `-490.3786` | `-388.2888` | `421.4198` | `1` | `30` |

Strict p10 has the best total PnL, improving no-guard by `+101.5576`, but it does not fix worst month or max drawdown.

Important strict p10 month deltas:

| month | delta vs no guard |
|---|---:|
| 2025-04 | `-8.9300` |
| 2025-05 | `-2.8890` |
| 2025-06 | `+23.8708` |
| 2025-07 | `+39.2090` |
| 2025-08 | `-24.3674` |
| 2025-09 | `+6.3262` |
| 2025-10 | `-34.0984` |
| 2025-11 | `+53.9528` |
| 2025-12 | `+48.4836` |

Strict short-only is less reactive than broad p5, but still shifts losses across months rather than producing a robust policy.

## Rule Behavior

Broad guard selected `67` rule-month rows; strict short-only selected `30`.

Examples from strict short-only:

| target month | side | context | prediction rows | side bias | selected trades | prior selected PnL |
|---|---|---|---:|---:|---:|---:|
| 2025-04 | short | `up_normal_vol / london` | `945` | `0.6148` | `11` | `-8.3194` |
| 2025-06 | short | `up_normal_vol / asia` | `5704` | `0.5745` | `25` | `-71.2538` |
| 2025-09 | short | `range_low_vol / london` | `21898` | `0.3815` | `87` | `-2.9706` |
| 2025-12 | short | `range_low_vol / london` | `26583` | `0.4382` | `109` | `-140.5838` |

The guard detects the same failure contexts as the fresh drift diagnostics, but the penalty can create replacement trades that are not necessarily better.

## Caveat

The 2025-01..08 and 2025-09..12 prediction frames were stitched so the 2025-08 month-end has more post-month prediction coverage than the previous isolated fine-grid run. This is closer to a continuous live evaluation, but it means the no-guard 2025-08 PnL here is not exactly the previous isolated report. Comparisons inside this report are same-input comparisons and are valid for this guard experiment.

## Decision

- Keep the walk-forward side drift guard infrastructure.
- Do not adopt broad p5 or strict p10 as standard policy yet.
- Broad p5 is the current drawdown/worst-month diagnostic candidate.
- Strict short p10 is the current total-PnL diagnostic candidate.
- Next step should evaluate replacement-trade quality after side penalties. The guard is correctly identifying bad short contexts, but the policy sometimes replaces them with different losing trades.

## Artifacts

- Broad guard modeling: `data/reports/modeling/20260629_134533_side_drift_guard_wf_2025_01_12_coststress_260/`
- Broad guard backtests: `data/reports/backtests/20260629_134533_side_drift_guard_wf_2025_01_12_coststress_260/`
- Strict short modeling: `data/reports/modeling/20260629_134638_side_drift_guard_wf_short_strict_2025_01_12_coststress_260/`
- Strict short backtests: `data/reports/backtests/20260629_134638_side_drift_guard_wf_short_strict_2025_01_12_coststress_260/`

## Verification

- `python3 -m unittest tests.test_side_drift_guard_walkforward`: OK, 4 tests
- `python3 -m py_compile scripts/experiments/side_drift_guard_walkforward.py`: OK
- `python3 scripts/experiments/side_drift_guard_walkforward.py --help`: OK

## Next Actions

- Use `model-trade-delta` or a dedicated delta diagnostic to compare no-guard vs strict p10 and broad p5.
- Separate "bad short removed" from "replacement trade added"; do not rely only on monthly PnL.
- Try a guard that lowers exposure without increasing trade count, for example by increasing side margin or entry threshold in flagged contexts instead of only subtracting EV from one side.
