# Entry EV Selected Replacement Scope Diagnostics

日時: 2026-07-03 14:53 JST
更新日時: 2026-07-03 14:53 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00360で `fresh2024 2024-11 long` は `available_candidates` ではなく `greedy_selected` にだけ存在すると分かったため、selected one-fail行をreplacement用の別scopeとして再露出する診断を追加した。
- `entry_ev_selected_replacement_scope_diagnostics.py` を追加し、`selected_any=true`, `stateful_available=true`, `selection_bucket=one_failed_strict_stage`, `side=needed_side`, `extra_side_needed>0` の行を `selected_onefail_replacement` として複製する。
- 複製条件は観測可能なselection metadataだけで、actual PnLはgateやstage分類には使わない。actual PnLは診断列だけ。
- `fresh2024 2024-11 long` は `selected_onefail_replacement` に1行出るが、strictでは通らずrelaxedのみ通る。00358 rankerでは60m `+0.3000`, 240m `+2.4500`, 720m `-5.2800`。
- ただしselected one-failをglobalに戻すと危険。00358 rankerでstrict choices 6件 / actual sum `-83.4028`、relaxed choices 8件 / `-68.0198`。
- 判断: `selected_onefail_replacement` はaccepted diagnostic scope。ただしglobal row-scope wideningはreject。`fresh2024 2024-11` へ使うならtarget-awareかつhorizon/tail guard付きの狭い候補として扱う。

## Artifacts

Added script:

- `scripts/experiments/entry_ev_selected_replacement_scope_diagnostics.py`

Added tests:

- `tests/test_entry_ev_selected_replacement_scope_diagnostics.py`

Runs:

- `data/reports/backtests/20260703_055321_20260703_entry_ev_00361_selected_replacement_scope_00358_ranker/`
- `data/reports/backtests/20260703_055327_20260703_entry_ev_00361_selected_replacement_scope_00322_base/`

Outputs per run:

- `selected_replacement_target_scope_summary.csv`
- `selected_replacement_rows.csv`
- `selected_replacement_scope_summary.csv`
- `selected_replacement_horizon_rows.csv`
- `selected_replacement_strict_gate_summary.csv`
- `selected_replacement_relaxed_gate_summary.csv`
- `selected_replacement_scope_meta.json`

## Method

Synthetic scope:

```text
selected_onefail_replacement
```

Eligibility:

```text
selected_any == true
stateful_available == true
selection_bucket == one_failed_strict_stage
side == needed_side
extra_side_needed > 0
```

Recomputed strict stage thresholds:

```text
side_score > 5.0
score_pct >= 0.95
side_margin_pct >= 0.95
entry_rank_pct >= 0.90
side_margin >= 0.0
holding_ok == true
```

Strict gate:

```text
pred executable prob >= 0.45
pred pnl >= 0.0
tail loss prob <= 0.50
model used = true
```

Relaxed gate:

```text
pred executable prob >= 0.30
pred pnl >= -2.0
tail loss prob <= 0.50
model used = true
```

## Target Results

00358 ranker:

| target | scope | stage | rows | strict choices | relaxed choices | best actual | max pred PnL | note |
|---|---|---|---:|---:|---:|---:|---:|---|
| `fresh2024 2024-03 long` | selected onefail replacement | strict candidate exists | `1` | `1` | `1` | `-3.5280` | `+0.0702` | bad replacement |
| `fresh2024 2024-08 long` | selected onefail replacement | strict candidate exists | `1` | `1` | `1` | `+3.1230` | `+1.2356` | 720m singleton risk still present |
| `fresh2024 2024-11 long` | selected onefail replacement | relaxed only candidate | `1` | `0` | `1` | `+2.4500` | `-0.7214` | entry exists, strict EV blocks |
| `refit2025 2025-03 short` | selected onefail replacement | no prediction rows | `0` | `0` | `0` | n/a | n/a | not solved |
| `refit2025 2025-07 short` | selected onefail replacement | strict candidate exists | `1` | `1` | `1` | `-2.4240` | `+22.9117` | dangerous overestimate |

00322 base:

| target | scope | stage | rows | strict choices | relaxed choices | best actual | max pred PnL | note |
|---|---|---|---:|---:|---:|---:|---:|---|
| `fresh2024 2024-11 long` | selected onefail replacement | relaxed only candidate | `1` | `0` | `1` | `+2.4500` | `-0.0441` | base would prefer 720m under relaxed score, actual `-5.2800` |
| `refit2025 2025-03 short` | selected onefail replacement | no prediction rows | `0` | `0` | `0` | n/a | n/a | not solved |

## Selected One-Fail Rows

There are 8 selected one-fail replacement rows in both 00358 ranker and 00322 base inputs.

00358 ranker selected rows:

| role/month/side | failed strict stage | fixed60 | fixed240 | fixed720 | ranker pred 60/240/720 |
|---|---|---:|---:|---:|---:|
| `fresh2024 2024-03 long` | score_floor | `-14.1240` | `-3.5280` | `-10.3440` | `-0.0808 / +0.0702 / -1.2600` |
| `fresh2024 2024-08 long` | score_floor | `-11.0604` | `+3.1230` | `-21.7452` | `-0.5089 / -0.5089 / +1.2356` |
| `fresh2024 2024-11 long` | score_floor | `+0.3000` | `+2.4500` | `-5.2800` | `-0.7214 / -0.7214 / -0.7805` |
| `hybrid2025 2025-10 long` | rank_q | `+1.3200` | `-9.2880` | `+13.5100` | `+1.9177 / +1.2787 / +2.3111` |
| `hybrid2025 2025-11 short` | holding | `+0.8200` | `-8.9760` | `-39.9600` | `-1.0036 / -0.7755 / +8.7803` |
| `refit2025 2025-07 short` | score_floor | `-2.4240` | `-20.3448` | `-45.4596` | `-0.0480 / -0.0480 / +22.9117` |
| `refit2025 2025-08 long` | rank_q | `+6.5200` | `+3.6500` | `+13.7800` | `+1.3456 / +1.5166 / +3.3697` |
| `refit2025 2025-08 short` | side_margin_q | `+0.8500` | `+1.2000` | `+15.0830` | `-4.8145 / -4.9857 / +2.9348` |

Global gate read:

| source | gate | choices | actual sum | positive / negative | reading |
|---|---|---:|---:|---:|---|
| 00358 ranker | strict | `6` | `-83.4028` | `2 / 4` | global widening is unsafe |
| 00358 ranker | relaxed | `8` | `-68.0198` | `4 / 4` | 2024-11 appears, but bad tails dominate |
| 00322 base | strict | `3` | `-15.5408` | `1 / 2` | unsafe |
| 00322 base | relaxed | `7` | `-40.3960` | `3 / 4` | unsafe; 2024-11 picks bad 720m |

## Interpretation

- The 2024-11 row was not absent from the pre-00358 candidate feed. It was `stateful_available=true` in 00318, then selected by the one-fail greedy path and reclassified as `greedy_selected` in 00319.
- The strict-stage blocker for 2024-11 is only `score_floor`; score percentile, side-margin percentile, entry rank, side margin, and holding are all acceptable.
- Re-exposing selected one-fail rows solves the row-scope visibility problem for 2024-11, but not the EV / horizon calibration problem. Strict EV still blocks it, and relaxed EV can select 720m on base predictions.
- The same selected-onefail lane also re-exposes large overestimates such as `refit2025 2025-07 short 720m` and `hybrid2025 2025-11 short 720m`.
- Therefore the next implementation should not globally widen `available_candidates`. It should build a narrow target-aware replacement candidate path with horizon/tail guard and chronological confidence.

## Decision

- `selected_onefail_replacement` diagnostic scope is accepted infrastructure.
- Global selected-onefail row-scope widening is rejected.
- `fresh2024 2024-11` remains a target-aware replacement / horizon-calibration problem, not a solved candidate-generation problem.
- `refit2025 2025-03` remains a prediction-row universe coverage problem.
- Standard policy remains NoTrade.

## Next

1. For `fresh2024 2024-11`, test a narrow selected-onefail replacement replay that excludes 720m unless horizon confidence clears a prediction-only guard.
2. For `refit2025 2025-03`, inspect upstream family/month prediction inventory before 00318 repair target filtering.
3. Keep global selected-onefail widening out of standard policy.

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_selected_replacement_scope_diagnostics.py tests/test_entry_ev_selected_replacement_scope_diagnostics.py`: OK
- `uv run python -m unittest tests.test_entry_ev_selected_replacement_scope_diagnostics`: OK
- 00361 ranker/base selected replacement scope diagnostics: OK
