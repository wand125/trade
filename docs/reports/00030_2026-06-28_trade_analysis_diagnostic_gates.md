# Trade Analysis Diagnostic Gates

日時: 2026-06-28 12:37 JST
更新日時: 2026-06-28 12:37 JST

## Summary

- Experiment ID: `trade_analysis_diagnostic_gates`
- Status: implemented and smoke-tested
- Main result: `model-sweep` now records trade-analysis diagnostics, and `model-candidate-selection` can reject candidates with high direction error, exit regret, or EV overestimate.
- Report numbering note: this file is numbered by the internal `日時`, not by file update time or `更新日時`.

## Motivation

2025-07 blindで候補Aは、short concentrationを避けた一方で、以下が悪化してNoTradeに負けた。

- direction error rate: `0.5303`
- exit regret mean: about `17.45`
- EV overestimate vs realized mean: `15.6821`
- actual profit barrier miss rate: `0.6515`

これまではこれらを `analyze-trades` で後から見るだけだった。次の候補選定では、validation段階で同じ弱点を落とせる必要がある。

## Implementation

`model-sweep` metricsに以下の列を追加した。

- `analysis_matched_prediction_rate`
- `direction_error_rate`
- `no_edge_rate`
- `predicted_side_error_rate`
- `exit_regret_sum`
- `exit_regret_mean`
- `best_side_regret_sum`
- `best_side_regret_mean`
- `ev_overestimate_vs_oracle_mean`
- `ev_overestimate_vs_realized_mean`

`model-candidate-selection` に以下のgateを追加した。

- `--max-direction-error-rate`
- `--max-predicted-side-error-rate`
- `--max-no-edge-rate`
- `--max-exit-regret-mean`
- `--max-ev-overestimate-vs-realized-mean`

古いsweep CSVには新列が存在しないため、`normalize_sweep_metrics` では新列を `0.0` で補完する。これにより既存レポートや過去artifactの読み込み互換を維持する。

## Smoke Test

2025-07 candidate Aを1点だけ再sweepした。これはpost-hoc検証であり、採用根拠ではない。

No-cost artifact:

- `data/reports/backtests/20260628_033639_model_sweep_2025-07/`

Cost-aware artifact:

- `data/reports/backtests/20260628_033650_model_sweep_2025-07/`

Candidate selection artifact:

- `data/reports/backtests/20260628_033702_model_candidate_selection/`

Candidate A diagnostic:

| metric | value | gate |
|---|---:|---|
| base adjusted pnl | `+1.5838` | pass under relaxed smoke |
| cost adjusted pnl | `-12.7764` | pass under relaxed smoke |
| direction error rate max | `0.5303` | fail at `0.50` |
| predicted side error rate max | `0.3788` | pass at `0.50` |
| exit regret mean max | `17.4505` | fail at `15.0` |
| EV overestimate vs realized mean max | `15.6821` | fail at `10.0` |

The post-hoc smoke confirms that the 2025-07 failed candidate can be rejected by diagnostic gates even when PnL gates are intentionally relaxed.

## Interpretation

この変更は、2025-07の失敗を直接回避するためのpost-hoc hardcodeではない。`ny_overlap` や `low_vol` のような具体regimeを見て直接blockするのではなく、失敗の構造である以下をvalidation候補選定へ戻す。

- 方向が逆に出ている
- exitを逃している
- 予測EVが実現PnLに対して過大
- 同側oracle edgeがあっても実行policyで取り切れていない

次の候補は、これらのgateをvalidation 4foldで見たうえで固定し、2025-08以降の未見月へ進む。

## Verification

- `python3 -m py_compile src/trade_data/backtest.py`: OK
- `python3 -m unittest tests.test_backtest`: 34 tests OK
- `python3 -m unittest discover tests`: 70 tests OK
- `python3 -m trade_data.backtest model-candidate-selection --help`: OK
- `git diff --check`: OK

## Next Actions

1. validation 4foldのhigh-turnover gridを、新diagnostic列入りで再生成する。
2. `max-direction-error-rate`, `max-exit-regret-mean`, `max-ev-overestimate-vs-realized-mean` の閾値台地を見る。
3. PnL, trade count, side/session loss, short share, smoothed barrier miss, trade-analysis diagnosticsを同時に満たす候補を固定する。
4. その候補だけを2025-08以降の未見月で評価する。
