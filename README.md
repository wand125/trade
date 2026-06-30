# XAUUSD Data Pipeline

Python pipeline for downloading long-run XAUUSD data from HistData, converting it
to Parquet, and preparing M1/M5 datasets for short-term modelling.

HistData timestamps are Eastern Standard Time without daylight saving
adjustments. The conversion scripts normalize timestamps to UTC.

## Repository Policy

This repository tracks source code, tests, and research documentation.
Generated data and model artifacts are intentionally excluded from Git:

- `data/raw/`: downloaded HistData ZIP files
- `data/processed/`: converted Parquet files and feature/label datasets
- `data/reports/`: backtest output CSV/JSON artifacts
- `experiments/`: trained models, predictions, and experiment outputs

The directory placeholders are kept with `.gitkeep` files. Recreate generated
artifacts locally with the commands below instead of committing them.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Download M1 Bars

XAUUSD M1 data starts from 2009 on HistData. Past complete years are downloaded
as yearly ZIP files. The current partial year may be monthly.

```bash
python -m trade_data.histdata download --mode m1 --pair XAUUSD --start-year 2009
```

To dry-run without downloading:

```bash
python -m trade_data.histdata download --mode m1 --pair XAUUSD --start-year 2009 --dry-run
```

## Download Tick Data

Tick data is monthly and much larger. Start with a narrow range.

```bash
python -m trade_data.histdata download --mode tick --pair XAUUSD --start-year 2025 --end-year 2025
```

Limit the number of files during testing:

```bash
python -m trade_data.histdata download --mode tick --pair XAUUSD --start-year 2025 --max-files 1
```

## Convert To Parquet

M1 and M5:

```bash
python -m trade_data.convert m1 --pair XAUUSD --also-m5
```

Tick data:

```bash
python -m trade_data.convert tick --pair XAUUSD
```

## Validate

```bash
python -m trade_data.validate data/processed/histdata/xauusd/xauusd_m1.parquet
python -m trade_data.validate data/processed/histdata/xauusd/xauusd_m5.parquet
```

## Backtest Baselines

Run one baseline strategy for a month:

```bash
python -m trade_data.backtest run --month 2025-01 --strategy ma_cross
```

Run all baseline strategies for a month:

```bash
python -m trade_data.backtest benchmark --month 2025-01
```

Artifacts are written under:

```text
data/reports/backtests/
```

## Build Feature/Label Datasets

Build a monthly M1 dataset with leak-free features and future-24h labels:

```bash
python -m trade_data.dataset build \
  --month 2025-01 \
  --min-adjusted-edge 15 \
  --entry-timing-lookahead-minutes 60
```

Build a contiguous monthly range:

```bash
python -m trade_data.dataset build-range \
  --start-month 2024-01 \
  --end-month 2024-07 \
  --min-adjusted-edge 15 \
  --entry-timing-lookahead-minutes 60
```

Outputs are written under:

```text
data/processed/datasets/xauusd_m1/
```

The dataset includes leak-free features, continuous regression targets, quantile
classification targets, dense entry quality targets, dense exit/holding
shortening targets, and the coarse `long/short/stay_flat` label.

Dense entry quality targets include `profit_barrier_hit`, `wait_regret`,
`entry_local_rank`, and `entry_urgency` for both long and short. Dense
exit/holding targets include exit-event adjusted PnL and fixed-horizon minus
exit-event adjusted PnL / beat labels for 60, 240, and 720 minutes.
Use `--target-set holding_shortening` for focused diagnostics on only those
exit/holding shortening targets.
Existing datasets generated before these schema changes must be regenerated
before training current models. Do not use `--skip-existing` when refreshing an
old dataset directory to the current schema.

## Train Initial Models

Train the first lightweight multi-task benchmark:

```bash
python -m trade_data.modeling train \
  --train-start 2024-01 --train-end 2024-06 \
  --valid-start 2024-07 --valid-end 2024-07 \
  --test-start 2025-01 --test-end 2025-01 \
  --min-adjusted-edge 15 \
  --max-iter 80 \
  --learning-rate 0.05 \
  --entry-threshold 15
```

Train on explicit, non-contiguous months and rebalance by month/label cells:

```bash
python -m trade_data.modeling train \
  --train-months 2023-01,2023-02,2023-03,2023-04 \
  --valid-months 2024-07,2024-09,2024-11 \
  --test-months 2024-12,2025-02 \
  --min-adjusted-edge 15 \
  --sample-weighting month_label
```

Artifacts are written under:

```text
experiments/
```

Build blocked out-of-fold predictions for calibration or meta-model training:

```bash
python -m trade_data.modeling oof \
  --dataset-dir data/processed/datasets/xauusd_m1_p1_l1p2 \
  --months 2023-01,2023-02,2023-03,2023-04 \
  --fold-month-count 1 \
  --target-set policy \
  --purge-label-overlap true \
  --embargo-hours 24
```

Fit a second-stage meta EV model from saved prediction frames:

```bash
python -m trade_data.meta_model fit \
  --train-predictions experiments/20260627_192112_hgb_multitask_edge15/predictions_valid.parquet \
  --apply-predictions experiments/20260627_192112_hgb_multitask_edge15/predictions_test.parquet \
  --label meta_ev_dense_entry_quality
```

Train a selected-trade failure classifier with chronological OOF. For exit
timing diagnostics, `exit_shortening_high` marks executed trades where the
oracle hold is at least 30 minutes shorter and exit regret is at least 5:

```bash
python -m trade_data.meta_model oof-trade-failure-model \
  --validation-trades data/reports/backtests/<validation_runs>/trades.csv \
  --validation-predictions data/reports/modeling/<run>/predictions_validation_oof.parquet \
  --validation-months 2024-11,2024-12,2025-01,2025-02,2025-03 \
  --failure-targets exit_shortening_high \
  --exit-regret-threshold 5 \
  --exit-shortening-gap-minutes 30 \
  --oof-scheme expanding \
  --min-train-months 2
```

The resulting `pred_trade_failure_exit_shortening_high_<side>_prob` columns can
be tested as holding-shortening inputs; the matching `<side>_risk` columns are
available but should only be promoted after chronological policy validation.

Online context drawdown guard options for `model-policy` / `model-sweep`:

- `--context-drawdown-guard-loss-threshold`: enable realized-loss guard.
- `--context-drawdown-guard-min-entry-margin`: require stronger entry margin after breach.
- `--context-drawdown-guard-cooldown-minutes`: use a time-limited block after breach; `0` preserves hard block behavior.
- `--context-drawdown-guard-recover-after-pnl-recovery`: clear breached state after realized context PnL recovers above `-threshold`.

Diagnose online context state available before each executed trade:

```bash
python scripts/experiments/online_context_state_diagnostics.py \
  --runs data/reports/backtests/<monthly_model_policy_runs> \
  --context-columns dataset_month \
  --thresholds 20,40,60
```

Evaluate whether those online context state columns help as chronological OOF
trade-risk features before wiring them into a dynamic policy:

```bash
python scripts/experiments/online_context_feature_model.py \
  --trades data/reports/backtests/<online_context_state_run>/enriched_context_state_trades.csv \
  --output-dir data/reports/modeling \
  --label online_context_feature_model \
  --min-train-months 4
```

This is a feature diagnostic. Its risk-filter output deletes already executed
trades and does not simulate replacement trades under the one-position
constraint, so it is not a policy promotion test.

To test a low-capacity dynamic interaction between an existing side-drift guard
and online context drawdown, apply context drawdown only inside side-EV penalty
rule contexts:

```bash
python scripts/experiments/side_context_interaction_guard_apply.py \
  --runs data/reports/backtests/<side_drift_guard_runs> \
  --data data/processed/histdata/xauusd/xauusd_m1.parquet \
  --context-columns dataset_month,combined_regime \
  --match-modes any_rule,selected_side_rule \
  --thresholds 20,40,60 \
  --min-entry-margins inf,20
```

`signal_short_raw_gap` is a stricter diagnostic mode for short-side drift. It
activates the guarded context only when the final desired signal is short and
the raw short score exceeds the raw long score by `--short-gap-thresholds`:

```bash
python scripts/experiments/side_context_interaction_guard_apply.py \
  --runs data/reports/backtests/<side_drift_guard_runs> \
  --data data/processed/histdata/xauusd/xauusd_m1.parquet \
  --context-columns dataset_month,combined_regime \
  --match-modes signal_short_raw_gap \
  --short-gap-thresholds 0,5,10 \
  --thresholds 20,40,60 \
  --min-entry-margins inf,20
```

To test a monthly/regime entry-count budget on those active contexts, set
`--entry-budgets`. A finite budget constrains only active guarded contexts;
inactive rows are passed with missing budget context and remain unconstrained.
Budget `0` is allowed and means "do not enter this active context":

```bash
python scripts/experiments/side_context_interaction_guard_apply.py \
  --runs data/reports/backtests/<side_drift_guard_runs> \
  --data data/processed/histdata/xauusd/xauusd_m1.parquet \
  --context-columns dataset_month,combined_regime \
  --match-modes signal_short_raw_gap \
  --short-gap-thresholds 0,5,10 \
  --thresholds inf \
  --min-entry-margins inf \
  --entry-budgets 0,1,2,3,5,10,inf
```

Then audit whether the budget can be selected from prior months using
short-focused metrics:

```bash
python scripts/experiments/short_budget_guard_selection.py \
  --summary-by-run data/reports/backtests/<short_entry_budget_sweep>/summary_by_run.csv \
  --output-dir data/reports/backtests \
  --label short_budget_guard_selection \
  --candidate-columns short_gap_threshold,context_entry_budget \
  --min-train-months 4 \
  --recent-month-count 3
```

To test an explicit prior-only drift trigger that switches from an aggressive
short-budget candidate to defensive `budget0`, use:

```bash
python scripts/experiments/short_budget_drift_trigger_selection.py \
  --summary-by-run data/reports/backtests/<short_entry_budget_sweep>/summary_by_run.csv \
  --output-dir data/reports/backtests \
  --label short_budget_drift_trigger_selection \
  --primary-candidates 5:0,5:1,0:1 \
  --defensive-candidate 0:0 \
  --min-train-months 4 \
  --recent-month-count 3
```

Once a rule is fixed, audit it without re-searching primary candidates or
thresholds:

```bash
python scripts/experiments/short_budget_fixed_rule_audit.py \
  --summary-by-run data/reports/backtests/<short_entry_budget_sweep>/summary_by_run.csv \
  --output-dir data/reports/backtests \
  --label short_budget_fixed_rule_gap5_to_gap0_audit \
  --primary-candidate 5:0 \
  --defensive-candidate 0:0 \
  --trigger-metric recent_short_losing_months \
  --operator ge \
  --trigger-threshold 1 \
  --min-train-months 4,5,6,7,8 \
  --train-window-months 0,4,6,8 \
  --recent-month-count 3
```

To include prior-only prediction side drift metrics, add prediction month
summaries and explicitly request those trigger metrics:

```bash
python scripts/experiments/short_budget_drift_trigger_selection.py \
  --summary-by-run data/reports/backtests/<short_entry_budget_sweep>/summary_by_run.csv \
  --prediction-month-summaries data/reports/modeling/<reference>/prediction_month_summary.csv,data/reports/modeling/<fresh>/prediction_month_summary.csv \
  --output-dir data/reports/backtests \
  --label short_budget_prediction_drift_trigger_selection \
  --primary-candidates 5:0,5:1,0:1,10:0 \
  --defensive-candidate 0:0 \
  --trigger-metrics recent_pred_short_bias_mean,recent_pred_short_bias_max,recent_pred_short_share_mean,recent_actual_short_share_mean,recent_pred_match_rate_mean,recent_pred_side_score_mean \
  --min-train-months 4 \
  --recent-month-count 3
```

To use context/session side-drift alerts from `side_drift_diagnostics.py`, pass
`side_drift_alerts.csv` files and request alert metrics:

```bash
python scripts/experiments/short_budget_drift_trigger_selection.py \
  --summary-by-run data/reports/backtests/<short_entry_budget_sweep>/summary_by_run.csv \
  --side-drift-alerts data/reports/modeling/<reference>/side_drift_alerts.csv,data/reports/modeling/<fresh>/side_drift_alerts.csv \
  --output-dir data/reports/backtests \
  --label short_budget_context_alert_trigger_selection \
  --primary-candidates 5:0,5:1,0:1,10:0 \
  --defensive-candidate 0:0 \
  --trigger-metrics recent_short_side_drift_alert_count,recent_short_side_drift_alert_months,recent_short_side_drift_loss_bias_sum,recent_short_side_drift_min_pnl,recent_short_alert_and_short_losing_months \
  --min-train-months 4 \
  --recent-month-count 3
```

To apply budget or admission margin only to the prior alert contexts themselves
instead of switching the whole month, use `prior_side_drift_alert` in the
dynamic interaction backtest:

```bash
python scripts/experiments/side_context_interaction_guard_apply.py \
  --runs data/reports/backtests/<side_drift_guard_runs> \
  --data data/processed/histdata/xauusd/xauusd_m1.parquet \
  --context-columns combined_regime,session_regime \
  --match-modes prior_side_drift_alert \
  --side-drift-alerts data/reports/modeling/<reference>/side_drift_alerts.csv,data/reports/modeling/<fresh>/side_drift_alerts.csv \
  --alert-recent-month-count 3 \
  --alert-sides short \
  --thresholds inf \
  --min-entry-margins inf \
  --active-min-entry-margins=-inf,10,20 \
  --entry-budgets 0,1,inf
```

This is a diagnostic selector. It should be read as "can prior deterioration
turn on budget0 before the bad target month?", not as a free parameter search
for the best-looking rule.

Rows outside the side-drift guarded prediction context are assigned unique
inactive contexts, so ordinary trades do not share drawdown state. This is a
dynamic backtest diagnostic and should still be judged by worst month,
drawdown, and side-level PnL, not total PnL alone.

To decompose whether a guard created harmful replacement short trades, run a
candidate-only replacement audit over `model-trade-delta` output:

```bash
python scripts/experiments/short_budget_replacement_trade_audit.py \
  --delta-run global_gap5_budget0=data/reports/backtests/<gap5_trade_delta_run> \
  --delta-run global_gap0_budget0=data/reports/backtests/<gap0_trade_delta_run> \
  --output-dir data/reports/backtests \
  --label short_budget_replacement_trade_audit \
  --top-n 40
```

This reads `trade_delta_rows.csv`, filters `delta_status=only_candidate` and
`direction=short`, then writes replacement summaries by month,
regime/session, exit reason, and worst individual trades.

To check whether those replacement trades were detectable from prior context
signals, join them with side-drift alerts, prediction group summaries, and
selected-trade group summaries:

```bash
python scripts/experiments/short_budget_replacement_signal_audit.py \
  --replacement-rows data/reports/backtests/<replacement_trade_audit>/replacement_rows.csv \
  --side-drift-alerts data/reports/modeling/<reference>/side_drift_alerts.csv,data/reports/modeling/<fresh>/side_drift_alerts.csv \
  --prediction-group-summaries data/reports/modeling/<reference>/prediction_group_summary.csv,data/reports/modeling/<fresh>/prediction_group_summary.csv \
  --selected-trade-group-summaries data/reports/modeling/<reference>/selected_trade_group_summary.csv,data/reports/modeling/<fresh>/selected_trade_group_summary.csv \
  --output-dir data/reports/backtests \
  --label short_budget_replacement_signal_audit \
  --recent-month-count 3
```

This is a causal-availability diagnostic: condition summaries use only months
before the replacement trade month. Same-month alert columns are attribution
context only and should not be used to promote a live rule.

Calibrate OOF trade-failure probabilities by side/regime without refitting the
failure classifier:

```bash
python -m trade_data.meta_model oof-trade-failure-calibration \
  --validation-trades data/reports/modeling/<failure_run>/validation_oof_failure_enriched_trades.csv \
  --validation-predictions data/reports/modeling/<failure_run>/predictions_validation_oof_trade_failure_model.parquet \
  --apply-predictions data/reports/modeling/<failure_run>/predictions_apply_trade_failure_model.parquet \
  --validation-months 2024-07,2024-09,2024-11,2025-01 \
  --apply-months 2024-12 \
  --target-name large_loss \
  --group-columns volatility_regime,session_regime
```

Train a candidate-entry failure classifier from every row that passes the entry
candidate filter, rather than only from executed trades:

```bash
python -m trade_data.meta_model oof-candidate-failure-model \
  --validation-predictions data/reports/modeling/<run>/predictions_oof.parquet \
  --apply-predictions data/reports/modeling/<run>/predictions_2024_12.parquet \
  --validation-months 2024-07,2024-09,2024-11,2025-01 \
  --apply-months 2024-12 \
  --source-mode columns \
  --long-column pred_long_best_adjusted_pnl \
  --short-column pred_short_best_adjusted_pnl \
  --failure-targets large_adverse \
  --large-adverse-threshold 10 \
  --entry-threshold 12 \
  --short-entry-threshold-offset 6 \
  --side-margin 5 \
  --min-entry-rank 0.5
```

Train candidate-entry realized-PnL mean and lower-quantile models from every row
that passes the entry candidate filter. The default target is hindsight best
adjusted PnL; use `barrier_event_adjusted_pnl` when the target should respect
profit/loss barrier order and time-exit PnL. Use
`joint_exit_adjusted_pnl` when the target should blend timed barrier outcome,
fixed-horizon realized PnL, and clipped hindsight best PnL. The joint pieces
can also be trained separately with
`timed_barrier_component_adjusted_pnl`,
`fixed_horizon_component_adjusted_pnl`, or `clipped_best_adjusted_pnl` when the
scalar blend hides too much information:

```bash
python -m trade_data.meta_model oof-candidate-quality-model \
  --validation-predictions data/reports/modeling/<run>/predictions_oof.parquet \
  --apply-predictions data/reports/modeling/<run>/predictions_2024_12.parquet \
  --validation-months 2024-07,2024-09,2024-11,2025-01 \
  --apply-months 2024-12 \
  --source-mode columns \
  --long-column pred_long_best_adjusted_pnl \
  --short-column pred_short_best_adjusted_pnl \
  --target-mode joint_exit_adjusted_pnl \
  --min-adjusted-edge 15 \
  --time-exit-target-minutes 720 \
  --joint-barrier-weight 0.7 \
  --joint-fixed-horizon-weight 0.2 \
  --joint-best-weight 0.1 \
  --joint-time-decay 0.25 \
  --joint-fixed-horizon-minutes 60,240,720 \
  --prediction-prefix joint_exit \
  --lower-quantile 0.25 \
  --entry-threshold 12 \
  --short-entry-threshold-offset 6 \
  --side-margin 5 \
  --min-entry-rank 0.5
```

When multiple candidate-quality targets should coexist in one prediction
parquet, set `--prediction-prefix`. For example,
`--prediction-prefix fixed_component` writes
`pred_candidate_quality_fixed_component_long_adjusted_pnl` and matching
short/lower/risk columns instead of overwriting the default
`pred_candidate_quality_long_adjusted_pnl` columns.

Prefixed component outputs can be combined into one candidate-quality column set
before a backtest sweep:

```bash
python -m trade_data.meta_model combine-candidate-quality-components \
  --predictions data/reports/modeling/<run>/predictions_validation_oof_candidate_quality_model.parquet \
  --output-path data/reports/modeling/<run>/predictions_component_fixed_weighted.parquet \
  --component-prefixes timed_component,fixed_component,clipped_best \
  --output-prefix component_fixed_weighted \
  --mode weighted_mean \
  --weights 0.25,0.5,0.25
```

This writes `pred_candidate_quality_component_fixed_weighted_<side>_*`
columns that can be passed to `model-sweep --long-trade-quality-column` and
`--short-trade-quality-column`.

Diagnose candidate-quality OOF examples by month, side, regime, and prediction
buckets before wiring the quality score into a policy:

```bash
python -m trade_data.meta_model candidate-quality-report \
  --examples data/reports/modeling/<run>/validation_oof_candidate_quality_examples.csv \
  --output-dir data/reports/modeling \
  --label candidate_quality_downside_report \
  --downside-thresholds 0,-15 \
  --bucket-score mean \
  --bucket-count 10 \
  --bucket-group-columns dataset_month,candidate_side
```

This writes `overall_metrics.csv`, `group_metrics.csv`,
`bucket_metrics.csv`, and `summary.json`. The report is intended to catch
month/regime drift in target downside prevalence, lower-quantile coverage, and
EV overestimate before a hard gate or scalar risk penalty is tried.

Support-aware candidate-quality downside calibration columns can be added from
the OOF candidate examples:

```bash
python -m trade_data.meta_model candidate-quality-downside-calibration \
  --examples data/reports/modeling/<run>/validation_oof_candidate_quality_examples.csv \
  --predictions data/reports/modeling/<run>/predictions_validation_oof_candidate_quality_model.parquet \
  --output-path data/reports/modeling/<run>/predictions_oof_downside.parquet \
  --input-prediction-prefix fixed_component \
  --output-prefix fixed_downside \
  --group-columns combined_regime \
  --bucket-count 10 \
  --min-group-support 20 \
  --prior-strength 50 \
  --lower-z 1.0 \
  --downside-threshold 0 \
  --large-downside-threshold -15 \
  --oof-column dataset_month
```

This writes calibrated target mean/lower, downside probabilities,
overestimate-risk columns, support, source, and quality bucket for each side.
Use `--oof-column` for validation OOF scoring; omit it when fitting on all OOF
examples and applying to a fixed holdout prediction parquet. Treat these columns
as diagnostic/ranking features until a separate holdout confirms the risk
penalty, because validation-only gains have repeatedly failed on later months.

If a saved prediction parquet was produced before actual forced-exit target
columns were preserved, enrich it from the dataset files before training
barrier-event targets:

```bash
python -m trade_data.modeling enrich-predictions \
  --predictions data/reports/modeling/<run>/predictions_oof.parquet \
  --output-path data/reports/modeling/<run>/predictions_oof_forced.parquet \
  --dataset-dir data/processed/datasets/xauusd_m1_p1_l1p2_policy_combined \
  --months 2024-07,2024-09,2024-11,2025-01 \
  --horizon-hours 24 \
  --min-adjusted-edge 15 \
  --target-columns long_forced_raw_pnl,short_forced_raw_pnl,long_forced_adjusted_pnl,short_forced_adjusted_pnl,forced_side_score
```

Train a shared multi-output MLP regressor for policy regression targets:

```bash
python -m trade_data.modeling train-shared-mlp \
  --dataset-dir data/processed/datasets/xauusd_m1_p1_l1p2_policy_combined \
  --train-months 2024-07 \
  --valid-months 2024-09 \
  --test-months 2024-12 \
  --target-set policy \
  --hidden-layers 64,32 \
  --max-iter 80
```

This prototype trains regression targets only. Probability-based gates still
require HGB classifier predictions or a later shared classifier.

Build blocked OOF predictions with the shared MLP:

```bash
python -m trade_data.modeling oof-shared-mlp \
  --dataset-dir data/processed/datasets/xauusd_m1_p1_l1p2_policy_combined \
  --months 2024-07,2024-09,2024-11,2025-01 \
  --fold-month-count 1 \
  --target-set policy \
  --hidden-layers 64,32 \
  --max-iter 80
```

## Backtest Saved Model Predictions

Run an executable policy from saved model predictions:

```bash
python -m trade_data.backtest model-policy \
  --month 2025-01 \
  --predictions experiments/20260627_171852_hgb_multitask_edge15/predictions_test.parquet \
  --policy stateful_ev \
  --entry-threshold 30 \
  --exit-threshold 10 \
  --side-margin 5 \
  --profit-multiplier 1.0 \
  --loss-multiplier 1.20
```

Optionally filter model entries with dense entry quality predictions:

```bash
python -m trade_data.backtest model-policy \
  --month 2025-01 \
  --predictions experiments/20260627_192112_hgb_multitask_edge15/predictions_test.parquet \
  --policy timed_ev \
  --entry-threshold 5 \
  --side-margin 5 \
  --risk-penalty 0.1 \
  --min-entry-rank 0.5 \
  --profit-multiplier 1.0 \
  --loss-multiplier 1.20
```

Sweep policy thresholds on a validation month:

```bash
python -m trade_data.backtest model-sweep \
  --month 2024-07 \
  --predictions experiments/20260627_171852_hgb_multitask_edge15/predictions_valid.parquet \
  --entry-thresholds 5,10,15,20,25,30 \
  --exit-thresholds=-5,0,5,10 \
  --side-margins 0,5,10 \
  --profit-multiplier 1.0 \
  --loss-multiplier 1.20
```

When `timed_ev` uses MLP holding columns such as
`pred_mlp_long_exit_event_minutes` and `pred_mlp_short_exit_event_minutes`,
omitting `--min-valid-predicted-hold-minutes` applies the standard 30 minute
fail-close guard. Use `--min-valid-predicted-hold-minutes -inf` only when
intentionally reproducing the historical clip-only behavior. Non-MLP holding
columns keep the historical `-inf` default unless a threshold is supplied.

Regime-conditioned side EV penalties can be swept with rule sets. These rules
subtract EV from the matching side before side selection, instead of hard
blocking a trade:

```bash
python -m trade_data.backtest model-sweep \
  --month 2024-07 \
  --predictions data/reports/modeling/<run>/predictions_oof.parquet \
  --policies timed_ev \
  --entry-thresholds 10,15 \
  --side-ev-penalty-rule-sets "none;long:session_regime=ny_late:5;long:session_regime=ny_late:15"
```

Aggregate multiple validation sweeps by identical policy parameters:

```bash
python -m trade_data.backtest model-sweep-summary \
  --sweeps data/reports/backtests/fold_a/metrics.csv,data/reports/backtests/fold_b/metrics.csv \
  --min-folds 2 \
  --min-trades-per-fold 30 \
  --max-forced-exit-rate 0.0 \
  --max-drawdown 100 \
  --min-adjusted-pnl-per-fold 0 \
  --sort-by mean_pnl
```

Use the summary command to choose entry/exit thresholds from validation folds
only. The final test month should receive the selected policy unchanged.

For candidate selection, keep the historical PnL ranking by default. When a
candidate is close to the best validation min PnL, `near_top_risk` can rank only
that near-top set by risk proxies instead of blindly taking the highest PnL:

```bash
python -m trade_data.backtest model-candidate-selection \
  --base-sweeps data/reports/backtests/fold_a/metrics.csv,data/reports/backtests/fold_b/metrics.csv \
  --cost-sweeps data/reports/backtests/fold_a_cost/metrics.csv,data/reports/backtests/fold_b_cost/metrics.csv \
  --min-folds 2 \
  --min-trades-per-fold 30 \
  --max-forced-exit-rate 0.05 \
  --max-drawdown 200 \
  --min-cost-adjusted-pnl-per-fold 0 \
  --candidate-rank-mode near_top_risk \
  --near-top-cost-pnl-tolerance 5
```

This mode is a tie-breaker for validation-close candidates; it is not evidence
by itself. If only one risk metric changes the selected candidate, treat that as
a sensitivity diagnostic rather than a promotion rule.

For fold-to-fold robustness diagnostics, `near_top_risk` and `stress_score` also
accept `--near-top-pnl-stability-weight`. This penalizes the max base/cost
standard deviation of fold adjusted PnL. Keep the default `0` unless using it as
a pre-registered sensitivity check.

After saving a candidate-selection run, run a leave-one-fold-out check from the
saved `config.json` without repeating the long option list:

```bash
python -m trade_data.backtest model-candidate-selection-jackknife \
  --selection-config data/reports/backtests/<selection_run>/config.json
```

This reselects candidates with one validation fold removed, then evaluates the
selected candidate on the removed fold. Treat it as a robustness diagnostic, not
as a substitute for unseen holdout months.

After fixed `model-policy` runs exist, inspect selected-trade exposure by month,
side, and regime directly from each run's `config.json` and `trades.csv`:

```bash
python -m trade_data.backtest model-trade-exposure \
  --runs data/reports/backtests/<model_policy_runs_parent> \
  --label model_trade_exposure
```

This writes `enriched_trades.csv` and `group_by_*` summaries. Use it for failure
localization and robustness diagnostics; do not promote post-hoc session/regime
blocks without a fresh pre-registered holdout.

To inspect why selected trades failed across exit timing, EV overestimate, side
gap, and profit-barrier interactions, run:

```bash
python -m trade_data.backtest model-trade-exposure-diagnostics \
  --runs data/reports/backtests/<model_policy_runs_parent> \
  --label model_trade_exposure_diagnostics
```

This writes `diagnostic_trades.csv` plus `group_by_context_*` and
`group_by_diagnostic_combo.csv`. It is intended for failure localization and
feature/target design, not for post-hoc hard blocking.

To profile selected-trade context risk without using the target month itself,
use the walk-forward selected-trade stress diagnostic:

```bash
python -m trade_data.backtest model-trade-context-walkforward-stress \
  --runs data/reports/backtests/<model_policy_runs_parent> \
  --group-columns direction,combined_regime \
  --min-validation-support 20 \
  --min-holdout-support 10 \
  --label model_trade_context_walkforward_stress
```

For each target month, this uses only earlier selected trades: the immediately
prior month(s) become a pseudo-holdout profile, and older months become the
pseudo-validation profile. It writes `selected_trades.csv`,
`walkforward_selected_trades.csv`, `walkforward_profile_drift.csv`,
`walkforward_month_summary.csv`, `walkforward_context_outcomes.csv`, and
`summary.json`. In addition to validation-positive / holdout-negative stress
columns, the selected-trade rows include all-prior context columns such as
`walkforward_prior_context_target_mean`,
`walkforward_prior_context_loss_flag`, and
`target_walkforward_prior_context_mean_floor`. Use these to diagnose recurring
common-trade losses and to build future-info-safe downside/context targets; do
not convert a single target-month failure into a hard block.

To compare two fixed policies and separate common, removed, and newly-added
trades, use `model-trade-delta`:

```bash
python -m trade_data.backtest model-trade-delta \
  --base-runs data/reports/backtests/<raw_policy_runs_parent> \
  --candidate-runs data/reports/backtests/<candidate_policy_runs_parent> \
  --label model_trade_delta
```

When parent directories contain multiple `model-policy` runs, the command pairs
base and candidate runs by the internal `backtest_config.evaluation_start`
month in each `config.json`. Duplicate or mismatched months fail fast instead of
silently comparing the wrong runs.

This is especially important for one-position-at-a-time policies: a hard gate can
change the trade path and block later opportunities, so evaluate `only_base` and
`only_candidate` PnL rather than only counting removed trades.
The command also writes `blocking_pairs.csv` and
`group_by_blocking_candidate_*` summaries, which estimate the base-policy
opportunities blocked while a candidate-policy trade was open.
`stateful_candidate_examples.csv` is a candidate-quality-style training frame
with `target`, `stateful_entry_value`, `stateful_positive_cost_value`,
`blocking_cost`, and `replacement_regret` columns.

To grid fixed `max_predicted_hold_minutes` values across one or more prediction
parquet files while keeping post-month predictions available for legal 24h exits,
use:

```bash
python scripts/experiments/holding_max_grid.py \
  --base-config data/reports/backtests/<baseline_run>/config.json \
  --prediction-paths data/reports/modeling/<validation_run>/predictions_validation_oof.parquet,data/reports/modeling/<apply_run>/predictions_apply.parquet \
  --months 2025-01,2025-02,2025-03 \
  --max-holds 240,260,480 \
  --label holding_max_grid
```

The script writes `policy_summary.csv`, `policy_summary_by_variant.csv`,
`prediction_coverage.csv`, and `manifest.json` to both modeling and backtest
artifact directories. Duplicate `decision_timestamp` values fail fast. Inspect
`prediction_coverage.csv` before interpreting monthly comparisons, and use
`--require-post-coverage` for fresh apply windows where positions can exit after
`evaluation_end`.

For holding-cap context diagnostics, build a prior-only context profile from
no-context cap deltas before turning a session/regime observation into a rule:

```bash
python scripts/experiments/holding_cap_context_walkforward.py \
  --delta-runs data/reports/backtests/<no_context_delta_risk0>,data/reports/backtests/<no_context_delta_risk5> \
  --focus-side short \
  --focus-regime range_low_vol \
  --label holding_cap_context_wf
```

The script writes `direct_cap_target_examples.csv`,
`walkforward_month_summary.csv`, `walkforward_selected_contexts.csv`, and
`walkforward_aggregate.csv`. To apply the selected contexts to the holding
overlay without using the target month's outcome, pass that CSV to
`holding_risk_overlay.py`:

```bash
python scripts/experiments/holding_risk_overlay.py \
  --exclude-combined-session-pairs-by-month data/reports/backtests/<context_wf_run>/walkforward_selected_contexts.csv \
  --exclude-month-context-selection-scope pooled \
  --exclude-month-context-scope pooled
```

To split selected-trade holding mistakes into "should have exited earlier" and
"should have held longer" targets, use:

```bash
python scripts/experiments/holding_error_target_diagnostics.py \
  --trade-rows data/reports/backtests/<trade_delta_run> \
  --pnl-source candidate \
  --case-label risk5 \
  --label holding_error_target_diagnostics
```

The script writes `holding_error_trade_rows.csv`, grouped summaries, and
`walkforward_context_profiles.csv`. Treat `exit_shortening_target`
(`oracle_holding_gap_minutes <= -30` and `exit_regret >= 5`) as the first risk
target candidate. `hold_extension_target` often includes profitable missed
upside, so do not turn it into a hard block without separate validation.

Before adopting a candidate, combine validation and holdout/apply delta runs in
a preflight audit:

```bash
python -m trade_data.backtest model-trade-delta-preflight \
  --validation-deltas data/reports/backtests/<validation_delta_run_a>,data/reports/backtests/<validation_delta_run_b> \
  --holdout-deltas data/reports/backtests/<holdout_delta_run_a>,data/reports/backtests/<holdout_delta_run_b> \
  --label model_trade_delta_preflight
```

The command writes `case_metrics.csv`, `failed_cases.csv`, `summary.json`,
`group_drift_status_direction_combined_regime.csv`, and
`stateful_group_drift_status_direction_combined_regime.csv`.
By default, every holdout case must have non-negative total PnL delta,
non-negative worst-month PnL delta, and non-negative worst-month stateful target.
Use this as a candidate rejection check; validation-only wins are not enough for
promotion. The group drift files show which status/direction/regime groups were
positive in validation but negative in holdout.

To compare repeated flip groups across multiple preflight audits, use:

```bash
python -m trade_data.backtest model-trade-delta-drift-stability \
  --preflight-runs data/reports/backtests/<preflight_run_a>,data/reports/backtests/<preflight_run_b> \
  --label model_trade_delta_drift_stability
```

This writes `flip_stability_pnl.csv`, `flip_stability_stateful.csv`, and
their `*_monthly_support*.csv` files plus `summary.json`. When the preflight
runs include available-context drift files, it also writes
`flip_stability_available_pnl*.csv` and
`flip_stability_available_stateful*.csv`, which drop `delta_status` and group
only by decision-time context such as direction and combined regime. Treat
repeated flips as drift/downside feature candidates first, not as immediate
hard-block rules.

Train a month-held-out stateful value model directly from those examples and
optionally score validation/apply prediction parquet files:

```bash
python -m trade_data.meta_model oof-stateful-value-model \
  --examples data/reports/backtests/<delta_run>/stateful_candidate_examples.csv \
  --validation-predictions data/reports/modeling/<run>/predictions_validation_oof_candidate_quality_model.parquet \
  --validation-months 2024-07,2024-09,2024-11,2025-01 \
  --target-column stateful_entry_value \
  --prediction-prefix stateful_entry \
  --source-mode columns \
  --long-column pred_long_best_adjusted_pnl \
  --short-column pred_short_best_adjusted_pnl
```

To audit those examples across validation and holdout splits before turning a
context into a feature or rule, use:

```bash
python -m trade_data.backtest stateful-examples-drift \
  --validation-examples data/reports/backtests/<validation_delta_run_a>,data/reports/backtests/<validation_delta_run_b> \
  --holdout-examples data/reports/backtests/<holdout_delta_run_a>,data/reports/backtests/<holdout_delta_run_b> \
  --group-columns candidate_side,combined_regime
```

This writes `combined_stateful_examples.csv`, `split_group_metrics.csv`,
`month_group_metrics.csv`, `group_drift.csv`, and `summary.json`. The combined
examples are also annotated with `context_stress_flag`,
`context_stress_penalty`, `target_context_stress_adjusted`, and
`target_context_holdout_mean_floor`; when flagged rows exist,
`context_stressed_examples.csv` is written as a focused audit file. Use these
columns to check whether a decision-time context is stable or flips under
holdout/stress before adding it to a model. Because the stress columns are
computed from the validation-vs-holdout comparison, they are audit targets by
default; for training, recompute the same idea from prior walk-forward folds
only.

To create leak-controlled walk-forward stress targets from all available
stateful examples, use:

```bash
python -m trade_data.backtest stateful-examples-walkforward-stress \
  --examples data/reports/backtests/<delta_run_a>,data/reports/backtests/<delta_run_b> \
  --group-columns candidate_side,combined_regime \
  --min-validation-support 20 \
  --min-holdout-support 10
```

For each target month, this uses only earlier months: the immediately prior
month(s) become a pseudo-holdout profile, and older months become the
pseudo-validation profile. It writes `walkforward_stateful_examples.csv`,
`walkforward_profile_drift.csv`, `walkforward_month_summary.csv`, and
`summary.json`. Use `target_walkforward_context_stress_adjusted` as a candidate
OOF target. Use `target_walkforward_prior_context_mean_floor` when the risk is
not a validation-to-holdout flip but a persistently weak prior context. Keep the
validation-vs-holdout `target_context_stress_adjusted` column as an audit-only
target.

To turn walk-forward stress/floor targets into side-specific stateful downside
risk columns, use the stateful risk model. Prefer chronological OOF when judging
whether a signal generalizes:

```bash
python -m trade_data.meta_model oof-stateful-risk-model \
  --examples data/reports/backtests/<walkforward_examples>/walkforward_stateful_examples.csv \
  --validation-predictions data/reports/modeling/<run>/predictions_validation_oof.parquet \
  --validation-months 2024-07,2024-09,2024-11,2024-12,2025-01,2025-02,2025-03,2025-04 \
  --risk-targets walkforward_floor_lowered \
  --prediction-prefix wf_exp_session_mm \
  --oof-scheme expanding \
  --min-train-months 2 \
  --probability-calibration mean_match
```

Use `walkforward_prior_floor_lowered` or
`walkforward_prior_floor_nonpositive` to train on
`target_walkforward_prior_context_mean_floor` instead of the immediate
validation/holdout floor. The prior-floor targets are intended for contexts
that are weak across all earlier months, while `walkforward_floor_lowered`
remains the sharper validation-to-holdout degradation target.

`--probability-calibration mean_match` shifts the predicted logits so each
scored fold's mean probability matches the fitted target prevalence. It
preserves ranking within the fold, but it does not use future holdout
prevalence and should still be validated with fresh months before any policy
promotion.

To audit whether an online context drawdown guard threshold can be selected
without looking at the target month, run the prior-only threshold selector on a
`context_drawdown_guard_apply.py` `summary_by_run.csv`:

```bash
python scripts/experiments/context_drawdown_guard_selection.py \
  --summary-by-run data/reports/backtests/<context_drawdown_apply>/summary_by_run.csv \
  --output-dir data/reports/backtests \
  --label context_drawdown_guard_selection \
  --candidate-columns context_drawdown_guard_loss_threshold \
  --min-train-months 8 \
  --objectives total,worst,risk_adjusted,risk_budget \
  --worst-weights 1,2,4 \
  --drawdown-weights 0,0.5 \
  --min-validation-worst-month-pnls=-inf,-150,-120
```

Use the `worst` objective only as a pre-registered risk-control mandate, not as
a profit-maximizing selector. Report ordering, latest-report detection, and
renumbering in `docs/reports/` are based on the internal creation-time `日時:`
line, not filesystem mtime or the edit-history `更新日時:` line.

For a two-dimensional candidate such as drawdown threshold plus post-breach
entry margin, include both numeric columns:

```bash
python scripts/experiments/context_drawdown_guard_selection.py \
  --summary-by-run data/reports/backtests/<context_drawdown_apply>/summary_by_run.csv \
  --candidate-columns context_drawdown_guard_loss_threshold,context_drawdown_guard_min_entry_margin
```

## Rebuild Generated Artifacts

From a fresh clone, the normal regeneration flow is:

```bash
python -m trade_data.histdata download --mode m1 --pair XAUUSD --start-year 2009
python -m trade_data.histdata download --mode tick --pair XAUUSD --start-year 2025 --end-year 2025 --max-files 1
python -m trade_data.convert m1 --pair XAUUSD --also-m5
python -m trade_data.convert tick --pair XAUUSD
python -m trade_data.validate data/processed/histdata/xauusd/xauusd_m1.parquet
python -m trade_data.dataset build-range \
  --start-month 2023-01 \
  --end-month 2025-12 \
  --min-adjusted-edge 15 \
  --entry-timing-lookahead-minutes 60
```

Then train and evaluate a walk-forward fold:

```bash
python -m trade_data.modeling train \
  --train-start 2023-01 --train-end 2024-12 \
  --valid-start 2025-01 --valid-end 2025-01 \
  --test-start 2025-02 --test-end 2025-02 \
  --min-adjusted-edge 15

python -m trade_data.backtest model-sweep \
  --month 2025-01 \
  --predictions experiments/<run>/predictions_valid.parquet \
  --policies stateful_ev,stateless_ev,timed_ev \
  --entry-thresholds 5,10,15,20,25,30,40,50 \
  --exit-thresholds=-5,0,5,10,15 \
  --side-margins 0,5,10,20 \
  --risk-penalties 0,0.1,0.2,0.4,0.6 \
  --min-trades 30 \
  --max-forced-exit-rate 0.5 \
  --max-drawdown 100 \
  --long-column pred_calibrated_long_best_adjusted_pnl \
  --short-column pred_calibrated_short_best_adjusted_pnl \
  --profit-multiplier 1.0 \
  --loss-multiplier 1.20
```

## Research Docs

Research goal and documentation workflow:

- `GOAL.md`
- `docs/README.md`
- `docs/status.md`
- `docs/research_log.md`
