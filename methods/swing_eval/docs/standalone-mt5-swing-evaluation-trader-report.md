# Standalone MT5 Swing Evaluation Trader Report

作成対象:

- `methods/swing_eval/mt5/Experts/Swing_Evaluation_Trader.mq5`
- `methods/swing_eval/mt5/Indicators/Swing_Evaluation_Predictor.mq5`
- 既存の `AI_Bridge_Advisor.mq5` / Analyzer / GPT運用とは別物
- WebRequestなし、外部APIなし、MT5単体の足・インジケーター・売買履歴だけで評価する

## 目的

山/谷の反発または戻り売りを、MT5単体の評価関数でスコア化する。
SLを近く、TPを遠く置ける候補を探し、1:3、1:4、1:5、および可変RRをStrategy TesterとForward Testで検証する。

初期状態では発注しない。

- `InpSignalOnly = true`
- `InpEnableTrading = false`
- `InpAllowLiveTrading = false`

実弾またはデモ発注には3つを明示的に切り替える必要がある。

## インジケータ表示

発注を伴わずにチャート上で予測を見たい場合は、EAではなくインジケータを使う。

- File: `methods/swing_eval/mt5/Indicators/Swing_Evaluation_Predictor.mq5`
- Install: MT5の `MQL5/Indicators` へコピーしてMetaEditorでCompile
- Attach: XAUUSD M1チャート
- 表示: 予測パネル、score、buy/sell score、理由、RR、SL幅
- ライン: 条件通過時に `DRY-RUN ENTRY` / `DRY-RUN SL` / `DRY-RUN TP`
- 安全性: `CTrade`、`OrderSend`、WebRequestを持たず、発注もtrade command生成もしない

用途は、次のエントリー候補を「ラインで見て手動判断する」段階である。Strategy TesterやForward Testで実約定ログを取りたい場合はEAを使う。

## 前回の最適化情報の反映

前回の168h検証で、blackout除外後の主候補は以下。

| 戦略 | count | wins | losses | timeouts | win_rate | avg_r | PF | total_r | max_losing_streak |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| variable_side_ladder | 100 | 16 | 54 | 30 | 0.1600 | 0.5716 | 1.9192 | 57.163 | 7 |
| fixed_1_4 | 87 | 14 | 47 | 26 | 0.1609 | 0.4808 | 1.7780 | 41.831 | 6 |
| fixed_1_5 | 114 | 12 | 68 | 34 | 0.1053 | 0.3390 | 1.4941 | 38.642 | 8 |
| fixed_1_3 | 72 | 16 | 39 | 17 | 0.2222 | 0.3251 | 1.5221 | 23.404 | 6 |

EA初期値への反映:

- `InpMinScore = 50.0`
- `InpUseSideRiskReward = true`
- `InpBuyRiskReward = 4.0`
- `InpSellRiskReward = 5.0`
- `InpMinRiskReward = 3.0`
- `InpMaxRiskReward = 5.0`
- `InpLot = 0.10`
- `InpMaxSingleLot = 0.10`
- `InpMaxTotalLot = 0.30`
- `InpUseDailyLossStop = true`
- `InpDailyLossLimit = 5000.0`
- `InpUseConsecutiveLossStop = true`
- `InpConsecutiveLossLimit = 20`
- `InpConsecutiveLossCooldownMinutes = 120`

side ladderの内訳は、買いRR4が46件、売りRR5が54件だったため、EAもその組み合わせを既定にした。

## 買い/売り別フィットの扱い

買いRR4:

| dataset | rule | count | win_rate | avg_r | PF | total_r |
|---|---|---:|---:|---:|---:|---:|
| all_baseline | none | 45 | 0.1333 | 0.4363 | 1.7292 | 19.6322 |
| test_baseline | none | 14 | 0.1429 | 0.0729 | 1.1015 | 1.0202 |
| all_fitted | broke_trigger >= 1 | 31 | 0.1290 | 0.1902 | 1.2927 | 5.8957 |
| test_fitted | broke_trigger >= 1 | 11 | 0.0909 | -0.0398 | 0.9439 | -0.4373 |

買いの `broke_trigger >= 1` はtrain上では見えるがtestで崩れたため、EAでは入力だけ用意し、既定OFFにした。

- `InpUseFittedBuyBreakFilter = false`
- `InpUseFittedBuyEntryFilter = false`
- `InpBuyRequireBreakConfirm = true`
- `InpBuyMinM1ClosePosition = 0.65`
- `InpBuyMinM1BodyAtr = 0.10`
- `InpBuyMinM5CloseSlowAtr = 0.0`

BUY初回refitでもPF/Forwardが残らないため、次の診断は `Swing_Evaluation_Trader_buy_entry_refit.set` でentry品質をBUY専用に再fitする。このセットはBUY only、全探索上限864通り、`InpUseFittedBuyEntryFilter=true` 固定で、反発後の高値更新確認、M1終値位置、M1陽線実体、M5 slow EMAからの距離を探索する。採用は必ずStrategy Testerのback/forwardと年次検証を通した後にする。

`Swing_Evaluation_Trader_buy_entry_refit.set` の短期窓結果はclosed 83,604、PF 0.6026、平均R -0.3784、positive forward/back pass 0で、BUY全体としては不採用だった。ただしentry server hour別では03:00-04:00がPF 4.4789、平均R 1.0763、closed 1,603で最も強く出たため、次の診断として `Swing_Evaluation_Trader_buy_hour03_validation.set` を追加した。このセットは `InpUseBuyAllowedServerHours=true`、`InpBuyAllowedServerHours=3` 固定で、時間帯依存がback/forwardでも残るかだけを検証する。

`Swing_Evaluation_Trader_buy_hour03_validation.set` の短期窓aggregateはclosed 2,023、PF 2.4784、平均R 0.7411まで改善した。しかしpositive forward/back passは0で、上位XML passも取引数が6-11件程度と薄い。したがってhour03は候補時間帯として扱うが、単独では昇格しない。次は強い複数時間帯への拡張、または2025年/out-of-year検証で同じ傾向が残るかを見る。

複数時間帯への拡張用に `Swing_Evaluation_Trader_buy_strong_hours_validation.set` を追加した。これは `InpBuyAllowedServerHours=3,5,6,10` 固定で、BUY entry refitで相対的に良かった時間帯をまとめてサンプルを増やす。採用条件は変えず、positive forward/back passが出ること、年次/out-of-yearでもPF >= 1.2と平均R > 0が残ることを要求する。

`Swing_Evaluation_Trader_buy_strong_hours_validation.set` の短期窓aggregateはclosed 15,108、PF 1.5644、平均R 0.3011まで改善した。ただしpositive forward/back passは0で、M15 down、M30/M15 downが明確に弱い。次はBUY側にも `M30/M15 up` ゲートを入れ、時間帯と上位足方向を同時に満たす時だけBUYを評価する。

このため `InpUseBuyM30M15UpGate` と `Swing_Evaluation_Trader_buy_strong_hours_m30m15_validation.set` を追加した。既定はOFFで、専用setだけONにする。採用条件は同じく、positive forward/back pass、年次/out-of-yearでPF >= 1.2、平均R > 0を満たすこと。

`Swing_Evaluation_Trader_buy_strong_hours_m30m15_validation.set` の短期窓aggregateはclosed 13,935、PF 1.5658、平均R 0.2615、純益9,932.22だった。M30/M15 downなどの弱い上位足レジームは除外できたが、positive forward/back passは0で、上位forward XML passもforward側がマイナスだった。したがってこのBUY条件もまだ採用しない。RR別では1:3がPF 1.7350、1:5が平均R 0.3692で相対的に強いが、forward/back安定性が出るまでは診断止まりとする。次は2025年などのout-of-year検証で、現在の7月寄りaggregateに過ぎないかを確認する。

2025年通期で `Swing_Evaluation_Trader_buy_strong_hours_m30m15_validation.set` を検証した結果、closed 552,628、PF 0.8980、平均R -0.1906、純益 -72,342.63、positive forward/back pass 0だった。短期窓のBUY aggregateは通期に残らず、BUY強時間帯 + M30/M15 upゲートは棄却する。RR別でも1:2 PF 0.8346、1:3 PF 0.9101、1:4 PF 0.9267、1:5 PF 0.9667で、すべてbreakeven未満だった。entry server hour別では03時 PF 0.9948、05時 PF 0.6980、06時 PF 0.8688、10時 PF 1.0107で、時間帯だけでも採用できない。

一方で、年次aggregate内のSL 300-350ptだけはPF 1.9573、RR 1:4/SL 300-350ptはPF 3.0872だった。これはXML back/forwardが通っていないため採用根拠ではないが、小さいSLでBUYが崩れている可能性を切り分ける価値はある。このため `Swing_Evaluation_Trader_buy_wide_stop_validation.set` を追加した。これはBUY only、`InpUseBuyM30M15UpGate=true`、`InpUseBuyAllowedServerHours=true`、`InpBuyAllowedServerHours=3,5,6,10`、`InpMinStopPoints=300`、`InpMaxStopPoints=350` 固定で、広めのSLだけを診断する。これもpositive forward/back passと年次/out-of-year検証を満たすまで採用しない。

`Swing_Evaluation_Trader_buy_wide_stop_validation.set` の短期窓aggregateはclosed 7,267、PF 1.4914、平均R 0.3299、純益7,687.65まで改善した。ただしpositive forward/back passは0で、上位forward passもforward result -984.00、back result 201.94、取引数16件だった。RR別では1:2がPF 1.8406、平均R 0.4446で最も強く、1:5もPF 1.3366、平均R 0.2700でプラスだったが、安定passがないため採用しない。entry server hourでは03:00-04:00がPF 6.1193と強い一方、10:00-11:00はPF 0.6442、6月はPF 0.1352、火曜はPF 0.1932で大きく崩れた。結論として、小さいSLはBUY失敗要因の一部だが、広いSLだけでは解決しない。次にBUYを続ける場合は、さらにSLを広げるのではなく、entry hour/calendar分割またはBUY評価関数の再設計を行う。

entry 03:00-04:00だけを切り出すため、`Swing_Evaluation_Trader_buy_hour03_wide_stop_validation.set` を追加した。これはBUY only、`InpBuyAllowedServerHours=3`、`InpUseBuyM30M15UpGate=true`、`InpMinStopPoints=300`、`InpMaxStopPoints=350` 固定で、wide-stop診断の中で最も強かったentry 03時だけがback/forwardでも残るかを検証する。これも診断用であり、年次/out-of-yearとpositive forward/back passが通るまで採用しない。

`Swing_Evaluation_Trader_buy_hour03_wide_stop_validation.set` の短期窓aggregateはclosed 1,732、PF 5.7400、平均R 1.6671だったが、positive forward/back passは0だった。2025年通期ではclosed 60,491、PF 1.1593、平均R 0.1157、純益23,322.99まで改善したが、昇格閾値PF 1.2に届かず、positive forward/back passも0だった。RR 1:3がPF 1.2385で最も近く、弱い月は6月/8月/10月、弱い曜日は水曜/金曜だったため、次段階として `Swing_Evaluation_Trader_buy_hour03_wide_stop_calendar_validation.set` を追加した。これはhour03/M30-M15 upを維持し、`InpUseFittedBuyCalendarFilter` のON/OFF、`InpBuyBlockedMonths=6,8,10`、`InpBuyBlockedWeekdays=3,5` を432 passで診断する。

`Swing_Evaluation_Trader_buy_hour03_wide_stop_calendar_validation.set` の短期窓aggregateはclosed 1,609、PF 6.2140、平均R 1.7013だったが、positive forward/back passは0だった。2025年通期ではclosed 47,303、PF 1.1215、平均R 0.0886、純益14,682.68で、hour03 wide-stop単体の年次PF 1.1593より悪化した。Tester XMLではcalendar ONがback側上位passに多く、back平均PFはON 1.4936、OFF 1.2712だったが、forward側はON/OFFとも全passがマイナスで、forward平均PFはON 0.9131、OFF 0.9166だった。calendar filterはback fitに効いてもforwardへ残らないため、採用しない。

このback/forwardの入力値別比較は、`mt5_tester_optimization_report.py` の `Back Parameter Diagnostics` / `Forward Parameter Diagnostics` で自動出力するようにした。今後はcalendar filterに限らず、entry閾値、MinScore、trend/time filterなどがbackだけで効いているのか、forwardにも残るのかをこの表で確認してから次のsetに固定する。

同じレポートに `Chronological Split Diagnostics` も追加した。これはAgent CSVのclose行を `server_time` 順に並べ、前半/後半と四分割でPF、平均R、net profitを出す。月別/曜日別の弱点だけでなく、年次データの後半でedgeが消えていないかを確認するための粗いwalk-forward診断として使う。

BUY hour03 wide-stop calendar validationの2025年通期を再集計したところ、前半はPF 1.2615、平均R 0.1795だったが、後半はPF 0.9951、平均R -0.0023まで落ちた。四分割ではq1がPF 1.9960と強い一方、q2がPF 0.7124、q3がPF 0.9317で崩れており、q4もPF 1.0593に留まる。calendar filterはforward XMLだけでなく、時系列分割でも安定しないため採用しない。

売りRR5:

| dataset | rule | count | win_rate | avg_r | PF | total_r |
|---|---|---:|---:|---:|---:|---:|
| all_baseline | none | 59 | 0.1864 | 0.6716 | 2.0398 | 39.6253 |
| test_baseline | none | 18 | 0.1667 | 0.6547 | 2.0474 | 11.7850 |
| all_fitted | M5_close_ema_long_atr >= -3.2145 AND m1_alternating_ratio >= 0.33333 | 33 | 0.2424 | 1.2660 | 3.5373 | 41.7786 |
| test_fitted | 同上 | 10 | 0.2000 | 0.8887 | 2.3696 | 8.8874 |

売りフィットはtestでも崩れなかったため、EAでは既定ONにした。

- `InpUseFittedSellFilter = true`
- `InpSellMinM5CloseSlowAtr = -3.2145`
- `InpSellMinM1AlternatingRatio = 0.33333`

## 評価ロジック

EAは毎回以下を計算する。

1. M30/M15/M5のEMA方向
2. M30/M15のEMA傾き
3. M1/M5 RSI
4. M1の直近スイング高値/安値
5. スイング近辺での反発または上ヒゲ/下ヒゲ拒否
6. 前足高値超え、前足安値割れ
7. SL/TPが成立するか
8. spread、rollover、ロット、最大建玉、合計ロット制限

買い評価:

- M30/M15/M5が上向き
- M1 RSIが反発
- 直近スイング安値付近で陽線反発
- 前足高値回復
- SLはスイング安値の外側、TPはRRで算出

売り評価:

- M30/M15/M5が下向き
- M1 RSIが下向きに折れる
- 直近スイング高値付近で陰線拒否
- 前足安値割れ
- SLはスイング高値の外側、TPはRRで算出
- 追加で、売りフィット条件を確認する

## SL/TP設計

SL:

- 買い: `直近スイング安値 - InpStopBufferPoints`
- 売り: `直近スイング高値 + InpStopBufferPoints`

TP:

- 買い: `entry + RR * risk`
- 売り: `entry - RR * risk`

拒否条件:

- `InpMinStopPoints` 未満
- `InpMaxStopPoints` 超過
- broker stop level内
- spread超過
- rollover時間
- lotがbroker制約またはEA制約外
- 最大建玉数または合計lot超過
- 日次損失が `InpDailyLossLimit` に到達
- 連敗数が `InpConsecutiveLossLimit` に到達

## Forward Test方針

Strategy Testerでは、まず最適化とForwardをセットで使う。

推奨設定:

- Expert: `Swing_Evaluation_Trader`
- Symbol: `XAUUSD-m`
- Period: `M1`
- Model: できれば `Every tick based on real ticks`
- Optimization: 有効
- Forward: `1/4` または直近25%をForwardにするCustom期間
- Deposit/currency: 実運用口座に近い設定

通常のBack/Forward比較では、Backtestは `ForwardMode=0` の純バックテスト、Forward Testは `ForwardMode=3` の1/4分割として別Reportに保存する。`mt5_back_forward_run.py --mode both --forward-mode 3` はForward Test側だけにForward指定を渡し、Backtest側にはForward指定を渡さない。

発注を伴うTester設定:

- `InpSignalOnly = false`
- `InpEnableTrading = true`
- `InpAllowLiveTrading = true`
- `InpRequireStrategyTester = true`
- `InpLot = 0.10`
- `InpMaxTotalLot = 0.30`

`InpRequireStrategyTester = true` のpresetはStrategy Tester/MT5 Forward内だけ自動発注を許可する。通常チャートに誤ってLoadした場合は発注を拒否する。デモ口座のForward運用で実発注まで確認する段階だけ、signal-only解除に加えて `InpRequireStrategyTester = false` を明示する。

最適化対象は広げすぎない。

| parameter | values |
|---|---|
| `InpMinScore` | 45, 50, 55, 60 |
| `InpBuyRiskReward` | 3, 4 |
| `InpSellRiskReward` | 4, 5 |
| `InpSwingAtrBand` | 0.6, 0.8, 1.0 |
| `InpStopBufferPoints` | 20, 30, 40 |
| `InpUseFittedSellFilter` | true, false |
| `InpSellMinM5CloseSlowAtr` | -4.0, -3.2145, -2.5 |
| `InpSellMinM1AlternatingRatio` | 0.25, 0.33333, 0.45 |

SELLの年次検証でplanned SL hit too oftenが残る場合は、通常の広い最適化ではなく `Swing_Evaluation_Trader_sell_entry_refit.set` を使う。このセットはSELL only、全探索上限864通り、`InpUseFittedSellEntryFilter=true` 固定で、以下だけを主に探索する。

| parameter | values |
|---|---|
| `InpSellRiskReward` | 2, 3, 4, 5 |
| `InpSellRequireBreakConfirm` | true, false |
| `InpSellMaxM1ClosePosition` | 0.25, 0.35, 0.45 |
| `InpSellMinM1BodyAtr` | 0.05, 0.10, 0.15 |
| `InpSellMaxM5CloseSlowAtr` | -0.50, -0.25, 0.0 |

entry品質だけでpositive forward/back passが出ない場合は `Swing_Evaluation_Trader_sell_regime_entry_refit.set` を使う。このセットは全探索上限2592通りで、上記entry条件に加えて `InpUseFittedSellTrendFilter` と `InpUseFittedSellTimeFilter` のON/OFFを同時に検証する。RRは1:3-1:5、SLは250-300ptへ絞る。

年次診断で特定サーバー時間だけPFが残る場合は `Swing_Evaluation_Trader_sell_hour12_validation.set` を使う。このセットは `InpUseSellAllowedServerHours=true`、`InpSellAllowedServerHours=12` 固定で、12:00-13:00のSELLだけを切り出す。全探索上限1296通りで、RR 1:3-1:5、MinScore、entry条件、trend filterを再検証する。時間帯診断のPFだけでは採用せず、この専用setでもback/forwardと年次検証を通す。hour12単独がPF 1.2に届かず、M30/M15 downだけが残る場合は `Swing_Evaluation_Trader_sell_hour12_m30m15_validation.set` で `InpUseSellM30M15DownGate=true` 固定の次段階診断を行う。

2025年のhour12 + M30/M15-down診断では、SELL単体でPF 1.3786、平均R 0.2914、closed 39,315、positive forward/back pass 30を確認した。これはSELL側の有力候補だが、BUY側が欠落しており、12月/3月/6月/水曜日が弱いため、システム全体の採用条件はまだ満たさない。`Swing_Evaluation_Trader_sell_hour12_m30m15_calendar_validation.set` で `InpUseFittedSellCalendarFilter` のON/OFFも検証した。stable passは68へ増えたが、年間aggregateはPF 1.3667、平均R 0.2834へ低下し、3月/6月/水曜の弱さも残ったため、calendar filterは診断止まりとする。

採用基準:

- trainとforwardの両方でPF >= 1.2
- forward closed trades >= 30
- max losing streak <= 20を目安
- buy/sellの片側だけに利益が偏りすぎない
- fixed RRでもside ladderでも極端に崩れない
- 直近1週間だけでなく、別週でも再検証する

EAの `OnTester()` はカスタム評価値を返す。

- closed tradesが `InpTesterMinClosedTrades` 未満なら強く減点
- PFが `InpTesterMinProfitFactor` 未満なら減点
- PF、期待値、取引数を加点
- 最大連敗を減点

これにより、単純な利益最大化だけでなく、サンプル数不足と連敗リスクを避ける。

## MT5 CSVログと集計

EAはStrategy Tester/Forward Test中にCSVログを出せる。

既定値:

- `InpWriteCsvLog = true`
- `InpCsvLogFile = swing_evaluation_trades.csv`
- `InpLogSignalRows = false`

ログはMT5の `MQL5/Files` 配下に作成される。Strategy Testerではテスター環境側のFilesに出るため、テスト完了後に `runtime/mt5_forward/swing_evaluation_trades.csv` へ置いて集計する。

最新CSVを自動収集して集計する場合:

```bash
python3 methods/swing_eval/analysis/mt5_forward_collect.py \
  --destination runtime/mt5_forward/swing_evaluation_trades.csv \
  --output-json runtime/latest_mt5_forward_report.json \
  --output-md runtime/latest_mt5_forward_report.md \
  --collect-status-json runtime/latest_mt5_forward_collect.json \
  --min-closed 30 \
  --min-pf 1.2 \
  --max-losing-streak 20
```

集計コマンド:

```bash
python3 methods/swing_eval/analysis/mt5_forward_report.py \
  --input runtime/mt5_forward/swing_evaluation_trades.csv \
  --min-closed 30 \
  --min-pf 1.2 \
  --max-losing-streak 20 \
  --output-json runtime/latest_mt5_forward_report.json \
  --output-md runtime/latest_mt5_forward_report.md
```

MT5 Forwardを昇格ゲートの必須条件にする場合:

```bash
python3 methods/swing_eval/analysis/promotion_gate.py \
  --mt5-forward-report runtime/latest_mt5_forward_report.json \
  --winrate-fit-report runtime/latest_winrate_fit.json \
  --require-mt5-forward \
  --require-winrate-fit
```

出力:

- `runtime/latest_mt5_forward_report.json`
- `runtime/latest_mt5_forward_report.md`
- `runtime/latest_winrate_fit.json`

集計内容:

- closed件数
- win/loss/breakeven
- net profit
- PF
- 価格ベースの平均R
- 平均/最大約定遅延seconds
- 平均/最大保有seconds
- オープン時の平均/最大滑りpoints
- 平均/最大spread points
- TP/SL/早期または手動決済の分類
- 最大連敗
- 売買別
- 決済理由別
- RR別
- SL幅帯/TP幅帯
- RR×SL幅帯/RR×TP幅帯
- score帯別
- closed件数/PF/最大連敗の採用条件

## デモForward運用

Strategy TesterのForwardを通過してから、デモ口座で行う。

段階:

1. `InpSignalOnly = true` のまま、チャート表示とログだけ確認
2. 期待通りのシグナルが出るか、1日以上確認
3. デモで `InpSignalOnly = false`, `InpEnableTrading = true`, `InpAllowLiveTrading = true`, `InpRequireStrategyTester = false`
4. 0.1 lot、合計0.3 lot上限で実行
5. 日次でPF、平均R、最大連敗、買い/売り別成績を確認

実口座化は、デモForwardで十分なclosedサンプルが出てからにする。
