# Regime Gate Experiment

日付: 2026-06-28 JST

## 目的

前回の失敗trade分析で、testの損失が `low_vol`、`asia`、`rollover` に偏っていた。そこで、特定regimeでは新規entryしない hard gate を実装し、損失回避に効くかを確認する。

## 実装

`model-policy` / `model-sweep` に以下のentry gateを追加した。

- `--block-trend-regimes`
- `--block-volatility-regimes`
- `--block-session-regimes`
- `--block-gap-regimes`
- `--block-combined-regimes`

指定値はカンマ区切り。例:

```bash
python3 -m trade_data.backtest model-policy \
  --month 2025-02 \
  --predictions experiments/20260627_215123_policy_iter80_p1_l1p2_regime_purge_e24_v2/predictions_test.parquet \
  --policy timed_ev \
  --entry-threshold 15 \
  --max-wait-regret 2 \
  --min-entry-rank 0.5 \
  --block-session-regimes asia,rollover
```

gateは `quality_ok` に合成し、新規entryだけを抑制する。保有中のexit判定は変えない。

`model-sweep-summary` では block条件もpolicy keyに含めるため、gateあり/なしを混ぜずに集計する。

## 検証

```bash
python3 -m unittest discover tests
git diff --check
```

結果:

- 41 tests OK。
- diff check OK。

## Validation Sweep

対象モデル:

- `experiments/20260627_215123_policy_iter80_p1_l1p2_regime_purge_e24_v2/`

validation:

- 2024-07
- 2024-09
- 2024-11
- 2025-01

条件:

- `timed_ev`
- `entry_threshold`: 10, 15, 20
- `side_margin`: 0, 5
- `risk_penalty`: 0, 0.1
- `max_wait_regret`: 2, 4, inf
- `min_entry_rank`: 0, 0.5
- `require_profit_barrier`: false, true
- each fold 10 trades以上、forced exit 0、max drawdown 100以下、各fold PnL 0以上

Top eligible:

| gate | policy | entry | side margin | risk | max wait | min rank | mean pnl | min pnl | min trades | max DD |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `asia,rollover` | timed_ev | 15 | 0 | 0.1 | 4 | 0 | 31.3258 | 21.4868 | 16 | 86.8664 |
| `asia` | timed_ev | 15 | 0 | 0.1 | 4 | 0.5 | 40.0143 | 16.6970 | 17 | 86.2208 |
| `rollover` | timed_ev | 15 | 0 | 0.0 | 2 | 0.5 | 62.6525 | 38.4034 | 15 | 50.5008 |

Artifacts:

- `data/reports/backtests/20260627_220223_model_sweep_summary/`
- `data/reports/backtests/20260627_220343_model_sweep_summary/`
- `data/reports/backtests/20260627_220443_model_sweep_summary/`

## Fixed Test

validation top候補を固定して、2024-12 / 2025-02 testへ適用した。

| gate | params | 2024-12 adjusted | 2024-12 trades | 2025-02 adjusted | 2025-02 trades | 判断 |
|---|---|---:|---:|---:|---:|---|
| `asia,rollover` | entry 15, risk 0.1, wait 4, rank 0 | -121.9240 | 23 | 58.5242 | 31 | test月間で不安定 |
| `asia` | entry 15, risk 0.1, wait 4, rank 0.5 | -127.9708 | 24 | 63.3104 | 35 | 2024-12で悪化 |
| `rollover` | entry 15, risk 0, wait 2, rank 0.5 | -37.5214 | 15 | -38.0992 | 14 | 改善せず |
| `asia,rollover` | 前回候補: entry 15, risk 0, wait 2, rank 0.5 | 5.8384 | 7 | 24.0720 | 3 | 損失回避には効くが薄すぎる |

Fixed test artifacts:

- `data/reports/backtests/20260627_220238_model_timed_ev_2024-12/`
- `data/reports/backtests/20260627_220238_model_timed_ev_2025-02/`
- `data/reports/backtests/20260627_220251_model_timed_ev_2024-12/`
- `data/reports/backtests/20260627_220251_model_timed_ev_2025-02/`
- `data/reports/backtests/20260627_220355_model_timed_ev_2024-12/`
- `data/reports/backtests/20260627_220355_model_timed_ev_2025-02/`
- `data/reports/backtests/20260627_220457_model_timed_ev_2024-12/`
- `data/reports/backtests/20260627_220457_model_timed_ev_2025-02/`

## 判断

hard regime gate は実装として有用。validation/test診断で「特定regimeを消すとどうなるか」を短時間で試せる。

ただし、採用policyとしてはまだ弱い。

- `asia` / `asia,rollover` は 2025-02 を改善するが、2024-12を大きく悪化させる。
- `rollover` はvalidationでは強いがtestではNoTradeに負ける。
- 前回候補に `asia,rollover` を足すと両testはプラス化するが、3から7 tradesで薄すぎる。

よって、hard gateは本流に採用しない。次は hard block ではなく、side/regime別に予測EVをcalibrate/shrinkし、regimeごとの閾値をvalidation内OOFで決める。

## 次

1. side/regime別EV calibrationを実装する。
2. hard blockではなく、regime別 `entry_threshold_offset` または predicted EV shrinkage を試す。
3. calibrationはtest月を見ず、validation内OOFでfit月と選択月を分ける。
