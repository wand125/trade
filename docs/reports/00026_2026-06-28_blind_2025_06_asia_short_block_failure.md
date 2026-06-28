# 2025-06 Blind: Asia Short Block Failure

日時: 2026-06-28 10:37 JST
更新日時: 2026-06-28 10:47 JST

## 目的

2025-03で見つけ、2025-04 / 2025-05の追加blindで有効に見えた `short:session_regime=asia` blockを、次のblind monthである 2025-06 に固定適用して反証確認する。

この確認では、2025-06を見た後に新しい採用ルールを決めない。特に `short:london` blockは診断としてのみ扱う。

## Dataset / Model

追加dataset:

- `data/processed/datasets/xauusd_m1_p1_l1p2/xauusd_m1_2025-06_h24_edge15.parquet`
- rows: `28,889`
- label counts: short `14,763`, flat `953`, long `13,173`
- best adjusted pnl mean: `38.3003`
- side score mean: `-0.9106`

追加model:

- `experiments/20260628_013141_full_fixed_horizon_blind_2025_06_barrier_prob_p1_l1p2/`

Train/validationは前回blindと同じ。

- train: 2023-01..2024-06, 2024-08, 2024-10
- validation: 2024-07, 2024-09, 2024-11, 2025-01
- blind holdout test: 2025-06
- target set: `full`
- max iter: `80`
- loss multiplier: `1.20`
- purge label overlap: true
- embargo: 24h

## 固定候補

- policy: `fixed_horizon_ev`
- entry: `0`
- short offset: `6`
- side margin: `1`
- max wait regret: `4`
- min entry rank: `0.5`
- profit barrier threshold: `0.40`
- extra margin: `session_regime=asia:5,session_regime=rollover:5`
- side block: `short:session_regime=asia`

## 2025-06 Blind Result

Artifacts:

- selected asia short block: `data/reports/backtests/20260628_013232_model_fixed_horizon_ev_2025-06_1/`
- no asia short block: `data/reports/backtests/20260628_013232_model_fixed_horizon_ev_2025-06/`
- offset8 reference: `data/reports/backtests/20260628_013232_model_fixed_horizon_ev_2025-06_2/`
- cost sensitivity selected: `data/reports/backtests/20260628_013232_model_cost_sensitivity_2025-06/`
- failure analysis selected: `data/reports/backtests/20260628_013257_side_specific_asia_short_block_2025-06/`
- failure analysis no block: `data/reports/backtests/20260628_013257_no_asia_short_block_2025-06/`

| variant | adjusted pnl | raw pnl | trades | win rate | profit factor | max DD | long pnl | short pnl | worst dir/session | actual miss | calibration overestimate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| selected asia short block | `-100.4662` | `-74.9250` | 15 | 0.5333 | 0.3444 | `133.5832` | `0.5570` | `-101.0232` | `short:london` `-101.2102` | 0.4667 | 0.4667 |
| no asia short block | `-109.9862` | `-75.8850` | 18 | 0.5000 | 0.4625 | `135.9506` | `0.5570` | `-110.5432` | `short:london` `-73.7800` | 0.5000 | 0.5000 |
| offset8 reference | `-80.9672` | `-59.0920` | 11 | 0.5455 | 0.3831 | `114.0842` | `0.5570` | `-81.5242` | `short:london` `-81.5242` | 0.4545 | 0.4545 |

NoTrade `0.0` に大きく負けた。2025-04 / 2025-05で有効だった asia short blockは、2025-06では損失の中心を London shortへ移しただけだった。

Cost sensitivity selected:

| spread | slippage | delay bars | adjusted pnl | trades | profit factor | max DD |
|---:|---:|---:|---:|---:|---:|---:|
| 0.0 | 0.00 | 0 | `-100.4662` | 15 | 0.3444 | `133.5832` |
| 0.1 | 0.05 | 0 | `-103.7488` | 15 | 0.3304 | `136.4658` |
| 0.2 | 0.10 | 1 | `-114.3990` | 15 | 0.3047 | `145.6090` |

## Failure Read

Selected asia short block:

- trade count: `15`
- short trades: `14`
- short adjusted pnl: `-101.0232`
- `direction_error_rate`: `0.6000`
- `predicted_side_error_rate`: `0.6000`
- `profit_barrier_miss`: 7 trades, adjusted pnl `-152.0642`
- `ev_overestimate_vs_realized_mean`: `33.4782`
- `exit_regret_sum`: `397.4972`

Session別:

| session | trades | adjusted pnl | direction error rate | exit regret sum |
|---|---:|---:|---:|---:|
| london | 13 | `-101.2102` | 0.6154 | `342.6842` |
| rollover | 1 | `0.1870` | 1.0000 | `24.0930` |
| ny_late | 1 | `0.5570` | 0.0000 | `30.7200` |

Actual best side別:

| actual best side | trades | adjusted pnl | direction error rate |
|---|---:|---:|---:|
| long | 10 | `-121.7172` | 0.9000 |
| short | 5 | `21.2510` | 0.0000 |

Worst trade:

- entry: `2025-06-02 07:02 UTC`
- direction: short
- adjusted pnl: `-60.4560`
- holding: `528` minutes
- regime: `up / low_vol / london`
- actual best side: long
- actual long best adjusted pnl: `66.180`
- actual short best adjusted pnl: `-0.576`

## Post-hoc Diagnostics

2025-06を見た後の London blockは採用不可だが、損失の移動を確認するため診断だけ実行した。

Artifacts:

- `short:london` block: `data/reports/backtests/20260628_013404_model_fixed_horizon_ev_2025-06/`
- `short:asia,london` block: `data/reports/backtests/20260628_013404_model_fixed_horizon_ev_2025-06_1/`
- all short sessions blocked: `data/reports/backtests/20260628_013405_model_fixed_horizon_ev_2025-06/`

| diagnostic | adjusted pnl | trades | note |
|---|---:|---:|---|
| block `short:london` only | `-36.2062` | 12 | asia short損失が残る |
| block `short:asia,london` | `0.7440` | 2 | trade数が薄すぎる |
| block all short sessions in this candidate | `0.5570` | 1 | 実質NoTrade |

これは「Londonをblockすれば解決」ではなく、short方向の選択が未知月で壊れており、session hard blockを増やすとNoTradeへ近づくだけという読み。

## Validation Back-check

2025-06を見た後に作った診断ルールが、validationで事前に支持されていたかを確認した。

固定候補1点を、4 validation monthsで以下4条件に戻して評価した。

- no block
- `short:session_regime=asia`
- `short:session_regime=london`
- `short:session_regime=asia,short:session_regime=london`

Artifacts:

- validation sweeps: `data/reports/backtests/20260628_013458_model_sweep_2024-07/` から `data/reports/backtests/20260628_013540_model_sweep_2025-01/`
- candidate selection: `data/reports/backtests/20260628_013608_model_candidate_selection/`

Summary:

| side block | base min pnl | base mean pnl | min trades | short min all | direction/session min all | actual miss max | eligible |
|---|---:|---:|---:|---:|---:|---:|---|
| none | `-4.5418` | `34.0009` | 2 | `-6.3276` | `-23.7720` | 1.0000 | false |
| `short:session_regime=asia` | `-4.5418` | `23.6679` | 0 | `-6.3276` | `-23.7720` | 1.0000 | false |
| `short:session_regime=london` | `-19.9560` | `3.9695` | 2 | `-22.0200` | `-23.7720` | 1.0000 | false |
| `short:session_regime=asia,short:session_regime=london` | `-28.8240` | `-6.3636` | 0 | `0.0000` | `-23.7720` | 1.0000 | false |

Validationは London blockを事前採用する根拠を出していない。むしろ London blockは validation mean / min pnl を悪化させている。

## 判断

`short:session_regime=asia` は暫定採用候補から降格する。

理由:

- 2025-06 blindで `-100.4662` とNoTradeに大きく負けた。
- 2025-04 / 2025-05の改善は、asia shortの局所損失を避けた効果であり、方向予測そのものを改善していない。
- 2025-06では同じshort過大評価が London shortへ移動した。
- post-hocに Londonもblockすると損失は消えるが、trade数は2以下で、実質NoTradeに近い。
- validation back-checkでも London blockは事前に支持されていない。

calibration overestimateは2025-06では `0.4667` まで悪化しており、過大評価診断としては有効。ただし小さなfoldでは actual miss / calibration max が 1.0 になりやすく、単純なhard max gateは不安定。support数と一緒に扱う必要がある。

## Next

1. session hard blockを増やす方向はいったん止める。
2. candidate selectionへ short exposure concentration を診断として追加する。例: `short_trade_share`, `max_side_trade_share`, short-only dependence。
3. actual miss / calibration gateは、観測trade数が少ないfoldへの過反応を避けるため、support-awareな指標へ変更する。
4. exit timing targetを、固定horizonだけでなく barrier time / hazard-like close probability へ拡張する。
5. 次のblind月を増やす前に、validation内の選択基準を再設計する。2025-07以降は新基準を固定してから見る。

## 検証

- dataset build 2025-06: OK
- HGB full target train for 2025-06 blind: OK
- fixed candidate backtest: OK
- cost sensitivity: OK
- failure analysis: OK
- validation back-check candidate selection: OK

## 更新: 2026-06-28 10:47 JST

Next 2 / 3 に対応し、short exposure concentration と support-aware barrier gateを追加した。

詳細:

- `docs/reports/00027_2026-06-28_short_exposure_support_aware_gates.md`

主な結果:

- 2025-06 selected `short:session_regime=asia` は `short_trade_share=0.933333` で `short_trade_share_ok=false` になった。
- all short sessions blocked diagnosticは1 tradeだけで、`eligible_base=false` / `eligible_cost=false`。
- smoothed actual miss / calibrationは、1 trade候補を raw 0.0 として過度に楽観しない値 `0.333333` に補正した。
