# Entry EV Support Repair Singleton Surface

日時: 2026-07-03 08:51 JST
更新日時: 2026-07-03 08:51 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00337のsingleton abstentionを、current-selected 2例から、00335 leak-free replayの複数scenario surfaceへ広げた。
- `selected + quota_full/overlap` candidate universeをscenarioごとに再構成し、singleton groupを抽出して、scenario-weighted集計とunique candidate dedup集計の両方を出した。
- all scopesでは72 scenarios / 2218 candidate rows / 79 singleton scenario-rows / 7 unique singleton candidates。`singleton_720_pred_pnl_lt2` は24 scenario-rowsをflagし、すべて `fresh2024_validation 2024-08 long -29.1360` の重複で、positive damageは0。
- available-onlyでは36 scenarios / 2047 candidate rows / 46 singleton scenario-rows / 4 unique singleton candidates。prior mean/tail/risk、pred PnL、pred fixed-best 60mの各ruleはいずれも24 scenario-rowsをflagし、uniqueでは同じ `fresh2024 2024-08` 1件だけ。positive damageは0。
- 一方、all scopesではprior mean/tail/risk ruleがgreedy側のpositive singleton `refit2025_validation 2025-08 long +13.7800` もflagする。`singleton_720_pred_pnl_lt2` はこのpositiveをflagしない。
- 判断: singleton surface diagnosticsはaccepted infrastructure。available-onlyではrisk-conditioned abstentionのsignalは強いが、unique負例が1件だけなので標準policyにはしない。次は別family / 別期間 / 追加surfaceでsingleton事例を増やすことと、fresh/thin month代替候補生成へ進む。標準policyはNoTrade。

## Artifacts

- Added script:
  - `scripts/experiments/entry_ev_support_repair_singleton_surface_diagnostics.py`
- Added tests:
  - `tests/test_entry_ev_support_repair_singleton_surface_diagnostics.py`
- All row scopes:
  - `data/reports/backtests/20260702_235020_20260703_entry_ev_00338_support_repair_singleton_surface_all_scenarios/`
- Available-only row scope:
  - `data/reports/backtests/20260702_235100_20260703_entry_ev_00338_support_repair_singleton_surface_available_scenarios/`

Outputs:

```text
singleton_surface_rule_summary.csv
singleton_surface_scenario_rule_summary.csv
singleton_surface_flagged_rows.csv
singleton_surface_unique_singletons.csv
singleton_surface_skipped_scenarios.csv
config.json
```

## Method

Inputs:

```text
data/reports/backtests/20260702_231709_20260703_entry_ev_00335_support_repair_leakfree_replay_w0_s2/broad_prior_horizon_choice_additions.csv
data/reports/backtests/20260702_231709_20260703_entry_ev_00335_support_repair_leakfree_replay_w0_s2/broad_prior_horizon_choice_rejections.csv
data/reports/backtests/20260702_231709_20260703_entry_ev_00335_support_repair_leakfree_replay_w0_s2/broad_prior_horizon_choice_replay_summary.csv
```

For each scenario, the diagnostic reconstructs the same stateful universe style as 00334:

```text
selected rows + rejected rows with reject_reason in quota_full,overlap
```

Then it computes:

```text
quota_group_row_count
quota_group_quota
quota_group_is_singleton = row_count <= quota
singleton_surface_key = role/month/side/decision_timestamp/horizon
```

The key point is deduplication. The same candidate appears in many threshold scenarios, so scenario-weighted evidence is useful for robustness across thresholds but not independent sample support. The unique candidate count is the stricter support number.

## Results

All row scopes:

| rule | flagged rows | flagged unique | flagged actual | flagged loss rate | positive damage | reading |
|---|---:|---:|---:|---:|---:|---|
| singleton_any | `79` | `7` | `-82.1600` | `0.3038` | `+617.1040` | too blunt |
| prior mean/tail/risk rules | `33` | `2` | `-575.2440` | `0.7273` | `+124.0200` | catches loss but damages a positive 720m singleton |
| singleton_720_pred_pnl_lt2 | `24` | `1` | `-699.2640` | `1.0000` | `0.0000` | cleanest in this surface |
| singleton_720_pred_best_60m | `42` | `2` | `-456.0840` | `0.5714` | `+243.1800` | too broad |

Available-only:

| rule | flagged rows | flagged unique | flagged actual | flagged loss rate | positive damage | reading |
|---|---:|---:|---:|---:|---:|---|
| singleton_any | `46` | `4` | `-488.4800` | `0.5217` | `+210.7840` | too blunt |
| prior mean/tail/risk rules | `24` | `1` | `-699.2640` | `1.0000` | `0.0000` | clean in available surface |
| singleton_720_pred_pnl_lt2 | `24` | `1` | `-699.2640` | `1.0000` | `0.0000` | clean in available surface |
| singleton_720_pred_best_60m | `24` | `1` | `-699.2640` | `1.0000` | `0.0000` | clean in available surface |

Available-only unique singleton candidates:

| role | month | side | horizon | actual | pred PnL | 720m prior mean | 720m prior tail | 720m prior risk | pred fixed best |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| fresh2024_validation | 2024-08 | long | `720` | `-29.1360` | `+1.2973` | `-3.4993` | `0.4145` | `9.9773` | `60` |
| refit2025_validation | 2025-07 | short | `240` | `+4.6900` | `+3.1819` | `-0.3434` | `0.3834` | `2.2602` | `240` |
| hybrid2025_0912_external | 2025-11 | short | `60` | `+10.4400` | `+2.3420` | `-6.9211` | `0.5760` | `18.8410` | `720` |
| hybrid2025_0912_external | 2025-10 | long | `720` | `+10.9530` | `+2.3111` | `+7.3031` | `0.2138` | `1.0692` | `0` |

Interpretation:

- `singleton_any` remains rejected. It damages positive singleton candidates.
- Available-only risk-conditioned rules look clean, but the independent support is one negative unique candidate repeated across thresholds.
- All-scopes prior rules are less clean because greedy-selected scenarios introduce a positive 720m singleton with negative broad prior. This means prior risk alone should not become a hard policy without row-scope/context separation.
- `singleton_720_pred_pnl_lt2` is the cleanest diagnostic candidate across all-scopes and available-only because it flags the repeated fresh negative without positive damage here.

## Decision

- `entry_ev_support_repair_singleton_surface_diagnostics.py`: accepted infrastructure.
- `singleton_any`: reject.
- `singleton_720_pred_pnl_lt2`: best diagnostic abstention candidate from this surface.
- Prior mean/tail/risk rules: useful features, but not hard policy because all-scopes positive damage appears.
- Standard policy remains NoTrade.

## Next

1. Create more singleton evidence from additional support-repair surfaces, families, and periods before hard-policy use.
2. Use `singleton_720_pred_pnl_lt2` as a pre-registered diagnostic guard in future replays, but do not standardize it yet.
3. Continue fresh/thin month candidate generation so abstention does not merely reduce trades and leave support blockers unresolved.
4. Keep scenario-weighted and unique-dedup evidence separate in reports.

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_support_repair_singleton_surface_diagnostics.py tests/test_entry_ev_support_repair_singleton_surface_diagnostics.py`: OK
- `uv run python -m unittest tests.test_entry_ev_support_repair_singleton_surface_diagnostics`: OK
- all-scenarios singleton surface diagnostics run: OK
- available-only singleton surface diagnostics run: OK
