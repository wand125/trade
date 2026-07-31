# Entry EV Position-Quality Holdout Support

日時: 2026-07-02 17:36 JST
更新日時: 2026-07-02 17:36 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00310の次アクションとして、`long_range_normal_ny_fixed60_pred_gt0` が refit2025 以外の未使用側で再現するかを確認した。
- `scripts/experiments/entry_ev_entry_block_holdout_support_diagnostics.py` を追加し、entry-block overlayの効果を discovery / holdout に分解できるようにした。
- discoveryは `refit2025_validation`、holdoutはそれ以外の `cal2024`, `fresh2024`, `hgb2024_0306`, `hgb2025_08`, `hybrid2025_0912` とした。
- 00310の最良診断候補 `long_range_normal_ny_fixed60_pred_gt0` は discoveryで +11.4912 改善したが、holdoutでは発火0件 / delta 0.0000。
- broader `long_range_normal_ny` はholdoutで2件発火し net +0.7370だが、1件勝ちtradeを削っており、ruleの主効果は引き続きrefit2025に集中している。
- 判断: `long_range_normal_ny_fixed60_pred_gt0` は未使用chronology支持なし。標準policyにはしない。短期path過大評価のfeature候補として残す。

## Artifacts

- New script:
  - `scripts/experiments/entry_ev_entry_block_holdout_support_diagnostics.py`
- New tests:
  - `tests/test_entry_ev_entry_block_holdout_support_diagnostics.py`
- Diagnostics:
  - `data/reports/backtests/20260702_083630_20260702_entry_ev_00311_position_quality_holdout_support_s1/`

## Method

Input:

```text
data/reports/backtests/20260702_082037_20260702_entry_ev_00310_position_quality_proxy_overlay_s1/entry_block_overlay_trades.csv
```

Filter:

```text
selector_variant contains isolated_large_loss_long_t-5_h720
discovery role = refit2025_validation
holdout = all non-refit roles
```

Rules checked without re-search:

```text
holdext_long_range_normal_ny
long_range_normal_ny
long_range_normal_ny_fixed60_pred_gt0
long_range_normal_ny_lossprob_lt0p3_sidegap_ge0p2
long_range_normal_ny_rank_lt0p55
```

For each rule, the script reports:

```text
input_adjusted_pnl
total_adjusted_pnl after block
blocked_trade_count
blocked_adjusted_pnl
pnl_delta_vs_input
affected role/family/month counts
```

This does not create a new rule. It only splits the already chosen rule into discovery and holdout cohorts.

## Results

### Main Candidate

`long_range_normal_ny_fixed60_pred_gt0`:

| scope | input trades | blocked | blocked loss | blocked win | input PnL | total after | delta |
|---|---:|---:|---:|---:|---:|---:|---:|
| all | `246` | `4` | `4` | `0` | `+326.1098` | `+337.6010` | `+11.4912` |
| discovery refit2025 | `113` | `4` | `4` | `0` | `+270.8392` | `+282.3304` | `+11.4912` |
| holdout non-refit | `133` | `0` | `0` | `0` | `+55.2706` | `+55.2706` | `+0.0000` |

Reading:

- 00310の改善は全てrefit2025由来。
- holdout側ではruleが1件も発火しないため、再探索なしの外部支持とは言えない。
- したがってこのruleはdiagnostic candidateから標準候補へ昇格しない。

### Broader Context Check

| rule | scope | blocked | blocked PnL | delta | reading |
|---|---|---:|---:|---:|---|
| `long_range_normal_ny` | discovery | `9` | `-15.3142` | `+15.3142` | refit主効果 |
| `long_range_normal_ny` | holdout | `2` | `-0.7370` | `+0.7370` | cal lossを消すがhgb winnerも消す |
| `long_range_normal_ny_rank_lt0p55` | discovery | `7` | `-12.2542` | `+12.2542` | refit主効果 |
| `long_range_normal_ny_rank_lt0p55` | holdout | `1` | `-2.6640` | `+2.6640` | cal2024 1件のみ |
| `long_range_normal_ny_lossprob_lt0p3_sidegap_ge0p2` | discovery | `1` | `-0.8832` | `+0.8832` | 00309 target rowのみ |
| `long_range_normal_ny_lossprob_lt0p3_sidegap_ge0p2` | holdout | `0` | `0.0000` | `0.0000` | no support |

Blocked holdout rows for broad context:

| rule | role | month | PnL | reading |
|---|---|---|---:|---|
| `long_range_normal_ny` | `cal2024_validation` | `2024-01` | `-2.6640` | helpful block |
| `long_range_normal_ny` | `hgb2024_0306_external` | `2024-05` | `+1.9270` | harmful block |
| `long_range_normal_ny_rank_lt0p55` | `cal2024_validation` | `2024-01` | `-2.6640` | one-row support |

Reading:

- broader context has weak non-refit signal, but support is 1-2 rows and includes a harmed winner.
- `rank_lt0p55` holdout improvement is one cal2024 row only.
- This is not enough to convert the refit-driven rule into a robust policy.

## Decision

Accepted:

- discovery/holdout split diagnostics for entry-block overlay outputs.
- `long_range_normal_ny_fixed60_pred_gt0` remains useful as a short-horizon overestimate diagnostic.

Rejected:

- `long_range_normal_ny_fixed60_pred_gt0` as standard policy candidate.
- treating refit-only block improvements as unused chronology evidence.
- promoting broader `long_range_normal_ny` or `rank_lt0p55` based on 1-2 holdout rows.

Standard policy remains NoTrade.

## Next

1. Stop trying to hard-block `long_range_normal_ny_fixed60_pred_gt0` directly.
2. Convert the fixed60 positive / actual short-horizon negative pattern into model-level uncertainty or calibration-residual features.
3. Keep holdout-support diagnostics as a mandatory step before promoting any entry-block overlay rule.
4. Continue with candidate-level selector / calibration / exit timing target rather than post-hoc static blacklist.

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_entry_block_holdout_support_diagnostics.py tests/test_entry_ev_entry_block_holdout_support_diagnostics.py`: OK
- `uv run python -m unittest tests.test_entry_ev_entry_block_holdout_support_diagnostics tests.test_entry_ev_stateful_entry_block_overlay tests.test_docs_reports`: OK
- `git diff --check`: OK
- 00311 holdout-support diagnostics run: OK
