# Group Loss Penalty Ranking

日時: 2026-06-28 17:30 JST
更新日時: 2026-06-28 17:30 JST

## Summary

- Experiment ID: `group_loss_penalty_ranking`
- Status: implemented, smoke-tested, and kept as a diagnostic ranking axis
- Main result: validation ranking can be shifted away from candidates with deep group losses, but 2024-12 holdout still loses to NoTrade.
- Report numbering note: this file is numbered from the internal `日時`, not filesystem mtime or `更新日時`.

## Implementation

`model-candidate-selection` に `--group-loss-penalty-weight` を追加した。

The penalty is:

```text
group_loss_penalty =
  max(0, -side_adjusted_pnl_min_all)
+ max(0, -direction_session_adjusted_pnl_min_all)
+ max(0, -combined_regime_adjusted_pnl_min_all)
+ max(0, -direction_combined_regime_adjusted_pnl_min_all)

robust_total_adjusted_pnl_min_cost =
  total_adjusted_pnl_min_cost - group_loss_penalty_weight * group_loss_penalty
```

`group_loss_penalty_weight=0.0` is the historical ranking. Non-zero values do not relax hard gates; they only reorder eligible candidates by a soft concentration penalty.

## Validation Comparison

Setup reused the delay `1` 4fold sweep from `docs/reports/00042_2026-06-28_delay1_combined_regime_holdout.md`.

Artifacts:

- weight `0.0`: `data/reports/backtests/20260628_082937_model_candidate_selection/`
- weight `1.0`: `data/reports/backtests/20260628_082923_model_candidate_selection/`

| weight | entry | short offset | max hold | cost min pnl | group loss penalty | robust cost min | direction/session min | combined min | direction/combined min |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `0.0` | `5` | `12` | `720` | `58.2310` | `191.6204` | `58.2310` | `-39.1058` | `-49.7778` | `-62.1324` |
| `1.0` | `5` | `20` | `720` | `38.6168` | `132.5520` | `-93.9352` | `-48.7918` | `-20.6574` | `-51.1704` |

Interpretation:

- The soft penalty selected a lower raw validation PnL candidate with shallower combined-regime loss.
- This is useful as a ranking lens, but the robust score is negative because every eligible candidate still has meaningful worst-group loss.

## 2024-12 Holdout

Artifact:

- `data/reports/backtests/20260628_083021_model_timed_ev_2024-12/`

| candidate | adjusted pnl | trades | profit factor | max drawdown | actual barrier miss rate | EV overestimate vs realized |
|---|---:|---:|---:|---:|---:|---:|
| previous combined-gate top, max hold `480` | `-149.7354` | `33` | `0.3820` | `176.6504` | `0.7576` | `21.8578` |
| group-loss penalty top, max hold `720` | `-126.0770` | `33` | `0.4731` | `165.9662` | `0.7576` | `21.2211` |

The penalty-ranked candidate improved the 2024-12 holdout loss, but still loses heavily to NoTrade. Worst holdout groups also moved into `long:london`, `range_low_vol`, and `long:range_low_vol`, so the ranking did not solve side/entry calibration.

## Decision

- Keep `--group-loss-penalty-weight` as a candidate-selection diagnostic and tie-break axis.
- Do not promote it to the standard selection rule yet.
- Harder group-loss filtering or soft ranking alone remains insufficient; it can reduce known concentration but does not create a robust edge in unseen months.

## Next Actions

1. Use `group_loss_penalty_weight` only in sensitivity tables until it survives multiple blind/holdout months.
2. Continue prioritizing side/entry calibration and profit-barrier hit calibration, because 2024-12 still shows high direction error and actual barrier miss.
3. Add a concise candidate-comparison table when future selections are run: raw cost min, group penalty, robust cost min, holdout PnL.
