# Entry EV Support-Sufficient Selector Surface

日時: 2026-07-03 16:33 JST
更新日時: 2026-07-03 16:33 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00367の次アクションとして、prior month count / support thresholdをreplacement selector surfaceへ入れ、00364のloss-risk selectorと接続した。
- `entry_ev_support_sufficient_selector_surface_diagnostics.py` を追加し、全current tradesからobservable loss-risk selectorで外す1本を選び、そのtradeを外した状態でstatefully available replacement candidateをprior-calibrated scoreで選ぶ。
- 対象は `refit2025_validation 2025-03`。baseline month PnL `-0.4730`、9 trades、loss 4本、candidate prior rows `664` / prior months `2`。
- min prior month `1` では、`feature:side_gap_ge0p15_lossfirst_lt0p30` + `side_score` が `2025-03-21 14:00 short -2.3400` を外し、`2025-03-27 13:59 long` one-fail replacementを選び、month PnL `+35.1570` まで伸びた。ただしcandidate prior month countは `1` なのでsupport不足。
- min prior month `2` かつ candidate prior count `>=50` / prior actual mean `>=0` でも、同じ `side_gap` risk selectorがworst short lossを選べる。bestは `bias_corrected` / context min20で `2025-03-27 23:58 long` を選び、month PnL `+22.4970`。`prior_actual_mean` / context min50では `+19.7740`。
- min prior month `3` ではreplacement候補が0件。現targetのpriorは2ヶ月しかなく、標準policy evidenceには足りない。
- `combined:any_lossrisk`、`score:loss_first_prob`、`prior:direction,combined_regime:prior_count_ge5_lossrate_ge0p50` は `2025-03-31 03:40 short +1.3800` のwinnerを外す。replacementが大きいためmonth PnL自体はpositiveになる場合があるが、loss-risk selectorとしてはwinner damageを示す。
- 判断: loss-risk + calibrated replacement selector surfaceはaccepted infrastructure。support-sufficient laneの方向性は前進したが、単一target月、2 prior months、one-fail replacement依存のため標準policyではない。標準policyはNoTrade。

## Artifacts

Added script:

- `scripts/experiments/entry_ev_support_sufficient_selector_surface_diagnostics.py`

Added tests:

- `tests/test_entry_ev_support_sufficient_selector_surface_diagnostics.py`

Run:

- `data/reports/backtests/20260703_073224_20260703_entry_ev_00368_support_sufficient_selector_surface/`

Outputs:

- `support_sufficient_selector_surface_choices.csv`
- `support_sufficient_selector_surface_summary.csv`
- `support_sufficient_selector_surface_targets.csv`
- `support_sufficient_selector_surface_risk_trades.csv`
- `support_sufficient_selector_surface_risk_hits.csv`
- `support_sufficient_selector_surface_candidates.csv`
- `support_sufficient_selector_surface_meta.json`

## Method

This report closes one hindsight gap in 00367:

```text
00367:
  actual loss trade is known -> choose replacement

00368:
  observable risk selector chooses one current trade -> choose replacement
```

Risk selectors:

```text
feature:ev_ge5_lossfirst_lt0p30
feature:side_gap_ge0p15_lossfirst_lt0p30
feature:lossfirst_ge0p40_or_ev_ge5_lossfirst_lt0p30
prior:direction,combined_regime:prior_count_ge5_lossrate_ge0p50
combined:any_lossrisk
score:loss_first_prob
score:ev_low_lossfirst
oracle:worst_loss
```

Candidate support surface:

```text
calibration_min_context_count: 20, 50
candidate_min_prior_count: 20, 50, 100
candidate_min_prior_month_count: 1, 2, 3
candidate_min_prior_actual_mean: -inf, 0, 5, 10
replacement_score_mode: prior_actual_mean, bias_corrected, raw_pred_fixed, side_score
```

Important:

- Risk selectors use selected-trade features and chronological trade prior only.
- Replacement calibration uses candidate side rows from months before the target month.
- `oracle:worst_loss` is diagnostic only.
- Candidate realized PnL is used only for evaluation.

## Main Result

Top support-light result:

| risk selector | score | support | selected trade | candidate | candidate actual | month PnL | reading |
|---|---|---|---|---|---:|---:|---|
| `feature:side_gap_ge0p15_lossfirst_lt0p30` | `side_score` | prior count `48`, months `1` | `2025-03-21 14:00 short -2.3400` | `2025-03-27 13:59 long` | `+33.2900` | `+35.1570` | very strong, but one-month candidate prior |
| `oracle:worst_loss` | `side_score` | prior count `48`, months `1` | same | same | `+33.2900` | `+35.1570` | confirms risk selector matches oracle on this target |
| `feature:ev_ge5_lossfirst_lt0p30` | `side_score` | prior count `48`, months `1` | `2025-03-21 14:29 short -0.3324` | same | `+33.2900` | `+33.1494` | selects smaller short loss |

Stricter support result with min prior month `2`, candidate prior count `>=50`, prior actual mean `>=0`:

| risk selector | score | context min | selected trade | candidate | candidate actual | candidate prior | month PnL |
|---|---|---:|---|---|---:|---:|---:|
| `feature:side_gap_ge0p15_lossfirst_lt0p30` | `bias_corrected` | `20` | `2025-03-21 14:00 short -2.3400` | `2025-03-27 23:58 long` | `+20.6300` | count `254`, months `2`, prior actual `+23.0083` | `+22.4970` |
| `feature:side_gap_ge0p15_lossfirst_lt0p30` | `prior_actual_mean` | `50` | `2025-03-21 14:00 short -2.3400` | `2025-03-11 06:39 long` | `+17.9070` | count `157`, months `2`, prior actual `+29.7708` | `+19.7740` |
| `feature:ev_ge5_lossfirst_lt0p30` | `bias_corrected` | `20` | `2025-03-21 14:29 short -0.3324` | `2025-03-27 23:58 long` | `+20.6300` | count `254`, months `2`, prior actual `+23.0083` | `+20.4894` |

Support sensitivity:

| candidate min prior months | choice rows | replacements |
|---:|---:|---:|
| `1` | `768` | `768` |
| `2` | `768` | `768` |
| `3` | `768` | `0` |

## Loss-Risk Selector Findings

Good signs:

- `feature:side_gap_ge0p15_lossfirst_lt0p30` selects `2025-03-21 14:00 short -2.3400`, the worst loss and same trade as the oracle worst-loss selector.
- `feature:ev_ge5_lossfirst_lt0p30` and `score:ev_low_lossfirst` select `2025-03-21 14:29 short -0.3324`, another short loss.
- This supports the idea that low loss-first + high EV / high side-gap captures an EV-overconfidence failure type.

Bad signs:

- `combined:any_lossrisk`, `score:loss_first_prob`, and the `direction,combined_regime` prior selector select `2025-03-31 03:40 short +1.3800`, a winner.
- That winner has many risk hits and high prior loss rate, so broad risk aggregation is still too noisy.
- Month PnL can remain positive after replacing that winner only because the replacement candidate is very strong in this target month. That is not valid evidence that the risk selector is safe.

## Decision

Accepted:

- support-sufficient selector surface diagnostics
- risk selector -> replacement selector connection
- candidate support filters by prior count, prior month count, prior actual mean
- explicit oracle-vs-observable risk selector comparison

Candidate:

- `side_gap_ge0p15_lossfirst_lt0p30` as a support-sufficient loss-risk selector feature
- min prior month `2` + prior count `>=50` replacement filter
- `bias_corrected` / `prior_actual_mean` replacement score under support filters

Rejected / not enough:

- standardizing any result from a single support-sufficient target month
- using min prior month `1` best result as policy evidence
- broad `combined:any_lossrisk` or pure `loss_first_prob` as replacement trigger
- treating replacement gains after selecting a winner as loss-risk success

Standard policy remains NoTrade.

## Next

1. Run this selector surface across all available support-sufficient negative months.
2. Add minimum target count requirements before considering any selector standardization.
3. Split loss-risk selectors by failure type: EV-overconfidence short loss, loss-first long loss, prior-context loss.
4. Move from rule surface to a small chronological loss-risk/rerank head only after target months are broadened.

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_support_sufficient_selector_surface_diagnostics.py tests/test_entry_ev_support_sufficient_selector_surface_diagnostics.py`: OK
- `uv run python -m unittest tests.test_entry_ev_support_sufficient_selector_surface_diagnostics`: OK
- 00368 support-sufficient selector surface run: OK
