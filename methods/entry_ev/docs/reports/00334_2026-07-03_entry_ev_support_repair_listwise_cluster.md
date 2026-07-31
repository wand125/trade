# Entry EV Support Repair Listwise Cluster

日時: 2026-07-03 08:03 JST
更新日時: 2026-07-03 08:17 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 訂正: 00335で、support repairのruntime sortとlistwise `repair_score_greedy` に `actual_pnl_at_hv_chosen_horizon` がtie-breakerとして混入していたことを確認した。00334の「repair_score_greedyがcurrent replayと完全一致」という読みはleak混入後の結果なので破棄し、00335のleak-free replayを正とする。
- 00333の次アクションとして、selected addition近傍だけでなく、stateful selection直前の広いgated候補面をlistwiseに診断した。
- `selected + quota_full` rejectionsを再構成し、同じquotaと一玉非重複制約で `repair_score`, actual oracle, predicted PnL, low harmful, low tail, high support proxy のgreedy選択を比較した。
- baseline best scenarioではpost-filter候補31本まで広がった。当時のleak混入後 `repair_score` はcurrent replayと一致して見えたが、この読みは00335で破棄した。actual oracleとの差は `+2.6360` だった。
- EV -2 scenarioではpost-filter候補111本、actual oracle差 `+22.3190` まで増えたが、`fresh2024 2024-08 long -29.1360` は候補が1本しかなく残る。
- low harmful / low tail / high support proxy の単純selectorは大きく悪化した。
- 結論: listwise cluster診断インフラはaccepted。現候補面ではsimple rerankerでは標準blockerを解けない。次は候補生成側、特にfresh2024のthin month coverageと、listwise repair utilityを教師にした広い候補生成/選択へ進む。標準policyはNoTrade。

## Artifacts

- Added script:
  - `scripts/experiments/entry_ev_support_repair_listwise_cluster_diagnostics.py`
- Added tests:
  - `tests/test_entry_ev_support_repair_listwise_cluster_diagnostics.py`
- Baseline best scenario:
  - `data/reports/backtests/20260702_230305_20260703_entry_ev_00334_support_repair_listwise_cluster_best_s1/`
- Looser EV -2 scenario:
  - `data/reports/backtests/20260702_230314_20260703_entry_ev_00334_support_repair_listwise_cluster_evm2_s1/`

## Implementation

The diagnostic reconstructs the stateful pre-selection candidate surface from:

```text
broad_prior_horizon_choice_additions.csv
broad_prior_horizon_choice_rejections.csv
```

Default included rejection reasons:

```text
quota_full, overlap
```

This excludes prefilter failures such as `pred_pnl_floor` and `tail_prob_ceiling`.

For each scenario, the script applies the same structural constraints as support repair:

```text
quota columns: scenario_label, role, month, side
overlap columns: role
```

It then compares selector families:

```text
current_replay
repair_score_greedy
actual_oracle_greedy
pred_pnl_greedy
harmful_low_greedy
tail_low_greedy
support_proxy_high_greedy
```

`actual_oracle_greedy` uses realized PnL and is diagnostic upper-bound / teacher design only. It is not policy evidence.

Outputs:

```text
support_repair_listwise_candidate_examples.csv
support_repair_listwise_selector_summary.csv
support_repair_listwise_cluster_summary.csv
support_repair_listwise_quota_group_summary.csv
config.json
```

## Results

Baseline best scenario:

```text
available_candidates_p0p45_ev2_tail0p3_reqmodel_ranker_pnl
```

Selector summary:

| selector | selected | actual sum | actual min | loss count | harmful mean | delta vs current |
|---|---:|---:|---:|---:|---:|---:|
| current replay | `5` | `+63.9770` | `+2.9340` | `0` | `0.2593` | `0.0000` |
| repair score greedy | `5` | `+63.9770` | `+2.9340` | `0` | `0.2593` | `0.0000` |
| actual oracle greedy | `5` | `+66.6130` | `+5.5700` | `0` | `0.2593` | `+2.6360` |
| predicted PnL greedy | `5` | `+60.8530` | `+0.3400` | `0` | `0.2593` | `-3.1240` |
| harmful low greedy | `5` | `+33.2530` | `+0.3400` | `0` | `0.1496` | `-30.7240` |
| tail low greedy | `5` | `+25.7830` | `-13.0200` | `1` | `0.3192` | `-38.1940` |
| support proxy high greedy | `5` | `+25.8630` | `-13.0200` | `1` | `0.3192` | `-38.1140` |

Quota group summary:

| role | month | side | rows | quota | current actual | oracle actual | repair actual | harmful-low actual | oracle delta |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| refit2025_validation | 2025-08 | short | `22` | `1` | `+2.9340` | `+5.5700` | `+2.9340` | `+0.3400` | `+2.6360` |
| refit2025_validation | 2025-07 | short | `2` | `1` | `+26.4000` | `+26.4000` | `+26.4000` | `+4.6900` | `0.0000` |
| refit2025_validation | 2025-08 | long | `3` | `1` | `+13.2500` | `+13.2500` | `+13.2500` | `+12.7200` | `0.0000` |
| hybrid2025_0912_external | 2025-11 | short | `3` | `1` | `+10.4400` | `+10.4400` | `+10.4400` | `+4.5500` | `0.0000` |
| hybrid2025_0912_external | 2025-10 | long | `1` | `1` | `+10.9530` | `+10.9530` | `+10.9530` | `+10.9530` | `0.0000` |

Interpretation:

- Current `repair_score` already recovers the same greedy selection under the replay constraints.
- The only listwise replacement target in the baseline best surface is `refit2025 2025-08 short`, worth `+2.6360`.
- This is not enough to solve `month_pnl_below_floor`, `role_trades_low`, or `side_share_high`.
- Low harmful / low tail / high support proxy are not useful direct selectors.

EV -2 scenario:

```text
available_candidates_p0p45_evm2_tail0p3_reqmodel_ranker_pnl
```

Selector summary:

| selector | selected | actual sum | actual min | loss count | harmful mean | delta vs current |
|---|---:|---:|---:|---:|---:|---:|
| current replay | `6` | `+34.8410` | `-29.1360` | `1` | `0.2172` | `0.0000` |
| repair score greedy | `6` | `+34.8410` | `-29.1360` | `1` | `0.2172` | `0.0000` |
| actual oracle greedy | `6` | `+57.1600` | `-29.1360` | `1` | `0.1496` | `+22.3190` |
| predicted PnL greedy | `6` | `+31.7170` | `-29.1360` | `1` | `0.2172` | `-3.1240` |
| harmful low greedy | `6` | `-36.5950` | `-29.1720` | `2` | `0.0521` | `-71.4360` |
| tail low greedy | `6` | `-38.1920` | `-29.1360` | `3` | `0.1753` | `-73.0330` |
| support proxy high greedy | `6` | `-0.9260` | `-29.1360` | `1` | `0.1755` | `-35.7670` |

Quota group summary highlights:

| role | month | side | rows | quota | current actual | oracle actual | oracle delta |
|---|---|---|---:|---:|---:|---:|---:|
| hybrid2025_0912_external | 2025-11 | short | `6` | `1` | `+10.4400` | `+23.3330` | `+12.8930` |
| refit2025_validation | 2025-08 | short | `72` | `1` | `+2.9340` | `+12.3600` | `+9.4260` |
| fresh2024_validation | 2024-08 | long | `1` | `1` | `-29.1360` | `-29.1360` | `0.0000` |

Interpretation:

- EV -2 reveals a richer listwise target in refit/hybrid months.
- However, it also admits the known bad fresh2024 2024-08 long trade.
- That bad trade has no local alternative in the post-filter quota group, so reranking cannot fix it.
- The missing capability is broader candidate generation or abstention for unsupported fresh/thin months, not just a better selector.

## Decision

Accepted:

- stateful pre-selection listwise candidate reconstruction
- quota-aware and one-position-aware greedy selector diagnostics
- interval cluster IDs for candidate-level listwise examples
- actual-oracle diagnostic target for teacher design

Rejected as current policy:

- `actual_oracle_greedy` as policy evidence
- `harmful_low_greedy`
- `tail_low_greedy`
- `support_proxy_high_greedy`
- EV -2 loosening without a fresh/thin-month abstention or candidate-generation fix

Standard policy remains NoTrade.

## Next

1. Turn the listwise examples into a training target:
   - predict `actual_oracle_greedy_selected` / high actual rank inside quota group
   - use chronological splits only
   - keep actual labels out of runtime features
2. Add a candidate-generation / abstention layer for thin fresh months:
   - avoid selecting the only available weak candidate just to satisfy support
   - require support repair to improve month/role floor, not only trade count
3. Diagnose the EV -2 positive oracle rows:
   - `hybrid2025_0912_external 2025-11 short`
   - `refit2025_validation 2025-08 short`
4. Keep harmful probability as a calibrated feature, not as a direct sorting key.
5. Continue using 00329 low-complexity horizon-ranker baseline as the diagnostic benchmark.

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_support_repair_listwise_cluster_diagnostics.py tests/test_entry_ev_support_repair_listwise_cluster_diagnostics.py`: OK
- `uv run python -m unittest tests.test_entry_ev_support_repair_listwise_cluster_diagnostics`: OK
- baseline best listwise cluster diagnostics: OK
- EV -2 listwise cluster diagnostics: OK
