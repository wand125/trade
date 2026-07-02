# Entry EV Overlay Residual Floor Diagnostics

日時: 2026-07-02 13:50 JST
更新日時: 2026-07-02 13:50 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00293で残ったsmall negative monthsを、追加blacklistではなくsupport / side concentration / fixed-horizon rescueの観点で診断した。
- `scripts/experiments/entry_ev_overlay_residual_floor_diagnostics.py` を追加し、entry-block overlay tradesとmonthly metricsから、unblocked tradesだけを対象に残存floor breachを抽出できるようにした。
- best 00293 branchのnegative monthsは4件で、そのうち3件は1 trade monthかつside share `1.0`。
- 残りのrefit2025 2025-03は9 trades / PnL `-0.4730` で、loss 4件のうち2件はfixed horizonで救えるが、主損失のshort down_normal_vol/ny_overlapはfixed 60/240/720mでさらに悪化した。
- 判断: residual floor diagnosticsはaccepted infrastructure。残った負け月を単発blacklistで追わない。標準policyはNoTrade。

## Artifacts

- New script:
  - `scripts/experiments/entry_ev_overlay_residual_floor_diagnostics.py`
- New test:
  - `tests/test_entry_ev_overlay_residual_floor_diagnostics.py`
- Diagnostic run:
  - `data/reports/backtests/20260702_045028_20260702_entry_ev_overlay_residual_floor_diagnostics_s2/`

Input branch:

```text
loss_exit30_cd15__holdext_isolated_large_loss_long_t-5_h720__entryblock_short_rollover_or_london_midloss_or_holdext_range_ny
```

## Results

Diagnostic summary:

| metric | value |
|---|---:|
| total PnL | `+329.4348` |
| trade count | `232` |
| negative month count | `4` |
| single-trade negative months | `3` |
| thin negative months | `3` |
| side-share-high negative months | `3` |
| negative loss trades | `7` |
| fixed-best improved negative loss trades | `5` |

Negative month summary:

| role | month | pnl | trades | loss trades | support reading | fixed-horizon reading |
|---|---|---:|---:|---:|---|---|
| hybrid2025_0912_external | 2025-11 | `-0.7200` | `1` | `1` | single trade / side share `1.0` | best hindsight fixed `720m`, delta `+31.9000` |
| fresh2024_validation | 2024-11 | `-0.6120` | `1` | `1` | single trade / side share `1.0` | best hindsight fixed `720m`, delta `+43.4820` |
| refit2025_validation | 2025-03 | `-0.4730` | `9` | `4` | not thin by month count | mixed; 2 losses rescued, main short worsens |
| fresh2024_validation | 2024-03 | `-0.3636` | `1` | `1` | single trade / side share `1.0` | best hindsight fixed `720m`, delta `+23.7136` |

Important details:

- The three 1-trade negative months are too sparse to justify a new static block. They are better treated as admission/support uncertainty.
- Fixed 720m would rescue the three 1-trade losses in hindsight, but that is not executable policy evidence by itself.
- In refit2025 2025-03, the worst remaining loss is short `down_normal_vol / ny_overlap`, PnL `-2.3400`; fixed 60/240/720m deltas are all negative (`-10.5240`, `-8.9040`, `-15.7800`), so hold-extension is the wrong repair there.
- Context-level removal is not stable enough: e.g. `short|down_normal_vol|ny_overlap` is positive overall at `+19.5636`, even though it contains the remaining refit loss.

## Decision

Accepted:

- overlay residual floor diagnostics infrastructure
- unblocked-trade-only residual analysis for entry-block overlays
- support/side concentration flags for remaining floor breaches

Rejected:

- chasing remaining one-trade negative months with new blacklist rules
- treating hindsight fixed-horizon rescue as executable policy evidence
- blocking broad contexts that are positive overall only because they contain a residual losing trade

Standard policy remains NoTrade.

## Next

1. Shift the next iteration from more entry-block rules to support-aware admission diagnostics.
2. Keep the 00293 combo branch as a diagnostic benchmark, not a standard policy.
3. If fixed-horizon rescue is pursued, it must go through chronological prediction/selector replay rather than hindsight deltas.
4. Investigate whether selector gates should explicitly distinguish "floor breach from one-trade support" from "floor breach from repeated structural loss".

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_overlay_residual_floor_diagnostics.py tests/test_entry_ev_overlay_residual_floor_diagnostics.py`: OK
- `uv run python -m unittest tests.test_entry_ev_overlay_residual_floor_diagnostics`: OK
- overlay residual floor diagnostics run: OK
