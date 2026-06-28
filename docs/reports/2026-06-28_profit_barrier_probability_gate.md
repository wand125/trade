# Profit Barrier Probability Gate

日時: 2026-06-28 09:08 JST
更新日時: 2026-06-28 09:26 JST

## 目的

2025-03 blind holdoutで最大損失になったshortは、`pred_short_profit_barrier_hit=0` だったにもかかわらず entry していた。これを受けて、profit barrierを0/1ラベルではなく確率として保存し、entry条件へ閾値付きで使えるようにする。

## 実装

- `trade_data.modeling` の分類target予測に、binary classifier の class `1` probabilityを `pred_<target>_prob` として保存するようにした。
- `ModelPolicyConfig` に `profit_barrier_threshold` を追加した。
- `model-policy` に `--profit-barrier-threshold` を追加した。
- `model-sweep` に `--profit-barrier-thresholds` を追加した。
- `SWEEP_KEY_COLUMNS` とsummary正規化へ `profit_barrier_threshold` を追加し、閾値違いの候補が混ざらないようにした。
- 既存 `docs/reports/*.md` は、ファイル更新時刻を基準に `更新日時` / `Updated` を補正した。

## Model

Artifact:

- `experiments/20260628_000509_full_fixed_horizon_blind_2025_03_barrier_prob_p1_l1p2/`

設定:

- dataset: `data/processed/datasets/xauusd_m1_p1_l1p2/`
- train: 2023-01..2024-06, 2024-08, 2024-10
- validation: 2024-07, 2024-09, 2024-11, 2025-01
- blind test: 2025-03
- target set: `full`
- max iter: 80
- learning rate: 0.05
- sample weighting: `month_label`
- purge label overlap: true
- embargo: 24h

2025-03 test prediction probability:

| column | min | max | mean |
|---|---:|---:|---:|
| `pred_long_profit_barrier_hit_prob` | 0.1049 | 0.5797 | 0.3300 |
| `pred_short_profit_barrier_hit_prob` | 0.0434 | 0.7203 | 0.3501 |

## Validation Selection

Validation 4ヶ月だけで、no-cost / cost-aware sweepを実行した。

Grid:

- policy: `fixed_horizon_ev`
- entry threshold: `0,2`
- short entry offset: `4,6,8,10`
- side margin: `1,2`
- max wait regret: `4`
- min entry rank: `0.5`
- profit barrier threshold: `0.40,0.45,0.50,0.55,0.60`
- profit barrier columns: probability columns
- extra margin: `session_regime=asia:5,session_regime=rollover:5`

Candidate selection:

| short offset | side margin | barrier threshold | base min pnl | base mean pnl | cost min pnl | cost mean pnl | min trades | min side pnl | cost drop | plateau |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 8 | 1 | 0.40 | 22.4864 | 49.7168 | 17.4064 | 43.1869 | 24 | -33.2458 | 5.0800 | 1 |
| 6 | 1 | 0.40 | 15.2908 | 65.2047 | 9.7348 | 58.1559 | 26 | -33.2458 | 5.5560 | 1 |

選択候補:

- `fixed_horizon_ev`
- entry `0`
- short offset `8`
- side margin `1`
- profit barrier threshold `0.40`

Artifacts:

- no-cost sweeps: `data/reports/backtests/20260628_000602_model_sweep_2024-07/`, `...2024-09/`, `...2024-11/`, `...2025-01/`
- cost-aware sweeps: `data/reports/backtests/20260628_000643_model_sweep_2024-07/`, `...2024-09/`, `...2024-11/`, `...2025-01/`
- candidate selection: `data/reports/backtests/20260628_000706_model_candidate_selection/`

## 2025-03 Blind

Selected candidate:

- artifact: `data/reports/backtests/20260628_000729_model_fixed_horizon_ev_2025-03/`
- adjusted pnl: `-29.5462`
- raw pnl: `-14.4330`
- trades: `29`
- win rate: `0.6207`
- profit factor: `0.6742`
- max drawdown: `54.1392`
- forced exits: `0`
- long pnl: `+18.0844`
- short pnl: `-47.6306`

前回blindの `-49.7004` より損失は縮小したが、NoTrade `0.0` には届かない。

Cost sensitivity:

| spread | slippage | delay bars | adjusted pnl | profit factor | max DD |
|---:|---:|---:|---:|---:|---:|
| 0.0 | 0.00 | 0 | -29.5462 | 0.6742 | 54.1392 |
| 0.1 | 0.05 | 0 | -35.7862 | 0.6165 | 59.5792 |
| 0.2 | 0.10 | 1 | -55.7310 | 0.4414 | 76.5640 |

Artifact:

- `data/reports/backtests/20260628_000839_model_cost_sensitivity_2025-03/`

## Failure Analysis

Artifact:

- `data/reports/backtests/20260628_000901_barrier_prob_gate_2025-03/`

Summary:

- total adjusted pnl: `-29.5462`
- long pnl: `+18.0844`
- short pnl: `-47.6306`
- direction error rate: `0.3448`
- predicted side error rate: `0.3793`
- exit regret sum: `692.1412`
- profit barrier miss trades: `15`

最大損失は引き続き 2025-03-31 01:28 UTC のshort。

- adjusted pnl: `-49.3248`
- holding: `721` minutes
- regime: `range / low_vol / asia`
- actual long best pnl: `43.243`
- actual short best pnl: `6.607`
- predicted short 720m fixed EV: `9.5934`
- predicted short barrier probability: `0.4859`
- actual short profit barrier hit: `0`

閾値 `0.50` ならこのtradeは落ちるが、validationでは月10tradesを満たしにくく、blind diagnosticでも `6` trades / adjusted pnl `-39.5282` と悪化した。blindを見た後に `0.50` を採用するのは不可。

## 判断

profit barrier probability gateは損失を縮めたが、採用水準ではない。

今回の主な示唆:

- barrier確率は有効なfilter軸だが、単独では `asia / range / low_vol` のshort大損を消せない。
- 確率閾値を高くするとtrade数が急減し、validation selectionが不安定になる。
- 最大損失は、barrier確率の過信だけでなく、固定horizon 720mのshort EV過大評価とexit timingの遅さが重なったもの。

次は以下を優先する。

1. side-specific regime suppression: `asia / range / low_vol` のshortだけを追加marginまたはblockできるようにする。
2. fixed horizon EVのcalibrationをside/regime別に再検討する。ただし同一validationへの過fitを避ける。
3. exit timing targetを、hazard-like close probability、stop-loss probability、time-to-barrierへ拡張する。
4. candidate selectionへ、actual/predicted profit barrier miss率と、side/regime別の最大損失集中を入れる。

## 更新: 2026-06-28 09:26 JST

このレポートの次アクション1を受けて、side-specific regime suppressionを実装・検証した。

Report:

- `docs/reports/2026-06-28_side_specific_regime_suppression.md`

主な結果:

- `short:trend_regime=range+volatility_regime=low_vol+session_regime=asia` は狭すぎて、2025-03の大損周辺で再entryを許した。
- `short:volatility_regime=low_vol+session_regime=asia` も、`asia / normal_vol` shortへの再entryを許した。
- `short:session_regime=asia` はvalidation選択候補で2025-03 blind adjusted pnl `+18.0748`、35 trades、profit factor `1.2700` まで改善した。
- ただし、このruleは2025-03の失敗を見た後に作ったため、2025-03でのプラスを最終採用根拠にはしない。2025-04以降のblindで事前登録候補として検証する。
