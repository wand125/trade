# Short Exposure And Support-Aware Gates

日時: 2026-06-28 10:47 JST
更新日時: 2026-06-28 10:47 JST

## 目的

2025-06 blindで、`short:session_regime=asia` block候補は損失中心を `short:london` へ移しただけだった。session hard blockを増やすとNoTradeに近づくため、次は候補選定で以下を直接見る。

- short-only dependence
- dominant side concentration
- small sampleで raw miss / calibration max が 1.0 になる問題

今回は `model-sweep` metricsと `model-candidate-selection` に、side exposure concentration と support-aware barrier diagnosticsを追加する。

## 実装

`model-policy` / `model-sweep` metricsへ追加:

- `long_trade_share`
- `short_trade_share`
- `max_side_trade_share`
- `predicted_profit_barrier_miss_rate_smoothed`
- `actual_profit_barrier_miss_rate_smoothed`
- `profit_barrier_calibration_overestimate_smoothed_max`
- `worst_profit_barrier_calibration_actual_hit_rate_smoothed`
- `worst_profit_barrier_calibration_overestimate_smoothed`
- bucket別 `actual_hit_rate_smoothed`
- bucket別 `overestimate_smoothed`

smoothed指標は Laplace smoothing。

- miss rate: `(miss_count + 1) / (observed_count + 2)`
- actual hit rate: `(hit_count + 1) / (bucket_count + 2)`

`model-candidate-selection` へ追加:

- `--max-short-trade-share`
- `--max-side-trade-share`
- `--max-smoothed-actual-profit-barrier-miss-rate`
- `--max-smoothed-profit-barrier-calibration-overestimate`

既存の raw gate は残し、defaultはすべて `1.0` にした。明示したときだけ新しいgateが効く。

## Smoke

対象:

- model: `experiments/20260628_013141_full_fixed_horizon_blind_2025_06_barrier_prob_p1_l1p2/`
- month: `2025-06`
- selected candidate: `short:session_regime=asia`
- diagnostic no-short candidate: `short:session_regime=asia,short:session_regime=london,short:session_regime=rollover`
- cost case: spread `0.1`, slippage `0.05`, delay `0`

Artifacts:

- no-cost selected: `data/reports/backtests/20260628_014713_model_sweep_2025-06_1/`
- no-cost no-short diagnostic: `data/reports/backtests/20260628_014713_model_sweep_2025-06/`
- cost selected: `data/reports/backtests/20260628_014713_model_sweep_2025-06_2/`
- cost no-short diagnostic: `data/reports/backtests/20260628_014713_model_sweep_2025-06_3/`
- candidate selection: `data/reports/backtests/20260628_014727_model_candidate_selection/`

Candidate selection smoke条件:

- `--min-folds 1`
- `--min-trades-per-fold 10`
- `--max-short-trade-share 0.8`
- `--max-side-trade-share 0.95`
- `--max-smoothed-actual-profit-barrier-miss-rate 0.5`
- `--max-smoothed-profit-barrier-calibration-overestimate 0.5`
- PnL系gateはsmokeのため緩めた。

## 結果

Selected `short:session_regime=asia`:

- adjusted pnl no-cost: `-100.4662`
- adjusted pnl cost: `-103.7488`
- trades: `15`
- short trade share: `0.933333`
- max side trade share: `0.933333`
- actual miss rate smoothed: `0.470588`
- calibration overestimate smoothed: `0.470588`
- candidate selection: `short_trade_share_ok=false`, `eligible=false`

No-short diagnostic:

- adjusted pnl no-cost: `0.5570`
- adjusted pnl cost: `0.3570`
- trades: `1`
- short trade share: `0.000000`
- max side trade share: `1.000000`
- actual miss rate smoothed: `0.333333`
- calibration overestimate smoothed: `0.333333`
- candidate selection: `eligible_base=false`, `eligible_cost=false`, `side_trade_share_ok=false`, `eligible=false`

Summary:

| side block | base pnl | cost pnl | min trades | short share max | max side share | smoothed actual miss | smoothed calibration overestimate | failed gate |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| `short:session_regime=asia` | `-100.4662` | `-103.7488` | 15 | `0.933333` | `0.933333` | `0.470588` | `0.470588` | `short_trade_share` |
| all short sessions blocked | `0.5570` | `0.3570` | 1 | `0.000000` | `1.000000` | `0.333333` | `0.333333` | `min trades`, `side_trade_share` |

## 判断

short exposure concentration gateは、2025-06の失敗候補を直接落とせる。

ただし、`max-side-trade-share` は単純に厳しくしすぎると、1 tradeだけのNoTrade類似候補も落とす。これは望ましいが、少数trade候補はまず `min-trades-per-fold` で落とすべきで、side shareは補助診断として扱う。

smoothed actual miss / calibrationは、raw値の過反応を弱める診断として有効。2025-06 selectedでは rawもsmoothedも `0.46-0.47` で悪く、small sampleだけが原因ではない。一方、1 trade候補では raw 0.0 に対して smoothed 0.3333 となり、過度に楽観しない。

現時点の採用方針:

- `--max-short-trade-share` は候補選定のhard gate候補に昇格してよい。
- `--max-side-trade-share` はNoTrade類似の片側1trade候補も検出する診断として使う。
- smoothed actual miss / smoothed calibrationは raw gateの代替候補としてvalidation全体で台地を見る。
- 次のblindを見る前に、validation 4fold以上でこのgateセットを固定する。

## 検証

- `python3 -m py_compile src/trade_data/backtest.py`: OK
- `python3 -m unittest tests.test_backtest`: 33 tests OK
- `model-candidate-selection --help`: OK
- `git diff --check`: OK
