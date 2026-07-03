# Entry EV Tail Support Gated Horizon Choice

日時: 2026-07-03 09:49 JST
更新日時: 2026-07-03 09:49 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00341の次アクションとして、tail-loss headを常にscore penaltyへ入れるのではなく、tail head側のtrain supportが十分な時だけpenaltyを有効化するscore modeを追加した。
- `entry_ev_broad_prior_horizon_choice_replay.py` に `pnl_tail_support_gated` と `pnl_delta_tail_support_gated` を追加し、`ranker_pred_tail_loss_prob_train_months / train_rows / train_rows_full` をscored examplesとprediction rowsへ出すようにした。
- gateは同月actualやfold AUCを使わない。使うのは、そのtarget monthより前にtail headが学習に使えた月数・行数だけ。
- mintrain1 + tail gate `2 months / 200 rows` では、fresh03 available choicesの `pnl_delta_tail` が `-111.0260` だったのに対し、`pnl_delta_tail_support_gated` は `-19.2310` まで改善した。greedy 1 decisionも `-14.1240 -> -3.5280` に改善。
- ただしfull replayではbestは従来の `pnl` のcombined `+400.1440` のまま。`pnl_delta_tail_support_gated` はbest combined `+389.5310`、`pnl_tail_support_gated` は `+378.7510` で、標準候補にはならない。
- strict gate `10 months / 10000 rows` もfull replayを改善せず、2024-08のavailable horizon choiceは `-46.3536 -> -99.7540` へ悪化した。
- 判断: tail-support-gated score modeはaccepted infrastructure。train support countだけのtail gatingはpolicy候補としてreject。標準policyはNoTrade。

## Artifacts

Changed script:

- `scripts/experiments/entry_ev_broad_prior_horizon_choice_replay.py`

Changed tests:

- `tests/test_entry_ev_broad_prior_horizon_choice_replay.py`

Runs:

- `data/reports/backtests/20260703_004539_20260703_entry_ev_00342_tail_support_gated_horizon_choice/`
- `data/reports/backtests/20260703_004857_20260703_entry_ev_00342_tail_support_gated_horizon_choice_strict/`

## Method

New score modes:

```text
pnl_tail_support_gated
  = pnl - tail_weight * tail_prob
    only when tail_train_months >= threshold and tail_train_rows >= threshold

pnl_delta_tail_support_gated
  = pnl + delta_weight * positive_delta_vs_60 + beats60_weight * beats60_prob
    - tail_weight * tail_prob
    only when tail train support passes the same gate
```

The first run used:

```text
min_train_months=1
min_train_rows=50
tail_penalty_min_train_months=2
tail_penalty_min_train_rows=200
max_leaf_nodes=4
l2_regularization=5.0
max_iter=80
```

The strict sensitivity used:

```text
tail_penalty_min_train_months=10
tail_penalty_min_train_rows=10000
```

Actual PnL is not used in the gate. Actual PnL remains evaluation/oracle/teacher only.

## Results

### Target-Level Horizon Choice

For `fresh2024_validation 2024-03 long`, all three horizons have only one prior train month for the tail head. The support gate disables the tail penalty here.

| score mode | row scope | chosen actual | chosen 60m | chosen 240m | chosen 720m | reading |
|---|---|---:|---:|---:|---:|---|
| `pnl` | available | `-69.6140` | `10` | `7` | `0` | PnL signal partially picks 240m |
| `pnl_delta_tail` | available | `-111.0260` | `14` | `3` | `0` | low-support tail penalty pushes back toward 60m |
| `pnl_delta_tail_support_gated` | available | `-19.2310` | `6` | `11` | `0` | support gate recovers much of the 240m signal |
| `pnl_delta_tail` | greedy | `-14.1240` | `1` | `0` | `0` | tail penalty chooses 60m |
| `pnl_delta_tail_support_gated` | greedy | `-3.5280` | `0` | `1` | `0` | support gate chooses 240m |

This confirms the 00341 diagnosis: early support tail-loss penalty can be actively harmful. However, this is still target-level, not a complete policy result.

### Full Replay

Best scenario by score mode under the `2 months / 200 rows` gate:

| score mode | added | added PnL | combined total | month min | role min | remaining extra | blockers |
|---|---:|---:|---:|---:|---:|---:|---|
| `pnl` | `5` | `+60.8530` | `+400.1440` | `-0.6120` | `+0.5354` | `3` | `month_pnl_below_floor,role_trades_low,side_share_high` |
| `pnl_delta_tail_support_gated` | `5` | `+50.2400` | `+389.5310` | `-0.6120` | `+0.5354` | `3` | same |
| `pnl_delta_tail` | `5` | `+50.2400` | `+389.5310` | `-0.6120` | `+0.5354` | `3` | same |
| `pnl_tail_support_gated` | `3` | `+39.4600` | `+378.7510` | `-0.7200` | `+0.5354` | `5` | same |

The support-gated delta-tail score does not beat the plain PnL score. The main loss versus `pnl` is visible in the selected additions:

| role/month/side | `pnl` horizon / actual | gated delta-tail horizon / actual | delta |
|---|---:|---:|---:|
| `hybrid2025_0912_external 2025-10 long` | `720m / +10.9530` | `60m / +0.3400` | `-10.6130` |

### Strict Gate Sensitivity

The strict gate does not improve the full replay:

| score mode | best combined | month min | reading |
|---|---:|---:|---|
| `pnl_delta_tail_support_gated`, strict | `+389.5310` | `-0.6120` | same full-replay best as loose gate |
| `pnl_tail_support_gated`, strict | `+378.7510` | `-0.7200` | same as loose gate |

It also worsens target-level 2024-08 available choices:

| score mode | 2024-08 available actual |
|---|---:|
| `pnl` | `-46.3536` |
| `pnl_delta_tail_support_gated`, loose | `-46.3536` |
| `pnl_delta_tail_support_gated`, strict | `-99.7540` |

This means train support count alone is too crude. It protects one-month fresh03 from a bad tail penalty, but can remove useful tail signal elsewhere or leave other overestimate problems untouched.

## Interpretation

- The local fresh03 failure in 00341 is real: low-support tail penalty can suppress the correct 240m horizon.
- A train-support gate is a useful safety feature and diagnostic hook, but not enough to produce a robust policy.
- Full replay still prefers plain PnL because tail/delta composition changes profitable horizon choices, especially the `hybrid2025_0912_external 2025-10 long` 720m winner.
- The next step should not be a stronger count gate. It should be prior/OOB reliability calibration for tail and delta heads, plus candidate generation for missing months.

## Decision

- Tail support metadata and gated score modes: accepted infrastructure.
- `pnl_delta_tail_support_gated`: useful diagnostic, not policy.
- `pnl_tail_support_gated`: reject as policy.
- Strict train-support gate: reject as policy.
- Standard policy remains NoTrade.

## Next

1. Build prior/OOB reliability calibration for tail-loss and delta heads instead of using train support count alone.
2. Diagnose why `hybrid2025_0912_external 2025-10 long` needs 720m under `pnl` but is shortened under delta/tail scoring.
3. Keep fresh03 as the target for low-support tail calibration, but do not optimize only for that month.
4. Continue candidate generation for `fresh2024 2024-11` and `refit2025 2025-03`.

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_broad_prior_horizon_choice_replay.py tests/test_entry_ev_broad_prior_horizon_choice_replay.py tests/test_docs_reports.py`: OK
- `uv run python -m unittest tests.test_entry_ev_broad_prior_horizon_choice_replay tests.test_docs_reports`: OK
- 00342 loose tail-support-gated replay: OK
- 00342 strict tail-support-gated replay: OK
