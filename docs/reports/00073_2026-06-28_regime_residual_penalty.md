# Regime Residual Penalty

日時: 2026-06-28 23:01 JST
更新日時: 2026-06-28 23:01 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻や `更新日時` ではなく、本文内の作成時刻である `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

support-aware lower EVはEV全体を下げすぎて実行validationを壊した。今回は、side/regimeごとの予測過大評価だけを削る `regime residual penalty` を追加した。

考え方:

```text
side_overestimate = mean(max(pred_side_ev - actual_side_pnl, 0))
group_overestimate = same metric by side/regime
excess = max(0, group_overestimate - side_overestimate - min_excess)
penalized_ev = raw_ev - penalty_weight * excess
```

全体を一律に下げず、side平均より過大評価が大きいgroupだけを下げる設計にした。

## Implementation

追加:

- `ResidualPenaltyConfig`
- `ResidualPenaltyStats`
- `ResidualPenaltyCalibrator`
- `fit_residual_penalty_calibrator`
- `add_residual_penalty_columns`
- `residual_penalty_scored_metrics`
- CLI `python3 -m trade_data.meta_model oof-residual-penalty`

出力列:

- `pred_regime_residual_penalized_long_best_adjusted_pnl`
- `pred_regime_residual_penalized_short_best_adjusted_pnl`
- penalty / excess / support / source / bias / overestimate metadata columns

既存backtestの `--long-column` / `--short-column` に直接渡せる。

## Setup

Input:

- OOF predictions: `data/reports/modeling/20260628_hgb_mlp_exit_hybrid/predictions_hgb_entry_mlp_exit_oof.parquet`
- 2024-12 predictions: `data/reports/modeling/20260628_hgb_mlp_exit_hybrid/predictions_hgb_entry_mlp_exit_2024_12.parquet`
- 2025-02 predictions: `data/reports/modeling/20260628_hgb_mlp_exit_hybrid/predictions_hgb_entry_mlp_exit_2025_02.parquet`

Policy:

- `timed_ev`
- `entry_threshold=15`
- `short_entry_threshold_offset=4`
- `side_margin=5`
- `max_predicted_hold_minutes=480`
- `min_entry_rank=0.0,0.5`
- holding columns: `pred_mlp_long_exit_event_minutes`, `pred_mlp_short_exit_event_minutes`
- evaluation: profit `1.0`, loss `1.20`

## Diagnostics

`volatility_regime,session_regime`, `penalty_weight=1`:

| split | selected rows raw | selected rows penalized | selected avg raw | selected avg penalized | side acc raw | side acc penalized |
|---|---:|---:|---:|---:|---:|---:|
| validation OOF | `54967` | `52719` | `19.0855` | `19.2500` | `0.5449` | `0.5492` |
| 2024-12 apply | `14438` | `13766` | `12.4549` | `12.5884` | `0.3441` | `0.3461` |
| 2025-02 apply | `21819` | `21044` | `18.2948` | `18.5276` | `0.4376` | `0.4445` |

row-levelでは改善したが、penalty平均は `0.1-0.2` 程度で実行売買には弱い。

`session_regime`, `penalty_weight=10`:

- validation OOF selected avgは `19.8574` へ上昇。
- 2024-12 apply selected avgは `13.5499`、side accuracyは `0.3766` へ改善。
- 2025-02 apply selected avgは `17.9703` へ悪化し、side accuracyも `0.4266` へ悪化。

final calibratorで強く削られたgroup:

| side | group | penalty |
|---|---|---:|
| long | `asia` | `3.2366` |
| long | `rollover` | `0.9635` |
| short | `london` | `6.5496` |

既知の2024-12改善候補だった `long:ny_late` は削られていない。row-level residualは、実行売買で壊れる方向を十分に表していない。

## Backtest Results

`session_regime`, `penalty_weight=10`, validation 4fold:

| min entry rank | fold count | eligible folds | min adjusted pnl | sum adjusted pnl | min trades | max DD | forced exit max | eligible |
|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `0.5` | `4` | `4` | `85.7296` | `421.6626` | `26` | `65.1552` | `0.0000` | true |
| `0.0` | `4` | `4` | `81.0356` | `390.4700` | `26` | `70.4052` | `0.0000` | true |

Fixed holdout:

| group | min entry rank | 2024-12 pnl | 2025-02 pnl | note |
|---|---:|---:|---:|---|
| session | `0.5` | `-156.1742` | `+102.3132` | 2024-12が大幅悪化 |
| session | `0.0` | `-159.1944` | `+137.5952` | 2024-12が大幅悪化 |
| vol/session | `0.5` | `-166.4110` | `+16.6456` | 両holdoutで弱い |
| vol/session | `0.0` | `-159.6254` | `+61.8658` | 両holdoutで弱い |

既存のraw hybrid baseline 2024-12 `-54.6032`、`long:ny_late:15` risk top `-5.4938` を大きく下回る。

## Decision

- residual penalty columnsとOOF CLIは研究インフラとして残す。
- row-level `pred - target` のpositive residualだけでは、実行売買の損失方向を捉えられない。
- `session_regime` penaltyはvalidation上はeligibleだが、fixed holdoutで大きく崩れるため標準採用しない。
- 次は全rowのresidualではなく、実際にentry条件を通った候補または実行tradeに限定した residual / side failure target を作る。具体的には `selected-trade residual`、`candidate-entry residual`、`direction/session realized failure` をOOFで作り、row-level targetとの乖離を明示的に見る。

## Artifacts

- session residual 2024-12 apply: `data/reports/modeling/20260628_135825_residual_penalty_session_w10_2024_12/`
- session residual 2025-02 apply: `data/reports/modeling/20260628_135825_residual_penalty_session_w10_2025_02/`
- session validation sweeps: `data/reports/backtests/residual_penalty_session_w10_validation_base/`
- session validation summary: `data/reports/backtests/residual_penalty_session_w10_validation_summary/20260628_135923_model_sweep_summary/`
- session fixed tests: `data/reports/backtests/residual_penalty_session_w10_fixed_tests/`
- vol/session residual 2024-12 apply: `data/reports/modeling/20260628_140106_residual_penalty_vol_session_w10_2024_12/`
- vol/session residual 2025-02 apply: `data/reports/modeling/20260628_140106_residual_penalty_vol_session_w10_2025_02/`
- vol/session fixed tests: `data/reports/backtests/residual_penalty_vol_session_w10_fixed_tests/`

## Verification

- `PYTHONPATH=src python3 -m unittest tests.test_meta_model`
