# 00045 Intrabar Pressure M30 transfer

日時: 2026-08-10 15:39 JST

## 目的

M15/M5で検証したIntrabar Pressure 11特徴を、定義・HGB・Platt・25% blendを変更せずM30へ移植する。方向、confidence選別、確率品質、nested odds、親Profileとの差を同じ7foldで評価する。

## 方向用途は棄却

| period | baseline | Pressure単体 | Pressure 25% blend |
|---|---:|---:|---:|
| development | 51.990% | 51.701% | 51.896% |
| confirmation | 51.520% | 51.347% | 51.488% |
| all | 51.807% | 51.563% | 51.737% |

通常25% blendはbaseline誤り修正1,590件、新規誤り1,640件、McNemar exact p=0.389だった。M30方向には使わない。

## Development選択0.52 confidence

方向をbaselineへ固定し、developmentの固定gridだけで目的関数最大の0.52を選んだ。

| period | model | coverage | accuracy | Wilson lower | selection score |
|---|---|---:|---:|---:|---:|
| development | baseline | 41.244% | 53.415% | 52.685% | 0.01724 |
| development | Pressure | 40.196% | 53.769% | 53.030% | 0.01921 |
| confirmation | baseline | 31.268% | 53.636% | 52.584% | 0.01445 |
| confirmation | Pressure | 30.639% | 53.735% | 52.672% | 0.01479 |
| all | baseline | 37.372% | 53.487% | 52.887% | 0.01765 |
| all | Pressure | 36.486% | 53.758% | 53.151% | 0.01903 |

Pressureは0.52 accuracyを7/7、selection scoreを6/7 fold改善した。confirmationは8,475件、mean confidence 53.354%、accuracy 53.735%、calibration gap +0.381ptでWilson区間内、Wilson下限も50%超である。

方向固定確率全体でもBrier、log loss、ECEはdevelopment/confirmation/allの3期間で改善した。fold別改善はそれぞれ5/7、5/7、4/7で、M30 Profileのproper score 7/7ほど安定していない。

## 親Profile 0.52との比較

| period | Profile score | Pressure score |
|---|---:|---:|
| development | 0.01663 | 0.01921 |
| confirmation | 0.01634 | 0.01479 |
| all | 0.01793 | 0.01903 |

Pressureはaccuracy/scoreとも5/7 fold勝ち、developmentとallでProfileを上回った。一方、confirmation合算ではProfile accuracy 53.994%、Pressure 53.735%でProfileが上だった。Pressureの増分は一貫して親を支配していないため、fresh期間でのhead-to-headを昇格条件に含める。

## Nested odds

test2020を初期校正用とし、次fold以前のOOSだけでreliability tableを作るnested検証をtest2021〜2026途中の59,838件で実施した。

| source | Brier | log loss | ECE |
|---|---:|---:|---:|
| baseline model confidence | 0.2495883 | 0.6923239 | 0.319% |
| Pressure model confidence | 0.2495426 | 0.6922317 | 0.250% |
| Pressure hierarchical empirical odds | 0.2496800 | 0.6925076 | 0.718% |

元model confidenceはbaselineより3指標を改善した。階層実績再校正は3指標すべて悪化したため使わない。0.52選別にはmodel confidenceをそのまま使い、authoritative fair oddsには昇格させない。

## Runtime parity

baselineとPressure latest artifactを同じ60/20/20境界・主要設定で生成した。2026-06-01 04:30 UTCはbaseline up 0.521993、Pressure up 0.515687、方向固定25% blend up 0.520416で0.52条件を満たした。

runtime policy上は `prediction_eligible=true` だが、局所odds cellが整合せず、かつ運用認可していないため `odds_calibration_gate_passed=false`、`odds_valid=false`、`strict_prediction_eligible=false` である。artifact parityは通過した。

## 成果物と判断

- 統合baseline: `experiments/next_bar/baseline_m30_complete_001`
- Pressure OOS: `experiments/next_bar/walk_forward_intrabar_pressure_m30_001`
- 通常blend: `experiments/next_bar/ensemble_intrabar_pressure_m30_25_001`
- 方向維持blend: `experiments/next_bar/intrabar_pressure_m30_confidence_blend_001`
- candidate分析: `experiments/next_bar/intrabar_pressure_m30_candidate_analysis.json`
- reliability: `experiments/next_bar/intrabar_pressure_m30_reliability_analysis.json`
- Profile 0.52比較: `experiments/next_bar/intrabar_pressure_vs_profile_m30_052_analysis.json`
- nested odds: `experiments/next_bar/intrabar_pressure_m30_odds_calibration.json`
- latest ensemble: `experiments/next_bar/intrabar_pressure_m30_latest_ensemble_001`
- 固定設定: `methods/next_bar/config/m30_intrabar_pressure_confidence_candidate_v1.json`
- runtime shadow policy: `methods/next_bar/config/m30_intrabar_pressure_runtime_shadow_policy_v1.json`

方向用途は棄却する。0.52 confidenceだけをparallel selective forward candidateとして採用し、fresh期間でbaselineとProfileの両方にaccuracy・selection score・Brier/log lossで劣らない場合だけ昇格を検討する。オッズ認可とpaper policyは変更しない。損失倍率は標準1.0のみとする。
