# Side EV Penalty Cost Stress

日時: 2026-06-28 21:52 JST
更新日時: 2026-06-28 21:52 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻や `更新日時` ではなく、本文内の `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

`long:session_regime=ny_late:15` のside EV penalty候補を、2024-12でspread / slippage / execution delayに対してストレスした。

結論は、risk top候補はruleなしbaselineより明確に壊れにくいが、標準条件では adjusted pnl `-5.4938` でNoTrade `0` に届かない。高コスト条件でもbaseline `-76.3910` に対して `-26.0816` まで損失を縮めるが、プラス化はしない。したがって標準policyへはまだ昇格しない。

## Setup

- predictions: `data/reports/modeling/20260628_hgb_mlp_exit_hybrid/predictions_hgb_entry_mlp_exit_2024_12.parquet`
- month: `2024-12`
- policy: `timed_ev`
- holding columns: `pred_mlp_long_exit_event_minutes`, `pred_mlp_short_exit_event_minutes`
- evaluation multipliers: profit `1.0`, loss `1.20`
- stress grid: spread `0,0.1,0.2`, slippage `0,0.05,0.1`, execution delay bars `0,1`

Candidates:

| candidate | side EV penalty | min entry rank | entry | short offset | side margin | max hold |
|---|---|---:|---:|---:|---:|---:|
| baseline | none | `0.5` | `15` | `4` | `5` | `480` |
| PnL top | `long:session_regime=ny_late:15` | `0.0` | `15` | `4` | `5` | `480` |
| risk top | `long:session_regime=ny_late:15` | `0.5` | `15` | `4` | `5` | `480` |

## Stress Results

| scenario | baseline adj pnl | PnL top adj pnl | risk top adj pnl |
|---|---:|---:|---:|
| standard | `-54.6032` | `-15.0538` | `-5.4938` |
| delay 1, no cost | `-45.9842` | `-10.6880` | `+3.6670` |
| spread 0.1 / slippage 0.05 / delay 0 | `-65.4832` | `-21.8538` | `-15.7738` |
| spread 0.2 / slippage 0.1 / delay 0 | `-76.3910` | `-28.6638` | `-26.0816` |
| spread 0.2 / slippage 0.1 / delay 1 | `-67.9042` | `-24.4480` | `-17.0530` |

Standard metrics:

| candidate | adjusted pnl | raw pnl | trades | long | short | profit factor | max DD | worst direction/combined |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| baseline | `-54.6032` | `-18.1410` | `49` | `12` | `37` | `0.7504` | `97.3520` | `long:range_low_vol` `-50.3094` |
| PnL top | `-15.0538` | `14.6140` | `31` | `9` | `22` | `0.9154` | `69.6900` | `short:range_low_vol` `-43.9426` |
| risk top | `-5.4938` | `21.2950` | `46` | `9` | `37` | `0.9658` | `61.1556` | `short:range_normal_vol` `-33.9232` |

Worst stress row:

| candidate | spread | slippage | delay | adjusted pnl | profit factor | max DD |
|---|---:|---:|---:|---:|---:|---:|
| baseline | `0.2` | `0.1` | `0` | `-76.3910` | `0.6706` | `115.2030` |
| PnL top | `0.2` | `0.1` | `0` | `-28.6638` | `0.8453` | `74.6292` |
| risk top | `0.2` | `0.1` | `0` | `-26.0816` | `0.8500` | `65.2456` |

## Findings

- `long:ny_late:15` penaltyは、2024-12の損失・drawdown・高コスト耐性をbaselineより大きく改善した。
- risk topはPnL topより取引数が多いが、標準条件と高コスト条件の両方でPnL topを上回った。
- delay 1でrisk topが `+3.6670` になるが、これは約定遅延に依存した改善であり、安定edgeとして扱わない。
- cost stress後もNoTradeを安定して超えていないため、標準policy採用は不可。
- 現在のhybrid prediction artifactは2024-12までで、別holdout月を評価するには `policy_combined` datasetの月追加、HGB/MLP再学習、hybrid prediction生成が必要。

## Decision

- `side_ev_penalty_rules` は探索軸として継続する。
- 現時点の暫定有力候補は risk top: `long:session_regime=ny_late:15`, `min_entry_rank=0.5`。
- ただし標準policyへは昇格しない。次は別holdout月を生成し、testを見ずに同じ候補を固定適用する。
- report ordering / latest checksは、ファイル更新時刻や `更新日時` ではなく本文の `日時` を参照する。

## Artifacts

- cost stress runs: `data/reports/backtests/hgb_entry_mlp_exit_side_ev_penalty_cost_stress_2024_12/`
- baseline: `data/reports/backtests/hgb_entry_mlp_exit_side_ev_penalty_cost_stress_2024_12/20260628_124906_model_cost_sensitivity_2024-12_2/`
- PnL top: `data/reports/backtests/hgb_entry_mlp_exit_side_ev_penalty_cost_stress_2024_12/20260628_124906_model_cost_sensitivity_2024-12_1/`
- risk top: `data/reports/backtests/hgb_entry_mlp_exit_side_ev_penalty_cost_stress_2024_12/20260628_124906_model_cost_sensitivity_2024-12/`

## Verification

- `PYTHONPATH=src python3 -m unittest tests.test_docs_reports`
- `git diff --check`
