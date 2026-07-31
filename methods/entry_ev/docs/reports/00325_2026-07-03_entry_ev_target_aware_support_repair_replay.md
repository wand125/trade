# Entry EV Target-Aware Support Repair Replay

日時: 2026-07-03 05:27 JST
更新日時: 2026-07-03 05:27 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00324の次アクションとして、00323 replayにtarget-aware repair utilityを接続した。
- `scripts/experiments/entry_ev_support_repair_horizon_replay.py` に `--selection-mode repair_score`、repair utility列、pred/actual/tail prefilterを追加した。
- actual-floor diagnosticでは、bestは available candidates / p0.5 / EV0 / tail0.3 / model-used yes。5本追加、added PnL `+32.3700`、combined total `+371.6610`。
- 00323 best totalの combined `+362.7000` からは `+8.9610` 改善したが、standard gateは通らない。month min `-0.6120`、remaining extra trades `3`、remaining month PnL hurdle `+1.4486`、blockersは `month_pnl_below_floor,role_trades_low,side_share_high`。
- pred-only対照では同じp0.5 / EV0 / tail0.3がfresh2024 2024-08 long 720m `-29.1360` を拾い、added PnLは `+3.2340`、month min `-19.8260`、role min `-20.8016` まで悪化した。
- 判断: target-aware repair utility infrastructureはaccepted。actual-floor runは上限診断としてaccepted。pred-only repair_score replayはpolicy候補としてreject。標準policyはNoTrade。

## Artifacts

- Updated script:
  - `scripts/experiments/entry_ev_support_repair_horizon_replay.py`
- Updated tests:
  - `tests/test_entry_ev_support_repair_horizon_replay.py`
- Main run, actual-floor diagnostic:
  - `data/reports/backtests/20260702_202623_20260703_entry_ev_00325_target_aware_support_repair_replay_00322_s2/`
- Control run, pred-only:
  - `data/reports/backtests/20260702_202706_20260703_entry_ev_00325_target_aware_support_repair_predonly_00322_s2/`

Outputs:

- `support_repair_horizon_replay_summary.csv`
- `support_repair_horizon_replay_monthly_metrics.csv`
- `support_repair_horizon_replay_additions.csv`
- `support_repair_horizon_replay_rejections.csv`

## Method

Added selection mode:

```text
repair_score =
  support_reduction_value
  + hv_chosen_pred_pnl
  - hv_chosen_pred_tail_loss_prob
```

Main diagnostic filters:

```text
selection_mode = repair_score
min_chosen_pred_pnl = 0
min_chosen_actual_pnl = 0
max_chosen_tail_prob = 0.3
```

Control filters:

```text
selection_mode = repair_score
min_chosen_pred_pnl = 0
max_chosen_tail_prob = 0.3
actual floor disabled
```

Important limitation:

```text
actual floor uses future realized PnL.
This is an upper-bound / error-analysis diagnostic, not executable policy evidence.
```

## Main Results

Best actual-floor diagnostic:

| scenario | added | added PnL | combined total | month min | role min | remaining extra trades | remaining PnL hurdle | blockers |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| available p0.5 EV0 tail0.3 model-used | `5` | `+32.3700` | `+371.6610` | `-0.6120` | `+0.5354` | `3` | `+1.4486` | month, role-trades, side-share |
| available p0.6 EV0 tail0.3 model-used | `5` | `+23.2000` | `+362.4910` | `-0.6120` | `+0.5354` | `3` | `+1.4486` | month, side-share |
| available p0.5 EV2 tail0.3 model-used | `4` | `+27.6800` | `+366.9710` | `-0.6120` | `+0.5354` | `4` | `+1.4486` | month, role-trades, side-share |

Best actual-floor additions:

| role | month | side | decision UTC | horizon | pred PnL | tail | repair score | actual |
|---|---|---|---|---:|---:|---:|---:|---:|
| hybrid2025_0912_external | 2025-10 | long | 2025-10-03 00:14 | 720 | `+7.1503` | `0.1520` | `+7.9983` | `+4.7300` |
| hybrid2025_0912_external | 2025-11 | short | 2025-11-10 01:34 | 60 | `+5.0987` | `0.2099` | `+5.8887` | `+9.4100` |
| refit2025_validation | 2025-07 | short | 2025-07-21 06:38 | 240 | `+1.7808` | `0.2601` | `+2.5207` | `+4.6900` |
| refit2025_validation | 2025-08 | long | 2025-08-14 16:27 | 720 | `+11.1635` | `0.1903` | `+11.9732` | `+1.1800` |
| refit2025_validation | 2025-08 | short | 2025-08-08 08:27 | 240 | `+2.3763` | `0.2607` | `+3.1157` | `+12.3600` |

Remaining worst months after best actual-floor:

| role | month | PnL | trades | long | short | side share |
|---|---|---:|---:|---:|---:|---:|
| fresh2024_validation | 2024-11 | `-0.6120` | `1` | `0` | `1` | `1.0000` |
| refit2025_validation | 2025-03 | `-0.4730` | `9` | `5` | `4` | `0.5556` |
| fresh2024_validation | 2024-03 | `-0.3636` | `1` | `0` | `1` | `1.0000` |
| refit2025_validation | 2025-07 | `+6.7724` | `8` | `7` | `1` | `0.8750` |

Pred-only control:

| scenario | added | added PnL | combined total | month min | role min | remaining extra trades | blockers |
|---|---:|---:|---:|---:|---:|---:|---|
| available p0.5 EV0 tail0.3 model-used | `6` | `+3.2340` | `+342.5250` | `-19.8260` | `-20.8016` | `2` | role, month, side-share |

Pred-only failure row:

| role | month | side | decision UTC | horizon | pred PnL | tail | repair score | actual |
|---|---|---|---|---:|---:|---:|---:|---:|
| fresh2024_validation | 2024-08 | long | 2024-08-22 03:39 | 720 | `+3.3056` | `0.2886` | `+4.0169` | `-29.1360` |

## Decision

Accepted:

- target-aware repair utility infrastructure
- repair_score mode with support reduction / predicted PnL / tail penalty
- pred/actual/tail prefilters for diagnostics
- 00324 refit2025 2025-07 candidate as a useful diagnostic target

Rejected:

- promoting actual-floor run to executable policy evidence
- promoting pred-only repair_score replay to policy candidate
- using pre-chosen horizon rows as the final target-aware repair mechanism
- treating remaining support count reduction as sufficient when month/role floor worsens

Standard policy remains NoTrade.

## Interpretation

The useful finding is not that actual-floor repair is tradable. It is that the repair objective can identify the right kind of target once bad realized candidates are removed. The gap is now narrower:

```text
Need a tradable proxy for "actual-floor safe" before support repair can be policy-like.
```

The current bottleneck is also more specific than 00323:

```text
The system chooses one horizon per row before repair utility sees it.
```

For example, p0.5 can see refit2025 2025-07 240m `+4.6900`, but pred-only still opens fresh2024 2024-08 720m `-29.1360`. This means the next repair layer should operate on row x horizon candidates directly, not only on `hv_chosen_horizon_minutes`.

## Next

1. Build row x horizon target-aware support replay using `support_repair_target_horizon_rows.csv` style inputs.
2. Score each row x horizon candidate by repair utility before collapsing to one horizon.
3. Add a learned/observable proxy for actual-floor safety; actual PnL remains diagnostic only.
4. Keep fresh2024 2024-03/2024-11 out of support repair until fallback/non-model and horizon-choice calibration are fixed.
5. Continue using 00317 repair target and standard admission blockers as pass/fail gates.

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_support_repair_horizon_replay.py tests/test_entry_ev_support_repair_horizon_replay.py`: OK
- `uv run python -m unittest tests.test_entry_ev_support_repair_horizon_replay`: OK
- 00325 actual-floor target-aware support repair replay: OK
- 00325 pred-only control replay: OK
