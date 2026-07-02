# Entry EV Hold-Extension Veto Diagnostics

日時: 2026-07-02 17:08 JST
更新日時: 2026-07-02 17:08 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00308の次アクションとして、00308 branchをsupport-aware admissionで再評価し、`holdext_long_range_normal_ny` をpost-hold no-replacement blockから実行時extension vetoへ戻せるか検証した。
- `scripts/experiments/entry_ev_hold_extension_stateful_replay.py` に `--extension-veto-rules` を追加した。
- `holdext_long_range_normal_ny` extension vetoは、延長判断時点で `long + range_normal_vol + ny_overlap + horizon>=720` を満たす延長だけを止める。
- 00308 bestのpost-hold block branchは default support-awareでは `support_aware_only` だが、support2 / shallow025感度ではblocked。標準policyはNoTradeのまま。
- extension vetoは実行可能な形ではあるが、対象tradeはbase exit `-2.5152`、720m延長 `-0.8832` だったため、延長を止めると total `+326.1098 -> +325.2078`、month min `-0.8832 -> -1.7852` へ悪化した。
- 判断: extension veto hookとoverlayの `extension_veto_rule` groupingはaccepted infrastructure。ただし `holdext_long_range_normal_ny` vetoはpost-hold blockの代替としてreject。

## Artifacts

- Updated scripts:
  - `scripts/experiments/entry_ev_hold_extension_stateful_replay.py`
  - `scripts/experiments/entry_ev_stateful_entry_block_overlay.py`
- Updated tests:
  - `tests/test_entry_ev_hold_extension_stateful_replay.py`
  - `tests/test_entry_ev_stateful_entry_block_overlay.py`
- 00308 support-aware diagnostics:
  - default: `data/reports/backtests/20260702_080331_20260702_entry_ev_00308_support_aware_default_s1/`
  - support2: `data/reports/backtests/20260702_080331_20260702_entry_ev_00308_support_aware_support2_s1/`
  - shallow025: `data/reports/backtests/20260702_080331_20260702_entry_ev_00308_support_aware_shallow025_s1/`
- Extension veto replay:
  - `data/reports/backtests/20260702_080552_20260702_entry_ev_short_entryblock_replacement_hold_extension_stateful_reqmodel_veto_s1/`
- Extension veto support-aware:
  - `data/reports/backtests/20260702_080624_20260702_entry_ev_00309_veto_support_aware_default_s1/`
- Veto replay -> block overlay check:
  - `data/reports/backtests/20260702_080749_20260702_entry_ev_00309_veto_block_overlay_s1/`

## Method

New replay option:

```text
--extension-veto-rules none,holdext_long_range_normal_ny
```

`holdext_long_range_normal_ny` veto:

```text
direction == long
AND combined_regime == range_normal_vol
AND session_regime == ny_overlap
AND proposed horizon >= 720m
```

This is deliberately different from the 00308 post-hold block:

```text
post-hold block: remove the whole trade after seeing the extended path
extension veto: keep the base trade, but do not extend it
```

The latter is closer to an executable exit-time decision.

## Admission Result

00308 best branch:

| check | status | total | month min | support-limited neg | shallow neg | structural neg | blockers |
|---|---|---:|---:|---:|---:|---:|---|
| default | `support_aware_only` | `+326.9930` | `-0.7200` | `3` | `1` | `0` | strict: month/role/month-trade/side-share |
| support2 | `blocked` | `+326.9930` | `-0.7200` | `3` | `1` | `0` | too many support-limited negative months |
| shallow025 | `blocked` | `+326.9930` | `-0.7200` | `3` | `0` | `1` | structural negative months |

Reading:

- 00308 is not structurally worse than 00296 residual combo, but it has the same sensitivity problem.
- Default support-aware pass remains diagnostic only. It is not standard admission.

## Veto Result

Key comparison for `isolated_large_loss_long / threshold -5 / fixed720`:

| branch | total | month min | role min | trades | extended | vetoed | skipped | skipped PnL |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| no veto | `+326.1098` | `-0.8832` | `+0.5354` | `246` | `8` | `0` | `8` | `-3.9820` |
| `holdext_long_range_normal_ny` veto | `+325.2078` | `-1.7852` | `+0.5354` | `247` | `7` | `1` | `7` | `-4.7120` |
| no veto + post-hold block | `+326.9930` | `-0.7200` | `+0.5354` | `245` | n/a | n/a | n/a | n/a |

The vetoed trade:

| item | value |
|---|---:|
| source / role | `replacement_internal_hgb / refit2025_validation` |
| month | `2025-08` |
| entry | `2025-08-07 15:43:00+00:00` |
| base exit PnL | `-2.5152` |
| fixed720 PnL | `-0.8832` |
| extension delta vs base | `+1.6320` |
| post-hold block effect | `+0.8832` by deleting the whole extended trade |
| extension veto effect | `-1.6320` on that trade, partly offset by one unskipped trade |

Reading:

- The no-replacement block improved PnL because it deleted the entire trade, not because extension was worse than base exit.
- Therefore the executable extension veto is the wrong proxy for this post-hold block.
- This is an important negative result: `holdext_long_range_normal_ny` is not an extension-risk veto; it is an entry/no-entry question that current entry-time features have not justified.

## Decision

Accepted:

- `--extension-veto-rules` replay infrastructure
- `hold_extension_vetoed` / `vetoed_extension_count` diagnostics
- preserving `extension_veto_rule` as an optional grouping key in entry-block overlay
- 00308 support-aware admission rerun as baseline evidence

Rejected:

- `holdext_long_range_normal_ny` extension veto as a replacement for the post-hold no-replacement block
- treating default support-aware pass as standard admission
- using post-hold block evidence as if it proves an executable entry-time block

Standard policy remains NoTrade.

## Next

1. Stop trying to map `holdext_long_range_normal_ny` to an extension veto; it is not the right causal mechanism.
2. Treat the 2025-08 row as an entry/no-entry or position-quality problem, and test only prediction-row observable proxies.
3. Re-run short replacement / hold-extension candidates with strict support-aware and support2/shallow025 sensitivity included by default.
4. Keep `extension_veto_rule` infrastructure for future rules where extended PnL is worse than base exit.

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_hold_extension_stateful_replay.py scripts/experiments/entry_ev_stateful_entry_block_overlay.py tests/test_entry_ev_hold_extension_stateful_replay.py tests/test_entry_ev_stateful_entry_block_overlay.py`: OK
- `uv run python -m unittest tests.test_entry_ev_hold_extension_stateful_replay tests.test_entry_ev_stateful_entry_block_overlay`: OK
- 00308 support-aware default/support2/shallow025 runs: OK
- extension veto stateful replay: OK
- veto replay -> entry-block overlay grouping check: OK
