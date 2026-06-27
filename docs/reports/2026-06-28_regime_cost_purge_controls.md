# Regime, Cost Sensitivity, and Purged Split Controls

日時: 2026-06-28 06:55 JST

## 目的

汎化レビューで不足として挙げた以下を、実験フローへ接続する。

- regime feature / regime label。
- spread / slippage / execution delay sensitivity。
- purged / embargo split。

## 実装

### Regime

`src/trade_data/regime.py` を追加した。

数値feature:

- `trend_score_240`
- `volatility_score_60`

診断用カテゴリ:

- `trend_regime`: `up`, `down`, `range`, `unknown`
- `volatility_regime`: `high_vol`, `normal_vol`, `low_vol`, `unknown`
- `session_regime`: `asia`, `london`, `ny_overlap`, `ny_late`, `rollover`
- `gap_regime`: `normal_gap`, `micro_gap`, `gap`, `unknown`
- `combined_regime`

`trend_score_240` と `volatility_score_60` は過去rolling特徴から作るため、datasetのfeature columnsに含める。カテゴリ列は主に分析・集計用として保存する。

`prediction_frame` と `analyze-trades` でもregime列を保持し、以下のような出力が可能になった。

- `group_by_trend_regime.csv`
- `group_by_volatility_regime.csv`
- `group_by_session_regime.csv`
- `group_by_gap_regime.csv`
- `group_by_combined_regime.csv`

### Cost / Execution Stress

`BacktestConfig` に以下を追加した。

- `spread_points`
- `slippage_points`
- `execution_delay_bars`

価格調整:

```text
cost_per_side = spread_points / 2 + slippage_points

long entry  = open + cost_per_side
long exit   = open - cost_per_side
short entry = open - cost_per_side
short exit  = open + cost_per_side
```

`execution_delay_bars` は、通常の次足open約定からさらに何bar遅らせるかを表す。

CLI:

```bash
python3 -m trade_data.backtest model-policy \
  --month 2025-02 \
  --predictions path/to/predictions.parquet \
  --spread-points 0.2 \
  --slippage-points 0.1 \
  --execution-delay-bars 1
```

固定policyの感度確認用に `model-cost-sensitivity` を追加した。

```bash
python3 -m trade_data.backtest model-cost-sensitivity \
  --month 2025-02 \
  --predictions path/to/predictions.parquet \
  --policy timed_ev \
  --entry-threshold 15 \
  --spread-points-list 0,0.1,0.2 \
  --slippage-points-list 0,0.05,0.1 \
  --execution-delay-bars-list 0,1
```

### Purged / Embargo Split

`trade_data.modeling train` に以下を追加した。

- `--purge-label-overlap`, default `true`
- `--embargo-hours`, default `0.0`

処理:

- train rows のラベル利用期間が valid/test のラベル期間に重なる場合、trainから削除する。
- valid rows のラベル利用期間が test のラベル期間に重なる場合、validから削除する。
- ラベル利用期間は `entry_timestamp + horizon_hours` までと見なす。
- `embargo_hours` はブロックする期間の前後に追加するbuffer。

これにより、月末の教師ラベルが翌月validation/testの未来pathを使う問題を抑える。

## 注意

既存datasetはregime列を持たない。regime featureを使うにはdataset再生成が必要。

旧datasetでも、purge/embargoとcost stressは使える。ただし `analyze-trades` のregime別集計は、新しいprediction parquetにregime列が含まれる場合だけ出力される。

## 実装検証

実行:

```bash
python3 -m unittest discover tests
git diff --check
python3 -m trade_data.backtest model-cost-sensitivity --help
python3 -m trade_data.modeling train --help
```

結果:

- 40 tests OK。
- diff check OK。
- 追加CLIのhelp表示 OK。

## Dataset Regeneration

1.0/1.2 aligned datasetをregime列込みで再生成した。

Command:

```bash
python3 -m trade_data.dataset build-range \
  --start-month 2023-01 \
  --end-month 2025-02 \
  --min-adjusted-edge 15 \
  --profit-multiplier 1.0 \
  --loss-multiplier 1.2 \
  --output-dir data/processed/datasets/xauusd_m1_p1_l1p2
```

結果:

- months: 2023-01 から 2025-02
- `feature_count`: 49
- 追加feature: `trend_score_240`, `volatility_score_60`
- `regime_counts` をsummaryに保存

## Purge Bug Fix

最初の実装では、複数test月を1つの連続したblocked windowとして扱っていた。そのため、test 2024-12 と 2025-02 の間にある valid 2025-01 が丸ごとpurgeされる問題が出た。

修正:

- `dataset_month` がある場合は、blocked windowを月ごとに分割する。
- 非連続test月の間にあるvalid月は、実際にラベル期間が重ならない限り保持する。

修正後のpurge統計:

| split | before | removed | after |
|---|---:|---:|---:|
| train | 546,537 | 11,044 | 535,493 |
| valid | 119,241 | 6,747 | 112,494 |
| test | 56,204 | 0 | 56,204 |

Valid month rows after purge:

| month | rows |
|---|---:|
| 2024-07 | 31,587 |
| 2024-09 | 28,885 |
| 2024-11 | 25,962 |
| 2025-01 | 26,060 |

## HGB 80iter Result

Artifact:

- `experiments/20260627_215123_policy_iter80_p1_l1p2_regime_purge_e24_v2/`

設定:

- dataset: `data/processed/datasets/xauusd_m1_p1_l1p2`
- target set: `policy`
- max iter: 80
- profit/loss: 1.0 / 1.2
- purge label overlap: true
- embargo: 24h
- train: 2023-01..2024-06, 2024-08, 2024-10
- valid: 2024-07, 2024-09, 2024-11, 2025-01
- test: 2024-12, 2025-02

Model-level test metrics:

- long EV R2: `-0.0198`
- short EV R2: `-0.0894`
- label macro F1: `0.3701`
- calibrated long EV R2: `-0.0766`
- calibrated short EV R2: `-0.1325`

回帰性能はtestで改善していない。

## Validation Sweep

Sweeps:

- `data/reports/backtests/20260627_215158_model_sweep_2024-07/`
- `data/reports/backtests/20260627_215158_model_sweep_2024-09/`
- `data/reports/backtests/20260627_215158_model_sweep_2024-11/`
- `data/reports/backtests/20260627_215158_model_sweep_2025-01/`

Summary:

- 30 trades/fold: `data/reports/backtests/20260627_215228_model_sweep_summary_1/`
- 10 trades/fold: `data/reports/backtests/20260627_215228_model_sweep_summary/`

30 trades/foldではeligibleなし。

10 trades/foldの最上位eligible:

| policy | entry | risk | max wait | min rank | barrier | mean pnl | min pnl | min trades | max DD |
|---|---:|---:|---:|---:|---|---:|---:|---:|---:|
| timed_ev | 15 | 0 | 2 | 0.5 | false | 61.3430 | 32.2858 | 15 | 56.5284 |

Validationは全foldプラスに見えるが、取引数は薄い。

## Fixed Test

Validationで選んだ候補:

```text
timed_ev
entry_threshold=15
side_margin=0
risk_penalty=0
max_wait_regret=2
min_entry_rank=0.5
require_profit_barrier=false
```

Fixed test:

| month | adjusted pnl | raw pnl | trades | win rate | profit factor | max DD |
|---|---:|---:|---:|---:|---:|---:|
| 2024-12 | -35.7010 | -23.2400 | 15 | 0.3333 | 0.5225 | 58.5892 |
| 2025-02 | -47.6716 | -33.1830 | 17 | 0.3529 | 0.4516 | 54.6236 |

NoTradeには届かない。損失は過去の大きな崩れより小さいが、edgeとはみなさない。

多めに取引するeligible候補もtestでは悪化した。

| candidate | month | adjusted pnl | trades | max DD |
|---|---:|---:|---:|---:|
| risk 0.1 / wait inf / rank 0.5 | 2024-12 | -154.9860 | 39 | 183.8798 |
| risk 0.1 / wait inf / rank 0.5 | 2025-02 | -125.5468 | 60 | 167.1474 |

## Regime Failure Analysis

Artifacts:

- `data/reports/backtests/20260627_215257_analyze_regime_purge_v2_2024-12/`
- `data/reports/backtests/20260627_215257_analyze_regime_purge_v2_2025-02/`

Summary:

| month | adjusted pnl | direction error | predicted side error | exit regret | EV overestimate vs realized |
|---|---:|---:|---:|---:|---:|
| 2024-12 | -35.7010 | 0.6000 | 0.6000 | 251.3950 | 18.8642 |
| 2025-02 | -47.6716 | 0.6471 | 0.6471 | 385.2146 | 19.0495 |

Regime:

- 両testとも全tradeが `low_vol` に集中した。
- 2024-12は `range` が 10 trades / `-24.3020`、`up` が 5 trades / `-11.3990`。
- 2025-02は `up` が 5 trades / `-30.1964`、`range` が 11 trades / `-15.3512`。
- 2025-02のsession別では `asia` が 9 trades / `-46.9276`、`rollover` が 5 trades / `-24.8160`、`ny_late` が 3 trades / `+24.0720`。

損失の中心は、以前と同じくdirection error、profit barrier miss、exit regret。regime列により「低ボラ、特に2025-02のasia/rolloverで壊れる」ことが見えるようになった。

## Cost Sensitivity

Artifacts:

- `data/reports/backtests/20260627_215324_model_cost_sensitivity_2024-12/`
- `data/reports/backtests/20260627_215325_model_cost_sensitivity_2025-02/`

2024-12は1bar遅延で偶然損失が縮むケースがあったが、全条件でNoTrade未満。2025-02はspread/slippage/delayで素直に悪化した。

| month | spread | slippage | delay bars | adjusted pnl |
|---|---:|---:|---:|---:|
| 2024-12 | 0.0 | 0.0 | 0 | -35.7010 |
| 2024-12 | 0.2 | 0.1 | 0 | -42.5010 |
| 2024-12 | 0.2 | 0.1 | 1 | -32.0962 |
| 2025-02 | 0.0 | 0.0 | 0 | -47.6716 |
| 2025-02 | 0.2 | 0.1 | 0 | -55.4116 |
| 2025-02 | 0.2 | 0.1 | 1 | -55.5746 |

## 判断

今回の基盤改善は有効。

- regime別に壊れ方を見られるようになった。
- explicit cost / delay stressを定量化できるようになった。
- label overlap purgeを標準学習フローに入れられた。

ただし、モデル成績は改善していない。

- validationでは全foldプラス候補が出る。
- fixed testではNoTradeに負ける。
- direction errorとprofit barrier missが依然として大きい。
- 低ボラ局面、特にasia/rolloverの判断が弱い。

## 次の実験

1. low-vol / asia / rolloverではentry thresholdを上げる、またはNoTrade寄りにするregime gateを試す。
2. direction modelをside/regime別にcalibrateする。
3. profit barrierを0/1予測ではなく確率として保存し、閾値をcalibrateする。
4. 低ボラ局面専用のexit timing targetを追加する。
5. 2024-12/2025-02を見すぎているため、追加holdout月で同じ傾向が出るか確認する。
