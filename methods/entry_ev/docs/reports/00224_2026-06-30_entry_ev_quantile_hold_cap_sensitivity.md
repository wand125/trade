# Entry EV Quantile Hold-Cap Sensitivity

日時: 2026-06-30 16:39 JST
更新日時: 2026-06-30 16:39 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00223の次アクションとして、q95/q99 quantile/floor候補の hold-cap sensitivity をvalidation roleだけで実行した。
- `scripts/experiments/entry_ev_quantile_hold_cap_sensitivity.py` を追加した。既存のquantile policy backtestと同じ `timed_ev` / loss multiplier `1.20` / MLP exit holdingで、`max_predicted_hold_minutes` を `260/480/720/1440` に振る。
- context-side inversion guardなし/ありを同じgridで比較した。guardありは00222のvalidation context summaryから、direction error rate `1.0` かつ負PnLの side/context を `side_block_rules` として動的backtestに入れる診断設定。
- guardは同じvalidationから作っているため、採用可能なlive ruleではない。cap延長の効果がdirection/context errorに依存しているかを見るための切り分けである。
- 追加で `guard_min_trade_count=4` も実行し、single-trade contextだけに依存していないかを確認した。
- 結論: hold cap延長はexit captureを改善する。特に `720m` が強い。ただしNoTrade-first selectorでは全候補が `month_pnl_below_floor` で落ちるため、標準policyはNoTradeのまま。

## Artifacts

- Script: `scripts/experiments/entry_ev_quantile_hold_cap_sensitivity.py`
- Tests: `tests/test_entry_ev_quantile_hold_cap_sensitivity.py`
- Main output:
  - `data/reports/backtests/20260630_entry_ev_quantile_hold_cap_sensitivity/20260630_073350_entry_ev_quantile_hold_cap_sensitivity/`
- Guard support check:
  - `data/reports/backtests/20260630_entry_ev_quantile_hold_cap_sensitivity/20260630_073622_entry_ev_quantile_hold_cap_sensitivity_guardmin4/`
- Guard source:
  - `data/reports/backtests/20260630_entry_ev_quantile_trade_diagnostics/20260630_071126_entry_ev_quantile_trade_diagnostics/role_context_trade_summary.csv`

## Main Results

Best row per guard/cap by role-worst PnL:

| guard | cap | candidate | total pnl | min role pnl | min month pnl | trades | blocker |
|---|---:|---|---:|---:|---:|---:|---|
| none | `260` | `q95_floor5` | `-5.6974` | `-23.2338` | `-36.8342` | `97` | role/month |
| none | `480` | `q95_floor5` | `+78.9806` | `+2.8324` | `-6.8346` | `92` | month |
| none | `720` | `q95_floor5` | `+117.0340` | `+16.2628` | `-9.1718` | `91` | month |
| none | `1440` | `q95_floor5` | `+105.3110` | `+15.5328` | `-10.0518` | `91` | month |
| diagnostic guard min1 | `260` | `q95_floor5` | `+138.7464` | `+18.6450` | `-4.8356` | `86` | month |
| diagnostic guard min1 | `480` | `q95_floor5` | `+216.9048` | `+5.9850` | `-6.0390` | `82` | month |
| diagnostic guard min1 | `720` | `q95_floor5` | `+273.6662` | `+27.7034` | `-10.3748` | `81` | month |
| diagnostic guard min1 | `1440` | `q95_floor5` | `+263.1132` | `+27.7034` | `-11.2548` | `81` | month |
| diagnostic guard min4 | `720` | `q95_floor5` | `+235.0452` | `+25.3464` | `-10.3748` | `83` | month |

The selected policy is still:

```json
{"selected": "NoTrade", "reason": "no_candidate_passed_notrade_first_gates"}
```

## Guard Contexts

The diagnostic guard with `min_trade_count=1` created `10` side/context rules. The stricter `min_trade_count=4` kept `6` rules:

| side/context rule | trades | total pnl | direction error |
|---|---:|---:|---:|
| `short:range_normal_vol/ny_overlap` | `10` | `-158.7504` | `1.0` |
| `long:up_low_vol/ny_overlap` | `6` | `-67.3992` | `1.0` |
| `long:up_normal_vol/london` | `4` | `-46.5600` | `1.0` |
| `long:range_low_vol/rollover` | `6` | `-33.8724` | `1.0` |
| `short:range_low_vol/rollover` | `8` | `-9.6960` | `1.0` |
| `short:up_low_vol/rollover` | `4` | `-7.1040` | `1.0` |

The support>=4 guard still improves the best `720m q95_floor5` row from no-guard total `+117.0340` to `+235.0452`, so the effect is not only from one-off contexts. It is still same-validation diagnostic evidence, not a deployable prior-only guard.

## Interpretation

- Cap `260m -> 480/720m` improves q95 role totals. This supports 00223's diagnosis that exit capture is real.
- Cap `1440m` is worse than `720m` on the best q95 rows. The useful plateau is not "hold as long as possible"; `720m` is the best current sensitivity point.
- No-guard cap extension does not fully fix monthly tail. For `q95_floor5 720m`, fresh `2024-03` remains `-9.1718`, and refit `2025-02` is `-0.8886`.
- Diagnostic inversion guard turns all role totals positive for the best q95 rows, but monthly worst remains negative. It therefore explains a large part of the failure while still failing the NoTrade-first gate.
- Because the guard contexts are derived from the same validation trade outcomes, the result is a hypothesis generator: future work must convert it into prior-only context-side inversion features or a purged walk-forward guard.

## Decision

Accepted:

- Hold-cap sensitivity script.
- `720m` as the next diagnostic hold cap to test with prior-only context-side inversion controls.
- context-side inversion guard as a diagnostic stress axis, not as a standard rule.

Not accepted:

- Blind `max_predicted_hold=720m` promotion.
- Same-validation diagnostic inversion guard as a live policy.
- Any q95/q99 candidate as standard policy.

Current standard remains NoTrade.

## Next

1. Build a prior-only context-side inversion detector from earlier months, not from the target validation month.
2. Re-run `720m` vs `260m` with that prior-only detector through the same NoTrade-first selector.
3. If prior-only inversion control preserves the `720m` lift, then test on fixed diagnostic windows without reselection.

## Verification

- `python3 -m unittest tests.test_entry_ev_quantile_hold_cap_sensitivity tests.test_entry_ev_quantile_policy_backtest`: OK, `10` tests
- `python3 -m py_compile scripts/experiments/entry_ev_quantile_hold_cap_sensitivity.py tests/test_entry_ev_quantile_hold_cap_sensitivity.py`: OK
- main hold-cap sensitivity run: OK
- `guard_min_trade_count=4` support check: OK
