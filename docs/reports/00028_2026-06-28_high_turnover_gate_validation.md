# High Turnover Gate Validation

日時: 2026-06-28 11:14 JST
更新日時: 2026-06-28 11:14 JST

## 目的

`short exposure concentration` と support-aware barrier gateを、2025-06を見た後のsmokeだけでなく、validation 4ヶ月で比較する。

対象は次の4 validation months。

- `2024-07`
- `2024-09`
- `2024-11`
- `2025-01`

2025-06は既に見た月なので、今回はblindではなく「既知の失敗月への回帰チェック」としてだけ使う。

## 入力

- model: `experiments/20260628_013141_full_fixed_horizon_blind_2025_06_barrier_prob_p1_l1p2/`
- validation predictions: `predictions_valid.parquet`
- known 2025-06 predictions: `predictions_test.parquet`
- evaluation multiplier: profit `1.0`, loss `1.20`
- cost-aware case: spread `0.1`, slippage `0.05`, delay `0`

## 実験1: 固定候補周辺grid

まず、前回候補に近い設定で `short_entry_threshold_offset`, `side_margin`, `exit_threshold`, `profit_barrier_threshold` だけを小さく広げた。

結果:

- candidate selection rows: `80`
- `min-trades-per-fold=10` を満たす候補: `0`
- min-tradesを緩めた場合の最大 `trade_count_min_base`: `5`

判断:

- 前回候補周辺は、validation 4ヶ月で月10trades条件を満たせない。
- gate以前に `min_entry_rank=0.5`, `max_wait_regret=4`, barrier threshold中心の設計が薄すぎる。

Artifacts:

- sweeps: `data/reports/backtests/20260628_020055_model_sweep_2024-07/` から `data/reports/backtests/20260628_020416_model_sweep_2025-01/`
- comparison: `data/reports/backtests/20260628_020416_model_sweep_candidate_gate_comparison.csv`

## 実験2: High-Turnover Grid

trade数不足を切り分けるため、以下を追加した。

- `min_entry_rank`: `0`, `0.5`
- `max_wait_regret`: `4`, `inf`
- `profit_barrier_threshold`: `0.0`, `0.2`
- `side_block_rules`: none, `short:session_regime=asia`
- `short_entry_threshold_offset`: `0`, `4`, `8`
- `side_margin`: `0`, `1`

`min-trades-per-fold=10` かつPnL条件を緩めた場合:

| condition | eligible |
|---|---:|
| no short-share gate | 48 |
| `max-short-trade-share=0.85` | 48 |
| `max-short-trade-share=0.75` | 48 |
| `max-short-trade-share=0.65` | 48 |

Top relaxed candidate:

| side block | short offset | side margin | min entry rank | max wait regret | barrier threshold | base min pnl | cost min pnl | min trades | short share max | smoothed miss | smoothed calibration |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| none | 8 | 1 | 0.5 | 4 | 0.0 | 34.5186 | 20.6606 | 56 | 0.142857 | 0.500000 | 0.750000 |

Artifacts:

- sweeps: `data/reports/backtests/20260628_020644_model_sweep_2024-07/` から `data/reports/backtests/20260628_021001_model_sweep_2025-01/`
- comparison: `data/reports/backtests/20260628_021001_high_turnover_candidate_gate_comparison.csv`

## 実験3: Forced Exit And Direction/Session Gate

strictに `max-forced-exit-rate=0` を置くと、上位候補も落ちる。上位候補の forced exit rate は約 `0.03-0.04` だった。

24h強制決済は仕様上あり得るため、診断として `max-forced-exit-rate=0.05` を試した。

| condition | eligible | note |
|---|---:|---|
| direction/session loss <= 45 | 0 | `-51.5902` のfoldで落ちる |
| direction/session loss <= 60 | 5 | high-turnover候補が残る |
| short share <= 0.65, dir loss <= 60 | 5 | top候補は変わらない |
| smoothed miss <= 0.55 | 5 | top候補は変わらない |
| smoothed miss <= 0.50 | 1 | top候補1つだけに絞られる |
| smoothed calibration <= 0.70 | 2 | asia block候補へ寄る |
| smoothed calibration <= 0.60 | 1 | asia block候補だけが残る |

暫定的に良い候補:

| candidate | side block | short offset | side margin | min entry rank | max wait regret | barrier threshold | base min pnl | cost min pnl | min trades | forced max | dir/session min | short share max | smoothed miss | smoothed calibration |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| A | none | 8 | 1 | 0.5 | 4 | 0.0 | 34.5186 | 20.6606 | 56 | 0.035714 | -51.5902 | 0.142857 | 0.500000 | 0.750000 |
| B | `short:session_regime=asia` | 8 | 1 | 0.0 | 4 | 0.0 | 27.6424 | 12.5964 | 52 | 0.038462 | -51.5902 | 0.076923 | 0.535211 | 0.500000 |

Artifacts:

- `data/reports/backtests/20260628_021102_high_turnover_forced_direction_gate_comparison.csv`
- A selection: `data/reports/backtests/20260628_021208_model_candidate_selection/`
- B selection: `data/reports/backtests/20260628_021216_model_candidate_selection/`

## 2025-06 Known-Month Regression

2025-06は既に見た月なので、これはblindではない。過去の失敗モードが再発するかだけ確認した。

| candidate | case | adjusted pnl | trades | profit factor | max drawdown | forced exit rate | short pnl | short share | worst direction/session | smoothed miss | smoothed calibration |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|
| A no block | base | 48.3378 | 52 | 1.2446 | 73.0372 | 0.076923 | -11.3422 | 0.25 | short:london -27.4536 | 0.388889 | 0.357143 |
| A no block | cost | 37.0572 | 52 | 1.1826 | 77.7572 | 0.076923 | -14.2222 | 0.25 | short:london -28.3336 | 0.388889 | 0.357143 |
| B asia block | base | -18.6904 | 50 | 0.9095 | 118.8928 | 0.080000 | -82.3312 | 0.24 | short:london -82.3312 | 0.403846 | 0.538462 |
| B asia block | cost | -29.4530 | 50 | 0.8605 | 123.6128 | 0.080000 | -84.9312 | 0.24 | short:london -84.9312 | 0.403846 | 0.538462 |

Artifacts:

- A base: `data/reports/backtests/20260628_021314_model_fixed_horizon_ev_2025-06/`
- A cost: `data/reports/backtests/20260628_021408_model_fixed_horizon_ev_2025-06/`
- B base: `data/reports/backtests/20260628_021409_model_fixed_horizon_ev_2025-06/`
- B cost: `data/reports/backtests/20260628_021411_model_fixed_horizon_ev_2025-06/`
- comparison: `data/reports/backtests/20260628_021217_known_2025_06_regression_candidates.csv`

## 判断

`max-short-trade-share` は hard gateとして採用しやすい。今回の high-turnover top候補は `0.142857` で、`0.65`, `0.75`, `0.85` のどれでも残る。暫定値は `0.65` がよい。

`max-smoothed-actual-profit-barrier-miss-rate` は `0.55` なら候補集合を壊さず、`0.50` だと1候補に絞りすぎる。暫定値は `0.55`。

`max-smoothed-profit-barrier-calibration-overestimate` は hard gateにしない。`0.60` まで締めるとB候補だけになり、2025-06既知月でLondon short崩れを再発した。calibrationは診断・tie-breakとして使い、直接hard gateにはしない。

`max-forced-exit-rate=0` は現時点では厳しすぎる。24h強制決済は仕様上許されるため、候補選定では暫定 `0.05` とし、forced exitが損失源になっていないかを別途見る。

`max-direction-session-loss-per-fold=45` は候補を全滅させる。`60` なら5候補が残る。暫定 `60` とし、次の未見月で妥当性を見る。

現時点の暫定選定基準:

- `min-trades-per-fold=10`
- `max-forced-exit-rate=0.05`
- `max-drawdown=100`
- `min-base-adjusted-pnl-per-fold=0`
- `min-cost-adjusted-pnl-per-fold=0`
- `max-side-loss-per-fold=100`
- `max-direction-session-loss-per-fold=60`
- `max-short-trade-share=0.65`
- `max-smoothed-actual-profit-barrier-miss-rate=0.55`
- smoothed calibrationはhard gateにしない

この基準は `docs/decisions/0007_high_turnover_gate_selection.md` に固定記録した。

暫定候補A:

- policy: `fixed_horizon_ev`
- entry threshold: `0`
- short entry threshold offset: `8`
- side margin: `1`
- min entry rank: `0.5`
- max wait regret: `4`
- require profit barrier: yes
- profit barrier threshold: `0.0`
- extra side margin: `session_regime=asia:5,session_regime=rollover:5`
- side block: none

注意:

- profit barrier threshold `0.0` は、barrier確率gateが実質フィルタとして働いていない。これは「高turnover化でvalidationは改善したが、barrier probability targetの選別力が弱い」という警告でもある。
- この基準は未見月を見る前に固定済み。次は2025-07以降でblind評価する。
