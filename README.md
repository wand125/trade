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
classification targets, dense entry quality targets, and the coarse
`long/short/stay_flat` label.

Dense entry quality targets include `profit_barrier_hit`, `wait_regret`,
`entry_local_rank`, and `entry_urgency` for both long and short. Existing
datasets generated before this schema change must be regenerated before
training current models. Do not use `--skip-existing` when refreshing an old
dataset directory to the current schema.

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

To compare two fixed policies and separate common, removed, and newly-added
trades, use `model-trade-delta`:

```bash
python -m trade_data.backtest model-trade-delta \
  --base-runs data/reports/backtests/<raw_policy_runs_parent> \
  --candidate-runs data/reports/backtests/<candidate_policy_runs_parent> \
  --label model_trade_delta
```

This is especially important for one-position-at-a-time policies: a hard gate can
change the trade path and block later opportunities, so evaluate `only_base` and
`only_candidate` PnL rather than only counting removed trades.

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
