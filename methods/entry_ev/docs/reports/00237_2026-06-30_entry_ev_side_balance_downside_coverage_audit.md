# Entry EV Side Balance Downside Coverage Audit

日時: 2026-06-30 19:41 JST
更新日時: 2026-06-30 19:41 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00236の反省に沿って、candidate全体平均ではなく required role ごとの coverage/support を監査する `scripts/experiments/entry_ev_side_balance_downside_coverage_audit.py` を追加した。
- required rolesは `cal2024_calibration_validation`, `fresh2024_validation`, `refit2025_validation`。各candidateについて、missing role、active role、role別prior zero、role別support、role別pressure、role別PnLを集計する。
- strict coverage gateでは全候補NoTrade。
- PnL床だけ緩めたrelaxed coverage gateでも全候補NoTrade。coverage/support sensitivity 216条件すべてでNoTradeだった。
- 00236で低pressureに見えたfloor10系は、fresh roleが欠損し、missing required role / active role不足 / prior zero / pressureで落ちる。
- floor5系はrequired 3 rolesを満たすが、fresh tail、required role PnL、月次PnL、cal2024 prior-zero過多で落ちる。
- 判断: coverage/support auditはaccepted。low pressure候補を採用しないためのpreflightとして有効。現候補は標準採用しない。

## Artifacts

- Script: `scripts/experiments/entry_ev_side_balance_downside_coverage_audit.py`
- Test: `tests/test_entry_ev_side_balance_downside_coverage_audit.py`
- Strict coverage audit:
  - `data/reports/backtests/20260630_104105_20260630_entry_ev_side_balance_downside_coverage_strict_s1/`
- Relaxed coverage audit:
  - `data/reports/backtests/20260630_104115_20260630_entry_ev_side_balance_downside_coverage_relaxed_s1/`
- Input:
  - `data/reports/backtests/20260630_103224_20260630_entry_ev_side_balance_downside_selector_relaxed_s1/role_month_side_balance_downside_features.csv`

## Method

Role-level coverage summary:

```text
required_roles =
  cal2024_calibration_validation
  fresh2024_validation
  refit2025_validation

role_present
role_active
role_trade_count
role_total_pnl
role_min_month_pnl
role_prior_zero_share
role_prior_support_mean
role_feature_pressure_score
```

Candidate gate checks:

```text
required_roles_missing
active_required_roles_low
required_role_trades_low
total_pnl_below_floor
required_role_total_pnl_below_floor
required_month_pnl_below_floor
required_role_prior_zero_high
required_role_prior_support_low
required_role_pressure_high
```

This intentionally separates "low pressure" from "enough evidence". Missing roles are not treated as safe low risk.

## Strict Coverage Gate

Gate:

```text
min active required roles = 3
min required role trades = 1
min total PnL = 0
min required role total PnL = 0
min required month PnL = 0
max required role prior zero share = 0.75
max required role pressure = 0.50
```

| candidate | active roles | missing roles | total | min required role | min month | prior zero max | support min | pressure max | blockers |
|---|---:|---|---:|---:|---:|---:|---:|---:|---|
| q99 floor10 | `2` | fresh2024 | `+1.1920` | `-7.3764` | `-7.3764` | `1.0000` | `0.0000` | `1.0000` | missing/active/trades/role/month/zero/pressure |
| q95 floor10 | `2` | fresh2024 | `+15.5736` | `-11.2600` | `-9.4600` | `1.0000` | `0.0000` | `1.0000` | missing/active/trades/role/month/zero/pressure |
| q99 floor5 | `3` | none | `-10.2286` | `-38.3550` | `-35.7120` | `0.9231` | `0.0308` | `0.4666` | total/role/month/zero |
| q95 floor5 | `3` | none | `+14.6138` | `-82.2428` | `-46.5308` | `0.8846` | `0.0462` | `0.4596` | role/month/zero |

Result: NoTrade.

## Relaxed Coverage Gate

Relaxed gate only loosens realized PnL floors:

```text
min required role total PnL = -15
min required month PnL = -10
coverage/support gates unchanged
```

Result is still NoTrade.

Feature sensitivity:

- 216 grid rows.
- 216 rows selected NoTrade.
- 0 rows selected a policy.

This is important: once required role coverage and prior-zero support are respected, the relaxed floor10 candidates from 00236 disappear. The remaining floor5 candidates have adequate role coverage but fail actual robustness and still have too much prior-zero exposure in cal2024.

## Role-Level Findings

| candidate | role | present | trades | role PnL | min month | prior zero | support | pressure | uncovered loss |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| q95 floor10 | cal2024 | true | `21` | `-11.2600` | `-9.4600` | `1.0000` | `0.0000` | `0.1500` | `-50.0040` |
| q95 floor10 | fresh2024 | false | `0` | `0.0000` | `0.0000` | `1.0000` | `0.0000` | `1.0000` | `0.0000` |
| q95 floor10 | refit2025 | true | `2` | `+26.8336` | `+26.8336` | `0.0000` | `0.9000` | `0.7355` | `0.0000` |
| q95 floor5 | cal2024 | true | `26` | `+2.8654` | `+0.1014` | `0.8846` | `0.0462` | `0.1696` | `-50.3676` |
| q95 floor5 | fresh2024 | true | `8` | `-82.2428` | `-46.5308` | `0.3750` | `0.3500` | `0.4213` | `-79.0368` |
| q95 floor5 | refit2025 | true | `19` | `+93.9912` | `+9.5300` | `0.3684` | `0.4105` | `0.4596` | `-23.6484` |
| q99 floor10 | fresh2024 | false | `0` | `0.0000` | `0.0000` | `1.0000` | `0.0000` | `1.0000` | `0.0000` |
| q99 floor5 | fresh2024 | true | `6` | `-38.3550` | `-35.7120` | `0.3333` | `0.4000` | `0.4666` | `-33.4920` |

Two separate failure classes are now visible:

1. Low-pressure floor10 candidates are not adequately covered.
2. Covered floor5 candidates still have realized role/month tail failures.

## Decision

Accepted:

- Coverage/support audit script.
- Required-role coverage summary.
- Role-level prior zero/support/pressure diagnostics.
- Coverage gate sensitivity.

Not accepted:

- Any current floor10 candidate as a policy.
- Any current floor5 candidate as a policy.
- Using missing role as implicit NoTrade-safe evidence.

Standard policy remains NoTrade.

## Next

1. Require role coverage and prior support as a preflight before using pressure/risk features in selection.
2. Add the same coverage features into future composite selector: executable EV, exit capture, direction-side inversion, side-balance downside pressure.
3. Investigate cal2024 prior-zero exposure separately; early months have no prior support and should not be treated as low risk.
4. For model training, add explicit missing-support indicators so the model learns "unknown risk" instead of "low risk".

## Verification

- `python3 -m py_compile scripts/experiments/entry_ev_side_balance_downside_coverage_audit.py tests/test_entry_ev_side_balance_downside_coverage_audit.py`: OK
- `python3 -m unittest tests.test_entry_ev_side_balance_downside_coverage_audit`: OK
- Strict coverage audit: OK
- Relaxed coverage audit: OK
