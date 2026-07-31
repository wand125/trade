# Entry EV Stateful Floor Meta Selector

日時: 2026-07-02 12:07 JST
更新日時: 2026-07-02 12:07 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00285の結論どおり、score arithmeticを止め、candidate-levelで stateful month/role floor を明示的に評価する横断selector診断を追加した。
- `scripts/experiments/entry_ev_stateful_floor_meta_selector.py` は複数runの `monthly_exit_timing_metrics.csv` を同一sourceへ結合し、candidate単位で total PnL、role min、month min、trade support、side share、floor-aware utilityを集計する。
- raw cd15 baseline、downside hard block、downside soft margin、supervised shrinkage replacement / quantile sweepを同じselectorで比較した。
- 結果: strict gateを通る候補はなし。floor-only条件でも候補はなし。最上位は raw cd15 baseline と downside `gte3` no-opで、どちらも total `+118.6900`, role min `+0.0074`, month min `-6.8324`。
- 判断: candidate-level selectorはaccepted infrastructure。現候補群では標準policyはNoTrade。次は新しいscore変換ではなく、month floorの主因月を対象に、entryを消すのではなくexit-capture / cooldown / post-exit re-entry pathを改善する。

## Artifacts

- Script:
  - `scripts/experiments/entry_ev_stateful_floor_meta_selector.py`
- Test:
  - `tests/test_entry_ev_stateful_floor_meta_selector.py`
- Selector runs:
  - `data/reports/backtests/20260702_030632_20260702_entry_ev_stateful_floor_meta_selector_downside_family_s1/`
  - `data/reports/backtests/20260702_030656_20260702_entry_ev_stateful_floor_meta_selector_floor_only_s1/`

## Method

Candidate summary:

```text
group = source + variant + candidate
total_pnl = sum(monthly total_adjusted_pnl)
role_total_pnl_min = min(sum monthly pnl by role)
month_pnl_min = min(monthly pnl)
support = role_trade_count_min, month_trade_count_min
side risk = max(overall side trade share, observed monthly max side share)
```

Strict gates:

```text
total_pnl >= 0
role_total_pnl_min >= 0
month_pnl_min >= 0
role_trade_count_min >= 4
month_trade_count_min >= 1
observed_max_side_trade_share <= 0.95
```

Diagnostic utility:

```text
floor_aware_utility =
  total_pnl
  - 25 * role_floor_breach
  - 15 * month_floor_breach
  - 5  * support_shortfall
```

The selector still returns NoTrade unless strict gates pass. Utility is used only to rank failed candidates and prevent total-only rescue.

## Main Selector Result

Compared sources:

- raw cd15 baseline
- downside hard block `gte1`, `gte3`
- downside soft margin `w0.1`, `w0.25`, `w0.5`, `w1`, `w2`, `w5`, `w10`
- supervised shrinkage replacement and q96-q99 sweep

Top rows:

| source | variant | candidate | pass | total | role min | month min | trades | utility | blockers |
|---|---|---|---:|---:|---:|---:|---:|---:|---|
| downside_block_gte3 | loss_exit30_cd15 | q95 floor5 | false | `+118.6900` | `+0.0074` | `-6.8324` | `266` | `+6.2040` | month/support/side |
| raw_cd15_baseline | loss_exit30_cd15 | q95 floor5 | false | `+118.6900` | `+0.0074` | `-6.8324` | `266` | `+6.2040` | month/support/side |
| supervised_shrinkage_replacement | loss_exit30_cd15 | q95 no-floor | false | `+219.7158` | `0.0000` | `-35.1586` | `899` | `-332.6632` | month/support/side |
| supervised_shrinkage_quantile_sweep | loss_exit30_cd15 | q96 no-floor | false | `+192.4624` | `0.0000` | `-38.1026` | `840` | `-404.0766` | month/support/side |
| margin_w0p5 | loss_exit30_cd15 | q95 floor5 | false | `+21.7298` | `-0.2120` | `-8.4858` | `178` | `-135.8572` | role/month/support/side |
| margin_w1 | loss_exit30_cd15 | q95 floor5 | false | `+18.9676` | `-3.9590` | `-5.6864` | `160` | `-190.3034` | role/month/support/side |

Reading:

- The selector correctly refuses the high-total supervised shrinkage candidates because their month floor collapse is much worse.
- The best candidate under floor-aware ranking is still raw cd15 baseline, tied with `gte3` because `gte3` was no-op.
- All score replacement / margin paths fall below raw baseline once role/month floors are explicit.

## Floor-Only Audit

Relaxed support and side gates:

```text
min_role_trades = 0
min_month_trades = 0
max_side_trade_share = 1.0
```

Top rows:

| source | total | role min | month min | blockers |
|---|---:|---:|---:|---|
| downside_block_gte3 | `+118.6900` | `+0.0074` | `-6.8324` | month_pnl_below_floor |
| raw_cd15_baseline | `+118.6900` | `+0.0074` | `-6.8324` | month_pnl_below_floor |
| supervised_shrinkage_replacement q95 no-floor | `+219.7158` | `0.0000` | `-35.1586` | month_pnl_below_floor |
| supervised_shrinkage_quantile_sweep q96 | `+192.4624` | `0.0000` | `-38.1026` | month_pnl_below_floor |

Reading:

- Even if support and side-balance gates are relaxed, no candidate passes.
- The blocker that survives every relaxation is month floor.
- Therefore the next improvement target is not more score gating; it is changing the stateful path in the specific losing months without deleting the profitable role/month exposure.

## Decision

Accepted:

- stateful floor meta selector infrastructure
- multi-run source merging for fair candidate comparison
- floor-aware utility as diagnostic ranking only

Rejected:

- selecting any current candidate as standard policy
- rescuing high-total supervised shrinkage candidates without fixing month floor
- further direct score arithmetic based on downside meta as the next main line

Standard policy remains NoTrade.

Raw `loss_exit30_cd15` remains the fixed diagnostic benchmark and the best failed candidate.

## Next

1. Focus on raw cd15 losing months, especially refit2025 2025-09/06/02 and hybrid2025 2025-12.
2. Preserve raw entry score/side and diagnose stateful path changes: dynamic exit timing, cooldown after loss-first exits, and post-exit re-entry quality.
3. Use candidate-level selector only after a path-changing intervention produces positive role min and non-negative month floor.
4. Keep supervised shrinkage/downside meta as diagnostic features, not direct score transforms.

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_stateful_floor_meta_selector.py tests/test_entry_ev_stateful_floor_meta_selector.py`: OK
- `uv run python -m unittest tests.test_entry_ev_stateful_floor_meta_selector`: OK
- stateful floor selector run on baseline / hard block / margin / supervised shrinkage candidates: OK
- floor-only audit run: OK
