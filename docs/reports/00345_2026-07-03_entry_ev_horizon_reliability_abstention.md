# Entry EV Horizon Reliability Abstention Diagnostics

日時: 2026-07-03 10:31 JST
更新日時: 2026-07-03 10:31 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00344でreliability-gated horizon scoreがplain `pnl` に対して大きく悪化したため、reliability-driven horizon switchをそのまま採用せず、prediction-only vetoでbaseline `pnl` horizonへ戻す診断を追加した。
- `entry_ev_horizon_reliability_abstention_diagnostics.py` は00344の `horizon_reliability_choice_deltas.csv` を入力にし、複数のabstention/veto ruleを適用した後のdelta、veto件数、回復した損失、削った利益をCSV化する。
- target subset available candidatesでは、`pnl_delta_tail_reliability_gated` の `-131.8792` 悪化に対し、`veto_chosen_pred_pnl_lt0` は `+13.6962` まで回復した。5件vetoし、5件すべて損失回復で、利益削除は0件。
- all rows available candidatesでも、`pnl_delta_tail_reliability_gated` は `-137.6916` から `+57.0582`、`pnl_tail_reliability_gated` は `-93.6228` から `+37.9022` へ改善した。
- 判断: abstention diagnosticsはaccepted infrastructure。`veto_chosen_pred_pnl_lt0` は次のstateful replay候補。これはchoice-delta後処理なので、まだ標準policyではない。標準policyはNoTrade。

## Artifacts

Changed script:

- `scripts/experiments/entry_ev_horizon_reliability_abstention_diagnostics.py`

Changed tests:

- `tests/test_entry_ev_horizon_reliability_abstention_diagnostics.py`

Runs:

- target subset: `data/reports/backtests/20260703_013038_20260703_entry_ev_00345_horizon_reliability_abstention_diagnostics/`
- all rows: `data/reports/backtests/20260703_013038_20260703_entry_ev_00345_horizon_reliability_abstention_diagnostics_allrows/`

Main outputs:

- `horizon_reliability_abstention_outcomes.csv`
- `horizon_reliability_abstention_summary.csv`
- `horizon_reliability_abstention_target_summary.csv`
- `horizon_reliability_abstention_cases.csv`
- `config.json`

## Method

Input is 00344's score-mode choice delta table. For each non-baseline score mode, a rule may veto the chosen horizon switch and revert the decision to the baseline `pnl` horizon.

Rules tested:

- `no_veto`
- `veto_all_switches`
- `veto_longer_horizon_switch`
- `veto_60_to_longer_switch`
- `veto_chosen_pred_pnl_below_baseline`
- `veto_chosen_pred_pnl_lt0`
- `veto_tail_prob_ge_0p30`
- `veto_uncertain_beats60_switch`
- `veto_longer_tail_or_lowpnl`

Actual PnL is used only to evaluate post-veto outcomes. Runtime-like rule conditions use prediction columns and horizon metadata, not realized PnL.

## Results

### Target Subset

Available candidates:

| score mode | rule | original delta vs `pnl` | post-veto delta vs `pnl` | recovered | switches | vetoes | recovered losses | removed gains |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `pnl_delta_tail_reliability_gated` | `no_veto` | `-131.8792` | `-131.8792` | `0.0000` | `13` | `0` | `0` | `0` |
| `pnl_delta_tail_reliability_gated` | `veto_chosen_pred_pnl_lt0` | `-131.8792` | `+13.6962` | `+145.5754` | `13` | `5` | `5` | `0` |
| `pnl_delta_tail_reliability_gated` | `veto_tail_prob_ge_0p30` | `-131.8792` | `-11.6830` | `+120.1962` | `13` | `11` | `5` | `6` |
| `pnl_delta_tail_reliability_gated` | `veto_all_switches` | `-131.8792` | `0.0000` | `+131.8792` | `13` | `13` | `6` | `7` |
| `pnl_tail_reliability_gated` | `no_veto` | `-87.8104` | `-87.8104` | `0.0000` | `7` | `0` | `0` | `0` |
| `pnl_tail_reliability_gated` | `veto_chosen_pred_pnl_lt0` | `-87.8104` | `-5.4598` | `+82.3506` | `7` | `4` | `4` | `0` |
| `pnl_tail_reliability_gated` | `veto_all_switches` | `-87.8104` | `0.0000` | `+87.8104` | `7` | `7` | `5` | `2` |
| `pnl_delta_tail` | `no_veto` | `-63.0506` | `-63.0506` | `0.0000` | `6` | `0` | `0` | `0` |
| `pnl_delta_tail` | `veto_all_switches` | `-63.0506` | `0.0000` | `+63.0506` | `6` | `6` | `6` | `0` |

Key reading:

- `veto_chosen_pred_pnl_lt0` is the only target subset rule that improves `pnl_delta_tail_reliability_gated` beyond simply reverting all switches to baseline.
- `veto_chosen_pred_pnl_below_baseline` looks plausible, but it worsens `pnl_delta_tail_reliability_gated` to `-138.9078` on target subset because it removes profitable positive-PnL switches while missing large negative ones.
- Broad longer-horizon vetoes mostly collapse back toward baseline and delete positive switches; they are diagnostics, not policy candidates.

### All Rows Check

Available candidates:

| score mode | rule | original delta vs `pnl` | post-veto delta vs `pnl` | recovered | switches | vetoes | recovered losses | removed gains |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `pnl_delta_tail_reliability_gated` | `no_veto` | `-137.6916` | `-137.6916` | `0.0000` | `23` | `0` | `0` | `0` |
| `pnl_delta_tail_reliability_gated` | `veto_chosen_pred_pnl_lt0` | `-137.6916` | `+57.0582` | `+194.7498` | `23` | `12` | `10` | `2` |
| `pnl_tail_reliability_gated` | `no_veto` | `-93.6228` | `-93.6228` | `0.0000` | `17` | `0` | `0` | `0` |
| `pnl_tail_reliability_gated` | `veto_chosen_pred_pnl_lt0` | `-93.6228` | `+37.9022` | `+131.5250` | `17` | `11` | `9` | `2` |
| `pnl_delta_tail` | `no_veto` | `-33.6478` | `-33.6478` | `0.0000` | `13` | `0` | `0` | `0` |
| `pnl_delta_tail` | `veto_tail_prob_ge_0p30` | `-33.6478` | `+29.4028` | `+63.0506` | `13` | `6` | `6` | `0` |

The all-rows check supports the same direction: direct reliability multiplier is bad, but a low-complexity self-consistency veto can turn the reliability-gated variant into a useful candidate surface.

### Target Breakdown for `veto_chosen_pred_pnl_lt0`

`pnl_delta_tail_reliability_gated`, target subset available candidates:

| target | decisions | original delta | post-veto delta | vetoes | recovered losses | removed gains |
|---|---:|---:|---:|---:|---:|---:|
| `fresh2024_validation 2024-03 long` | `17` | `0.0000` | `0.0000` | `0` | `0` | `0` |
| `fresh2024_validation 2024-08 long` | `14` | `-53.4004` | `0.0000` | `1` | `1` | `0` |
| `refit2025_validation 2025-07 short` | `10` | `-27.4596` | `0.0000` | `1` | `1` | `0` |
| `hybrid2025_0912_external 2025-10 long` | `4` | `-15.5800` | `-15.5800` | `0` | `0` | `0` |
| `hybrid2025_0912_external 2025-11 short` | `23` | `-35.4392` | `+29.2762` | `3` | `3` | `0` |

Important cases:

| target | baseline -> chosen | baseline actual | chosen actual | delta | predicted PnL | veto |
|---|---:|---:|---:|---:|---:|---|
| `fresh2024 2024-08 long` | `60m -> 240m` | `+9.4600` | `-43.9404` | `-53.4004` | `-2.7612` | yes |
| `hybrid2025 2025-11 short` | `60m -> 240m` | `+2.5570` | `-25.0320` | `-27.5890` | `-0.2810` | yes |
| `refit2025 2025-07 short` | `60m -> 720m` | `-9.5400` | `-36.9996` | `-27.4596` | `-1.5076` | yes |
| `hybrid2025 2025-10 long` | `60m -> 240m` | `+3.5800` | `-12.0000` | `-15.5800` | `+0.6115` | no |
| `hybrid2025 2025-11 short` | `60m -> 240m` | `-6.7440` | `-0.5208` | `+6.2232` | `+2.7074` | no |

The remaining miss is clear: `hybrid2025 2025-10 long` still has positive predicted PnL but negative realized PnL. That case needs a separate tail/overestimate or context reliability signal; the negative-PnL veto should not be overfit to cover it.

## Decision

- `entry_ev_horizon_reliability_abstention_diagnostics.py`: accepted infrastructure.
- `veto_chosen_pred_pnl_lt0`: promoted to diagnostic candidate for the next stateful replay / score-mode implementation.
- `veto_tail_prob_ge_0p30`: useful comparator, especially for plain `pnl_delta_tail` all-rows, but it removes many gains in reliability-gated target subset.
- `veto_chosen_pred_pnl_below_baseline`: rejected as current policy candidate for reliability-gated choice; target subset worsens.
- `veto_all_switches`, `veto_longer_horizon_switch`, `veto_60_to_longer_switch`: diagnostic baselines, not policy improvements.
- Standard policy remains NoTrade.

## Next

1. Implement `ranker_pred_pnl < 0` horizon-switch abstention inside the replay path, not only as post-hoc choice-delta evaluation.
2. Compare `pnl_delta_tail_reliability_gated + pred_pnl_lt0 veto` against plain `pnl` under one-position stateful constraints and standard admission checks.
3. Add a separate overestimate/tail diagnostic for positive predicted PnL failures like `hybrid2025 2025-10 long`.
4. Continue candidate generation for `fresh2024 2024-11` and `refit2025 2025-03`; abstention cannot fix missing candidate rows.

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_horizon_reliability_abstention_diagnostics.py`: OK
- `uv run python -m py_compile scripts/experiments/entry_ev_horizon_reliability_abstention_diagnostics.py tests/test_entry_ev_horizon_reliability_abstention_diagnostics.py`: OK
- `uv run python -m unittest tests.test_entry_ev_horizon_reliability_abstention_diagnostics`: OK
- 00345 target subset diagnostics: OK
- 00345 all rows diagnostics: OK
