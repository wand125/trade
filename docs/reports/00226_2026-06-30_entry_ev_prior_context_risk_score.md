# Entry EV Prior Context Risk Score

日時: 2026-06-30 17:13 JST
更新日時: 2026-06-30 17:13 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00225の反省を受け、prior context-side evidenceを即hard blockにせず、risk scoreとして診断するscriptを追加した。
- `scripts/experiments/entry_ev_prior_context_risk_diagnostics.py` は対象tradeに、対象月より前の同一 `direction + combined_regime + session_regime` 実績を結合し、risk bucket別PnLと「このflagを消したら点評価で何が起きるか」を出す。
- `scripts/experiments/entry_ev_quantile_hold_cap_sensitivity.py` には `prior_risk` guard modeと `--prior-roles` を追加した。これにより、対象roleとprior evidence roleを分けられる。
- 結論: risk score化は広いhard blockよりかなり良い診断軸。validationではq95_floor5/720mを `+117.0340 -> +133.2270` へ改善し、fresh fixedでは cal2024+fresh2024 prior を使うと `+402.1118 -> +427.6524` へ改善した。ただしfresh `2024-03` の負け `-9.1718` は残り、NoTrade-first selectorはまだ通らない。
- 標準policyはNoTradeのまま。`prior_risk` はaccepted infrastructure / diagnostic candidateであり、標準採用しない。

## Artifacts

- Script: `scripts/experiments/entry_ev_prior_context_risk_diagnostics.py`
- Extended script: `scripts/experiments/entry_ev_quantile_hold_cap_sensitivity.py`
- Tests:
  - `tests/test_entry_ev_prior_context_risk_diagnostics.py`
  - `tests/test_entry_ev_quantile_hold_cap_sensitivity.py`
- Validation pointwise risk diagnostics:
  - `data/reports/backtests/20260630_entry_ev_prior_context_risk_diagnostics/20260630_080544_entry_ev_prior_context_risk_validation_q95q99/`
- Fresh q95_floor5 720m no-guard trades:
  - `data/reports/backtests/20260630_entry_ev_prior_context_risk_diagnostics/20260630_080607_entry_ev_q95_floor5_720_fresh_trades/`
- Fresh q95_floor5 720m enriched trade diagnostics:
  - `data/reports/backtests/20260630_entry_ev_prior_context_risk_diagnostics/20260630_080630_entry_ev_q95_floor5_720_fresh_trade_diagnostics/`
- Fresh q95_floor5 720m pointwise risk, cal+fresh prior:
  - `data/reports/backtests/20260630_entry_ev_prior_context_risk_diagnostics/20260630_080641_entry_ev_prior_context_risk_fresh_q95_720_prior_validation/`
- Fresh q95_floor5 720m pointwise risk, fresh-only prior:
  - `data/reports/backtests/20260630_entry_ev_prior_context_risk_diagnostics/20260630_081250_entry_ev_prior_context_risk_fresh_q95_720_prior_freshonly/`
- Stateful validation prior_risk guard:
  - `data/reports/backtests/20260630_entry_ev_prior_context_risk_diagnostics/20260630_080935_entry_ev_prior_risk_guard_validation_q95_floor5/`
- Stateful fresh-only prior_risk guard:
  - `data/reports/backtests/20260630_entry_ev_prior_context_risk_diagnostics/20260630_081001_entry_ev_prior_risk_guard_fresh_q95_floor5/`
- Stateful cal+fresh prior_risk guard:
  - `data/reports/backtests/20260630_entry_ev_prior_context_risk_diagnostics/20260630_081420_entry_ev_prior_risk_guard_fresh_q95_floor5_crossprior/`

## Risk Score

The score is intentionally simple and diagnostic:

```text
support_weight = clip(prior_trade_count / 4, 0, 1)
pnl_risk       = clip(-prior_avg_adjusted_pnl / 10, 0, 1)
risk_score     = support_weight * (
  0.45 * prior_direction_error_rate
  + 0.35 * prior_loss_rate
  + 0.20 * pnl_risk
)
```

This is not optimized. It is a way to separate weak context warnings from severe prior failures before trying a stateful guard.

## Pointwise Diagnostics

Validation q95/q99 candidates, using only months before each target month:

| flag | flagged trades | flagged pnl | kept pnl if blocked | pointwise delta |
|---|---:|---:|---:|---:|
| `direction_error_1_and_prior_pnl_negative` | `52` | `-84.6872` | `+91.7972` | `+84.6872` |
| `risk_score >= 0.25` | `22` | `-23.5464` | `+30.6564` | `+23.5464` |
| `risk_score >= 0.50` | `8` | `-15.3772` | `+22.4872` | `+15.3772` |
| `risk_score >= 0.75` | `0` | `0.0000` | `+7.1100` | `0.0000` |

Role/candidate split shows why hard block is dangerous:

| role/candidate | flag | total pnl | flagged pnl | pointwise delta |
|---|---|---:|---:|---:|
| refit q95_floor5 | hard direction-error | `-23.2338` | `-45.4296` | `+45.4296` |
| refit q99_floor5 | hard direction-error | `-27.9456` | `-37.9762` | `+37.9762` |
| fresh q95_floor5 | hard direction-error | `+1.9920` | `+19.3652` | `-19.3652` |
| fresh q95_floor5 | `risk_score >= 0.50` | `+1.9920` | `-2.9244` | `+2.9244` |

Interpretation: broad direction-error block catches refit losses but deletes profitable fresh trades. A stricter score threshold is less powerful but less destructive.

## Stateful Validation

q95_floor5 only, validation roles:

| guard | cap | total pnl | min role pnl | min month pnl | trades | max DD | selector |
|---|---:|---:|---:|---:|---:|---:|---|
| none | `260` | `-5.6974` | `-23.2338` | `-36.8342` | `97` | `54.4442` | fail |
| prior_risk | `260` | `+10.4956` | `-7.0408` | `-20.6412` | `97` | `44.4834` | fail |
| none | `720` | `+117.0340` | `+16.2628` | `-9.1718` | `91` | `44.9406` | fail |
| prior_risk | `720` | `+133.2270` | `+24.5508` | `-9.1718` | `91` | `38.9548` | fail |

`prior_risk` improves both caps, but it does not solve the fresh `2024-03` month tail.

## Fresh Fixed Diagnostic

First, with fresh-only prior evidence, which matches the earlier `--roles fresh2024_validation,fresh2024_fixed_diagnostic` behavior:

| guard | cap | total pnl | min role pnl | min month pnl | trades | max DD | selector |
|---|---:|---:|---:|---:|---:|---:|---|
| none | `720` | `+402.1118` | `+76.2204` | `-9.1718` | `163` | `43.7928` | fail |
| prior_risk fresh-only | `720` | `+396.0818` | `+76.2204` | `-9.1718` | `162` | `43.7928` | fail |

Fresh-only prior chooses only:

```text
short:up_low_vol/asia
```

This improves `2024-05` by `+1.0000`, but hurts `2024-07` by `-7.0300`, net `-6.0300`.

Second, with prior roles separated as `cal2024_calibration_validation,fresh2024_validation`:

| guard | cap | total pnl | min role pnl | min month pnl | trades | max DD | selector |
|---|---:|---:|---:|---:|---:|---:|---|
| none | `720` | `+402.1118` | `+76.2204` | `-9.1718` | `163` | `43.7928` | fail |
| prior_risk cal+fresh | `720` | `+427.6524` | `+76.2204` | `-9.1718` | `158` | `43.7928` | fail |

The cal+fresh prior uses two context-side rules:

```text
short:up_low_vol/asia
short:range_low_vol/london
```

Monthly changes vs no-guard:

| month | none | prior_risk cal+fresh | delta |
|---|---:|---:|---:|
| `2024-05` | `+18.6860` | `+19.6860` | `+1.0000` |
| `2024-07` | `+21.2556` | `+14.2256` | `-7.0300` |
| `2024-09` | `+1.3594` | `+11.2594` | `+9.9000` |
| `2024-10` | `+17.8112` | `+34.9988` | `+17.1876` |
| `2024-11` | `+192.8188` | `+197.4908` | `+4.6720` |
| `2024-12` | `+19.1658` | `+18.9768` | `-0.1890` |

The improvement is real on this diagnostic window, but `2024-03` remains `-9.1718`, so it still fails the NoTrade-first monthly gate.

## Decision

Accepted:

- Prior context risk score diagnostic script.
- `prior_risk` guard mode.
- `--prior-roles` separation in hold-cap sensitivity.
- `risk_score >= 0.50` as a diagnostic threshold to carry forward.

Not accepted:

- `prior_risk` as standard policy.
- broad hard blocking based only on direction error and negative prior PnL.
- using fresh fixed improvement as promotion evidence without additional chronological folds.

Current standard remains NoTrade.

## Next

1. Run `prior_risk` on additional chronological windows where prior roles and target roles are predeclared before looking at fixed results.
2. Add a selector-level report that treats prior context risk as a feature/ranking column, not only a hard block.
3. Test whether the remaining `2024-03` loss is an exit-capture issue, an entry-side issue, or simply insufficient prior coverage.
4. Keep `720m q95_floor5` as a diagnostic candidate, but require NoTrade-first monthly pass before promotion.

## Verification

- `python3 -m unittest tests.test_entry_ev_quantile_hold_cap_sensitivity tests.test_entry_ev_prior_context_risk_diagnostics`: OK, `7` tests
- `python3 -m py_compile scripts/experiments/entry_ev_quantile_hold_cap_sensitivity.py scripts/experiments/entry_ev_prior_context_risk_diagnostics.py tests/test_entry_ev_quantile_hold_cap_sensitivity.py tests/test_entry_ev_prior_context_risk_diagnostics.py`: OK
- validation pointwise risk diagnostics: OK
- fresh q95_floor5 720m trade generation and enrichment: OK
- stateful validation prior_risk run: OK
- stateful fresh-only and cal+fresh prior_risk runs: OK
