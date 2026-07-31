# Entry EV Broad Duration Prior Repair Replay

日時: 2026-07-03 06:11 JST
更新日時: 2026-07-03 06:11 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00327の次アクションとして、support-repair対象行だけでなく00322 s2のbroad candidate universeからduration risk priorを作り、row x horizon support repairへ接続した。
- `scripts/experiments/entry_ev_broad_duration_prior_repair_replay.py` を追加した。target monthより前のbroad train rowsだけから、context別のhorizon PnL、60m比delta、tail-loss率、60m比underperform率を作り、`repair_duration_risk_score` として `repair_score` へ追加ペナルティできる。
- 00322 s2を `--write-train-rows` で再実行し、9697 broad train rowsを保存した。
- broad duration priorはfresh2024 2024-08の悪い720mを事前に警告できた。同rowの `side,combined_regime,session_regime,near_miss_bucket` priorは48 rows / 6 monthsで、60m mean `+0.9061`、240m mean `+1.7885`、720m mean `-3.4993`、720m delta vs 60m `-4.4053`、720m tail-loss rate `0.4145`。
- ただしfull replayではcurrent direct prior penaltyは00326 fixed hpen0.25に届かない。bestは added PnL `+23.7960`、combined `+363.0870`、month min `-0.6120`、remaining extra trades `3`。
- p0.4系ではrisk weight `0.5` 以上でfresh2024 2024-08を720m `-29.1360` から60m `+2.9500` へ切り替えられるが、refit2025 2025-07などの勝ち候補も削るため、added PnLは `+16.6340` に留まった。
- 結論: broad duration prior infrastructureはaccepted。current direct penaltyはpolicy候補としてreject。標準policyはNoTrade。

## Artifacts

- New script:
  - `scripts/experiments/entry_ev_broad_duration_prior_repair_replay.py`
- Updated script:
  - `scripts/experiments/entry_ev_support_repair_horizon_replay.py`
- New tests:
  - `tests/test_entry_ev_broad_duration_prior_repair_replay.py`
- 00322 s2 train rows re-run:
  - `data/reports/backtests/20260702_210343_20260703_entry_ev_00328_broad_horizon_viability_s2_trainrows/`
- Composite duration risk replay:
  - `data/reports/backtests/20260702_210841_20260703_entry_ev_00328_broad_duration_prior_repair_replay_s2/`
- Tail-only duration risk replay:
  - `data/reports/backtests/20260702_211059_20260703_entry_ev_00328_broad_duration_prior_repair_replay_tailonly_s2/`

## Method

For each row x horizon candidate:

```text
prior rows = broad_train_rows where month < target_month
context hierarchy =
  side,combined_regime,session_regime,near_miss_bucket
  side,combined_regime,session_regime
  side,combined_regime
  side,session_regime
  combined_regime,session_regime
  side
  global
```

The first context with enough prior support is used, then shrunk toward global prior.

Composite risk score:

```text
risk =
  max(0, -prior_horizon_mean_pnl)
  + max(0, -prior_horizon_delta_vs_60m_mean)
  + 5.0 * prior_horizon_tail_loss_rate
```

Tail-only diagnostic:

```text
risk = 5.0 * prior_horizon_tail_loss_rate
```

Replay score:

```text
repair_score =
  support_reduction
  + predicted_pnl
  - predicted_tail_prob
  - duration_risk_weight * broad_duration_prior_risk
```

No target-month realized PnL is used to build the prior.

## Results

| run | best scenario | risk weight | added | added PnL | combined total | month min | role min | remaining extra | remaining hurdle | blockers |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| composite | available p0.6 EV-2 tail0.3 model-used | `0.05` | `5` | `+23.7960` | `+363.0870` | `-0.6120` | `+0.5354` | `3` | `+1.4486` | month, side-share |
| tail-only | available p0.6 EV-2 tail0.3 model-used | `0.50` | `5` | `+23.7960` | `+363.0870` | `-0.6120` | `+0.5354` | `3` | `+1.4486` | month, side-share |
| no duration prior control | available p0.6 EV-2 tail0.3 model-used | `0.00` | `5` | `+23.2000` | `+362.4910` | `-0.6120` | `+0.5354` | `3` | `+1.4486` | month, side-share |

The p0.4 repair scenario where 00326 hpen0.25 worked:

| risk weight | added | added PnL | combined total | month min | note |
|---:|---:|---:|---:|---:|---|
| `0.00` | `6` | `+3.2340` | `+342.5250` | `-19.8260` | bad 720m remains |
| `0.05` | `6` | `+3.8300` | `+343.1210` | `-19.8260` | too weak |
| `0.25` | `6` | `-2.6360` | `+336.6550` | `-19.8260` | still too weak and starts damaging winners |
| `0.50` | `6` | `+16.6340` | `+355.9250` | `-0.6120` | bad 720m stopped, winners also damaged |
| `1.00` | `6` | `+16.6340` | `+355.9250` | `-0.6120` | same selected set as 0.50 |

Critical fresh2024 2024-08 evidence:

| horizon | pred PnL | pred tail | prior count | prior months | prior mean PnL | prior delta vs 60m | prior tail rate | risk score | actual |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 60 | `+0.5880` | `0.0767` | `48` | `6` | `+0.9061` | `0.0000` | `0.0650` | `0.3249` | `+2.9500` |
| 240 | `+0.3319` | `0.1540` | `48` | `6` | `+1.7885` | `+0.8825` | `0.1493` | `0.7467` | `+4.8500` |
| 720 | `+3.3056` | `0.2886` | `48` | `6` | `-3.4993` | `-4.4053` | `0.4145` | `9.9773` | `-29.1360` |

Best composite additions:

| role | month | side | decision UTC | horizon | prior context | risk | penalty | actual |
|---|---|---|---|---:|---|---:|---:|---:|
| fresh2024_validation | 2024-08 | long | 2024-08-22 03:39 | 60 | side,regime,session,bucket | `0.3249` | `0.0162` | `+2.9500` |
| hybrid2025_0912_external | 2025-10 | long | 2025-10-03 00:14 | 720 | side,regime,session,bucket | `1.4238` | `0.0712` | `+4.7300` |
| hybrid2025_0912_external | 2025-11 | short | 2025-11-10 08:07 | 60 | side,regime,session,bucket | `0.5188` | `0.0259` | `+1.9800` |
| refit2025_validation | 2025-08 | short | 2025-08-08 08:31 | 240 | side,regime,session,bucket | `1.8589` | `0.0929` | `+12.9560` |
| refit2025_validation | 2025-08 | long | 2025-08-14 16:27 | 720 | side,regime,session | `2.1871` | `0.1094` | `+1.1800` |

## Decision

Accepted:

- broad candidate train rows as a duration-risk source
- chronological broad duration prior infrastructure
- row-level prior evidence columns for horizon choice diagnostics
- `repair_duration_risk_penalty_amount` hook in support repair replay

Rejected:

- current direct broad duration prior penalty as a policy candidate
- treating p0.6 best as a duration-risk policy improvement; it mostly uses stricter probability gating
- treating the fresh2024 2024-08 fix alone as sufficient evidence
- replacing hpen0.25 with current broad prior

Standard policy remains NoTrade.

## Interpretation

The good news:

```text
The broader prior sees the exact bad pattern:
shorter horizons have positive prior, 720m has negative prior and high tail rate.
```

The bad news:

```text
Direct context-prior penalty is too blunt.
It protects 2024-08 but also suppresses or reranks useful support trades.
```

This is still progress. 00327 showed sparse support-repair-only calibration cannot learn before 2024-08. 00328 shows broad prior has enough evidence, but the evidence must be fed into a learned horizon selector or calibrated ranker, not directly subtracted as a static penalty.

## Next

1. Treat broad duration prior columns as model features, not as a direct penalty.
2. Train a small chronological horizon-choice ranker/head over broad train rows to predict realized `side_fixed_horizon_pnl` or `fixed_horizon > alternative` outcomes.
3. Include opportunity-preservation terms so refit2025 2025-07 style positive 240m rows are not discarded just because their context is risky.
4. Separate tail-risk warning from expected-PnL shrinkage; current composite risk mixes them too aggressively.
5. Keep support repair admission gates unchanged: current best still fails month floor and side-share.

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_broad_duration_prior_repair_replay.py scripts/experiments/entry_ev_support_repair_horizon_replay.py tests/test_entry_ev_broad_duration_prior_repair_replay.py`: OK
- `uv run python -m unittest tests.test_entry_ev_broad_duration_prior_repair_replay tests.test_entry_ev_support_repair_horizon_replay`: OK
- 00322 s2 train rows re-run with `--write-train-rows`: OK
- 00328 composite broad duration prior replay: OK
- 00328 tail-only broad duration prior replay: OK
