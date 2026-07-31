# Entry EV Quantile Prior Inversion Guard

日時: 2026-06-30 16:55 JST
更新日時: 2026-06-30 16:55 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00224のsame-validation diagnostic inversion guardを、対象月より前のtrade実績だけで作る prior-only guardへ置き換えた。
- `scripts/experiments/entry_ev_quantile_hold_cap_sensitivity.py` に `prior_inversion` guard modeを追加した。prior sourceは00222の `enriched_trades.csv` で、同じentry timestamp / side / contextに出るfloor・candidate重複は1 tradeとしてdedupeする。
- 評価条件は既存quantile policyと同じ `timed_ev` / MLP exit holding / profit multiplier `1.0` / loss multiplier `1.20`。
- prior ruleは `target_month` より前の月だけを使い、`direction + combined_regime + session_regime` 単位で、trade数、direction error rate、total PnLが悪いcontext-sideを `side_block_rules` に変換する。
- 結論: prior-only化しても `720m q95_floor5` の改善は残る。ただしvalidationでは月別tailがわずかに残り、fresh fixed diagnosticではguardが良い取引も削るため、現guardは標準採用しない。
- 標準policyはNoTradeのまま。`720m` hold capは引き続き有望な診断軸だが、blocking ruleはより保守的なprior detectorへ作り直す。

## Artifacts

- Script: `scripts/experiments/entry_ev_quantile_hold_cap_sensitivity.py`
- Tests: `tests/test_entry_ev_quantile_hold_cap_sensitivity.py`
- Prior source: `data/reports/backtests/20260630_entry_ev_quantile_trade_diagnostics/20260630_071126_entry_ev_quantile_trade_diagnostics/enriched_trades.csv`
- Strict prior run:
  - `data/reports/backtests/20260630_entry_ev_quantile_prior_inversion_hold_cap/20260630_074726_entry_ev_quantile_prior_inversion_hold_cap_min2/`
- Fast prior run:
  - `data/reports/backtests/20260630_entry_ev_quantile_prior_inversion_hold_cap/20260630_074829_entry_ev_quantile_prior_inversion_hold_cap_min1_trade1_err1/`
- Fresh fixed diagnostic:
  - `data/reports/backtests/20260630_entry_ev_quantile_prior_inversion_hold_cap/20260630_075000_entry_ev_quantile_prior_inversion_hold_cap_fresh_fixed_min1_trade1_err1/`

## Implementation Notes

- `prior_trade_context_frame` filters by role/candidate, normalizes `month`, parses `entry_decision_timestamp`, and deduplicates on `month + entry_decision_timestamp + direction + combined_regime + session_regime`.
- `derive_prior_context_side_block_rules` uses only `month < target_month`, optional recent-month window, `min_prior_months`, `min_trade_count`, `min_direction_error_rate`, and `max_total_pnl`.
- `prior_inversion_guard_contexts.csv` records the contexts actually available to each target month. This is important because `2024-03` has no prior 2024 evidence in the fast run and therefore remains unguarded.
- The current detector is intentionally low-capacity, but still outcome-derived. It is acceptable as a validation diagnostic and not yet a deployable live rule.

## Main Results

Strict prior evidence, `min_prior_months=2`, `min_trade_count=2`, `direction_error_rate>=0.75`:

| guard | cap | candidate | total pnl | min role pnl | min month pnl | trades | blocker |
|---|---:|---|---:|---:|---:|---:|---|
| none | `260` | `q95_floor5` | `-5.6974` | `-23.2338` | `-36.8342` | `97` | role/month |
| none | `720` | `q95_floor5` | `+117.0340` | `+16.2628` | `-9.1718` | `91` | month |
| prior min2 | `260` | `q95_floor5` | `+35.1232` | `+6.1268` | `-7.4736` | `96` | month |
| prior min2 | `720` | `q95_floor5` | `+126.0190` | `+24.5508` | `-9.1718` | `91` | month |

Fast prior evidence, `min_prior_months=1`, `min_trade_count=1`, `direction_error_rate=1.0`:

| guard | cap | candidate | total pnl | min role pnl | min month pnl | trades | blocker |
|---|---:|---|---:|---:|---:|---:|---|
| prior min1 | `260` | `q95_floor5` | `+41.0910` | `+0.6738` | `-6.8364` | `85` | month |
| prior min1 | `720` | `q95_floor5` | `+139.0422` | `+17.7308` | `-0.4914` | `82` | month |
| prior min1 | `720` | `q95_floor10` | `+130.2652` | `+7.5574` | `-6.9920` | `80` | month |

The best validation row nearly clears the monthly floor but still fails:

| role | month | total pnl | trades | max DD | rule count |
|---|---|---:|---:|---:|---:|
| cal2024_calibration_validation | `2024-01` | `+2.5694` | `20` | `26.9590` | `0` |
| cal2024_calibration_validation | `2024-02` | `+15.1614` | `7` | `2.2716` | `9` |
| fresh2024_validation | `2024-03` | `-0.4914` | `16` | `28.5544` | `11` |
| fresh2024_validation | `2024-04` | `+47.4570` | `15` | `39.6960` | `11` |
| refit2025_validation | `2025-01` | `+21.5714` | `9` | `10.9536` | `8` |
| refit2025_validation | `2025-02` | `+52.7744` | `15` | `21.8280` | `8` |

The selected policy remains:

```json
{"selected": "NoTrade", "reason": "no_candidate_passed_notrade_first_gates"}
```

## Fixed Diagnostic

Fresh family fixed diagnostic with q95_floor5 only:

| guard | cap | total pnl | min role pnl | min month pnl | trades | max DD | blocker |
|---|---:|---:|---:|---:|---:|---:|---|
| none | `260` | `+207.2986` | `+1.9920` | `-30.7764` | `171` | `51.6972` | month |
| none | `720` | `+402.1118` | `+76.2204` | `-9.1718` | `163` | `43.7928` | month |
| prior min1 | `260` | `+222.1654` | `+18.8154` | `-7.7974` | `158` | `51.6972` | month |
| prior min1 | `720` | `+373.4814` | `+2.0982` | `-9.1718` | `152` | `43.7928` | month |

Interpretation:

- `720m` cap itself is strong on fresh fixed diagnostic: no-guard total `+402.1118`, min role `+76.2204`.
- prior guard improves the `260m` fixed row but hurts `720m` fixed total and role minimum.
- The guard therefore looks like an over-blocking detector when transferred to fixed months. It catches some bad contexts, but also removes good future trades.

## Decision

Accepted:

- prior-only guard infrastructure.
- internal `日時` based report ordering reminder remains active.
- `720m` q95_floor5 as a diagnostic hold-cap candidate.

Not accepted:

- current prior inversion guard as standard policy.
- same-validation diagnostic guard as live rule.
- selecting the near-pass `q95_floor5 720m` row despite `2024-03` still being `-0.4914`.

Current standard remains NoTrade.

## Next

1. Replace one-loss context blocking with a calibrated detector: prior direction error, prior side PnL, support, predicted side bias, and side share drift should be scored rather than turned into immediate hard blocks.
2. Separate the `720m` hold-cap fixed diagnostic from guard testing. First ask whether longer exit capture is robust, then ask whether blocking improves it.
3. Add side/context prior features into selection reports so the model can learn or rank risk instead of relying on a brittle context exclusion list.
4. Increase chronological validation coverage before promoting any near-pass monthly result.

## Verification

- `python3 -m unittest tests.test_entry_ev_quantile_hold_cap_sensitivity`: OK, `3` tests
- `python3 -m py_compile scripts/experiments/entry_ev_quantile_hold_cap_sensitivity.py tests/test_entry_ev_quantile_hold_cap_sensitivity.py`: OK
- strict prior-only run: OK
- fast prior-only run: OK
- fresh fixed diagnostic run: OK
