# Failure Probability Quality Feature

日時: 2026-06-29 15:09 JST
更新日時: 2026-06-29 15:09 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻である `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## 目的

`00145` では `pred_hit_actual_miss` を単独risk penaltyへ直結すると、2025-05は改善するがOOF validationを悪化させた。

今回はその反省として、failure probabilityをhard penaltyではなく selected-trade EV calibration / trade quality model の説明変数へ戻す。狙いは、失敗分類を意思決定へ直接足すのではなく、実現PnLの過大評価を補正する側へ使うこと。

## 実装

`trade_quality_features` の optional side feature に、`pred_trade_failure_*_{long,short}_prob` を追加した。

対象は以下。

- `large_loss`
- `wrong_side`
- `profit_barrier_miss`
- `pred_hit_actual_miss`
- `exit_regret_high`
- `ev_overestimate_high`
- `any_failure`

各side-specific probabilityから、selected side視点の以下を作る。

- `pred_taken_trade_failure_<target>_prob`
- `pred_opposite_trade_failure_<target>_prob`
- `pred_trade_failure_<target>_prob_gap`

また、`enrich_trades_for_trade_quality` でselected tradesへfailure probability列を保持できるよう、`ANALYSIS_PREDICTION_COLUMNS` に `pred_trade_failure_*_{long,short}_prob` を追加した。

これにより、`oof-trade-failure-model` のOOF prediction parquetを `oof-trade-quality-model` へ渡すと、OOF failure probabilityをEV回帰featureとして使える。

## OOF Quality Metrics

2024-11..2025-04 highcost risk5 selected trades 502件で比較した。両方とも `sample_weighting=month_side`, `prediction_shrinkage=0.75`。

| model | calibrated bias | overestimate mean | MAE | RMSE | R2 |
|---|---:|---:|---:|---:|---:|
| baseline quality | `0.2806` | `4.4680` | `8.6555` | `12.7486` | `-0.0027` |
| failure-prob quality | `0.2061` | `4.4255` | `8.6450` | `12.7609` | `-0.0047` |

failure probabilityを入れるとbias、過大評価平均、MAEはわずかに改善した。一方でRMSE/R2は改善していない。rank能力はまだ弱く、これだけでtrade選択を任せる段階ではない。

## 2025-05 Policy Screen

raw EV、stateful risk5、MLP holding guardは維持し、quality columnを `min_trade_quality` filterに使った。

| run | min quality | adjusted PnL | trades | win rate | profit factor | max DD |
|---|---:|---:|---:|---:|---:|---:|
| baseline stateful risk5 | `-inf` | `-52.9764` | 105 | `0.5238` | `0.9016` | `137.4392` |
| baseline quality | `0.5` | `-92.2498` | 87 | `0.5402` | `0.8127` | `158.5032` |
| failure-prob quality | `0.5` | `-101.9736` | 75 | `0.5067` | `0.7739` | `139.9440` |
| failure-prob quality | `1.0` | `-124.0614` | 26 | `0.5000` | `0.5288` | `158.2160` |

quality hard filterは採用しない。特にfailure-prob qualityは、OOF上の過大評価平均を少し下げるが、2025-05の実行policyでは良いtradeも落として損益を悪化させる。

## 判断

1. failure probabilityをtrade quality featureとして使う配線は残す。
2. `min_trade_quality` hard filterには使わない。今回もNoTrade化・良いtradeの脱落に近い。
3. OOF regression指標の改善は小さい。bias/overestimate/MAEは微改善だが、RMSE/R2は改善していない。
4. 次はquality値をhard filterではなく、候補ranking、near-tie tie-break、またはEV overestimate residualの説明変数として使う。
5. `ev_overestimate_high` / `exit_regret_high` は分類probabilityだけでなく、連続値・分位・holding ratioを含むtargetに作り替える。

## Artifacts

- failure-prob quality OOF: `experiments/20260629_060752_trade_quality_with_failure_prob_highcost_risk5/`
- baseline quality OOF: `experiments/20260629_060825_trade_quality_baseline_no_failure_prob_highcost_risk5/`
- policy compare: `data/reports/backtests/20260629_trade_quality_failure_feature_policy_compare/`

## 検証

- `python3 -m unittest tests.test_meta_model`: OK, 44 tests
- `python3 -m unittest tests.test_meta_model tests.test_backtest tests.test_docs_reports`: OK, 126 tests
- `python3 -m trade_data.meta_model oof-trade-quality-model --help`: OK
- `git diff --check`: OK

## 次の作業

1. quality scoreをhard filterにせず、near-tieのside/entry rankingだけに限定して試す。
2. `pred_hit_actual_miss` probabilityとexit timing targetを組み合わせたoverestimate residual modelを作る。
3. `ev_overestimate_high` を閾値分類ではなく、`pred_taken_ev - adjusted_pnl` の連続targetまたは上側分位targetにする。
