# Entry EV Support Repair Pairwise Switch

日時: 2026-07-03 07:52 JST
更新日時: 2026-07-03 07:52 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00332でscalar harmful penaltyが勝ち候補を落とすと分かったため、同一decision cluster内のpairwise/listwise switching診断へ進んだ。
- `entry_ev_support_repair_pairwise_switch_diagnostics.py` を追加し、選択済みsupport repair候補と近傍代替候補を `(scenario_label, role, month, side)` 内で比較するようにした。
- best 00329/00332 baseline scenarioでは、近傍代替がある選択候補は3本、pairwise examplesは22本だけだった。
- harmful probabilityが低い代替へ切り替える規則は、baseline best scenarioで1件発火し、その1件はactual `-5.8900` の悪化だった。
- EV -2 scenarioまで緩めるとpairsは72本まで増えたが、harmful lower switchは9 pairsすべて悪化し、actual delta sum `-118.6696` だった。
- 結論: pairwise/listwise switching診断インフラはaccepted。現support repair surfaceは学習policyにするには薄く、harmful lower ruleもswitch policyとしてreject。標準policyはNoTrade。

## Artifacts

- Added script:
  - `scripts/experiments/entry_ev_support_repair_pairwise_switch_diagnostics.py`
- Added tests:
  - `tests/test_entry_ev_support_repair_pairwise_switch_diagnostics.py`
- Baseline best scenario diagnostics:
  - `data/reports/backtests/20260702_225020_20260703_entry_ev_00333_support_repair_pairwise_switch_s2/`
  - `data/reports/backtests/20260702_225038_20260703_entry_ev_00333_support_repair_pairwise_switch_w120_s1/`
- Looser EV -2 scenario diagnostics:
  - `data/reports/backtests/20260702_225051_20260703_entry_ev_00333_support_repair_pairwise_switch_evm2_s1/`

## Implementation

The diagnostic reads existing support repair replay artifacts:

```text
ranker_replay_candidates_pnl.csv
broad_prior_horizon_choice_additions.csv
broad_prior_horizon_choice_replay_summary.csv
```

It reconstructs `scenario_label` from scenario columns when the candidates CSV does not contain it.

Default local grouping:

```text
scenario_label, role, month, side
```

Outputs:

```text
support_repair_pairwise_switch_examples.csv
support_repair_listwise_switch_summary.csv
support_repair_pairwise_rule_summary.csv
support_repair_context_harmful_summary.csv
config.json
```

The core targets are:

```text
switch_actual_delta =
  alt_actual_pnl_at_hv_chosen_horizon
  - chosen_actual_pnl_at_hv_chosen_horizon

harmful_prob_reduction =
  chosen_harmful_prob
  - alt_harmful_prob
```

This does not alter the replay policy. It only asks whether a candidate-level meta-selector could learn to replace the current support-repair selection with a better near alternative.

## Results

Baseline best scenario:

```text
available_candidates_p0p45_ev2_tail0p3_reqmodel_ranker_pnl
```

Listwise summary:

| selected | role | month | side | chosen actual | near alternatives | best actual switch | lowest harmful switch | harmful correct | harmful wrong |
|---:|---|---|---|---:|---:|---:|---:|---:|---:|
| 2 | refit2025_validation | 2025-08 | long | `+13.2500` | `2` | `-0.4500` | `-0.4500` | `0` | `0` |
| 3 | refit2025_validation | 2025-08 | short | `+2.9340` | `18` | `+2.6360` | `-0.7740` | `0` | `0` |
| 4 | hybrid2025_0912_external | 2025-11 | short | `+10.4400` | `2` | `-1.0300` | `-5.8900` | `0` | `1` |

Rule summary:

| rule | pairs | selected | improves | hurts | actual delta sum | mean |
|---|---:|---:|---:|---:|---:|---:|
| all near pairs | `22` | `3` | `4` | `18` | `-43.4054` | `-1.9730` |
| support proxy higher alt | `2` | `1` | `0` | `2` | `-0.9800` | `-0.4900` |
| harmful lower alt | `1` | `1` | `0` | `1` | `-5.8900` | `-5.8900` |

The only strong harmful-lower switch is exactly the 00332 false-positive case: 2025-11 short `01:35` actual `+10.4400` would be replaced by `01:43` actual `+4.5500`.

The 120-minute near window produced the same selected rows and the same local alternatives. The bottleneck is not the near-window width; it is the thin candidate surface after current support-repair gating.

Looser EV -2 scenario:

```text
available_candidates_p0p45_evm2_tail0p3_reqmodel_ranker_pnl
```

This expands the listwise rows to 6 selected choices and 72 pairs, but the switching signal is still not policy-ready.

Key results:

| rule | pairs | selected | improves | hurts | actual delta sum | mean |
|---|---:|---:|---:|---:|---:|---:|
| all near pairs | `72` | `6` | `6` | `66` | `-424.6582` | `-5.8980` |
| tail prob lower alt | `47` | `5` | `2` | `45` | `-351.3928` | `-7.4764` |
| support proxy higher alt | `46` | `4` | `0` | `46` | `-406.6476` | `-8.8402` |
| harmful lower alt | `9` | `3` | `0` | `9` | `-118.6696` | `-13.1855` |

EV -2 also adds the known bad `fresh2024_validation 2024-08 long` selected row, actual `-29.1360`. Oracle local switching could improve it by `+33.9860`, but the harmful-lower rule does not identify this reliably; the selected harmful probability is already low (`0.0067`).

## Interpretation

The diagnostic confirms three points.

First, 00332's scalar penalty failure was not just a weight issue. In the current local clusters, lowering harmful probability often chooses worse realized PnL.

Second, the useful switching target is not `lower harmful probability`. The useful target is closer to:

```text
which candidate in this local non-overlap cluster has better realized repair utility
```

This needs richer context: local rank, horizon, support need, month/role/side pressure, time density, model-used status, and prior evidence. Harmful probability can be one feature, not the objective.

Third, current selected-addition-only clusters are too sparse for a stable learned switcher. Baseline best gives only 22 pairs across 3 selected rows. EV -2 gives more pairs, but mostly by admitting weak candidates and known bad support fillers.

## Decision

Accepted:

- pairwise/listwise support-repair switch diagnostic infrastructure
- scenario label reconstruction for older candidates CSV
- local rule summary for harmful / tail / support proxy comparisons
- context-level harmful summary for selected additions and candidate pool

Rejected as current policy:

- harmful-lower switch rule
- tail-lower switch rule
- support-proxy-higher switch rule
- EV -2 loosening as a way to thicken the support-repair policy surface

Standard policy remains NoTrade.

## Next

1. Broaden the switch universe before stateful selection:
   - compare all gated support candidates, not only candidates near selected additions
   - group by non-overlap decision clusters instead of selected-addition clusters only
2. Build a listwise target that ranks alternatives by realized repair utility:
   - actual PnL
   - repair target reduction
   - month/role/side blocker relief
   - one-position constraint impact
3. Use harmful probability only as a calibrated feature:
   - horizon
   - side
   - session
   - regime
   - support bucket
4. Keep 00329 low-complexity horizon-ranker baseline as the diagnostic comparison point.
5. Revisit remaining standard blockers:
   - `role_trades_low`
   - `side_share_high`
   - month floor `-0.6120`

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_support_repair_pairwise_switch_diagnostics.py tests/test_entry_ev_support_repair_pairwise_switch_diagnostics.py`: OK
- `uv run python -m unittest tests.test_entry_ev_support_repair_pairwise_switch_diagnostics`: OK
- baseline best scenario pairwise diagnostics: OK
- 120-minute baseline near-window sensitivity: OK
- EV -2 pairwise diagnostics: OK
