# HGB Entry With MLP Exit Hybrid

日時: 2026-06-28 20:38 JST
更新日時: 2026-06-28 20:38 JST

## 目的

shared MLP単体はentry EV/sideが弱く、strict候補が残らなかった。一方で `pred_*_exit_event_minutes` はOOFでもR2約`0.34`を持っていた。そこで、entry/sideは既存HGB combined model、exit timingだけMLPに差し替えるhybridを検証する。

Report numbering note: this file is numbered from the internal file `日時`, not filesystem mtime, file-update timestamp, or `更新日時`. Latest-report checks and renumbering must use the internal `日時`.

## Setup

Base HGB predictions:

- `experiments/20260628_101740_policy_combined_side_exit_p1_l1p2/`
- train months: `2023-01..2024-10`, excluding validation months and `2024-12`
- validation months: `2024-07`, `2024-09`, `2024-11`, `2025-01`
- test month: `2024-12`

Hybrid validation predictions:

- HGB validation predictions with MLP OOF holding columns merged by `decision_timestamp` and `dataset_month`.
- Added columns: `pred_mlp_long_exit_event_minutes`, `pred_mlp_short_exit_event_minutes`
- Artifact: `data/reports/modeling/20260628_hgb_mlp_exit_hybrid/predictions_hgb_entry_mlp_exit_oof.parquet`
- Rows: `115252`

Hybrid test predictions:

- HGB 2024-12 test predictions with final shared MLP 2024-12 holding columns merged.
- MLP final model: `experiments/20260628_113707_shared_mlp_hgb_split_test_2024_12/`
- Artifact: `data/reports/modeling/20260628_hgb_mlp_exit_hybrid/predictions_hgb_entry_mlp_exit_2024_12.parquet`
- Rows: `28763`

Final MLP diagnostic:

| split | long exit event minutes R2 | short exit event minutes R2 | note |
|---|---:|---:|---|
| validation | `0.369380` | `0.375580` | trained on HGB train months |
| 2024-12 test | `0.301197` | `0.306834` | still useful but weaker |

The MLP again hit `max_iter=40`, so this is still convergence-limited.

## Validation Selection

Same grid for base and hybrid:

- policy: `timed_ev`
- entry threshold: `5,10,15,20,30,40`
- short offset: `0,4,8,12`
- side margin: `1,3,5,10`
- min entry rank: `0,0.5`
- max predicted hold: `240,480,720`
- min hold: `1`

Strict candidate selection:

- `min_folds=4`
- `min_trades_per_fold=10`
- `max_forced_exit_rate=0.05`
- `max_drawdown=200`
- `min_adjusted_pnl_per_fold=0`
- `max_side_trade_share=0.85`

| variant | eligible | top entry | short offset | side margin | rank | max hold | min pnl | sum pnl | min trades | max DD | max side share |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| HGB holding base | `51` | `15` | `0` | `5` | `0.0` | `480` | `78.4344` | `369.5736` | `27` | `68.0340` | `0.718750` |
| HGB entry + MLP holding | `58` | `15` | `4` | `5` | `0.5` | `480` | `81.5352` | `396.9782` | `23` | `60.0744` | `0.709677` |

Same-key comparison:

| key | variant | min pnl | sum pnl | min trades | max DD | max side share |
|---|---|---:|---:|---:|---:|---:|
| base top | HGB holding | `78.4344` | `369.5736` | `27` | `68.0340` | `0.718750` |
| base top | MLP holding | `76.8152` | `381.6780` | `28` | `70.2264` | `0.718750` |
| hybrid top | HGB holding | `75.9228` | `385.1490` | `23` | `67.0176` | `0.709677` |
| hybrid top | MLP holding | `81.5352` | `396.9782` | `23` | `60.0744` | `0.709677` |

Validationでは、MLP holdingは小さいが一貫した改善を作った。特にhybrid top keyではmin pnl `+5.6124`、sum pnl `+11.8292`、max DD `-6.9432` の改善。

## 2024-12 Fixed Test

Validationで選んだbase topとhybrid topを、2024-12へ固定適用した。

| candidate | holding | adjusted pnl | raw pnl | trades | PF | DD | forced | long pnl | short pnl | worst direction/session | direction error | EV over realized |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| base top | HGB | `-91.5596` | `-50.1230` | `32` | `0.6317` | `109.3812` | `1` | `-45.3902` | `-46.1694` | `long:ny_late -59.3304` | `0.6250` | `22.3310` |
| base top | MLP | `-79.0698` | `-35.9480` | `49` | `0.6944` | `104.5370` | `1` | `-24.8794` | `-54.1904` | `long:ny_late -55.3134` | `0.6531` | `22.6520` |
| hybrid top | HGB | `-56.3716` | `-21.0700` | `28` | `0.7339` | `97.2372` | `1` | `-45.3902` | `-10.9814` | `long:ny_late -59.3304` | `0.6071` | `22.0973` |
| hybrid top | MLP | `-54.6032` | `-18.1410` | `49` | `0.7504` | `97.3520` | `1` | `-25.1324` | `-29.4708` | `long:ny_late -55.3134` | `0.6327` | `23.0714` |

MLP holdingは2024-12でも損失を縮めたが、改善幅はbase topで `+12.4898`、hybrid topで `+1.7684` に留まった。NoTrade `0.0` には届かない。

## 判断

HGB entry/side + MLP exit timing hybridは、validationではbaseよりわずかに良い。2024-12でも損失は縮む。ただし、損失の主因はexit timingではなく、direction errorとEV overestimateである。2024-12では `direction_error_rate` が `0.60` 超、`EV over realized` が約`22-23`残っており、holding差し替えだけでは壊れたentry/sideを救えない。

今回のhybridは標準policyへ昇格しない。MLP exit timingは補助信号として残すが、本流はentry/side calibration、EV過大評価抑制、side classifierの改善へ戻す。

## Next

- MLP exit timingは、HGBまたは別classifierのentry/sideが十分安定した候補にだけ適用する。
- 次の実験では、2024-12で崩れた `long:ny_late` と `range_low_vol` を直接扱うentry/side risk controlを優先する。
- shared MLPを続けるなら、regression-onlyではなくside/profit-barrier classifierも共有表現側に入れる。

## Artifacts

- Hybrid validation predictions: `data/reports/modeling/20260628_hgb_mlp_exit_hybrid/predictions_hgb_entry_mlp_exit_oof.parquet`
- Hybrid test predictions: `data/reports/modeling/20260628_hgb_mlp_exit_hybrid/predictions_hgb_entry_mlp_exit_2024_12.parquet`
- MLP final model: `experiments/20260628_113707_shared_mlp_hgb_split_test_2024_12/`
- Base sweeps: `data/reports/backtests/hgb_exit_holding_base_sweep/`
- Hybrid sweeps: `data/reports/backtests/hgb_entry_mlp_exit_hybrid_sweep/`
- Base selection: `data/reports/backtests/hgb_exit_holding_base_selection/20260628_113516_model_candidate_selection/`
- Hybrid selection: `data/reports/backtests/hgb_entry_mlp_exit_hybrid_selection/20260628_113516_model_candidate_selection/`
- 2024-12 fixed tests: `data/reports/backtests/hgb_vs_mlp_exit_holding_2024_12/`
