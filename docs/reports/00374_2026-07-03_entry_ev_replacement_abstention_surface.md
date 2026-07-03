# Entry EV Replacement Abstention Surface

日時: 2026-07-03 21:18 JST
更新日時: 2026-07-03 21:18 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00373の次アクションとして、replacement candidateを通す/捨てる abstention gate をsurface上で診断した。
- 候補を捨てた場合はskip-onlyではなく「介入しない」としてbaseline月PnLに戻す。winner damageは実際にreplacement interventionしたtradeだけで数える。
- `abstain_all_replacements` や一部の厳しいgateは全surface rowsで制約を通るが、current-negative改善は0なのでpolicy改善ではない。
- observable gateでは `prior_actual_mean >= 25`、`prior_margin >= 0`、`selection_mae_margin >= 0`、`prior_count >= 100/150` などが、非oracleでも `refit2025 2025-03` だけへ介入し、baseline-positive degradation 0 / winner intervention 0で通る行を作った。
- 例: `feature:side_gap_ge0p15_lossfirst_lt0p30` + `prior_actual_mean` + candidate prior count `>=100` + abstention `prior_actual_mean >= 25` は、`refit2025 2025-03` のlossだけに介入し、current-negative delta `+20.2470`、mean delta `+2.0247`、baseline-positive degraded 0。
- `hgb2024_0306 2024-05` は同ruleでcandidate prior actual mean `14.4308` のため介入せず、`+0.9578` のbaseline維持になる。
- 判断: replacement abstention surfaceはaccepted infrastructure。`prior_actual_mean >= 25` 系はdiagnostic candidateだが、target 1件への介入に近いため標準policy化しない。標準policyはNoTrade。

## Artifacts

Added script:

- `scripts/experiments/entry_ev_replacement_abstention_surface_diagnostics.py`

Added tests:

- `tests/test_entry_ev_replacement_abstention_surface_diagnostics.py`

Run:

- `data/reports/backtests/20260703_121800_20260703_entry_ev_00374_replacement_abstention_surface/`

Outputs:

- `replacement_abstention_surface_choices.csv`
- `replacement_abstention_surface_summary.csv`
- `replacement_abstention_gate_summary.csv`
- `replacement_abstention_meta.json`

## Method

Input:

- `data/reports/backtests/20260703_082714_20260703_entry_ev_00373_winner_damage_ranked_selector_surface/support_sufficient_selector_surface_choices.csv`

Simulation:

```text
if replacement candidate passes abstention gate:
    intervene and use original replacement result
else:
    do not intervene; month PnL remains baseline
```

Constraint metrics are computed on actual interventions:

- intervention loss precision `>=0.5`
- winner interventions 0
- baseline-positive degradation 0
- current-negative delta `>=0`

Swept observable gates include:

- `candidate_pred_pnl >= threshold`
- `selection_score >= threshold`
- `prior_actual_mean >= threshold`
- `prior_margin = prior_actual_mean - prior_mae >= threshold`
- `selection_mae_margin = selection_score - prior_mae >= threshold`
- `pred_mae_margin = candidate_pred_pnl - prior_mae >= threshold`
- `prior_count >= threshold`
- `prior_month_count >= threshold`
- a few simple combined gates

`oracle_actual_nonnegative` is included only as a diagnostic leak and must not be treated as executable policy evidence.

## Result

Gate-level summary:

| abstention gate | observable | passing rows | best current-negative delta | best mean delta | note |
|---|---|---:|---:|---:|---|
| `abstain_all_replacements` | yes | 16/16 | `0.0000` | `0.0000` | No intervention, not a repair policy |
| `pred_mae_margin_ge_0` | yes | 16/16 | `0.0000` | `0.0000` | Too strict / no useful interventions |
| `prior_actual_mean_ge_30` | yes | 12/16 | `0.0000` | `+10.7498` | Mostly skips current-negative repair |
| `prior_actual_mean_ge_25` | yes | 6/16 | `+20.2470` | `+5.8913` | Keeps some useful loss interventions, no winner intervention in passing rows |
| `prior_margin_ge_0` | yes | 6/16 | `+20.2470` | `+2.0247` | Nonoracle passing row exists |
| `prior_count_ge_100` | yes | 4/16 | `+20.2470` | `+19.4980` | Strong in oracle rows, nonoracle row is target-local |

Representative nonoracle passing row:

| gate | risk selector | score | prior count | interventions | loss interventions | winner interventions | baseline-positive degraded | current-negative delta | mean delta |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| `prior_actual_mean_ge_25` | `feature:side_gap_ge0p15_lossfirst_lt0p30` | `prior_actual_mean` | `100` | 1 | 1 | 0 | 0 | `+20.2470` | `+2.0247` |
| `prior_margin_ge_0` | `feature:side_gap_ge0p15_lossfirst_lt0p30` | `prior_actual_mean` | `100` | 1 | 1 | 0 | 0 | `+20.2470` | `+2.0247` |
| `prior_actual_mean_ge_20` | `feature:ev_ge5_lossfirst_lt0p30` | `prior_actual_mean` | `100` | 2 | 2 | 0 | 0 | `+18.2394` | `+6.5621` |

Target detail for the representative row:

| target | baseline | risk trade | gate passed | after | delta |
|---|---:|---:|---|---:|---:|
| `refit2025 2025-03` | `-0.4730` | loss `-2.3400` | yes | `+19.7740` | `+20.2470` |
| `hgb2024_0306 2024-05` | `+0.9578` | loss `-3.8520` | no | `+0.9578` | `0.0000` |
| `refit2025 2025-04` | `+107.8580` | winner `+5.6900` | no | `+107.8580` | `0.0000` |
| `refit2025 2025-10` | `+27.7980` | winner `+7.5600` | no | `+27.7980` | `0.0000` |

This is the first surface where a nonoracle row can satisfy the winner-damage constraints while improving the current-negative target. However, the evidence is still thin: the useful intervention is essentially one current-negative target, and the threshold is selected after seeing this surface.

## Decision

Accepted:

- replacement abstention surface diagnostics
- intervention-only winner damage accounting
- baseline fallback when replacement is abstained

Diagnostic candidate:

- `prior_actual_mean >= 25` / `prior_margin >= 0` style abstention over `prior_actual_mean` replacement mode

Rejected as standard policy:

- no-intervention gates as "improvement"
- using oracle actual gate
- promoting the threshold without cross-target / walk-forward stress

Standard policy remains NoTrade.

## Next

1. Re-run abstention gates on additional target sets or held-out artifact windows to check whether `prior_actual_mean >= 25` is stable.
2. Split the result into current-negative repair and cross-artifact robustness so the one useful intervention is not overstated.
3. Add abstention-gated rows back into the selector surface ranking as a first-class score mode, but keep them diagnostic until support improves.

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_replacement_abstention_surface_diagnostics.py tests/test_entry_ev_replacement_abstention_surface_diagnostics.py`: OK
- `uv run python -m unittest tests.test_entry_ev_replacement_abstention_surface_diagnostics`: OK
- 00374 replacement abstention surface run: OK
