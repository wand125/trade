# Entry EV Upstream Universe Coverage Diagnostics

日時: 2026-07-03 15:07 JST
更新日時: 2026-07-03 15:07 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00361の次アクションとして、`refit2025 2025-03 short` が00318/00322で0件になった原因をrepair target生成前から監査した。
- `entry_ev_upstream_universe_coverage_diagnostics.py` を追加し、00318 s2のconfigをそのまま読み、repair targetを `extra_*_needed > 0` で落とさずに、raw prediction rows、side rows、threshold candidate rows、stateful availabilityを同じ表で出すようにした。
- 直接原因はprediction parquetのcoverage不足ではなかった。`refit2025 2025-03 short` は raw prediction rows `28,972`、short side rows `28,972`、candidate rows `41`、stateful available `33` が存在する。
- それでも00318に出ない理由は、00317 repair targetで `extra_short_needed=0`、`extra_long_needed=0` だったため。`read_repair_targets()` はextraが正のsideだけを発行するので、この月はcandidate generation対象から外れていた。
- 判断: `refit2025 2025-03` は「追加entry不足」ではなく「負け月だがside/trade supportは足りている月」。次は追加候補ではなく、既存tradeのexit timing / replacement / EV過大評価補正として扱う。

## Artifacts

Added script:

- `scripts/experiments/entry_ev_upstream_universe_coverage_diagnostics.py`

Added tests:

- `tests/test_entry_ev_upstream_universe_coverage_diagnostics.py`

Run:

- `data/reports/backtests/20260703_060716_20260703_entry_ev_00362_upstream_universe_00318_s2/`

Outputs:

- `upstream_universe_target_summary.csv`
- `upstream_universe_side_stage_summary.csv`
- `upstream_universe_candidate_examples.csv`
- `upstream_universe_current_trades.csv`
- `upstream_universe_meta.json`

## Method

Input config:

```text
data/reports/backtests/20260702_111114_20260702_entry_ev_00318_thin_month_opposite_candidates_00314_w5_s2/config.json
```

Target list:

```text
refit2025_validation:2025-03:short
fresh2024_validation:2024-11:long
fresh2024_validation:2024-03:long
fresh2024_validation:2024-08:long
refit2025_validation:2025-07:short
```

Classification priority:

```text
repair_target_missing
repair_target_has_no_extra_side_need
repair_target_not_emitted_no_extra_side_need
no_prediction_rows
no_target_side_rows
holding_window_filtered
threshold_filtered
stateful_overlap_filtered
candidate_generation_possible
```

Important distinction:

- 00318 production path emits target side rows only when `extra_side_needed > 0`.
- 00362 diagnostic path keeps repair target rows even when `extra_side_needed == 0`, then separately checks whether prospective candidates exist.
- Actual PnL is used only for diagnosis and interpretation, not for target emission or candidate gate.

## Target Results

| target | stage | extra side | raw rows | side rows | holding ok | candidates | available | current trades | current side mix | current PnL |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|---:|
| `fresh2024 2024-03 long` | candidate generation possible | `1` | `27,589` | `27,589` | `2,012` | `18` | `18` | `1` | `0L / 1S` | `-0.3636` |
| `fresh2024 2024-08 long` | candidate generation possible | `1` | `30,300` | `30,300` | `7,137` | `15` | `15` | `1` | `0L / 1S` | `+9.3100` |
| `fresh2024 2024-11 long` | candidate generation possible | `1` | `28,572` | `28,572` | `9,012` | `1` | `1` | `1` | `0L / 1S` | `-0.6120` |
| `refit2025 2025-03 short` | repair target has no extra side need | `0` | `28,972` | `28,972` | `16,616` | `41` | `33` | `9` | `5L / 4S` | `-0.4730` |
| `refit2025 2025-07 short` | candidate generation possible | `1` | `31,499` | `31,499` | `21,296` | `11` | `11` | `7` | `7L / 0S` | `+2.0824` |

`refit2025 2025-03 short` prospective candidate buckets:

| bucket | rows | available rows |
|---|---:|---:|
| strict | `2` | `0` |
| relaxed | `6` | `1` |
| one-fail | `36` | `32` |

Top examples for `refit2025 2025-03 short` are not reassuring:

- The top score cluster around `2025-03-31 03:40..03:45 UTC` has 60m actual mostly negative and 240m/720m actual strongly negative.
- The best-looking available example in the excerpt was 60m `+0.8200` but 240m `-19.3920`, 720m `-17.3040`.
- Several high-margin `2025-03-21` rows are stateful-blocked or fixed-horizon negative.

## Interpretation

- The 00360 label `no prediction rows` for `refit2025 2025-03` was accurate for the post-00318/00322 prediction feed, but incomplete as an upstream explanation. The raw family parquet has rows; the row disappeared because the admission repair target never emitted that side.
- This month already has `9` trades and a `5L / 4S` split. Under 00317's support repair definition, it does not need extra side/trade support even though total PnL is `-0.4730`.
- Therefore adding opposite-side trades is the wrong main repair mechanism for this target. Extra short candidates exist, but the high-score examples include large fixed-horizon losses.
- The correct next lane is negative-month repair for support-sufficient months: existing trade replacement, exit timing, early exit, or EV overestimate calibration. This should be separate from the thin-support repair lane.

## Decision

- `entry_ev_upstream_universe_coverage_diagnostics.py` is accepted infrastructure.
- `refit2025 2025-03` is reclassified from raw universe coverage problem to repair-target objective mismatch: floor-breach with no extra side need.
- Do not widen 00318 target emission to all negative months without a separate replacement/exit objective. That would inject candidate rows where the support objective says no extra trade is needed.
- Standard policy remains NoTrade.

## Next

1. Add a support-sufficient negative-month repair lane that starts from existing losing trades and evaluates replacement / earlier exit / horizon guard, not extra side support.
2. For `fresh2024 2024-11`, continue narrow selected-onefail replacement replay with horizon/tail guard.
3. Keep 00318 thin-support candidate generation limited to positive `extra_side_needed`; do not overload it with all negative-month repair.

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_upstream_universe_coverage_diagnostics.py tests/test_entry_ev_upstream_universe_coverage_diagnostics.py`: OK
- `uv run python -m unittest tests.test_entry_ev_upstream_universe_coverage_diagnostics`: OK
- 00362 upstream universe coverage diagnostic run: OK
