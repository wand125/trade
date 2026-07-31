# Group Loss Gate And Posthoc Failure Analysis

日時: 2026-06-28 20:45 JST
更新日時: 2026-06-28 20:45 JST

## 目的

前回のHGB entry/side + MLP exit timing hybridは、validationでは小幅改善したが2024-12でNoTradeに負けた。失敗診断では `long:ny_late` と `range_low_vol` が目立った。今回は、2024-12のグループ名を直接使った採用ではなく、validation時点のgroup loss / diagnostic gateだけで候補選定を改善できるかを確認する。

Report numbering note: this file is numbered from the internal file `日時`, not filesystem mtime, file-update timestamp, or `更新日時`. Latest-report checks and renumbering must use the internal `日時`.

## Setup

Input sweeps:

- `data/reports/backtests/hgb_entry_mlp_exit_hybrid_sweep/`

Common strict criteria:

- `min_folds=4`
- `min_trades_per_fold=10`
- `max_forced_exit_rate=0.05`
- `max_drawdown=200`
- `min_adjusted_pnl_per_fold=0`
- `max_side_trade_share=0.85`

Additional selection variants:

- baseline: no extra group/diagnostic penalty
- group soft: `group_loss_penalty_weight=1.0`
- group gate60: `max_direction_session_loss=60`, `max_combined_regime_loss=60`, `max_direction_combined_regime_loss=70`
- group gate50: `max_direction_session_loss=50`, `max_combined_regime_loss=50`, `max_direction_combined_regime_loss=55`
- diagnostic soft: `diagnostic_penalty_weight=1.0`, thresholds direction error `0.45`, smoothed actual miss `0.55`, EV over realized `16`

## Validation Selection

| variant | eligible | top entry | short offset | side margin | rank | max hold | min pnl | sum pnl | min trades | group loss / diagnostic note |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| baseline | `58` | `15` | `4` | `5` | `0.5` | `480` | `81.5352` | `396.9782` | `23` | top unchanged |
| group soft | `58` | `15` | `4` | `5` | `0.5` | `480` | `81.5352` | `396.9782` | `23` | ranking unchanged; penalty did not overcome pnl lead |
| group gate60 | `11` | `15` | `4` | `5` | `0.0` | `240` | `23.1484` | `212.0362` | `28` | group losses reduced but pnl much lower |
| group gate50 | `0` | - | - | - | - | - | - | - | - | too strict; no eligible candidate |
| diagnostic soft | `58` | `15` | `4` | `5` | `0.5` | `480` | `81.5352` | `396.9782` | `23` | top unchanged |

Soft ranking did not change the chosen candidate. Hard group gate60 produced a different candidate with lower validation group-loss depth, but validation edge was much smaller.

## 2024-12 Fixed Test

The group gate60 top was fixed and applied to 2024-12.

| candidate | holding | adjusted pnl | raw pnl | trades | PF | DD | forced | long pnl | short pnl | worst direction/session | direction error | EV over realized |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| previous hybrid top | MLP | `-54.6032` | `-18.1410` | `49` | `0.7504` | `97.3520` | `1` | `-25.1324` | `-29.4708` | `long:ny_late -55.3134` | `0.6327` | `23.0714` |
| group gate60 top | HGB | `-69.0240` | `-31.6420` | `40` | `0.6923` | `100.9666` | `1` | `-69.9372` | `0.9132` | `long:ny_late -83.7752` | `0.6000` | `21.9547` |
| group gate60 top | MLP | `-97.6568` | `-53.4810` | `63` | `0.6316` | `131.9654` | `1` | `-66.7032` | `-30.9536` | `long:ny_late -83.7752` | `0.6984` | `23.6829` |

Validation group-loss gateは、2024-12の `long:ny_late` failureを事前に抑えられなかった。むしろgroup gate60 topはlong側の損失を悪化させた。

## Posthoc Diagnostic Only

The following is explicitly posthoc and must not be treated as adoption evidence. It is only used to identify the next hypothesis to test inside validation.

Baseline for this diagnostic is previous hybrid top with MLP holding:

| posthoc rule | adjusted pnl | raw pnl | trades | PF | DD | forced | long pnl | short pnl | worst direction/session |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| none | `-54.6032` | `-18.1410` | `49` | `0.7504` | `97.3520` | `1` | `-25.1324` | `-29.4708` | `long:ny_late -55.3134` |
| block `long:session_regime=ny_late` | `-5.4938` | `21.2950` | `46` | `0.9658` | `61.1556` | `0` | `23.9770` | `-29.4708` | `short:london -11.3790` |
| block `long:combined_regime=range_low_vol` | `-13.1318` | `16.1000` | `47` | `0.9251` | `62.8626` | `0` | `16.3390` | `-29.4708` | `short:london -11.3790` |
| block both long rules | `-23.5298` | `6.3100` | `46` | `0.8686` | `62.8626` | `0` | `5.9410` | `-29.4708` | `short:london -11.3790` |
| block all `range_low_vol` | `-10.0104` | `19.2240` | `47` | `0.9429` | `59.4102` | `0` | `16.3390` | `-26.3494` | `short:london -10.5510` |

Posthocには `long:ny_late` blockが最も効く。ただしNoTrade `0.0` にはまだ届かず、direction error / EV overestimateも残る。これは採用候補ではなく、次にvalidation gridへ入れて事前評価すべき仮説である。

## 判断

Current selection diagnostics do not yet isolate the 2024-12 failure before seeing it. Group-loss hard gate reduces validation group-loss depth but also discards much of the edge and does not improve the 2024-12 fixed test.

The useful finding is narrower: `long:ny_late` and `long:range_low_vol` are plausible risk-control axes, but they must be added to validation sweeps as candidate rules and re-selected without using 2024-12 performance. If those rules only work on 2024-12, they should be rejected.

## Next

- Add validation sweep variants for side-specific long suppression or extra margin:
  - `long:session_regime=ny_late`
  - `long:combined_regime=range_low_vol`
  - possibly softer `side-extra-margin-rules` before hard block
- Re-run validation selection with these rules included as grid dimensions.
- Only after validation selection, fix the chosen rule and test on 2024-12 and a later blind month.

## Artifacts

- group soft selection: `data/reports/backtests/hgb_entry_mlp_exit_hybrid_selection_group_soft/20260628_114255_model_candidate_selection/`
- group gate60 selection: `data/reports/backtests/hgb_entry_mlp_exit_hybrid_selection_group_gate60/20260628_114255_model_candidate_selection/`
- group gate50 selection: `data/reports/backtests/hgb_entry_mlp_exit_hybrid_selection_group_gate50/20260628_114255_model_candidate_selection/`
- diagnostic soft selection: `data/reports/backtests/hgb_entry_mlp_exit_hybrid_selection_diag_soft/20260628_114255_model_candidate_selection/`
- group gate60 fixed test: `data/reports/backtests/hgb_entry_mlp_exit_group_gate_2024_12/`
- posthoc block diagnostics: `data/reports/backtests/hgb_entry_mlp_exit_posthoc_blocks_2024_12/`
