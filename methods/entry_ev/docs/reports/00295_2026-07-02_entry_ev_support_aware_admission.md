# Entry EV Support-Aware Admission

日時: 2026-07-02 14:00 JST
更新日時: 2026-07-02 14:00 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00294の次アクションとして、月次floor breachを一律 `month_pnl_below_floor` とせず、support-limited / shallow / structural に分けるdiagnostic selectorを追加した。
- `scripts/experiments/entry_ev_stateful_support_aware_admission.py` はmonthly metricsだけを使い、strict standard gateとsupport-aware floor gateを並べて評価する。
- 00293 best branchは、strict standardではNoTradeのままだが、default support-aware floorでは `support_aware_only` になった。
- ただし感度確認では、support-limited negative months許容を3から2へ下げる、またはshallow floorを `-1.0` から `-0.25` へ厳しくすると通らない。
- 判断: support-aware admission diagnosticsはaccepted infrastructure。support-aware passは標準採用ではなく、失敗種類を分ける診断に留める。標準policyはNoTrade。

## Artifacts

- New script:
  - `scripts/experiments/entry_ev_stateful_support_aware_admission.py`
- New test:
  - `tests/test_entry_ev_stateful_support_aware_admission.py`
- Default diagnostic:
  - `data/reports/backtests/20260702_045942_20260702_entry_ev_stateful_support_aware_admission_residual_combo_s1/`
- Sensitivity:
  - `data/reports/backtests/20260702_050012_20260702_entry_ev_stateful_support_aware_admission_residual_combo_support2_s1/`
  - `data/reports/backtests/20260702_050012_20260702_entry_ev_stateful_support_aware_admission_residual_combo_shallow025_s1/`

## Definitions

Monthly floor breaches are classified as:

```text
support_limited:
  total_adjusted_pnl < 0
  AND (trade_count < 5 OR max_side_trade_share > 0.95)

shallow:
  total_adjusted_pnl < 0
  AND not support_limited
  AND total_adjusted_pnl >= -1.0

structural:
  total_adjusted_pnl < 0
  AND not support_limited
  AND not shallow
```

Default support-aware gate allows:

```text
structural_negative_month_count == 0
shallow_negative_month_count <= 1
support_limited_negative_month_count <= 3
total_pnl >= 0
role_total_pnl_min >= 0
```

This gate is diagnostic only. Strict standard gate still requires month floor, role/month support, side-share, and NoTrade comparison.

## Results

Default support-aware run:

| metric | value |
|---|---:|
| diagnostic best total | `+329.4348` |
| role total min | `+0.5354` |
| month min | `-0.7200` |
| trade count | `232` |
| negative months | `4` |
| support-limited negative months | `3` |
| shallow negative months | `1` |
| structural negative months | `0` |
| strict standard pass | `false` |
| support-aware floor pass | `true` |
| selected | `NoTrade` |
| reason | `support_aware_diagnostic_only` |

Strict blockers remain:

```text
month_pnl_below_floor
role_trades_low
month_trades_low
side_share_high
```

Sensitivity:

| run | change | result |
|---|---|---|
| support2 | allow support-limited negative months `3 -> 2` | blocked by `too_many_support_limited_negative_months` |
| shallow025 | shallow floor `-1.0 -> -0.25` | blocked by `structural_negative_months` |

## Decision

Accepted:

- support-aware admission diagnostics
- separating support-limited / shallow / structural floor breaches
- reporting support-aware pass separately from standard pass

Rejected:

- treating `support_aware_only` as standard policy admission
- loosening strict standard gates solely because total PnL is high
- hiding role/month support failures behind a renamed selector

Standard policy remains NoTrade.

## Next

1. Use support-aware classification as an analysis layer for future candidate comparisons.
2. Design the next admission experiment around stability of floor-breach class, not just PnL floor.
3. If a candidate is `support_aware_only`, require additional unused chronology or a policy-level reason before considering any relaxation.
4. Keep 00293 best branch as diagnostic benchmark, not standard policy.

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_stateful_support_aware_admission.py tests/test_entry_ev_stateful_support_aware_admission.py`: OK
- `uv run python -m unittest tests.test_entry_ev_stateful_support_aware_admission`: OK
- default support-aware admission run: OK
- support2 sensitivity run: OK
- shallow025 sensitivity run: OK
