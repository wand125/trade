# Entry EV Quantile Candidate Support Diagnostics

日時: 2026-07-02 02:52 JST
更新日時: 2026-07-02 02:52 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00262で見えた `fresh2024_broad_validation` 0-tradeの原因を、candidate row supportの漏斗で診断した。
- `scripts/experiments/entry_ev_quantile_candidate_support_diagnostics.py` を追加した。
- replguard + `sg95` では fresh2024 q99/floor5 が quantile all `187`, hold ok `184` まで残るが、floor5通過が `0`。q95/floor5も hold ok `622` から floor5通過 `0`。
- ただし base `side_prior_pressure_s0p5` では fresh q99/floor5が `26` rows、q95/floor5が `34` rows 通過しており、すべてshortだった。
- base q99/floor5の26 rowsを追跡すると、exit-regret selector後も `score > 5` は26 rows残り、直接blockも0。しかし `side_gap_pct >= 0.95` が0 rowsになる。
- 原因は `side_gap_pct` を selector blocking 後のscoreで再計算していること。blocked sideの `-1e9` がside gap分布を膨らませ、baseでは有効だったshort候補の `side_gap_pct` が約 `0.88` に落ちる。
- `sg0` 診断では fresh supportが戻り、replguard q99/floor5 `26` rows、q95/floor5 `38` rows が候補化した。
- しかし `sg0` stateful replayは tailが大きく、q95/floor5 total `+117.7700` でも worst month `-133.6988`。strict/relaxed admissionはNoTrade。
- 判断: `side_gap_pct` のpost-block再計算汚染をaccepted diagnosticとする。`sg95` を単純に外して標準化しない。次は pre-block/finite-side のside-gap quantileを作る。

## Artifacts

- Added script:
  - `scripts/experiments/entry_ev_quantile_candidate_support_diagnostics.py`
- Added test:
  - `tests/test_entry_ev_quantile_candidate_support_diagnostics.py`
- Replguard `sg95` support:
  - `data/reports/backtests/20260701_174501_20260702_entry_ev_exit_regret_replguard_candidate_support_v2_s1/`
- No-guard `sg95` support:
  - `data/reports/backtests/20260701_174614_20260702_entry_ev_exit_regret_noguard_candidate_support_s1/`
- Base side-prior support:
  - `data/reports/backtests/20260701_174652_20260702_entry_ev_side_prior_s0p5_candidate_support_s1/`
- No-guard `sg0` support:
  - `data/reports/backtests/20260701_174857_20260702_entry_ev_exit_regret_noguard_sg0_support_s1/`
- Replguard `sg0` support:
  - `data/reports/backtests/20260701_174926_20260702_entry_ev_exit_regret_replguard_sg0_support_s1/`
- Replguard `sg0` broad replay:
  - `data/reports/backtests/20260701_175000_20260702_entry_ev_exit_regret_replguard_sg0_broad_backtest_s1/`
- Replguard `sg0` admission:
  - `data/reports/backtests/20260701_175147_20260702_entry_ev_exit_regret_replguard_sg0_admission_strict3_s1/`
  - `data/reports/backtests/20260701_175147_20260702_entry_ev_exit_regret_replguard_sg0_admission_relaxed3_s1/`

## Candidate Support

Replguard `sg95`:

| family | candidate | quantile hold ok | floor pass | max score before floor | first zero |
|---|---|---:|---:|---:|---|
| fresh2024 | q99/floor5 | `184` | `0` | `4.2415` | `threshold_after_quantile_hold` |
| fresh2024 | q95/floor5 | `622` | `0` | `4.4456` | `threshold_after_quantile_hold` |
| refit2025 | q99/floor5 | `187` | `101` | `11.3153` |  |
| refit2025 | q95/floor5 | `599` | `280` | `11.3153` |  |

Base side-prior comparison:

| score kind | candidate | fresh quantile hold ok | fresh floor pass | fresh candidate side |
|---|---|---:|---:|---|
| side_prior_s0p5 | q99/floor5 | `409` | `26` | short `26` |
| side_prior_s0p5 | q95/floor5 | `1279` | `34` | short `34` |
| exit_regret no-guard | q99/floor5 | `197` | `0` | none |
| exit_regret replguard | q99/floor5 | `184` | `0` | none |

Monthly note:

- base q99/floor5のfresh floor pass `26` rowsは2024-03に集中。
- base q95/floor5は2024-03に `27`, 2024-08に `3`, 2024-11に `4` rows。

## Root Cause

Base q99/floor5のfresh 26 rowsを同じdecision timestampで追跡した。

Under no-guard exit-regret selector:

```text
score_q99      = 26
side_gap_q95   = 0
rank_q90       = 26
score_gt5      = 26
all_quantiles  = 0
direct blocks  = 0
```

Under replacement guard:

```text
score_q99      = 26
side_gap_q95   = 0
rank_q90       = 26
score_gt5      = 26
all_quantiles  = 0
direct blocks  = 0
```

Reading:

- The rows are not killed by floor5.
- The rows are not directly blocked by exit-regret risk or replacement guard.
- They fail because selector-side `side_gap_pct` falls to around `0.88`, below `sg95`.
- fresh2024 has long risk block share `0.20045`. Blocking with `-1e9` creates artificial huge side gaps in the same scope.
- Therefore post-block `side_gap_pct` no longer measures ordinary side confidence. It partly measures whether one side was blocked.

## sg0 Diagnostic

Removing only side-gap quantile restores fresh row support:

| score kind | candidate | fresh row support |
|---|---|---:|
| no-guard sg0 | q99/floor5 | `26` |
| no-guard sg0 | q95/floor5 | `38` |
| replguard sg0 | q99/floor5 | `26` |
| replguard sg0 | q95/floor5 | `38` |

Stateful replay of replguard `sg0`:

| candidate | validation total | min role total | worst month | trades | max DD | max side share |
|---|---:|---:|---:|---:|---:|---:|
| q99/sg0/floor5 | `+34.4720` | `-3.7090` | `-126.0104` | `88` | `126.0104` | `0.5455` |
| q95/sg0/floor5 | `+117.7700` | `+4.4324` | `-133.6988` | `181` | `133.6988` | `0.5967` |

Admission:

- strict: NoTrade.
- relaxed: NoTrade.
- q95/sg0/floor5 blockers include `month_pnl_below_floor` and `role_trades_low`.
- q99/sg0/floor5 blockers include `role_total_pnl_below_floor`, `month_pnl_below_floor`, and `role_trades_low`.

## Decision

Accepted:

- Candidate support diagnostic script and tests.
- `fresh2024` 0-trade root cause diagnosis.
- Evidence that `side_gap_pct` after blocking is contaminated by sentinel-score side gaps.

Not accepted:

- Dropping `sg95` as a standard fix.
- Promoting `sg0` replay despite positive total PnL.
- Treating fresh q99/q95 row support as sufficient; actual executed fresh trades are only `1` and `3` in the `sg0` replay.

Standard policy remains NoTrade.

## Next

1. Add pre-block or finite-side side-gap quantile columns for selector outputs.
2. Re-run replguard candidate support and broad replay with side-gap quantile computed before `blocked_score=-1e9`.
3. Keep `sg0` only as a diagnostic proving the side-gap bottleneck, not as an adoption candidate.
4. Preserve strict role/month floor and role trade support gates.

## Verification

- `python3 -m unittest tests.test_entry_ev_quantile_candidate_support_diagnostics`: OK
- `python3 -m py_compile scripts/experiments/entry_ev_quantile_candidate_support_diagnostics.py tests/test_entry_ev_quantile_candidate_support_diagnostics.py`: OK
- candidate support diagnostic runs: OK
- `sg0` broad replay: OK
- `sg0` strict/relaxed admission selector runs: OK
