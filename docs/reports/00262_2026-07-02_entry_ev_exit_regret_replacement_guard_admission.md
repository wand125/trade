# Entry EV Exit Regret Replacement Guard Admission

日時: 2026-07-02 02:35 JST
更新日時: 2026-07-02 02:35 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00261の replacement guard replayを、NoTrade-first admission selectorへ通した。
- strict gate、relaxed diagnostic gateともに `selected = no_trade`。
- strict gateでは全4候補が `positive_roles_low`, `active_roles_low`, `role_trades_low`, `month_trades_low` を含むblockerで落ちた。
- relaxed diagnostic gateでも全4候補が `role_trades_low` で落ちた。
- 主因は `fresh2024_broad_validation` が全候補で0 tradeとなり、role-level trade supportを満たせないこと。
- support-only relaxationとして `min_role_trades=0`, `min_month_trades=0` を許すと q99/floor5 が通るが、これは標準ゲートではない。
- q99/floor5 support-relaxed resultは validation total `+27.1222`, min role total `0.0000`, worst month `-54.2268`, trades `36`, max DD `54.5368`, max side share `0.6944`。
- q95/floor5は total `+63.5468` だが positive role countが1で、support-relaxedでも不合格。
- 判断: replacement guard候補は admission gate diagnosticを通したが、標準policyにはしない。標準policyはNoTrade。

## Artifacts

- Strict admission:
  - `data/reports/backtests/20260701_173345_20260702_entry_ev_exit_regret_replguard_admission_strict3_s1/`
- Relaxed diagnostic admission:
  - `data/reports/backtests/20260701_173345_20260702_entry_ev_exit_regret_replguard_admission_relaxed3_s1/`
- Support-relaxed diagnostic admission:
  - `data/reports/backtests/20260701_173532_20260702_entry_ev_exit_regret_replguard_admission_support_relaxed3_s1/`
- Source replay:
  - `data/reports/backtests/20260701_172413_20260702_entry_ev_exit_regret_selector_replguard_confextreme_t0p4_broad_backtest_s1/monthly_policy_metrics.csv`

## Admission Settings

Validation roles:

```text
cal2024_calibration_validation
fresh2024_broad_validation
refit2025_broad_validation
```

Strict gate:

```text
min_total_pnl       = 0
min_role_total_pnl  = 0
min_month_pnl       = 0
min_role_trades     = 10
min_month_trades    = 1
max_side_trade_share = 0.75
```

Relaxed diagnostic gate:

```text
min_positive_roles  = 2
min_active_roles    = 2
min_total_pnl       = 0
min_role_total_pnl  = -2
min_month_pnl       = -60
min_role_trades     = 10
min_month_trades    = 0
max_side_trade_share = 0.75
```

Support-relaxed diagnostic gate:

```text
min_positive_roles  = 2
min_active_roles    = 2
min_total_pnl       = 0
min_role_total_pnl  = -2
min_month_pnl       = -60
min_role_trades     = 0
min_month_trades    = 0
max_side_trade_share = 0.75
```

The support-relaxed gate is not a standard adoption gate. It exists only to separate PnL/side limits from the zero-activity fresh role problem.

## Results

Strict gate selected:

```json
{
  "selected": "no_trade",
  "reason": "no validation-role candidate passed the pre-registered gates"
}
```

Relaxed diagnostic selected:

```json
{
  "selected": "no_trade",
  "reason": "no validation-role candidate passed the pre-registered gates"
}
```

Support-relaxed diagnostic selected:

```text
candidate = q99_sg95_rank90_floor5_side_regime_session_month
selected  = policy
reason    = best eligible validation-role candidate
```

Candidate summary:

| candidate | strict eligible | relaxed eligible | support-relaxed eligible | validation total | min role total | worst month | trades | max DD | max side share | blockers under relaxed |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| q99/floor5 | no | no | yes | `+27.1222` | `0.0000` | `-54.2268` | `36` | `54.5368` | `0.6944` | `role_trades_low` |
| q95/floor5 | no | no | no | `+63.5468` | `-1.6986` | `-59.8792` | `71` | `59.8792` | `0.7324` | `positive_roles_low;role_trades_low` |
| q99/floor10 | no | no | no | `+1.0804` | `-7.4880` | `-7.4880` | `10` | `7.4880` | `0.7000` | `positive_roles_low;role_total_pnl_below_floor;role_trades_low` |
| q95/floor10 | no | no | no | `-39.7360` | `-28.4760` | `-28.4760` | `23` | `37.6890` | `0.6522` | `positive_roles_low;total_pnl_below_floor;role_total_pnl_below_floor;role_trades_low` |

## Reading

The guard improved broad and fixed replay in 00261, but admission selection exposes a separate weakness:

- The candidate has no activity in `fresh2024_broad_validation`.
- The candidate is therefore not supported by all validation roles.
- q99/floor5 is positive in two roles and neutral in one role, but the neutral role is neutral because it does not trade, not because it traded safely.
- q95/floor5 has better total PnL, but only one positive role, so it is a stronger same-window total candidate but a weaker cross-role candidate.

This matters because NoTrade-first selection is meant to reject policies that only work in a subset of roles. Allowing zero-trade roles can hide missing support and produce a candidate that looks stable only because it stays inactive in a hard window.

## Decision

Accepted:

- Replacement guard admission diagnostic.
- Evidence that q99/floor5 is the only near-pass under support-relaxed conditions.
- Evidence that `role_trades_low` is now the primary blocker after guard replay.

Not accepted:

- Standard-policy promotion.
- Treating support-relaxed q99/floor5 as a selected production policy.
- Treating q95/floor5 as better because it has the largest same-window total PnL.
- Relaxing `min_role_trades` in the standard gate without additional chronology.

Standard policy remains NoTrade.

## Next

1. Keep `exit_regret_selector_replguard_confidenceexit_bucket_t0p4` and `strong,nonpositive` guard fixed.
2. Apply it to an additional chronology or another family without changing threshold, quantile, floor, or guard bucket.
3. Diagnose why `fresh2024_broad_validation` produces 0 trades after the guard: missing high-quantile support, score scale, side-gap distribution, or entry floor.
4. Keep q99/floor5 as the support-relaxed diagnostic candidate for external validation; keep q95/floor5 as same-window total diagnostic only.
5. Do not standardize until role trade support, role PnL, month floor, side share, and NoTrade-first comparison all pass.

## Verification

- strict admission selector run: OK
- relaxed diagnostic admission selector run: OK
- support-relaxed diagnostic admission selector run: OK
