# Profit Barrier Miss Candidate Gate

日時: 2026-06-28 10:06 JST
更新日時: 2026-06-28 10:21 JST

## 目的

candidate selectionに、実際に取ったsideのprofit barrier miss率を入れる。

前段の `short:session_regime=asia` blockはPnL改善に効いたが、方向予測やexit timingはまだ弱い。PnLだけで候補を選ぶと、たまたま勝っているがprofit barrier missが多い候補を残す危険がある。

今回は次を標準metricsへ入れる。

- `predicted_profit_barrier_miss_rate`
- `predicted_profit_barrier_miss_count`
- `predicted_profit_barrier_observed_count`
- `predicted_profit_barrier_miss_adjusted_pnl`
- `actual_profit_barrier_miss_rate`
- `actual_profit_barrier_miss_count`
- `actual_profit_barrier_observed_count`
- `actual_profit_barrier_miss_adjusted_pnl`

## 実装

`model-policy` / `model-sweep` は、存在する場合に以下の列をprediction parquetから任意列として読む。

- predicted barrier列: `--long-profit-barrier-column`, `--short-profit-barrier-column`
- actual label列: `long_profit_barrier_hit`, `short_profit_barrier_hit`

`require_profit_barrier=false` でも、列が存在すれば predicted miss を計測する。これにより、barrier gateをまだ使っていない候補でも「predicted barrierが弱いtradeをどれだけ含むか」を候補選択で見られる。

`model-candidate-selection` に以下を追加した。

- `--max-predicted-profit-barrier-miss-rate`
- `--max-actual-profit-barrier-miss-rate`

どちらもdefaultは `1.0` なので、明示的に指定しない限り既存選択は変わらない。古いsweep CSVに新列がない場合はmiss率 `0.0` として扱い、互換性を保つ。

## Smoke

対象:

- model: `experiments/20260628_003756_full_fixed_horizon_blind_2025_05_barrier_prob_p1_l1p2/`
- month: `2025-05`
- policy: `fixed_horizon_ev`
- entry threshold: `0`
- short offset: `6`
- side margin: `1`
- max wait regret: `4`
- min entry rank: `0.5`
- barrier threshold: `0.40`
- extra margin: `session_regime=asia:5,session_regime=rollover:5`
- cost case: spread `0.1`, slippage `0.05`, delay `0`

Artifacts:

- model-policy block: `data/reports/backtests/20260628_010449_model_fixed_horizon_ev_2025-05/`
- model-policy no block: `data/reports/backtests/20260628_010449_model_fixed_horizon_ev_2025-05_1/`
- no-cost no block sweep: `data/reports/backtests/20260628_010537_model_sweep_2025-05_1/`
- no-cost asia short block sweep: `data/reports/backtests/20260628_010537_model_sweep_2025-05_3/`
- cost no block sweep: `data/reports/backtests/20260628_010537_model_sweep_2025-05_2/`
- cost asia short block sweep: `data/reports/backtests/20260628_010537_model_sweep_2025-05/`
- candidate selection: `data/reports/backtests/20260628_010550_model_candidate_selection/`

## 結果

No block:

- adjusted pnl: `-57.6474`
- trades: `34`
- `actual_profit_barrier_miss_rate`: `0.5000`
- `actual_profit_barrier_miss_count`: `17`
- `actual_profit_barrier_miss_adjusted_pnl`: `-221.5828`
- cost `actual_profit_barrier_miss_adjusted_pnl`: `-225.4228`
- `predicted_profit_barrier_miss_rate`: `0.0000`

`short:session_regime=asia` block:

- adjusted pnl: `+83.0630`
- trades: `28`
- `actual_profit_barrier_miss_rate`: `0.464286`
- `actual_profit_barrier_miss_count`: `13`
- `actual_profit_barrier_miss_adjusted_pnl`: `-126.3004`
- cost `actual_profit_barrier_miss_adjusted_pnl`: `-129.2604`
- `predicted_profit_barrier_miss_rate`: `0.0000`

Candidate selection:

- `--max-direction-session-loss-per-fold 1000`
- `--max-predicted-profit-barrier-miss-rate 0`
- `--max-actual-profit-barrier-miss-rate 0.48`

この条件では、direction/session gateを実質的に緩めても、no block候補は `actual_profit_barrier_miss_rate_max_all=0.5000` で `actual_profit_barrier_miss_ok=False` になりeligibleから落ちた。blockあり候補は `actual_profit_barrier_miss_rate_max_all=0.464286` でeligibleに残った。

## 判断

actual barrier miss率は、PnLやdirection/session損失集中とは別の候補選択軸として機能する。

ただし今回の差は小さく、`0.48` という閾値をこのsmokeだけで採用してはいけない。実運用の選択条件にするには、validation fold全体でmiss率の台地を見る必要がある。

predicted miss率は今回 `0.0` だった。これは barrier threshold `0.40` を必須にした候補だからであり、miss率だけではcalibrationの過大評価は検出できない。次は predicted probability bucket別のactual hit rate、つまりcalibration curveを標準診断へ入れる。

## 検証

- `python3 -m py_compile src/trade_data/backtest.py`: OK
- `python3 -m unittest tests.test_backtest`: 28 tests OK
- `python3 -m unittest discover tests`: 64 tests OK
- `model-candidate-selection --help`: OK
- `model-sweep --help`: OK

## 更新: 2026-06-28 10:21 JST

次アクションとして、predicted probability bucket別actual hit rateを標準metricsへ追加した。

Report:

- `docs/reports/00025_2026-06-28_profit_barrier_calibration_candidate_gate.md`

主な結果:

- `model-sweep` metricsへ probability bucket別calibration列を追加した。
- `model-candidate-selection` に `--max-profit-barrier-calibration-overestimate` を追加した。
- 2025-05 smokeでは、blockあり候補の0.6-0.8 bucketが predicted mean `0.676661` に対してactual hit rate `0.428571` で、calibration overestimate `0.248089`。PnLは良いがbarrier probabilityは過大評価しているため、このgateは当面診断軸として扱う。
