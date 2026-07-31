# Holding Risk Overlay

日時: 2026-06-29 18:06 JST
更新日時: 2026-06-29 18:06 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻である `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## 目的

`00156` で `pred_hit_actual_miss * q75 high-overestimate` をentry riskへ足す方式は未使用月2025-06で反証された。

ただし失敗の中身は、entry方向そのものよりも、short側のprofit-barrier/EV過大評価とexit/holdingの問題に見える。今回は同じsignalをentry penaltyではなく、MLP予測保有時間の上限capとして使う。

## 実装

`scripts/experiments/holding_risk_overlay.py` を追加した。

処理:

1. q75 high-overestimate predictionを複数parquetから結合する。
2. `pred_trade_failure_pred_hit_actual_miss_prob * pred_trade_overestimate_high_q75_prob` をside別riskとして計算する。
3. threshold sourceはvalidation OOFの2025-02..2025-04だけに固定し、side別quantileを作る。
4. riskがthreshold以上のsideだけ、`pred_mlp_<side>_exit_event_minutes` を `60/120/240` 分などでcapする。
5. `both`, `long_only`, `short_only` のside modeを比較する。
6. 既存の標準policy条件でbacktestし、metricsとdeltaを保存する。

評価条件:

- profit multiplier: `1.0`
- loss multiplier: `1.2`
- spread: `0.2`
- slippage: `0.1`
- execution delay: `1`
- entry threshold: `12`
- short threshold offset: `6`
- side margin: `5`
- MLP holding guard: `30..480m`
- fixed-horizon source: max of `60/240/720m`

## Threshold

threshold sourceは2025-02..2025-04のchronological q75 OOF prediction。2025-05/06/07にはこのthresholdを固定適用した。

| side | quantile | threshold | source rows |
|---|---:|---:|---:|
| long | `0.75` | `0.006284` | 85361 |
| short | `0.75` | `0.007846` | 85361 |
| long | `0.90` | `0.006539` | 85361 |
| short | `0.90` | `0.119474` | 85361 |

2025-07 fixed applyではshort active率が `6.75%` まで下がった。2025-02..2025-06の評価時よりsignal発火は薄い。

## 2025-02..2025-06 Grid

まずboth sideをcapしたところ、`q0.75 cap60 risk0` はmax DDを大きく縮めたが、long側を壊してtotal PnLはrisk0を下回った。

| label | total PnL | min month | max DD | trades |
|---|---:|---:|---:|---:|
| risk0 | `222.1276` | `-61.3708` | `259.0392` | 529 |
| baseline risk5 | `203.3466` | `-48.2052` | `224.7524` | 506 |
| both q0.75 cap60 risk0 | `200.8008` | `-47.5324` | `145.4232` | 657 |
| both q0.75 cap60 risk5 | `170.9660` | `-43.7684` | `146.3352` | 643 |

deltaではboth q0.75 cap60 risk0が2025-04を `-38.6926 -> 68.5380` に改善した一方、2025-02/03を大きく削った。主因はlong側までcapして悪い追加longを増やしたこと。

そこでshort-onlyに限定した。

| label | total PnL | min month | max DD | trades |
|---|---:|---:|---:|---:|
| short-only q0.75 cap60 risk0 | `314.7458` | `-47.5324` | `145.4232` | 590 |
| short-only q0.75 cap60 risk5 | `281.7134` | `-43.7684` | `146.3352` | 567 |
| short-only q0.75 cap120 risk0 | `250.6894` | `-57.8344` | `213.4128` | 549 |
| short-only q0.75 cap120 risk5 | `250.5184` | `-43.0848` | `198.9120` | 531 |
| short-only q0.75 cap240 risk0 | `236.5290` | `-63.7828` | `257.9744` | 531 |
| risk0 | `222.1276` | `-61.3708` | `259.0392` | 529 |
| short-only q0.75 cap240 risk5 | `210.3064` | `-49.3488` | `224.0836` | 509 |
| baseline risk5 | `203.3466` | `-48.2052` | `224.7524` | 506 |

月別:

| label | 2025-02 | 2025-03 | 2025-04 | 2025-05 | 2025-06 |
|---|---:|---:|---:|---:|---:|
| risk0 | `141.4436` | `60.2172` | `-38.6926` | `-61.3708` | `120.5302` |
| baseline risk5 | `113.1642` | `27.1660` | `-0.2248` | `-48.2052` | `111.4464` |
| short-only q0.75 cap60 risk0 | `114.5970` | `49.6982` | `68.5380` | `-47.5324` | `129.4450` |
| short-only q0.75 cap60 risk5 | `98.3160` | `14.9458` | `83.3158` | `-43.7684` | `128.9042` |

short-only q0.75 cap60 risk0は2025-02/03を削るが、2025-04/05/06の改善が大きく、total/min/DDの全てでrisk0とbaseline risk5を上回った。

## Delta Diagnosis

short-only q0.75 cap60 risk0 vs risk0:

| month | delta | base PnL | candidate PnL | base trades | candidate trades |
|---|---:|---:|---:|---:|---:|
| 2025-02 | `-26.8466` | `141.4436` | `114.5970` | 113 | 137 |
| 2025-03 | `-10.5190` | `60.2172` | `49.6982` | 110 | 119 |
| 2025-04 | `+107.2306` | `-38.6926` | `68.5380` | 78 | 91 |
| 2025-05 | `+13.8384` | `-61.3708` | `-47.5324` | 107 | 114 |
| 2025-06 | `+8.9148` | `120.5302` | `129.4450` | 121 | 129 |

主な改善:

- 2025-04 `common short/range_normal_vol`: `-77.8268 -> +30.0540`, delta `+107.8808`
- 2025-04 `common short/up_normal_vol`: `-60.3224 -> -21.4398`, delta `+38.8826`
- 2025-05 `only_base short/up_normal_vol`: 悪いbase trade `-36.6300` を消した
- 2025-06 `only_candidate short/up_normal_vol`: `+24.8600`

主な悪化:

- 2025-02 `only_candidate short/range_low_vol`: `-32.8810`
- 2025-02 `only_candidate short/up_low_vol`: `-28.8312`
- 2025-03 `only_candidate short/up_normal_vol`: `-24.8160`
- 2025-03 `only_base long/range_normal_vol`: `+27.0130` を失った

結論として、short側exit短縮は特定のshort損失を大きく改善するが、一玉制約により追加shortや後続long喪失も発生する。hard adoptionには追加のcontext filterが必要。

## 2025-07 Fixed Check

2025-07は現行schemaのpredictionが不足していたため、同じHGB/MLP設定でdatasetとpredictionを再生成し、stateful/failure/quality/q75をapplyした。

固定適用結果:

| label | PnL | max DD | trades | win rate |
|---|---:|---:|---:|---:|
| short-only q0.75 cap60 risk5 | `16.7946` | `110.1244` | 129 | `0.4961` |
| baseline risk5 | `8.2858` | `110.1244` | 127 | `0.5039` |
| short-only q0.75 cap60 risk0 | `-0.8914` | `105.6078` | 135 | `0.4889` |
| risk0 | `-9.4002` | `105.6078` | 133 | `0.4962` |

delta:

| base | candidate | delta | added positive | added negative | removed positive | removed negative |
|---|---|---:|---:|---:|---:|---:|
| risk0 | short-only cap60 risk0 | `+8.5088` | `45.6700` | `-7.9716` | `15.3270` | `-1.8564` |
| risk5 | short-only cap60 risk5 | `+8.5088` | `45.6700` | `-7.9716` | `15.3270` | `-1.8564` |

2025-07の改善は小さいが、同じ固定ルールで符号はプラス。主因は `only_candidate short/range_low_vol +27.6300` と `common short/range_low_vol +1.8080`。ただし `common short/up_low_vol` は `+16.5070 -> -1.0200` と悪化し、`only_base long/down_low_vol +11.1406` も落としている。

## 判断

1. q75/predhit interactionはentry risk penaltyとしては不採用だが、short側exit/holding capとしては有望なsignalになった。
2. `short-only q0.75 cap60 risk0` は2025-02..2025-06で total/min/DDを同時改善し、2025-07固定でも小幅改善した。
3. ただし2025-02/03では悪化し、2025-07の改善も小さい。標準policyへ即採用しない。
4. 固定候補として次の未使用月へ進める。次は2025-08以降、またはwalk-forwardでthresholdを月順更新する。
5. 次の改良はcapをさらに調整することではなく、short-only capを発動するcontextを絞ること。特に `short/range_low_vol` と `short/range_normal_vol` は改善が出る一方、`short/up_low_vol` と一部 `short/up_normal_vol` で悪化する。

## Artifacts

- script: `scripts/experiments/holding_risk_overlay.py`
- both-side grid: `data/reports/modeling/20260629_084841_holding_risk_overlay_2025_02_06/`
- both-side backtests: `data/reports/backtests/20260629_084841_holding_risk_overlay_2025_02_06/`
- both-side cap60 risk0 delta: `data/reports/backtests/20260629_085037_holding_q075_cap60_risk0_delta_2025_02_06/`
- short-only grid: `data/reports/modeling/20260629_085141_holding_risk_overlay_short_only_2025_02_06/`
- short-only backtests: `data/reports/backtests/20260629_085141_holding_risk_overlay_short_only_2025_02_06/`
- short-only cap60 risk0 delta: `data/reports/backtests/20260629_085243_holding_short_only_q075_cap60_risk0_delta_2025_02_06/`
- 2025-07 dataset: `data/processed/datasets/xauusd_m1_p1_l1p2_policy_combined/xauusd_m1_2025-07_h24_edge15.parquet`
- HGB 2025-07: `experiments/20260629_090245_policy_combined_side_exit_test_2025_07/`
- MLP 2025-07: `experiments/20260629_090311_shared_mlp_hgb_split_test_2025_07/`
- hybrid 2025-07: `data/reports/modeling/20260629_hgb_mlp_exit_hybrid_2025_07/`
- stateful 2025-07: `data/reports/modeling/20260629_090355_stateful_risk_mean_match_session_floor_lowered_apply_2025_07/`
- failure 2025-07: `experiments/20260629_090448_trade_failure_pred_hit_ev_overestimate_highcost_risk5_apply_2025_07/`
- quality 2025-07: `experiments/20260629_090522_trade_quality_with_failure_prob_highcost_risk5_apply_2025_07/`
- q75 2025-07: `experiments/20260629_090551_trade_overestimate_high_q75_expanding_min3_highcost_risk5_apply_2025_07/`
- fixed 2025-07 holding overlay: `data/reports/modeling/20260629_090604_holding_risk_overlay_short_only_fixed_2025_07/`
- fixed 2025-07 backtests: `data/reports/backtests/20260629_090604_holding_risk_overlay_short_only_fixed_2025_07/`
- fixed 2025-07 delta risk0: `data/reports/backtests/20260629_090635_holding_short_only_q075_cap60_risk0_delta_2025_07/`
- fixed 2025-07 delta risk5: `data/reports/backtests/20260629_090635_holding_short_only_q075_cap60_risk5_delta_2025_07/`

## 検証

- `python3 -m py_compile scripts/experiments/holding_risk_overlay.py`: pass
- `python3 scripts/experiments/holding_risk_overlay.py`: pass
- `python3 scripts/experiments/holding_risk_overlay.py --side-modes short_only --threshold-quantiles 0.75 --caps 60,120,240`: pass
- `python3 scripts/experiments/holding_risk_overlay.py --months 2025-07 --side-modes short_only --threshold-quantiles 0.75 --caps 60`: pass
- `python3 -m trade_data.backtest model-trade-delta`: pass, 4 runs

## 次の作業

1. `short-only q0.75 cap60` を固定候補として2025-08へ再探索なしで適用する。
2. 発動contextを絞る。候補は `short/range_low_vol`, `short/range_normal_vol` を残し、`short/up_low_vol` を弱める方向。
3. cap値の追加探索は後回し。まずside/contextの一般化を確認する。
4. risk5はprofit最大化signalとして弱いので、holding overlayはrisk0とrisk5を併記し、標準判断はtotal/min/DDの3軸で行う。
