# Entry EV Fixed60 Margin Trade Set Delta

日時: 2026-07-02 19:04 JST
更新日時: 2026-07-02 19:04 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00314の次アクションとして、w5で消えた/置換されたtradeを00310 referenceと差分比較した。
- `scripts/experiments/entry_ev_trade_set_delta_diagnostics.py` を追加し、entry-block overlay trade setを `added / removed / common_changed / common_same` に分解できるようにした。
- 対象は00310 `position_quality_proxy_overlay` と00314 `fixed60_margin_w5_position_quality_overlay` の同一branch `isolated_large_loss_long / t-5 / h720`。
- 00314 w5は新しいtradeを追加して改善したのではなく、00310にあった少数のrefit2025 tradeを先に落として改善していた。
- `entryblock_none` は `+326.1098 -> +338.4078`、差分 `+12.2980`。内訳はremoved 5本だけで、added 0 / common_changed 0。
- `long_range_normal_ny_fixed60_pred_gt0` は `+337.6010 -> +339.2910`、差分 `+1.6900`。内訳はremoved 2本だけで、added 0 / common_changed 0。
- 00310で同proxyがblockedしていた4本のうち3本は、00314ではw5 margin側で既に候補集合から消えていた。blocked rowは4本から1本へ減ったが、これはposition-quality ruleの汎化改善ではなく、w5がrefit2025の一部を先に落とした結果。
- 判断: trade-set delta diagnosticsはaccepted infrastructure。00314 w5の改善源は理解できたが、refit2025集中は解消していない。標準policyはNoTrade。

## Artifacts

- New script:
  - `scripts/experiments/entry_ev_trade_set_delta_diagnostics.py`
- New tests:
  - `tests/test_entry_ev_trade_set_delta_diagnostics.py`
- Run:
  - `data/reports/backtests/20260702_100322_20260702_entry_ev_00315_trade_set_delta_00310_vs_00314_w5_s1/`

## Method

Comparison target:

```text
left:  00310 position-quality overlay
right: 00314 fixed60 family-aware uncertainty margin w5 overlay
branch filter: isolated_large_loss_long_t-5_h720
rules: none, long_range_normal_ny_fixed60_pred_gt0, holdext_long_range_normal_ny
key: role, family, candidate, direction, entry_decision_timestamp
```

The diagnostic compares kept trades only for final PnL:

```text
added          = right only
removed        = left only
common_changed = same key, different adjusted_pnl
common_same    = same key, same adjusted_pnl
```

Blocked rows are compared separately, because blocked rows explain rule behavior but are not part of final kept PnL.

## Trade Set Delta

| entry block rule | 00310 kept PnL | 00314 kept PnL | delta | 00310 kept | 00314 kept | added | removed | common changed | 00310 blocked | 00314 blocked |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `none` | `+326.1098` | `+338.4078` | `+12.2980` | `246` | `241` | `0` | `5` | `0` | `0` | `0` |
| `long_range_normal_ny_fixed60_pred_gt0` | `+337.6010` | `+339.2910` | `+1.6900` | `242` | `240` | `0` | `2` | `0` | `4` | `1` |
| `holdext_long_range_normal_ny` | `+326.9930` | `+339.2910` | `+12.2980` | `245` | `240` | `0` | `5` | `0` | `1` | `1` |

Reading:

- w5 does not discover replacement winners in this comparison.
- The improvement is selection shrinkage: removing a few 00310 trades.
- Since all common trades have identical PnL, the hold-extension behavior of common trades did not change.

## Removed Rows

Rows removed by w5 from `entryblock_none` / `holdext_long_range_normal_ny`:

| role | month | direction | context | entry decision | 00310 PnL | delta from removal | fixed60 pred | fixed60 actual |
|---|---|---|---|---|---:|---:|---:|---:|
| `refit2025_validation` | `2025-10` | long | `range_normal_vol / ny_overlap` | `2025-10-09 16:21+00:00` | `-2.9880` | `+2.9880` | `+0.9762` | `-8.3520` |
| `refit2025_validation` | `2025-12` | long | `range_normal_vol / ny_overlap` | `2025-12-01 15:05+00:00` | `-7.5480` | `+7.5480` | `+0.5132` | `-9.6960` |
| `refit2025_validation` | `2025-12` | long | `range_normal_vol / ny_overlap` | `2025-12-01 16:02+00:00` | `-0.0720` | `+0.0720` | `+1.2409` | `-10.1880` |
| `refit2025_validation` | `2025-12` | short | `down_normal_vol / asia` | `2025-12-24 06:49+00:00` | `+0.1700` | `-0.1700` | `+0.6942` | `+7.7400` |
| `refit2025_validation` | `2025-12` | short | `down_normal_vol / asia` | `2025-12-31 06:53+00:00` | `-1.8600` | `+1.8600` | `+4.3605` | `-5.9364` |

Net:

```text
long range_normal_vol / ny_overlap removal: +10.6080
short down_normal_vol / asia removal: +1.6900
total removed effect: +12.2980
```

For `long_range_normal_ny_fixed60_pred_gt0`, the three long rows above were already blocked by the 00310 proxy. Therefore the 00314-vs-00310 final delta for this rule is only the two short `down_normal_vol / asia` rows:

```text
+0.1700 winner removed  -> -0.1700
-1.8600 loser removed   -> +1.8600
net                     -> +1.6900
```

## Blocked Row Delta

`long_range_normal_ny_fixed60_pred_gt0` blocked set:

| status | role | month | PnL | reading |
|---|---|---|---:|---|
| blocked common | `refit2025_validation` | `2025-08` | `-0.8832` | remains blocked in both 00310 and 00314 |
| blocked removed | `refit2025_validation` | `2025-10` | `-2.9880` | w5 removed before entry-block overlay |
| blocked removed | `refit2025_validation` | `2025-12` | `-7.5480` | w5 removed before entry-block overlay |
| blocked removed | `refit2025_validation` | `2025-12` | `-0.0720` | w5 removed before entry-block overlay |

Reading:

- The blocked-count improvement `4 -> 1` is not independent support for the position-quality rule.
- It is mostly a consequence of w5 margin removing three of the same refit2025 long rows before the rule is applied.
- This is useful engineering behavior, but it does not solve the holdout-support problem found in 00311.

## Admission Implication

00314 best still has:

```text
standard: blocked
default support-aware: support_aware_only
support2: blocked by too_many_support_limited_negative_months
shallow025: blocked by structural_negative_months
```

The trade-set delta explains why:

- removed rows are all `refit2025_validation`;
- no non-refit trade is newly improved;
- no added replacement winner appears;
- the remaining negative months are still thin/support-limited or shallow.

Therefore the right interpretation is:

```text
fixed60 family-aware w5 is a useful diagnostic score perturbation,
but current evidence is still refit-concentrated and not a standardizable edge.
```

## Decision

Accepted:

- trade-set delta diagnostics infrastructure;
- using `added / removed / common_changed` as a standard audit after score-head changes;
- blocked-row delta as a separate explanation layer;
- 00314 w5 as a diagnostic feature whose improvement source is now understood.

Rejected:

- treating the 00314 `+1.6900` overlay improvement over 00310 as broad generalization evidence;
- treating `blocked count 4 -> 1` as independent support for the position-quality rule;
- promoting family-aware w5 to standard policy without non-refit or support-robust evidence.

Standard policy remains NoTrade.

## Next

1. Reproduce the useful w5 behavior without family/refit-specific leakage: test coarser `direction,combined_regime,session_regime` variants or shrink family-aware priors toward a global prior.
2. Move from hard row removal to calibrated EV uncertainty: compare margin strength against support-aware negative months rather than total PnL.
3. Address the unchanged support blockers directly: support-limited negative months and side-share remain the standard-admission bottleneck.
4. Keep `added/removed/common_changed` audit mandatory for every score-head experiment, because total PnL can hide refit-only row removal.

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_trade_set_delta_diagnostics.py tests/test_entry_ev_trade_set_delta_diagnostics.py`: OK
- `uv run python -m unittest tests.test_entry_ev_trade_set_delta_diagnostics`: OK
- `uv run python -m unittest tests.test_entry_ev_trade_set_delta_diagnostics tests.test_docs_reports`: OK
- `uv run python -m unittest tests.test_entry_ev_fixed60_uncertainty_margin_policy_inputs tests.test_entry_ev_stateful_entry_block_overlay tests.test_entry_ev_stateful_support_aware_admission`: OK
- `git diff --check`: OK
- 00310 vs 00314 w5 trade-set delta run: OK
