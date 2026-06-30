# Entry EV Quantile Role Selector

日時: 2026-06-30 15:47 JST
更新日時: 2026-06-30 15:47 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00219の次アクションとして、quantile policy結果を固定diagnostic月なしで選ぶrole-level NoTrade-first selectorを追加した。
- `scripts/experiments/entry_ev_quantile_policy_selection.py` は `monthly_policy_metrics.csv` を読み、validation roleだけで候補を審査し、fixed diagnostic roleは選択後の参考列に分離する。
- 出力は `candidate_selection_summary.csv`, `blocker_summary.csv`, `selected_policy.json`, `config.json`。
- 標準gateは validation role数、positive role数、active role数、role total PnL、月別worst PnL、role trades、月別trades、drawdown、side concentrationを同時に見る。
- strict3 (`cal2024_calibration_validation`, `fresh2024_validation`, `refit2025_validation`) はNoTrade。
- clean2 (`fresh2024_validation`, `refit2025_validation`) もNoTrade。
- clean2では絶対閾値baselineだけがvalidation total/worstでは通りそうに見えるが、fresh role trades `4` と validation max side share `0.9595` で落ちる。
- 判断: selector infrastructureはaccepted。現quantile候補はrole-level selectionでも標準採用しない。

## Artifacts

- Script: `scripts/experiments/entry_ev_quantile_policy_selection.py`
- Tests: `tests/test_entry_ev_quantile_policy_selection.py`
- Source backtest run:
  - `data/reports/backtests/20260630_entry_ev_quantile_policy_backtest/20260630_063440_entry_ev_quantile_policy_backtest/`
- strict3 selection:
  - `data/reports/backtests/20260630_entry_ev_quantile_policy_selection/20260630_064643_entry_ev_quantile_policy_selection_strict3/`
- clean2 selection:
  - `data/reports/backtests/20260630_entry_ev_quantile_policy_selection/20260630_064643_entry_ev_quantile_policy_selection_clean2/`

## Gate

Common gate:

```text
min_total_pnl >= 0
min_role_total_pnl >= 0
min_month_pnl >= 0
min_role_trades >= 10
min_month_trades >= 1
max_side_trade_share <= 0.95
positive_roles = all validation roles
active_roles = all validation roles
fixed_diagnostic_roles are not used for selection
```

This intentionally rejects "positive only because one role is very strong" candidates.

## Results

Strict3 uses cal2024 calibration-validation, fresh2024 validation, and refit2025 validation.

| candidate | validation total | min role total | min month | trades | side share | main blockers |
|---|---:|---:|---:|---:|---:|---|
| `abs_entry10_short9_side5_rank0` | `+254.7066` | `0.0000` | `0.0000` | `173` | `0.9595` | positive/active roles low, trades low, side share |
| `q99_sg95_rank90_side_regime_session_month` | `+12.5532` | `-27.9456` | `-37.7536` | `44` | `0.5227` | positive roles low, role/month PnL |
| `q95_sg95_rank90_side_regime_session_month` | `-5.6974` | `-23.2338` | `-36.8342` | `97` | `0.5052` | total/role/month PnL |
| `q99_sg95_rank0_side_regime_session_month` | `+21.2028` | `-70.7894` | `-72.0966` | `163` | `0.5767` | positive roles low, role/month PnL |

Strict3 blocker counts:

| blocker | candidates |
|---|---:|
| `positive_roles_low` | `7` |
| `role_total_pnl_below_floor` | `6` |
| `month_pnl_below_floor` | `6` |
| `role_trades_low` | `3` |
| `month_trades_low` | `3` |
| `total_pnl_below_floor` | `3` |
| `active_roles_low` | `1` |
| `side_share_high` | `1` |

Clean2 uses only fresh2024 validation and refit2025 validation. Cal2024 and fresh fixed months are diagnostics only.

| candidate | validation total | min role total | min month | trades | side share | main blockers |
|---|---:|---:|---:|---:|---:|---|
| `abs_entry10_short9_side5_rank0` | `+254.7066` | `+16.1220` | `+1.0490` | `173` | `0.9595` | role trades low, side share |
| `q99_sg95_rank90_side_regime_session_month` | `+6.3484` | `-27.9456` | `-37.7536` | `30` | `0.5333` | positive roles low, role/month PnL |
| `q95_sg95_rank90_side_regime_session_month` | `-21.2418` | `-23.2338` | `-36.8342` | `67` | `0.5224` | total/role/month PnL |
| `q99_sg95_rank0_side_regime_session_month` | `+15.6616` | `-70.7894` | `-72.0966` | `110` | `0.5455` | positive roles low, role/month PnL |

Clean2 blocker counts:

| blocker | candidates |
|---|---:|
| `positive_roles_low` | `6` |
| `role_total_pnl_below_floor` | `6` |
| `month_pnl_below_floor` | `6` |
| `total_pnl_below_floor` | `4` |
| `role_trades_low` | `3` |
| `month_trades_low` | `2` |
| `side_share_high` | `1` |

Both `selected_policy.json` files return:

```json
{
  "selected": "no_trade",
  "reason": "no validation-role candidate passed the pre-registered gates"
}
```

## Decision

Accepted:

- Role-level quantile policy selector.
- Explicit separation of validation roles and fixed diagnostic roles.
- Blocker summary as a standard admission debugging output.

Not accepted:

- Any current quantile policy.
- Absolute EV baseline as a standard policy, even in clean2, because support and side concentration fail.
- Using fixed diagnostic PnL to rescue a validation-failing candidate.

Current standard remains NoTrade.

## Next

1. Add more chronological validation roles and run this selector unchanged.
2. Only after a candidate passes validation-role gates, run fixed diagnostic and cost stress.
3. Keep `max_side_trade_share <= 0.95` and `min_role_trades >= 10` as explicit diagnostics, not permanent truths; re-evaluate them after more validation roles exist.
4. Add small absolute positive EV floor only as a pre-registered candidate family, not as post-hoc rescue.

## Verification

- `python3 -m unittest tests.test_entry_ev_quantile_policy_selection`: OK, `5` tests
- `python3 -m py_compile scripts/experiments/entry_ev_quantile_policy_selection.py tests/test_entry_ev_quantile_policy_selection.py`: OK
- strict3 selector run: OK, selected NoTrade
- clean2 selector run: OK, selected NoTrade
