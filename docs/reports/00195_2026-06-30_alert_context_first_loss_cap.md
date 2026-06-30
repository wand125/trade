# Alert Context First Loss Cap

日時: 2026-06-30 10:07 JST
更新日時: 2026-06-30 10:07 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00194の次ステップとして、prior side-drift alert context内だけに current-month realized loss fast stop を掛けた。
- 既存の `context_drawdown_guard_loss_threshold` を `prior_side_drift_alert` contextへ限定して使う。`0` はbacktestで禁止されているため、near first-loss capとして `0.01` を試した。
- Clean gridは `threshold=0.01,1,5,10,20,40,60,inf`、`context_drawdown_guard_min_entry_margin=inf`、`context_entry_budget=inf`。
- 全12ヶ月では `threshold=5` がbestで total `-71.8598`。baseline `-90.1378` よりは小改善だが、00194のalert-context `budget0` `+6.0170` に届かない。
- prior-only selectionは明確に失敗。min4は target 8ヶ月 total `-396.3152`、min8は target 4ヶ月 total `-609.1884`。
- 結論: alert context内のfirst-loss/fast-stopは標準採用しない。late 2025の損失はalert context内の繰り返し損失だけでなく、非alert short exposureとreplacement pathに残る。

## Artifacts

- Clean sweep: `data/reports/backtests/20260630_010642_short_alert_context_first_loss_cap_clean_recent3/`
- Clean prior-only selection min4: `data/reports/backtests/short_alert_context_first_loss_clean_selection_min4/`
- Clean prior-only selection min8: `data/reports/backtests/short_alert_context_first_loss_clean_selection_min8/`

Exploratory duplicate grid:

- `data/reports/backtests/20260630_010401_short_alert_context_first_loss_cap_recent3/`
- `data/reports/backtests/short_alert_context_first_loss_selection_min4/`
- `data/reports/backtests/short_alert_context_first_loss_selection_min8/`

Inputs:

- Baseline runs: `data/reports/backtests/20260629_140836_side_drift_guard_admission_margin_isolated_2025_01_12_coststress_260/coststress_side_guard_p10_replm10`
- Data: `data/processed/histdata/xauusd/xauusd_m1.parquet`
- Alert files:
  - `data/reports/modeling/20260629_133501_side_drift_reference_2025_01_08_coststress_260/side_drift_alerts.csv`
  - `data/reports/modeling/20260629_133440_side_drift_fresh_2025_09_12_coststress_260/side_drift_alerts.csv`

## Method

Command shape:

```bash
python3 scripts/experiments/side_context_interaction_guard_apply.py \
  --runs data/reports/backtests/20260629_140836_side_drift_guard_admission_margin_isolated_2025_01_12_coststress_260/coststress_side_guard_p10_replm10 \
  --data data/processed/histdata/xauusd/xauusd_m1.parquet \
  --output-dir data/reports/backtests \
  --label short_alert_context_first_loss_cap_clean_recent3 \
  --context-columns combined_regime,session_regime \
  --match-modes prior_side_drift_alert \
  --side-drift-alerts data/reports/modeling/20260629_133501_side_drift_reference_2025_01_08_coststress_260/side_drift_alerts.csv,data/reports/modeling/20260629_133440_side_drift_fresh_2025_09_12_coststress_260/side_drift_alerts.csv \
  --alert-recent-month-count 3 \
  --alert-sides short \
  --thresholds 0.01,1,5,10,20,40,60,inf \
  --min-entry-margins inf \
  --recover-after-pnl-recovery-values false \
  --active-min-entry-margins=-inf \
  --entry-budgets inf \
  --warmup-days 7 \
  --post-days 4
```

Selection used:

```bash
python3 scripts/experiments/context_drawdown_guard_selection.py \
  --summary-by-run data/reports/backtests/20260630_010642_short_alert_context_first_loss_cap_clean_recent3/summary_by_run.csv \
  --output-dir data/reports/backtests \
  --label short_alert_context_first_loss_clean_selection_min4 \
  --candidate-columns context_drawdown_guard_loss_threshold \
  --min-train-months 4 \
  --objectives total,worst,risk_adjusted,risk_budget \
  --worst-weights 1,2,4 \
  --drawdown-weights 0,0.5 \
  --min-validation-worst-month-pnls=-inf,-150,-120
```

`min8` は `--min-train-months 8` のみ変更。

## Results

### All-window shape

| threshold | trades | total PnL | worst month | max DD | short PnL | active trades | active trade PnL |
|---:|---:|---:|---:|---:|---:|---:|---:|
| `5` | `923` | `-71.8598` | `-286.9232` | `286.9232` | `-416.1158` | `117` | `-102.5788` |
| `inf` | `949` | `-90.1378` | `-289.0056` | `289.0056` | `-434.3938` | `211` | `-218.5658` |
| `10` | `927` | `-90.9188` | `-286.9232` | `286.9232` | `-435.1748` | `134` | `-164.6188` |
| `20` | `935` | `-94.3600` | `-289.2208` | `289.2208` | `-438.6160` | `172` | `-210.2556` |
| `60` | `949` | `-99.4538` | `-289.0056` | `289.0056` | `-443.7098` | `209` | `-218.0778` |
| `40` | `949` | `-104.5872` | `-289.0056` | `289.0056` | `-448.8432` | `201` | `-205.2554` |
| `0.01` | `907` | `-155.3242` | `-286.9232` | `286.9232` | `-499.5802` | `78` | `-151.5282` |
| `1` | `910` | `-155.7718` | `-286.9232` | `286.9232` | `-500.0278` | `82` | `-159.9558` |

Tighter near-first-loss thresholds cut active trades most aggressively, but worsen total and short PnL. This indicates that some alert-context trades are still profitable, and removing them lets worse replacement exposure appear.

### Monthly shape for threshold 5

| month | total PnL | short PnL | active trade PnL | max DD |
|---|---:|---:|---:|---:|
| 2025-01 | `+101.4088` | `+30.8668` | `0.0000` | `56.3844` |
| 2025-02 | `+75.0192` | `+44.4944` | `0.0000` | `66.8408` |
| 2025-03 | `+22.5032` | `-51.0276` | `+3.7472` | `83.3284` |
| 2025-04 | `+96.0090` | `+3.8400` | `+59.1420` | `163.7916` |
| 2025-05 | `+46.8080` | `+92.8150` | `-21.8412` | `65.8240` |
| 2025-06 | `+235.4576` | `+107.0646` | `+27.4140` | `39.1298` |
| 2025-07 | `+47.2574` | `+43.7126` | `-26.3462` | `131.3490` |
| 2025-08 | `-87.1346` | `-65.0862` | `-15.5352` | `109.9094` |
| 2025-09 | `-286.9232` | `-273.9512` | `-34.6860` | `286.9232` |
| 2025-10 | `-25.4220` | `-35.4420` | `-14.6014` | `122.3370` |
| 2025-11 | `-121.8452` | `-144.3842` | `-49.2240` | `132.5992` |
| 2025-12 | `-174.9980` | `-169.0180` | `-30.6480` | `174.9980` |

2025-09のworst month is essentially unchanged. The remaining loss is not only repeated losses inside prior alert contexts.

### Prior-only selection

min_train_months=4:

| selection family | target months | selected thresholds | trades | total PnL | worst month | max DD | short PnL |
|---|---:|---|---:|---:|---:|---:|---:|
| all objectives | `8` | `5,20` | `545` | `-396.3152` | `-286.9232` | `286.9232` | `-473.8046` |

Representative month choices:

| target month | selected threshold | total PnL | short PnL |
|---|---:|---:|---:|
| 2025-05 | `5` | `+46.8080` | `+92.8150` |
| 2025-06 | `5` | `+235.4576` | `+107.0646` |
| 2025-07 | `5` | `+47.2574` | `+43.7126` |
| 2025-08 | `20` | `-116.6498` | `-94.6014` |
| 2025-09 | `5` | `-286.9232` | `-273.9512` |
| 2025-10 | `5` | `-25.4220` | `-35.4420` |
| 2025-11 | `5` | `-121.8452` | `-144.3842` |
| 2025-12 | `5` | `-174.9980` | `-169.0180` |

min_train_months=8:

| selection family | target months | selected thresholds | trades | total PnL | worst month | max DD | short PnL |
|---|---:|---|---:|---:|---:|---:|---:|
| all objectives | `4` | `5` | `158` | `-609.1884` | `-286.9232` | `286.9232` | `-622.7954` |

## Interpretation

- The all-window improvement from `-90.1378` to `-71.8598` is too small and does not change the core failure.
- The near-first-loss setting `0.01` is worse than a looser `5`, so "block immediately after any loss" is too aggressive.
- Prior-only selection overfits the early alert-context behavior and still selects `5` into the late short regime.
- Compared with 00194, alert-context `budget0` is stronger (`+6.0170`) because it removes all active alert-context entries rather than waiting for a realized loss.
- But even `budget0` was not enough to beat global `gap0/budget0` / 00191. Therefore the missing exposure is outside this alert-context subset.

## Decision

- Do not promote alert-context first-loss cap / fast-stop to standard policy.
- Keep `prior_side_drift_alert` + context drawdown composition as a diagnostic pattern.
- The next useful move is not another alert-context-only rule. Focus on:
  - non-alert short exposure after alert suppression,
  - global `gap0/budget0` fixed/fresh verification,
  - replacement-path diagnostics after `budget0`,
  - rebuilding alerts from the exact p10 + margin10 candidate family only if needed for attribution.

## Verification

- `python3 scripts/experiments/side_context_interaction_guard_apply.py ... --label short_alert_context_first_loss_cap_clean_recent3`: OK
- `python3 scripts/experiments/context_drawdown_guard_selection.py ... --label short_alert_context_first_loss_clean_selection_min4`: OK
- `python3 scripts/experiments/context_drawdown_guard_selection.py ... --label short_alert_context_first_loss_clean_selection_min8`: OK
- `python3 -m unittest tests.test_docs_reports`: OK, 3 tests
- `git diff --check`: OK
