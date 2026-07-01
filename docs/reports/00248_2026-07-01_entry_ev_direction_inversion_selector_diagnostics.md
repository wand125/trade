# Entry EV Direction Inversion Selector Diagnostics

日時: 2026-07-01 23:07 JST
更新日時: 2026-07-01 23:07 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00247の次アクションとして、direction inversion riskをdirect score penaltyではなくcandidate-level selector/ranking featureとして評価する `scripts/experiments/entry_ev_direction_inversion_selector_diagnostics.py` を追加した。
- 00244 side-prior baselineと00247 direction s0.1 runを、同じdirection inversion prediction parquetでenrichし、selected sideのrisk/source/supportをcandidate単位に集約した。
- NoTrade-first selectionでは全候補が `total_pnl_below_floor`, `role_total_pnl_below_floor`, `month_pnl_below_floor` で不合格。risk条件以前にPnL床を通らない。
- candidate-levelでは direction s0.1 q99/floor5 が最上位だが、total `-147.3314`, min month `-153.9192` で標準化不可。
- pointwise screenでは high-risk rowsを消すと見かけ上改善する。例: side-prior q95/floor5 の `bucket_or_global_high` 削除は `-160.8606 -> +79.3774`。しかし kept min monthは `-55.3686` で、one-position replacementを再実行していないためpolicyとして扱わない。
- high-risk sourceを見ると、bucket highとglobal highの両方が損失を含むが、contextごとに分布が違う。global highをscore penaltyから外した00247判断は維持しつつ、selector診断ではsource別featureとして残す。
- 判断: selector/ranking diagnosticsはaccepted。direction inversion risk単独ではNoTrade-first selectorを通らない。次はreplacement positive-quality headと組み合わせ、pointwise screenではなくstateful replayで確認する。

## Artifacts

- Script: `scripts/experiments/entry_ev_direction_inversion_selector_diagnostics.py`
- Test: `tests/test_entry_ev_direction_inversion_selector_diagnostics.py`
- Input predictions:
  - `data/reports/backtests/20260701_135325_20260701_entry_ev_direction_inversion_policy_inputs_s0p1_s1/enriched_predictions/refit2025_predictions_direction_inversion.parquet`
- Policy runs:
  - side-prior baseline: `data/reports/backtests/20260701_131856_20260701_entry_ev_side_prior_pressure_s0p5_fixed2025_03_12_trades_s1/`
  - direction s0.1: `data/reports/backtests/20260701_135349_20260701_entry_ev_direction_inversion_s0p1_fixed2025_03_12_trades_s1/`
- Diagnostic run:
  - `data/reports/backtests/20260701_140703_20260701_entry_ev_direction_inversion_selector_diagnostics_s1/`

## Method

For each selected trade:

```text
selected_direction_inversion_risk
selected_direction_inversion_source
selected_direction_inversion_support
selected_direction_inversion_risk_bucket
selected_direction_inversion_score_delta
```

are selected from long/short prediction columns according to the actual selected trade side.

Candidate-level aggregation includes:

```text
PnL floors
trade support
direction_error_rate
bucket/global/no-prior share
bucket high-risk share and PnL
global high-risk share and PnL
mean support
score delta
```

Selector gates are NoTrade-first:

```text
total_pnl >= 0
min_role_total_pnl >= 0
min_month_pnl >= 0
trade_count >= 10
```

Risk gates are also available, but in this run no candidate reaches the PnL gates.

## Candidate Summary

| run | candidate | total | min month | trades | dir error rate | bucket share | global share | bucket high share | bucket high PnL | global high PnL |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| direction s0.1 | q99/floor5 | `-147.3314` | `-153.9192` | `50` | `0.5400` | `0.4400` | `0.4400` | `0.1600` | `-51.3254` | `-68.8644` |
| side-prior | q95/floor5 | `-160.8606` | `-233.2854` | `80` | `0.5125` | `0.5375` | `0.3625` | `0.2125` | `-48.9320` | `-191.3060` |
| direction s0.1 | q95/floor5 | `-163.3410` | `-206.7934` | `73` | `0.5342` | `0.5068` | `0.3836` | `0.1918` | `-19.0462` | `-162.1372` |
| side-prior | q99/floor5 | `-177.3790` | `-162.1992` | `53` | `0.5283` | `0.4717` | `0.4151` | `0.1698` | `-121.9334` | `-77.2560` |

Reading:

- direction s0.1 q99 is best by total and min month, but still NoTrade below zero.
- bucket high risk is not always the main loss bucket. For side-prior q95, global high PnL `-191.3060` dominates.
- source-aware features matter, but source-aware hard screening is still not a stateful policy.

## Selector

All four candidate/run rows are ineligible:

```text
total_pnl_below_floor
role_total_pnl_below_floor
month_pnl_below_floor
```

No risk gate is the decisive blocker in this run.

## Pointwise Screen Effects

Top pointwise improvements:

| run | candidate | screen | original | removed trades | removed PnL | kept total | kept min month |
|---|---|---|---:|---:|---:|---:|---:|
| side-prior | q95/floor5 | bucket_or_global_high | `-160.8606` | `44` | `-240.2380` | `+79.3774` | `-55.3686` |
| side-prior | q95/floor5 | global_high | `-160.8606` | `27` | `-191.3060` | `+30.4454` | `-60.1466` |
| side-prior | q99/floor5 | bucket_or_global_high | `-177.3790` | `30` | `-199.1894` | `+21.8104` | `-28.9580` |
| direction s0.1 | q95/floor5 | bucket_or_global_high | `-163.3410` | `40` | `-181.1834` | `+17.8424` | `-55.3686` |

This is diagnostic only:

- removing selected trades pointwise does not model replacement entries under the one-position constraint.
- min month remains negative.
- the screen uses fixed-period outcomes for interpretation.

## Worst Contexts

Recurring loss contexts:

| context | signal |
|---|---|
| short / down_normal_vol / asia | bucket and global high-risk losses both appear |
| short / down_normal_vol / ny_overlap | bucket high-risk captures large direction-error losses |
| short / down_normal_vol / london | mostly global high-risk, not bucket-supported |
| long / range_normal_vol / ny_overlap | can remain bucket-supported but not always high-risk |
| long / down_normal_vol / rollover | high direction-error and mixed source |

These contexts should be handled by stateful replay or a replacement-quality layer, not by static deletion.

## Decision

Accepted:

- Direction inversion selected-trade enrichment.
- Candidate-level direction inversion risk/source/support summary.
- Source-aware pointwise diagnostics.

Not accepted:

- Any direction inversion selector output as standard policy.
- Pointwise high-risk deletion as policy evidence.
- Global high-risk hard block without replacement replay.

Standard policy remains NoTrade.

## Next

1. Build `replacement_positive_quality_target` prediction-row input and compare with direction inversion risk.
2. Test combined ranking where direction inversion risk only penalizes entries when replacement quality is also low.
3. Run stateful replay for any combined rule; do not rely on pointwise deletion.
4. Diagnose residual contexts from direction s0.1 q99: down_normal_vol/london, range_normal_vol/ny_overlap, down_normal_vol/rollover.

## Verification

- `python3 -m py_compile scripts/experiments/entry_ev_direction_inversion_selector_diagnostics.py tests/test_entry_ev_direction_inversion_selector_diagnostics.py`: OK
- `python3 -m unittest tests.test_entry_ev_direction_inversion_selector_diagnostics`: OK
- Direction inversion selector diagnostic run: OK
