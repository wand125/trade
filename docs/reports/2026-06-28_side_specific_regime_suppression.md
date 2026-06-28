# Side-Specific Regime Suppression

日時: 2026-06-28 09:26 JST
更新日時: 2026-06-28 09:39 JST

## 目的

2025-03 blind holdoutで最大損失になった `asia / range / low_vol` shortを抑える。

profit barrier probability gateは損失を縮めたが、最大損失shortを消し切れなかった。今回は、long/short共通のregime blockではなく、選択sideとregime条件が一致したときだけ追加marginまたはblockを適用する。

## 実装

`trade_data.backtest` の `model-policy` / `model-sweep` に以下を追加した。

- `--side-block-rules`
- `--side-extra-margin-rules`

形式:

```text
--side-block-rules short:session_regime=asia
--side-block-rules short:trend_regime=range+volatility_regime=low_vol+session_regime=asia
--side-extra-margin-rules short:session_regime=asia:5
```

挙動:

- `side:column=value+...` で、選択sideと全条件が一致した時だけentryを禁止する。
- `side:column=value+...:margin` で、選択sideと全条件が一致した時だけ追加side marginを足す。
- blockされたsideの代わりに反対sideへfallbackはしない。現時点では、選択sideが危険regimeなら no-trade にする。
- `model-candidate-selection` の集計keyにも `side_extra_margin_rules` / `side_block_rules` を追加した。

## Model

前回のprofit barrier probability gateと同じモデルを使う。

- model: `experiments/20260628_000509_full_fixed_horizon_blind_2025_03_barrier_prob_p1_l1p2/`
- train: 2023-01..2024-06, 2024-08, 2024-10
- validation: 2024-07, 2024-09, 2024-11, 2025-01
- blind test: 2025-03
- target set: `full`
- evaluation multiplier: profit `1.0`, loss `1.20`

共通設定:

- policy: `fixed_horizon_ev`
- entry threshold grid: `0,2`
- short offset grid: `4,6,8,10`
- side margin grid: `1,2`
- max wait regret: `4`
- min entry rank: `0.5`
- require profit barrier: true
- profit barrier threshold grid: `0.40,0.45,0.50,0.55,0.60`
- profit barrier columns: probability columns
- extra margin: `session_regime=asia:5,session_regime=rollover:5`

## Validation Attempts

### Narrow Rule

Rule:

```text
short:trend_regime=range+volatility_regime=low_vol+session_regime=asia
```

Artifacts:

- no-cost sweeps: `data/reports/backtests/20260628_001626_model_sweep_2024-07/`, `...2024-09/`, `...2024-11/`, `...2025-01/`
- cost-aware sweeps: `data/reports/backtests/20260628_001708_model_sweep_2024-07/`, `...2024-09/`, `...2024-11/`, `...2025-01/`
- candidate selection: `data/reports/backtests/20260628_001732_model_candidate_selection/`
- 2025-03 blind: `data/reports/backtests/20260628_001750_model_fixed_horizon_ev_2025-03/`

Validation選択は前回とほぼ同じ `entry=0`, `short offset=8`, `side_margin=1`, `barrier=0.40`。

2025-03 blind:

- adjusted pnl: `-27.4534`
- raw pnl: `-12.6890`
- trades: `29`
- profit factor: `0.6901`
- max drawdown: `52.0464`

診断:

- 2025-03-31 01:28 UTC のshortは抑制できた。
- しかし `01:35 UTC` で `trend_regime` が `up` に変わった後、同じasia/low_vol系のshortへ再entryした。
- 条件が瞬間regimeに依存しすぎており、最大損失の周辺局面を消し切れない。

### Medium Rule

Rule:

```text
short:volatility_regime=low_vol+session_regime=asia
```

Artifacts:

- no-cost sweeps: `data/reports/backtests/20260628_001858_model_sweep_2024-07/`, `...2024-09/`, `...2024-11/`, `...2025-01/`
- cost-aware sweeps: `data/reports/backtests/20260628_001939_model_sweep_2024-07/`, `...2024-09/`, `...2024-11/`, `...2025-01/`
- candidate selection: `data/reports/backtests/20260628_002001_model_candidate_selection/`
- 2025-03 blind: `data/reports/backtests/20260628_002018_model_fixed_horizon_ev_2025-03/`

Validation top:

| entry | short offset | side margin | barrier | base min pnl | base mean pnl | cost min pnl | cost mean pnl | min trades |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 8 | 1 | 0.40 | 22.4864 | 49.8413 | 17.4064 | 43.6514 | 23 |

2025-03 blind:

- adjusted pnl: `-26.8930`
- raw pnl: `-12.2220`
- trades: `29`
- profit factor: `0.6945`
- max drawdown: `51.4860`

診断:

- `asia / low_vol` shortは抑制した。
- しかし `2025-03-31 02:17 UTC` に `asia / normal_vol` shortへ再entryし、`-46.6716` の大損が残った。
- low_vol条件だけでは不十分。

### Strong Rule

Rule:

```text
short:session_regime=asia
```

Artifacts:

- no-cost sweeps: `data/reports/backtests/20260628_002115_model_sweep_2024-07/`, `...2024-09/`, `...2024-11/`, `...2025-01/`
- cost-aware sweeps: `data/reports/backtests/20260628_002157_model_sweep_2024-07/`, `data/reports/backtests/20260628_002156_model_sweep_2024-09/`, `...2024-11/`, `...2025-01/`
- candidate selection: `data/reports/backtests/20260628_002217_model_candidate_selection/`

Validation-selected candidate:

| entry | short offset | side margin | barrier | base min pnl | base mean pnl | cost min pnl | cost mean pnl | min trades | short min |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 6 | 1 | 0.40 | 15.2708 | 54.0920 | 9.9508 | 47.6421 | 24 | -9.1356 |

Reference candidate:

| entry | short offset | side margin | barrier | base min pnl | base mean pnl | cost min pnl | cost mean pnl | min trades | short min |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 0 | 8 | 1 | 0.40 | 5.2322 | 39.2400 | 0.8022 | 33.2602 | 20 | -1.6800 |

`offset=6` がvalidation選択。`offset=8` は2025-03 blindでは良いが、validationの順位では2番目なので参考値に留める。

## 2025-03 Blind

Validation-selected `offset=6`:

- artifact: `data/reports/backtests/20260628_002235_model_fixed_horizon_ev_2025-03/`
- adjusted pnl: `+18.0748`
- raw pnl: `+29.2330`
- trades: `35`
- win rate: `0.6000`
- profit factor: `1.2700`
- max drawdown: `44.6526`
- forced exits: `0`
- long pnl: `+18.0844`
- short pnl: `-0.0096`

Reference `offset=8`:

- artifact: `data/reports/backtests/20260628_002236_model_fixed_horizon_ev_2025-03/`
- adjusted pnl: `+27.1356`
- raw pnl: `+34.0280`
- trades: `28`
- win rate: `0.6429`
- profit factor: `1.6562`
- max drawdown: `24.4644`
- forced exits: `0`
- long pnl: `+18.0844`
- short pnl: `+9.0512`

## Cost Sensitivity

Validation-selected `offset=6`:

| spread | slippage | delay bars | adjusted pnl | trades | profit factor | max DD |
|---:|---:|---:|---:|---:|---:|---:|
| 0.0 | 0.00 | 0 | 18.0748 | 35 | 1.2700 | 44.6526 |
| 0.1 | 0.05 | 0 | 10.5148 | 35 | 1.1496 | 48.6926 |
| 0.2 | 0.10 | 1 | -6.1046 | 35 | 0.9208 | 53.9950 |

Artifact:

- `data/reports/backtests/20260628_002255_model_cost_sensitivity_2025-03/`

Reference `offset=8`:

| spread | slippage | delay bars | adjusted pnl | trades | profit factor | max DD |
|---:|---:|---:|---:|---:|---:|---:|
| 0.0 | 0.00 | 0 | 27.1356 | 28 | 1.6562 | 24.4644 |
| 0.1 | 0.05 | 0 | 21.1356 | 28 | 1.4831 | 26.3044 |
| 0.2 | 0.10 | 1 | 5.4936 | 28 | 1.1122 | 28.4194 |

Artifact:

- `data/reports/backtests/20260628_002255_model_cost_sensitivity_2025-03_1/`

## Failure Analysis

Artifact:

- `data/reports/backtests/20260628_002507_side_specific_asia_short_block_2025-03/`

Validation-selected `offset=6`:

- trade count: `35`
- total adjusted pnl: `+18.0748`
- long adjusted pnl: `+18.0844`
- short adjusted pnl: `-0.0096`
- direction error rate: `0.4286`
- predicted side error rate: `0.4571`
- exit regret sum: `702.5012`
- best side regret sum: `932.9262`
- EV overestimate vs realized mean: `2.0183`
- profit barrier miss trades: `19`

解釈:

- `asia short block` は、2025-03の最大short損失をほぼ消した。
- ただしdirection error、predicted side error、exit regretはまだ大きい。
- よって今回の改善は「方向予測がよくなった」よりも、「壊れやすい時間帯のshortを no-trade にした」効果が中心。

## 判断

`short:session_regime=asia` は今回のlineで初めて2025-03 blindのNoTradeを上回った。

ただし、これは2025-03の最大損失を見た後に作った抑制ルールである。したがって、2025-03でのプラスを最終採用根拠にはしない。次のblind monthで事前登録候補として検証する。

採用候補としての扱い:

- validation-selectedは `entry=0`, `short offset=6`, `side_margin=1`, `barrier threshold=0.40`, `side block=short:session_regime=asia`
- 2025-03では NoTradeを上回ったが、コスト最悪条件では負ける。
- `offset=8` は2025-03ではより良いが、blindを見た後の選択になるため本採用しない。

## 更新: 2026-06-28 09:39 JST

2025-03で事後的に見つけた `short:session_regime=asia` を、2025-04 / 2025-05 のblindで事前登録候補として検証した。

追加dataset:

- `data/processed/datasets/xauusd_m1_p1_l1p2/xauusd_m1_2025-04_h24_edge15.parquet`
- `data/processed/datasets/xauusd_m1_p1_l1p2/xauusd_m1_2025-05_h24_edge15.parquet`

追加model:

- 2025-04: `experiments/20260628_003331_full_fixed_horizon_blind_2025_04_barrier_prob_p1_l1p2/`
- 2025-05: `experiments/20260628_003756_full_fixed_horizon_blind_2025_05_barrier_prob_p1_l1p2/`

固定候補:

- policy: `fixed_horizon_ev`
- entry: `0`
- short offset: `6`
- side margin: `1`
- max wait regret: `4`
- min entry rank: `0.5`
- profit barrier threshold: `0.40`
- extra margin: `session_regime=asia:5,session_regime=rollover:5`
- side block: `short:session_regime=asia`

### 2025-04 Blind

Artifacts:

- selected: `data/reports/backtests/20260628_003401_model_fixed_horizon_ev_2025-04/`
- no asia short block: `data/reports/backtests/20260628_003401_model_fixed_horizon_ev_2025-04_1/`
- offset8 reference: `data/reports/backtests/20260628_003402_model_fixed_horizon_ev_2025-04/`
- cost sensitivity: `data/reports/backtests/20260628_003424_model_cost_sensitivity_2025-04/`
- failure analysis: `data/reports/backtests/20260628_003423_side_specific_asia_short_block_2025-04/`

| variant | adjusted pnl | raw pnl | trades | win rate | profit factor | max DD | long pnl | short pnl |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| selected asia short block | 56.3148 | 81.4040 | 31 | 0.5806 | 1.3741 | 56.7380 | 55.1940 | 1.1208 |
| no asia short block | -24.5976 | 19.2370 | 38 | 0.5789 | 0.9065 | 109.2280 | 55.1940 | -79.7916 |
| offset8 reference | 10.4808 | 32.2240 | 22 | 0.5000 | 1.0803 | 74.0872 | 55.1940 | -44.7132 |

Cost sensitivity selected:

| spread | slippage | delay bars | adjusted pnl | trades | profit factor | max DD |
|---:|---:|---:|---:|---:|---:|---:|
| 0.0 | 0.00 | 0 | 56.3148 | 31 | 1.3741 | 56.7380 |
| 0.1 | 0.05 | 0 | 49.5948 | 31 | 1.3228 | 57.8980 |
| 0.2 | 0.10 | 1 | 51.5630 | 32 | 1.3202 | 61.4640 |

Regime diagnosis:

- blockなしでは `asia` shortが 14 trades / adjusted pnl `-106.2104`。
- blockありでは `asia` shortが0 tradesになり、short合計は `+1.1208` まで改善。
- 残る損失は主に `london` short。selectedの `london` shortは 19 trades / adjusted pnl `-19.0052`。
- failure analysisでは direction error rate `0.5161`、predicted side error rate `0.5484`、exit regret sum `1183.4512`。PnLは良いが、方向予測自体は強くない。

### 2025-05 Blind

Artifacts:

- selected: `data/reports/backtests/20260628_003824_model_fixed_horizon_ev_2025-05/`
- no asia short block: `data/reports/backtests/20260628_003824_model_fixed_horizon_ev_2025-05_1/`
- offset8 reference: `data/reports/backtests/20260628_003824_model_fixed_horizon_ev_2025-05_2/`
- cost sensitivity: `data/reports/backtests/20260628_003846_model_cost_sensitivity_2025-05/`
- failure analysis: `data/reports/backtests/20260628_003846_side_specific_asia_short_block_2025-05/`

| variant | adjusted pnl | raw pnl | trades | win rate | profit factor | max DD | long pnl | short pnl |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| selected asia short block | 83.0630 | 109.8070 | 28 | 0.6429 | 1.5176 | 53.2900 | 19.8400 | 63.2230 |
| no asia short block | -57.6474 | -0.1360 | 34 | 0.6176 | 0.8329 | 115.7496 | 19.8400 | -77.4874 |
| offset8 reference | 7.1750 | 26.1870 | 22 | 0.6364 | 1.0629 | 61.9440 | 19.8400 | -12.6650 |

Cost sensitivity selected:

| spread | slippage | delay bars | adjusted pnl | trades | profit factor | max DD |
|---:|---:|---:|---:|---:|---:|---:|
| 0.0 | 0.00 | 0 | 83.0630 | 28 | 1.5176 | 53.2900 |
| 0.1 | 0.05 | 0 | 77.0270 | 28 | 1.4723 | 54.6500 |
| 0.2 | 0.10 | 1 | 68.2500 | 28 | 1.4205 | 55.3260 |

Regime diagnosis:

- blockなしでは `asia` shortが 15 trades / adjusted pnl `-100.5254`。
- blockありでは `asia` shortが0 tradesになり、short合計は `+63.2230` まで改善。
- selectedの `london` shortは 16 trades / adjusted pnl `+40.6290`。
- failure analysisでは direction error rate `0.3214`、predicted side error rate `0.3214`、exit regret sum `869.0450`。

### 更新判断

2025-04 / 2025-05 の追加blindは、`short:session_regime=asia` が偶然の2025-03専用ruleではない可能性を強めた。

一方で、これは「XAUUSDのasia session shortに構造的に弱い」という執行・regime仮説であり、モデルの方向予測が十分に良いことを意味しない。特に2025-04では direction errorが高く、残る課題は exit timing と london short の損失制御。

現時点の扱い:

- `short:session_regime=asia` は暫定採用候補へ昇格する。
- ただし標準評価には、必ず cost sensitivity と side/session別PnLを含める。
- `short offset=8` は2025-04/05でもselectedより悪いため採用しない。
- 次はcandidate selectionへ side/session別損失集中を組み込み、今回のようなruleをvalidation内で機械的に検出できるようにする。

## Next Actions

1. `model-candidate-selection` にside/session別損失集中を追加し、`asia short` のような抑制候補をvalidation内で検出する。
2. exit timing targetを追加し、block後にも残る exit regretを減らす。
3. コスト条件を標準選択に入れる。少なくとも spread `0.1` / slippage `0.05` / delay `0` を通常評価へ昇格する。
4. 2025-06以降も追加blindとして継続確認する。
