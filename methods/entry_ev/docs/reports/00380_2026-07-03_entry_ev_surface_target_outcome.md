# Entry EV Surface Target Outcome Diagnostics

日時: 2026-07-03 22:10 JST
更新日時: 2026-07-03 22:10 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00378 surfaceの制約通過をtarget単位に分解する `entry_ev_surface_target_outcome_diagnostics.py` を追加した。
- 各targetを `no_risk_trade`, `risk_trade_winner`, `loss_selected_no_supported_candidate`, `loss_selected_no_replacement`, `loss_replacement_degrades`, `loss_replacement_improves_but_still_negative`, `loss_replacement_repairs_month` に分類する。
- 00378で一見制約通過した非oracle `feature:ev_ge5_lossfirst_lt0p30` + `prior_actual_mean` は、5 target中1件だけが修復成功、3件はsupported candidate 0、1件はrisk trade未検知だった。
- つまり「loss selected 4 / winner selected 0 / precision 1.0」は、4件を直せたという意味ではない。
- 判断: target-level outcome categoryはaccepted infrastructure。00378の非oracle passはpolicy readinessではなく、候補不足とrisk detection gapの切り分け結果として読む。標準policyはNoTrade。

## Artifacts

Input surface:

- `data/reports/backtests/20260703_125327_20260703_entry_ev_00378_074738_aligned_current_negative_selector_surface/`

Outcome diagnostics:

- `data/reports/backtests/20260703_131006_20260703_entry_ev_00380_surface_target_outcome_00378/`

Code:

- `scripts/experiments/entry_ev_surface_target_outcome_diagnostics.py`
- `tests/test_entry_ev_surface_target_outcome_diagnostics.py`

## Method

Each row of `support_sufficient_selector_surface_choices.csv` is classified by observable outcome state:

| category | meaning |
|---|---|
| `no_risk_trade` | risk selector did not select a trade for the target |
| `risk_trade_winner` | risk selector selected a trade, but it was not a loss |
| `loss_selected_no_supported_candidate` | loss was selected, but supported replacement candidate was 0 |
| `loss_selected_no_replacement` | supported candidate existed, but replacement was not chosen |
| `loss_replacement_degrades` | replacement was chosen and worsened monthly PnL |
| `loss_replacement_improves_but_still_negative` | replacement improved monthly PnL but month stayed negative |
| `loss_replacement_repairs_month` | replacement improved monthly PnL to non-negative |

The summary then counts success, candidate gap, risk gap, and replacement gap by surface row.

Run:

```text
uv run python scripts/experiments/entry_ev_surface_target_outcome_diagnostics.py \
  --surface-run-dir data/reports/backtests/20260703_125327_20260703_entry_ev_00378_074738_aligned_current_negative_selector_surface \
  --run-label 20260703_entry_ev_00380_surface_target_outcome_00378 \
  --print-rows 20
```

## Outcome Summary

| risk selector | score | targets | success | candidate gap | risk gap | replacement gap | mean after | min after | category counts |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| `oracle:worst_loss` | `prior_actual_mean` | 5 | 2 | 3 | 0 | 0 | `+4.2790` | `-17.6936` | `repairs:2;candidate_gap:3` |
| `combined:any_lossrisk` | `prior_actual_mean` | 5 | 1 | 2 | 2 | 0 | `+3.5350` | `-17.6936` | `repairs:1;candidate_gap:2;winner:2` |
| `feature:side_gap_ge0p15_lossfirst_lt0p30` | `prior_actual_mean` | 5 | 1 | 2 | 2 | 0 | `+0.0770` | `-17.6936` | `repairs:1;candidate_gap:2;no_risk:1;winner:1` |
| `feature:ev_ge5_lossfirst_lt0p30` | `prior_actual_mean` | 5 | 1 | 3 | 1 | 0 | `-0.3246` | `-17.6936` | `repairs:1;candidate_gap:3;no_risk:1` |

The oracle row is useful as an upper bound: even perfect loss selection cannot repair targets that have no supported replacement candidate.

## Nonoracle Detail

Representative row:

```text
risk_selector = feature:ev_ge5_lossfirst_lt0p30
replacement_score_mode = prior_actual_mean
candidate_min_prior_count = 50
```

| target | baseline | outcome | supported candidates | after | delta | reading |
|---|---:|---|---:|---:|---:|---|
| `hgb2024_0306 2024-03` | `-17.6936` | `loss_selected_no_supported_candidate` | 0 | `-17.6936` | `0.0000` | early-month same-family prior shortage |
| `fresh2024 2024-03` | `-0.3636` | `loss_selected_no_supported_candidate` | 0 | `-0.3636` | `0.0000` | support-limited candidate gap |
| `fresh2024 2024-11` | `-0.6120` | `loss_selected_no_supported_candidate` | 0 | `-0.6120` | `0.0000` | support-limited candidate gap |
| `refit2025 2025-03` | `-0.4730` | `loss_replacement_repairs_month` | 184 | `+17.7664` | `+18.2394` | only effective nonoracle repair |
| `hybrid2025_0912 2025-11` | `-0.7200` | `no_risk_trade` | 0 | `-0.7200` | `0.0000` | risk selector did not reach the target |

This explains why mean after PnL stays negative even when the winner-damage constraints pass.

## Decision

Accepted:

- target-level outcome diagnostic categories
- separating risk-selection gap, candidate-support gap, and replacement-selection gap
- using these counts as additional reading for selector surface reports

Rejected:

- treating `loss selected` as `repair succeeded`
- treating no-risk/no-candidate baseline維持 as improvement
- promoting 00378 nonoracle pass to a standard policy

Standard policy remains NoTrade.

## Next

1. Add these outcome categories to surface ranking constraints, or at minimum require success count and candidate-gap count to be visible in every candidate comparison.
2. Continue shrunk cross-family prior diagnostics, but evaluate them by outcome category rather than mean PnL alone.
3. Keep support-sufficient repair and support-limited candidate generation as separate lanes.

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_surface_target_outcome_diagnostics.py tests/test_entry_ev_surface_target_outcome_diagnostics.py`: OK
- `uv run python -m unittest tests.test_entry_ev_surface_target_outcome_diagnostics`: OK
- 00380 surface target outcome diagnostics run: OK
