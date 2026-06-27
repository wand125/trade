# Fixed Horizon Exit Policy

日時: 2026-06-28 08:26 JST

## 目的

前回追加した固定保有 60/240/720 分targetを使い、best holding minutes だけに依存しない exit policy を検証する。

狙い:

- 固定horizonごとのEV面を学習する。
- 各sideで最も高い固定horizon EVをentry scoreにする。
- 選ばれたhorizonを予定exit時刻にする。
- 2025-02で壊れた `asia` / `rollover` には、hard blockではなく追加side marginを試す。

## 実装

`trade_data.backtest` に `fixed_horizon_ev` policy を追加した。

追加CLI:

- `--fixed-horizon-minutes`
- `--long-fixed-horizon-columns`
- `--short-fixed-horizon-columns`
- `--extra-side-margin-rules`

`fixed_horizon_ev` は、sideごとに以下を計算する。

```text
long_score = max(pred_long_fixed_60m, pred_long_fixed_240m, pred_long_fixed_720m)
short_score = max(pred_short_fixed_60m, pred_short_fixed_240m, pred_short_fixed_720m)
```

entry時は高いsideを選び、最大scoreを出したhorizon分だけ保有予定にする。

追加side margin ruleの形式:

```text
session_regime=asia:5,session_regime=rollover:5
```

これは該当regimeだけ、通常の `side_margin` に追加marginを足す。

## Dataset

`data/processed/datasets/xauusd_m1_p1_l1p2/` を 2023-01 から 2025-02 まで再生成した。

設定:

- profit multiplier: 1.0
- loss multiplier: 1.20
- horizon: 24h
- min adjusted edge: 15
- fixed horizons: 60m, 240m, 720m

確認:

- 2024-07 / 2025-02 で固定horizon target列に欠損なし。

## Model

Artifact:

- `experiments/20260627_231921_full_fixed_horizon_targets_p1_l1p2/`

設定:

- target set: `full`
- max iter: 80
- train months: 2023-01..2024-06, 2024-08, 2024-10
- validation months: 2024-07, 2024-09, 2024-11, 2025-01
- fixed test months: 2024-12, 2025-02
- purge label overlap: true
- embargo: 24h
- sample weighting: month_label

固定horizon targetのR2:

| target | valid R2 | test R2 |
|---|---:|---:|
| long fixed 60m | 0.0103 | -0.0074 |
| short fixed 60m | 0.0033 | -0.0149 |
| long fixed 240m | 0.0127 | -0.0070 |
| short fixed 240m | -0.0004 | -0.0125 |
| long fixed 720m | -0.0171 | -0.0991 |
| short fixed 720m | -0.0225 | -0.0797 |

予測精度はまだ弱く、特に720mは汎化していない。

## Validation

まず追加marginなしで `fixed_horizon_ev` をsweepした。

Summary:

- `data/reports/backtests/20260627_232147_model_sweep_summary/`

top by min-pnl:

| entry | side margin | max wait | min rank | barrier | mean pnl | min pnl | min trades | max DD |
|---:|---:|---:|---:|---|---:|---:|---:|---:|
| 2 | 1 | inf | 0 | true | 21.6805 | 12.9000 | 16 | 73.2680 |
| 0 | 1 | inf | 0 | true | 30.6500 | 10.8906 | 27 | 71.3840 |
| 0 | 0 | 4 | 0 | true | 36.3548 | 10.6226 | 31 | 38.8510 |

この段階のfixed testは両月マイナスだった。

次に `session_regime=asia:5,session_regime=rollover:5` の追加side margin付きでsweepした。

Summary:

- `data/reports/backtests/20260627_232445_model_sweep_summary/`

top by min-pnl:

| entry | side margin | max wait | min rank | barrier | extra margin | mean pnl | min pnl | min trades | max DD |
|---:|---:|---:|---:|---|---|---:|---:|---:|---:|
| 2 | 2 | 4 | 0.5 | false | asia/rollover +5 | 27.2219 | 19.1398 | 45 | 50.3740 |
| 2 | 2 | 4 | 0 | false | asia/rollover +5 | 27.4748 | 17.9848 | 47 | 51.2204 |
| 2 | 1 | 4 | 0.5 | false | asia/rollover +5 | 17.2973 | 12.3498 | 47 | 50.3740 |

## Fixed Test

validation top-min候補を固定した。

Policy:

- policy: `fixed_horizon_ev`
- entry threshold: 2
- side margin: 2
- max wait regret: 4
- min entry rank: 0.5
- require profit barrier: false
- extra side margin: `session_regime=asia:5,session_regime=rollover:5`

Results:

| month | adjusted pnl | raw pnl | trades | win rate | profit factor | max DD | forced exits | long pnl | short pnl |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2024-12 | 30.2662 | 43.5420 | 58 | 0.5345 | 1.3800 | 25.2926 | 1 | 31.4940 | -1.2278 |
| 2025-02 | 4.6898 | 35.8250 | 71 | 0.5070 | 1.0251 | 99.4746 | 0 | 17.6144 | -12.9246 |

今回の研究の中では、validationで選んだ同一候補をfixed test 2ヶ月へ適用して、両月ともNoTradeを上回った初回の候補。

ただし2025-02のedgeは薄く、short側はまだマイナス。

## Cost Sensitivity

Cost sensitivity artifacts:

- `data/reports/backtests/20260627_232526_model_cost_sensitivity_2024-12/`
- `data/reports/backtests/20260627_232526_model_cost_sensitivity_2025-02/`

2024-12:

| spread | slippage | delay bars | adjusted pnl |
|---:|---:|---:|---:|
| 0.0 | 0.00 | 0 | 30.2662 |
| 0.0 | 0.10 | 0 | 17.5842 |
| 0.2 | 0.10 | 0 | 4.8282 |
| 0.2 | 0.10 | 1 | -10.1278 |

2025-02:

| spread | slippage | delay bars | adjusted pnl |
|---:|---:|---:|---:|
| 0.0 | 0.00 | 0 | 4.6898 |
| 0.0 | 0.05 | 0 | -3.1102 |
| 0.2 | 0.00 | 1 | 1.4582 |
| 0.2 | 0.10 | 0 | -26.5356 |

コスト耐性は不足。2025-02はわずかなslippageでNoTrade以下になる。

## Failure Analysis

Artifacts:

- `data/reports/backtests/20260627_232556_analyze_fixed_horizon_safe_2024-12/`
- `data/reports/backtests/20260627_232556_analyze_fixed_horizon_safe_2025-02/`

2024-12:

- direction error rate: 0.6379
- exit regret sum: 790.2618
- long pnl: 31.4940
- short pnl: -1.2278
- actual profit barrier hit = 1 のtradeは `+50.9902`
- actual profit barrier hit = 0 のtradeは `-20.7240`

2025-02:

- direction error rate: 0.5211
- exit regret sum: 1377.3402
- long pnl: 17.6144
- short pnl: -12.9246
- `ny_late` が `+12.8040`
- `asia` が `-8.5146`
- `london` が `-1.2412`

読み取り:

- 改善は、方向予測が強くなったというより、追加side marginとentry quality filterで大損を減らした効果が大きい。
- 2025-02のshortはまだ弱い。
- exit regretは依然大きく、fixed horizonだけでは手放し方の問題は解決していない。
- actual profit barrier missの検出・回避が次の主要課題。

## 判断

この候補は、新しい比較基準として採用する価値がある。

ただし本採用ではない。

- 良い点: validationで選んだ候補が 2024-12 / 2025-02 の両test月でプラス。
- 悪い点: 2025-02の利益は薄く、コスト・slippageで消える。
- 悪い点: direction errorとexit regretがまだ大きい。
- 悪い点: short側が弱く、2025-02ではshort pnlがマイナス。

## 次

1. short側だけ追加margin、またはshort専用entry thresholdを導入する。
2. actual barrier missを避けるため、barrier hit probabilityを確率として保存・calibrationする。
3. fixed horizon EVにcalibrationを入れる。
4. cost/slippage込みをvalidation選択条件に入れる。
