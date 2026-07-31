# Entry EV External Hybrid 2025-09..12 Replay

日時: 2026-07-02 07:49 JST
更新日時: 2026-07-02 07:49 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00269のHGB alias replayはpreflight止まりだったため、既存のHGB entry + MLP exit hybrid 2025-09..12へq99 prior guard方針を固定適用した。
- 使用したhybridは `data/reports/modeling/20260629_hgb_mlp_exit_hybrid_2025_09_12/predictions_hgb_entry_mlp_exit_2025_09_12.parquet`。
- `entry_ev_base_policy_input_aliases.py` でbase quantile / base riskを付けたが、holdingは既存 `pred_mlp_*_exit_event_minutes` をそのまま使った。
- exit-regret selector、pre-block side-gap、prior `direction_regime` guardは00267/00269と同じ設定で固定した。
- q99/floor5/rank90は9 candidate rows / 7 episodes / 3 active monthsだが、stateful replayは `-28.3940`, 6 trades, worst month `-19.2900`。
- prior guardはq99/q95とも発火0。no-guardとguard replayは同一。
- q95/floor5/rank90は15 candidate rows / 13 episodes / 4 active months、10 tradesで total `+0.0820` だが、worst month `-18.2640` でmonth floorを落とす。
- 判断: q99 prior guardは外部full-hybrid foldでも標準採用を支持しない。q95も月別tailでreject。標準policyはNoTrade。

## Artifacts

- External hybrid base inputs:
  - `data/reports/backtests/20260701_224656_20260702_entry_ev_external_hybrid_2025_0912_base_inputs_s1/`
- Exit-regret risk inputs:
  - `data/reports/backtests/20260701_224706_20260702_entry_ev_external_hybrid_2025_0912_exit_regret_risk_s1/`
- Selector inputs:
  - `data/reports/backtests/20260701_224722_20260702_entry_ev_external_hybrid_2025_0912_preblock_selector_t0p4_s1/`
  - `data/reports/backtests/20260701_224723_20260702_entry_ev_external_hybrid_2025_0912_postblock_selector_t0p4_s1/`
- Prior guard inputs:
  - `data/reports/backtests/20260701_224738_20260702_entry_ev_external_hybrid_2025_0912_prior_guard_inputs_s1/`
- q99 replay:
  - `data/reports/backtests/20260701_224800_20260702_entry_ev_external_hybrid_2025_0912_q99_preblock_noguard_s1/`
  - `data/reports/backtests/20260701_224800_20260702_entry_ev_external_hybrid_2025_0912_q99_prior_guard_s1/`
- q99 support:
  - `data/reports/backtests/20260701_224825_20260702_entry_ev_external_hybrid_2025_0912_q99_support_s1/`
  - `data/reports/backtests/20260701_224825_20260702_entry_ev_external_hybrid_2025_0912_q99_episode_support_s1/`
- q95 replay/support:
  - `data/reports/backtests/20260701_224850_20260702_entry_ev_external_hybrid_2025_0912_q95_prior_guard_s1/`
  - `data/reports/backtests/20260701_224851_20260702_entry_ev_external_hybrid_2025_0912_q95_support_s1/`
  - `data/reports/backtests/20260701_224851_20260702_entry_ev_external_hybrid_2025_0912_q95_episode_support_s1/`
- Combined admission:
  - `data/reports/backtests/20260701_224850_20260702_entry_ev_external_hybrid_2025_0912_q99_q95_combined_s1/`
  - `data/reports/backtests/20260701_224913_20260702_entry_ev_external_hybrid_2025_0912_q99_q95_admission_s1/`

## Input

Hybrid input:

| family | months | rows | selected score q99 | holding missing |
|---|---|---:|---:|---:|
| hybrid2025_0912 | `2025-09..12` | `118887` | `40.3697` | `0` |

Exit-regret risk distribution:

| side | risk mean | bucket share | global share |
|---|---:|---:|---:|
| long | `0.2793` | `0.4688` | `0.5312` |
| short | `0.1980` | `0.6846` | `0.3154` |

Selector block summary:

| long block | short block | any side block | selected side changed |
|---:|---:|---:|---:|
| `0.2254` | `0.0982` | `0.2790` | `0.1206` |

## Prior Guard Inputs

| candidate | pre pass | post pass | newly admitted | newly admitted short | blocked rows |
|---|---:|---:|---:|---:|---:|
| q99/floor5/rank90 | `9` | `9` | `1` | `1` | `0` |
| q95/floor5/rank90 | `15` | `19` | `5` | `4` | `0` |

The prior guard has no direct effect in this fold.

## Replay

q99/floor5/rank90:

| total pnl | worst month | trades | max DD | max side share |
|---:|---:|---:|---:|---:|
| `-28.3940` | `-19.2900` | `6` | `26.7600` | `0.6667` |

q95/floor5/rank90:

| total pnl | worst month | trades | max DD | max side share |
|---:|---:|---:|---:|---:|
| `+0.0820` | `-18.2640` | `10` | `26.7600` | `0.7000` |

Monthly q99:

| month | pnl | trades | note |
|---|---:|---:|---|
| 2025-09 | `-18.2640` | `2` | short-only loss |
| 2025-10 | `0.0000` | `0` | no trade |
| 2025-11 | `+9.1600` | `2` | mixed side |
| 2025-12 | `-19.2900` | `2` | mixed side, short tail |

## Support

| candidate | candidate rows | episodes | active months | long episodes | short episodes |
|---|---:|---:|---:|---:|---:|
| q99/floor5/rank90 | `9` | `7` | `3` | `2` | `5` |
| q95/floor5/rank90 | `15` | `13` | `4` | `3` | `10` |

Reading:

- q99 is sparse again in this full hybrid fold.
- q95 improves support to month10-trade level but still has a negative worst month.
- This is not a candidate to rescue by lowering q/rank/floor further; that already failed in 00268.

## Admission

Combined q99/q95 selector:

| candidate | eligible | blockers | total pnl | min month | trades |
|---|---|---|---:|---:|---:|
| q95/floor5/rank90 | false | `month_pnl_below_floor` | `+0.0820` | `-18.2640` | `10` |
| q99/floor5/rank90 | false | `positive_roles_low;total_pnl_below_floor;role_total_pnl_below_floor;month_pnl_below_floor;role_trades_low;month_trades_low` | `-28.3940` | `-19.2900` | `6` |

Selected policy:

```text
no_trade
```

## Decision

Accepted:

- fixed external full-hybrid replay evidence
- q95 stress comparison on the same fold

Rejected:

- q99 prior guard standard promotion
- q95 as a replacement standard candidate
- further q/rank/floor relaxation on this fold

Standard policy remains NoTrade.

## Next

1. Stop trying to standardize the current q99 prior guard family; it has now failed external HGB and external full-hybrid preflights.
2. Shift back to model/data design: richer chronology, better exit timing constraints, and side/regime robustness rather than threshold rescue.
3. If continuing this branch, diagnose 2025-09 and 2025-12 losses only for feature/target insight, not for blacklist tuning.

## Verification

- external hybrid base input generation: OK
- exit-regret risk input generation: OK
- pre/post selector input generation: OK
- prior guard input generation: OK
- q99 no-guard and prior-guard replay: OK
- q95 prior-guard stress replay: OK
- q99/q95 support and episode diagnostics: OK
- q99/q95 combined admission selector: OK
