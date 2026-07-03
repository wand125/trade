# Entry EV Candidate Generation Gap Audit

日時: 2026-07-03 14:40 JST
更新日時: 2026-07-03 14:40 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00359で残った薄い月について、candidate generationのどこで落ちているかを `role/month/side/row_scope` 別に診断した。
- `entry_ev_candidate_generation_gap_audit.py` を追加し、base prediction / ranker prediction / replay candidateを同じtarget-scope表へ正規化した。
- stageは `no_prediction_rows`, `no_rows_in_scope`, `no_target_side_rows`, `no_target_support_rows`, `threshold_filtered`, `relaxed_only_candidate`, `strict_candidate_exists` へ分類する。
- actual PnLは `best_oracle_actual_pnl` やpositive countの診断列だけに使い、gateやstage分類には使わない。
- 00358 ranker側では、`fresh2024 2024-11 long` は月内1行だけあるが `available_candidates` が0。`greedy_selected` の1行だけがrelaxed条件で候補になる。
- `refit2025 2025-03 short` は00322 base / 00358 rankerの両方でprediction row自体が0。rankerやstateful replay以前にcandidate universeから落ちている。
- 判断: 次はglobal gateやrerankingではなく、`fresh2024 2024-11` のavailable候補化と、`refit2025 2025-03` のprediction-row universe拡張を分けて設計する。

## Artifacts

Added script:

- `scripts/experiments/entry_ev_candidate_generation_gap_audit.py`

Added tests:

- `tests/test_entry_ev_candidate_generation_gap_audit.py`

Runs:

- `data/reports/backtests/20260703_054032_20260703_entry_ev_00360_candidate_generation_gap_audit_00358_ranker/`
- `data/reports/backtests/20260703_054103_20260703_entry_ev_00360_candidate_generation_gap_audit_00322_base/`

Outputs per run:

- `candidate_generation_gap_target_scope_summary.csv`
- `candidate_generation_gap_horizon_rows.csv`
- `candidate_generation_gap_strict_gate_summary.csv`
- `candidate_generation_gap_relaxed_gate_summary.csv`
- `candidate_generation_gap_replay_summary.csv` when replay candidates are supplied
- `candidate_generation_gap_meta.json`

## Method

Target set:

```text
fresh2024_validation:2024-03:long
fresh2024_validation:2024-08:long
fresh2024_validation:2024-11:long
refit2025_validation:2025-03:short
refit2025_validation:2025-07:short
```

Row scopes:

```text
available_candidates
greedy_selected
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

The 00358 ranker run prefers `ranker_hv_*_pred_pnl` when present. The 00322 base run uses `pred_hv_*_pnl`.

## Target-Scope Results

00358 ranker prediction:

| target | row scope | stage | role/month rows | scope rows | target support rows | strict choices | relaxed choices | best actual | max pred PnL |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| `fresh2024 2024-03 long` | available | strict candidate exists | `18` | `17` | `17` | `13` | `17` | `+13.4900` | `+2.3779` |
| `fresh2024 2024-08 long` | available | strict candidate exists | `15` | `14` | `14` | `4` | `7` | `+10.3600` | `+2.8165` |
| `fresh2024 2024-11 long` | available | no rows in scope | `1` | `0` | `0` | `0` | `0` | n/a | n/a |
| `fresh2024 2024-11 long` | greedy | relaxed only candidate | `1` | `1` | `1` | `0` | `1` | `+2.4500` | `-0.7214` |
| `refit2025 2025-03 short` | available | no prediction rows | `0` | `0` | `0` | `0` | `0` | n/a | n/a |
| `refit2025 2025-03 short` | greedy | no prediction rows | `0` | `0` | `0` | `0` | `0` | n/a | n/a |
| `refit2025 2025-07 short` | available | strict candidate exists | `11` | `10` | `10` | `9` | `10` | `+26.4000` | `+11.2218` |

00322 base prediction comparison:

| target | row scope | stage | role/month rows | scope rows | target support rows | strict choices | relaxed choices | best actual | max pred PnL |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| `fresh2024 2024-11 long` | available | no rows in scope | `1` | `0` | `0` | `0` | `0` | n/a | n/a |
| `fresh2024 2024-11 long` | greedy | relaxed only candidate | `1` | `1` | `1` | `0` | `1` | `+2.4500` | `-0.0441` |
| `refit2025 2025-03 short` | available | no prediction rows | `0` | `0` | `0` | `0` | `0` | n/a | n/a |
| `refit2025 2025-03 short` | greedy | no prediction rows | `0` | `0` | `0` | `0` | `0` | n/a | n/a |

## Key Examples

`fresh2024_validation 2024-11 long` has one greedy row:

| source | timestamp | horizon | actual | pred PnL | prob | tail | model used |
|---|---|---:|---:|---:|---:|---:|---|
| 00322 base | 2024-11-29 03:22 UTC | 60m | `+0.3000` | `-2.9427` | `0.5704` | `0.2527` | true |
| 00322 base | 2024-11-29 03:22 UTC | 240m | `+2.4500` | `-0.4546` | `0.3952` | `0.4964` | true |
| 00322 base | 2024-11-29 03:22 UTC | 720m | `-5.2800` | `-0.0441` | `0.4765` | `0.4071` | true |
| 00358 ranker | 2024-11-29 03:22 UTC | 60m | `+0.3000` | `-0.7214` | `0.4839` | `0.1988` | true |
| 00358 ranker | 2024-11-29 03:22 UTC | 240m | `+2.4500` | `-0.7214` | `0.4812` | `0.2825` | true |
| 00358 ranker | 2024-11-29 03:22 UTC | 720m | `-5.2800` | `-0.7805` | `0.6016` | `0.3473` | true |

Reading:

- The `2024-11` issue is not missing horizon labels. It is a row-scope problem: the only usable row is not in `available_candidates`.
- Strict EV gate blocks this row because predicted PnL remains negative. Relaxed EV admits it, but there is only one market event.
- The 720m path is the bad tail; 60/240m are positive. This is another exit-timing / horizon-choice calibration problem, but support is too thin for a target-local rule.

## Interpretation

- `fresh2024 2024-03` is no longer a pure candidate-generation gap under 00358 ranker; it has available support. Its remaining issue is confidence/calibration and fallback history from 00324.
- `fresh2024 2024-08` has available support and strict candidates. Its known problem is singleton 720m risk, already isolated in 00357/00358.
- `fresh2024 2024-11` needs candidate generation into `available_candidates`, not just a reranker. The single greedy row shows there is at least one market event, but the standard candidate scope cannot see it.
- `refit2025 2025-03` needs a broader prediction-row universe. Since role/month rows are zero in both 00322 base and 00358 ranker, no horizon confidence layer can repair it downstream.
- The next implementation should treat these two targets differently: row-scope widening for `fresh2024 2024-11`, and source universe expansion for `refit2025 2025-03`.

## Decision

- Candidate generation gap audit is accepted infrastructure.
- Actual PnL remains diagnostic-only and is not used in stage classification or gate selection.
- `fresh2024 2024-11` is a row-scope/candidate availability problem.
- `refit2025 2025-03` is a prediction universe coverage problem.
- Standard policy remains NoTrade.

## Next

1. Trace why the `fresh2024 2024-11 long` greedy row is excluded from `available_candidates`, then test a prediction-only row-scope widening rule.
2. Audit the upstream filters that produce zero `refit2025 2025-03 short` prediction rows, starting from month/side inventory before support repair.
3. Keep `fresh2024 2024-03` on the fallback/non-model confidence lane, not the candidate-generation lane.
4. Keep `fresh2024 2024-08` on the singleton 720m guard / horizon calibration lane.

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_candidate_generation_gap_audit.py tests/test_entry_ev_candidate_generation_gap_audit.py`: OK
- `uv run python -m unittest tests.test_entry_ev_candidate_generation_gap_audit`: OK
- 00360 ranker and base candidate-generation gap audit runs: OK
