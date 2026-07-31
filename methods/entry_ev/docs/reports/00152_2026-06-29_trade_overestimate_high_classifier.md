# Trade Overestimate High Classifier

日時: 2026-06-29 16:37 JST
更新日時: 2026-06-29 16:39 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻である `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## 目的

`00151` では、chronological amount modelの予測スケールが低く、q90は発火せず、q75は発火するがpolicyを悪化させた。

今回はamount値を直接penaltyにせず、selected tradeの `trade_overestimate_target_amount = max(pred_taken_ev - adjusted_pnl, 0)` がside別fit分布の高分位を超えるかを分類targetにする。foldごとの閾値はholdoutより前のfit月だけで決める。

## 実装

`src/trade_data/meta_model.py` に high-overestimate classification modelを追加した。

- `TradeOverestimateHighModelBundle`
- `build_trade_overestimate_high_training_frame`
- `fit_trade_overestimate_high_model`
- `add_trade_overestimate_high_model_columns`
- `add_trade_overestimate_high_model_values_to_enriched`
- `trade_overestimate_high_scored_metrics`
- CLI: `oof-trade-overestimate-high-model`

出力列:

- `pred_trade_overestimate_high_q75_long_prob`
- `pred_trade_overestimate_high_q75_short_prob`
- `pred_trade_overestimate_high_q75_long_risk`
- `pred_trade_overestimate_high_q75_short_risk`
- selected trade側: `pred_trade_overestimate_high_q75_taken_prob`

## OOF Metrics

対象は highcost risk5 selected trades、2024-11..2025-04から `expanding`, `min_train_months=3` で2025-02..2025-04を評価した。

| quantile | trades | target rate | predicted mean | bias | brier | AUC | top quartile target rate |
|---|---:|---:|---:|---:|---:|---:|---:|
| q75 | `281` | `0.2811` | `0.2488` | `-0.0323` | `0.2015` | `0.5509` | `0.3662` |
| q90 | `281` | `0.1281` | `0.1070` | `-0.0212` | `0.1126` | `0.4574` | `0.1268` |

q75には薄いrank signalがあるが、q90は逆方向気味で尾部識別には使えない。

q75 side/month診断:

| group | support | target rate | predicted mean | AUC | top quartile target rate |
|---|---:|---:|---:|---:|---:|
| all | `281` | `0.2811` | `0.2488` | `0.5509` | `0.3714` |
| 2025-02 all | `104` | `0.3269` | `0.2585` | `0.5971` | `0.3846` |
| 2025-03 all | `103` | `0.2621` | `0.2109` | `0.4783` | `0.2800` |
| 2025-04 all | `74` | `0.2432` | `0.2879` | `0.5694` | `0.3889` |
| long | `138` | `0.2319` | `0.2289` | `0.5149` | `0.2647` |
| short | `143` | `0.3287` | `0.2680` | `0.5457` | `0.3714` |

2025-03 longはAUC `0.3869` と明確に悪く、月・sideで安定していない。

## Policy Check

既存の stateful risk5 固定policyに、q75 high-overestimate probabilityを追加riskとして重ねた。`risk_penalty=5` は維持し、combined riskは `EV -= 5 * stateful_prob + w * high_overestimate_prob` になるよう作った。

Baselineは `00150/00151` と同じ2025-02..2025-04 highcost risk5 fixed policy。

| label | total PnL | min month PnL | trades | max DD | forced exits |
|---|---:|---:|---:|---:|---:|
| baseline | `154.6374` | `14.3072` | `281` | `224.7524` | `1` |
| q75 high prob w0.5 | `94.7914` | `-12.8388` | `280` | `221.9324` | `1` |
| q75 high prob w1.0 | `109.3234` | `-12.7308` | `279` | `224.7804` | `1` |
| q75 high prob w2.0 | `86.1926` | `4.9996` | `273` | `221.6244` | `1` |

どの重みでもbaselineを下回った。w2は月最低はプラスのままだが、2025-02/03を大きく削る。w0.5/w1.0は2025-04をマイナス化した。

## Delta Diagnosis

bestのw1.0をbaselineと比較した。

| month | base PnL | candidate PnL | delta | base trades | candidate trades |
|---|---:|---:|---:|---:|---:|
| 2025-02 | `113.1642` | `94.8166` | `-18.3476` | `104` | `103` |
| 2025-03 | `27.1660` | `27.2376` | `+0.0716` | `102` | `102` |
| 2025-04 | `14.3072` | `-12.7308` | `-27.0380` | `75` | `74` |

悪化要因:

- 2025-02: `only_base long/down_normal_vol +23.4200`, `only_base short/down_normal_vol +18.0700`, `only_base long/range_low_vol +14.0000` を落とした。
- 2025-02: `only_candidate short/up_normal_vol -15.3288`, `only_candidate long/down_low_vol -12.9420` を追加した。
- 2025-04: `only_base long/up_low_vol +26.2600`, `only_base short/down_normal_vol +22.1170`, `only_base short/up_low_vol +10.7400` を落とした。

前回のfold-local q75 thresholdと同様に、良いbase tradeを落として悪いcandidateを一部追加する形になった。

## 判断

1. q75 high-overestimate分類はOOF AUC `0.5509` で薄いsignalはある。
2. しかし追加riskとしてpolicyへ入れると、`w=0.5/1.0/2.0` の全てでbaselineを下回る。
3. q90分類はAUC `0.4574` で、尾部risk検知には使わない。
4. high-overestimate probabilityは単独riskとして採用しない。次に使うなら、stateful/context downside modelの特徴量、または同一side内ranking/position blocking targetの補助特徴に限定する。
5. q75 amount threshold、q75 high classification probability、どちらも単純penaltyでは不採用。次は「入るtradeの点予測」ではなく「一玉制約で逃す機会」と「exit/holdingの失敗」をtargetへ戻す。

## Artifacts

- q75 classifier: `experiments/20260629_073137_trade_overestimate_high_q75_expanding_min3_highcost_risk5/`
- q90 classifier: `experiments/20260629_073202_trade_overestimate_high_q90_expanding_min3_highcost_risk5/`
- combined risk predictions and summaries: `data/reports/modeling/20260629_1634_trade_overestimate_high_q75_combined_risk/`
- w0.5 backtests: `data/reports/backtests/20260629_trade_overestimate_high_q75_combined_risk_w0p5_validation/`
- w1.0 backtests: `data/reports/backtests/20260629_trade_overestimate_high_q75_combined_risk_w1p0_validation/`
- w2.0 backtests: `data/reports/backtests/20260629_trade_overestimate_high_q75_combined_risk_w2p0_validation/`
- w1.0 delta: `data/reports/backtests/20260629_073704_trade_overestimate_high_q75_w1p0_delta_validation/`

## 検証

- `python3 -m unittest tests.test_meta_model`: pass
- `python3 -m unittest tests.test_meta_model tests.test_backtest tests.test_docs_reports`: pass, 129 tests
- `git diff --check`: pass

## 次の作業

1. high-overestimate probabilityは単独riskから外し、stacking featureとしてだけ残す。
2. selected tradeだけでなくcandidate examplesへ戻り、`blocking_cost`, `replacement_regret`, `stateful_entry_value` をexit/holding失敗targetと組み合わせる。
3. 月・sideでAUCが崩れるtargetは、採用前に必ずside/month別診断を通す。
