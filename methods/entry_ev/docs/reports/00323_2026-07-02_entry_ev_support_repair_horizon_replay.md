# Entry EV Support Repair Horizon Replay

日時: 2026-07-02 21:40 JST
更新日時: 2026-07-02 21:40 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00322の次アクションとして、q90 + one-failed broad horizon viability outputを00314 best branchのsupport-repairへ接続した。
- `scripts/experiments/entry_ev_support_repair_horizon_replay.py` を追加し、00314 best branchの既存stateful trade pathへ、00322 horizon choicesを必要side・必要本数・既存trade非重複制約つきで追加する診断を作った。
- best totalは available candidates / prob `0.6` / EV `0` / tail `0.3` / model-used yes。5本追加、added PnL `+23.4090`、combined total `+362.7000`。
- ただしstandard gateは通らない。month minは `-0.6120`、remaining extra tradesは `3`、remaining month PnL hurdleは `+1.4486`、blockersは `month_pnl_below_floor,side_share_high`。
- repair targetを最も減らす設定は available candidates / prob `0.6` / EV `-2` / tail `0.3`。6本追加でremaining extra tradesは `2` まで減るが、refit2025 2025-07 short `-4.9356` を拾い、month minは `-2.8532` へ悪化する。
- 判断: support-repair horizon replay infrastructureはaccepted。00322 s2はsupport repairの一部を埋めるが、標準policy / support overlayとしてはreject。標準policyはNoTrade。

## Artifacts

- New script:
  - `scripts/experiments/entry_ev_support_repair_horizon_replay.py`
- New tests:
  - `tests/test_entry_ev_support_repair_horizon_replay.py`
- Run:
  - `data/reports/backtests/20260702_123930_20260702_entry_ev_00323_support_repair_horizon_replay_00322_s2/`

Outputs:

- `support_repair_horizon_replay_summary.csv`
- `support_repair_horizon_replay_monthly_metrics.csv`
- `support_repair_horizon_replay_additions.csv`
- `support_repair_horizon_replay_rejections.csv`

## Method

Base branch:

```text
00314 fixed60 margin w5 position-quality overlay
candidate = q95_sg95_rank90_floor5_side_regime_session_month
variant contains = loss_exit30_cd15__holdext_isolated_large_loss_long_t-5_h720
entry_block_rule = long_range_normal_ny_fixed60_pred_gt0
base total = +339.2910
```

Candidate source:

```text
00322 s2 q90 + one-failed broad horizon viability
choices = broad_horizon_viability_threshold_choices.csv
row scopes = available_candidates, greedy_selected
```

Replay rule:

```text
for each threshold scenario:
  keep only chosen horizon rows
  require side == needed_side
  cap additions by extra_side_needed for each role/month/side
  reject additions that overlap existing stateful trades in the same role
  score order = hv_chosen_score desc, actual PnL desc, decision time asc
  update monthly PnL, trade count, side share, repair target
```

This is stateful-compatible overlay diagnostics, not a full stateful replay over the complete candidate stream. It can prove that a proposed addition does not overlap the existing path, but it does not prove what a full re-ranked policy would have chosen.

## Main Results

Best scenarios:

| scenario | added | added PnL | combined total | month min | role min | remaining extra trades | remaining PnL hurdle | blockers |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| available p0.6 EV0 tail0.3 model-used | `5` | `+23.4090` | `+362.7000` | `-0.6120` | `+0.5354` | `3` | `+1.4486` | month, side-share |
| available p0.6 EV2 tail0.3 model-used | `3` | `+18.4790` | `+357.7700` | `-0.7200` | `+0.5354` | `5` | `+2.1686` | month, role-trades, side-share |
| available p0.6 EV-2 tail0.3 model-used | `6` | `+18.4734` | `+357.7644` | `-2.8532` | `+0.5354` | `2` | `+4.3018` | month, side-share |
| greedy p0.6 EV-2 tail0.3 model-used | `4` | `+20.5430` | `+359.8340` | `-0.6120` | `+0.5354` | `4` | `+1.4486` | month, side-share |

Best total additions, available p0.6 EV0 tail0.3 model-used:

| role | month | side | horizon | actual PnL |
|---|---|---|---:|---:|
| refit2025_validation | 2025-08 | long | 720 | `+1.3890` |
| hybrid2025_0912_external | 2025-10 | long | 720 | `+4.7300` |
| refit2025_validation | 2025-08 | short | 240 | `+12.3600` |
| hybrid2025_0912_external | 2025-11 | short | 60 | `+1.9800` |
| fresh2024_validation | 2024-08 | long | 60 | `+2.9500` |

Remaining worst months after best total:

| role | month | PnL | trades | long | short | side share |
|---|---|---:|---:|---:|---:|---:|
| fresh2024_validation | 2024-11 | `-0.6120` | `1` | `0` | `1` | `1.0000` |
| refit2025_validation | 2025-03 | `-0.4730` | `9` | `5` | `4` | `0.5556` |
| fresh2024_validation | 2024-03 | `-0.3636` | `1` | `0` | `1` | `1.0000` |
| refit2025_validation | 2025-07 | `+2.0824` | `7` | `7` | `0` | `1.0000` |

Coverage diagnosis:

- EV>=0 / p0.6 / tail0.3 passes no candidates for `fresh2024 2024-03`, `fresh2024 2024-11`, or `refit2025 2025-07`.
- EV-2 adds `refit2025 2025-07 short`, reducing side-share repair count, but the chosen 60m result is `-4.9356` and makes month floor worse.
- Therefore, the broad horizon head can repair some thin months, but it still lacks safe candidates for the remaining support-limited months.

## Decision

Accepted:

- support-repair horizon replay infrastructure
- capping additions by `extra_side_needed`
- rejecting additions that overlap existing stateful trades
- reporting repair-target progress separately from total PnL

Rejected:

- promoting 00322 s2 support additions to standard policy
- using EV-2 support additions to fix side-share when they worsen month floor
- treating this overlay diagnostic as full candidate-stream stateful replay
- optimizing total PnL while remaining repair target / standard blockers are unresolved

Standard policy remains NoTrade.

## Next

1. Diagnose missing target coverage for `fresh2024 2024-03`, `fresh2024 2024-11`, and `refit2025 2025-07`.
2. Add target-aware selection that optimizes per-role/month repair utility, not just `hv_chosen_score`.
3. For refit2025 2025-07, require non-negative realized/expected floor contribution before allowing side-share repair additions.
4. Re-run support repair after adding a target-specific utility: `repair_score = support_reduction_value + expected_pnl - tail_penalty - overlap_cost`.
5. Keep 00317 repair target as the pass/fail gate. Total PnL improvement alone is not standard-readiness progress.

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_support_repair_horizon_replay.py tests/test_entry_ev_support_repair_horizon_replay.py`: OK
- `uv run python -m unittest tests.test_entry_ev_support_repair_horizon_replay`: OK
- 00323 support repair horizon replay run: OK
