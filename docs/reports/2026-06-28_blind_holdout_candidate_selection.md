# Blind Holdout Candidate Selection

日時: 2026-06-28 08:53 JST

## 目的

2024-12 / 2025-02 を繰り返し見たことで、fixed testが最終holdoutとして弱くなっている。

そこで、候補選択基準を先にコード化し、新しいblind holdout月として 2025-03 を追加して検証する。

## 実装

`trade_data.backtest` に `model-candidate-selection` を追加した。

入力:

- no-cost sweep metrics
- cost-aware sweep metrics

評価する条件:

- fold数
- 最低trade数
- forced exit rate
- max drawdown
- no-cost / cost-aware の各fold最低adjusted pnl
- cost-awareでのPnL低下幅
- side別PnLの片側崩れ
- 指定パラメータ周辺のplateau support

今回のplateauは `short_entry_threshold_offset` で見る。

## Dataset

2025-03 の p1/l1.2 fixed horizon dataset を追加生成した。

Artifact:

- `data/processed/datasets/xauusd_m1_p1_l1p2/xauusd_m1_2025-03_h24_edge15.parquet`

Summary:

- rows: `28,972`
- label counts: short `7,663`, flat `4,792`, long `16,517`
- best adjusted pnl mean: `26.3519`
- side score mean: `9.7462`

## Model

Artifact:

- `experiments/20260627_235034_full_fixed_horizon_blind_2025_03_p1_l1p2/`

Train/validは前回fixed horizon modelと同じ。

- train: 2023-01..2024-06, 2024-08, 2024-10
- validation: 2024-07, 2024-09, 2024-11, 2025-01
- blind holdout test: 2025-03
- target set: `full`
- max iter: `80`
- purge label overlap: true
- embargo: 24h
- sample weighting: `month_label`

## Candidate Selection

Validation sweeps:

- no-cost: `data/reports/backtests/20260627_235111_model_sweep_2024-07/` など4ヶ月
- cost-aware: `data/reports/backtests/20260627_235147_model_sweep_2024-07/` など4ヶ月

Candidate selection artifact:

- `data/reports/backtests/20260627_235220_model_candidate_selection/`

事前条件:

- min folds: `4`
- min trades per fold: `10`
- max forced exit rate: `0.04`
- max drawdown: `150`
- min no-cost adjusted pnl per fold: `0`
- min cost-aware adjusted pnl per fold: `0`
- max cost pnl drop: `20`
- max side loss per fold: `45`
- plateau column: `short_entry_threshold_offset`
- plateau radius: `4`
- min plateau neighbors: `1`

選択候補:

| policy | entry | short offset | side margin | base min pnl | cost min pnl | cost drop | side min | plateau support |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| fixed_horizon_ev | 0 | 8 | 1 | 34.5186 | 20.6606 | 13.8580 | -41.3082 | 2 |

## Blind Holdout Result

2025-03 に、validationで選んだ候補を固定適用した。

Artifact:

- `data/reports/backtests/20260627_235231_model_fixed_horizon_ev_2025-03/`

| month | adjusted pnl | raw pnl | trades | win rate | profit factor | max DD | forced exits | long pnl | short pnl |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2025-03 | -49.7004 | -24.2030 | 63 | 0.6190 | 0.6751 | 73.8334 | 2 | -0.3766 | -49.3238 |

NoTrade `0.0` に負けた。

## Cost Sensitivity

Artifact:

- `data/reports/backtests/20260627_235330_model_cost_sensitivity_2025-03/`

| spread | slippage | delay bars | adjusted pnl | long pnl | short pnl |
|---:|---:|---:|---:|---:|---:|
| 0.0 | 0.00 | 0 | -49.7004 | -0.3766 | -49.3238 |
| 0.1 | 0.05 | 0 | -63.2604 | -12.8566 | -50.4038 |
| 0.2 | 0.10 | 1 | -75.9388 | -24.8544 | -51.0844 |

costを入れるほど悪化する。遅延1barでも改善しない。

## Failure Read

損失の中心:

- short 5 trades 合計 `-49.3238`
- long 58 trades 合計 `-0.3766`
- 最大損失: 2025-03-31 01:28 UTC short, adjusted pnl `-49.3248`

Regime別:

| group | count | adjusted pnl | min |
|---|---:|---:|---:|
| asia | 2 | -47.1718 | -49.3248 |
| ny_overlap | 12 | -16.4540 | -11.0400 |
| london | 15 | -5.1160 | -7.6920 |
| ny_late | 34 | +19.0414 | -11.2680 |

Trend別:

| group | count | adjusted pnl | min |
|---|---:|---:|---:|
| range | 40 | -56.0890 | -49.3248 |
| down | 8 | -6.7100 | -7.6920 |
| up | 15 | +13.0986 | -11.2680 |

最大損失trade:

- direction: short
- entry: 2025-03-31 01:28 UTC
- holding: 721 minutes
- regime: `range / low_vol / asia`
- actual best side: long
- actual long best adjusted pnl: `43.243`
- actual short best adjusted pnl: `6.607`
- predicted fixed long EV: `-0.3524`
- predicted fixed short EV: `9.5934`
- predicted short profit barrier hit: `0`

読み取り:

- validationではshort offsetとplateauで壊れにくそうに見えたが、blind月では `asia / range / low_vol` のshort大損を避けられなかった。
- 最大損失tradeは predicted short profit barrier hit が `0` なのにentryしている。`require_profit_barrier=false` の弱点が出た。
- fixed horizon EVだけでは、実際のbest sideがlongの局面をshortとして過大評価した。
- 2025-03は「勝率は高いが負け幅が大きい」失敗で、loss 1.20倍率下ではprofit factorが `0.6751` まで落ちる。

## 判断

今回の候補は採用しない。

この結果は、short offsetとcost-aware selectionだけでは汎化不足であることを示す。

次の本流:

1. `require_profit_barrier` を再評価し、0/1ではなく確率calibrationとして使う。
2. `asia / range / low_vol` のshortをhard blockではなく、追加side marginまたはentry thresholdで抑制する。
3. 721分保有の大損を避けるため、固定horizonだけでなく hazard-like close probability / stop-loss timing target を追加する。
4. candidate selectionへ「predicted profit barrier hitが0のtradeをどれだけ含むか」を追加する。
5. blind holdoutを1ヶ月だけで終えず、2025-04以降も同じ事前条件で評価する。
