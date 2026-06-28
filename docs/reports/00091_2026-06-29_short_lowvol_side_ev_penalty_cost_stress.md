# Short Low-vol Side EV Penalty Cost Stress

日時: 2026-06-29 03:59 JST
更新日時: 2026-06-29 03:59 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻である `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## 目的

`component_fixed_weighted quality>=2` は2025-03追加holdoutで悪化したため、quality hard gateを深掘りせず、2025-03で見えたshort偏重、side error、`short:asia` 損失集中を抑える方向を確認した。

今回は既存の `timed_ev` fixed policyに対して、side-confidence gate、side-confidence soft penalty、short側のcombined-regime EV penalty、entry/rank tightening、cost stressを比較する。

## 固定条件

- predictions: `component_fixed_weighted`
- validation months: `2024-07`, `2024-09`, `2024-11`, `2025-01`
- holdout months: `2024-12`, `2025-02`, `2025-03`
- fixed policy base: `timed_ev`, `entry=12`, `long offset=0`, `short offset=6`, `side margin=5`, `risk penalty=0`, `min entry rank=0.5`
- holding columns: `pred_mlp_long_exit_event_minutes`, `pred_mlp_short_exit_event_minutes`
- max predicted hold: `480`
- evaluation multipliers: profit `1.0`, loss `1.20`

Baseline fixed policy:

| scope | adjusted pnl | trades | note |
|---|---:|---:|---|
| validation min | `82.7176` | `24` | 4fold minimum |
| validation sum | `406.6546` | - | 4fold total |
| 2024-12 | `-31.7576` | `52` | fixed holdout |
| 2025-02 | `47.1824` | `126` | fixed holdout |
| 2025-03 | `-48.6826` | `112` | fixed holdout |

## 2025-03 Trade診断

2025-03 baselineのselected tradesでは、longは勝っている一方、shortが損失源だった。

| side | trades | adjusted pnl | avg adjusted pnl |
|---|---:|---:|---:|
| long | `15` | `47.6936` | `3.1796` |
| short | `97` | `-96.3762` | `-0.9936` |

最悪groupは `short:asia` 6 trades `-67.7956` と `short:rollover` 3 trades `-37.6094`。ただし2024-11ではlow-confidence shortが利益に寄与しており、low confidence hard gateは危険。

## Side-confidence Gate

`min_side_confidence` はvalidationを壊した。

| min side confidence | validation min pnl | validation sum pnl | min trades |
|---:|---:|---:|---:|
| `0.00` | `82.7176` | `406.6546` | `24` |
| `0.55` | `7.0802` | `195.0792` | `19` |
| `0.60` | `-12.1826` | `279.1138` | `10` |
| `0.65` | `-9.0452` | `146.5860` | `3` |
| `0.70` | `0.0000` | `48.2778` | `0` |

`side_confidence_penalty` もbaselineを超えなかった。

| side confidence penalty | validation min pnl | validation sum pnl |
|---:|---:|---:|
| `0` | `82.7176` | `406.6546` |
| `5` | `49.0358` | `330.5774` |
| `10` | `39.8008` | `289.4002` |
| `15` | `-14.2936` | `189.4414` |
| `20` | `-10.6610` | `154.9200` |

判断: side confidenceは単体hard/soft gateとして採用しない。calibration特徴として残す。

## Short Side EV Penalty

単一ルールでは `short:combined_regime=down_low_vol:5` がvalidationを改善したが、holdoutで2025-02を壊した。

| rule | validation min pnl | validation sum pnl | holdout min pnl | holdout sum pnl |
|---|---:|---:|---:|---:|
| none | `82.7176` | `406.6546` | `-48.6826` | `-33.2578` |
| `short:combined_regime=down_low_vol:5` | `110.3942` | `555.3644` | `-18.0732` | `70.2802` |
| `short:session_regime=rollover:5` | - | - | `-30.1586` | `3.9642` |
| `short:combined_regime=up_low_vol:10` | `99.3870` | `584.3816` | `-56.2664` | `132.1686` |

単一ルールは標準採用しない。

## Low-vol Combo

short low-vol系の組み合わせはvalidation上は強い。

| rule set | validation min pnl | validation sum pnl | min trades | max short share |
|---|---:|---:|---:|---:|
| `down5,up10,range5` | `138.3706` | `676.1198` | `66` | `0.3662` |
| `down5,up10` | `138.0338` | `622.6486` | `65` | `0.3973` |
| `down5,up15` | `131.3082` | `623.1814` | `70` | `0.4068` |
| `down5,up15,range10` | `118.7610` | `638.9718` | `70` | `0.3469` |
| none | `82.7176` | `406.6546` | `24` | `0.7188` |

固定holdoutでは `down5,up15,range10` が3ヶ月すべてプラスだった。

| rule set | holdout min pnl | holdout sum pnl | min trades | max short share |
|---|---:|---:|---:|---:|
| `down5,up15,range10` | `10.0758` | `175.8862` | `138` | `0.5729` |
| `down5,up10,range5` | `-0.0572` | `125.5160` | `91` | `0.6209` |
| `down10,up10,range10` | `-1.6414` | `295.7600` | `121` | `0.5512` |
| none | `-48.6826` | `-33.2578` | `52` | `0.9048` |

`down5,up15,range10` の月別zero-cost結果:

| month | adjusted pnl | trades | profit factor | max drawdown |
|---|---:|---:|---:|---:|
| 2024-12 | `10.0758` | `138` | `1.0306` | `101.8636` |
| 2025-02 | `83.0220` | `199` | `1.1779` | `109.1208` |
| 2025-03 | `82.7884` | `156` | `1.2051` | `69.3974` |

## Cost Stress

`down5,up15,range10`, `entry=12`, `rank=0.5` はzero-costでは改善したが、取引回数が多くcost fragileだった。

| month | no cost | moderate cost | high cost | worst case |
|---|---:|---:|---:|---:|
| 2024-12 | `10.0758` | `-22.8348` | `-53.7684` | `-53.7684` |
| 2025-02 | `83.0220` | `15.1854` | `-28.4626` | `-28.4626` |
| 2025-03 | `82.7884` | `59.1726` | `24.8552` | `13.7836` |

Cost scenarios:

- moderate: `spread=0.1`, `slippage=0.05`, `execution_delay=1`
- high: `spread=0.2`, `slippage=0.1`, `execution_delay=1`
- worst case: each monthのstress grid内の最小adjusted pnl

3ヶ月同一cost scenario集計:

| spread | slippage | delay | sum pnl | min month pnl |
|---:|---:|---:|---:|---:|
| `0.0` | `0.00` | `0` | `175.8862` | `10.0758` |
| `0.0` | `0.00` | `1` | `159.8046` | `7.9372` |
| `0.0` | `0.05` | `0` | `121.8794` | `-5.0642` |
| `0.1` | `0.05` | `1` | `51.5232` | `-22.8348` |
| `0.2` | `0.10` | `1` | `-57.3758` | `-53.7684` |

## Entry/rank Tightening

validationではentryを厳しくしても `entry=12`, `rank=0.5` が最良だった。

| entry | rank | no-cost min pnl | no-cost sum pnl | mid-cost min pnl | mid-cost sum pnl | mean trades |
|---:|---:|---:|---:|---:|---:|---:|
| `12` | `0.5` | `118.7610` | `638.9718` | `100.6632` | `574.3542` | `80.2` |
| `16` | `0.5` | `32.2752` | `413.1038` | `30.9642` | `412.0414` | `32.8` |
| `20` | `0.5` | `8.8110` | `160.8618` | `4.8370` | `155.6296` | `5.5` |
| `12` | `0.6` | `5.4574` | `80.6342` | `5.9134` | `76.3912` | `7.8` |

`entry=16`, `rank=0.5` をholdoutへ適用すると、zero-costの時点で崩れた。

| month | entry=12 no cost | entry=16 no cost | entry=16 mid-cost | entry=16 worst |
|---|---:|---:|---:|---:|
| 2024-12 | `10.0758` | `-18.6930` | `-33.6448` | `-54.0018` |
| 2025-02 | `83.0220` | `-43.3716` | `-70.4028` | `-96.0728` |
| 2025-03 | `82.7884` | `55.7596` | `31.0562` | `12.4162` |

判断: 単純なentry tighteningは勝ちtradeも落としており、cost耐性の改善策として採用しない。

## 判断

`short:combined_regime=down_low_vol:5,short:combined_regime=up_low_vol:15,short:combined_regime=range_low_vol:10` はzero-cost fixed holdoutで初めて3ヶ月すべてプラスになったため、重要な候補として残す。

ただし標準policyにはまだ昇格しない。理由は、2024-12がmoderate costで `-22.8348` へ落ち、高costでは3ヶ月合算もマイナスになるため。取引回数を増やしてzero-costの見かけを改善した可能性がある。さらに、combo探索はvalidation後にholdout比較しているため、post-hoc overfit riskも残る。

採用しないもの:

- `min_side_confidence` hard gate
- `side_confidence_penalty` global soft penalty
- single `short:combined_regime=down_low_vol:5`
- `entry=16` などの単純なentry tightening

次はcost-aware validationを選定基準へ組み込み、zero-costだけでなくmoderate costのmin month pnlも同時に満たす候補を探す。side EV penaltyをさらに広げるより、entry quality component、side-confidence、profit-barrier miss、EV overestimate、direction/session riskをmulti-feature stackingまたは候補rankingに使う方向を優先する。

## Artifacts

- 2025-03 baseline trade analysis: `data/reports/backtests/component_fixed_weighted_side_proxy_trade_analysis/20260628_184305_model_timed_ev_2025-03/`
- side confidence gate validation: `data/reports/backtests/component_fixed_weighted_side_confidence_gate_validation/`
- side confidence penalty validation: `data/reports/backtests/component_fixed_weighted_side_confidence_penalty_validation/`
- short side EV single-rule validation: `data/reports/backtests/component_fixed_weighted_short_side_ev_penalty_validation/`
- short side EV holdout sweep: `data/reports/backtests/component_fixed_weighted_short_side_ev_penalty_holdout_sweep/`
- low-vol combo validation: `data/reports/backtests/component_fixed_weighted_short_lowvol_combo_validation/`
- low-vol combo holdout sweep: `data/reports/backtests/component_fixed_weighted_short_lowvol_combo_holdout_sweep/`
- low-vol combo cost stress: `data/reports/backtests/component_fixed_weighted_short_lowvol_combo_cost_stress/`
- low-vol combo entry/rank validation no-cost: `data/reports/backtests/component_fixed_weighted_short_lowvol_combo_entry_rank_validation_base/`
- low-vol combo entry/rank validation mid-cost: `data/reports/backtests/component_fixed_weighted_short_lowvol_combo_entry_rank_validation_midcost/`
- entry16 cost stress: `data/reports/backtests/component_fixed_weighted_short_lowvol_combo_entry16_cost_stress/`

## Verification

- `PYTHONPATH=src python3 -m trade_data.backtest model-sweep`: OK for validation and holdout sweeps
- `PYTHONPATH=src python3 -m trade_data.backtest model-cost-sensitivity`: OK for entry12 and entry16 cost stress
