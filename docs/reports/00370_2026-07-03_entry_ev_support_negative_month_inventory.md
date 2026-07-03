# Entry EV Support Negative Month Inventory

日時: 2026-07-03 16:52 JST
更新日時: 2026-07-03 16:52 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00369で現00314/00318 branchのsupport-sufficient negative targetが1件だけと分かったため、過去のselector monthly metrics全体を棚卸しするdiagnosticsを追加した。
- `data/reports/backtests` 配下の `*selector_monthly_metrics.csv` を17件読み、既存のrepair target分類でnegative monthをsupport-sufficient / support-limitedへ分けた。
- inventory rowsは29,371、negative rowsは9,491。そのうちsupport-sufficient negative rowsは5,065、support-limited negative rowsは4,426。
- target identityは20件あり、support-sufficient configを持つtargetは14件、support-limited onlyは6件。
- 重要: row数やconfig数はvariant/parameterの重複を含む棚卸しであり、独立サンプル数ではない。target候補を選ぶ地図として使い、policy evidenceとして直接読まない。
- 判断: support-sufficient targetは現branch以外にも存在する。次は複数metric parentにまたがるcanonical support-sufficient target setを作り、00368/00369のselector surfaceを複数targetへ広げる。support-limited only targetは別laneとして扱う。標準policyはNoTrade。

## Artifacts

New script:

- `scripts/experiments/entry_ev_support_negative_month_inventory_diagnostics.py`

New tests:

- `tests/test_entry_ev_support_negative_month_inventory_diagnostics.py`

Run:

- `data/reports/backtests/20260703_075023_20260703_entry_ev_00370_support_negative_month_inventory/`

Outputs:

- `support_negative_month_source_inventory.csv`
- `support_negative_month_inventory.csv`
- `support_negative_month_config_summary.csv`
- `support_negative_month_target_summary.csv`
- `support_negative_month_inventory_meta.json`

## Method

Scan target:

```text
data/reports/backtests/**/*selector_monthly_metrics.csv
```

Support classification reuses the same path as admission repair target diagnostics:

```text
negative month:
  month_pnl < month_floor

support-sufficient negative month:
  negative month
  support_limited_month == false

support-limited negative month:
  negative month
  support_limited_month == true
```

Default thresholds:

```text
month_floor = 0.0
shallow_month_floor = -1.0
min_month_trades = 1
max_side_trade_share = 0.95
```

Realized monthly PnL is used only to label research targets and summarize artifact history. It is not an execution-time feature.

## Aggregate Result

| metric | value |
|---|---:|
| monthly metrics loaded | 17 |
| load errors | 0 |
| inventory rows | 29,371 |
| negative rows | 9,491 |
| support-sufficient negative rows | 5,065 |
| support-limited negative rows | 4,426 |
| config groups | 1,277 |
| configs with support-sufficient negatives | 1,274 |
| configs with support-limited negatives | 1,271 |
| negative target identities | 20 |
| targets with support-sufficient config | 14 |
| support-limited-only targets | 6 |

## Target Inventory

Top support-sufficient targets by config count:

| role | family | month | configs | support-sufficient | support-limited | best PnL | worst PnL | metric parents |
|---|---|---|---:|---:|---:|---:|---:|---:|
| `refit2025_validation` | `refit2025` | `2025-03` | 1,257 | 1,250 | 7 | `-0.4730` | `-44.1730` | 17 |
| `refit2025_validation` | `refit2025` | `2025-09` | 1,124 | 1,118 | 6 | `-0.4374` | `-16.7540` | 16 |
| `refit2025_validation` | `refit2025` | `2025-06` | 763 | 756 | 7 | `-0.3744` | `-25.6500` | 17 |
| `refit2025_validation` | `refit2025` | `2025-05` | 430 | 429 | 1 | `-9.3634` | `-400.7906` | 17 |
| `refit2025_validation` | `refit2025` | `2025-08` | 850 | 406 | 444 | `-0.8832` | `-2.6304` | 15 |
| `refit2025_validation` | `refit2025` | `2025-12` | 347 | 345 | 2 | `-1.2210` | `-7.6116` | 13 |
| `refit2025_validation` | `refit2025` | `2025-02` | 314 | 308 | 6 | `-0.0120` | `-6.0104` | 13 |
| `refit2025_validation` | `refit2025` | `2025-04` | 163 | 163 | 0 | `-0.3000` | `-18.4180` | 11 |
| `hgb2024_0306_external` | `hgb2024_0306` | `2024-05` | 135 | 135 | 0 | `-0.6352` | `-37.4922` | 5 |
| `hgb2024_0306_external` | `hgb2024_0306` | `2024-03` | 66 | 66 | 0 | `-2.0850` | `-53.4296` | 7 |

Support-limited-only targets:

| role | family | month | configs | support-sufficient | support-limited | best PnL | metric parents |
|---|---|---|---:|---:|---:|---:|---:|
| `hybrid2025_0912_external` | `hybrid2025_0912` | `2025-10` | 7 | 0 | 7 | `-18.7960` | 1 |
| `refit2025_validation` | `refit2025` | `2025-07` | 22 | 0 | 22 | `-2.4840` | 2 |
| `hybrid2025_0912_external` | `hybrid2025_0912` | `2025-12` | 166 | 0 | 166 | `-4.1460` | 5 |
| `hybrid2025_0912_external` | `hybrid2025_0912` | `2025-11` | 1,232 | 0 | 1,232 | `-0.7200` | 17 |
| `fresh2024_validation` | `fresh2024` | `2024-11` | 1,258 | 0 | 1,258 | `-0.6120` | 17 |
| `fresh2024_validation` | `fresh2024` | `2024-03` | 1,264 | 0 | 1,264 | `-0.3636` | 17 |

## Decision

Accepted:

- support negative month inventory diagnostics
- source inventory / config summary / target summary outputs
- using the inventory to choose future support-sufficient selector-surface targets

Not accepted:

- treating config rows as independent observations
- merging support-limited-only targets into support-sufficient replacement selector evaluation
- reading realized monthly PnL summaries as execution-time features

Standard policy remains NoTrade.

## Next

1. Build a canonical support-sufficient target set from multiple metric parents, avoiding duplicate config rows as pseudo-samples.
2. Re-run the support-sufficient selector surface from 00368/00369 across that target set.
3. Keep support-limited-only targets in a separate lane for side/trade-support repair.

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_support_negative_month_inventory_diagnostics.py tests/test_entry_ev_support_negative_month_inventory_diagnostics.py`: OK
- `uv run python -m unittest tests.test_entry_ev_support_negative_month_inventory_diagnostics`: OK
- 00370 support negative month inventory run: OK
