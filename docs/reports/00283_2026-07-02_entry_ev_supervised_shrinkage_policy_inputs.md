# Entry EV Supervised Shrinkage Policy Inputs

日時: 2026-07-02 11:18 JST
更新日時: 2026-07-02 11:18 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00282の次アクションとして、selected-trade supervised shrinkage headをprediction row側へ戻すpolicy input生成を実装した。
- `scripts/experiments/entry_ev_supervised_shrinkage_policy_inputs.py` を追加した。selected tradesの実現PnL/factorを対象月より前だけで学び、各prediction parquetのlong/short両側へ `pred_supervised_shrink_factor_*_best_adjusted_pnl` とquantile列を付与する。
- raw `loss_exit30_cd15` と同じ6 familyへ factor shrinkage scoreを付与し、`loss_exit30_cd15` dynamic exit cooldownでstateful replayした。
- 結果は「totalは伸びるがtailが悪い」。q95 no-floor + `loss_exit30_cd15` は total `+219.7158`, 899 tradesまで伸びたが、month min `-35.1586` で raw cd15 benchmarkの `-6.8324` より悪い。
- q96-q99近傍sweepでも安定した台地は出ない。q99は month min `-13.8816` まで縮むが role min `-12.9278` でNoTrade-first gateは通らない。
- 判断: supervised shrinkage policy input infrastructureはaccepted。supervised shrinkage score replacementはまだreject。次はstandalone scoreではなく、raw cd15 candidateを残したうえで補助featureとしてmeta selector / downside-weighted headへ入れる。

## Artifacts

- Script:
  - `scripts/experiments/entry_ev_supervised_shrinkage_policy_inputs.py`
- Test:
  - `tests/test_entry_ev_supervised_shrinkage_policy_inputs.py`
- Policy input run:
  - `data/reports/backtests/20260702_020553_20260702_entry_ev_supervised_shrinkage_factor_policy_inputs_s1/`
- Replay:
  - `data/reports/backtests/20260702_020652_20260702_entry_ev_supervised_shrinkage_factor_exit_replay_s1/`
- Quantile sweep:
  - `data/reports/backtests/20260702_021724_20260702_entry_ev_supervised_shrinkage_factor_quantile_sweep_s1/`

## Method

Training target:

```text
target_mode = factor
y = adjusted_pnl / raw_pred_ev
clipped to [-1, 1]
score = raw_pred_ev * predicted_factor
```

Chronology:

```text
target month M:
  train = selected raw cd15 trades with month < M
  apply = all prediction rows in month M, both long and short sides
```

Generated columns:

```text
pred_supervised_shrink_factor_long_best_adjusted_pnl
pred_supervised_shrink_factor_short_best_adjusted_pnl
pred_supervised_shrink_factor_selected_score_pct_*
pred_supervised_shrink_factor_side_gap_pct_*
pred_supervised_shrink_factor_selected_entry_rank_pct_*
```

Replay settings:

```text
score_kind = supervised_shrink_factor
variants = base, loss_exit30_cd15
candidates =
  q95_sg95_rank90_side_regime_session_month
  q95_sg95_rank90_floor5_side_regime_session_month
  q99_sg95_rank90_side_regime_session_month
profit_multiplier = 1.0
loss_multiplier = 1.2
max_hold = 24h
```

## Policy Input Behavior

Fold summary:

| month range | behavior |
|---|---|
| 2024-01 | no prior, default score `0.0` |
| 2024-02/03 | only 1 prior month, below `min_train_months=2`, default score `0.0` |
| 2024-04 onward | model used |

Score scale:

| example | base q95 | shrink q95 |
|---|---:|---:|
| fresh2024 2024-04 | `15.6104` | `0.6049` |
| fresh2024 2024-11 | `15.8602` | `1.8368` |
| refit2025 2025-10 | `29.0069` | `4.7080` |
| hybrid2025_0912 2025-12 | `37.6429` | `5.2463` |

Reading:

- shrinkage scoreはraw EVの過大scaleを強く縮める。
- side switch shareが高く、fresh2024 2024-12は `0.6749`、refit2025 2025-01は `0.5711`。
- scale correctionはできているが、side/order decisionが大きく変わるため、直接score replacementは危険。

## Stateful Replay

Main replay:

| variant | candidate | total pnl | role min | month min | trades | decision |
|---|---|---:|---:|---:|---:|---|
| `loss_exit30_cd15` | q95 no-floor | `+219.7158` | `0.0000` | `-35.1586` | `899` | NoTrade |
| `loss_exit30_cd15` | q95 floor5 | `+45.5674` | `0.0000` | `-53.4046` | `44` | NoTrade |
| `loss_exit30_cd15` | q99 no-floor | `+113.8160` | `-12.9278` | `-13.8816` | `507` | NoTrade |
| `base` | q95 no-floor | `-60.8218` | `-137.0278` | `-41.8236` | `847` | NoTrade |

Worst months for q95 no-floor + `loss_exit30_cd15`:

| family | month | pnl | trades |
|---|---|---:|---:|
| refit2025 | 2025-10 | `-35.1586` | `33` |
| fresh2024 | 2024-12 | `-14.1778` | `48` |
| refit2025 | 2025-02 | `-5.7536` | `21` |
| hgb2024_0306 | 2024-05 | `-5.2860` | `31` |
| hybrid2025_0912 | 2025-09 | `-4.1970` | `15` |

Reading:

- q95 no-floor is promising by total, but it worsens the exact gate we are trying to protect: month floor.
- raw cd15 benchmark remains stronger on tail: total `+118.6900`, month min `-6.8324`, positive roles `6/6`.
- q95 no-floor total improvement is not enough to override month floor degradation.

## Quantile Sweep

q96-q99 no-floor with `loss_exit30_cd15`:

| candidate | total pnl | role min | month min | trades |
|---|---:|---:|---:|---:|
| q96 | `+192.4624` | `0.0000` | `-38.1026` | `840` |
| q97 | `+129.0388` | `-3.4448` | `-25.5882` | `770` |
| q98 | `+94.2870` | `-16.0760` | `-22.7082` | `680` |
| q99 | `+113.8160` | `-12.9278` | `-13.8816` | `507` |

Reading:

- q95/q96 totalは高いがtailが悪い。
- q99はtailを縮めるが、role minはまだ負。
- 近傍に「安定した台地」は見えない。

## Decision

Accepted:

- supervised shrinkage prediction-row policy input generation
- long/short side-row application with chronological selected-trade training
- quantile columns for `supervised_shrink_factor`

Rejected:

- supervised shrinkage score replacement as the main policy score
- q95/q96 no-floor rescue based on high total PnL
- floor5 reuse on shrunk score scale

Standard policy remains NoTrade.

Raw `loss_exit30_cd15` remains the fixed diagnostic benchmark.

## Next

1. Keep raw cd15 entry score path as baseline and add supervised shrinkage outputs as auxiliary features.
2. Train a downside-weighted meta selector that blocks only high downside / low realized-EV rows, instead of replacing the main score.
3. Add explicit constraints for month floor and role floor during selector evaluation.
4. Investigate refit2025 2025-10 and fresh2024 2024-12 as shrinkage-score side-switch failure cases, without static-blacklisting those months.

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_supervised_shrinkage_policy_inputs.py tests/test_entry_ev_supervised_shrinkage_policy_inputs.py`: OK
- `uv run python -m unittest tests.test_entry_ev_supervised_shrinkage_policy_inputs`: OK
- supervised shrinkage factor policy input generation: OK
- supervised shrinkage factor replay: OK
- q96-q99 quantile sweep: OK
