# Entry EV Fresh Support Episode Diagnostics

日時: 2026-07-02 03:50 JST
更新日時: 2026-07-02 03:50 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00267の弱点であるfresh2024 support不足を、candidate row数、episode数、stateful trade数に分解した。
- 独立した外部chronologyとしてそのまま使える別pre-block / exit-regret familyはローカルartifact上に見当たらなかったため、今回はfresh support shortageの原因分析へ寄せた。
- `scripts/experiments/entry_ev_candidate_episode_support_diagnostics.py` を追加し、candidate rowsが連続する時間帯をepisodeとして集計できるようにした。
- q99/floor5/rank90はfresh2024で26 candidate rowsあるが、6 episodes、1 active monthに集中し、stateful実行では1 trade `+24.0400` だけになる。
- q95/floor5/rank90は34 rows、9 episodes、3 active months、3 trades `+32.7380` まで増えるが、00267のstateful replayではq99よりtail/DDが悪い。
- rankを0まで緩めたq99/floor5はfresh2024を61 rows、23 episodes、5 active months、8 trades `+73.6226` へ増やすが、cal2024 `-26.9300`、refit2025 `-106.8816`、overall `-60.1890` へ崩れる。
- 判断: episode support診断はaccepted。rank0緩和はsupport改善策としてreject。q99 prior guardは固定diagnostic candidateのまま、標準policyはNoTrade。

## Artifacts

- Added script:
  - `scripts/experiments/entry_ev_candidate_episode_support_diagnostics.py`
- Added test:
  - `tests/test_entry_ev_candidate_episode_support_diagnostics.py`
- Fresh support funnel:
  - `data/reports/backtests/20260701_184430_20260702_entry_ev_preblock_prior_guard_fresh_support_diag_s1/`
- Episode support:
  - `data/reports/backtests/20260701_184729_20260702_entry_ev_preblock_fresh_episode_support_s1/`
- Rank0 stress replay:
  - `data/reports/backtests/20260701_184507_20260702_entry_ev_preblock_q99_rank0_floor5_support_stress_s1/`
- Rank0 admission:
  - `data/reports/backtests/20260701_184749_20260702_entry_ev_preblock_q99_rank0_floor5_support_stress_admission_strict3_s1/`

## Candidate Support Funnel

fresh2024 q99/floor5/rank90:

| stage | rows |
|---|---:|
| valid predictions | `296756` |
| score q99 pass | `3308` |
| side-gap q95 pass | `15185` |
| rank q90 pass | `30037` |
| all quantiles pass | `404` |
| hold-valid after quantile | `370` |
| floor5 candidate rows | `26` |

Important readings:

- `floor5` is the main support killer after q99/rank90: `370 -> 26`.
- Lowering side-gap from q95 to q90 does not help once floor5 remains: q99/sg90/rank90/floor5 is still 26 rows.
- Removing rank filter while keeping q99/sg95/floor5 increases support to 61 rows, but this is a policy change with large downstream cost.

## Episode Support

| candidate | rows | episodes | active months | max episode rows | long episodes | short episodes |
|---|---:|---:|---:|---:|---:|---:|
| q99/sg95/rank90/floor5 | `26` | `6` | `1` | `6` | `0` | `6` |
| q95/sg95/rank90/floor5 | `34` | `9` | `3` | `7` | `0` | `9` |
| q99/sg95/rank0/floor5 | `61` | `23` | `5` | `18` | `0` | `23` |

q99/rank90/floor5 is concentrated in one short cluster family:

| month | rows | episodes | first | last |
|---|---:|---:|---|---|
| 2024-03 | `26` | `6` | `2024-03-21 02:32 UTC` | `2024-03-21 03:14 UTC` |

q95/rank90/floor5 adds small short episodes in 2024-08 and 2024-11:

| month | rows | episodes |
|---|---:|---:|
| 2024-03 | `27` | `6` |
| 2024-08 | `3` | `1` |
| 2024-11 | `4` | `2` |

q99/rank0/floor5 expands to five months, but all episodes are still short-only.

## Stateful Replay Check

q99/sg95/rank0/floor5 stress:

| family | total pnl | worst month | trades | max DD | max side share |
|---|---:|---:|---:|---:|---:|
| cal2024 | `-26.9300` | `-25.1300` | `32` | `46.0474` | `0.6250` |
| fresh2024 | `+73.6226` | `-7.9080` | `8` | `7.9080` | `1.0000` |
| refit2025 | `-106.8816` | `-76.5898` | `237` | `144.7384` | `0.6835` |
| overall | `-60.1890` | `-76.5898` | `277` | `144.7384` | `0.6570` |

Admission:

| candidate | selected | blockers |
|---|---|---|
| q99/sg95/rank0/floor5 | no_trade | `positive_roles_low;total_pnl_below_floor;role_total_pnl_below_floor;month_pnl_below_floor;role_trades_low;month_trades_low` |

Reading:

- rank relaxation solves the visible fresh support count but reintroduces broad role loss.
- The failure is not only trade count. `positive_roles_low`, `total_pnl_below_floor`, and `role_total_pnl_below_floor` also fail.
- fresh2024 being short-only remains a side concentration risk even when its PnL is positive.

## Decision

Accepted:

- candidate episode support diagnostics
- using episode count and active months as a support-quality view in addition to raw candidate rows

Rejected:

- q99 rank0 as a support fix
- lowering rank/floor on the same windows to force admission
- treating fresh2024 positive PnL with sparse short-only support as enough evidence

Standard policy remains NoTrade.

## Next

1. Keep q99/floor5/rank90 + prior `direction_regime` guard frozen as the current diagnostic candidate.
2. Improve support by external chronology, regenerated families, or added data/windows, not by same-window threshold relaxation.
3. If support must be loosened, require it to pass cal/fresh/refit role PnL floors before considering it a candidate.
4. Add episode/active-month summaries to future support diagnostics when sparse row clusters can masquerade as broad support.

## Verification

- `python3 -m unittest tests.test_entry_ev_candidate_episode_support_diagnostics`: OK
- `python3 -m py_compile scripts/experiments/entry_ev_candidate_episode_support_diagnostics.py tests/test_entry_ev_candidate_episode_support_diagnostics.py`: OK
- fresh support funnel run: OK
- episode support diagnostic run: OK
- rank0 stress replay: OK
- rank0 strict admission selector: OK
