# Entry EV Pre-Block Side Gap Quantile

日時: 2026-07-02 03:03 JST
更新日時: 2026-07-02 03:03 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00263で見つけた post-block `side_gap_pct` 汚染に対応するため、selector input生成へ `--side-gap-quantile-mode {post_block,pre_block}` を追加した。
- 既定値は従来互換の `post_block`。
- `pre_block` では selector のlong/short score自体はpost-blockのまま維持し、`side_gap_pct_*` だけbase scoreから計算して上書きする。
- unit testで、blocked score sentinel による side-gap percentile の膨張を `pre_block` が避けることを確認した。
- 実データでは pre-block side-gap quantileにより fresh2024 supportは復活した。q99/floor5は `0 -> 26` rows、q95/floor5は `0 -> 34` rows。
- しかし stateful replayでは refit2025 tailが大きく悪化し、q99/floor5 total `-23.5882`, q95/floor5 total `-14.6536`。
- strict/relaxed admissionはNoTrade。
- 判断: pre-block side-gap quantile infrastructureはaccepted。現pre-block `sg95` policyはreject。標準policyはNoTrade。

## Artifacts

- Updated script:
  - `scripts/experiments/entry_ev_forced_exit_selector_inputs.py`
- Updated test:
  - `tests/test_entry_ev_forced_exit_selector_inputs.py`
- Pre-block side-gap selector inputs:
  - `data/reports/backtests/20260701_175911_20260702_entry_ev_exit_regret_replguard_preblockgap_t0p4_inputs_s1/`
- Candidate support:
  - `data/reports/backtests/20260701_180008_20260702_entry_ev_exit_regret_replguard_preblockgap_candidate_support_s1/`
- Broad replay:
  - `data/reports/backtests/20260701_180025_20260702_entry_ev_exit_regret_replguard_preblockgap_broad_backtest_s1/`
- Admission:
  - `data/reports/backtests/20260701_180326_20260702_entry_ev_exit_regret_replguard_preblockgap_admission_strict3_s1/`
  - `data/reports/backtests/20260701_180326_20260702_entry_ev_exit_regret_replguard_preblockgap_admission_relaxed3_s1/`

## Implementation

New option:

```text
--side-gap-quantile-mode post_block  # default, existing behavior
--side-gap-quantile-mode pre_block   # side_gap_pct only uses base long/short scores
```

Important detail:

- `selected_score_pct` remains post-block.
- `selected_entry_rank_pct` remains post-block-selected side rank.
- `side_gap_pct` is replaced with base long/short side-gap percentile when `pre_block` is selected.

This preserves selector blocking behavior while preventing `blocked_score=-1e9` from dominating the side-gap distribution.

## Candidate Support

Replguard `sg95` post-block versus pre-block:

| family | candidate | post-block floor pass | pre-block floor pass | pre-block side |
|---|---|---:|---:|---|
| fresh2024 | q99/floor5 | `0` | `26` | short `26` |
| fresh2024 | q95/floor5 | `0` | `34` | short `34` |
| refit2025 | q99/floor5 | `101` | `225` | long `161`, short `64` |
| refit2025 | q95/floor5 | `280` | `535` | long `403`, short `132` |

Reading:

- The fix does exactly what it was meant to do: fresh support returns.
- It also opens many additional refit2025 candidates. That larger exposure is where tail risk comes back.

## Replay

Broad replay with `exit_regret_selector_replguard_preblockgap_confidenceexit_bucket_t0p4`:

| candidate | total | worst month | trades | max DD | max side share |
|---|---:|---:|---:|---:|---:|
| q99/floor5 | `-23.5882` | `-128.3504` | `70` | `128.3504` | `0.5429` |
| q95/floor5 | `-14.6536` | `-140.8024` | `119` | `140.8024` | `0.5714` |
| q99/floor10 | `+1.0804` | `-7.4880` | `10` | `7.4880` | `0.7000` |
| q95/floor10 | `-39.7360` | `-28.4760` | `23` | `37.6890` | `0.6522` |

Role detail:

- fresh q99/floor5: `+24.0400`, `1` trade.
- fresh q95/floor5: `+32.7380`, worst `-0.6120`, `3` trades.
- refit q99/floor5: `-50.0440`, worst `-128.3504`, `59` trades.
- refit q95/floor5: `-45.6930`, worst `-140.8024`, `95` trades.

## Admission

Strict gate:

- selected: NoTrade.
- q99/q95 floor5 both fail `total_pnl_below_floor`, `role_total_pnl_below_floor`, `month_pnl_below_floor`, `role_trades_low`, `month_trades_low`.

Relaxed diagnostic gate:

- selected: NoTrade.
- q99/floor5 fails `total_pnl_below_floor`, `role_total_pnl_below_floor`, `month_pnl_below_floor`, `role_trades_low`.
- q95/floor5 fails `positive_roles_low`, `total_pnl_below_floor`, `role_total_pnl_below_floor`, `month_pnl_below_floor`, `role_trades_low`.

## Decision

Accepted:

- `side_gap_quantile_mode=pre_block` as selector input infrastructure.
- Evidence that the 00263 side-gap contamination diagnosis was correct.
- Candidate support restoration for fresh2024.

Not accepted:

- Pre-block `sg95` policy promotion.
- Treating restored fresh support as improved policy evidence.
- Widening refit exposure without a new tail control.

Standard policy remains NoTrade.

## Next

1. Keep `pre_block` as an available diagnostic/infrastructure option.
2. Do not use pre-block `sg95` alone as a fix; it reopens refit tail.
3. Diagnose the refit2025 rows newly admitted by pre-block side-gap quantile, especially q95/floor5 added rows and May tail.
4. Consider a two-stage admission: pre-block side-gap for support normalization, then replacement/tail risk guard on the newly admitted rows.

## Verification

- `python3 -m unittest tests.test_entry_ev_forced_exit_selector_inputs`: OK
- `python3 -m py_compile scripts/experiments/entry_ev_forced_exit_selector_inputs.py tests/test_entry_ev_forced_exit_selector_inputs.py`: OK
- pre-block selector input generation: OK
- candidate support diagnostic: OK
- broad replay: OK
- strict/relaxed admission selector runs: OK
