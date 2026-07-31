# FX/MT5 山谷評価トレード研究環境

このリポジトリは、XAUUSD-mの短期売買について、MT5の足データを使って山/谷、スコア、SL/TP、RR、Forward成績を検証するための作業環境です。

目的はすぐに自動売買することではありません。まず候補を出し、スコアが高いほど期待RやPFが改善するかを確認し、十分なdry-run/Forward結果が出てからMT5 EAのlive化を検討します。

## 主要ファイル

| 種類 | ファイル | 役割 |
|---|---|---|
| Bridge | `src/bridge/mt5_ai_bridge.py` | MT5からsnapshot/history/accountを保存 |
| Bridge EA | `methods/swing_eval/mt5/Experts/AI_Bridge_Advisor.mq5` | MT5からBridgeへデータ送信 |
| Bridge状態 | `methods/swing_eval/analysis/bridge_status.py` | Bridge HTTP、EA POST鮮度、MT5 terminal、履歴要求pendingを診断 |
| Bridge復旧計画 | `methods/swing_eval/analysis/bridge_recovery_plan.py` | EA POST停止、履歴pending、Strategy Testerへ進める状態を分類 |
| Bridge監視 | `methods/swing_eval/analysis/bridge_status_watch.py` | Bridge/EA/terminal状態を定期更新しheartbeatに要約 |
| MT5手動collect監視 | `methods/swing_eval/analysis/mt5_manual_auto_collect_watch.py` | 手動Strategy Tester後のcollect readyを定期検知 |
| MT5単体EA | `methods/swing_eval/mt5/Experts/Swing_Evaluation_Trader.mq5` | Strategy Tester/Forward Test用 |
| MT5表示Indicator | `methods/swing_eval/mt5/Indicators/Swing_Evaluation_Predictor.mq5` | 予測パネルとdry-run注文ライン表示 |
| 仕様書 | `docs/swing-evaluation-trading-system-spec.md` | 全体設計 |
| 仕様カバレッジ | `methods/swing_eval/analysis/spec_coverage.py` | 仕様上のコンポーネント、Phase完了条件、runtime証跡の監査 |
| MT5導入 | `docs/mt5-installation-guide.md` | MT5への配置、Compile、使い方 |

## 基本方針

- データ取得と売買判断を分離する。
- Analyzer/GPTに依存しないMT5単体EA/Indicatorも用意する。
- 評価関数は勝率そのものではなく期待Rを高める方向で検証する。
- 1:2、1:3、1:4、1:5、可変RRを比較する。
- TPまでの空間はM1だけでなく、M5/M15の確定山/谷障害物も見て評価する。
- M15/M30の確定山/谷が近い場合は、上位足の支持抵抗として減点する。
- 既存運用に合わせ、基本lotは `0.1`、合計上限は `0.3` とする。
- 実口座live化は最後。まず表示、dry-run、Forward Testを通す。

## 導入済みMT5ファイル

このMacのMetaTrader 5環境には以下を配置済みです。

```text
/Users/HHosono/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5/MQL5/Indicators/Swing_Evaluation_Predictor.mq5
/Users/HHosono/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5/MQL5/Experts/Swing_Evaluation_Trader.mq5
```

次にMT5のMetaEditorでCompileしてください。

詳細:

```text
docs/mt5-installation-guide.md
```

## まずチャートで見る

予測表示だけなら `Swing_Evaluation_Predictor` を使います。

1. MT5でMetaEditorを開く。
2. `Indicators/Swing_Evaluation_Predictor.mq5` をCompileする。
3. MT5のNavigatorを更新する。
4. XAUUSD M1チャートに `Swing_Evaluation_Predictor` を適用する。
5. チャート左0%、縦80%付近のBoxパネルを見る。

表示されるもの:

- 左0%、縦80%付近に置く5行のコンパクトな背景Box
- `HOLD: 49.0` / `BUY: 61.0` / `SELL: 58.0` 形式の推奨とscore
- HOLDは黄色、BUYは緑、SELLは赤
- HOLD時は `WAIT: SCORE LOW` / `WAIT: NO DOMINANCE` などの短い理由
- 更新時刻、spread、有効期限
- 小さく表示されるBUY/SELL score
- M30/M15トレンド
- ENTRY、SL推奨値、TP推奨値
- `DRY-RUN ENTRY`
- `DRY-RUN SL`
- `DRY-RUN TP`

短い理由の見方:

| 表示 | 意味 | 見方 |
|---|---|---|
| `WAIT: SCORE LOW` | 採用下限score未満 | 方向感があっても見送り |
| `WAIT: NO DOMINANCE` | BUY/SELLの優位差や採用条件が不足 | Scoreが高めでも、片側に決め切れない状態 |
| `WAIT: SPREAD` | spreadが上限超え | 価格が良くても新規は避ける |
| `WAIT: ROLLOVER` | 日跨ぎ/低流動性の除外時間 | 時間要因で見送り |
| `WAIT: DATA` | 足/インジケータが未準備 | 起動直後やデータ不足 |
| `WAIT: OTHER` | その他の保留理由 | リスク計画不成立などを含む |

`HOLD: 67.0` のようにscoreが高くても、最終推奨がHOLDならEntry/SL/TPは出ません。BUY/SELLのどちらかが採用条件を満たした時だけ、ENTRY、SL推奨値、TP推奨値と水平線が出ます。
HOLD時は既定で古い `DRY-RUN ENTRY` / `DRY-RUN SL` / `DRY-RUN TP` 線を削除します。

表示内の `Spr` は現在のspreadです。`Valid` は、そのENTRY/SL/TP推奨ラインを有効と見る期限です。HOLD時はエントリー対象がないため `Valid -` になります。

このIndicatorは発注しません。手動判断用です。

## MT5単体EAでForward Testする

`Swing_Evaluation_Trader` はStrategy Tester/Forward Test用です。

最短の実行入口:

1. `runtime/latest_mt5_tester_status.md` を開き、`MT5 Operator Handoff` の `MT5 Quick Input` を確認する。
2. MT5上で手動実行する場合は `runtime/latest_mt5_manual_test_queue.md` の `MT5 Quick Input` と `Manual Execution Checklist` の順に、Strategy TesterへExpert、Symbol、Period、Model、Dates、Forward、Inputs、Report名を設定してStartする。
3. MT5を閉じて `/config` から1ステップずつ起動したい場合は `python3 methods/swing_eval/analysis/mt5_manual_queue_launch.py --queue runtime/latest_mt5_manual_test_queue.json --output-json runtime/latest_mt5_manual_queue_launch.json --output-md runtime/latest_mt5_manual_queue_launch.md` でdry-runし、選択stepとblock理由を確認してから `--execute --detached` を付ける。
4. MT5で実行後は `python3 methods/swing_eval/analysis/mt5_manual_collect.py --execute` で、readyになったBacktest、Forward、BUY/SELL sample collection結果だけを取り込む。

MT5がすでに起動している場合は、`/config` 自動起動ではなくMT5上のStrategy Testerを使います。`MT5 Operator Handoff` の `MT5 Quick Input` に表示された値をそのまま設定し、完了後は同じ欄の `Collect execute command` を使います。MT5を閉じてから1ステップだけ自動起動したい場合だけ、`latest_mt5_manual_queue_launch.md` の `/config` コマンドを使います。

Backtest/Forwardの2本だけをまとめて準備、実行、取り込みする場合は `methods/swing_eval/analysis/mt5_back_forward_run.py` を使います。まずdry-runで `runtime/latest_mt5_back_forward_run.md` の `MT5 Strategy Tester Quick Start` を確認し、MT5上ではBacktest、Forward Testの2行を順に実行します。Quick Startには `MT5 mode`、`run type`、`report note` も出るため、単発Forward profileとOptimization Forwardを混同せずに確認できます。次に同じ条件で `--execute --refresh-ready-status`、手動実行後に取り込む時は `--collect-only --csv-modified-after "<MT5実行開始時刻>"` です。

Back/Forwardに加えてOptimization Forwardや年次候補をMT上で回す場合は、`runtime/latest_mt5_manual_test_queue_with_optimization.md` を見ます。`static_sell_hour12_m30m15_2025` と `static_sell_hour12_m30m15_calendar_2025` は短期 `.ini` を直接開かず、`runner execute` 行のコマンドで `2025.01.01` から `2025.12.31`、Forward `1/4`、年次Report名へ上書きして実行します。通常キューはBacktest/ForwardとBUY/SELL sample collection用、最適化込みキューは追加検証用として分けています。

`runtime/latest_mt5_manual_test_queue_with_optimization.md` の `MT5 Pass Budget` には、各stepの全探索上限が表示されます。通常のBacktest/Forward/sample collectionは `Passes=1` です。Optimizationが有効なstepは `full-factorial passes` を上限として表示し、MT5のFast genetic algorithmでは実際の実行passがそれより少なくなることがあります。MT5上で次に走らせるものだけを見たい時は、同じファイルの `Next step summary` か `runtime/latest_mt5_manual_operator_packet_with_optimization.md` を見ます。

初期値:

```text
InpSignalOnly = true
InpEnableTrading = false
InpAllowLiveTrading = false
InpRequireStrategyTester = false
```

Strategy Testerで約定ログを取りたい場合だけ、テスター上で以下にします。

```text
InpSignalOnly = false
InpEnableTrading = true
InpAllowLiveTrading = true
InpRequireStrategyTester = true
```

Tester用 `.set` は `InpRequireStrategyTester = true` にしてあります。通常チャートに誤ってLoadした場合、自動発注は拒否されます。デモForwardで実発注まで確認する最終段階だけ `InpRequireStrategyTester = false` を明示します。

チャート上の手動Entryボタンは補助機能です。EA側の基本確認は自動売買ロジックをStrategy Tester/Forward Testで回すことです。

- `Swing_Evaluation_Trader` は `ENTRY BUY` / `ENTRY SELL` / `WAIT` ボタンを任意で表示できます。
- 既定では `InpShowChartEntryButton = false` なので、ボタンは出しません。
- 表示した場合も、既定では `InpChartButtonDryRunOnly = true`、`InpAllowChartButtonTrading = false` なので、押しても発注せずCSVにbuttonログだけ残します。
- ボタンだけで操作したい場合は `InpManualButtonOnly = true` にします。
- 実発注には `InpSignalOnly = false`、`InpEnableTrading = true`、`InpAllowLiveTrading = true`、`InpRequireStrategyTester = false`、`InpChartButtonDryRunOnly = false`、`InpAllowChartButtonTrading = true` がすべて必要です。

推奨:

```text
Symbol: XAUUSD-m
Period: M1
Model: Every tick based on real ticks
Forward: 1/4 またはCustom
Lot: 0.10
Max total lot: 0.30
```

TesterのInputsでは以下をLoadできます。

```text
Swing_Evaluation_Trader_backtest.set
Swing_Evaluation_Trader_forward_test.set
Swing_Evaluation_Trader_sample_collection.set
Swing_Evaluation_Trader_optimization.set
Swing_Evaluation_Trader_next_optimization.set
Swing_Evaluation_Trader_buy_refit.set
Swing_Evaluation_Trader_buy_entry_refit.set
Swing_Evaluation_Trader_buy_hour03_validation.set
Swing_Evaluation_Trader_buy_strong_hours_validation.set
Swing_Evaluation_Trader_buy_strong_hours_m30m15_validation.set
Swing_Evaluation_Trader_buy_wide_stop_validation.set
Swing_Evaluation_Trader_buy_hour03_wide_stop_validation.set
Swing_Evaluation_Trader_buy_hour03_wide_stop_calendar_validation.set
Swing_Evaluation_Trader_sell_entry_refit.set
Swing_Evaluation_Trader_sell_regime_entry_refit.set
Swing_Evaluation_Trader_sell_hour12_validation.set
Swing_Evaluation_Trader_sell_hour12_m30m15_validation.set
Swing_Evaluation_Trader_sell_hour12_m30m15_calendar_validation.set
```

`Swing_Evaluation_Trader_buy_score_weight_refit.set` と `Swing_Evaluation_Trader_sell_score_weight_refit.set` は `score_weight_set.py` がwalk-forward合格済み候補から生成した時だけLoadします。生成前の通常Inputs一覧には含めません。

このMacではMT5側にも配置済みです。

```text
MQL5/Profiles/Tester/Swing_Evaluation_Trader_backtest.set
MQL5/Profiles/Tester/Swing_Evaluation_Trader_forward_test.set
MQL5/Profiles/Tester/Swing_Evaluation_Trader_sample_collection.set
MQL5/Profiles/Tester/Swing_Evaluation_Trader_optimization.set
MQL5/Profiles/Tester/Swing_Evaluation_Trader_next_optimization.set
MQL5/Profiles/Tester/Swing_Evaluation_Trader_stable_candidate_next.set
MQL5/Profiles/Tester/Swing_Evaluation_Trader_buy_refit.set
MQL5/Profiles/Tester/Swing_Evaluation_Trader_buy_entry_refit.set
MQL5/Profiles/Tester/Swing_Evaluation_Trader_buy_hour03_validation.set
MQL5/Profiles/Tester/Swing_Evaluation_Trader_buy_strong_hours_validation.set
MQL5/Profiles/Tester/Swing_Evaluation_Trader_buy_strong_hours_m30m15_validation.set
MQL5/Profiles/Tester/Swing_Evaluation_Trader_buy_wide_stop_validation.set
MQL5/Profiles/Tester/Swing_Evaluation_Trader_buy_hour03_wide_stop_validation.set
MQL5/Profiles/Tester/Swing_Evaluation_Trader_buy_hour03_wide_stop_calendar_validation.set
MQL5/Profiles/Tester/Swing_Evaluation_Trader_sell_entry_refit.set
MQL5/Profiles/Tester/Swing_Evaluation_Trader_sell_regime_entry_refit.set
MQL5/Profiles/Tester/Swing_Evaluation_Trader_sell_hour12_validation.set
MQL5/Profiles/Tester/Swing_Evaluation_Trader_sell_hour12_m30m15_validation.set
MQL5/Profiles/Tester/Swing_Evaluation_Trader_sell_hour12_m30m15_calendar_validation.set
MQL5/Profiles/Tester/Swing_Evaluation_Trader_backtest.ini
MQL5/Profiles/Tester/Swing_Evaluation_Trader_forward_test.ini
MQL5/Profiles/Tester/Swing_Evaluation_Trader_strategy_test.ini
MQL5/Profiles/Tester/Swing_Evaluation_Trader_sample_collection.ini
MQL5/Profiles/Tester/Swing_Evaluation_Trader_optimization.ini
MQL5/Profiles/Tester/Swing_Evaluation_Trader_next_optimization.ini
MQL5/Profiles/Tester/Swing_Evaluation_Trader_stable_candidate.ini
```

Strategy Testerで手動テストする手順:

1. MetaEditorで `Experts/Swing_Evaluation_Trader.mq5` をCompileする。
2. MT5で `View -> Strategy Tester` を開く。
3. Expertに `Swing_Evaluation_Trader` を選ぶ。
4. Symbolは `XAUUSD-m`、Periodは `M1`、Modelは `Every tick based on real ticks` にする。
5. Datesはまず `2026.06.30` から `2026.07.08` にする。純バックテストならForwardは使わず、Forward検証なら `1/4` にする。
6. Inputsで、純バックテストなら `Swing_Evaluation_Trader_backtest.set`、Forward検証なら `Swing_Evaluation_Trader_forward_test.set` をLoadする。
7. Startで実行する。最適化する場合だけ `Swing_Evaluation_Trader_optimization.set` をLoadし、Optimizationを有効にする。推薦結果を絞り込む2回目の最適化では `Swing_Evaluation_Trader_next_optimization.set` をLoadする。

`Swing_Evaluation_Trader_optimization.set` はBUY/SELLそれぞれのRRを `1:2`、`1:3`、`1:4`、`1:5` で探索します。`InpMinRiskReward=2.0` にしているため、`1:2` が内部で `1:3` に丸められません。

BUYの初回refitでPF/Forwardが残らない場合は `Swing_Evaluation_Trader_buy_entry_refit.set` を使います。これはBUY only、RR `1:2`-`1:5`、`InpUseFittedBuyEntryFilter=true` 固定で、`InpBuyRequireBreakConfirm`、`InpBuyMinM1ClosePosition`、`InpBuyMinM1BodyAtr`、`InpBuyMinM5CloseSlowAtr` を探索する診断用セットです。

BUY entry refitでも全体が崩れ、特定時間だけが残る場合は `Swing_Evaluation_Trader_buy_hour03_validation.set` を使います。これはBUY only、`InpUseBuyAllowedServerHours=true`、`InpBuyAllowedServerHours=3` 固定で、03:00-04:00サーバー時間のBUYだけを検証する診断用セットです。

hour03単独ではpassごとの取引数が薄い場合は `Swing_Evaluation_Trader_buy_strong_hours_validation.set` を使います。これはBUY only、`InpBuyAllowedServerHours=3,5,6,10` 固定で、強いBUY時間帯をまとめて再検証する診断用セットです。

強いBUY時間帯でも下落/混合レジームで崩れる場合は `Swing_Evaluation_Trader_buy_strong_hours_m30m15_validation.set` を使います。これはBUY only、`InpUseBuyM30M15UpGate=true`、`InpBuyAllowedServerHours=3,5,6,10` 固定で、M30/M15が両方upの時だけBUYを検証します。

BUY強時間帯 + M30/M15 upが年次で崩れ、広めSL帯だけが残る場合は `Swing_Evaluation_Trader_buy_wide_stop_validation.set` を使います。これはBUY only、同じ時間帯/上位足ゲートを固定し、`InpMinStopPoints=300`、`InpMaxStopPoints=350` でSL 300-350ptだけを検証する診断用セットです。back/forwardと年次が通るまでは採用しません。

wide-stop診断でもentry 03:00-04:00だけが強い場合は `Swing_Evaluation_Trader_buy_hour03_wide_stop_validation.set` を使います。これはBUY only、`InpBuyAllowedServerHours=3`、`InpUseBuyM30M15UpGate=true`、SL 300-350ptを同時に固定し、時間帯分割でback/forwardが残るかを見る診断用セットです。

hour03 wide-stopの年次検証がPF 1.1593で昇格閾値に届かず、6月/8月/10月や水曜/金曜で崩れる場合は `Swing_Evaluation_Trader_buy_hour03_wide_stop_calendar_validation.set` を使います。これは同じhour03/M30-M15 up条件を維持し、`InpUseFittedBuyCalendarFilter` のON/OFFを432 passで確認する診断用セットです。2025年通期ではPF 1.1215へ悪化したため、採用せず診断止まりです。弱いBUY月は `6,8,10`、曜日はMT5 `day_of_week` の `3,5` です。

SELLの年次検証でSLヒット過多が残る場合は `Swing_Evaluation_Trader_sell_entry_refit.set` を使います。これはSELL only、RR `1:2`-`1:5`、SL 250-350pt、`InpUseFittedSellEntryFilter=true` 固定で、`InpSellRequireBreakConfirm`、`InpSellMaxM1ClosePosition`、`InpSellMinM1BodyAtr`、`InpSellMaxM5CloseSlowAtr` を主に探索する診断用セットです。

entry品質だけでback/forward安定passが出ない場合は `Swing_Evaluation_Trader_sell_regime_entry_refit.set` を使います。これはSELL only、RR `1:3`-`1:5`、SL 250-300pt、entry filter ON固定に加えてtrend/time filterのON/OFFを同時に探索する診断用セットです。

`score_inversion` が残る場合は、先に `methods/swing_eval/analysis/weight_search.py --side buy|sell --walk-forward` で評価関数の部品倍率を探索し、合格した候補だけ `methods/swing_eval/analysis/score_weight_set.py` でMT5検証用setへ変換します。`--regime-search entry_hour,m30_m15_trend,m30_trend,m15_trend,htf_alignment` を付けると、時間帯や上位足レジーム別にも同じ探索を行い、全体fitでは落ちるが一部レジームだけ残る候補を確認できます。`score_weight_set.py` はwalk-forward aggregateが `walk_forward_candidate_passed` でない限り、既定では `.set` を書きません。SELL側は `Swing_Evaluation_Trader_sell_regime_entry_refit.set` をテンプレートにして `Swing_Evaluation_Trader_sell_score_weight_refit.set` を作り、BUY側は `Swing_Evaluation_Trader_buy_refit.set` から `Swing_Evaluation_Trader_buy_score_weight_refit.set` を作ります。生成後は専用config `Swing_Evaluation_Trader_sell_score_weight_refit.ini` / `Swing_Evaluation_Trader_buy_score_weight_refit.ini` でMT5のback/forward最適化にかけます。ここで良く見えても、MT5 Optimizationと年次検証を通るまでは採用しません。Gateは `runtime/latest_score_weight_set_168h_<side>_rr4.json` も読み、`walk_forward_not_passed` やレジーム別 `walk_forward_sample_shortage` の場合は同じ変換を繰り返さず、history確認と `Swing_Evaluation_Trader_sample_collection.set` による診断サンプル収集計画を出します。採否はJSON直下の `decision.status`、`decision.adoptable`、`decision.next_action`、`decision.failure_mode` を見ればプログラム単体でも判定できます。`latest_spec_coverage.md` の `score_weight_follow_up_buy/sell` には、top候補、walk-forwardのtest件数/不足fold/delta、平均R/PF、baseline比、`failure_mode`、レジーム候補のsample shortage、`.set` 書き出し停止理由を短く出すため、MT5でsample collectionを回す前に「全体性能劣化なのか、レジームだけ追加サンプル待ちなのか」を確認できます。

件数を集めて評価関数を診断するだけなら `Swing_Evaluation_Trader_sample_collection.set` を使います。これは `InpUseDailyLossStop=false`、`InpUseConsecutiveLossStop=false` のテスター専用設定です。実運用寄りの停止条件確認やデモForward判定には使わず、純バックテストは `backtest.set`、Forward検証は `forward_test.set` に戻してください。自動Runnerから実行する場合は `--focus-side sell|buy|both` ごとに `runtime/latest_mt5_tester_sample_collection_<side>_run.json` と `runtime/latest_mt5_sample_collection_<side>_report.json` へ分けて保存し、`--sync-expert-parameters-set` で対象 `.set` だけをMT5 profileへ同期してから起動します。

Promotion GateにBUY/SELL両方のsample collectionが出ている場合、Next Action Runnerは `--focus-side` で明示選択できます。SELLを優先実行する場合は `python3 methods/swing_eval/analysis/mt5_next_action_run.py --target score_weight_sample_collection --focus-side sell --output-json runtime/latest_mt5_next_action_run.json --output-md runtime/latest_mt5_next_action_run.md`、BUYを先に確認したい場合は `--focus-side buy` にします。生成されるMarkdownには、そのside用のStrategy Tester設定表と `--csv-modified-after` 付きcollect-onlyコマンドが出ます。

Back/Forward、SELL sample collection、BUY sample collectionをMT5画面でまとめて回す場合は、手動キューを生成します。

```bash
python3 methods/swing_eval/analysis/mt5_manual_test_queue.py \
  --output-json runtime/latest_mt5_manual_test_queue.json \
  --output-md runtime/latest_mt5_manual_test_queue.md
```

MT5上で実際にStartする直前に、同じMarkdownの `Mark manual run start command` を1回実行します。これは `--mark-manual-run-start` 付きでキューを再生成し、Back/Forward、SELL/BUY sample、Optimization entryの `manual_run_start_after` / `collect_modified_after` を現在時刻へ更新します。これにより、後で `mt5_manual_collect.py` がqueue refreshしても、古いTester ReportやAgent CSVを誤って回収しない下限時刻が維持されます。

MT5 Optimizationも同じ手動キューに並べたい場合は、`--include-optimization-configs` を付けます。これで `Swing_Evaluation_Trader_optimization.ini` と `Swing_Evaluation_Trader_next_optimization.ini` がBack/Forward/SELL/BUYの後ろに追加され、`Optimization=2` かつ `ForwardMode=3` のstepは `XML + forward XML + Agent CSV` を期待成果物として表示されます。任意の診断 `.ini` を追加する場合は `--include-static-config methods/swing_eval/mt5/TesterConfigs/<name>.ini` を繰り返し指定します。標準の保存先は `runtime/latest_mt5_manual_test_queue_with_optimization.json` / `.md` です。`latest_spec_coverage.md` の `run_mt5_manual_test_queue` には、この最適化込みキューを生成する `refresh_manual_test_queue_with_optimization`、次step起動dry-run、collect dry-runも表示されます。静的config entryは `static_strategy_config_state` に手動実行開始時刻を保存するため、後で `mt5_manual_collect.py` がqueue refreshしても `--csv-modified-after` の下限時刻は実行前の時刻のまま維持されます。

BUY候補不足をMT5上で診断する場合は、最適化込みキューへ静的候補ラベルを追加します。`buy_wide_stop_short` は短期wide-stop診断、`buy_hour03_wide_stop_2025` と `buy_hour03_wide_stop_calendar_2025` は2025年通期のForward 1/4診断です。これは採用設定ではなく、Back/ForwardとPromotion Gateを通るかを確認するための検証キューです。

```bash
python3 methods/swing_eval/analysis/mt5_manual_test_queue.py \
  --include-optimization-configs \
  --include-static-candidate-label sell_hour12_m30m15_2025 \
  --include-static-candidate-label sell_hour12_m30m15_calendar_2025 \
  --include-static-candidate-label buy_wide_stop_short \
  --include-static-candidate-label buy_hour03_wide_stop_2025 \
  --include-static-candidate-label buy_hour03_wide_stop_calendar_2025 \
  --output-json runtime/latest_mt5_manual_test_queue_with_optimization.json \
  --output-md runtime/latest_mt5_manual_test_queue_with_optimization.md
```

MT5で作業する時に長いキュー全体ではなく次の1手だけを見たい場合は、operator packetを生成します。`runtime/latest_mt5_manual_operator_packet_with_optimization.md` は、現在実行するstep、MT5入力、全step順序、起動dry-run状態、Bridge Recovery、Bridge検証コマンド、Strategy Evidence、実行後のcollectコマンドだけを短く表示します。先頭寄りの `MT5 Run Sheet` には、Strategy Testerへ転記するExpert、Symbol、Period、Model、From/To、Forward、Optimization、Inputs、Reportと、Backtest/Forward 2本の順番、Start前mark、実行後collectコマンドをまとめて表示します。`next_operator_action` には `manual_strategy_tester_input`、`auto_launch_selected_step`、`collect_ready_results`、`wait_for_mt5_report` などの正規化された次操作、mode、instruction、実行コマンド、MT5実行前のmark command、follow-up collectコマンドを出すため、Markdownを全部読まなくても「MT5へ手入力する」「/configで起動する」「readyな結果をcollectする」のどれかをJSONだけで判定できます。packet JSON直下の `next_operator_before_mt5_command_text`、`next_step_quick_input`、`next_step_operator_summary`、`next_step_collect_filter_summary` でも、Start前mark、MT5入力値、次step要約、回収フィルタを直接読めます。同じ要約は `runtime/latest_mt5_tester_status.md` 冒頭の `MT5 Next Operator Action` と、`operator_summary.manual_operator_packet_with_optimization_*` にも転記されるため、Backtest/Forward Testの手入力、report待ち、collect実行をstatusファイルだけで追えます。status JSONと `runtime/mt5_tester_status_watch_heartbeat_current.json` では `manual_operator_packet_with_optimization_next_operator_before_mt5_command_text`、`manual_operator_packet_with_optimization_next_step_quick_input`、`manual_operator_packet_with_optimization_next_step_operator_summary`、`manual_operator_packet_with_optimization_next_step_collect_filter_summary` を見れば、packet由来の実行前mark command、MT5入力値、次step要約、回収フィルタをそのまま読めます。さらに `latest_mt5_tester_status.json` 直下の `mt5_operator_handoff_state`、`mt5_operator_handoff_next_mt5_step`、`mt5_operator_handoff_quick_input`、`mt5_operator_handoff_manual_collect_execute_command_text` でも、MT5画面で次に回すstepと実行後の取り込み入口をネストを読まずに確認できます。Strategy EvidenceにはBack/Forward証跡、source-time刷新計画、source-time分析再生成コマンド、BUY診断キュー、BUY診断collectコマンドの要点が出ます。MT5端末がすでに開いていて `/config` 直起動できない場合は、Launch Statusに `manual_input_required` と `running_terminal_blocks_direct_config` が出るため、表示されたMT5 InputをStrategy Testerへ手動入力します。Bridge Recoveryが `needs_ea_restart` でも、packetの `Standalone Strategy Tester allowed=True` ならBridge復旧と切り分けてMT5上のBacktest/Forward Testを進めます。

```bash
python3 methods/swing_eval/analysis/mt5_manual_operator_packet.py \
  --queue runtime/latest_mt5_manual_test_queue_with_optimization.json \
  --queue-launch-json runtime/latest_mt5_manual_queue_launch_with_optimization.json \
  --bridge-recovery-plan-json runtime/latest_bridge_recovery_plan.json \
  --strategy-analysis-json runtime/latest_mt5_strategy_tester_analysis.json \
  --output-json runtime/latest_mt5_manual_operator_packet_with_optimization.json \
  --output-md runtime/latest_mt5_manual_operator_packet_with_optimization.md
```

MT5でStrategy Testerを実行した後、ready検知だけをファイルに残す場合はauto collect watcherを1回実行します。`--execute-ready` を付けない限り取り込みは実行しません。watcherは同じタイミングで `runtime/latest_mt5_manual_queue_launch_with_optimization.md` と `runtime/latest_mt5_manual_operator_packet_with_optimization.md` も更新するため、次にMT5上で回す1手、自動起動可否、MT5 Start直前に実行する `--mark-manual-run-start` コマンド、Bridge復旧状態、Strategy Evidence、source-time/BUY診断の回収入口も古くなりにくくなります。`runtime/latest_mt5_manual_auto_collect_watch.json` の `ready_for_collect_execute`、`selected_count`、`waiting_count`、`invalid_count` を見れば、collect可能か、まだ何件待ちかをトップレベルだけで確認できます。
watcherのJSON/Markdown/heartbeatには `Collect dry-run command` と `Collect execute command` も出ます。MT5レポートがreadyになった後は、そのexecuteコマンドで同じ条件のcollect-onlyと `--refresh-post-collect-analysis` を再実行できます。
この1回実行は既定では常駐監視用の `runtime/mt5_manual_auto_collect_watch_heartbeat.json` とPIDファイルを上書きしません。Bridge、MT5 tester status、forward test/status のwatcherも同じで、`--max-runs 1` は明示的に `--heartbeat` と `--pid-file` を指定した時だけ共有daemon stateへ書きます。常駐監視のheartbeatを更新したい場合だけ、`runtime_watchers.py` から起動するか、明示pathを指定します。

```bash
python3 methods/swing_eval/analysis/mt5_manual_auto_collect_watch.py \
  --queue runtime/latest_mt5_manual_test_queue_with_optimization.json \
  --collect-output-json runtime/latest_mt5_manual_collect_with_optimization.json \
  --collect-output-md runtime/latest_mt5_manual_collect_with_optimization.md \
  --bridge-recovery-plan-json runtime/latest_bridge_recovery_plan.json \
  --strategy-analysis-json runtime/latest_mt5_strategy_tester_analysis.json \
  --output-json runtime/latest_mt5_manual_auto_collect_watch.json \
  --output-md runtime/latest_mt5_manual_auto_collect_watch.md \
  --max-runs 1
```

MT5レポートがreadyになったら、同じwatcherに `--execute-ready` を付けると、readyなcollect-onlyだけを実行し、Promotion Gate、Strategy Tester Analysis、Spec Coverageまで更新します。

```bash
python3 methods/swing_eval/analysis/mt5_manual_auto_collect_watch.py \
  --queue runtime/latest_mt5_manual_test_queue_with_optimization.json \
  --collect-output-json runtime/latest_mt5_manual_collect_with_optimization.json \
  --collect-output-md runtime/latest_mt5_manual_collect_with_optimization.md \
  --bridge-recovery-plan-json runtime/latest_bridge_recovery_plan.json \
  --strategy-analysis-json runtime/latest_mt5_strategy_tester_analysis.json \
  --output-json runtime/latest_mt5_manual_auto_collect_watch.json \
  --output-md runtime/latest_mt5_manual_auto_collect_watch.md \
  --max-runs 1 \
  --execute-ready
```

常駐監視として起動する場合はruntime watcher管理から `mt5_manual_auto_collect` だけを起動します。通常の常駐版は `--execute-ready` を付けず、ready検知だけを行います。MT5上でBacktest/Forwardを回した後に、readyになったレポートを自動でcollectしてPromotion Gate、Strategy Tester Analysis、Spec Coverageまで更新したい場合だけ、管理コマンドに `--mt5-manual-auto-collect-execute-ready` を付けて起動またはrestartします。
常駐版は `--max-runs 0`、共有heartbeat、共有PIDファイル付きで起動されるため、`runtime_watchers.py --dry-run` からdaemon状態、PID一致、schema互換性を確認できます。
既存daemonが検知専用のまま動いている時に自動collectモードを要求すると、`running_heartbeat_mode_mismatch` として表示されます。その場合は `--restart --mt5-manual-auto-collect-execute-ready` で起動し直します。

```bash
python3 methods/swing_eval/analysis/runtime_watchers.py --only mt5_manual_auto_collect
python3 methods/swing_eval/analysis/runtime_watchers.py --only mt5_manual_auto_collect --restart --mt5-manual-auto-collect-execute-ready
```

`runtime/latest_mt5_manual_test_queue.md` にはMT5 Strategy Testerで選ぶExpert、Symbol、Period、Model、Dates、Forward、Optimization、Inputs、Report名をBack/Forward/SELL/BUYの順にまとめて表示します。上部の `MT5 Strategy Tester Targets` ではBacktest、Forward Test、SELL/BUY sampleの目的、Report、Inputs、start after、collect after、collect状態、自動起動種別に加えて、`optimization`、`run type`、`expected report`、`report note` を先に確認できます。`Optimization=0` のBacktest/Forward/sample collectionは単発Strategy Testなので、Forward指定があっても期待成果物は `HTML report + Agent CSV` です。Optimization Forwardを使う最適化runだけ `Fast genetic algorithm` と `XML + forward XML + Agent CSV` を期待します。`MT5 Operation Cards` とJSONの `operation_cards` には、`is_next`、`action`、目的、queue/step、Forward、Optimization、Inputs、Report、collect statusを短く出します。Markdownを開かない監視でも、次にMT5で実行する1手をここから読めます。`Manual Execution Checklist` にはBacktest、Forward、SELL sample、BUY sampleを `[ ]` 付きで並べ、MT5画面ではこの順番でSymbol、Period、Model、Dates、Forward、Optimization、run type、expected report、Inputs、Report、start afterを確認します。`Auto Launch Commands` には、各stepのworkspace `.ini`、MT5側 `MQL5/Profiles/Tester` の `.ini`、起動コマンドを出します。固定 `.ini` のReport/Dates/Forwardがstepと一致するBacktest/ForwardはWine経由の `terminal64.exe /config:` 直起動になり、Report名などのruntime上書きが必要なSELL/BUY sample collectionはrunner executeコマンドになります。既存MT5端末が開いている時は `/config` 起動がブロックされるため手動チェックリストを使い、端末を閉じてから自動起動したい場合だけこのコマンドを使います。Queue表と各collectブロックには `runner generated`、`gate generated`、`current gate`、`decision`、`current gate decision`、`start after` も出るため、手動実行後の `--csv-modified-after` に使うrunner生成時刻、runner作成時のPromotion Gate世代、最新Promotion Gateでも同じactionとして実行可能かを分けて確認できます。Back/Forward Runnerのように `runner_generated_at` を持たないartifactでは、計画JSONの `generated_at` をrunner生成時刻として表示します。各ブロックのcollect-onlyコマンドも同じファイルに出るため、MT5手動実行後は `Ready to collect` と `Collect status` を確認してから該当コマンドで取り込みます。まとめて取り込む場合は `methods/swing_eval/analysis/mt5_manual_collect.py` を使います。既定はdry-runで、元runnerの `manual_collect_readiness` とキューを再評価してから `collect_ready=true` のentryだけを選びます。`latest_mt5_manual_collect_run.md` のplanned/skipped/invalidにも `runner generated`、`gate generated`、`decision`、`next_action`、`blocking_reasons` が出るため、MT5で実行した手順と回収対象の世代、次に見るべき待ち理由を照合できます。`--execute` を付けた時だけ許可済みの `--collect-only` コマンドを順番に実行します。既定のsource runner再評価が失敗した場合は `blocked_queue_refresh_failed` で実行を止めます。再評価せず保存済みキューをそのまま使う場合だけ `--no-refresh-queue` を付けます。このキューは `latest_mt5_tester_status.md` の `MT5 Manual Test Queue` と、`mt5_tester_status_watch_heartbeat_current.json` の `manual_test_queue_*` にも転記されるため、定期監視ファイルだけでも4本の手動Strategy Tester待ちを確認できます。`manual_test_queue_strategy_tester_targets`、`manual_test_queue_operation_cards`、`manual_test_queue_execution_checklist` もheartbeatの必須snapshot keyなので、古いwatcherがTarget要約、次の操作カード、手動実行順を転記できない場合は `incompatible` になります。`latest_mt5_tester_status.md` と `latest_spec_coverage.md` にも同じTarget要約、operation cards、チェックリストを転記するため、status/coverageだけを開いた場合でもMT5画面で実行する順番と取り込み対象時刻を確認できます。status watcherは各更新の先頭で `mt5_manual_collect.py` のdry-runも実行し、`manual_collect_refresh_*` と最新の `manual_collect_run_*` をheartbeatへ残します。最適化込みキューがある場合は `latest_mt5_tester_status.md` の `MT5 Manual Test Queue With Optimization` / `MT5 Manual Queue Launch With Optimization` / `MT5 Manual Collect With Optimization` にも転記し、`MT5 Next Operator Action` には `latest_mt5_manual_operator_packet_with_optimization.json` の正規化済み次操作を表示します。heartbeatには `manual_test_queue_with_optimization_*`、`manual_queue_launch_with_optimization_*`、`manual_collect_with_optimization_*`、`manual_operator_packet_with_optimization_*` と `manual_collect_with_optimization_refresh_*` / `manual_queue_launch_with_optimization_refresh_*` を追加情報として残します。これは既存必須schemaではなく、通常キューを壊さずOptimization Forwardの待ち状態を併読するための任意フィールドです。手動テスト完了後に `selected_count > 0` になったら、必要に応じて `python3 methods/swing_eval/analysis/mt5_manual_collect.py --execute` で実取り込みします。`latest_spec_coverage.md` も `run_mt5_manual_test_queue` をNext Actionに出し、キュー全体のentry/step/waiting/ready件数、Manual Execution Checklist、entry別status、runner/Gate世代、collect可能な場合のcollect-onlyコマンドと一括collectorコマンドをまとめて表示します。CoverageのRuntime ArtifactsにはSELL用の `latest_mt5_next_action_run.json` に加えてBUY用の `latest_mt5_next_action_run_buy.json` も含め、古いBUY手順や欠落したBUY runnerを手動実行前に検出します。runner artifactが欠落またはstaleの場合は `refresh_mt5_next_action_runner_artifacts` を出し、SELL/canonicalとBUY runner、統合手動キュー、MT5 tester statusを順に再生成するコマンドを表示します。
MT5手動実行後にcollectと横断採用判定をまとめて更新する場合は、`--refresh-strategy-tester-analysis` を付けます。

```bash
python3 methods/swing_eval/analysis/mt5_manual_collect.py \
  --queue runtime/latest_mt5_manual_test_queue.json \
  --execute \
  --refresh-strategy-tester-analysis \
  --output-json runtime/latest_mt5_manual_collect_run.json \
  --output-md runtime/latest_mt5_manual_collect_run.md
```

この場合、collectが `collect_executed` になった後で `runtime/latest_mt5_strategy_tester_analysis.json` / `.md` も再生成されます。まだreadyなcollect対象がない場合やcollectが失敗した場合は、横断分析はスキップされ、`latest_mt5_manual_collect_run.md` の `Strategy Tester Analysis Refresh` に理由が残ります。
MT上で次に回すBacktest/Forward stepは `runtime/latest_mt5_tester_status.md` と `runtime/latest_mt5_strategy_tester_analysis.md` の `Next MT5 step` で確認できます。`latest_mt5_strategy_tester_analysis.md` には参照元artifactの生成時刻/mtime、Optimization Evidenceのsource-time整合、通常手動キューと最適化込みキューのhandoff、collect dry-run/execute/analysis refreshコマンド、`Operation Cards`、`Manual Execution Checklist`、coverage next actionsも転記されるため、Optimization証跡、採用ブロッカー、MT5で回す順番、実行後の回収コマンド、次の優先アクションを同じレポートで確認できます。`latest_spec_coverage.md` のRuntime Artifactsにも `strategy_tester_analysis_source_artifacts` とlabel別の生成時刻/状態/pathが出るため、Coverageだけでも横断分析がどのPromotion Gate、Back/Forward run、手動キュー世代を読んだか確認できます。Back/Forwardの採否はJSON直下の `back_forward_decision.status`、`back_forward_decision.adoptable`、`back_forward_decision.next_action` を見ます。`passed` ならPromotion Gateへ証跡として使え、`run_manual_back_forward` はMT5未実行、`collect_ready` は回収待ち、`sample_shortage` は期間/件数不足、`forward_regression` / `forward_below_break_even` はForward崩れとして再fitまたは棄却候補です。候補レポートのsource-timeが不一致、年次候補で欠落、またはレポートが参照しているAgent CSVが古い/消えている場合は、横断採用ブロッカーと `latest_spec_coverage.md` の `refresh_mt5_strategy_source_time_evidence` に出ます。このNext Actionは最適化込み手動キューの再生成、launch dry-run、collect dry-run、`--refresh-strategy-tester-analysis` 付き回収、coverage再生成までのコマンドをまとめます。MT5でレポートを保存した後は、同じMarkdown内の `Collect execute + analysis command` / `Queue collect + analysis command` を実行すると、取り込みと採用横断判定までまとめて更新できます。

JSONを読む監視や自動判断では、`runtime/latest_mt5_manual_test_queue.json` の `operator_handoff` を使います。`state`、`next_mt5_step`、ready/waiting/stale entry、collect dry-run/executeコマンドが1つにまとまっています。
`runtime/latest_mt5_manual_queue_launch.json` / `.md` にも同じhandoff要約を転記します。`selected_matches_queue_handoff` が `true` なら、ランチャーが選んだstepとキューが推奨する次stepが一致しており、同じファイル内のcollect dry-run/executeコマンドで実行後の回収確認まで進められます。最適化込みキューを使う場合は `--queue runtime/latest_mt5_manual_test_queue_with_optimization.json` を指定し、結果は `runtime/latest_mt5_manual_queue_launch_with_optimization.json` / `.md` に保存します。標準キューのlaunch handoffはstatus watcher heartbeatの必須snapshot keyです。最適化込みlaunch handoffは `*_with_optimization_*` の追加フィールドとして転記します。

端末を閉じて `/config` 起動で次の1ステップだけ実行したい場合は、先にランチャーをdry-runします。

```bash
python3 methods/swing_eval/analysis/mt5_manual_queue_launch.py \
  --queue runtime/latest_mt5_manual_test_queue.json \
  --output-json runtime/latest_mt5_manual_queue_launch.json \
  --output-md runtime/latest_mt5_manual_queue_launch.md
```

`latest_mt5_manual_queue_launch.md` で選択step、queue handoff、collect command、起動コマンドを確認し、既存 `terminal64.exe` が検出されていない状態でだけ `--execute --detached` を付けます。`--detached` は `direct_config` の `/config` 起動を非同期にし、MT5画面上でStrategy Testerを走らせたままCLIをすぐ戻して `status=launched` とPIDを残します。`direct_config` のBacktest/Forwardは既存MT5が起動中なら `running_terminal_blocks_direct_config` で止まり、SELL/BUY sample collectionは保存済みrunner executeコマンド経由で起動します。

`latest_spec_coverage.md` の `run_mt5_manual_test_queue` には、`latest_mt5_tester_status.json.operator_summary` 由来の次のMT5 Strategy Tester step、launch blocker、collect executeコマンドを先頭付近に表示します。さらにmanual queue launch dry-runの選択step、起動種別、blocked、blocked reasons、起動中terminal件数、launch handoffの次step/selected一致/collect executeコマンド、manual collect runのstatus、next action、blocking reasonsも表示されるため、coverageだけでもMT5を閉じて自動起動へ進むべきか、手動実行待ちかcollect実行待ちかを確認できます。Runtime Artifacts表にも同じoperator summary、status/next action/blocking reasonsとready/selected/waiting/invalid件数が出ます。

Coverageからstatusを再生成する `refresh_mt5_tester_status` 系コマンドも、通常キューに加えて `latest_mt5_manual_test_queue_with_optimization.json`、`latest_mt5_manual_queue_launch_with_optimization.json`、`latest_mt5_manual_collect_with_optimization.json`、`latest_mt5_manual_operator_packet_with_optimization.json` を明示して読みます。これにより、Back/ForwardだけでなくOptimization Forwardの待ち状態と次operator actionも `latest_mt5_tester_status.md` に揃って残ります。

`latest_mt5_manual_queue_launch.json` もRuntime Artifacts表に出ます。`selected_queue_id`、`selected_step_label`、`launch_command_kind`、`blocked_reasons`、`running_terminal_count` を見ると、次に自動起動されるstepと、MT5起動中で止まっているかをcoverageだけで確認できます。

MT5の `/config` 起動で自動テストしたい場合は、以下の起動設定を使えます。

```text
methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_backtest.ini
methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_forward_test.ini
methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_strategy_test.ini
methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_sample_collection.ini
methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_optimization.ini
methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_next_optimization.ini
methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_stable_candidate.ini
methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_buy_refit.ini
methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_buy_entry_refit.ini
methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_buy_hour03_validation.ini
methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_buy_strong_hours_validation.ini
methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_buy_strong_hours_m30m15_validation.ini
methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_buy_wide_stop_validation.ini
methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_buy_hour03_wide_stop_validation.ini
methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_buy_hour03_wide_stop_calendar_validation.ini
methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_sell_entry_refit.ini
methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_sell_regime_entry_refit.ini
methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_sell_hour12_validation.ini
methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_sell_hour12_m30m15_validation.ini
methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_sell_hour12_m30m15_calendar_validation.ini
```

`backtest.ini` はForwardなしの単発バックテスト、`forward_test.ini` はForward 1/4の単発検証、`strategy_test.ini` は従来互換のForward 1/4単発テストです。`sample_collection.ini` は連敗停止で早期終了させずにサンプルを集める診断用、`optimization.ini` は広めのgenetic optimization用、`next_optimization.ini` は推薦結果から生成した focused optimization 用、`buy_refit.ini` はBUY初回refit用、`buy_entry_refit.ini` はBUY entry品質の再fit用、`buy_hour03_validation.ini` はBUYの03:00-04:00切り出し検証用、`buy_strong_hours_validation.ini` はBUYの03/05/06/10時台まとめ検証用、`buy_strong_hours_m30m15_validation.ini` は強時間帯かつM30/M15 up固定の検証用、`buy_wide_stop_validation.ini` は同条件でSL 300-350ptだけを検証する診断用、`buy_hour03_wide_stop_validation.ini` はentry 03時かつSL 300-350ptだけを検証する診断用、`buy_hour03_wide_stop_calendar_validation.ini` はhour03/wide-stopに弱い月/曜日のcalendar filterを加える診断用、`sell_entry_refit.ini` はSELL entry品質の再fit用、`sell_regime_entry_refit.ini` はentry品質とtrend/time regimeの複合refit用です。いずれも `XAUUSD-m`、`M1`、real ticks、期間 `2026.06.30` から `2026.07.08` を初期値にしています。

`forward_test.set` は診断用に `InpLogSignalRows=true` です。トレードが0件でも `swing_evaluation_trades.csv` にsignal行が残るため、HOLD数、BUY/SELL候補数、主な理由を集計できます。

MT5上で通常のバックテスト/フォワードテストを行う場合は、純バックテストなら `backtest.ini`、Forward 1/4なら `forward_test.ini` を使います。`Optimization=0` の単発Strategy TestではMT5がXMLではなくHTMLレポートだけを出すことがあります。この場合でも `mt5_tester_run.py --no-recommendation` は、HTMLレポートと新規Agent CSVを確認して `runtime/latest_mt5_*_report.*` に集計します。

`mt5_back_forward_run.py --mode both` で `--forward-mode 3` を指定した場合も、Backtest stepは常に `ForwardMode=0` の純バックテストとして扱い、Forward Test stepだけに `ForwardMode=3` を渡します。MT5上では `Swing_Evaluation_Trader_backtest.set` と `Swing_Evaluation_Trader_forward_test.set` を別々にLoadし、Report名も `Tester\Swing_Evaluation_Trader_backtest` と `Tester\Swing_Evaluation_Trader_forward_test` に分けます。`MT5 Strategy Tester Quick Start` の `MT5 mode` / `run type` / `report note` で、HTML reportを期待する単発Strategy Testか、XML + forward XMLを期待するOptimization Forwardかを確認できます。

backtest/forwardの2本をまとめて準備するdry-run:

```bash
python3 methods/swing_eval/analysis/mt5_back_forward_run.py \
  --mode both \
  --timeout-seconds 3600 \
  --since-minutes 240 \
  --min-closed 30
```

手動でMT5 Strategy Testerを回す前に、既存Agent CSVの期間だけ確認したい場合:

```bash
python3 methods/swing_eval/analysis/mt5_back_forward_run.py \
  --mode both \
  --run-archive-preview \
  --timeout-seconds 3600 \
  --since-minutes 240 \
  --min-closed 30
```

このdry-runはMT5を起動せず、`runtime/latest_mt5_agent_csv_archive_<run_id>_*.json` / `.md` に残存CSVのsource timeを保存します。

実際にMT5を起動して順に回す場合:

```bash
python3 methods/swing_eval/analysis/mt5_back_forward_run.py \
  --mode both \
  --execute \
  --refresh-ready-status \
  --timeout-seconds 3600 \
  --since-minutes 240 \
  --min-closed 30
```

MT5画面でBacktest/Forwardを手動実行した後、既存のTester XML/Agent CSVだけをRunner証跡へ取り込む場合:

```bash
python3 methods/swing_eval/analysis/mt5_back_forward_run.py \
  --mode both \
  --collect-only \
  --csv-modified-after "2026.07.13 17:30" \
  --timeout-seconds 3600 \
  --since-minutes 240 \
  --min-closed 30
```

`--collect-only` はMT5を起動せず、`mt5_tester_run.py --collect-only` をBacktest/Forward各stepに実行して、指定Report名のTester XMLとAgent CSVを集計します。Runner JSONでは `execute=true`、`collect_only=true`、`launch_mt5=false`、`dry_run=false` になり、BacktestとForwardの両レポートが揃えば `evidence_state` は `executed_consistent` / `executed_degraded` / `executed_below_break_even` / `executed_sample_shortage` のいずれかになります。手動実行時刻が分かる場合は `--csv-modified-after` を付け、古いAgent CSVを混ぜないようにしてください。`latest_mt5_back_forward_run.md` には `Manual Strategy Tester Checklist` も出し、MT5画面で選ぶExpert、Symbol、Period、Model、Dates、Forward、Inputs、Report名と、生成時刻を使った推奨 `--csv-modified-after` 付きcollect-onlyコマンドを確認できます。同じMarkdownの `Manual Strategy Tester Prerequisites` では、`runtime/latest_mt5_compile_status.json` を元に、必要なEA `.ex5`、Tester `.ini`、`ExpertParameters` `.set` がMT5側へ同期済みかをBacktest/Forward対象だけに絞って確認できます。`Back/Forward Plan Validation` では、BacktestとForwardが同じEA、Symbol、Period、Model、期間で、BacktestだけForward無効、Forward側だけForward有効、Reportや出力JSONが別名になっているかを確認できます。この前提条件と計画検証は `runtime/latest_mt5_tester_status.md` と `runtime/mt5_tester_status_watch_heartbeat_current.json` にも転記されるため、定期監視ファイルだけでも手動Strategy Testerへ進める状態か確認できます。前提条件がNGの場合は `runtime/latest_spec_coverage.md` の `Next Actions` に `refresh_mt5_back_forward_prerequisites` が出るため、Compile status更新とBack/Forward plan再生成を先に実行します。

Next Action Runnerで選ばれたMT5テスター系アクションも、`runtime/latest_mt5_next_action_run.md` に `Manual Strategy Tester Checklist` を出します。MT5上では表のExpert、Symbol、Period、Model、Dates、Forward、Inputs、Report名をそのまま設定してStrategy Testerを実行します。完了後は同じMarkdownの `Recommended collect-only`、または `runtime/latest_mt5_tester_status.md` / `runtime/mt5_tester_status_watch_heartbeat_current.json` の `Manual Strategy Tester collect-only` を実行すると、MT5を起動せずにTesterレポートとAgent CSVを取り込みます。古いCSV混入を避けるため、推奨コマンドにはRunner生成時刻を使った `--csv-modified-after` を付けています。Runner JSONでは互換性のため `generated_at` はPromotion Gate生成時刻のまま保持し、Runner自体の生成時刻は `runner_generated_at`、参照したGateは `promotion_generated_at` / `promotion_decision` で明示します。手動collectの下限時刻には `runner_generated_at` を使います。

`--execute` は既定で `runtime/latest_mt5_tester_status.json` を確認し、compileが新しい、MT5 terminalが起動中でない、直近のback/forward dry-run計画が現在の `--mode`、config、`ExpertParameters` `.set`、ForwardMode、base From/To、report名、予定出力先、`--timeout-seconds`、`--since-minutes`、`--min-closed`、`--from-date`、`--to-date`、`--forward-mode`、主要実行フラグ、dry-run JSONの `execution_conditions` と一致している、という条件を満たす時だけMT5を起動します。`mode=both` の実行またはcollect-onlyでは、先に `Back/Forward Plan Validation` を確認し、不整合があれば `back_forward_plan_validation_not_ready` でMT5起動や取り込みを止めます。`execution_conditions` では `skip_archive_preview` や `max_ready_status_age_seconds` も比較し、command配列だけでは分からない実行条件のずれも `ready_status_plan_mismatch` として止めます。dry-runとexecuteでは上のように同じ `--timeout-seconds`、`--since-minutes`、`--min-closed`、期間上書き、ForwardMode上書きを指定してください。`--run-archive-preview` を付けたdry-runでは、MT5起動前と同じarchive previewを実行し、残存CSVのsource timeとvalidation結果も `latest_mt5_back_forward_run.*` に残します。`latest_mt5_back_forward_run.json` / `.md` には `Execution Hints` として、同じ `run_id_prefix` と実行条件を引き継いだMT5起動コマンド、手動MT5実行後の `--collect-only` 取り込みコマンドも出ます。Runner Markdown本文にも `Skip archive preview` を表示し、`Execution Hints` の起動/collect-onlyコマンドにも同じ `--skip-archive-preview` を保持します。`latest_mt5_tester_status.md` のBack/Forward実行ヒントもready status最大鮮度と `--skip-archive-preview` を保持し、step commandが省略されたrunnerでも `execution_conditions` からtimeout、since、min closed、期間、ForwardMode、同期/許可フラグを復元します。`--execute --refresh-ready-status` を付けると、status更新の直前に同じ条件のdry-run planを `latest_mt5_back_forward_run.json` / `.md` へ一度書き、`methods/swing_eval/analysis/mt5_tester_status.py --back-forward-run ...` でそのplanを読ませてからpreflightを判定します。これにより、事前dry-runを忘れても今選んだBack/Forward条件が比較対象になります。dry-run JSON/Markdownには `execution_conditions` としてper-step timeout、since minutes、min closed、期間/ForwardMode上書き、同期/許可フラグを保存し、各stepのset名、ForwardMode、実効ForwardMode、timeoutを順次足した最大待ち時間と、今開始した場合の期限も出ます。statusのstep表で `0->3` のように出る場合は、左が `.ini` のbase ForwardMode、右が `--forward-mode` 上書き後にMT5へ渡る実効値です。同じ条件は `latest_mt5_tester_status.md` とstatus watcher heartbeatにも転記されます。status watcherはNext Action Runnerのprimary/archive preview/follow-up/follow-up archive preview出力先を `next_action_run_planned_outputs` にまとめても保持し、`latest_mt5_tester_status.md` の `Watch planned outputs` でMT5起動前に出力先を確認できます。Next Action Runnerについても、statusとheartbeatにMT5起動用 `execute_command_text` と、MT上で手動Strategy Testerを回した後に使う `collect_only_command_text` を転記するため、`latest_mt5_next_action_run.md` を開かなくても手動結果取り込みの入口を確認できます。Promotion Gateの `MT5 Back/Forward Runner Drift` 復旧planも、直近dry-runの `run_id_prefix`、timeout、since、min closed、期間/ForwardMode上書き、ready status最大鮮度を実行コマンドへ引き継ぎ、Markdownに `mt5_back_forward_conditions` として表示します。dry-runの `plan_only` は昇格証跡としてはFAIL扱いで、MT5上で実行済みのBack/Forward比較が必要です。実行後は各stepの `run_json` / `report_json` を読み直し、Tester runが未ブロックで成功し、期待レポートが存在する場合だけ全体OKにします。backtestとforwardの両方のレポートが揃った場合は、`Backtest Vs Forward Drift` としてclosed、PF、平均R、期待R、価格R DD、損益の差分を出し、backtestまたはforwardのclosedが `--min-closed` 未満なら `backtest_sample_shortage` / `forward_sample_shortage` / `back_forward_sample_shortage` として成績評価前に不採用にします。実行済みRunnerのstatusが `forward_degraded_vs_backtest` または `forward_below_break_even` の場合、Promotion Gateは候補setを採用せず再fit/再検証へ戻します。sample shortage系の場合は候補否定ではなく `collect_more_mt5_back_forward_samples_before_promotion` として、期間延長や診断gate調整でclosed件数を増やす導線にします。このnext actionには `sample_shortage_recovery` として `--from-date 2025.01.01 --to-date 2025.12.31` の拡張期間で回すBack/Forward再実行コマンドも表示します。`latest_spec_coverage.md` の `run_or_collect_mt5_back_forward` にも、Back/Forward比較status、backtest/forwardのclosed・PF・平均R・delta、sample shortage時の通年拡張再実行コマンドを転記します。ブロックやartifact不備は `runtime/latest_mt5_back_forward_run.md` の `Ready Status` / `Post execution validation` に理由が残り、比較対象は `Checked execution conditions` でも確認できます。明示的に無視する場合のみ `--skip-ready-status-check` を付けます。

Promotion GateのAgent CSV archive run IDは、実行するアクションごとの入力証跡をseedにします。たとえばscore sample collectionはscore/refit系の証跡だけでIDを決めるため、Back/Forward dry-run計画を更新しただけではNext Action Runnerの出力先はstaleになりません。

個別に回す場合:

```bash
python3 methods/swing_eval/analysis/mt5_back_forward_run.py --mode backtest --timeout-seconds 3600 --since-minutes 240 --min-closed 30
python3 methods/swing_eval/analysis/mt5_back_forward_run.py --mode backtest --execute --refresh-ready-status --timeout-seconds 3600 --since-minutes 240 --min-closed 30

python3 methods/swing_eval/analysis/mt5_back_forward_run.py --mode forward --timeout-seconds 3600 --since-minutes 240 --min-closed 30
python3 methods/swing_eval/analysis/mt5_back_forward_run.py --mode forward --execute --refresh-ready-status --timeout-seconds 3600 --since-minutes 240 --min-closed 30
```

```bash
python3 methods/swing_eval/analysis/mt5_tester_run.py \
  --config methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_forward_test.ini \
  --report-name 'Tester\Swing_Evaluation_Trader_forward_test' \
  --archive-agent-csvs-before-run \
  --agent-csv-archive-run-id strategy_forward_current \
  --min-closed 30 \
  --no-recommendation \
  --output-json runtime/latest_mt5_tester_forward_test_run.json \
  --output-md runtime/latest_mt5_tester_forward_test_run.md \
  --optimization-output-json runtime/latest_mt5_forward_strategy_report.json \
  --optimization-output-md runtime/latest_mt5_forward_strategy_report.md
```

テスト後はEAが出す `swing_evaluation_trades.csv` を集計します。

## Python分析コマンド

MT5配置/コンパイル状態:

EAやインジケータを編集した後は、MT5側の `.mq5` が同期済みで、`.ex5` が最新ソースより新しいかを確認します。Tester `.set` や `/config` 用 `.ini` を編集した後も、MT5側 `MQL5/Profiles/Tester` の `.set` / `.ini` が同期済みか確認します。

```bash
python3 methods/swing_eval/analysis/mt5_compile_status.py \
  --output-json runtime/latest_mt5_compile_status.json \
  --output-md runtime/latest_mt5_compile_status.md
```

`Compiled fresh: false` の場合は、MetaEditorで対象 `.mq5` をCompileしてからStrategy Testerを実行します。`Tester sets synced: false` の場合は `methods/swing_eval/mt5/TesterSets/*.set`、`Tester configs synced: false` の場合は `methods/swing_eval/mt5/TesterConfigs/*.ini` をMT5側 `MQL5/Profiles/Tester` へ配置し直します。`Tester Config ExpertParameters` には各 `.ini` が参照する `.set` の状態も出ます。score-weight refit用 `.set` はwalk-forward合格後に生成されるため、生成前は `generated_set_missing` と表示されます。

`mt5_tester_run.py` は全体一覧に加え、そのrunの `ExpertParameters` が指す `.set` を直接確認します。compile statusの一覧に出ない一時的な `.set` でも、workspace側とMT5側 `MQL5/Profiles/Tester` の内容が一致しない場合は `missing_mt5_set` / `set_not_synced` として起動前に止めます。

MetaEditor起動も含めて確認する場合:

```bash
python3 methods/swing_eval/analysis/mt5_compile.py \
  --output-json runtime/latest_mt5_compile_run.json \
  --output-md runtime/latest_mt5_compile_run.md
```

このコマンドはMetaEditorの終了コードだけでは成功扱いにせず、最後に `.ex5` の更新時刻を再確認します。`ok=false` / `Compiled fresh: false` の場合、MT5のStrategy Tester最適化は古いEAで走る可能性があるため止めます。

履歴取得ステータス:

Bridge/EA接続状態:

```bash
python3 methods/swing_eval/analysis/bridge_status.py \
  --output-json runtime/latest_bridge_status.json \
  --output-md runtime/latest_bridge_status.md
```

`operational_status=ready` ならBridge `/health` / `/config`、`latest_snapshot.json` の鮮度、履歴要求pending状態が揃っています。`ea_not_posting` の場合はBridge自体は応答しているが、MT5側EAの `/snapshot` / history chunk POSTが止まっている状態です。`Bridge Log` の `Activity status`、`Last EA POST`、`Last snapshot POST` を見ます。`GET /config` はstatus監視でも発生するため、EA生存判定はPOST時刻を優先します。JSONでは `ea_liveness_signal`、`config_get_recent`、`ea_post_recent`、`config_get_recent_but_ea_post_stale` を確認し、`config_get_only_not_liveness` ならBridge監視GETだけでEA POSTは止まっています。`MT5 Terminal / EA` にはterminal起動有無、`ea_attention.required`、`ea_attention.reason` が出ます。`mt5_terminal_running_but_ea_post_stale` の場合はMT5自体は開いているため、チャートに `AI_Bridge_Advisor` が付いているか、自動売買許可、URL許可、Bridge URL/Token設定を確認します。

Bridge/EA復旧計画:

```bash
python3 methods/swing_eval/analysis/bridge_recovery_plan.py \
  --bridge-status runtime/latest_bridge_status.json \
  --history-status runtime/latest_history_status.json \
  --output-json runtime/latest_bridge_recovery_plan.json \
  --output-md runtime/latest_bridge_recovery_plan.md
```

`status=needs_ea_restart` の場合はMT5 terminalは動いていてもEA由来の `POST /snapshot` が止まっています。MT5で `AI_Bridge_Advisor` をチャートへ付け直し、Algo Trading、WebRequest許可、Bridge URL/Tokenを確認します。JSONの `operation_cards` とMarkdownの `Bridge Recovery Operation Cards` には、次に実行するBridge復旧操作、対象、検証条件、履歴request/done ID、復旧後の確認コマンドがまとまります。`history_request_stale_pending=true` の時は同じ履歴要求を繰り返さず、EA POST復旧後に `history_request.done.json` のID一致を待ちます。履歴取得やBridge依存の検証は `ready_for_mt5_validation=true` を待ちますが、Bridge/GPT非依存の `Swing_Evaluation_Trader` Strategy Tester Back/ForwardはBridge未readyでも手動実行できます。この切り分けは `bridge_required_for_standalone_tester=false`、`standalone_strategy_tester_allowed=true`、`standalone_strategy_tester_note` としてJSON直下と `operator_summary` にも出ます。

定期監視する場合:

```bash
python3 methods/swing_eval/analysis/bridge_status_watch.py \
  --interval-seconds 60 \
  --heartbeat runtime/bridge_status_watch_heartbeat.json \
  --pid-file runtime/bridge_status_watch.pid
```

常駐watcherを動かしたまま1回だけファイル更新する場合は `--max-runs 1` だけで共有heartbeat/PIDを上書きしません。診断用に別heartbeatへ書く場合は `--heartbeat` を明示し、既存PIDを保護する場合は `--skip-pid-file-write` も付けます。watcherは `bridge_status.py` に続けて `bridge_recovery_plan.py` も実行し、`runtime/latest_bridge_recovery_plan.json` / `.md` も同じ周期で更新します。heartbeatには `implementation_version`、`snapshot_required_keys`、`operational_status`、`health_ok`、`config_history_request_id`、`snapshot_fresh`、`history_request_stale_pending`、`ea_liveness_signal`、`config_get_recent_but_ea_post_stale`、`bridge_log_ea_liveness_signal`、`mt5_terminal_running`、`ea_attention_reason`、`recovery_plan_status`、`recovery_plan_ready_for_mt5_validation`、`recovery_plan_bridge_required_for_standalone_tester`、`recovery_plan_standalone_strategy_tester_allowed`、`recovery_plan_standalone_strategy_tester_note`、`recovery_plan_blocking_reasons`、`recovery_plan_next_action`、`recovery_plan_operation_cards`、`recovery_plan_next_operation_*`、次操作の `verification_commands`、`watcher_pid`、`pid_file_enabled`、`pid_file_written`、`heartbeat_enabled`、`run_index` が残ります。
`runtime_watchers.py` から起動する既定のBridge watcherは `--refresh-history-status` 付きです。各tickで `bridge_status.py` の後に `history_status.py` を実行し、更新済みの `runtime/latest_history_status.json` を `bridge_recovery_plan.py` へ渡します。EA復旧後に `latest_history_168h.json` と `history_request.done.json` が更新された場合、次のwatcher更新で履歴本数、request/done ID、M1最終時刻がRecovery PlanとCoverageへ反映されます。heartbeatでは `history_status_refresh_status`、`history_status_refresh_returncode`、`history_status_server_time`、`history_status_m1_bars`、`history_status_m1_last_time` を確認します。

履歴本数ステータス:

```bash
python3 methods/swing_eval/analysis/history_status.py \
  --history runtime/latest_history_168h.json \
  --done runtime/history_request.done.json \
  --output-json runtime/latest_history_status.json \
  --output-md runtime/latest_history_status.md
```

`latest_history_168h.json` のtop-level `bars` はコンパクトなプレビューです。分析では `timeframes.M1.bars` を使います。168hの目安はM1 10080本、M5 2016本、M15 672本、M30 336本です。Promotion Gateも `history_timeframes_complete` でM1/M5/M15/M30が168h期待本数の98%以上あるかを確認し、top-level previewだけの履歴を採用根拠にしないようにします。

山/谷一覧:

```bash
python3 methods/swing_eval/analysis/swing_points.py \
  --history runtime/latest_history_168h.json \
  --timeframes M1,M5 \
  --output reports/swing_points_168h.xlsx
```

バックテスト:

```bash
python3 methods/swing_eval/analysis/backtest.py \
  --history runtime/latest_history_168h.json \
  --deals runtime/latest_deal_history.json \
  --rr 5 \
  --min-score 50 \
  --output reports/signal_score_backtest_168h_min50.xlsx \
  --deal-context-output reports/signal_score_backtest_168h_min50_deal_context.xlsx
```

Markdownサマリー:

```bash
python3 methods/swing_eval/analysis/backtest.py \
  --history runtime/latest_history_168h.json \
  --rr 5 \
  --min-score 50 \
  --output reports/signal_score_summary_168h_min50.md
```

決済周辺M1足:

```bash
python3 methods/swing_eval/analysis/deal_context.py \
  --history runtime/latest_history_168h.json \
  --deal-history runtime/latest_deal_history.json \
  --symbol XAUUSD-m \
  --entry out \
  --before-minutes 10 \
  --after-minutes 10 \
  --output reports/deal_m1_context.xlsx
```

RR比較:

```bash
python3 methods/swing_eval/analysis/rr_experiment.py \
  --history runtime/latest_history_168h.json \
  --rr-values 2,3,4,5 \
  --min-score 50 \
  --output reports/rr_strategy_experiment_168h_all_min50.xlsx
```

評価関数重み探索:

```bash
python3 methods/swing_eval/analysis/weight_search.py \
  --history runtime/latest_history_168h.json \
  --rr 4 \
  --side both \
  --min-count 20 \
  --max-hold-minutes 60 \
  --calendar runtime/economic_calendar.json \
  --calendar-input-utc-offset 9 \
  --calendar-server-utc-offset 3 \
  --output reports/score_weight_search_168h_both_rr4.xlsx \
  --output-json runtime/latest_score_weight_search.json \
  --output-md runtime/latest_score_weight_search.md \
  --walk-forward \
  --wf-folds 4 \
  --wf-train-window 240 \
  --wf-test-window 60 \
  --wf-embargo-records 5
```

`latest_score_weight_search.json` には上位重み候補、baseline閾値別成績、探索条件、walk-forward aggregateを保存します。`latest_score_weight_search.md` には同じ証跡の要約、top候補、baseline表、walk-forward不足、regime候補/不足を保存します。Excel確認だけで終わらせず、Promotion Gateや後続スクリプトから同じ探索証跡を参照できるようにします。Promotion GateはこのJSONを読み、score calibration / score quality未達時に `weight_search_top`、`weight_search_delta`、`Score Weight Search` セクションへ上位候補、baseline比較、walk-forward結果を表示します。walk-forwardのsample shortageでは `missing_test_weight_count`、`folds_with_weight_trades`、`missing_folds_with_weight_trades`、最薄foldも表示されるため、何件・何fold足りないかを見てMT5 sample collectionへ戻れます。ここで良く見える候補は「次に検証する候補」であり、walk-forward、MT5 Optimization、年次検証を通るまでは採用しません。

勝率fit:

```bash
python3 methods/swing_eval/analysis/winrate_fit.py \
  --history runtime/latest_history_168h.json \
  --rr 4 \
  --side buy \
  --min-score 50 \
  --validation-folds 3 \
  --wf-folds 4 \
  --purge-records 1 \
  --embargo-records 1 \
  --embargo-minutes 60 \
  --min-test-count 5 \
  --min-test-avg-r 0 \
  --min-test-pf 1.0 \
  --output reports/winrate_fit_168h_buy_rr4.xlsx \
  --output-json runtime/latest_winrate_fit.json
```

fit結果は `adoption_decision` 行と `ウォークフォワード` のaggregateを見る。trainで改善しても、final testの件数、平均R、PFが不足する場合、またはwalk-forwardのfitted test件数やPFが薄い場合は不採用にする。

最新シグナル生成:

```bash
python3 methods/swing_eval/analysis/signal.py \
  --history runtime/latest_history_168h.json \
  --snapshot runtime/latest_snapshot.json \
  --strategy side_ladder \
  --min-score 50 \
  --output runtime/latest_signal.json
```

dry-run command生成:

```bash
python3 methods/swing_eval/analysis/dry_run_command.py \
  --signal runtime/latest_signal.json \
  --output runtime/trade_command.json \
  --volume 0.1 \
  --account runtime/latest_account.json \
  --deal-history runtime/latest_deal_history.json \
  --max-open-positions 3 \
  --max-total-volume 0.3 \
  --daily-loss-limit 5000 \
  --consecutive-loss-limit 20 \
  --consecutive-loss-cooldown-minutes 120
```

`generated_at + valid_for_seconds` を過ぎたsignalは拒否します。既存の `runtime/trade_command.json` が `pending` の場合は、明示的に `--replace` を付けない限り上書きしません。
最新signalがHOLDの場合、`dry_run_command.py --write-rejections` はEAへ送らない `rejected` commandを作ります。この時の `dry_run_audit.py` はEA resultを要求せず、commandの鮮度、signal/command整合、埋め込み `risk_gate.allowed` を監査します。古い `latest_trade_result.json` はHOLD監査のfreshnessには使いません。
HOLD、blackout、risk gateなどでrejectedになった場合も、`source_signal` にはscore、RR、`generated_at`、`valid_for_seconds`、candidate time、latest bar time、history server timeを残し、`lot_policy` には0.1 lot基準と0.3 lot合計上限を残します。後で「どの足の判断を、どの有効期限とロットルールで拒否したか」を監査できます。

Forward Test稼働状況:

```bash
python3 methods/swing_eval/analysis/forward_test.py status \
  --signal runtime/latest_signal.json \
  --ledger runtime/forward_tests.jsonl \
  --output-json runtime/latest_forward_test_status.json \
  --output-md runtime/latest_forward_test_status.md
```

状態だけを定期更新する場合:

```bash
python3 methods/swing_eval/analysis/forward_status_watch.py \
  --signal runtime/latest_signal.json \
  --ledger runtime/forward_tests.jsonl \
  --output-json runtime/latest_forward_test_status.json \
  --output-md runtime/latest_forward_test_status.md \
  --interval-seconds 60
```

現在は `tmux` セッション `forward_status_watch` でこの状態監視を動かしています。状態は `runtime/forward_status_watch_heartbeat.json` と `runtime/latest_forward_test_status.md` で確認できます。heartbeatには `schema_version`、`started_epoch`、`finished_epoch`、`elapsed_seconds`、`watcher_pid`、`pid_file`、`pid_file_written`、`run_index`、`max_runs`、`continuous`、`operational_status`、signal action、closed/open件数も残すため、監視の鮮度とHOLD待ち状態をファイルだけで確認できます。常駐watcherのpidファイルを維持したまま1回だけ更新する場合は `--max-runs 1 --skip-pid-file-write` を付けます。

record/evaluate/statusをまとめて定期実行する場合:

```bash
python3 methods/swing_eval/analysis/forward_test_watch.py \
  --signal runtime/latest_signal.json \
  --ledger runtime/forward_tests.jsonl \
  --history runtime/latest_history_168h.json \
  --summary-json runtime/latest_forward_test.json \
  --summary-md runtime/latest_forward_test.md \
  --status-json runtime/latest_forward_test_status.json \
  --status-md runtime/latest_forward_test_status.md \
  --heartbeat runtime/forward_test_watch_heartbeat.json \
  --interval-seconds 60
```

`forward_test_watch.py` はBUY/SELLだけを台帳へ記録します。同じsignal IDは二重記録せず、HOLDは台帳へ書かずにstatus/heartbeatだけ更新します。heartbeatには `schema_version`、`started_epoch`、`finished_epoch`、`elapsed_seconds`、`watcher_pid`、`pid_file`、`pid_file_written`、`run_index`、`max_runs`、`continuous` も残し、1回実行の更新と常駐監視、ファイル鮮度を区別します。常駐watcherのpidファイルを維持したまま1回だけ記録/評価/status更新する場合は `--max-runs 1 --skip-pid-file-write` を付けます。
`runtime/latest_forward_test.json` / `.md` にはclosed/open/ignored、勝率、平均R、PF、総R、最大連敗、最大DD、期待Rを出します。
Promotion Gateは `runtime/latest_forward_test_status.json` も読みます。最新signalがHOLDで `waiting_for_tradable_signal` の時は、Python forwardのnext actionをBUY/SELL待ちとして扱います。
この場合、`Next Action Execution Plans` の `python_forward` には `forward_wait` を表示し、`operational_status`、signal action、recordability、closed/open件数、HOLD理由を確認できます。`forward_test_watch_heartbeat.json` があれば `forward_watch` も表示し、watcherが常駐中か、pidファイルを書いた常駐更新か、heartbeatが新しいか、PID、run index、直近のrecord/evaluate結果を同じ場所で確認できます。`forward_status_watch_heartbeat.json` があれば `forward_status_watch` も表示し、status-only監視の鮮度、pidファイル書き込み有無、PID、run index、signal action、closed/open、PFを確認できます。
BUY/SELLのdry-run commandは、`latest_dry_run_audit` のcommand要約にSL/TP、source signal score、`max_spread_points` が残っているかをPromotion Gateで再確認します。欠けている場合は `dry_run_command_safety` を表示し、risk gate付きのdry-run commandを作り直すnext actionへ戻します。HOLDなど非tradable signalが正しくrejectedされた場合は、EA発注用のSL/TPやspread上限は要求しませんが、`lot_policy` などの監査証跡が欠けていればHOLD待ちの実行計画にも `dry_run_command_safety` として表示します。
Promotion GateのMarkdownにもMT5 Forwardのsignal/reject診断を出します。`latest_mt5_forward_report.md` を開かなくても、HOLD過多、BUY/SELL候補不足、reject上位理由を確認できます。
`diagnostic_warnings` と検出された連敗停止limitも表示し、3連敗など古い停止設定が混ざったForward結果を見落とさないようにします。Promotion Gateでは `diagnostic_warnings` が空であることもcheckし、警告が残るForwardは `mt5_forward_diagnostics` のnext actionでcompile確認と修正/再実行に戻します。検出limitが20未満の場合は `Swing_Evaluation_Trader_forward_test.set` のrisk preset確認planも出し、Markdownに検出limit、現在値、エラー、`InpConsecutiveLossLimit >= 20`、`InpConsecutiveLossCooldownMinutes >= 120`、`InpRequireStrategyTester = true`、`InpChartButtonDryRunOnly = true`、`InpAllowChartButtonTrading = false` を明示します。
Forward CSVのchart button行はdry-runまたはignoredだけを許可します。unsafe button rowがある場合は `mt5_forward_button` のnext actionで `InpRequireStrategyTester=true`、`InpChartButtonDryRunOnly=true`、`InpAllowChartButtonTrading=false` の確認、compile、Forward再実行計画を表示します。
`--require-mt5-forward` では `mt5_forward_sl_tp_diagnostics` も確認します。Forwardレポートに `By Risk Reward And TP Points` がない場合は、RR×TP帯で崩れる設定を見落とすため、`mt5_forward_collect.py` で最新CSVから再集計するnext actionへ戻します。短期Optimization推薦が `adoptable=false` / `skipped_write=true` の間は、Forward性能不足のnext actionも候補set検証として扱わず、先に `mt5_optimization_recommendation_refresh` へ戻します。entry-time/trend schemaや古い連敗停止limitなどのForward診断更新だけは、現行EA確認として `forward_test.set` の再実行計画を残します。
MT5 Optimization、年次Optimization、MT5 ForwardではBUY/SELL別PFと平均price-Rに加え、`avg_price_r * price_r_count` で近似したプラス総price-Rの片側集中も確認します。片側shareが85%を超える場合は `mt5_optimization_side_total_price_r_balance` / `mt5_yearly_optimization_side_total_price_r_balance` / `mt5_forward_side_total_price_r_balance` をFAILにし、BUY/SELLの片側だけで成績が成立している候補を昇格させません。
Forwardのrisk exposureがlot上限、合計lot、同時建玉、日次/連敗停止後openで失敗した場合も、`mt5_forward_risk` のnext actionでcompile確認とForward再実行に戻します。
MT5 ForwardレポートはCSV schemaも診断し、`opened_at`、`entry_server_hour`、M30/M15/M5 trend列、M30/M15 slope列が欠けている古いCSVでは、entry-hour/trend診断を使う前に再実行を促す警告を出します。`entry`、`sl`、`deal_price`、`spread_points`、`latency_seconds`、`hold_seconds` などのexecution列も確認し、価格R、滑り、スプレッド、約定遅延の診断に使えるかを分けて表示します。
Promotion Gateでもこのschema診断をcheck化し、entry-time/trend/execution診断が使えないForward CSVは `mt5_forward_schema` のnext actionで現行EAのcompile確認とForward再実行に戻します。
MT5 Forwardのnext actionでは、Strategy Tester forward実行計画の直下に `mt5_forward_gap`、`mt5_forward_side_gap`、`mt5_forward_signal_flow`、`mt5_forward_reject_flow`、`mt5_forward_reject_top`、`mt5_forward_risk_exposure`、`mt5_forward_warning`、`mt5_forward_detected_loss_limits`、`mt5_forward_schema_gap`、`mt5_forward_sl_tp_gap` を表示します。PF、最大連敗、side別PF/平均R、signal/reject件数、上位reject理由、risk exposure、古い連敗停止limit、entry-time/trend診断フィールド不足、SL/TP診断キー不足を、再実行または再集計コマンドの近くで確認できます。
Forward SL/TP診断キーが揃っている場合は `mt5_forward_sl_tp` にSL、TP、RR×SL、RR×TP、Weak SL/TP件数を表示し、弱いセグメント上位は `mt5_forward_weak_sl_tp` に出します。Promotion Gate本文にも `MT5 Forward SL/TP Diagnostics` として同じ要約を出します。

Forward Test CSV集計:

MT5 Strategy Tester実行後、最新CSVを探してコピーし、そのまま集計する場合:

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

集計ではsignal診断も出力します。トレードが0件の場合は、まず `Signal buy/sell/hold` と `Top signal reasons` を見て、全HOLDなのか、BUY/SELL候補は出たがrejectされたのかを確認します。
トレードが途中で止まった場合は `Reject top messages` を見ます。`consecutive loss cooldown active 20 >= 20` なら、20連敗で `InpUseConsecutiveLossStop` が発動し、120分の新規停止に入っています。評価関数の候補数を集めたいだけなら `sample_collection.set` で再テストし、Forward判定には安全停止ありの `forward_test.set` を使います。

CSVを手で `runtime/mt5_forward/swing_evaluation_trades.csv` に置いた場合:

```bash
python3 methods/swing_eval/analysis/mt5_forward_report.py \
  --input runtime/mt5_forward/swing_evaluation_trades.csv \
  --min-closed 30 \
  --min-pf 1.2 \
  --max-losing-streak 20 \
  --max-single-volume 0.10 \
  --max-total-volume 0.30 \
  --max-positions 3 \
  --daily-loss-limit 5000 \
  --output-json runtime/latest_mt5_forward_report.json \
  --output-md runtime/latest_mt5_forward_report.md
```

このCLIの標準出力は監視用の小さいJSON要約だけです。詳細な `summary`、SL/TP診断、score診断は `runtime/latest_mt5_forward_report.json` / `.md` を確認します。デバッグで全summaryを標準出力に出す場合だけ `--print-full-summary` を付けます。

集計では全体だけでなく、買い/売り、RR、SL幅帯、TP幅帯、RR×SL幅帯、RR×TP幅帯、score帯ごとにPF、平均価格R、価格Rベース最大DD、期待価格R、平均保有時間、平均滑り、平均スプレッド、TP/SL/早期決済数、Entryボタンのdry-run/ignored件数を確認できます。`Risk Exposure` では実際に観測された最大単発lot、同時保有lot、同時建玉数、日次損失停止後open、連敗停止後openを確認します。
`By SL Points`、`By TP Points`、`By Risk Reward And SL Points`、`By Risk Reward And TP Points`、`Weak SL/TP Segments` では、どのSL/TP設定ラインで崩れているかを確認します。近いSLでPFが崩れるならSL幅/バッファ/エントリー精度、遠いTPでTP到達率が低いならRRまたは利確ラインが課題です。

Tester最適化結果の集計:

MT5のOptimizationではローカルAgentごとに `swing_evaluation_trades.csv` が分かれます。1ファイルだけを選ぶのではなく、以下で直近のAgent CSVとTester XMLをまとめて集計します。

```bash
python3 methods/swing_eval/analysis/mt5_tester_optimization_report.py \
  --since-minutes 30 \
  --min-closed 100 \
  --weak-pf 1.0 \
  --set-file methods/swing_eval/mt5/TesterSets/Swing_Evaluation_Trader_next_optimization.set \
  --output-json runtime/latest_mt5_optimization_report.json \
  --output-md runtime/latest_mt5_optimization_report.md
```

Tester実行後に別setを回した可能性がある場合は、latest tester runの `terminal_run.finished_at` を `--modified-before "YYYY.MM.DD HH:MM"` として付け、後から上書きされたAgent CSVを除外します。Promotion Gateが出す短期Optimization再集計planでは、この値をlatest tester runから自動付与します。

年次検証やout-of-year検証では、残っている短期Agent CSVを誤って拾わないように期待期間も指定します。

```bash
python3 methods/swing_eval/analysis/mt5_tester_optimization_report.py \
  --since-minutes 0 \
  --expected-from-date 2025.01.01 \
  --expected-to-date 2025.12.31 \
  --drop-source-time-mismatch-files \
  --fail-on-source-time-mismatch \
  --set-file methods/swing_eval/mt5/TesterSets/Swing_Evaluation_Trader_next_optimization.set
```

`mt5_tester_run.py --from-date ... --to-date ...` 経由では、この期待期間は子のOptimizationレポートへ自動で渡されます。JSONの `source_time_diagnostics.matches_expected_range`、またはMarkdownの `Source time in expected range` が `false` の場合、その年次レポートは別期間CSVを集計している可能性が高いため採用しません。
`--fail-on-source-time-mismatch` を付けると、期間不一致時は出力JSON/Markdownを上書きせず終了します。`mt5_tester_run.py` も期間不一致の集計からは推薦 `.set` を生成せず、`ok=false` として扱います。
既存Agent CSVから年次レポートを復旧する時に短期CSVが混ざっている場合は、`--drop-source-time-mismatch-files` を付けると期待期間外のCSVをファイル単位で除外し、`source_time_file_filter` に除外ファイル、first/last、理由を残します。
Promotion Gateのsource-time mismatch next actionでは、実行計画の直下に `source_time_gap` と `source_time_warnings` を表示し、期待From/Toと実際のAgent CSV close `server_time` first/last、server_time付き/なし行数、期間不一致の理由を確認できます。

MT5 Strategy TesterのBack/Forwardと複数Optimization結果を横断して採用可否を見る場合:

```bash
python3 methods/swing_eval/analysis/mt5_strategy_tester_analysis.py \
  --output-json runtime/latest_mt5_strategy_tester_analysis.json \
  --output-md runtime/latest_mt5_strategy_tester_analysis.md
```

このレポートは `latest_promotion_gate.json`、`latest_spec_coverage.json`、`latest_mt5_back_forward_run.json`、`latest_mt5_tester_status.json`、BUY/SELLの主要Optimizationレポートを読み、候補、参考、閾値未満、不採用、未実行を1枚の表にまとめます。MT5上のBacktest/Forwardがまだ未実行なら `plan_only` として表示し、次のMT5 Strategy Tester stepとcollect-onlyコマンドも転記します。SELLだけが候補でBUYに安定passがない場合など、片側だけのfitも採用ブロッカーとして明示します。

MT5を `mt5_tester_run.py` から起動する場合は、`--archive-agent-csvs-before-run` を付けます。EAはAgentごとのCSVへ追記するため、既存ファイルを `runtime/mt5_agent_csv_archive/` に退避してから起動しないと、前回実行の期間が新しい集計に混ざります。
手動previewと同じ退避先を使いたい場合は、`mt5_tester_run.py` 側に `--agent-csv-archive-run-id <id>` を付けます。
通常起動で `--archive-agent-csvs-before-run` が未指定の場合、run JSON/Markdownの `agent_csv_archive_missing=true` とwarningで警告します。
退避を実行したrun JSON/Markdownにも、退避したCSVのclose `server_time` first/lastと欠落件数を残します。

現在の退避対象だけ確認する場合:

```bash
python3 methods/swing_eval/analysis/mt5_agent_csv_archive.py --run-id before_next_optimization
```

実際に移動する時だけ `--execute` を付けます。プレビューの `--run-id` と、`mt5_tester_run.py` の `--agent-csv-archive-run-id` を同じ値にすると、退避先ディレクトリを固定できます。
期間混入を調べる時は `--include-source-time` を付けると、各Agent CSVのclose `server_time` のfirst/lastと欠落件数を確認できます。Gateのsource-time mismatch復旧planもこのフラグ付きpreviewを出します。

見る場所:

- `By Risk Reward`: RR 1:2、1:3、1:4、1:5の全体比較
- `By Action And Risk Reward`: BUY/SELL別のRR比較
- `Best Segments`: PFが残っているSL/TP帯。RR×SL幅帯とRR×TP幅帯も候補に含みます。
- `Weak SL/TP Segments`: 崩れているSL/TP帯と短い診断。RR×SL幅帯とRR×TP幅帯も確認します。
- `Temporal Diagnostics`: 四半期、月、曜日、サーバー時間帯、RR×月で崩れる時間レジーム
- `Trend Regime Diagnostics`: M30/M15/M5、M30/M15 slope、トレンド整合、売買方向×トレンド整合で崩れる相場レジーム
- `Tester Optimization XML`: MT5 Tester本体のback/forward上位パス
- `Back/Forward Parameter Diagnostics`: Tester XMLの全passを `Inp...` 入力値ごとに集計。backで良くforwardで崩れる値は `Back-Fit Parameter Artifacts` に出し、次setのstable hint固定採用から除外します。
- `Full-factorial pass candidates`: `.set` 上の全探索候補数。`Executed Tester XML rows` がMT5 genetic optimizationで実際に出たpass数の目安です。JSONでは同じ証跡を `optimization_pass_budget.executed_tester_xml_rows` に残します。
- `Source time first/last`: 集計したAgent CSVの実際のclose時刻範囲。年次検証では期待期間内に入っていることを確認します。

次の探索範囲を機械的に整理する場合:

```bash
python3 methods/swing_eval/analysis/mt5_optimization_recommend.py \
  --input runtime/latest_mt5_optimization_report.json \
  --min-segment-closed 500 \
  --min-segment-pf 1.2 \
  --output-json runtime/latest_mt5_optimization_recommendation.json \
  --output-md runtime/latest_mt5_optimization_recommendation.md \
  --output-set methods/swing_eval/mt5/TesterSets/Swing_Evaluation_Trader_next_optimization.set
```

`Next Search` では、BUY/SELL別に再fitが必要か、主候補にするRR/SL/TP帯、除外候補にする崩れた帯を確認します。少数サンプルでPFだけ高い帯は `Reference segments` に分け、主候補とは別扱いにします。`--output-set` を付けると、主候補sideに合わせて `InpEnableBuy` / `InpEnableSell`、RR、SL幅を絞った次回Optimization用 `.set` を生成します。
`Next Set` には `Stable hint coverage` も表示し、stable pass由来の各 `Inp...` hintが実際の `.set` に反映されたか、back-fit artifactとして除外されたか、未対応でスキップされたかを確認できます。Promotion Gateの `Next Action Execution Plans` にも `recommendation_set_passes` と `recommendation_stable_hints` を出し、既存 `.set` のpass数と、推薦されたが未書き込みの `.set` のpass数を混同しないようにします。
推薦が不採用でも、stable back/forward pass周辺を次の探索として検証したい場合は、通常の `next_optimization.set` ではなく別名の `Swing_Evaluation_Trader_stable_candidate_next.set` へ明示保存します。この時だけ `--allow-non-adoptable-output-set` を付けます。このsetは探索用であり、Promotion Gateでは採用済み候補として扱いません。

`score_inversion` が出ているsideを明示的に選ぶと、生成候補はscore refit用の診断setになります。この場合、通常の `next_optimization.set` を壊さないため、既定では `--output-set` への書き込みをスキップし、標準出力と推薦JSON/Markdownの `set_metadata.skipped_write=true` に残します。診断setを保存したい時だけ、別パスを指定して `--allow-diagnostic-output-set` を付けます。`mt5_tester_run.py` でOptimization実行から推薦生成までまとめる場合も同じフラグを使い、子の推薦レポートにも同じ `set_metadata` を残します。

採用候補は、CSV集計でPFが良いだけでなく、Tester XMLでbackとforwardが同時に崩れていないものを優先します。forwardだけ良く、backが大きくマイナスのものは過剰適合候補として扱います。
`Score Thresholds` と `Side Score Diagnostics` では、scoreを上げた時にbuy/sell別で改善するかを確認できます。`candidate_gate` は採用候補、`score_inversion` は高scoreほど悪化しているため評価関数の再fit対象です。
`Chronological Split Diagnostics` に失敗splitがある場合、Recommendation Markdownには `Chronological Failure Context` を出します。ここでは失敗期間に重なる `Weak Time Segments`、弱いtrend regime、弱いSL/TP帯をまとめ、次に時間帯/トレンド/SLTPのどれを切り出して再fitするかを確認します。Promotion GateのNext Actionでも `chronological_weak_time` / `yearly_weak_time` などの短い要約を出します。
stable candidateをMT5 Strategy Testerで検証済みの場合は、Promotion Gateの `mt5_optimization_recommendation` 実行計画に `stable_candidate_result` に加えて `stable_candidate_chronological_failure`、`stable_candidate_weak_trend`、`stable_candidate_weak_sl_tp`、`stable_candidate_weak_time` を表示します。探索用setが採用不可のままなのか、どのsplit/相場 regime / SLTP帯で崩れているのかをGate側だけで確認できます。弱いtrend/timeが出た場合は `stable_candidate_refit` として `sell_regime_entry_refit` / `buy_entry_refit` などの次のTester計画も出し、同じstable candidate探索setを再実行する前に崩れた条件の再fitへ進みます。`latest_mt5_sell_regime_entry_refit_recommendation.json` などのSELL refit結果がすでに完了済みで、`score_refit_required` や `diagnostic_only` のままなら、Gateは同じ `sell_regime_entry_refit` を繰り返さず `sell_score_refit` としてSELL側のscore weight探索/評価関数再fitへ進めます。
短期窓で良くても、年次検証で `Weak Time Segments` や `Weak Trend Segments` が支配的なら採用しません。M30/M15が上昇なのにSELLが崩れる、または下落なのにBUYが崩れる場合は、BUY/SELLの評価関数を分けて再fitします。
SELL側では `InpUseFittedSellTrendFilter` をOptimization対象にできます。これは `M30 down M15 up` や、M30/M15が上向きだがM5が揃わない部分的な上向きレジームでSELLを減点する候補フィルタです。既定はOFFで、ON採用はback/forwardと年次検証を通った場合だけにします。
時間帯の崩れは `InpUseFittedSellTimeFilter` で検証します。`InpSellBlockedServerHours` はサーバー時刻ベースのカンマ区切りリストで、初期値は `1,9,10,13,14,16,20` です。この時間帯ではSELLを禁止ではなく減点し、ON/OFFでPF、平均R、back/forward安定性が改善するかを見ます。特定時間帯だけを切り出す時は `InpUseSellAllowedServerHours` と `InpSellAllowedServerHours` を使います。例えば `Swing_Evaluation_Trader_sell_hour12_validation.set` は12:00-13:00のSELLだけを検証する診断用setです。hour12の中でもM30/M15 downだけを厳格に残す次段階診断は `Swing_Evaluation_Trader_sell_hour12_m30m15_validation.set` を使います。2025年検証ではこのSELL単体診断がPF 1.3786、平均R 0.2914まで改善しましたが、BUY側未検証と弱い月/曜日が残るためライブ用ではありません。`Swing_Evaluation_Trader_sell_hour12_m30m15_calendar_validation.set` で弱かった3月/6月/12月と水曜を `InpUseFittedSellCalendarFilter` で減点する検証も行いましたが、年間aggregateはPF 1.3667へ低下したため診断止まりです。曜日はMT5の `day_of_week` で、水曜は `3` です。
Promotion Gateの `sell_sl_tp` next actionでは、focused `next_optimization` の次段として `sell_entry_refit` もfollow-upに出します。SL/TP帯を絞ってもSLヒットや早期損失が支配的なら、SELLのentry確認自体を再fitします。`Next Action Execution Plans` のfocused `next_optimization` 直下には `sl_tp_best` / `sl_tp_weak` を表示し、次に寄せるRR/SL/TP帯と除外候補の崩れた帯をPF、平均R、損益、診断文付きで確認します。focus sideの帯がない場合は、BUY帯などをSELL候補として誤表示せず、`sl_tp_segment_gap` にside別件数と再実行/再生成が必要なことを表示します。

MT5 TesterのOptimization起動、集計、推薦 `.set` 更新までまとめて行う場合:

```bash
python3 methods/swing_eval/analysis/mt5_tester_run.py \
  --config methods/swing_eval/mt5/TesterConfigs/Swing_Evaluation_Trader_next_optimization.ini \
  --timeout-seconds 7200 \
  --since-minutes 240 \
  --archive-agent-csvs-before-run \
  --min-closed 100 \
  --min-segment-closed 500 \
  --min-segment-pf 1.2 \
  --output-json runtime/latest_mt5_tester_run.json \
  --output-md runtime/latest_mt5_tester_run.md
```

このランナーは実行前に `latest_mt5_compile_status` 相当の確認を行い、`.ex5` が古い場合は最適化起動をブロックします。既存の `terminal64.exe` が起動中の場合も既定で止めます。これは `/config` 起動が既存MT5へ吸われ、return code 0でもStrategy Testerが走らないことを避けるためです。参照する `.set` のrisk presetも確認し、通常のForward/Optimizationでは `InpUseConsecutiveLossStop=true`、`InpConsecutiveLossLimit>=20`、`InpConsecutiveLossCooldownMinutes>=120`、`InpRequireStrategyTester=true`、`InpChartButtonDryRunOnly=true`、`InpAllowChartButtonTrading=false` を満たさない場合に起動前ブロックします。さらに対象configの `ExpertParameters` `.set` がMT5側 `MQL5/Profiles/Tester` に同期されていない場合も `tester_set_not_synced` として起動前に止めます。復旧は `--sync-expert-parameters-set` 付きで再実行するか、対象 `.set` をMT5側へコピーします。この起動前ブロックでは既存のTester XML/CSVを収集せず、`report_paths.source=blocked_not_collected` として古い結果の誤読を防ぎます。停止理由は `blocked_components.compile_stale` / `risk_preset_invalid` / `tester_set_not_synced` / `terminal_already_running` / `agent_csv_archive_failed` と個別booleanにも残すため、warning文字列を読まなくてもGate側で原因を判定できます。`latest_mt5_tester_run.md` の `Running Terminal Detection` には検出ON/OFF、ブロック有無、起動中terminalのPID/commandも残します。`sample_collection.set` だけはサンプル収集用として日次損失停止/連敗停止OFFを許容しますが、Tester限定とチャートボタン実発注禁止は確認します。診断目的で既存のTester出力だけ集計する場合は `--collect-only`、古い `.ex5` でも強制的に試す場合は `--allow-stale-compile`、risk preset不一致でも強制実行する場合は `--allow-invalid-risk-preset`、起動中terminalを承知で試す場合は `--allow-running-terminal` を明示します。
`runtime/latest_mt5_tester_run.json` / `.md` にはterminal開始時刻、timeout秒数、deadline、elapsed秒数も残します。長いOptimizationを走らせた後は、ここで「最大いつまで待ったか」を確認できます。terminalがtimeoutまたは非0終了した場合は `terminal_failed=true` とし、古いTester XML/CSVへのfallback収集や推薦生成は行いません。停止マーカーとして出る子Optimization/Recommendation Markdownにも同じterminal時刻証跡を残します。

MT5 Testerの現在状態だけを確認する場合:

```bash
python3 methods/swing_eval/analysis/mt5_tester_status.py \
  --tester-run runtime/latest_mt5_tester_run.json \
  --promotion-gate runtime/latest_promotion_gate.json \
  --compile-status runtime/latest_mt5_compile_status.json \
  --optimization-report runtime/latest_mt5_optimization_report.json \
  --back-forward-run runtime/latest_mt5_back_forward_run.json \
  --manual-test-queue runtime/latest_mt5_manual_test_queue.json \
  --manual-queue-launch runtime/latest_mt5_manual_queue_launch.json \
  --manual-collect-run runtime/latest_mt5_manual_collect_run.json \
  --output-json runtime/latest_mt5_tester_status.json \
  --output-md runtime/latest_mt5_tester_status.md
```

状態を定期更新する場合:

```bash
python3 methods/swing_eval/analysis/mt5_tester_status_watch.py \
  --tester-run runtime/latest_mt5_tester_run.json \
  --promotion-gate runtime/latest_promotion_gate.json \
  --compile-status runtime/latest_mt5_compile_status.json \
  --optimization-report runtime/latest_mt5_optimization_report.json \
  --next-action-run runtime/latest_mt5_next_action_run.json \
  --back-forward-run runtime/latest_mt5_back_forward_run.json \
  --manual-test-queue runtime/latest_mt5_manual_test_queue.json \
  --manual-queue-launch runtime/latest_mt5_manual_queue_launch.json \
  --manual-collect-run runtime/latest_mt5_manual_collect_run.json \
  --output-json runtime/latest_mt5_tester_status.json \
  --output-md runtime/latest_mt5_tester_status.md \
  --interval-seconds 60
```

常駐watcherを動かしたまま、ハートビートだけ今すぐ1回更新したい場合:

```bash
python3 methods/swing_eval/analysis/mt5_tester_status_watch.py \
  --max-runs 1 \
  --skip-pid-file-write \
  --heartbeat runtime/mt5_tester_status_watch_heartbeat_current.json \
  --pid-file runtime/mt5_tester_status_watch_current.pid \
  --manual-test-queue runtime/latest_mt5_manual_test_queue.json \
  --manual-queue-launch runtime/latest_mt5_manual_queue_launch.json \
  --manual-collect-run runtime/latest_mt5_manual_collect_run.json
```

`--skip-pid-file-write` を付けると常駐watcherのpidファイルを上書きしません。heartbeatには `pid_file_written=false` が残るため、1回実行の更新と常駐監視プロセスを区別できます。watcherは既定でstatus更新前に `methods/swing_eval/analysis/mt5_manual_collect.py` をdry-run実行し、`manual_collect_refresh_returncode/status/selected_count/waiting_count/invalid_count` をheartbeatへ残します。`returncode=2` はreadyなcollect対象がまだない通常状態です。このdry-runを止めたい場合だけ `--skip-manual-collect-refresh` を付けます。status更新時は、先に現行スキーマのpre heartbeatを書いてから `mt5_tester_status.py` を実行し、final heartbeatを書いた後にstatusをもう一度同期生成します。正常な最終heartbeatは `status_refresh_phase=synced_status_refresh` になり、`latest_mt5_tester_status.md` 内のwatcher欄も旧schemaを読んだ `incompatible` になりません。`latest_mt5_tester_status.md` の watcher `restart_hint` と `runtime_watchers.py` から起動する既定コマンドも `--manual-test-queue runtime/latest_mt5_manual_test_queue.json`、`--manual-queue-launch runtime/latest_mt5_manual_queue_launch.json`、`--manual-collect-run runtime/latest_mt5_manual_collect_run.json` を含め、古いwatcher再起動時に統合手動キュー、次の自動起動候補、collector状態を見落とさないようにします。

主要watcherをまとめて確認し、不足分だけ起動する場合:

```bash
python3 methods/swing_eval/analysis/runtime_watchers.py \
  --interval-seconds 60 \
  --output-json runtime/latest_runtime_watchers.json \
  --output-md runtime/latest_runtime_watchers.md
```

Bridge、MT5 tester status、MT5 manual auto collect、forward test、forward status の5本を対象に、PIDファイル上のプロセスが動いていればそのままにし、止まっているwatcherだけを起動します。Bridge watcherはBridge状態と復旧プランを両方更新します。PIDが残っていてもheartbeatが `interval_seconds * 3` より古い場合は `running_heartbeat_stale`、heartbeatがない場合は `running_heartbeat_missing` として `ok=false` にします。heartbeatがfreshでも、heartbeat内の `watcher_pid` がPIDファイルのPIDと一致しない、`continuous=false`、または `pid_file_written=false` の場合は `running_heartbeat_not_daemon` として `ok=false` にします。MT5 tester status watcher、MT5 manual auto collect watcher、Bridge status watcherは、常駐heartbeatがfreshでも `implementation_version` が現行値と違う、または必須snapshot keyが欠ける場合に `running_heartbeat_incompatible` として `ok=false` にし、古いwatcherが手動テストキュー、Back/Forward preflight、Bridge Recovery Operation Cards、collect ready状態を転記できない状態を見落とさないようにします。これにより、`--skip-pid-file-write` の一回実行heartbeatだけで常駐watcherが健全に見える誤判定も避けます。古いGate/Next Actionを見ているwatcherやheartbeatが止まったwatcherを起動し直したい場合は `--restart`、起動/停止せず確認だけしたい場合は `--dry-run` を付けます。結果は `runtime/latest_runtime_watchers.md` で、watcher名、状態、PID、heartbeat鮮度、heartbeat側PID、PID一致、`pid_file_written`、`continuous`、実装version、期待実装version、schema ok、必須key欠落数、status refresh phase、log、start/restartコマンド、tail logコマンド、直接watcher実行コマンドを確認できます。鮮度条件を変える場合は `--max-heartbeat-age-seconds` を指定します。

`latest_mt5_tester_status.md` には `operational_status`、起動中terminalのPID/command、Bridge Recoveryのstatus/ready/EA POST鮮度/blocking reasons/next action、入力artifactの鮮度、最新runnerのブロック理由、terminal開始時刻/deadline/elapsed、risk preset要約のスキーマ必須/状態/鮮度/欠落入力、compile鮮度、Optimization pass予算、MT5 Manual Test Queue、MT5 Manual Queue Launch、MT5 Manual Collect Run、MT5 Next Action Runner、MT5 Back/Forward Runner、stable candidate探索結果、Promotion GateのP1 actionをまとめます。Artifact Freshnessでは `latest_mt5_tester_run.json`、`latest_promotion_gate.json`、`latest_mt5_compile_status.json`、`latest_mt5_optimization_report.json`、`latest_mt5_next_action_run.json`、`latest_mt5_back_forward_run.json`、`latest_mt5_manual_test_queue.json`、`latest_mt5_manual_queue_launch.json`、`latest_mt5_manual_collect_run.json`、`latest_bridge_recovery_plan.json`、stable candidateのレポート/推薦/runner JSONの存在、更新からの経過秒数、fresh/staleを表示します。Back/Forward Runner欄では `backtest.ini` / `forward_test.ini` のdry-run計画、Back/Forward Plan Validation、各stepのset名とForwardMode、ForwardMode上書き後の実効値、出力先、順次実行時の合計timeoutと今開始した場合の期限、今すぐ実行できるか、dry-runの期間/timeout/件数条件と `run_id_prefix` を引き継いだ `mt5_back_forward_run.py --mode ... --execute ...` の実行ヒント、MT5画面で手動Backtest/Forwardを回すためのExpert/Symbol/Period/Model/Dates/Forward/Inputs/Report表、手動実行後の `--collect-only --csv-modified-after ...` 取り込みコマンド、`Manual Collect Readiness` のready/status/Agent CSV件数、reason、blocking reasons、next action、`evidence_state`、実行後のBacktest vs Forward差分、preflightで止まった場合の `blocked_before_steps`、理由、Ready Statusのreasons/mismatchesとchecked/expected/status execution conditionsを確認できます。`MT5 Manual Test Queue` 欄ではBack/Forward、SELL sample collection、BUY sample collectionのentry/total/stale/step/waiting件数、blocking reasons、Report/Inputs表をまとめて確認できます。`MT5 Manual Queue Launch` 欄では次に自動起動されるqueue/step、起動種別、command、既存terminal検出、blocked reasonsを確認できます。`MT5 Manual Collect Run` 欄ではqueue refresh状態、selected/waiting/invalid件数、execute/dry-run、次にcollectを実行すべきか、まだMT5 Strategy Tester結果待ちかを確認できます。`mt5_tester_status.py` の標準出力JSONと `latest_mt5_tester_status.json` の `operator_summary` にも `manual_strategy_tester_*`、`manual_test_queue_*`、`manual_queue_launch_*`、`manual_collect_run_*` を出すため、Markdownを開かなくてもMT5上で手動Backtest/Forwardを回す入口、自動起動のブロック理由、取り込み状態を確認できます。手動Strategy Testerを回した後は `latest_mt5_back_forward_run.md` または `latest_mt5_manual_test_queue.md` の `Manual Collect Readiness` が `ready=True` / `status=ready_to_collect` になってから、`methods/swing_eval/analysis/mt5_manual_collect.py --execute` または表示されたcollect-onlyコマンドを実行します。readyでない時は `Next action` がReport待ち、Agent CSV待ち、時刻指定ミスのどれかを示します。`evidence_state` は `plan_only`、`executed_consistent`、`executed_degraded`、`executed_below_break_even`、`executed_sample_shortage`、`executed_blocked`、`executed_missing_comparison` などで、dry-run計画と実行済み証跡を区別します。Back/Forward比較表には `min ok` 列を出し、`--min-closed` の件数条件を満たしているかをStatusだけで確認できます。Promotion Gate欄にはGate JSONの `failed_check_names` 全件と `mt5_back_forward_run` / `mt5_back_forward_run_ok` / `mt5_back_forward_run_performance` のpass/value/requirementを表示し、MT上のBack/Forward実行結果を昇格判断へ使える状態か確認できます。定期更新watcherのheartbeatにも `bridge_recovery_plan_status`、`bridge_recovery_plan_ready_for_mt5_validation`、`bridge_recovery_plan_output_json`、`bridge_recovery_plan_blocking_reasons`、`bridge_recovery_plan_next_action`、`manual_test_queue_status`、`manual_test_queue_entry_count`、`manual_test_queue_total_entry_count`、`manual_test_queue_stale_entry_count`、`manual_test_queue_waiting_count`、`manual_queue_launch_status`、`manual_queue_launch_selected_item`、`manual_queue_launch_launch_command_kind`、`manual_queue_launch_blocked_reasons`、`manual_queue_launch_running_terminal_count`、`manual_collect_run_status`、`manual_collect_run_selected_count`、`manual_collect_run_waiting_count`、`manual_collect_run_next_action`、`manual_collect_refresh_status`、`manual_collect_refresh_returncode`、`back_forward_run_plan_validation_ready/status/reasons` が入り、MT5側でEAを付け直した後にBack/Forwardへ進める状態か、Back/Forward計画自体が比較可能か、次にどのStrategy Tester stepを自動起動しようとして止まっているか、手動実行後にcollectへ進める状態か、古いrunner由来のキューが混ざっていないかをstatus watcherだけで確認できます。

Promotion Gateの `MT5 Operator Summary` には、`latest_mt5_tester_status.json.operator_summary` 由来の次のMT5 Strategy Tester step、queue/launch/collect状態、`running_terminal_blocks_direct_config` などの自動起動blocker、collect dry-run/executeコマンドが先頭近くに出ます。詳細が必要な場合は、続く `MT5 Manual Queue From Watcher` でForward/Inputs/Report、launch選択stepとキュー推奨stepの一致、手動チェックリストを確認できます。

仕様書に対して現在の実装とruntime証跡がどこまで揃っているかをまとめる場合:

```bash
python3 methods/swing_eval/analysis/spec_coverage.py \
  --output-json runtime/latest_spec_coverage.json \
  --output-md runtime/latest_spec_coverage.md
```

このレポートは `docs/swing-evaluation-trading-system-spec.md` の `methods/swing_eval/analysis/*.py` コンポーネント見出し、Phase完了条件、主要runtime artifactを読みます。既定では主要artifactのmtimeが24時間以内かも確認し、古い履歴やstatusを `stale_runtime_artifacts` として未完了理由にします。MQL5 artifact確認では、Back/Forward用だけでなくOptimization、stable candidate、BUY/SELL refit、hour/time/trend/calendar validation用の `.ini` / `.set` も監視します。各Tester `.ini` は `ExpertParameters`、Forward、Optimization設定まで確認し、各 `.set` はsignal/live/risk/button安全入力に加えて `InpDailyLossLimit=5000.0`、`InpConsecutiveLossLimit=20`、`InpConsecutiveLossCooldownMinutes=120`、`InpRequireStrategyTester=true` も確認します。MQL5 artifactの欠落、テスト参照不足、marker gapがある場合は `fix_mql5_artifact_coverage` を出し、対象ファイル修正、`mt5_compile_status.py`、`spec_coverage.py` の再確認へ戻します。`latest_mt5_compile_status.json` がMQL5 artifact更新より古い場合や、sources/binaries/Tester `.ini`/`.set` の同期・参照readyフラグがfalseの場合は `refresh_mt5_compile_status` を出し、MT5 Strategy Tester起動前にcompile/status更新へ戻します。BUY/SELL両方のscore weight探索とset変換に加えて、`latest_winrate_fit.json` と `latest_risk_shape_weight_search.json` も主要runtime artifactとして監視し、winrate fitの採用判定、walk-forward集計、risk shape用weight searchの鮮度を同じRuntime Artifacts表で確認します。walk-forward不合格や `skipped_write=true` の `.set` 未生成を未完了理由にします。`goal_completion_proven=false` の時は、Promotion Gate未通過、MT5 terminal起動中、Back/Forwardがplan onlyなど、完了と言えない理由を `not_complete_reasons` に残します。Promotion Gateがcompile status、Back/Forward runner、履歴status、score weight探索/setなどの判断証跡より古い場合も `promotion_gate_stale_vs_dependencies` を出し、古いGateのnext actionを根拠にしないようにします。`latest_mt5_strategy_tester_analysis.json` が読んだPromotion GateまたはBack/Forward runの生成時刻と最新artifactの `generated_at` が違う場合も `mt5_strategy_tester_analysis_stale_vs_dependencies` を出し、横断分析とCoverageの再生成Actionへ戻します。`latest_mt5_tester_status.json` 上のNext Action Runnerが現在のPromotion Gateと一致しない場合は `mt5_next_action_runner_not_current` を出し、MT5起動前に `latest_mt5_next_action_run.*` を再生成させます。Next Action Runnerに高優先度の未処理Actionが残っている場合は `mt5_next_action_runner_blocked_by_prior_actions` を出し、blocking prior actionのpriority/area/action/reason/commandを表示して、commands欄にも `run_blocking_prior_action_N` として出します。これにより、選択中runnerを飛ばしてMT5を起動せず、先行Actionから順に処理できます。`MT5 Operator Handoff` が手動Strategy Testerを推奨している場合、この先行Action blockerは選択中Next Action Runnerだけの停止理由として表示し、Standaloneの手動Strategy Testerキューは `run_mt5_manual_test_queue` から進められることも明示します。Bridge/EAがreadyでない、またはEA POST/snapshot活動が止まっている場合は、履歴更新より先に `refresh_bridge_status` を上位Actionとして出し、`ea_liveness_signal` と `config_get_recent_but_ea_post_stale` で `GET /config` だけが新しい状態も分けて表示します。`latest_bridge_recovery_plan.json` のstatus、blocking reasons、next action、operation card、verification commandsも同じNext Action手順へ転記します。一方でBridge/GPT非依存の `Swing_Evaluation_Trader` Strategy Tester Back/Forward手順、手動キュー、collect-only導線は表示し続けます。履歴pendingがstaleになっている場合は `refresh_history` Actionにも同じBridge Recovery要約を表示し、Bridge statusとRecovery planの再生成コマンドも含めるため、履歴待ちではなくEA再起動待ちであることをその行だけで確認できます。`Next Actions` には履歴更新、MT5 compile/status更新、MT5 status更新、Back/Forwardの `--execute --refresh-ready-status`、手動Strategy Tester後の `--collect-only`、score weight sample collectionの実行ヒントをまとめるため、MT5上でバックテスト/フォワードテストへ進む入口として使えます。`History Request` には `runtime/history_request.json` と `runtime/history_request.done.json` のID照合結果を表示し、pending中は同じ168h取得要求を繰り返さず、EAブリッジの次回POSTを待ってから `history_status.py` で診断を更新します。既定ではpendingが180秒を超えると `history_request_stale_pending`、`runtime/latest_snapshot.json` が300秒を超えると `bridge_snapshot_stale` を出し、履歴待ちではなくBridge/EA接続が止まっている可能性を分けます。この場合の `Next Actions` には `runtime/bridge.log` と `mt5_ai_bridge.py` プロセス確認も表示します。鮮度条件を変える場合は `--max-artifact-age-seconds`、`--max-history-request-pending-seconds`、`--max-bridge-snapshot-age-seconds` を指定します。

`latest_winrate_fit.json` または `latest_risk_shape_weight_search.json` が欠落・staleの場合、`latest_spec_coverage.md` は `refresh_fit_quality_artifacts` をNext Actionに出します。このActionにはwinrate fit再実行、risk shape用backtest診断、risk shape用weight_search、Promotion Gate再生成のコマンドをまとめて表示します。
`latest_spec_coverage.json` / `.md` / 標準出力には `not_complete_reason_count` と `next_action_count` も出すため、監視スクリプトは `not_complete_reasons` / `next_actions` 配列を展開しなくても未完了理由数と未処理Action件数を確認できます。さらに `blocked_phase_count`、`first_blocked_phase`、`first_blocked_phase_primary_reason`、`first_blocked_phase_primary_next_action` も出るため、短縮JSONだけで最初に詰まっているPhaseと実行入口を確認できます。
これらのfit証跡がPromotion Gateより新しい場合も `promotion_gate_stale_vs_dependencies` に含め、古いGateで昇格可否を判断しないようにします。

`latest_bridge_recovery_plan.json` が存在し `ready_for_mt5_validation=false` の場合でも、`Swing_Evaluation_Trader` はBridge/GPT非依存の単体EAなので、`spec_coverage.py` はMT5 Strategy TesterのBack/Forward手順、手動キュー、collect-only導線を表示します。Bridge未readyは履歴取得やsnapshot更新の注意としてNext Actionに残しますが、Standalone Strategy Testerそのものは止めません。Bridge readyを必須にしたい診断時だけ、`mt5_back_forward_run.py --require-bridge-ready --bridge-recovery-plan runtime/latest_bridge_recovery_plan.json` を指定します。この場合はBridge Recoveryが未readyならMT5起動前に停止し、Runner Markdown上でもブロック理由を表示します。

`latest_spec_coverage.json` には `blocked_phase_count` と `phase_current_blockers` も出します。各Phaseの主要な未完了理由、`primary_next_action_id` / priority / summary、関連Next Action IDをJSONで読めるため、Bridge/履歴、Back/Forward、BUY診断、score weightのどれから進めるべきかをMarkdownを横断せず確認できます。Markdownの `Phase Current Blockers` でも主要Actionと関連Action IDを表示します。

`MT5 Status Watcher` 欄には、heartbeatが保持しているNext Action Runnerの `Watch primary`、`Watch archive preview`、`Watch follow-up`、`Watch follow-up archive preview` の予定出力先、action context key、関連実行件数/キーも表示します。Back/Forward Runnerについても `run_id_prefix`、手動Strategy Tester後のcollect-onlyコマンド、手動開始下限時刻、手動step数、per-step timeout、since minutes、min closed、ForwardMode上書き、許可フラグ、Ready Statusのok/reasons/mismatches、checked step keys/options/flags、checked/expected/status execution conditions、archive preview出力先、Backtest/Forward比較のavailable/status/行数/thresholdを表示します。さらに統合手動キューのstatus、next action、entry/step/waiting/ready件数、blocking reasons、current Gate上で実行可能なentry数、selected action一致数、current Gate時刻/decision、stale理由も転記します。score weight再探索中は、walk-forward不合格、`walk_missing` / `walk_folds`、レジーム別 `regime_missing` / `regime_folds`、`.set` 未生成のskip reasonも表示し、次のMT5実行が昇格判定用Back/Forwardではなく診断サンプル収集であることを区別します。Promotion GateはheartbeatのNext Action Runner target/config/archive run ID/planned outputsが最新 `latest_mt5_tester_status.json` の `next_action_runner` と一致するかを `mt5_status_watch_next_action_current` で確認します。Back/Forward `run_id_prefix` と `execution_conditions` も `mt5_status_watch_back_forward_current` で確認し、watcher自体が `ok` でも古い出力先、古いrun-id、ForwardMode、timeoutを見ていれば再起動next actionへ戻します。MT5を閉じて `/config` 起動する前に、この欄で常駐watcherが最新Gateの出力先、Back/Forward条件、手動キューの待ち状態を見ているか確認できます。

Promotion GateのAgent CSV archive run IDは入力証跡の生成時刻をseedにします。Gateだけを再生成してもrun IDは変わらず、status/watch更新だけでNext Action Runnerのplanned outputsが即staleになることを防ぎます。Statusの `current_for_execution` もGateの生成時刻だけでは落とさず、decision、target、config、set、archive run ID、timeout、primary/archive/follow-up planned outputsが現Gateと一致していれば実行可能とします。同じtargetでもrun IDや出力先が変わった場合は `selected_action_mismatch` で止めます。Promotion Gateのwatcher一致checkも `runner_promotion_generated_at` の差だけでは落とさず、実行計画の差だけをmismatchとして扱います。Runner freshnessを見る場合は `runner_generated_at`、Gate一致を見る場合は `promotion_generated_at` / `promotion_decision` を使います。CLI短縮出力にもこの3項目を出すため、MT5手動実行のcollect下限時刻とGate世代を混同しないで確認できます。

`--optimization-report` を指定すると、最新runnerがブロック中でも直近Optimizationレポートから `.set`、最適化入力数、全探索上限pass数、Tester XMLへ実際に出たback/forward行数、全探索比率を表示します。加えて `max_executed_tester_xml_rows`、`full_factorial_progress_ratio`、`full_factorial_remaining_upper_bound` を出し、全探索上限に対してTester XMLに何行出ているかを確認できます。これはMT5 genetic optimizationの参考値であり、実際の最適化は全探索候補より少ないpassで終わることがあります。`.set` が存在する場合はレポート内の古いpass予算ではなく、現在の `.set` から再見積もりし、`set_file_reestimated` で判別できるようにします。

`blocked_running_terminal` は `/config` 自動起動だけを止める状態です。`MT5 Operator Handoff` が `manual_strategy_tester` を推奨している場合はMT5を閉じず、表示された `Next MT5 step` のExpert、Symbol、Period、Dates、Forward、Inputs、ReportをStrategy Testerへ設定してBacktest/Forwardを回します。完了後は同じ欄のcollect-onlyコマンドでReport/Agent CSVを取り込みます。MT5を閉じるのは、`latest_mt5_manual_queue_launch.md` の `/config` コマンドで1ステップだけ自動起動したい場合です。過去runが `terminal_already_running` で止まっていても、現在terminalが検出されなければ `ready_to_rerun_after_terminal_closed` になり、次はTester再実行へ進めます。通常runが `ok=true` でもrisk preset要約に現在の安全入力が欠けている場合は `blocked_risk_preset_schema` になり、現在runnerでの再実行が必要だと分かります。`risk_preset_schema_status` は `not_required`、`current`、`missing_inputs`、`missing_preset` のいずれかです。

`latest_spec_coverage.md` の `run_mt5_manual_test_queue` Next Actionにも `Queue current Gate` を表示します。ここで `current_for_execution`、`selected_action_current`、`selected_action_stale`、`current_gate`、`current_decision`、`gate_stale`、`not_current` を確認し、SELL/BUY sample runnerが最新Promotion Gateでも同じ実行計画かを見てからMT5 Strategy Testerへ入ります。

`latest_mt5_next_action_run.json` がある場合は、statusにtarget、kind、config、set、output set、archive run ID、timeout、今開始した場合のtimeout期限、理論pass上限、直近Tester XML行数、dry-run/実行済み、primary実行結果を表示し、MT5上でバックテスト/forward testを起動する前後の状態を同じ画面で確認できます。Markdownでは直近Tester XML行数を `back=185, forward=185` のように表示し、sourceやfull-factorial比率も同じ行で確認できます。dry-run時点でもprimary/follow-upの `output_json`、`optimization_output_json`、`recommendation_output_json` を表示するため、実行後にどのファイルを確認するかをstatusだけで追えます。`post_execution_artifacts` がある場合は、statusにもprimary/follow-up後の証跡種別、Tester run `ok/blocked/source_time_blocked/report_fallback_blocked/elapsed`、Optimization closed/PF/XML rows、Recommendation採用可否/next setを表示します。`score_weight_sample_collection` は `evidence_role=diagnostic_sample_collection` / `promotion_evidence=false` として表示され、score再fit用サンプルと昇格判定用成績を混同しないようにします。score weightの `action_context` がある場合は、follow-up status、sample shortage、walk-forward状態、`walk_missing` / `walk_folds`、レジーム別 `regime_missing` / `regime_folds`、set skip reason、上位weight候補に加えて、`action_context_keys` と `related_execution_keys` もstatus/heartbeatへ要約し、同じweight変換を繰り返すべきか、先にMT5でサンプル収集すべきかを確認できます。Next Action Runnerの `Manual Collect Readiness` では、手動Strategy Tester後のReport/Agent CSV待ち、collect-only実行可、次アクションも確認できます。さらにrunnerが現在のPromotion Gateから作られたものかを `promotion_gate_current`、`selected_action_current`、`current_for_execution`、`gate_stale_reason` で表示し、Gate更新後に古いrunnerをMTへ渡さないようにします。`spec_coverage.py` のBUY/SELL side別sample collection Actionも、`latest_mt5_next_action_run_<side>.json` のGate生成時刻やdecisionが現在のPromotion Gateと合わない場合は、その古い手順を使わずside別runner再生成へ戻します。選択中runnerより優先度の高いGate action、または同じ優先度で選択中runnerより前に並ぶGate actionが残っている場合は `Blocking prior actions`、件数、`blocking_prior_action_summary`、action一覧を表示し、0件の場合も `blocking_prior_action_count=0` / `blocking_prior_actions=[]` として実行前の前段なしをJSONで確認できます。前段が残る場合は `next_action_execution.ready=false` / `higher_priority_actions_pending` でMT5 Tester起動を止めます。`Blocking prior actions` には、生のprimary commandに加えて `mt5_next_action_run.py --target ... --execute --refresh-ready-status ...` のRunner実行ヒントを表示し、primaryがローカルrefreshなら `--allow-non-tester-primary` 付きの安全な入口を示します。`next_action_execution.ready/status/reasons` では、現在terminal、compile鮮度、Promotion Gate/compile/next action runのfresh判定、primaryがMT5 Tester起動かどうかをまとめて判定し、MT5上でバックテスト/forward testへ投入できる状態かを明示します。`mt5_next_action_run.py --execute` のpreflightはtarget/config/commandだけでなく、primary/archive preview/follow-upのplanned outputsも比較し、出力先がずれた古いrunnerを実行前に止めます。primaryが `mt5_optimization_recommend.py` のようなローカルrefreshの場合は、MT5 Tester起動判定とは別に `next_action_local_execution.ready/status/reasons` を表示します。これはPromotion Gate、Optimization report、Next Action dry-runのfresh判定を使い、`--allow-non-tester-primary` を付けて推薦refreshだけを安全に実行できる状態かを示します。Optimization reportのmtimeが古い場合でも、latest tester run内の `optimization_summary` とgenerated_at、closed、PF、平均R、net profit、source-time整合が一致する場合は `optimization_report_evidence.current=true` として、既存の最新Tester証跡からの推薦refreshを許可します。stable candidate検証後にGateが `stable_candidate_refit` を出した場合は、statusにもrefit side/driver/kind/config/set/output set/archive run IDを表示し、Gate Markdownを開かなくても次に走らせるTester計画を確認できます。すでにそのrefitが完了済みで `stable_candidate_refit_completed` が出ている場合は、status/heartbeatにも完了kind、side、status、PF、平均R、理由、skip reasonを転記し、同じstable candidate検証を繰り返さずscore refitなど次段へ進む理由を監視ファイルだけで確認できます。

短期Optimizationのchronological splitが失敗していても、Recommendation refreshが不採用として確定し、SELL regime-entry refitも完了済みで次がscore weightサンプル収集の場合は、`reject_chronologically_unstable_optimization` を別P1 actionとして二重に残さず、`sell_score_refit` の `upstream_chronological_rejection` としてrunnerへ転記します。chronological split欠落、未処理のローカルrefresh、またはscore sample収集へ進めない状態では従来通り先行ActionとしてMT5起動を止めます。

定期更新watcherの `runtime/mt5_tester_status_watch_heartbeat_current.json` にも `operational_status`、`ready_for_tester_launch`、`next_action`、`next_action_execution_ready/status/reasons`、`next_action_local_execution_ready/status/reasons`、artifact鮮度、起動中terminal件数、risk presetスキーマ状態と欠落入力、pass予算、Next Action Runnerのtarget/kind/config/timeout/今開始した場合のtimeout期限/pass見積もり/dry-run/primary実行状態/planned outputs、Next Action RunnerのMT5起動コマンドと手動collect-onlyコマンド、action context key、関連実行件数/キー、ブロック前段action件数/一覧/summary、`evidence_role` / `diagnostic_only` / `promotion_evidence`、score weight follow-up status / sample shortage / walk-forward status / walk不足件数 / regime不足件数 / fold不足 / set skip reason、Back/Forward Runnerの `run_id_prefix` / 手動Strategy Tester後のcollect-onlyコマンド / 手動開始下限時刻 / Manual Collect Readiness / 手動step一覧 / 合計timeout/期限/step別timeout/execution conditions/ForwardMode上書き/evidence state / 比較available/status/行数/threshold、Ready Statusのok/reasons/mismatches/checked step keys/options/flags/checked/expected/status execution conditions、Gate一致判定、未処理の高優先度actionまたは同順位の前段action、実行後artifact要約、stable candidateのclosed/PF/採用不可理由、stable candidate refitのkind/config/set/run-id、Promotion Gateのdecision/failed件数/failed check名/Back-Forward Gate checkのpassとvalueを転記するため、heartbeatだけでも監視が動いているか、現在のブロック理由、参照ファイルが古くないか、次に走らせるrefitが何か、実行後のTester/Optimization/Recommendation結果がどうだったか、ローカルrefreshを先に実行すべきか、Back/Forward実行結果が昇格判断へ使えるか、MT上で手動実行した結果をどう取り込むかを確認できます。heartbeatには `watcher_pid`、`run_index`、`max_runs`、`continuous`、`started_epoch`、`finished_epoch`、`elapsed_seconds`、`implementation_version`、必須snapshot key一覧も残します。統合手動キューの `entry_count`、`total_entry_count`、`stale_entry_count`、current Gate上の実行可能件数、selected action一致件数、current Gate時刻/decision、Gate stale理由も必須snapshot keyで、古いrunner由来のentryが混ざっていないか確認できます。Back/Forwardの `run_id_prefix`、手動collect-onlyコマンド、手動開始下限時刻、Manual Collect Readinessのready/status/csv_count/modified_after/reason/blocking/next_action、手動step数/一覧、`execution_conditions` とForwardMode上書き、比較available/status/行数/threshold、Ready Statusのok/reasons/mismatches/checked step keys/options/flags/checked/expected/status execution conditions、Next Action Runnerのprimary/archive preview/follow-up planned outputs、Next Action Runnerの起動/collect-onlyヒント、Next Action RunnerのManual Collect Readiness、Next Action Runnerの証跡区分、score weight診断区分、score weightのwalk/regime不足件数とfold数、関連実行件数、ブロック前段action件数/一覧/summaryも必須snapshot keyで、`implementation_version` も現行statusが期待する値と一致する必要があります。古い常駐watcherがBack/Forward実行条件やpreflight比較対象、比較状態、統合手動キューの総数/stale件数、Gate一致要約、Back/ForwardのMT5手動手順取り込みヒント、Back/Forward/Next Actionの手動取り込みreadiness、前段action一覧やsummaryを転記できない場合、または実装世代が古い場合は `incompatible` になります。`latest_mt5_tester_status.md` の `MT5 Status Watcher` ではheartbeatの `status` を `ok` / `stale` / `incompatible` / `missing` で表示し、古い常駐watcherが新しいsnapshot keyを出していない場合や実装世代が古い場合は `restart_hint` に再起動用コマンドを表示します。Promotion Gateも `latest_mt5_tester_status.json` のwatcher診断を読み、`mt5_status_watch_heartbeat` が `ok` でない場合は `restart_mt5_status_watch_with_current_schema` のnext actionを出し、watcher世代、Gate世代、Back/Forward実行条件、比較available/status/行数、前段action件数/一覧/summary、Ready Statusのok/reasons/mismatches/checked step keys/options/flags/checked/expected/status execution conditions、archive preview出力先、Next Action planned outputsをGate Markdownに表示します。

`--report-name` のXMLがまだ存在しない場合は、MT5 Tester直下または `runtime/mt5_optimization` にある最新の `Swing_Evaluation_Trader*.xml` / `.forward.xml` ペアへfallbackします。どのXMLを使ったかは `runtime/latest_mt5_tester_run.json` の `report_paths` に残ります。ただし通常起動でfallbackした場合は `report_fallback_blocked=true` とし、古いXML/CSVからの収集や推薦 `.set` 更新は行いません。collect-onlyでは既存XMLの再集計用途としてfallbackを許容します。
`mt5_tester_run.py` がterminal失敗、通常fallbackブロック、期間不一致などで集計または推薦生成を止めた場合、子の `latest_mt5_optimization_report` / `latest_mt5_optimization_recommendation` には `ok=false` の停止マーカーを出します。停止マーカーにはReportパス、terminal時刻、compile状態、risk preset、Agent CSV退避状況、`blocked_components` も残します。期間不一致で集計summaryだけは作れた場合はOptimization子レポートに実測値を残し、Recommendation子レポートだけを停止マーカーにします。

Promotion Gateが出したMT5の次実行計画を確認する場合:

```bash
python3 methods/swing_eval/analysis/mt5_next_action_run.py \
  --promotion-gate runtime/latest_promotion_gate.json \
  --output-json runtime/latest_mt5_next_action_run.json \
  --output-md runtime/latest_mt5_next_action_run.md
```

既定はdry-runで、無指定時は現在のPromotion Gate内で最初に見つかるMT5 Tester計画を選び、`target` には `score_weight_sample_collection` などの具体ラベルを記録します。特定の計画を狙う場合だけ `--target stable_candidate_refit` のように指定します。選ばれたconfig/set/output set、Agent CSV archive preview、実行コマンド、予定出力先をファイルに書くだけです。MT5 primaryにtimeoutがある場合は、dry-run JSON/Markdownのprimaryにも今開始した場合のtimeout期限を出し、Status Watcher欄にも監視中target、config、timeout、pass見積もりを表示します。Forward系のnext actionではStrategy Tester本体をprimaryにし、`mt5_forward_collect.py` はfollow-upとして表示します。手動Strategy Tester前に残存Agent CSVのsource timeだけ確認する場合は、`--run-archive-preview` を付けるとMT5 primaryを起動せずarchive previewだけを実行し、`post_execution_validation.archive_preview` にreturncode、予定JSON、`ok=true`、`execute=false` の確認結果を残します。実際にMT5 Testerを起動する時だけ `--execute` を付けます。`--execute` は既定でprimaryが `methods/swing_eval/analysis/mt5_tester_run.py` の時だけ通し、Promotion Gateが先に `mt5_optimization_recommend.py` などのローカルrefreshへ戻している場合は `non_tester_primary` で止めます。MT5 Tester primaryを実行する場合は `runtime/latest_mt5_tester_status.json` の `next_action_execution.ready=true`、同じtarget/config/command、primary/archive preview/follow-upのplanned outputs、status鮮度を実行直前に要求します。古いstatusや別target/別出力先のdry-runからMT5を起動しないためです。そのローカル処理を意図的にrunnerから実行する時だけ `--allow-non-tester-primary` を付けます。この場合も同じready statusを読み、`next_action_local_execution.ready=true`、同じtarget/command/planned outputs、status鮮度を要求します。古いOptimization report、古いGate、または別出力先のrunnerから推薦refreshしないためです。`--execute --refresh-ready-status` では、status更新前に選択済みtargetのdry-runを `latest_mt5_next_action_run.json` / `.md` へ一度書き、status preflightが古いrunnerではなく今選んだrunnerを比較できるようにします。診断目的でこの実行直前checkを外す場合だけ `--skip-ready-status-check` を使います。`mt5_optimization_recommend.py` は推薦JSONを正常生成しても `adoptable=false` なら終了コード2を返すため、runnerは予定 `--output-json` の推薦artifactが `ok=true` でdecisionを含む場合に限り、`accepted_returncode=true` / `recommendation_refresh_completed_not_adoptable` として処理完了扱いにします。MetaEditor compile planも先に実行したい時だけ `--run-compile` を付けます。primary成功後に収集コマンドまで続ける時だけ `--run-follow-up` を付けます。`--execute` 後はprimary/follow-up commandの `--output-json`、`--optimization-output-json`、`--recommendation-output-json` を読み、`post_execution_artifacts` とMarkdownの `Post Execution Artifacts` に証跡種別、Tester runの `ok/blocked/source_time_blocked/report_fallback_blocked/elapsed`、Optimizationのclosed/PF/XML rows、Recommendationの採用可否と次setを要約します。`score_weight_sample_collection` の実行結果には `diagnostic_only=true` / `promotion_evidence=false` を付け、評価関数再fit用のサンプルとして扱います。MT5 Tester primaryではsubprocess returncodeだけでは成功扱いにせず、予定 `output_json` が存在し、Tester run JSONが `ok=true` で、blocked/source-time/fallback/terminal失敗がないことを `post_execution_validation` で確認します。不備があれば `blocked_after_primary=primary_tester_artifact_not_ok` で停止し、follow-upは実行しません。`mt5_forward_collect.py` follow-upもreturncodeだけでは成功扱いにせず、予定 `output_json` のForward reportが存在し、`ok=false` でなく、`summary.overall.closed` が読めることを確認します。不備があれば `blocked_after_follow_up=follow_up_artifact_not_ok` になります。

`runtime/latest_mt5_next_action_run.json` は、ネストされた `primary` を開かなくてもMT上の実行確認に使えるように、トップレベルにも `kind`、`focus_side`、`optimization_mode`、`config`、`set`、`output_set`、`agent_csv_archive_run_id`、`timeout_*`、`estimated_full_factorial_passes`、`latest_executed_tester_xml_rows`、4分類をまとめた `planned_outputs`、`primary_planned_outputs`、`archive_preview_planned_outputs`、`follow_up_planned_outputs`、`action_context_keys`、`related_execution_keys` を出します。dry-run、実行前status refresh用preflight、preflight失敗のどの経路でも同じキーを確認できます。

MT5を実際に起動する時は、通常はstatus再生成込みで次の形にします。`--refresh-ready-status` により、起動直前に `latest_mt5_tester_status.json` / `.md` を更新してからpreflightを判定します。現在statusの `MT5 Next Action Runner` 欄にも同じ実行ヒントが表示されます。

```bash
python3 methods/swing_eval/analysis/mt5_next_action_run.py \
  --target score_weight_sample_collection \
  --execute \
  --refresh-ready-status \
  --output-json runtime/latest_mt5_next_action_run.json \
  --output-md runtime/latest_mt5_next_action_run.md
```

昇格判定:

```bash
python3 methods/swing_eval/analysis/promotion_gate.py \
  --forward-ledger runtime/forward_tests.jsonl \
  --forward-status runtime/latest_forward_test_status.json \
  --mt5-forward-report runtime/latest_mt5_forward_report.json \
  --mt5-optimization-report runtime/latest_mt5_optimization_report.json \
  --mt5-tester-run-report runtime/latest_mt5_tester_run.json \
  --mt5-back-forward-run runtime/latest_mt5_back_forward_run.json \
  --mt5-buy-refit-recommendation runtime/latest_mt5_buy_refit_recommendation.json \
  --mt5-buy-entry-refit-recommendation runtime/latest_mt5_buy_entry_refit_recommendation.json \
  --mt5-sell-entry-refit-recommendation runtime/latest_mt5_sell_entry_refit_recommendation.json \
  --mt5-sell-regime-entry-refit-recommendation runtime/latest_mt5_sell_regime_entry_refit_recommendation.json \
  --mt5-buy-hour03-validation-recommendation runtime/latest_mt5_buy_hour03_validation_recommendation.json \
  --mt5-buy-hour03-wide-stop-validation-recommendation runtime/latest_mt5_buy_hour03_wide_stop_validation_recommendation.json \
  --mt5-buy-hour03-wide-stop-calendar-validation-recommendation runtime/latest_mt5_buy_hour03_wide_stop_calendar_validation_recommendation.json \
  --bridge-status runtime/latest_bridge_status.json \
  --mt5-compile-status runtime/latest_mt5_compile_status.json \
  --winrate-fit-report runtime/latest_winrate_fit.json \
  --risk-shape-weight-search-report runtime/latest_risk_shape_weight_search.json \
  --require-mt5-forward \
  --require-mt5-optimization \
  --require-mt5-compile \
  --require-winrate-fit \
  --min-side-avg-r 0.0 \
  --max-side-total-r-share 0.85 \
  --min-score-quality-threshold 70 \
  --min-score-quality-count 20 \
  --min-score-quality-avg-r 0.0 \
  --min-score-quality-pf 1.2 \
  --max-score-quality-avg-r-drop 0.25 \
  --max-drawdown-r 0 \
  --min-expectancy-r 0 \
  --max-forward-drawdown-r 0 \
  --min-forward-expectancy-r 0 \
  --min-forward-side-closed 10 \
  --min-forward-side-pf 1.0 \
  --min-forward-side-avg-r 0.0 \
  --max-mt5-forward-drawdown-price-r 0 \
  --min-mt5-forward-expectancy-price-r 0 \
  --min-mt5-forward-side-closed 10 \
  --min-mt5-forward-side-pf 1.0 \
  --min-mt5-forward-side-avg-price-r 0.0 \
  --min-mt5-optimization-closed 100 \
  --min-mt5-optimization-pf 1.2 \
  --max-mt5-optimization-drawdown-price-r 0 \
  --min-mt5-optimization-expectancy-price-r 0 \
  --min-mt5-optimization-side-closed 30 \
  --min-mt5-optimization-side-pf 1.0 \
  --min-mt5-optimization-side-avg-price-r 0.0 \
  --min-mt5-optimization-forward-pf 1.2 \
  --min-mt5-optimization-forward-trades 30 \
  --min-mt5-optimization-positive-forward-back 1
```

標準出力には判定、失敗件数、主要next actionだけを出します。完全な判定JSONは
`runtime/latest_promotion_gate.json`、読みやすい要約は `runtime/latest_promotion_gate.md` を見ます。
`latest_promotion_gate.json` のトップレベルには `check_count`、`failed`、`failed_checks`、`failed_check_names` も入り、MT5でBack/Forwardを回した後にどのGate checkで止まっているかをJSONだけで確認できます。
デバッグで全JSONを端末へ出したい場合だけ `--print-full-report` を付けます。
`Next Action Execution Plans` のMT5実行計画には `passes` と `timeout` も表示します。`passes.full_factorial` は `.set` から見た理論上限で、直近Optimizationレポートに実行済みTester XML行数がある場合は `recent_xml_rows` として back/forward の実績も併記します。`stable_candidate_refit` など未来の出力先へ向かうgenetic系refitにも、source付きで直近Optimization行数を表示します。一方、単発のStrategy Forward TestにはOptimization行数を混ぜません。MT5 Testerを起動する計画には、事前確認用の `compile` plan も表示します。Agent CSV退避付きのMT5実行には、同じrun-idの `archive_preview` / `follow_up_archive_preview` / `refit_archive_preview` も表示し、previewは `--include-source-time` 付きで残存CSVの期間を確認します。手動previewの既定は `runtime/latest_mt5_agent_csv_archive.json` のままですが、Gateが自動生成するpreviewは `runtime/latest_mt5_agent_csv_archive_<run_id>.json` へ分け、BUY/SELLや年次計画の証跡を上書きしません。Markdownのplan行にも `include_source_time=True` を出します。`mt5_next_action_run.py --execute` では、archive previewのreturncodeと予定 `--output-json` の `ok=true` / previewモードを確認し、失敗または出力欠落なら `archive_preview_failed` / `archive_preview_artifact_not_ok` でMT5 Tester primaryを起動前に止めます。
時系列split失敗で年次検証へ戻すnext actionでは `chronological_failure` を表示し、崩れたsplitのPF、平均R、期間、診断文を実行計画の近くで確認できます。forward-only上位passを避けてstable pass周辺へ絞るnext actionでは `forward_only_top` と `stable_pass_hint` を表示し、除外すべき上位forward passと次に制約するstable pass候補を確認できます。
`timeout` は起動後の最長待機時間で、実際の終了時刻はコマンドを開始した時刻から見ます。
score calibrationのnext actionでは、実行コマンドの直下に `score_gap`、`highest_sampled`、`highest_sufficient`、`calibration_recommendation`、`score_quality_gap`、`weight_search_top`、`weight_search_delta` を表示し、70点以上が何件足りないか、どのscore帯までは十分なサンプルがあるか、平均R/PF/score劣化がどの条件で未達か、探索済みの重み候補はどれか、baselineから平均R/PF/DDがどう変わったか、walk-forwardで残ったかを確認します。follow-upの `weight_search.py` は `runtime/latest_score_weight_search.json` も出力し、上位重み候補、baseline、walk-forward aggregateを機械可読な探索証跡として残します。walk-forward表示では平均R/PFだけでなく、候補とbaselineの `total_r`、`delta_total_r`、`min_count` も併記し、平均値が良く見えても総Rで負けていないかを確認します。
MT5 Optimization / 年次 / Forwardのside別score診断で `score_inversion` が出た場合は、MT5 Testerのside別再fit計画に加えて `score_weight_search` 計画も出します。これは `methods/swing_eval/analysis/weight_search.py --side buy` または `--side sell` をwalk-forward付きで実行し、`runtime/latest_score_weight_search_168h_<side>_rr4.json` に診断用の配点探索結果を残すためのものです。既存のside別JSONがあれば `side_weight_search_top`、`side_weight_search_delta`、`side_weight_search_walk`、`side_weight_regime_top` を該当action近くに表示し、さらに本文の `Side Score Weight Search` セクションにもBUY/SELL別の上位候補、baseline比較、walk-forward結果、レジーム別上位候補をまとめます。Gateは続けて `score_weight_set` 計画も表示し、walk-forward合格済み候補だけを `methods/swing_eval/analysis/score_weight_set.py` でMT5検証用setへ変換します。ここで良く見えた重みも、MT5 Optimizationと年次検証を通るまでは採用しません。
Optimization推薦が不採用、またはscore inversionで診断用setになっている場合は、該当するMT5実行計画の直下に `recommendation_block`、`recommendation_reason`、`side_score_issue` を表示します。ここで `adoptable=false`、`skipped_write=true`、`skip_reason=not_adoptable` または `diagnostic_only=true` / `skip_reason=diagnostic_only`、`score_refit_sides`、side別のbase/high PFを確認し、既存のfocused `.set` を採用しない理由と再fit対象sideを実行前に確認します。
`sell_sl_tp` のfocused `next_optimization` では、実行計画の直下に `sl_tp_best` と `sl_tp_weak` を表示します。`sl_tp_best` は次に探索範囲を寄せる候補、`sl_tp_weak` はPF/平均Rや診断文から除外または減点する候補です。focus sideの帯が欠ける場合は `sl_tp_segment_gap` に `best_counts` / `weak_counts` を出し、現在のOptimization集計がSELL用SL/TP判断に足りないことを明示します。
MT5 Optimization未達のfocused `next_optimization` では、実行計画の直下に `mt5_optimization_gap` と `mt5_optimization_side_gap` も表示します。全体PFとBUY/SELL別のclosed件数、PF、平均Rの不足を同じコマンドの近くで確認できます。
dry-runが最新HOLD signalをEA送信前に正しくrejectedしている場合は、`dry_run_wait` にoutcome、signal action、command status、signal/command整合理由、risk gate許可状態、失敗check名を表示します。鮮度で落ちている場合は `dry_run_freshness` にcommand/resultの経過秒数、許容秒数、fresh判定も表示します。古いrejected commandに `lot_policy` が無い場合などは、HOLD待ちでも `dry_run_command_safety` に欠落内容を表示します。
candidate数不足のnext actionでは、`candidate_gap`、`history_check`、`history_timeframes_check` を表示し、候補数が何件不足しているか、168h履歴自体とM1/M5/M15/M30の本数が条件を満たしているかを確認します。Promotion Gateは `runtime/latest_bridge_status.json` も読み、Bridge/EA接続が `ready` でない場合は `bridge_status_ready` をFAILにして、履歴再取得やbacktest再実行より先にBridge/EA復旧next actionを出します。Bridge Status欄には `ea_liveness_signal`、`config_get_recent_but_ea_post_stale`、last config GETも表示するため、`GET /config` だけが新しくEA POSTが止まっている状態をGate側だけでも確認できます。Bridge/EAが復旧してから `src/bridge/request_history.py 168` と `history_status.py` の `status_check` を実行し、`runtime/latest_history_status.json` で履歴更新と本数を確認してからbacktestを再実行します。
MT5 Optimization / Yearly Optimizationは、`.set` 由来の `optimization_pass_budget` と `executed_tester_xml_rows` もGateで確認します。古い再集計レポートでこの証跡が欠けている場合は、pass数やforward/back rowsを確認できないため昇格不可にします。
年次/out-of-yearレポートでsource-time、chronological split、time/trend診断、pass budget証跡が欠けている場合は、`mt5_yearly_validation` のnext actionに `collect_refresh` を出します。このplanは `runtime/latest_mt5_2025_optimization_report.json` / `runtime/latest_mt5_2025_recommendation.json` を出力先にし、期待期間 `2025.01.01` から `2025.12.31`、`--drop-source-time-mismatch-files`、`--fail-on-source-time-mismatch`、年次Tester XML `Swing_Evaluation_Trader_next_optimization_2025.xml` / `.forward.xml` を明示します。ただし短期Optimization推薦が `adoptable=false` / `skipped_write=true` の場合は、年次XMLを再集計せず、先に短期の `mt5_optimization_recommendation_refresh` へ戻します。除外したCSVがある場合はGateの `yearly_source_time_file_filter` / `yearly_source_time_dropped` に件数と理由を出します。
年次/out-of-yearのnext actionでは、実行計画の直下に `yearly_overall`、`yearly_metric_gap`、`yearly_missing_evidence`、`yearly_chronological_failure` も表示します。PF/平均R/positive forward-backの未達、source-timeやchronological splitの欠落、time/trend診断の不足を、年次再実行または再集計コマンドの近くで確認できます。
古いレポートに証跡だけを補完する場合は、`python3 methods/swing_eval/analysis/mt5_pass_budget_backfill.py --optimization-json runtime/latest_mt5_2025_optimization_report.json --tester-run-json runtime/latest_mt5_tester_2025_run.json --output-json runtime/latest_mt5_2025_optimization_report.json --output-md runtime/latest_mt5_2025_optimization_report.md` を使います。
Gateの `Backtest Vs Forward Drift` では、backtestを基準にPython forward、MT5 forward、MT5 Optimization、Yearly OptimizationのPF、平均R/価格R、期待R、最大DDの差分を表示します。`--mt5-back-forward-run` を指定している場合は、別枠の `MT5 Back/Forward Runner Drift` にMT5上で手動検証したbacktest/forwardのclosed、PF、平均R、期待R、価格R DD、損益差分も表示します。実運用ログやTester結果がバックテストからどれだけ劣化しているかをここで確認します。
Gateは `runtime/latest_mt5_optimization_recommendation.json` も読み、`decision.adoptable=false` や `set_metadata.diagnostic_only=true` / `skipped_write=true` の場合は、既存の `next_optimization.set` を最新推薦として扱わず昇格不可にします。この場合の `mt5_optimization_recommendation` next actionは、古い `.set` でTesterを再実行するのではなく、まず `mt5_optimization_recommend.py` を既存の `runtime/latest_mt5_optimization_report.json` に対して実行し、推薦と次回 `.set` だけを更新します。Strategy Test後にこのrefreshでAgent CSVを再集計すると、直近Forward CSVをOptimization証跡として誤読するためです。Optimization report自体が欠落、古い、期間不一致、またはschema不足の場合だけ `mt5_tester_optimization_report.py` で再集計してから推薦を作ります。stable hintがある不採用推薦では、別名のstable candidate setを `--allow-non-adoptable-output-set` で生成し、`Swing_Evaluation_Trader_stable_candidate.ini` と `--sync-expert-parameters-set` 付きTester計画を出します。同じ状態でstable pass、focused `next_optimization`、SELL score refit、regime/yearly refit、年次validation、MT5 runner失敗復旧の実行計画が出る場合も、未更新の `.set` を直接実行せず、先に推薦refreshまたはstable candidate検証へ戻します。SELL regime/entry refitの推薦ファイルもGate入力として扱い、完了済みの同種refitが採用不可なら `stable_candidate_refit_completed` を表示して再実行計画を抑制します。
Gateは `runtime/latest_mt5_tester_run.json` も読み、`ok=false` の場合は `mt5_tester_run_ok`、通常起動で `agent_csv_archive_missing=true`、`agent_csv_archive.ok=false`、または退避件数があるのに `source_time_coverage` がない場合は `mt5_tester_run_agent_csv_archive`、runner側で `source_time_blocked=true` の場合は `mt5_tester_run_source_time`、terminalがtimeoutまたは非0終了した場合は `mt5_tester_run_terminal`、通常起動で `report_paths.source=latest_pair_fallback` の場合は `mt5_tester_run_report_paths` をFAILにし、Agent CSV退避付き再実行へ戻します。Promotion Gate Markdownの `MT5 Tester Run` には退避OK/countと `source_time_coverage` のclose件数、server_time付き件数、first/lastも表示します。通常起動で `ok=true` でもrisk preset要約に現在の安全入力一式、特に `InpRequireStrategyTester`、`InpChartButtonDryRunOnly`、`InpAllowChartButtonTrading` が無い場合は `mt5_tester_run_risk_preset_schema` をFAILにし、現在のrunnerで再実行します。`mt5_tester_run_agent_csv_archive` の復旧previewは `--include-source-time` 付きで、残っているAgent CSVの期間を先に確認します。`mt5_tester_run_ok` のnext actionは `blocked_components` を見て、compile staleなら `compile` plan、risk preset不正なら `risk_preset_fix` plan、Agent CSV退避失敗なら `archive_failure` を分けて表示します。
Optimizationのtime/trend診断は、表が存在するだけでは不十分です。`by_entry_server_hour` やM30/M15/M5 trend/slope系が `unknown` だけの場合は、古いCSVまたはEA再配置漏れとして `mt5_optimization_time_regime_diagnostics` / `mt5_optimization_trend_regime_diagnostics` をFAILにし、現行EAのCSVで再集計します。
年次/out-of-year Optimizationレポートを読み込んだ場合も同じです。`mt5_yearly_optimization_time_regime_diagnostics` / `mt5_yearly_optimization_trend_regime_diagnostics` が欠ける、または `unknown` だけなら、年次検証は再実行/再集計対象です。
SL/TP診断も同じ扱いです。`--require-mt5-optimization` や年次検証では `mt5_optimization_sl_tp_diagnostics` / `mt5_yearly_optimization_sl_tp_diagnostics` を確認し、`By Risk Reward And TP Points` がない古いレポートはRR×TP帯の崩れを見落とすため、Agent CSVから再集計するnext actionへ戻します。
Winrate fitは `adoption_decision.adopted=true` だけでは不十分です。Gateは `walk_rows` のaggregateも確認し、`total_test_fitted_count` が最終testの最低件数未満、または `mean_test_fitted_pf` が最低PF未満なら `winrate_fit_walk_forward` をFAILにして、purge/embargo付き `winrate_fit.py` の再実行へ戻します。
`winrate_fit` のnext actionでは、実行計画の直下に `winrate_adoption` と `winrate_walk_gap` を表示します。採用判定の理由、walk-forward fold数、fitted test件数の不足、平均R/PFの閾値との差を再fitコマンドの近くで確認できます。

`--max-*-drawdown-*` は `0` 以下で無効です。指定した場合はbacktest / Python forward / MT5 forward / MT5 optimization / yearly optimizationの最大DDを昇格条件に加えます。`--min-*-expectancy-*` を指定した場合は期待Rも昇格条件に加え、未達時は `risk_shape` のnext actionでDD低減または期待R再fitを促します。このnext actionは `reports/risk_shape_backtest_168h_min40.xlsx` と `reports/risk_shape_weight_search_168h_both_rr4.xlsx` を出す専用診断計画を持ち、weight_searchはwalk-forward付きで実行します。`--risk-shape-weight-search-report` のJSONが存在する場合は、実行計画直下に上位候補、baseline差分、walk-forward結果も表示します。`risk_shape_gap` にはデータセット別のDD/期待R未達値を表示します。

## 出力物

- `reports/swing_points_*.xlsx`: 山/谷一覧
- `reports/signal_score_backtest_*.xlsx`: 候補、結果、スコア帯、方向別、時間帯別、特徴量診断
- `reports/signal_score_summary_*.md`: Markdownサマリー
- `reports/deal_m1_context.xlsx`: 決済前後のM1足レポート
- `runtime/latest_signal.json`: 最新手動確認シグナル
- `runtime/trade_command.json`: dry-run command
- `runtime/latest_dry_run_audit.json`: dry-run監査
- `runtime/latest_forward_test.json`: Python側Forward Test集計
- `runtime/latest_bridge_status.json`: MT5 AI Bridge HTTP、EA POST鮮度、履歴要求pendingの診断
- `runtime/latest_bridge_recovery_plan.json`: Bridge/EA停止や履歴pendingからMT5検証へ進むための復旧計画
- `runtime/bridge_status_watch_heartbeat.json`: Bridge状態監視watcherの直近実行結果と要約
- `runtime/latest_mt5_forward_report.json`: MT5 Forward CSV集計
- `runtime/latest_mt5_optimization_report.json`: MT5 Tester OptimizationのAgent CSV/XML統合集計
- `runtime/latest_mt5_optimization_recommendation.json`: Optimization結果から見た次探索範囲と不採用理由
- `runtime/latest_mt5_strategy_tester_analysis.json`: MT5 Back/Forwardと複数Optimization結果の横断採用判定
- `runtime/latest_mt5_compile_status.json`: MT5配置済み `.mq5` / `.ex5` の鮮度とTester `.set` / `.ini` 同期チェック
- `runtime/latest_mt5_compile_run.json`: MetaEditor起動とcompile後鮮度確認の結果
- `runtime/latest_mt5_back_forward_run.json`: MT5 backtest/forward testのdry-runまたは実行計画
- `runtime/latest_mt5_tester_backtest_run.json`: MT5 Forwardなし単発backtest起動、集計の実行記録
- `runtime/latest_mt5_tester_forward_test_run.json`: MT5 Forward 1/4単発test起動、集計の実行記録
- `runtime/latest_mt5_tester_run.json`: MT5 Tester Optimization起動、集計、推薦生成の実行記録
- `runtime/latest_mt5_tester_status.json`: MT5 Testerとback/forward runnerを次に起動できるかの運用status
- `runtime/latest_mt5_next_action_run.json`: Promotion Gateから選んだ次のMT5実行計画とdry-run/実行結果
- `runtime/latest_mt5_manual_test_queue.json`: MT5画面で手動実行するBack/ForwardとBUY/SELL sample collectionの統合キュー
- `runtime/latest_mt5_manual_collect_run.json`: 統合キューからreadyな手動Strategy Tester結果だけをcollect-onlyで取り込むcollectorのdry-run/実行結果
- `runtime/latest_spec_coverage.json`: 仕様書コンポーネント、Phase完了条件、主要runtime証跡の監査結果
- `methods/swing_eval/mt5/TesterSets/Swing_Evaluation_Trader_next_optimization.set`: 推薦結果から生成した次回Optimization用set
- `runtime/latest_score_weight_search.json`: 評価関数重み探索の上位候補、baseline成績、walk-forward aggregate
- `runtime/latest_score_weight_set_168h_<side>_rr4.json`: side別評価関数候補をMT5検証用setへ変換した結果。walk-forward不合格なら `.set` は書かれず `skip_reason=walk_forward_not_passed` になる
- `runtime/latest_risk_shape_weight_search.json`: DD/期待R再fit用の重み探索証跡
- `runtime/latest_winrate_fit.json`: 勝率fitの機械判定結果
- `runtime/latest_promotion_gate.json`: live化可否判定

## live化前の条件

以下を満たすまでは実口座でlive発注しません。

- 1週間以上のM1履歴で検証済み
- 候補100件以上
- score上位帯で平均Rがプラス
- PF >= 1.2
- score閾値を上げた時に平均Rが大きく崩れていない
- Forward Testでclosed 30件以上
- 最大連敗が許容範囲内
- buy/sell片側だけに利益が偏りすぎない
- buy/sell別の平均Rが0以上
- プラス総Rのうち片側だけが85%超を占めない
- dry-run結果が最新signalと一致
- 最新signalがHOLDの場合はEA dry-run passedを昇格根拠にせず、BUY/SELLシグナルを待つ
- 日次損失停止が有効
- 連敗停止が有効
- 1回 `0.1` lot、合計 `0.3` lot上限を維持

## テスト

```bash
python3 -m py_compile methods/swing_eval/analysis/*.py src/bridge/*.py
python3 -m unittest discover -s tests
```
