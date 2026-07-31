# MT5 AI Bridge

Local bridge for saving MT5 market snapshots so Codex can read them. The default path is save-only through `/snapshot`; OpenAI/Claude signal generation is an optional `/analyze` mode and is not used for normal Codex acquisition.

Japanese README: `README.ja.md`

The default EA does not trade. It logs model output first. Turn trading on only after you have tested it on a demo account and tuned the risk limits.

## Layout

- `bridge/mt5_ai_bridge.py` - local HTTP bridge using only Python standard library.
- `bridge/request_history.py` - one-time request for a larger historical snapshot.
- `bridge/create_trade_command.py` - create a dry-run or live trade command for the EA to validate/execute.
- `bridge/sample_request.json` - test payload.
- `bridge/config.env.example` - environment variables.
- `mt5/Experts/AI_Bridge_Advisor.mq5` - MT5 Expert Advisor.
- `mt5/Experts/Swing_Evaluation_Trader.mq5` - standalone MT5 EA. No bridge, no GPT.
- `mt5/Indicators/Swing_Evaluation_Predictor.mq5` - standalone MT5 indicator overlay for prediction and dry-run order lines.
- `runtime/` - generated latest MT5 snapshot/account/history files for Codex to read.

## Normal Acquisition Policy

Use `/snapshot` for normal MT5-to-Codex acquisition. Codex should read the
files written under `runtime/`, with `runtime/latest_snapshot.json` as the
source of truth for market analysis.

Do not use `/analyze` or `runtime/latest_signal.json` as the normal acquisition
source. They are only for explicit provider-backed signal tests or bridge status
checks.

## Forward Test Watch

To keep forward-test status files refreshed for manual inspection:

```bash
python3 analysis/forward_status_watch.py \
  --signal runtime/latest_signal.json \
  --ledger runtime/forward_tests.jsonl \
  --output-json runtime/latest_forward_test_status.json \
  --output-md runtime/latest_forward_test_status.md \
  --interval-seconds 60
```

The current local watcher runs in the `tmux` session `forward_status_watch`.
Check `runtime/forward_status_watch_heartbeat.json` and
`runtime/latest_forward_test_status.md` for the latest state.

To record tradable BUY/SELL signals, evaluate open records with subsequent M1
bars, and refresh both summary and status files:

```bash
python3 analysis/forward_test_watch.py \
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

`forward_test_watch.py` skips HOLD signals and deduplicates repeated signal IDs.
`runtime/latest_forward_test.json` / `.md` includes closed/open/ignored counts, win rate, average R, PF, total R, max losing streak, max drawdown R, and expectancy R.

## Deal Context

To inspect M1 candles around closed MT5 deals:

```bash
python3 analysis/deal_context.py \
  --history runtime/latest_history_168h.json \
  --deal-history runtime/latest_deal_history.json \
  --symbol XAUUSD-m \
  --entry out \
  --before-minutes 10 \
  --after-minutes 10 \
  --output reports/deal_m1_context.xlsx
```

## Quick Start

1. Start the bridge:

```bash
python3 bridge/mt5_ai_bridge.py
```

The EA defaults to `http://127.0.0.1:8765/snapshot`, which only saves data locally. Codex then reads `runtime/` and performs judgment in this workspace.

2. In MT5:

- Copy `mt5/Experts/AI_Bridge_Advisor.mq5` into your MT5 `MQL5/Experts` folder.
- Compile it in MetaEditor.
- Enable `Tools -> Options -> Expert Advisors -> Allow WebRequest for listed URL`.
- Add `http://127.0.0.1:8765` to the allowed URLs.
- Attach the EA to one XAUUSD M1 chart. It still sends M1/M5/M15/M30 data in one snapshot.

## Standalone MT5 EA

Use this when you want MT5 to evaluate and forward-test the strategy without Analyzer, Codex, GPT, or WebRequest:

- `mt5/Experts/Swing_Evaluation_Trader.mq5`
- chart-only indicator: `mt5/Indicators/Swing_Evaluation_Predictor.mq5`
- install guide: `docs/mt5-installation-guide.md`
- report: `docs/standalone-mt5-swing-evaluation-trader-report.md`

Install:

- Copy `mt5/Experts/Swing_Evaluation_Trader.mq5` into MT5 `MQL5/Experts`.
- Compile it in MetaEditor.
- Attach it to an XAUUSD M1 chart, or run it in Strategy Tester.

Initial state is signal-only:

- `InpSignalOnly = true`
- `InpEnableTrading = false`
- `InpAllowLiveTrading = false`

Chart-only dry-run view:

- Copy `mt5/Indicators/Swing_Evaluation_Predictor.mq5` into MT5 `MQL5/Indicators`.
- Compile it in MetaEditor.
- Attach it to an XAUUSD M1 chart.
- It draws a prediction panel plus `DRY-RUN ENTRY`, `DRY-RUN SL`, and `DRY-RUN TP` horizontal lines when the score passes.
- It never sends orders, never writes trade commands, and does not use WebRequest.

Backtest and forward test in Strategy Tester:

- Symbol: `XAUUSD-m`
- Period: `M1`
- Model: `Every tick based on real ticks`
- Dates: start with `2026.06.30` to `2026.07.08`
- If the Promotion Gate reports Back/Forward sample shortage, use its `sample_shortage_recovery` command. Short date windows are expanded to `2025.01.01` to `2025.12.31` unless the current range is already at least 180 days.
- Pure backtest: set Forward to `No` and load `Swing_Evaluation_Trader_backtest.set` from Strategy Tester Inputs.
- Forward validation: set Forward to `1/4` or a custom out-of-sample period and load `Swing_Evaluation_Trader_forward_test.set`.
- Use `Swing_Evaluation_Trader_sample_collection.set` only when you need more tester samples for scoring diagnostics.
- Automated sample-collection runs are split by `--focus-side sell|buy|both` into `runtime/latest_mt5_tester_sample_collection_<side>_run.json` and `runtime/latest_mt5_sample_collection_<side>_report.json`.
- `runtime/mt5_tester_status_watch_heartbeat_current.json` records Back/Forward comparison `available`, `status`, row count, and thresholds so stale/missing comparison evidence is visible before promotion.
- For optimization, load `Swing_Evaluation_Trader_optimization.set` and enable optimization.
- For buy-entry refit diagnostics after the first buy refit fails, load `Swing_Evaluation_Trader_buy_entry_refit.set`. It is buy-only, fixed to `InpUseFittedBuyEntryFilter=true`, and searches RR 1:2-1:5 plus buy trigger quality thresholds.
- If buy-entry refit only leaves a strong 03:00-04:00 server-hour pocket, load `Swing_Evaluation_Trader_buy_hour03_validation.set`. It fixes `InpUseBuyAllowedServerHours=true` and `InpBuyAllowedServerHours=3`; keep it diagnostic until back/forward and annual validation pass.
- If hour03 alone is too thin per optimization pass, load `Swing_Evaluation_Trader_buy_strong_hours_validation.set`. It fixes `InpBuyAllowedServerHours=3,5,6,10` to retest the strongest buy hours with more samples.
- If strong buy hours still break in down/mixed regimes, load `Swing_Evaluation_Trader_buy_strong_hours_m30m15_validation.set`. It also fixes `InpUseBuyM30M15UpGate=true`.
- If annual validation rejects those buy gates but only the 300-350pt SL band remains positive, load `Swing_Evaluation_Trader_buy_wide_stop_validation.set`. It keeps the same buy hour/trend gates and forces `InpMinStopPoints=300`, `InpMaxStopPoints=350`; keep it diagnostic until back/forward and annual validation pass.
- If wide-stop diagnostics show only entry server hour 03 remains strong, load `Swing_Evaluation_Trader_buy_hour03_wide_stop_validation.set`. It combines `InpBuyAllowedServerHours=3`, `InpUseBuyM30M15UpGate=true`, and SL 300-350pt to test the hour split directly.
- If the hour03 wide-stop annual run is close but still below promotion, load `Swing_Evaluation_Trader_buy_hour03_wide_stop_calendar_validation.set`. It keeps the hour/trend gate, searches `InpUseFittedBuyCalendarFilter`, and blocks weak BUY months `6,8,10` plus weekdays `3,5`; the 2025 run worsened PF, so this remains diagnostic only.
- For sell-entry refit diagnostics, load `Swing_Evaluation_Trader_sell_entry_refit.set`. It is sell-only, fixed to `InpUseFittedSellEntryFilter=true`, and searches RR 1:2-1:5 plus the sell trigger quality thresholds.
- If sell-entry refit has no stable back/forward pass, load `Swing_Evaluation_Trader_sell_regime_entry_refit.set` to combine entry quality with trend/time filters.
- If annual diagnostics show only a specific server hour remains profitable, load `Swing_Evaluation_Trader_sell_hour12_validation.set`. It fixes `InpUseSellAllowedServerHours=true` and `InpSellAllowedServerHours=12` to validate only 12:00-13:00 sell entries before considering any hour-specific rule.
- If the hour-12 slice only works in M30/M15 down regimes, load `Swing_Evaluation_Trader_sell_hour12_m30m15_validation.set`. It also fixes `InpUseSellM30M15DownGate=true` and is diagnostic only until annual PF stays above 1.2.
- `Swing_Evaluation_Trader_sell_hour12_m30m15_calendar_validation.set` optimizes `InpUseFittedSellCalendarFilter` against weak months `3,6,12` and weekday `3` (MT5 Wednesday) while keeping the same hour and trend gates. In the 2025 run it increased stable passes but lowered aggregate PF, so it remains diagnostic only.
- For tester trades only, keep `InpSignalOnly=false`, `InpEnableTrading=true`, `InpAllowLiveTrading=true`.
- The forward-test preset keeps `InpLogSignalRows=true`, so zero-trade tests still produce signal diagnostics in `swing_evaluation_trades.csv`.
- The sample-collection preset disables `InpUseDailyLossStop` and `InpUseConsecutiveLossStop`; do not use it for demo/live readiness checks.

Reusable MT5 `/config` launcher files:

- `mt5/TesterConfigs/Swing_Evaluation_Trader_backtest.ini`
- `mt5/TesterConfigs/Swing_Evaluation_Trader_forward_test.ini`
- `mt5/TesterConfigs/Swing_Evaluation_Trader_strategy_test.ini`
- `mt5/TesterConfigs/Swing_Evaluation_Trader_sample_collection.ini`
- `mt5/TesterConfigs/Swing_Evaluation_Trader_optimization.ini`
- `mt5/TesterConfigs/Swing_Evaluation_Trader_next_optimization.ini`
- `mt5/TesterConfigs/Swing_Evaluation_Trader_buy_refit.ini`
- `mt5/TesterConfigs/Swing_Evaluation_Trader_buy_entry_refit.ini`
- `mt5/TesterConfigs/Swing_Evaluation_Trader_buy_hour03_validation.ini`
- `mt5/TesterConfigs/Swing_Evaluation_Trader_buy_strong_hours_validation.ini`
- `mt5/TesterConfigs/Swing_Evaluation_Trader_buy_strong_hours_m30m15_validation.ini`
- `mt5/TesterConfigs/Swing_Evaluation_Trader_buy_wide_stop_validation.ini`
- `mt5/TesterConfigs/Swing_Evaluation_Trader_buy_hour03_wide_stop_validation.ini`
- `mt5/TesterConfigs/Swing_Evaluation_Trader_buy_hour03_wide_stop_calendar_validation.ini`
- `mt5/TesterConfigs/Swing_Evaluation_Trader_sell_entry_refit.ini`
- `mt5/TesterConfigs/Swing_Evaluation_Trader_sell_regime_entry_refit.ini`
- `mt5/TesterConfigs/Swing_Evaluation_Trader_sell_hour12_validation.ini`
- `mt5/TesterConfigs/Swing_Evaluation_Trader_sell_hour12_m30m15_validation.ini`
- `mt5/TesterConfigs/Swing_Evaluation_Trader_sell_hour12_m30m15_calendar_validation.ini`

Prepare both the pure backtest and MT5 forward-split run:

```bash
python3 analysis/mt5_back_forward_run.py \
  --mode both \
  --timeout-seconds 3600 \
  --since-minutes 240 \
  --min-closed 30
```

`runtime/latest_mt5_back_forward_run.md` `MT5 Strategy Tester Quick Start`
shows the MT5 mode, run type, and report note for each row, so a single forward
profile is not confused with Optimization Forward XML evidence.

Launch MT5 and run them sequentially:

```bash
python3 analysis/mt5_back_forward_run.py \
  --mode both \
  --execute \
  --refresh-ready-status \
  --timeout-seconds 3600 \
  --since-minutes 240 \
  --min-closed 30
```

For a single side of the validation, create a dry-run plan for that mode first,
then execute the same mode:

```bash
python3 analysis/mt5_back_forward_run.py --mode backtest --timeout-seconds 3600 --since-minutes 240 --min-closed 30
python3 analysis/mt5_back_forward_run.py --mode backtest --execute --refresh-ready-status --timeout-seconds 3600 --since-minutes 240 --min-closed 30

python3 analysis/mt5_back_forward_run.py --mode forward --timeout-seconds 3600 --since-minutes 240 --min-closed 30
python3 analysis/mt5_back_forward_run.py --mode forward --execute --refresh-ready-status --timeout-seconds 3600 --since-minutes 240 --min-closed 30
```

When MT5 is already open, prefer the manual Strategy Tester handoff instead of
`terminal64.exe /config:` auto-launch:

```bash
python3 analysis/mt5_tester_status.py \
  --back-forward-run runtime/latest_mt5_back_forward_run.json \
  --manual-test-queue runtime/latest_mt5_manual_test_queue.json \
  --manual-queue-launch runtime/latest_mt5_manual_queue_launch.json \
  --manual-collect-run runtime/latest_mt5_manual_collect_run.json \
  --manual-test-queue-with-optimization runtime/latest_mt5_manual_test_queue_with_optimization.json \
  --manual-queue-launch-with-optimization runtime/latest_mt5_manual_queue_launch_with_optimization.json \
  --manual-collect-with-optimization runtime/latest_mt5_manual_collect_with_optimization.json \
  --manual-operator-packet-with-optimization runtime/latest_mt5_manual_operator_packet_with_optimization.json \
  --bridge-recovery-plan runtime/latest_bridge_recovery_plan.json \
  --output-json runtime/latest_mt5_tester_status.json \
  --output-md runtime/latest_mt5_tester_status.md
```

Read `runtime/latest_mt5_tester_status.md` `MT5 Operator Handoff` and
`runtime/latest_mt5_manual_test_queue.md` `Manual Execution Checklist` for the
next Backtest/Forward/sample-collection step, Inputs, Forward setting, Report
name, and collect-only command. `runtime/latest_bridge_recovery_plan.json`
`operator_summary` shows the separate Bridge action, such as restarting
`AI_Bridge_Advisor` and waiting for a fresh `POST /snapshot`. A stale Bridge
blocks live snapshot/history refreshes, but the standalone `Swing_Evaluation_Trader`
Strategy Tester path remains available unless a runner was explicitly launched
with `--require-bridge-ready`.

When you want the full MT5 queue, including Optimization Forward and annual
candidate validation, generate the optimization queue and operator packet:

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

python3 analysis/mt5_manual_operator_packet.py \
  --queue runtime/latest_mt5_manual_test_queue_with_optimization.json \
  --queue-launch-json runtime/latest_mt5_manual_queue_launch_with_optimization.json \
  --bridge-recovery-plan-json runtime/latest_bridge_recovery_plan.json \
  --strategy-analysis-json runtime/latest_mt5_strategy_tester_analysis.json \
  --output-json runtime/latest_mt5_manual_operator_packet_with_optimization.json \
  --output-md runtime/latest_mt5_manual_operator_packet_with_optimization.md
```

Use `runtime/latest_mt5_manual_operator_packet_with_optimization.md` while
operating MT5. It shows only the current Strategy Tester input, the full run
sequence, whether `/config` auto-launch is blocked by an already-running MT5
terminal, Bridge recovery state, and the collect commands to run after MT5
finishes.

The MT5 tester status watcher also copies the auto-collect operator packet into
`runtime/mt5_tester_status_watch_heartbeat_current.json`. In addition to the
next queue step and `/config` blocker, that heartbeat includes the source-time
analysis refresh command and the BUY diagnostic collect refresh command, plus
availability flags, source-time issue labels, and BUY diagnostic labels, so a
status-only check can show the next analysis step after Backtest/Forward Test.

`runtime/latest_mt5_manual_test_queue_with_optimization.md` also includes an
`MT5 Pass Budget` table. Normal Backtest/Forward/sample-collection rows show
`Passes=1`; optimization rows show the full-factorial upper bound derived from
the `.set` file. MT5 fast genetic optimization can execute fewer passes than
that upper bound.

To keep the handoff files fresh while you run Strategy Tester manually, start
the manual auto-collect watcher in detection-only mode:

```bash
python3 analysis/runtime_watchers.py --only mt5_manual_auto_collect
```

Detection-only mode does not import results. If you want completed Strategy
Tester reports to be collected automatically and then refresh Promotion Gate,
Strategy Tester Analysis, and Spec Coverage, restart that watcher with the
explicit execute-ready flag:

```bash
python3 analysis/runtime_watchers.py --only mt5_manual_auto_collect --restart --mt5-manual-auto-collect-execute-ready
```

Check an execute-ready daemon with the same flag:

```bash
python3 analysis/runtime_watchers.py --only mt5_manual_auto_collect --max-heartbeat-age-seconds 180 --mt5-manual-auto-collect-execute-ready
```

If an existing detection-only daemon is still running while execute-ready mode
is requested, `runtime_watchers.py` reports `running_heartbeat_mode_mismatch`.
Restart with the command above so the daemon heartbeat and requested mode match.

Before running Strategy Tester, verify that the MT5-installed `.mq5` files,
compiled `.ex5` binaries, and `MQL5/Profiles/Tester/*.set` / `*.ini` tester
presets match the workspace state:

```bash
python3 analysis/mt5_compile_status.py \
  --output-json runtime/latest_mt5_compile_status.json \
  --output-md runtime/latest_mt5_compile_status.md
```

`all_tester_sets_synced=false` means at least one workspace
`mt5/TesterSets/*.set` file is not the same as the MT5 profile copy.

After Strategy Tester finishes, collect the latest MT5 CSV and generate the
project report:

```bash
python3 analysis/mt5_forward_collect.py \
  --destination runtime/mt5_forward/swing_evaluation_trades.csv \
  --output-json runtime/latest_mt5_forward_report.json \
  --output-md runtime/latest_mt5_forward_report.md \
  --collect-status-json runtime/latest_mt5_forward_collect.json
```

For optimization reports that merge Agent CSV files, pass the expected Tester
date range so stale CSVs from another run are detected:

```bash
python3 analysis/mt5_tester_optimization_report.py \
  --since-minutes 0 \
  --expected-from-date 2025.01.01 \
  --expected-to-date 2025.12.31 \
  --fail-on-source-time-mismatch \
  --set-file mt5/TesterSets/Swing_Evaluation_Trader_next_optimization.set
```

`mt5_tester_run.py --from-date ... --to-date ...` forwards that range to the
child optimization report automatically. Check `source_time_diagnostics` in the
JSON or `Source time in expected range` in Markdown before trusting annual or
out-of-year results. With `--fail-on-source-time-mismatch`, the report command
exits without overwriting the output files when stale Agent CSVs are detected.
The Tester runner also skips recommendation generation when the collected CSV
range does not match the expected dates.

When launching MT5 through `mt5_tester_run.py`, add
`--archive-agent-csvs-before-run` for clean optimization evidence. The EA appends
to each Agent CSV, so this moves existing files into
`runtime/mt5_agent_csv_archive/` before the terminal starts and prevents older
date ranges from being mixed into the new run.
Use `--agent-csv-archive-run-id <id>` when you want the runner to use the same
archive directory that you previewed manually.
If a normal launch omits `--archive-agent-csvs-before-run`, the run JSON/Markdown
sets `agent_csv_archive_missing=true` and emits a warning.
When the runner archives CSVs, its run JSON/Markdown also records the archived
CSV close `server_time` first/last values and missing timestamp counts.
The run JSON/Markdown also records the terminal start time, timeout seconds,
deadline, and elapsed seconds so long optimizations have a clear maximum wait
window after they finish. If the terminal times out or returns a non-zero code,
the runner sets `terminal_failed=true` and skips fallback collection from older
Tester XML/CSV files.
If a normal launch has to use `report_paths.source=latest_pair_fallback`, the
runner sets `report_fallback_blocked=true` and skips collection/recommendation
from older XML/CSV files. Collect-only mode may still use fallback XML for
manual re-aggregation.
When the runner stops collection or recommendation generation because of a
terminal failure, normal-run fallback block, or source-time mismatch, it writes
`ok=false` blocked markers to the child optimization/recommendation outputs so
stale child reports are not mistaken for fresh evidence. If source-time
mismatch is detected after a summary was collected, the optimization child keeps
that measured summary and only the recommendation child is blocked.

To inspect the current archive targets without moving anything:

```bash
python3 analysis/mt5_agent_csv_archive.py --run-id before_next_optimization
```

Add `--execute` only when you intentionally want to move the current Agent CSVs.
Manual archive previews still default to `runtime/latest_mt5_agent_csv_archive.json`; Promotion Gate generated MT5 plans use run-id specific preview files (`runtime/latest_mt5_agent_csv_archive_<run_id>.json`) so BUY/SELL and yearly preview evidence is not overwritten.
Using the same `--run-id` for preview and `--agent-csv-archive-run-id` for
`mt5_tester_run.py` keeps the planned archive directory stable.
Add `--include-source-time` when investigating date-range contamination; the
preview then reports each Agent CSV's close `server_time` first/last values and
missing timestamp counts. Source-time mismatch gate actions use this preview.

History status check:

```bash
python3 analysis/history_status.py \
  --history runtime/latest_history_168h.json \
  --done runtime/history_request.done.json \
  --output-json runtime/latest_history_status.json \
  --output-md runtime/latest_history_status.md
```

The top-level `bars` field in `latest_history_168h.json` is a compact preview.
Use `timeframes.M1.bars` for full analysis; 168h should contain about 10080 M1
bars.

Defaults reflect the latest local optimization notes:

- `InpMinScore = 50`
- side ladder RR: buy `1:4`, sell `1:5`
- TP space checks include confirmed M5/M15 swing obstacles, not only M1 swings.
- nearby M15/M30 confirmed swing levels are treated as higher-timeframe support/resistance risk.
- lot baseline `0.1`, total cap `0.3`
- sell fitted filter enabled
- daily loss stop enabled at `5000`
- consecutive loss cooldown enabled at `20` losses for `120` minutes

After MT5 Forward testing, copy `swing_evaluation_trades.csv` from MT5 `MQL5/Files` into `runtime/mt5_forward/`, then summarize it:

```bash
python3 analysis/mt5_forward_report.py \
  --input runtime/mt5_forward/swing_evaluation_trades.csv \
  --output-json runtime/latest_mt5_forward_report.json \
  --output-md runtime/latest_mt5_forward_report.md
```

The report includes PF, win rate, net profit, max losing streak, price-based R, max drawdown price R, expectancy price R, latency seconds, hold seconds, slippage points, and spread points. It also includes signal BUY/SELL/HOLD counts, top signal/rejection reasons, cumulative score thresholds, side score diagnostics such as `candidate_gate` and `score_inversion`, and `Risk Exposure` checks for single lot, concurrent lot, concurrent positions, daily-loss-stop breaches, and consecutive-loss-stop breaches.

Include that MT5 result in the promotion gate when deciding whether to move beyond dry-run:

```bash
python3 analysis/promotion_gate.py \
  --mt5-forward-report runtime/latest_mt5_forward_report.json \
  --mt5-tester-run-report runtime/latest_mt5_tester_run.json \
  --winrate-fit-report runtime/latest_winrate_fit.json \
  --require-mt5-forward \
  --require-winrate-fit \
  --max-mt5-forward-drawdown-price-r 0 \
  --min-mt5-forward-expectancy-price-r 0
```

The gate reads `latest_mt5_tester_run.json` too. If the runner reported
`ok=false`, the gate fails `mt5_tester_run_ok`. If a normal Tester launch
reported `agent_csv_archive_missing=true`, the gate fails
`mt5_tester_run_agent_csv_archive` and sends the next action back to a run with
Agent CSV archiving enabled. The same check fails if the archive payload reports
`ok=false`, or if archived files exist but no `source_time_coverage` evidence was
recorded. If the runner reported `source_time_blocked=true`, the gate fails
`mt5_tester_run_source_time` and sends the next action back to a clean
rerun/recollect flow. If the terminal run timed out or returned a non-zero code,
the gate fails `mt5_tester_run_terminal` and sends the next action back to an
archived Tester rerun. If a normal run used a fallback XML pair instead of the
requested Report output or reported `report_fallback_blocked=true`, the gate
fails `mt5_tester_run_report_paths`.

`--max-*-drawdown-*` values are disabled when they are `0` or lower. When set, the promotion gate rejects excessive drawdown for backtest, Python forward, MT5 forward, MT5 optimization, or yearly optimization. `--min-*-expectancy-*` adds a minimum expectancy gate; failures produce a `risk_shape` next action.

Winrate fit promotion checks require both `adoption_decision.adopted=true` and enough fitted test samples plus PF in the walk-forward aggregate. If `walk_rows` shows too few fitted test trades or `mean_test_fitted_pf` is below the required PF, the gate fails `winrate_fit_walk_forward` and returns to the purge/embargo `winrate_fit.py` plan.

## Safer Operating Mode

Keep these defaults until the logs look reasonable:

- `InpBridgeUrl = http://127.0.0.1:8765/snapshot`
- `InpSaveOnlyMode = true`
- `InpRequestOnlyFromMatchingChart = true`
- `InpPollCodexTradeCommands = false`
- `InpEnableTrading = false`
- `InpMinConfidence = 0.70`
- `InpMaxSpreadPoints` set for your broker's XAUUSD symbol
- `InpMaxPositions = 1`

The EA rejects trades when:

- trading is disabled
- confidence is below the threshold
- spread is too wide
- stop loss or take profit is missing
- an existing position already matches the magic number

## Local Test

```bash
python3 bridge/mt5_ai_bridge.py
```

In another terminal:

```bash
python3 -m unittest discover -s tests
curl -s http://127.0.0.1:8765/health
curl -s -X POST http://127.0.0.1:8765/snapshot \
  -H "Content-Type: application/json" \
  --data @bridge/sample_request.json
```

## Optional `/analyze` Signal Test

Provider-backed signal generation is separate from normal Codex acquisition.
Use `/analyze` only when explicitly testing OpenAI/Claude signal generation:

OpenAI:

```bash
export AI_PROVIDER=openai
export OPENAI_API_KEY="sk-..."
export OPENAI_MODEL="gpt-5.2"
python3 bridge/mt5_ai_bridge.py
```

Claude:

```bash
export AI_PROVIDER=anthropic
export ANTHROPIC_API_KEY="sk-ant-..."
export ANTHROPIC_MODEL="claude-sonnet-4-5"
python3 bridge/mt5_ai_bridge.py
```

Then post to `/analyze`:

```bash
curl -s -X POST http://127.0.0.1:8765/analyze \
  -H "Content-Type: application/json" \
  --data @bridge/sample_request.json
```

## Reading From Codex

The bridge writes Codex-readable files every time MT5 posts to `/snapshot`. Treat
`runtime/latest_snapshot.json` as the source of truth for normal acquisition:

- `runtime/latest_snapshot.json` - latest raw MT5 market snapshot.
- `runtime/latest_signal.json` - save-only status unless `/analyze` was explicitly used.
- `runtime/latest_context.md` - concise human-readable context.
- `runtime/latest_account.json` - latest account, open positions, and recent deals when enabled in the EA.
- `runtime/latest_account.md` - readable account and trade summary.
- `runtime/events.jsonl` - snapshot/status history, one JSON object per line.

Ask Codex to read `runtime/latest_snapshot.json` first when you want a fresh
market view. Read `runtime/latest_account.json` only when positions, P/L, or
recent deals matter, and use `runtime/latest_context.md` only as a readable
summary. Do not use `/analyze` as the normal acquisition path; it is only for
optional provider-backed signal tests. This keeps MT5 capture and Codex judgment
separated. If MT5 is running on another machine or VPS, sync this project folder
or point `STATE_DIR` to a shared folder that this Codex workspace can read.

For a one-time 24-hour pull:

```bash
python3 bridge/request_history.py 24
```

Wait for the next EA post. The bridge will write:

- `runtime/latest_history_24h.json`
- `runtime/latest_history_24h_context.md`

The EA caps requested history at `InpMaxHistoryHours`, default `24`.

## Trade Commands

Default is dry-run:

```bash
python3 bridge/create_trade_command.py buy \
  --symbol XAUUSD-m --volume 0.01 --sl 4100 --tp 4120
```

The EA writes the result to:

- `runtime/latest_trade_result.json`
- `runtime/latest_trade_result.md`

Live execution additionally requires:

- EA input `InpAllowCodexTrading = true`
- CLI flags `--live --confirm LIVE`
- valid SL/TP, spread, symbol, volume, expiry, and position-count checks

## Security Notes

- Do not expose the bridge to the internet.
- Bind to `127.0.0.1` unless MT5 runs on a separate machine.
- If you use a remote/VPS setup, set `BRIDGE_TOKEN` and send it as `X-Bridge-Token`.
- Never rely on model output alone for order sizing or risk controls.
