# Direction Session Candidate Gate

日時: 2026-06-28 09:51 JST
更新日時: 2026-06-28 09:51 JST

## 目的

`short:session_regime=asia` を手作業で見つけるのではなく、candidate selectionが `direction x session_regime` の損失集中を検出できるようにする。

前回の2025-04 / 2025-05 blindでは、blockなし候補が全体ではそこそこ取引していても、`short:asia` だけで約 `-100` の損失を作っていた。従来のside loss gateはlong/short全体しか見ないため、この局所的な壊れ方を検出しにくい。

## 実装

`model-policy` / `model-sweep` のmetricsに以下を追加した。

- `direction_session_adjusted_pnl_min`
- `worst_direction_session`
- `worst_direction_session_trade_count`

これは各tradeを `entry_decision_timestamp` でpredictionの `session_regime` にjoinし、`direction, session_regime` ごとに実現adjusted pnlを集計して、最も悪いグループを記録する。

`model-candidate-selection` に以下を追加した。

```text
--max-direction-session-loss-per-fold
```

この値を超える損失集中がある候補は `direction_session_loss_ok=False` になり、eligibleから落ちる。

後方互換:

- 古いsweep CSVに新列がない場合は `direction_session_adjusted_pnl_min=inf` として扱い、既存評価を壊さない。
- `session_regime` を含まない古いpredictionでは、診断値は空になる。

## Smoke Check

2025-05の同一候補で、`short:session_regime=asia` blockあり/なしを比較した。

共通条件:

- model: `experiments/20260628_003756_full_fixed_horizon_blind_2025_05_barrier_prob_p1_l1p2/`
- policy: `fixed_horizon_ev`
- entry: `0`
- short offset: `6`
- side margin: `1`
- max wait regret: `4`
- min entry rank: `0.5`
- barrier threshold: `0.40`
- extra margin: `session_regime=asia:5,session_regime=rollover:5`

Artifacts:

- no-cost no block: `data/reports/backtests/20260628_005016_model_sweep_2025-05/`
- no-cost asia short block: `data/reports/backtests/20260628_005016_model_sweep_2025-05_1/`
- cost no block: `data/reports/backtests/20260628_005015_model_sweep_2025-05_1/`
- cost asia short block: `data/reports/backtests/20260628_005015_model_sweep_2025-05/`
- candidate selection: `data/reports/backtests/20260628_005032_model_candidate_selection/`

No block:

- adjusted pnl: `-57.6474`
- short pnl: `-77.4874`
- `direction_session_adjusted_pnl_min`: `-100.5254`
- `worst_direction_session`: `short:asia`
- cost `direction_session_adjusted_pnl_min`: `-103.8054`
- candidate selection: `direction_session_loss_ok=False`, `eligible=False`

Asia short block:

- adjusted pnl: `+83.0630`
- short pnl: `+63.2230`
- `direction_session_adjusted_pnl_min`: `+19.8400`
- `worst_direction_session`: `long:ny_late`
- cost `direction_session_adjusted_pnl_min`: `+17.4840`
- candidate selection: `direction_session_loss_ok=True`, `eligible=True`

Gate条件:

- `--max-direction-session-loss-per-fold 45`

## 判断

実装は目的に合っている。

これで `short:asia` のような局所損失を、blindを見た後の手作業ではなく、validation sweepの候補選択基準として扱える。

注意点:

- `direction_session_adjusted_pnl_min` は実現tradeベースなので、trade数が極端に少ない候補では不安定になりうる。
- したがって `min-trades-per-fold`、side loss、cost drop、plateau supportと併用する。
- 次は `predicted/actual profit barrier miss` もcandidate selectionへ追加し、損失集中の理由をさらに分解する。

## Verification

- `python3 -m py_compile src/trade_data/backtest.py`: OK
- `python3 -m unittest tests.test_backtest`: 26 tests OK
- `python3 -m unittest discover tests`: 62 tests OK
- `python3 -m trade_data.backtest model-candidate-selection --help`: OK
- `python3 -m trade_data.backtest model-sweep --help`: OK
- `git diff --check`: OK
