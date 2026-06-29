# Side Drift Guard Admission Margin

日時: 2026-06-29 23:10 JST
更新日時: 2026-06-29 23:10 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- `side_ev_penalty_replacement_min_margin` を `ModelPolicyConfig` / `model-policy` / `model-sweep` に追加した。
- 意味: `side_ev_penalty_rules` が選択sideにかかる、またはpenaltyで選択sideが変わる場合だけ、通常entry thresholdに追加のscore marginを要求する。
- 目的: side drift guardで悪い文脈を検出した後、弱いreplacement tradeへ即入らず stay flat に近づける。
- strict short-only p10 guardに admission margin `10` を加えると、2025-01..12 coststress `260m` total PnL は `-317.4998 -> -90.1378`。
- no guard比では `-419.0574 -> -90.1378` で大幅改善。ただしまだNoTrade未満で、標準採用しない。

## Artifacts

- isolated sweep: `data/reports/backtests/20260629_140836_side_drift_guard_admission_margin_isolated_2025_01_12_coststress_260/`
- modeling input: `data/reports/modeling/20260629_140836_side_drift_guard_admission_margin_isolated_2025_01_12_coststress_260/`
- delta no-guard margin10 vs p10 margin10: `data/reports/backtests/20260629_140952_side_drift_guard_admission_margin10_delta_vs_margin10/`
- delta p10 vs p10 margin10: `data/reports/backtests/20260629_140952_side_drift_guard_admission_margin10_delta_vs_p10/`

## Aggregate

| variant | penalty | margin | trades | total PnL | worst month | max DD | forced exits |
|---|---:|---:|---:|---:|---:|---:|---:|
| no guard | `0` | `-inf` | `1153` | `-419.0574` | `-370.8744` | `376.0724` | `1` |
| no guard replm5 | `0` | `5` | `1026` | `-263.4492` | `-315.1082` | `315.1082` | `2` |
| no guard replm10 | `0` | `10` | `1018` | `-290.8978` | `-309.6422` | `309.6422` | `1` |
| p10 guard | `10` | `-inf` | `1146` | `-317.4998` | `-364.5482` | `369.7462` | `1` |
| p10 guard replm5 | `10` | `5` | `969` | `-136.1994` | `-297.5986` | `297.5986` | `2` |
| p10 guard replm10 | `10` | `10` | `949` | `-90.1378` | `-289.0056` | `289.0056` | `2` |
| p10 guard replm15 | `10` | `15` | `947` | `-90.8798` | `-289.0056` | `289.0056` | `2` |
| p10 guard replm_block | `10` | `inf` | `947` | `-90.8798` | `-289.0056` | `289.0056` | `2` |

Interpretation:

- Existing base side penalties also benefit from admission margin. That is why no-guard replm5 improves by `+155.6082` vs no guard.
- But strict p10 + replm10 still improves another `+200.7600` over no-guard replm10, so the prior-only drift guard contributes additional signal.
- `10`, `15`, and `block` are close. `10` is the best total, while `15/block` have almost identical defense.

## Month View

`p10 guard replm10`:

| month | trades | PnL | delta vs no guard replm10 |
|---|---:|---:|---:|
| 2025-01 | `92` | `101.4088` | `0.0000` |
| 2025-02 | `106` | `75.0192` | `0.0000` |
| 2025-03 | `113` | `22.5032` | `0.0000` |
| 2025-04 | `69` | `67.7250` | `-3.6500` |
| 2025-05 | `87` | `52.0092` | `+84.8160` |
| 2025-06 | `84` | `235.3276` | `+16.7726` |
| 2025-07 | `124` | `80.9808` | `+23.6690` |
| 2025-08 | `99` | `-98.9364` | `-21.1274` |
| 2025-09 | `81` | `-289.0056` | `+20.6366` |
| 2025-10 | `29` | `-46.6894` | `-27.2008` |
| 2025-11 | `23` | `-111.6232` | `-9.0436` |
| 2025-12 | `42` | `-178.8570` | `+115.8876` |

The fresh tail is improved but not solved. 2025-08, 2025-09, 2025-11, and 2025-12 still decide the failure.

## Delta vs No-Guard Margin10

Comparing `no_guard_replm10 -> p10_guard_replm10`:

| status | rows | base PnL | candidate PnL | delta |
|---|---:|---:|---:|---:|
| common | `878` | `118.2442` | `198.4666` | `+80.2224` |
| only_base | `140` | `-409.1420` | `0.0000` | `+409.1420` |
| only_candidate | `71` | `0.0000` | `-288.6044` | `-288.6044` |

Direction split:

| status | direction | rows | delta |
|---|---|---:|---:|
| only_base | short | `140` | `+409.1420` |
| only_candidate | short | `66` | `-278.4984` |
| only_candidate | long | `5` | `-10.1060` |
| common short | short | `412` | `+75.9150` |

The guard still works mainly by removing losing shorts. Admission margin shrinks replacement losses, but remaining added shorts are still the main drag.

Worst remaining added contexts:

| month | direction | combined regime | rows | candidate PnL |
|---|---|---|---:|---:|
| 2025-09 | short | range_low_vol | `3` | `-138.6240` |
| 2025-11 | short | range_low_vol | `4` | `-62.9580` |
| 2025-09 | short | range_normal_vol | `2` | `-42.7320` |
| 2025-12 | short | range_low_vol | `12` | `-35.0640` |
| 2025-05 | short | range_normal_vol | `6` | `-22.6520` |

Best removed loss contexts:

| month | direction | combined regime | rows | removed base PnL |
|---|---|---|---:|---:|
| 2025-09 | short | range_low_vol | `18` | `-154.0636` |
| 2025-12 | short | range_low_vol | `10` | `-85.3304` |
| 2025-11 | short | range_normal_vol | `1` | `-42.2484` |
| 2025-05 | short | range_low_vol | `2` | `-41.2200` |
| 2025-09 | short | up_normal_vol | `9` | `-39.3730` |

## Decision

- Do not standardize this policy yet. The best result is much less bad but still negative.
- Keep `side_ev_penalty_replacement_min_margin` in the codebase as a general admission/risk-control axis.
- Treat `p10 + margin10` as the next diagnostic baseline for fresh tail analysis.
- Next work:
  - isolate the remaining 2025-08/09/11/12 failures under `p10 + margin10`;
  - split residual `short/range_low_vol` into session/time/side-gap/quality buckets;
  - test whether a walk-forward replacement-risk target can catch those residual added shorts without killing 2025-05/06/07 gains.

## Verification

- `python3 -m py_compile src/trade_data/backtest.py scripts/experiments/side_drift_guard_walkforward.py`: OK
- `python3 -m unittest tests.test_backtest tests.test_side_drift_guard_walkforward`: OK, 88 tests
