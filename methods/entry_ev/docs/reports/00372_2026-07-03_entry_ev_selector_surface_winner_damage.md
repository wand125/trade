# Entry EV Selector Surface Winner Damage

日時: 2026-07-03 17:16 JST
更新日時: 2026-07-03 17:16 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00371のselector surfaceをpost-processし、current-negative repairとcross-artifact robustnessを分けるwinner-damage diagnosticsを追加した。
- 制約は `loss_selection_precision >= 0.5`、`winner_selected_count == 0`、baseline-positive targetの悪化0、current-negative targetのdelta `>=0`。
- 00371の16 surface rowsで制約を通過したものは0件。
- 非oracleでは `feature:ev_ge5_lossfirst_lt0p30` だけがloss precision `0.5556` を満たすが、winner selected 4件、baseline-positive degraded 2-4件で落ちる。
- `combined:any_lossrisk` はmean deltaが最大だったが、loss precision `0.3000`、winner selected 7件で落ちる。
- `feature:side_gap_ge0p15_lossfirst_lt0p30` は00368単一targetでは有望だったが、複数targetではloss precision `0.2857`、winner selected 5件で落ちる。
- `oracle:worst_loss` はwinner selected 0 / precision 1.0だが、`hgb2024_0306 2024-05` でbaseline-positiveをnegativeへ反転させるため落ちる。これはreplacement selection/calibration側の失敗。
- 判断: winner-damage diagnosticsはaccepted infrastructure。現risk selectorも現replacement selectorも標準policy化しない。標準policyはNoTrade。

## Artifacts

New script:

- `scripts/experiments/entry_ev_selector_surface_winner_damage_diagnostics.py`

New tests:

- `tests/test_entry_ev_selector_surface_winner_damage_diagnostics.py`

Run:

- `data/reports/backtests/20260703_081549_20260703_entry_ev_00372_selector_surface_winner_damage/`

Inputs:

- `data/reports/backtests/20260703_080722_20260703_entry_ev_00371_canonical_support_sufficient_selector_surface/`

Outputs:

- `selector_surface_winner_damage_choices.csv`
- `selector_surface_winner_damage_summary.csv`
- `selector_surface_winner_damage_target_coverage.csv`
- `selector_surface_winner_damage_meta.json`

## Method

Post-process each 00371 choice row:

```text
current_negative:
  baseline_month_pnl < 0

current_nonnegative:
  baseline_month_pnl >= 0

winner selected:
  risk_trade_selected == true
  risk_trade_is_loss == false

baseline-positive degraded:
  baseline_month_pnl >= 0
  delta_vs_baseline < 0
```

Constraint:

```text
loss_selection_precision >= 0.5
winner_selected_count == 0
baseline_positive_degraded_count == 0
current_negative_min_delta >= 0
```

This treats winner selection as risk-selector damage even when the replacement later improves PnL. That is intentional: replacing a winner with an even larger winner is not evidence that the risk selector can identify losses.

## Constraint Result

| group | rows passing |
|---|---:|
| all surface rows | 0 / 16 |
| loss precision | 8 / 16 |
| winner selected count | 4 / 16 |
| baseline-positive degradation | 0 / 16 |
| current-negative delta | 16 / 16 |

No row passed all constraints because every row degraded at least one baseline-positive target.

## Surface Summary

| risk selector | score | prior | loss precision | loss selected | winner selected | baseline-positive degraded | current-negative min delta | mean delta | pass |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| `oracle:worst_loss` | `bias_corrected` | `>=100` | `1.0000` | 10 | 0 | 1 | `+10.0070` | `+19.4980` | no |
| `feature:ev_ge5_lossfirst_lt0p30` | `bias_corrected` | `>=100` | `0.5556` | 5 | 4 | 2 | `+7.9994` | `+8.2042` | no |
| `combined:any_lossrisk` | `bias_corrected` | `>=100` | `0.3000` | 3 | 7 | 1 | `+6.2870` | `+12.3633` | no |
| `feature:side_gap_ge0p15_lossfirst_lt0p30` | `bias_corrected` | `>=100` | `0.2857` | 2 | 5 | 1 | `+10.0070` | `+5.3253` | no |

The important point is not just that no rule passes. The failure mode differs:

- non-oracle rules fail mostly because they select too many winners;
- oracle fails because replacement selection can turn a positive baseline month negative.

## Oracle Failure

Even with perfect loss selection, `hgb2024_0306 2024-05` fails:

| role | month | baseline | selected loss | replacement actual | after | delta |
|---|---|---:|---:|---:|---:|---:|
| `hgb2024_0306_external` | `2024-05` | `+0.9578` | `-11.4480` | `-24.1788` | `-11.7730` | `-12.7308` |

This means the next fix cannot be only a better loss-risk selector. The replacement selector needs a stronger abstention / calibration layer for `hgb2024_0306 2024-05`-type failures.

## Decision

Accepted:

- winner-damage post-process diagnostics
- current-negative vs current-nonnegative split
- explicit pass/fail constraints for selector surface rows

Rejected as standard policy:

- selecting a surface by mean delta alone
- treating replacement-compensated winner deletion as a loss-risk success
- current `combined:any_lossrisk`
- current `side_gap_ge0p15_lossfirst_lt0p30`
- current replacement selector as sufficient under oracle loss selection

Standard policy remains NoTrade.

## Next

1. Add winner-damage constrained objective directly to selector surface ranking.
2. Add replacement abstention/calibration diagnostics for `hgb2024_0306 2024-05`.
3. Keep current-branch negative repair separate from cross-artifact robustness when reporting model quality.

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_selector_surface_winner_damage_diagnostics.py tests/test_entry_ev_selector_surface_winner_damage_diagnostics.py`: OK
- `uv run python -m unittest tests.test_entry_ev_selector_surface_winner_damage_diagnostics`: OK
- 00372 winner-damage diagnostics run: OK
