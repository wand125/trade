# Selected Trade Exit EV Confidence Diagnostics

日時: 2026-06-29 14:38 JST
更新日時: 2026-06-29 14:38 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻である `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## 目的

`00143` のprior context floorでは、2025-05 highcostの残存損失を十分に抑えられなかった。

次に見るべき弱点は「入る方向」そのものより、選択済みtrade上の exit timing、profit-barrier hit予測、EV過大評価、side confidenceの相互作用。今回は profit `1.0` / loss `1.20` の標準評価で、どの失敗型が残っているかを切り分ける。

## 実装

`trade_data.backtest` に `model-trade-exposure-diagnostics` を追加した。

入力は `model-policy` run親ディレクトリ、個別run、またはenriched trade CSV。`model-trade-exposure` と同じようにselected tradesへprediction列を結合し、さらに以下の診断bucketを作る。

| column | purpose |
|---|---|
| `pred_side_gap_bucket` | selected side EV と opposite side EV の差 |
| `pred_side_confidence_bucket` | selected side の best-side confidence |
| `pred_side_confidence_gap_bucket` | selected side confidence - opposite side confidence |
| `pred_holding_bucket` | 予測保有時間 |
| `holding_ratio_bucket` | 実保有時間 / 予測保有時間 |
| `profit_barrier_outcome` | predicted hit / actual hit の組み合わせ |
| `ev_overestimate_bucket` | 予測EV - 実現PnL |
| `exit_regret_bucket` | exit timing regret |

出力は `diagnostic_trades.csv` と、`group_by_context_*`, `group_by_diagnostic_combo.csv`, `group_by_diagnostic_combo_overall.csv`。これはfailure localizationと次のfeature/target設計用であり、post-hoc hard block用ではない。

## 2025-05 Highcost Context

2025-05 highcost risk5で悪いcontextは以下。

| context | trades | PnL | avg PnL | predicted hit | actual hit | side gap | confidence | exit regret | EV overestimate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `long/down_low_vol/london` | 3 | `-87.6396` | `-29.2132` | `0.0000` | `0.0000` | `0.9601` | `0.5516` | `32.3409` | `47.6835` |
| `short/up_normal_vol/asia` | 13 | `-56.7420` | `-4.3648` | `0.4615` | `0.3846` | `12.1773` | `0.6479` | `30.4754` | `31.9397` |
| `short/up_normal_vol/london` | 8 | `-54.5500` | `-6.8188` | `1.0000` | `0.3750` | `14.6367` | `0.6674` | `30.8054` | `33.3024` |
| `short/up_normal_vol/rollover` | 5 | `-29.6140` | `-5.9228` | `0.2000` | `0.2000` | `10.4147` | `0.5797` | `25.3248` | `32.1285` |

`long/down_low_vol/london` はside gapが小さく、confidenceも中程度で、actual profit barrier hitが0。これはcontext risk / low-edge entry / exit targetの候補。

一方で `short/up_normal_vol/london` はside gapもconfidenceも高い。ここは「低confidenceだから負けた」ではなく、profit-barrier hitとEVが過大評価された失敗。

## Short Up Normal Vol London

`short/up_normal_vol/london` では8 tradeすべてが `pred_taken_profit_barrier_hit=1` だったが、actual hitは3/8だけ。`pred_hit_actual_miss` は5 tradeで合計 `-52.2960`。

主なcomboは以下。

| combo | trades | PnL | EV overestimate |
|---|---:|---:|---:|
| `side_gap>10 / confidence 0.55-0.7 / holding 6-12h / pred_hit_actual_miss` | 2 | `-30.4320` | `45.2094` |
| `side_gap>10 / confidence 0.55-0.7 / holding 12-24h / pred_hit_actual_miss` | 1 | `-18.2880` | `45.6770` |
| `side_gap>10 / confidence 0.7-0.85 / holding 12-24h / pred_hit_actual_miss` | 1 | `-5.4360` | `42.6243` |

最悪tradeは `2025-05-05 09:58 UTC` のshortで、adjusted PnL `-27.6120`、predicted EV `34.3325`、side confidence `0.6712`、EV overestimate `61.9445`。confidenceは十分高いので、単純なconfidence filterでは捕捉できない。

## Side Confidence Screen

念のため `min_side_confidence` を直接かけるscreenも確認した。

| cost | min confidence | total PnL | min month | trades | max DD | forced |
|---|---:|---:|---:|---:|---:|---:|
| base | `0.00` | `567.7900` | `8.0868` | 603 | `218.4530` | 4 |
| base | `0.60` | `-112.2150` | `-244.5272` | 203 | `326.9740` | 2 |
| base | `0.75` | `66.3384` | `-10.9060` | 22 | `72.9060` | 0 |
| highcost | `0.00` | `354.8408` | `-52.9764` | 607 | `224.7524` | 4 |
| highcost | `0.60` | `-173.5306` | `-253.6986` | 205 | `334.6816` | 2 |
| highcost | `0.75` | `48.3630` | `-12.2140` | 22 | `76.5540` | 0 |

`0.75` は2025-05の高コスト最悪月を `-12.2140` まで縮めるが、7ヶ月で22 tradeしか残らない。これは実質NoTrade寄りで、標準policyとして採用しない。`0.60` は2025-04を大きく壊す。

## 判断

1. `short/up_normal_vol/london` の残存損失は低confidence問題ではなく、profit-barrier / exit / EV過大評価問題。
2. `long/down_low_vol/london` はlow side gapかつactual barrier missなので、context-risk targetまたはlow-edge entry targetの候補。
3. side confidence hard thresholdは採用しない。特に `0.75` は取引数を削りすぎ、研究の中心である「壊れにくい意思決定」ではなくNoTrade化に近い。
4. 次はselected tradeに対して、`pred_hit_actual_miss`、`ev_overestimate_vs_realized`、`exit_regret`、`holding_ratio_actual_vs_pred` をtarget/featureに戻す。
5. 2025-05だけのpost-hoc ruleにはしない。chronological OOF / walk-forwardで、profit-barrier overconfidenceとexit timing targetを校正する。

## Artifacts

- highcost diagnostics: `data/reports/backtests/20260629_053401_selected_trade_exit_ev_confidence_diagnostics_highcost_risk5/`
- base diagnostics: `data/reports/backtests/20260629_053123_selected_trade_exit_ev_diagnostics_base_risk5/`
- highcost no-confidence diagnostic: `data/reports/backtests/20260629_053154_selected_trade_exit_ev_diagnostics_highcost_risk5_v2/`
- single-month side confidence screen: `data/reports/backtests/20260629_side_confidence_screen_2025_05/`
- 7-month side confidence screen: `data/reports/backtests/20260629_side_confidence_screen_7m/`

## 検証

- `python3 -m unittest tests.test_backtest tests.test_docs_reports`: OK, 82 tests
- `python3 -m trade_data.backtest model-trade-exposure-diagnostics --help`: OK
- `git diff --check`: OK

## 次の作業

1. `pred_hit_actual_miss` をselected trade / candidate examplesの分類targetとして作る。
2. `ev_overestimate_vs_realized` と `exit_regret` のsupport-aware calibrationを追加する。
3. side confidenceはhard gateではなく、profit-barrier overconfidenceのinteraction featureとして使う。
4. 追加したtargetは2025-05専用ではなく、2024-11..2025-05のchronological OOFから評価する。
