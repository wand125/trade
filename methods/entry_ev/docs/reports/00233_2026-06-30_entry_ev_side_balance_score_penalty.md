# Entry EV Side Balance Score Penalty

日時: 2026-06-30 18:55 JST
更新日時: 2026-06-30 18:55 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00232の次アクションとして、dense executable scoreへ prior-only の side-balance / side-drift penalty を掛ける `scripts/experiments/entry_ev_side_balance_score_inputs.py` を追加した。
- 対象月より前のprediction全行から、predicted selected long share と fixed720 dense label long share の差分を作り、過剰に出ているsideだけを縮小する。
- refit2025のlong過剰は少し改善した。fixed720 dense direct scoreで、refit2025 long shareは `2025-01 0.9453 -> 0.8911`, `2025-02 0.8970 -> 0.8750`。refit validationの q95 floor5 は `+93.9912`, min month `+9.5300`, trades `19`。
- しかしfresh側のtailが大きく悪化した。fresh validationは q95 floor5 `-82.2428`, q99 floor5 `-38.3550`。overallでも q95 floor5 は total `+14.6138` だが min role `-82.2428`, min month `-46.5308`。
- selectorはNoTradeを選んだ。fresh fixed `2024-10..11` では q99 floor5 が `+27.3080` だが2 tradesだけ、q95 floor5 は `-33.9804`。
- 結論: side-balance score infrastructureはaccepted。generic side-balance penaltyをdirect scoreとして標準policyへ採用しない。side-balanceはhard/direct penaltyではなく、selector/ranking feature、downside-conditioned penalty、context-specific correctionとして使う。

## Artifacts

- Script: `scripts/experiments/entry_ev_side_balance_score_inputs.py`
- Test: `tests/test_entry_ev_side_balance_score_inputs.py`
- Side-balance input generation:
  - `data/reports/backtests/20260630_095101_20260630_entry_ev_side_balance_dense720_inputs_s1/`
- Validation stateful backtest:
  - `data/reports/backtests/20260630_095136_20260630_entry_ev_side_balance_dense720_policy_backtest_s1/`
- Validation selector:
  - `data/reports/backtests/20260630_095158_20260630_entry_ev_side_balance_dense720_policy_selector_s1_relaxed_trades/`
- Fresh fixed diagnostic:
  - `data/reports/backtests/20260630_095220_20260630_entry_ev_side_balance_dense720_policy_backtest_s1_fixed_2024_10_11/`

## Method

Prior-only side-balance:

```text
target month M:
  prior rows = rows with month < M and valid fixed720 dense target
  prior_pred_long_share = mean(pred_long_score >= pred_short_score)
  prior_target_long_share = mean(long_fixed_720m_adjusted_pnl >= short_fixed_720m_adjusted_pnl)
  drift = prior_pred_long_share - prior_target_long_share

  if drift > 0:
    long_scale = 1 - penalty_strength * drift
    short_scale = 1
  if drift < 0:
    long_scale = 1
    short_scale = 1 - penalty_strength * (-drift)
```

Context stats use `combined_regime + session_regime` and are blended with global stats by `support_scale=5000`. All target-month rows use only months before the target month. Validation uses profit multiplier `1.00`, loss multiplier `1.20`, `max_predicted_hold_minutes=720`, and NoTrade-first selector gates.

## Prediction Effect

| family/month | dense long share | balanced long share | side switch | dense q95 | balanced q95 | long scale | short scale | drift |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| cal2024 `2024-02` | `0.6477` | `0.7155` | `0.0678` | `4.3564` | `4.1429` | `1.0000` | `0.8230` | `-0.1770` |
| fresh2024 `2024-03` | `0.4786` | `0.4964` | `0.0291` | `4.3571` | `4.1720` | `0.9830` | `0.9637` | `-0.0194` |
| fresh2024 `2024-04` | `0.6417` | `0.7527` | `0.1304` | `4.7899` | `4.6168` | `0.9849` | `0.9021` | `-0.0828` |
| refit2025 `2025-01` | `0.9453` | `0.8911` | `0.0573` | `4.9781` | `4.6095` | `0.8916` | `0.9954` | `0.1037` |
| refit2025 `2025-02` | `0.8970` | `0.8750` | `0.0236` | `9.3278` | `8.3601` | `0.8889` | `0.9956` | `0.1067` |

refit2025では想定通りlong過剰が縮む。一方、cal2024/fresh2024の初期月ではprior driftがnegativeになり、short側が縮むためlong shareが増える。ここがfresh validation悪化の主因候補。

## Validation

Role summary:

| role | candidate | total | min month | trades | max side share |
|---|---|---:|---:|---:|---:|
| cal2024 | q99 floor10 | `+8.5684` | `-1.8000` | `9` | `1.0000` |
| cal2024 | q95 floor5 | `+2.8654` | `+0.1014` | `26` | `0.8333` |
| fresh2024 | q99 floor5 | `-38.3550` | `-35.7120` | `6` | `1.0000` |
| fresh2024 | q95 floor5 | `-82.2428` | `-46.5308` | `8` | `1.0000` |
| refit2025 | q95 floor5 | `+93.9912` | `+9.5300` | `19` | `1.0000` |
| refit2025 | q99 floor5 | `+30.2336` | `+0.0000` | `10` | `0.7000` |

Overall:

| candidate | total | min role | min month | trades | selector |
|---|---:|---:|---:|---:|---|
| q95 floor10 | `+15.5736` | `-11.2600` | `-9.4600` | `23` | NoTrade |
| q95 floor5 | `+14.6138` | `-82.2428` | `-46.5308` | `53` | NoTrade |
| q99 floor10 | `+1.1920` | `-7.3764` | `-7.3764` | `10` | NoTrade |
| q99 floor5 | `-10.2286` | `-38.3550` | `-35.7120` | `29` | NoTrade |

Selector blockers:

| candidate | main blockers |
|---|---|
| q99 floor10 | `positive_roles_low`, `active_roles_low`, `role_total_pnl_below_floor`, `month_pnl_below_floor`, `role_trades_low`, `month_trades_low` |
| q95 floor10 | `positive_roles_low`, `active_roles_low`, `role_total_pnl_below_floor`, `month_pnl_below_floor`, `role_trades_low`, `month_trades_low` |
| q99 floor5 | `positive_roles_low`, `total_pnl_below_floor`, `role_total_pnl_below_floor`, `month_pnl_below_floor`, `month_trades_low` |
| q95 floor5 | `positive_roles_low`, `role_total_pnl_below_floor`, `month_pnl_below_floor` |

Fresh fixed `2024-10..11` diagnostic:

| candidate | fixed total | min month | trades |
|---|---:|---:|---:|
| q99 floor5 | `+27.3080` | `+0.0000` | `2` |
| q95 floor5 | `-33.9804` | `-33.9804` | `4` |
| q95/q99 floor10 | `+0.0000` | `+0.0000` | `0` |

The fixed q99 result is too sparse and side-concentrated to override validation failure.

## Decision

Accepted:

- Prior-only predicted-vs-target side share diagnostics.
- `pred_side_balance_*` columns.
- `pred_side_balanced_dense_executable_long_best_adjusted_pnl` / `short`.
- `side_balanced_dense_executable` quantile columns.
- Unit tests proving target-month rows use prior months only and quantile columns are written.

Not accepted:

- Generic side-balance penalty as the direct entry score.
- Selecting sparse fixed-positive q99 rows.
- Treating side-share correction alone as sufficient to solve stateful admission.

Standard policy remains NoTrade.

## Interpretation

The penalty helped the obvious refit2025 long-heavy failure, but it is too symmetric and too coarse. It assumes that prior predicted/target side drift should always be corrected toward the dense label distribution. That is not necessarily true under the one-position path, because a side-share correction can move the selected sequence into a different set of replacement trades and can penalize the side that contains the few high-quality executable entries.

The useful signal is not "always reduce the overrepresented side"; it is "when this drift is associated with downside in comparable contexts, reduce admission or lower rank." Therefore side-balance belongs in selector/ranking/downside features, not as an unconditional multiplier on all rows.

## Next

1. Use `pred_side_balance_long_share_drift`, `prior_pred_long_share`, `prior_target_long_share`, and side scales as selector/ranking features rather than direct score replacement.
2. Condition any side-balance penalty on downside evidence: prior side PnL, direction error, exit capture failure, realized executable EV, and support.
3. Evaluate context-specific penalties only where fresh/refit validation losses agree, not globally by sign of side drift.
4. Keep NoTrade-first selection and do not promote sparse fixed q99 positivity.

## Verification

- `python3 -m py_compile scripts/experiments/entry_ev_side_balance_score_inputs.py tests/test_entry_ev_side_balance_score_inputs.py`: OK
- `python3 -m unittest tests.test_entry_ev_side_balance_score_inputs`: OK
- Side-balance input generation: OK
- Validation stateful backtest: OK
- Validation selector: OK, selected NoTrade
- Fresh fixed diagnostic: OK
