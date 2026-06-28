# Selected Trade Quality Calibration

日時: 2026-06-28 15:00 JST
更新日時: 2026-06-28 15:00 JST

## Summary

- Experiment ID: `selected_trade_quality_calibration`
- Status: implemented and validation-tested
- Main result: policyが実際に選んだtradeだけを使い、side/regime別に `pred_taken_ev -> realized adjusted_pnl` をOOF補正する基盤を追加した。raw biasは下がったが、`min_trade_quality` gateとして使うとvalidation topは改善せず、標準候補はgateなし `min_trade_quality=-inf` のまま。
- Report numbering note: this file is numbered by the internal `日時`, not by file update time or `更新日時`.

## Motivation

前回の線形profit-barrier miss penaltyは、trade集合の実現品質を改善しなかった。そこで今回は、row全体のtargetではなく、policyが実際にentryしたtrade集合から実現PnLを学習する。

狙い:

- selected tradesのEV過大評価を下げる。
- actual profit-barrier missやexit regretが大きいentryを落とす。
- 同月fit/同月選択を避けるため、validation月をleave-one-month-outにする。

## Implementation

追加:

- `TradeQualityCalibrator`
- `oof-trade-quality-calibration` CLI
- `pred_trade_source_long_ev`
- `pred_trade_source_short_ev`
- `pred_trade_quality_long_adjusted_pnl`
- `pred_trade_quality_short_adjusted_pnl`
- `model-policy --min-trade-quality`
- `model-sweep --min-trade-qualities`

補正式:

```text
trade_quality = group_target_mean + shrinkage * (raw_side_ev - group_pred_mean)
```

今回のfit対象は、現行基準候補のcost-aware trades。

## Setup

Validation months:

- `2024-07`
- `2024-09`
- `2024-11`
- `2025-01`

Base policy for selected-trade fit:

- policy: `fixed_horizon_ev`
- score mode: `max`
- entry threshold: `0`
- short offset: `8`
- side margin: `1`
- max wait regret: `4`
- min entry rank: `0.5`
- profit barrier threshold: `0.2`
- extra margin: `session_regime=asia:5`, `session_regime=rollover:5`
- cost case: spread `0.1`, slippage `0.05`, delay `0`

Trade quality calibration:

- source mode: `fixed_horizon`
- source score mode: `max`
- group columns: `volatility_regime,session_regime`
- min group size: `5`
- prior strength: `20`
- prediction shrinkage: `0.5`

Sweep grid:

- min trade quality: `-inf`, `-1`, `0`, `0.5`, `1`, `1.5`, `2`
- short offsets: `4`, `8`
- min entry rank: `0`, `0.5`
- profit barrier thresholds: `0.0`, `0.2`
- same strict candidate gates as current standard validation

## Calibration Diagnostics

OOF selected-trade calibration on 246 trades:

| metric | value |
|---|---:|
| raw bias | `0.628560` |
| calibrated bias | `-0.078209` |
| bias reduction | `0.550351` |
| raw overestimate mean | `2.182599` |
| calibrated overestimate mean | `1.805135` |
| calibrated MAE | `3.688478` |
| calibrated RMSE | `6.744752` |
| calibrated R2 | `-0.017978` |

平均biasは下がったが、R2は負。group mean/shrink型では個別tradeの識別力はまだ弱い。

## Candidate Selection Results

Strict candidate selection:

| min trade quality | eligible | best cost min pnl | best base min pnl | min trades | best smoothed miss | best EV overestimate | best exit regret |
|---:|---:|---:|---:|---:|---:|---:|---:|
| `-inf` | 7 | `27.2158` | `39.7538` | 47 | `0.454545` | `14.377795` | `20.940811` |
| `-1.0` | 6 | `22.7466` | `34.8046` | 47 | `0.454545` | `14.377795` | `20.940811` |
| `0.0` | 3 | `9.2116` | `20.8296` | 47 | `0.464286` | `14.549737` | `20.119757` |
| `0.5` | 3 | `4.7194` | `15.3554` | 27 | `0.488889` | `14.763182` | `19.831520` |
| `1.0` | 0 | `-9.1060` | `-4.2660` | 17 | `0.625000` | `16.130152` | `20.550062` |
| `1.5` | 0 | `-9.5430` | `-6.0630` | 7 | `0.555556` | `16.353062` | `22.190215` |
| `2.0` | 0 | `-11.8200` | `-11.3400` | 2 | `0.727273` | `21.725741` | `20.487900` |

Top eligible remains:

- `min_trade_quality=-inf`
- `short offset=8`
- `min_entry_rank=0.5`
- `profit_barrier_threshold=0.2`
- cost min pnl `27.2158`

## Interpretation

selected-trade calibrationは、平均的なEV過大評価を下げる診断としては有効だった。しかし、entry gateとしてはまだ弱い。

- `min_trade_quality >= 0` はtradeを削るが、cost-aware fold最低PnLを大きく落とす。
- `min_trade_quality >= 1` 以上ではeligibleが消える。
- smoothed actual barrier missは改善せず、むしろ悪化する閾値が多い。
- exit regretは少し下がるが、PnL悪化を補えない。
- group平均/shrinkでは個別entryを見分けられず、R2が負になった。

この結果は、selected-trade targetという方針自体の否定ではなく、今回の単純なside/regime平均補正が粗いことを示す。

## Decision

- `oof-trade-quality-calibration` と `min_trade_quality` gateの基盤は残す。
- 現時点では `min_trade_quality` gateを標準候補へ採用しない。
- 標準候補選定は raw fixed horizon + `score_mode=max` + `min_trade_quality=-inf` を維持する。
- 次は、selected-trade targetをgroup平均ではなく、小型モデルで学習するか、exit hazard/survival targetで利確/損切り/時間切れのタイミングを直接扱う。

## Artifacts

- selected-trade fit trades:
  - `data/reports/backtests/20260628_055630_model_fixed_horizon_ev_2024-07/`
  - `data/reports/backtests/20260628_055630_model_fixed_horizon_ev_2024-09/`
  - `data/reports/backtests/20260628_055630_model_fixed_horizon_ev_2024-11/`
  - `data/reports/backtests/20260628_055630_model_fixed_horizon_ev_2025-01/`
- OOF trade quality calibration: `experiments/20260628_055648_trade_quality_oof_fixed_horizon/`
- no-cost sweeps:
  - `data/reports/backtests/20260628_055803_model_sweep_2024-07/`
  - `data/reports/backtests/20260628_055803_model_sweep_2024-09/`
  - `data/reports/backtests/20260628_055803_model_sweep_2024-11/`
  - `data/reports/backtests/20260628_055803_model_sweep_2025-01/`
- cost sweeps:
  - `data/reports/backtests/20260628_055853_model_sweep_2024-07/`
  - `data/reports/backtests/20260628_055853_model_sweep_2024-09/`
  - `data/reports/backtests/20260628_055853_model_sweep_2024-11/`
  - `data/reports/backtests/20260628_055853_model_sweep_2025-01/`
- candidate selection: `data/reports/backtests/20260628_055927_model_candidate_selection/`

## Verification

- `python3 -m unittest tests.test_backtest tests.test_meta_model`: OK
