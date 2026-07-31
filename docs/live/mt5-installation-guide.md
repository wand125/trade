# MT5導入手順

## 導入するもの

用途ごとに3つを分ける。

| 用途 | ファイル | MT5配置先 | 発注 |
|---|---|---|---|
| 予測表示だけ | `mt5/Indicators/Swing_Evaluation_Predictor.mq5` | `MQL5/Indicators` | しない |
| MT5単体Forward/Strategy Tester | `mt5/Experts/Swing_Evaluation_Trader.mq5` | `MQL5/Experts` | 初期状態ではしない |
| Bridgeでruntime取得 | `mt5/Experts/AI_Bridge_Advisor.mq5` | `MQL5/Experts` | 初期状態ではしない |

まず使うのは `Swing_Evaluation_Predictor.mq5`。これはチャートに予測パネルと `DRY-RUN ENTRY` / `DRY-RUN SL` / `DRY-RUN TP` を表示するだけで、発注コードを持たない。

## 今回の配置済みパス

このMacのMetaTrader 5環境には配置済み。

```text
/Users/HHosono/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5/MQL5/Indicators/Swing_Evaluation_Predictor.mq5
/Users/HHosono/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5/MQL5/Experts/Swing_Evaluation_Trader.mq5
```

元ファイル:

```text
mt5/Indicators/Swing_Evaluation_Predictor.mq5
mt5/Experts/Swing_Evaluation_Trader.mq5
```

## MetaEditorでCompile

1. MT5を開く。
2. `Tools -> MetaQuotes Language Editor` でMetaEditorを開く。
3. Navigatorで `Indicators/Swing_Evaluation_Predictor.mq5` を開く。
4. `Compile` を実行する。
5. `Experts/Swing_Evaluation_Trader.mq5` も同じくCompileする。

Compile後に `.ex5` が生成される。

## 予測インジケータの使い方

1. MT5のNavigatorを更新する。
2. `Indicators -> Swing_Evaluation_Predictor` をXAUUSD M1チャートへ適用する。
3. チャート左0%、縦80%付近のBoxパネルを見る。
4. 条件通過時は水平線が出る。

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

これは手動判断用。発注は行わない。

## MT5単体EAの使い方

`Swing_Evaluation_Trader.mq5` はStrategy Tester/Forward Test用。

初期値は安全側:

```text
InpSignalOnly = true
InpEnableTrading = false
InpAllowLiveTrading = false
InpRequireStrategyTester = false
```

チャートへ適用しても、この3つのままなら発注しない。まずはsignal-onlyで表示とログだけ確認する。

Strategy Testerで実際に約定ログを取りたい場合だけ、テスター上で以下にする。

```text
InpSignalOnly = false
InpEnableTrading = true
InpAllowLiveTrading = true
InpRequireStrategyTester = true
```

Tester/Forward用 `.set` では、誤操作防止のため `InpRequireStrategyTester = true`、`InpChartButtonDryRunOnly = true`、`InpAllowChartButtonTrading = false` のままにする。これにより、Tester用setを通常チャートに誤ってLoadしても自動発注は拒否される。

MT5上で手動Backtest/Forward Testを回す時は、先に `runtime/latest_mt5_tester_status.md` の `MT5 Operator Handoff` -> `MT5 Quick Input` を確認する。そこに表示されるExpert、Symbol、Period、Model、From/To、Forward、Optimization、Inputs、ReportをStrategy Testerへそのまま入れる。Backtest/Forwardの2本を続けて確認する場合は、`runtime/latest_mt5_manual_operator_packet_with_optimization.md` の `Back/Forward Quick Start` -> `Back/Forward MT5 Inputs`、または `runtime/latest_mt5_tester_status.json` の `mt5_back_forward_quick_start_quick_inputs` を見る。複数stepを順に回す場合は `runtime/latest_mt5_manual_test_queue.md` の `MT5 Quick Input` と `Manual Execution Checklist` を使う。

チャート上の手動Entryボタンは補助機能。EA側の基本確認は自動売買ロジックをStrategy Tester/Forward Testで回す。

- `ENTRY BUY` / `ENTRY SELL` / `WAIT` ボタンを任意で表示できる。
- 既定では `InpShowChartEntryButton = false` のため、ボタンは出ない。
- 表示した場合も、既定では `InpChartButtonDryRunOnly = true`、`InpAllowChartButtonTrading = false` のため、押しても発注せずCSVへbuttonログだけ残す。
- ボタンだけで操作する場合は `InpManualButtonOnly = true` にする。
- 通常チャートで実発注する最終段階では `InpRequireStrategyTester = false` に戻す。
- 実発注には `InpSignalOnly = false`、`InpEnableTrading = true`、`InpAllowLiveTrading = true`、`InpRequireStrategyTester = false`、`InpChartButtonDryRunOnly = false`、`InpAllowChartButtonTrading = true` がすべて必要。

推奨Tester設定:

```text
Expert: Swing_Evaluation_Trader
Symbol: XAUUSD-m
Period: M1
Model: Every tick based on real ticks
Backtest: Forwardなし
Forward Test: Forward 1/4 またはCustom
Lot: 0.10
Max total lot: 0.30
```

InputsのLoadで以下を使える。

```text
Swing_Evaluation_Trader_backtest.set
Swing_Evaluation_Trader_forward_test.set
Swing_Evaluation_Trader_sample_collection.set
Swing_Evaluation_Trader_optimization.set
Swing_Evaluation_Trader_sell_entry_refit.set
Swing_Evaluation_Trader_sell_regime_entry_refit.set
```

プロジェクト内の元ファイル:

```text
mt5/TesterSets/Swing_Evaluation_Trader_backtest.set
mt5/TesterSets/Swing_Evaluation_Trader_forward_test.set
mt5/TesterSets/Swing_Evaluation_Trader_sample_collection.set
mt5/TesterSets/Swing_Evaluation_Trader_optimization.set
mt5/TesterSets/Swing_Evaluation_Trader_next_optimization.set
mt5/TesterSets/Swing_Evaluation_Trader_stable_candidate_next.set
mt5/TesterSets/Swing_Evaluation_Trader_buy_refit.set
mt5/TesterSets/Swing_Evaluation_Trader_buy_entry_refit.set
mt5/TesterSets/Swing_Evaluation_Trader_buy_hour03_validation.set
mt5/TesterSets/Swing_Evaluation_Trader_buy_strong_hours_validation.set
mt5/TesterSets/Swing_Evaluation_Trader_buy_strong_hours_m30m15_validation.set
mt5/TesterSets/Swing_Evaluation_Trader_buy_wide_stop_validation.set
mt5/TesterSets/Swing_Evaluation_Trader_buy_hour03_wide_stop_validation.set
mt5/TesterSets/Swing_Evaluation_Trader_buy_hour03_wide_stop_calendar_validation.set
mt5/TesterSets/Swing_Evaluation_Trader_sell_entry_refit.set
mt5/TesterSets/Swing_Evaluation_Trader_sell_regime_entry_refit.set
mt5/TesterSets/Swing_Evaluation_Trader_sell_hour12_validation.set
mt5/TesterSets/Swing_Evaluation_Trader_sell_hour12_m30m15_validation.set
mt5/TesterSets/Swing_Evaluation_Trader_sell_hour12_m30m15_calendar_validation.set
```

このMacではMT5側にも配置済み。

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

## Strategy Testerでテストする

まずはMT5の画面から手動で回す。

1. MetaEditorで `Experts/Swing_Evaluation_Trader.mq5` をCompileする。
2. MT5で `View -> Strategy Tester` を開く。
3. Expertに `Swing_Evaluation_Trader` を選ぶ。
4. Symbolは `XAUUSD-m`、Periodは `M1` にする。
5. Modelは `Every tick based on real ticks` にする。
6. Datesはまず `2026.06.30` から `2026.07.08` にする。
7. 純バックテストならForwardは使わない。Forward検証なら `1/4` にする。
8. Inputsで、純バックテストなら `Swing_Evaluation_Trader_backtest.set`、Forward検証なら `Swing_Evaluation_Trader_forward_test.set` をLoadする。
9. Startで実行する。

トレード件数を集めて評価関数だけを診断したい場合は `Swing_Evaluation_Trader_sample_collection.set` をLoadする。このsetは `InpUseDailyLossStop=false`、`InpUseConsecutiveLossStop=false` で、連敗による早期停止を避ける。デモForward判定や実運用寄りの安全確認には使わず、純バックテストは `backtest.set`、Forward検証は `forward_test.set` に戻す。自動Runnerからは `--focus-side sell|buy|both` ごとに `runtime/latest_mt5_tester_sample_collection_<side>_run.json` と `runtime/latest_mt5_sample_collection_<side>_report.json` へ保存し、BUY/SELLの診断証跡を混ぜない。

約定ログを取るため、`backtest.set` と `forward_test.set` は以下を有効にしている。

```text
InpSignalOnly = false
InpEnableTrading = true
InpAllowLiveTrading = true
InpRequireStrategyTester = true
InpWriteCsvLog = true
InpLogSignalRows = true
```

これはStrategy Tester検証用。通常チャートへ載せる時は初期値のsignal-onlyに戻す。デモForwardで自動売買まで確認する最終段階だけ、`InpRequireStrategyTester = false` を明示してから実行する。
`InpLogSignalRows = true` により、トレードが0件でも `swing_evaluation_trades.csv` にsignal行が残る。HOLD理由、BUY/SELL候補数、scoreを集計して、発注なしの原因を確認する。

## 現在の手動Back/Forwardキューを使う

MT5を開いたまま検証する場合は、毎回まず現在のハンドオフを見る。

```bash
python3 analysis/mt5_tester_status.py \
  --back-forward-run runtime/latest_mt5_back_forward_run.json \
  --manual-test-queue runtime/latest_mt5_manual_test_queue.json \
  --manual-queue-launch runtime/latest_mt5_manual_queue_launch.json \
  --manual-collect-run runtime/latest_mt5_manual_collect_run.json \
  --bridge-recovery-plan runtime/latest_bridge_recovery_plan.json \
  --output-json runtime/latest_mt5_tester_status.json \
  --output-md runtime/latest_mt5_tester_status.md
```

見る場所:

- `runtime/latest_mt5_tester_status.md` の `MT5 Operator Handoff`
- `runtime/latest_mt5_manual_test_queue.md` の `Manual Execution Checklist`
- Bridge復旧が必要な時は `runtime/latest_bridge_recovery_plan.md` の `Bridge Recovery Operation Cards` と、JSONの `operator_summary` を見る

`Next MT5 step` に表示された順に、Strategy TesterへExpert、Symbol、Period、Model、Dates、Forward、Inputs、Report名を設定してStartする。Back/Forwardの標準順序は以下。

自動監視や別ツールから読む場合は `runtime/latest_mt5_manual_test_queue.json` の `operator_handoff` を見る。`state`、`next_mt5_step`、`ready_entry_ids`、`waiting_entry_ids`、collect dry-run/executeコマンドが1か所にまとまっている。
同じJSONの `operation_cards` には `is_next`、`action`、目的、queue/step、Forward、Inputs、Report、collect statusが入る。Markdownを開かずに次のMT5操作だけ読む場合は `is_next=true` のカードを見る。status watcher heartbeatにも `manual_test_queue_operation_cards` として転記され、古いwatcherが出していない場合は再起動対象になる。
`runtime/latest_mt5_manual_queue_launch.json` / `.md` も同じhandoff要約を持つ。`selected_matches_queue_handoff=true` なら、ランチャーが選んだstepとキュー推奨stepが一致している。このlaunch handoffはstatus watcher heartbeatの必須snapshot keyでもあるため、古いwatcherが出していない場合は再起動対象になる。
`runtime/latest_promotion_gate.md` の `MT5 Manual Queue From Watcher` にも同じhandoffが表示されるため、Promotion Gateだけを見ても次のMT5 Strategy Tester stepと実行後のcollectコマンドを確認できる。
Bridge復旧側の `operator_summary` には、`next_operation_action`、対象EA、手動手順、確認条件、確認コマンド、直近EA POST経過秒、履歴request/done IDがまとまる。`status=needs_ea_restart` の時は履歴要求を再送せず、`AI_Bridge_Advisor` をライブ `XAUUSD-m` チャートへ付け直し、freshな `POST /snapshot` と履歴done ID一致を待つ。

`runtime/latest_mt5_manual_test_queue.md` と `runtime/latest_mt5_manual_test_queue_with_optimization.md` の `MT5 Pass Budget` には、stepごとのpass規模が出る。通常のBacktest/Forward/sample collectionは `full-factorial passes = 1`、Optimizationが有効なstepは `.set` の最適化入力から計算した全探索上限が出る。Fast genetic algorithmを使うstepでは、表示値は上限であり、MT5が実際に回すpass数は少なくなる場合がある。

| order | purpose | Forward | Inputs | Report |
|---:|---|---|---|---|
| 1 | Backtest | Disabled | `Swing_Evaluation_Trader_backtest.set` | `Tester\Swing_Evaluation_Trader_backtest` |
| 2 | Forward Test | 1/4 | `Swing_Evaluation_Trader_forward_test.set` | `Tester\Swing_Evaluation_Trader_forward_test` |

MT5が起動中の時は、`terminal64.exe /config:` が既存プロセスへ吸われてStrategy Testerが走らないことがある。そのため `mt5_manual_queue_launch.py` は既定で `running_terminal_blocks_direct_config` として止める。MT5を閉じてから自動起動したい場合だけ、dry-runで選択stepを確認してから `--execute` を付ける。

```bash
python3 analysis/mt5_manual_queue_launch.py \
  --queue runtime/latest_mt5_manual_test_queue.json \
  --output-json runtime/latest_mt5_manual_queue_launch.json \
  --output-md runtime/latest_mt5_manual_queue_launch.md
```

MT5上で各stepを実行した後は、まずcollect dry-runでReportとAgent CSVが揃ったか確認する。

```bash
python3 analysis/mt5_manual_collect.py \
  --queue runtime/latest_mt5_manual_test_queue.json \
  --output-json runtime/latest_mt5_manual_collect_run.json \
  --output-md runtime/latest_mt5_manual_collect_run.md
```

`selected_count > 0` になったら、readyなentryだけを取り込む。

```bash
python3 analysis/mt5_manual_collect.py \
  --queue runtime/latest_mt5_manual_test_queue.json \
  --execute \
  --output-json runtime/latest_mt5_manual_collect_run.json \
  --output-md runtime/latest_mt5_manual_collect_run.md
```

MT5上でBacktest/Forward/BUY/SELL sampleを回した後に採用可否まで一気に更新する場合は、こちらを標準にする。collect成功後にPromotion Gate、Strategy Tester Analysis、Spec Coverageを順に再生成する。

```bash
python3 analysis/mt5_manual_collect.py \
  --queue runtime/latest_mt5_manual_test_queue.json \
  --execute \
  --refresh-post-collect-analysis \
  --output-json runtime/latest_mt5_manual_collect_run.json \
  --output-md runtime/latest_mt5_manual_collect_run.md
```

最適化込みキューを回した後は、queueと出力先を最適化用に変える。

BUY候補不足も同時にMT5で診断する場合は、最適化込みキューを以下で作る。`buy_wide_stop_short` は短期wide-stop診断、`buy_hour03_wide_stop_2025` と `buy_hour03_wide_stop_calendar_2025` は2025年通期のForward 1/4診断としてStrategy Testerに並ぶ。これは採用設定ではなく、`runtime/latest_mt5_strategy_tester_analysis.md` の `BUY Candidate Gap Plan` を埋めるための診断キュー。

```bash
python3 analysis/mt5_manual_test_queue.py \
  --include-optimization-configs \
  --include-static-candidate-label sell_hour12_m30m15_2025 \
  --include-static-candidate-label sell_hour12_m30m15_calendar_2025 \
  --include-static-candidate-label buy_wide_stop_short \
  --include-static-candidate-label buy_hour03_wide_stop_2025 \
  --include-static-candidate-label buy_hour03_wide_stop_calendar_2025 \
  --output-json runtime/latest_mt5_manual_test_queue_with_optimization.json \
  --output-md runtime/latest_mt5_manual_test_queue_with_optimization.md
```

長いqueue markdownではなくMT5作業用の短い指示書だけを見る場合:

```bash
python3 analysis/mt5_manual_operator_packet.py \
  --queue runtime/latest_mt5_manual_test_queue_with_optimization.json \
  --queue-launch-json runtime/latest_mt5_manual_queue_launch_with_optimization.json \
  --bridge-recovery-plan-json runtime/latest_bridge_recovery_plan.json \
  --strategy-analysis-json runtime/latest_mt5_strategy_tester_analysis.json \
  --output-json runtime/latest_mt5_manual_operator_packet_with_optimization.json \
  --output-md runtime/latest_mt5_manual_operator_packet_with_optimization.md
```

このpacketの `Bridge Recovery` は、Bridge EA POST停止、履歴pending、Bridge検証コマンドを同じ画面に表示する。`Strategy Evidence` はBack/Forward証跡、source-time刷新計画、source-time分析再生成、BUY診断キュー、BUY診断collectコマンドを短く表示する。`Standalone Strategy Tester allowed=True` の時は、Bridge復旧は別作業として扱い、MT5上のBacktest/Forward Testは続行できる。

MT5でStrategy Testerを実行した後は、auto collect watcherでready検知だけを行える。`--execute-ready` を付けない限りcollectは実行しない。watcherは同時に `runtime/latest_mt5_manual_queue_launch_with_optimization.md` と `runtime/latest_mt5_manual_operator_packet_with_optimization.md` も再生成し、次のStrategy Tester入力、`/config` 自動起動可否、Bridge復旧状態、Strategy Evidence、source-time/BUY診断の回収入口を短いpacketとして更新する。Launch Statusが `manual_input_required` の時はMT5端末が起動中なので、packetのMT5 Inputを手動でStrategy Testerへ入力する。
watcherのJSON/Markdown/heartbeatには `Collect dry-run command` と `Collect execute command` も出る。ready検知後は、そのexecuteコマンドで同じ条件のcollect-onlyと `--refresh-post-collect-analysis` を再実行できる。
`--max-runs 1` の1回実行は、既定では常駐監視用のheartbeat/PIDを上書きしない。これはBridge、MT5 tester status、forward test/status、manual auto collect watcherで共通。共有heartbeat/PIDを使う常駐監視は `runtime_watchers.py --only <watcher>` から起動する。診断用に1回実行のheartbeatを残す時だけ `--heartbeat` と必要に応じて `--pid-file` / `--skip-pid-file-write` を明示する。

```bash
python3 analysis/mt5_manual_auto_collect_watch.py \
  --queue runtime/latest_mt5_manual_test_queue_with_optimization.json \
  --collect-output-json runtime/latest_mt5_manual_collect_with_optimization.json \
  --collect-output-md runtime/latest_mt5_manual_collect_with_optimization.md \
  --bridge-recovery-plan-json runtime/latest_bridge_recovery_plan.json \
  --strategy-analysis-json runtime/latest_mt5_strategy_tester_analysis.json \
  --output-json runtime/latest_mt5_manual_auto_collect_watch.json \
  --output-md runtime/latest_mt5_manual_auto_collect_watch.md \
  --max-runs 1
```

readyなcollect-onlyを自動実行し、Promotion Gate、Strategy Tester Analysis、Spec Coverageまで更新する場合:

```bash
python3 analysis/mt5_manual_auto_collect_watch.py \
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

ready検知だけを常駐させる場合:

```bash
python3 analysis/runtime_watchers.py --only mt5_manual_auto_collect
```

ready検知後にcollectと分析更新まで自動で進める現在の運用では、常駐監視の確認にも同じモード指定を付ける。これを付けずに確認すると、監視自体は動いていても `execute_ready_mode_mismatch` と表示される。

```bash
python3 analysis/runtime_watchers.py \
  --only mt5_manual_auto_collect \
  --interval-seconds 60 \
  --max-heartbeat-age-seconds 180 \
  --mt5-manual-auto-collect-execute-ready
```

再起動する場合:

```bash
python3 analysis/runtime_watchers.py \
  --only mt5_manual_auto_collect \
  --interval-seconds 60 \
  --restart \
  --max-heartbeat-age-seconds 180 \
  --mt5-manual-auto-collect-execute-ready
```

```bash
python3 analysis/mt5_manual_collect.py \
  --queue runtime/latest_mt5_manual_test_queue_with_optimization.json \
  --execute \
  --refresh-post-collect-analysis \
  --output-json runtime/latest_mt5_manual_collect_with_optimization.json \
  --output-md runtime/latest_mt5_manual_collect_with_optimization.md
```

Bridge EAのsnapshot/history POSTが止まっていても、`Swing_Evaluation_Trader` のStrategy Tester単体実行は続行できる。Bridge復旧は履歴更新、live snapshot、GPT/Bridge経由のruntime更新に必要な別作業として扱う。Bridge readyをTester前提にしたい診断時だけ、Runnerへ `--require-bridge-ready` を明示する。

最適化する場合:

1. Inputsで `Swing_Evaluation_Trader_optimization.set` をLoadする。
2. Optimizationを有効にする。
3. Optimization criterionはEAの `OnTester()` を使う。
4. Startで実行する。
5. 良い結果が出ても、Forward区間、buy/sell別、score帯別の結果を確認するまでは採用しない。

BUYの初回refitでPF/Forwardが残らない場合は `Swing_Evaluation_Trader_buy_entry_refit.set` を使う。これはBUY only、RR 1:2-1:5、`InpUseFittedBuyEntryFilter=true` 固定で、`InpBuyRequireBreakConfirm`、`InpBuyMinM1ClosePosition`、`InpBuyMinM1BodyAtr`、`InpBuyMinM5CloseSlowAtr` を探索する診断用セット。BUY側の反発確認ロジックをSELL側とは分けて検証する。

BUY entry refitでも全体が崩れ、03:00-04:00サーバー時間だけが残る場合は `Swing_Evaluation_Trader_buy_hour03_validation.set` を使う。これはBUY only、`InpUseBuyAllowedServerHours=true`、`InpBuyAllowedServerHours=3` 固定で、BUYの時間帯依存が本当にback/forwardで残るかを見る診断用セット。

hour03単独ではpassごとの取引数が薄い場合は `Swing_Evaluation_Trader_buy_strong_hours_validation.set` を使う。これはBUY only、`InpUseBuyAllowedServerHours=true`、`InpBuyAllowedServerHours=3,5,6,10` 固定で、強いBUY時間帯をまとめてサンプルを増やす診断用セット。

強いBUY時間帯でも下落/混合レジームで崩れる場合は `Swing_Evaluation_Trader_buy_strong_hours_m30m15_validation.set` を使う。これはBUY only、`InpUseBuyM30M15UpGate=true`、`InpUseBuyAllowedServerHours=true`、`InpBuyAllowedServerHours=3,5,6,10` 固定で、M30/M15が両方upの時だけBUYを検証する診断用セット。

BUY強時間帯 + M30/M15 upが年次で崩れ、SL 300-350ptだけが残る場合は `Swing_Evaluation_Trader_buy_wide_stop_validation.set` を使う。これはBUY only、同じ時間帯/上位足ゲートを固定し、`InpMinStopPoints=300`、`InpMaxStopPoints=350` で広めSLだけを検証する診断用セット。back/forwardと年次が通るまでは採用しない。

wide-stop診断でもentry 03:00-04:00だけが強い場合は `Swing_Evaluation_Trader_buy_hour03_wide_stop_validation.set` を使う。これはBUY only、`InpBuyAllowedServerHours=3`、`InpUseBuyM30M15UpGate=true`、SL 300-350ptを同時に固定し、時間帯分割でback/forwardが残るかを見る診断用セット。

hour03 wide-stopの年次検証がPF 1.1593で昇格閾値に届かず、6月/8月/10月や水曜/金曜で崩れる場合は `Swing_Evaluation_Trader_buy_hour03_wide_stop_calendar_validation.set` を使う。これは同じhour03/M30-M15 up条件を維持し、`InpUseFittedBuyCalendarFilter` のON/OFFを432 passで確認する診断用セット。2025年通期ではPF 1.1215へ悪化したため、採用せず診断止まり。弱いBUY月は `6,8,10`、曜日はMT5 `day_of_week` の `3,5`。

SELLのentry品質だけを再fitする場合は `Swing_Evaluation_Trader_sell_entry_refit.set` を使う。これはSELL only、RR 1:2-1:5、SL 250-350pt、`InpUseFittedSellEntryFilter=true` 固定で、`InpSellRequireBreakConfirm`、`InpSellMaxM1ClosePosition`、`InpSellMinM1BodyAtr`、`InpSellMaxM5CloseSlowAtr` を主に探索する診断用セット。

entry品質だけでback/forward安定passが出ない場合は `Swing_Evaluation_Trader_sell_regime_entry_refit.set` を使う。これはSELL only、RR 1:3-1:5、SL 250-300pt、entry filter ON固定に加えて `InpUseFittedSellTrendFilter` と `InpUseFittedSellTimeFilter` を同時に探索する診断用セット。

年次集計で特定サーバー時間だけが残るかを見る場合は `Swing_Evaluation_Trader_sell_hour12_validation.set` を使う。これは `InpUseSellAllowedServerHours=true`、`InpSellAllowedServerHours=12` 固定で、12:00-13:00のSELLだけを対象にRR、MinScore、entry条件、trend filterを再探索する診断用セット。hour12の中でもM30/M15 downだけを残す次段階診断は `Swing_Evaluation_Trader_sell_hour12_m30m15_validation.set` を使う。2025年検証ではSELL単体でPF 1.3786まで改善したが、BUY側と弱い月/曜日の検証が残るためライブ設定としては使わない。`Swing_Evaluation_Trader_sell_hour12_m30m15_calendar_validation.set` で3月/6月/12月と水曜を減点する `InpUseFittedSellCalendarFilter` のON/OFFも確認したが、年間aggregateはPF 1.3667へ低下したため診断止まり。曜日はMT5の `day_of_week` で、水曜は `3`。

MT5の `/config` 起動で自動テストしたい場合は、以下の起動設定を使える。

```text
mt5/TesterConfigs/Swing_Evaluation_Trader_backtest.ini
mt5/TesterConfigs/Swing_Evaluation_Trader_forward_test.ini
mt5/TesterConfigs/Swing_Evaluation_Trader_strategy_test.ini
mt5/TesterConfigs/Swing_Evaluation_Trader_sample_collection.ini
mt5/TesterConfigs/Swing_Evaluation_Trader_optimization.ini
mt5/TesterConfigs/Swing_Evaluation_Trader_next_optimization.ini
mt5/TesterConfigs/Swing_Evaluation_Trader_stable_candidate.ini
mt5/TesterConfigs/Swing_Evaluation_Trader_buy_refit.ini
mt5/TesterConfigs/Swing_Evaluation_Trader_buy_entry_refit.ini
mt5/TesterConfigs/Swing_Evaluation_Trader_buy_hour03_validation.ini
mt5/TesterConfigs/Swing_Evaluation_Trader_buy_strong_hours_validation.ini
mt5/TesterConfigs/Swing_Evaluation_Trader_buy_strong_hours_m30m15_validation.ini
mt5/TesterConfigs/Swing_Evaluation_Trader_buy_wide_stop_validation.ini
mt5/TesterConfigs/Swing_Evaluation_Trader_buy_hour03_wide_stop_validation.ini
mt5/TesterConfigs/Swing_Evaluation_Trader_buy_hour03_wide_stop_calendar_validation.ini
mt5/TesterConfigs/Swing_Evaluation_Trader_sell_entry_refit.ini
mt5/TesterConfigs/Swing_Evaluation_Trader_sell_regime_entry_refit.ini
mt5/TesterConfigs/Swing_Evaluation_Trader_sell_hour12_validation.ini
mt5/TesterConfigs/Swing_Evaluation_Trader_sell_hour12_m30m15_validation.ini
mt5/TesterConfigs/Swing_Evaluation_Trader_sell_hour12_m30m15_calendar_validation.ini
```

`backtest.ini` は `Swing_Evaluation_Trader_backtest.set` を使うForwardなしの単発バックテスト、`forward_test.ini` は `Swing_Evaluation_Trader_forward_test.set` を使うForward 1/4の単発検証、`strategy_test.ini` は従来互換のForward 1/4単発テスト。`sample_collection.ini` は連敗停止で早期終了させずにサンプルを集める診断用、`optimization.ini` はgenetic optimization用、`next_optimization.ini` は推薦結果から生成したfocused optimization用、`buy_refit.ini` はBUY初回refit用、`buy_entry_refit.ini` はBUY entry品質の再fit用、`buy_hour03_validation.ini` はBUYの03:00-04:00切り出し検証用、`buy_strong_hours_validation.ini` はBUYの03/05/06/10時台まとめ検証用、`buy_strong_hours_m30m15_validation.ini` は強時間帯かつM30/M15 up固定の検証用、`buy_wide_stop_validation.ini` は同条件でSL 300-350ptだけを検証する診断用、`buy_hour03_wide_stop_validation.ini` はentry 03時かつSL 300-350ptだけを検証する診断用、`buy_hour03_wide_stop_calendar_validation.ini` はhour03/wide-stopに弱い月/曜日のcalendar filterを加える診断用、`sell_entry_refit.ini` はSELL entry品質の再fit用、`sell_regime_entry_refit.ini` はentry品質とtrend/time regimeの複合refit用、`sell_hour12_validation.ini` は年次で強かった12時台SELLだけの切り出し検証用、`sell_hour12_m30m15_validation.ini` は12時台かつM30/M15 down固定の次段階検証用、`sell_hour12_m30m15_calendar_validation.ini` は弱い月/曜日を減点する次段階検証用。いずれも `XAUUSD-m`、`M1`、real ticks、期間 `2026.06.30` から `2026.07.08` を初期値にしている。

backtest/forwardの2本をまとめて準備するdry-run:

```bash
python3 analysis/mt5_back_forward_run.py \
  --mode both \
  --timeout-seconds 3600 \
  --since-minutes 240 \
  --min-closed 30
```

手動Strategy Tester前に残存Agent CSVの期間だけ確認する場合:

```bash
python3 analysis/mt5_back_forward_run.py \
  --mode both \
  --run-archive-preview \
  --timeout-seconds 3600 \
  --since-minutes 240 \
  --min-closed 30
```

これはMT5を起動せず、Back/Forward各stepのarchive preview JSON/Markdownにsource timeを残す。

Promotion Gateが出した次のMT5 Tester計画を手動Strategy Testerで走らせる前に、同じく残存Agent CSVの期間だけ確認する場合:

```bash
python3 analysis/mt5_next_action_run.py \
  --promotion-gate runtime/latest_promotion_gate.json \
  --run-archive-preview \
  --output-json runtime/latest_mt5_next_action_run.json \
  --output-md runtime/latest_mt5_next_action_run.md
```

通常のdry-runは計画作成だけだが、`--run-archive-preview` を付けるとMT5 primaryを起動せずarchive previewだけを実行し、`latest_mt5_next_action_run.md` の `Post Execution Validation` で古いCSV混入やpreview失敗を確認できる。

実際にMT5を起動して順に回す場合:

```bash
python3 analysis/mt5_back_forward_run.py \
  --mode both \
  --execute \
  --refresh-ready-status \
  --timeout-seconds 3600 \
  --since-minutes 240 \
  --min-closed 30
```

MT5画面でBacktest/Forwardを手動実行した後、既存Tester出力だけをRunner証跡へ取り込む場合:

```bash
python3 analysis/mt5_back_forward_run.py \
  --mode both \
  --collect-only \
  --csv-modified-after "2026.07.13 17:30" \
  --timeout-seconds 3600 \
  --since-minutes 240 \
  --min-closed 30
```

`--collect-only` はMT5を起動せず、Back/Forward各stepへ `mt5_tester_run.py --collect-only` を実行する。JSON/Markdownには `collect_only=true`、`launch_mt5=false` が残り、両方のReport JSONが揃えば `Backtest Vs Forward Drift` と `evidence_state` が更新される。手動実行時刻が分かる場合は `--csv-modified-after` を付けて、古いAgent CSVを混ぜない。

`--execute` は `runtime/latest_mt5_tester_status.json` を事前確認し、compile鮮度、起動中terminal、直近dry-run計画と選択mode、config、`ExpertParameters` `.set`、ForwardMode、base From/To、report名、予定出力先、`--timeout-seconds`、`--since-minutes`、`--min-closed`、`--from-date`、`--to-date`、主要実行フラグの一致を満たす場合だけMT5を起動する。dry-runとexecuteでは上のように同じ `--timeout-seconds`、`--since-minutes`、`--min-closed` を指定する。`--run-archive-preview` 付きdry-runでは、MT5起動前と同じarchive previewを実行し、古いAgent CSVを混ぜる危険がないかを確認できる。`--refresh-ready-status` を付けると、MT5起動前にpreflight用statusを再生成する。dry-run時点でBack/Forward各stepのset名、ForwardMode、timeoutを順次足した最大待ち時間と、今開始した場合の期限を `latest_mt5_back_forward_run.md` とstatusに表示する。実行後は各stepの `run_json` / `report_json` を検証し、Tester runが成功して期待レポートが存在する場合だけ全体OKにする。ブロック理由やartifact不備は `runtime/latest_mt5_back_forward_run.md` の `Ready Status` / `Post execution validation` に残る。検証目的でこのガードを外す場合は `--skip-ready-status-check` を明示する。

期間やtimeoutを変えたdry-runを作った場合は、`runtime/latest_mt5_tester_status.md` の Back/Forward Runner 欄に出る `Execute hint` を使う。dry-runの `--from-date` / `--to-date` / `--timeout-seconds` などを引き継いだコマンドになり、同じ欄で合計timeoutと期限も確認できる。

個別に回す場合は、対象modeでdry-runを作ってからexecuteする。

```bash
python3 analysis/mt5_back_forward_run.py --mode backtest --timeout-seconds 3600 --since-minutes 240 --min-closed 30
python3 analysis/mt5_back_forward_run.py --mode backtest --execute --refresh-ready-status --timeout-seconds 3600 --since-minutes 240 --min-closed 30

python3 analysis/mt5_back_forward_run.py --mode forward --timeout-seconds 3600 --since-minutes 240 --min-closed 30
python3 analysis/mt5_back_forward_run.py --mode forward --execute --refresh-ready-status --timeout-seconds 3600 --since-minutes 240 --min-closed 30
```

## Forward結果の集計

MT5の `MQL5/Files/swing_evaluation_trades.csv` をこのプロジェクトへコピーする。

```text
runtime/mt5_forward/swing_evaluation_trades.csv
```

最新CSVを自動で探してコピーし、そのまま集計する場合:

```bash
python3 analysis/mt5_forward_collect.py \
  --destination runtime/mt5_forward/swing_evaluation_trades.csv \
  --output-json runtime/latest_mt5_forward_report.json \
  --output-md runtime/latest_mt5_forward_report.md \
  --collect-status-json runtime/latest_mt5_forward_collect.json \
  --min-closed 30 \
  --min-pf 1.2 \
  --max-losing-streak 20
```

少数で止まった場合は、Markdown/JSONのreject診断を見る。`consecutive loss cooldown active 20 >= 20` は `InpConsecutiveLossLimit=20` による120分クールダウンで、ドライランではない。サンプル不足の切り分けは `sample_collection.set` で再実行する。

集計Markdownの `Signal Diagnostics` では、signalのBUY/SELL/HOLD数、平均score、主なHOLD/reject理由を確認できる。

手動でCSVを置いた場合の集計:

集計:

```bash
python3 analysis/mt5_forward_report.py \
  --input runtime/mt5_forward/swing_evaluation_trades.csv \
  --min-closed 30 \
  --min-pf 1.2 \
  --max-losing-streak 20 \
  --output-json runtime/latest_mt5_forward_report.json \
  --output-md runtime/latest_mt5_forward_report.md
```

昇格判定:

```bash
python3 analysis/promotion_gate.py \
  --mt5-forward-report runtime/latest_mt5_forward_report.json \
  --winrate-fit-report runtime/latest_winrate_fit.json \
  --require-mt5-forward \
  --require-winrate-fit
```

## Bridge EAを使う場合

MT5から `runtime/latest_snapshot.json` などを保存したい場合だけ `AI_Bridge_Advisor.mq5` を使う。

1. Python bridgeを起動する。

```bash
python3 bridge/mt5_ai_bridge.py
```

2. MT5で `Tools -> Options -> Expert Advisors` を開く。
3. `Allow WebRequest for listed URL` を有効にする。
4. `http://127.0.0.1:8765` を追加する。
5. `AI_Bridge_Advisor` をXAUUSD M1チャートへ適用する。

通常取得は `/snapshot` のsave-only。`/analyze` は明示的なprovider-backed signal test以外では使わない。

## live化前の禁止事項

以下を満たすまでは実口座でlive発注しない。

- MT5 Strategy TesterのForwardでclosed 30件以上
- PF >= 1.2
- 最大連敗が許容範囲内
- buy/sell別に片側だけ大きく崩れていない
- dry-run結果が最新signalと一致している
- 日次損失停止が有効
- 連敗停止が有効
- 1回 `0.1` lot、合計 `0.3` lot上限を維持

実口座化は、デモForwardで十分なclosedサンプルが出てからにする。
