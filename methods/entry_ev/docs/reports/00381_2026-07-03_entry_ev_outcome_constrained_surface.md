# Entry EV Outcome-Constrained Surface

日時: 2026-07-03 22:20 JST
更新日時: 2026-07-03 22:20 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00380のtarget outcome categoryを `entry_ev_support_sufficient_selector_surface_diagnostics.py` 本体へ統合した。
- `support_sufficient_selector_surface_choices.csv` に `target_outcome_category` と成功/gap flagを出力し、summaryに success / candidate gap / risk gap / replacement gap countsを追加した。
- 新しい `passes_target_outcome_constraints` を追加した。defaultは `min_target_outcome_success_count=1`, `max_target_candidate_gap_count=0`, `max_target_replacement_gap_count=0`, `max_target_risk_gap_count=-1`。
- 00378と同じsurface条件を再実行したところ、旧winner-damage制約は16行中8行が通過したが、target outcome制約は16行中0行だった。
- 判断: outcome-constrained surfaceはaccepted infrastructure。00378の旧passは候補不足を成功扱いしない読みへ修正された。標準policyはNoTrade。

## Artifacts

Run:

- `data/reports/backtests/20260703_131956_20260703_entry_ev_00381_outcome_constrained_surface_00378/`

Code:

- `scripts/experiments/entry_ev_support_sufficient_selector_surface_diagnostics.py`
- `tests/test_entry_ev_support_sufficient_selector_surface_diagnostics.py`

## Method

Re-ran the 00378 aligned surface with the same config and target set:

```text
config: data/reports/backtests/20260703_generated_surface_configs/00378_074738_long_tminus5_holdext_surface_config.json
targets:
  hgb2024_0306_external:2024-03:both
  fresh2024_validation:2024-03:both
  fresh2024_validation:2024-11:both
  refit2025_validation:2025-03:both
  refit2025_validation:2025-08:both
  hybrid2025_0912_external:2025-11:both
risk selectors:
  feature:side_gap_ge0p15_lossfirst_lt0p30
  feature:ev_ge5_lossfirst_lt0p30
  combined:any_lossrisk
  oracle:worst_loss
score modes:
  prior_actual_mean,bias_corrected
candidate prior counts:
  50,100
```

New target outcome constraints:

| parameter | value | meaning |
|---|---:|---|
| `min_target_outcome_success_count` | 1 | at least one target must be repaired to non-negative |
| `max_target_candidate_gap_count` | 0 | loss-selected-but-no-candidate is not allowed as a pass |
| `max_target_replacement_gap_count` | 0 | supported replacement failure is not allowed as a pass |
| `max_target_risk_gap_count` | -1 | risk gap is reported but not constrained by default |

This keeps old winner-damage constraints visible while adding a stricter repair-readiness layer.

## Result

| metric | count |
|---|---:|
| surface rows | 16 |
| old winner-damage pass | 8 |
| target outcome pass | 0 |
| both pass | 0 |

Best old-pass nonoracle rows:

| risk selector | score | prior count | old pass | outcome pass | success | candidate gap | risk gap | mean after | category counts |
|---|---|---:|---|---|---:|---:|---:|---:|---|
| `feature:ev_ge5_lossfirst_lt0p30` | `prior_actual_mean` | 50 | yes | no | 1 | 3 | 1 | `-0.3246` | `repairs:1;candidate_gap:3;no_risk:1` |
| `feature:ev_ge5_lossfirst_lt0p30` | `prior_actual_mean` | 100 | yes | no | 1 | 3 | 1 | `-0.3246` | `repairs:1;candidate_gap:3;no_risk:1` |
| `feature:ev_ge5_lossfirst_lt0p30` | `bias_corrected` | 50 | yes | no | 1 | 3 | 1 | `-2.3726` | `repairs:1;candidate_gap:3;no_risk:1` |
| `feature:ev_ge5_lossfirst_lt0p30` | `bias_corrected` | 100 | yes | no | 1 | 3 | 1 | `-2.3726` | `repairs:1;candidate_gap:3;no_risk:1` |

Oracle upper bound:

| risk selector | score | old pass | outcome pass | success | candidate gap | mean after |
|---|---|---|---|---:|---:|---:|
| `oracle:worst_loss` | `prior_actual_mean` | yes | no | 2 | 3 | `+4.2790` |
| `oracle:worst_loss` | `bias_corrected` | yes | no | 2 | 3 | `+2.2310` |

Even oracle loss selection cannot pass the new outcome layer because 3 targets still have no supported replacement candidate.

## Representative Target Detail

Nonoracle row:

```text
risk_selector = feature:ev_ge5_lossfirst_lt0p30
replacement_score_mode = prior_actual_mean
candidate_min_prior_count = 50
```

| target | baseline | outcome | supported candidates | after | delta |
|---|---:|---|---:|---:|---:|
| `hgb2024_0306 2024-03` | `-17.6936` | `loss_selected_no_supported_candidate` | 0 | `-17.6936` | `0.0000` |
| `fresh2024 2024-03` | `-0.3636` | `loss_selected_no_supported_candidate` | 0 | `-0.3636` | `0.0000` |
| `fresh2024 2024-11` | `-0.6120` | `loss_selected_no_supported_candidate` | 0 | `-0.6120` | `0.0000` |
| `refit2025 2025-03` | `-0.4730` | `loss_replacement_repairs_month` | 184 | `+17.7664` | `+18.2394` |
| `hybrid2025_0912 2025-11` | `-0.7200` | `no_risk_trade` | 0 | `-0.7200` | `0.0000` |

## Decision

Accepted:

- target outcome columns in the main selector surface artifact
- target outcome constraints as a separate pass/fail layer
- sorting surface summary with outcome pass and violation count before PnL

Rejected:

- reading old winner-damage pass as policy readiness
- treating candidate-gap baseline維持 as repair
- treating oracle old-pass rows as sufficient evidence while candidate gap remains

Standard policy remains NoTrade.

## Next

1. Continue early-month replacement calibration, but evaluate by `passes_target_outcome_constraints`, not old winner-damage pass alone.
2. Try shrunk cross-family prior only if it reduces candidate gap without introducing replacement gap or winner damage.
3. Keep support-limited target generation separate from support-sufficient replacement calibration.

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_support_sufficient_selector_surface_diagnostics.py tests/test_entry_ev_support_sufficient_selector_surface_diagnostics.py`: OK
- `uv run python -m unittest tests.test_entry_ev_support_sufficient_selector_surface_diagnostics`: OK
- 00381 outcome-constrained surface run: OK
