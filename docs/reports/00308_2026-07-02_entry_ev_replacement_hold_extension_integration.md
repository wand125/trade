# Entry EV Replacement Hold-Extension Integration

日時: 2026-07-02 16:51 JST
更新日時: 2026-07-02 16:51 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00307の次アクションとして、short entry-block replacement後のtrade pathへhold-extension target / stateful replayを戻した。
- `entry_ev_hold_extension_stateful_replay.py` に `--require-model-used` を追加し、chronological modelが実際に使われたhorizonだけをhold-extension対象にできるようにした。
- 00307 replacement raw pathは total `+126.8118` / 254 trades / month min `-6.8324`。
- `--require-model-used` なしの `isolated_large_loss_long / threshold -5 / fixed720` は total `+307.7638` まで伸びるが、hgb2024_0306 2024-03が `-17.6936` へ壊れた。
- 原因は replacementで生じた hgb2024_0306 2024-03のlong tradeが、`pred_hold_extension_model_used_720m=False` のfallback score `+0.4951` でfixed720延長され、`-2.0400 -> -20.1840` になったこと。
- `--require-model-used` を入れると、同じ `isolated_large_loss_long / threshold -5 / fixed720` は total `+326.1098` / 246 trades / month min `-0.8832` / role min `+0.5354` まで改善した。
- さらに `holdext_long_range_normal_ny` no-replacement blockを重ねると total `+326.9930` / 245 trades / month min `-0.7200` / role min `+0.5354`。00293 bestの `+329.4348` / month min `-0.7200` よりtotalは `-2.4418` 低いが、short blockは削除ではなくreplacement pathで処理できた。
- 判断: `require_model_used` replay hookはaccepted infrastructure。replacement + hold-extension integrationはdiagnostic candidateへ昇格。ただし `holdext_long_range_normal_ny` は依然no-replacement post-hold blockで、standard policyはNoTrade。

## Artifacts

- Updated script:
  - `scripts/experiments/entry_ev_hold_extension_stateful_replay.py`
- Updated tests:
  - `tests/test_entry_ev_hold_extension_stateful_replay.py`
- Replacement trade enrichment:
  - internal+hgb: `data/reports/backtests/20260702_074614_20260702_entry_ev_short_entryblock_replacement_internal_hgb_enrichment_s1/`
  - hybrid: `data/reports/backtests/20260702_074624_20260702_entry_ev_short_entryblock_replacement_hybrid_enrichment_s1/`
- Replacement path diagnostics:
  - isolated exit capture: `data/reports/backtests/20260702_074635_20260702_entry_ev_short_entryblock_replacement_isolated_exit_capture_s1/`
  - hold-extension target: `data/reports/backtests/20260702_074705_20260702_entry_ev_short_entryblock_replacement_hold_extension_target_s1/`
  - stateful hold-extension without model-used guard: `data/reports/backtests/20260702_074716_20260702_entry_ev_short_entryblock_replacement_hold_extension_stateful_s1/`
  - post-hold block overlay without model-used guard: `data/reports/backtests/20260702_074738_20260702_entry_ev_short_entryblock_replacement_holdext_block_overlay_s1/`
  - stateful hold-extension with model-used guard: `data/reports/backtests/20260702_075031_20260702_entry_ev_short_entryblock_replacement_hold_extension_stateful_reqmodel_s1/`
  - post-hold block overlay with model-used guard: `data/reports/backtests/20260702_075050_20260702_entry_ev_short_entryblock_replacement_holdext_reqmodel_block_overlay_s1/`

## Method

Pipeline:

```text
00307 replacement trades
-> multifamily policy trade enrichment
-> isolated exit-capture feature regeneration
-> chronological hold-extension target model
-> stateful hold-extension replay
-> optional post-hold holdext false-positive block overlay
```

New guard:

```text
--require-model-used
```

When enabled, a candidate extension is allowed only if the horizon-specific column is true:

```text
pred_hold_extension_model_used_{horizon}m == true
```

This prevents fallback / insufficient-history mean predictions from opening an aggressive fixed-horizon extension.

## Result

| path | total PnL | trades | month min | role min | note |
|---|---:|---:|---:|---:|---|
| 00307 raw replacement | `+126.8118` | `254` | `-6.8324` | `+0.5354` | short block replacement only |
| replacement + holdext, no model-used guard, `long t-5 h720` | `+307.7638` | `244` | `-17.6936` | `+0.5354` | fallback extension tail |
| replacement + holdext, require model-used, `long t-5 h720` | `+326.1098` | `246` | `-0.8832` | `+0.5354` | 8 extensions / 8 skipped |
| require model-used + `holdext_long_range_normal_ny` block | `+326.9930` | `245` | `-0.7200` | `+0.5354` | 1 post-hold block |
| 00293 no-replacement combo reference | `+329.4348` | `232` | `-0.7200` | `+0.5354` | 24 blocked trades |

Reading:

- The integration nearly reproduces 00293's floor while preserving the short replacement idea from 00307.
- The remaining gap versus 00293 is small in total PnL, but the execution semantics differ: 00308 replaces short-block contexts first, then blocks only one hold-extension false positive.
- The current branch still fails strict standard admission because month min remains negative and max side share/support blockers remain.

## Failure Analysis

The no-guard fixed720 branch failed in hgb2024_0306 2024-03:

| item | value |
|---|---:|
| replacement trade direction | `long` |
| context | `range_normal_vol / london` |
| base adjusted PnL | `-2.0400` |
| fixed720 actual PnL | `-20.1840` |
| fixed720 delta | `-18.1440` |
| `pred_hold_extension_model_used_720m` | `False` |
| fallback fixed720 score | `+0.4951` |

This explains why `threshold -5` was too permissive after replacement. It allowed a non-model fallback score to drive a large fixed720 loss.

## Best Branch Worst Months

For:

```text
loss_exit30_cd15__holdext_isolated_large_loss_long_t-5_h720__entryblock_holdext_long_range_normal_ny
```

Worst months:

| source | role | family | month | PnL | trades | note |
|---|---|---|---|---:|---:|---|
| replacement_hybrid | hybrid2025_0912_external | hybrid2025_0912 | `2025-11` | `-0.7200` | `1` | sparse residual |
| replacement_internal_hgb | fresh2024_validation | fresh2024 | `2024-11` | `-0.6120` | `1` | sparse residual |
| replacement_internal_hgb | refit2025_validation | refit2025 | `2025-03` | `-0.4730` | `9` | unchanged residual |
| replacement_internal_hgb | fresh2024_validation | fresh2024 | `2024-03` | `-0.3636` | `1` | sparse residual |
| replacement_internal_hgb | refit2025_validation | refit2025 | `2025-08` | `0.0000` | `0` | one holdext false positive blocked |

Reading:

- The remaining month floor is now the same sparse-tail structure as 00293, not the raw cd15 structural floor.
- `refit2025 2025-09` and `2025-02` are no longer the floor after require-model-used fixed720 extension.

## Decision

Accepted:

- `--require-model-used` in stateful hold-extension replay
- replacement path -> enrichment -> isolated/capture -> hold target -> stateful replay pipeline
- replacement + require-model-used hold-extension as a diagnostic candidate

Rejected:

- allowing fallback hold-extension predictions to drive aggressive fixed720 extension
- treating 00307 replacement-only total improvement as sufficient
- treating the current post-hold `holdext_long_range_normal_ny` block as fully executable entry-time policy

Standard policy remains NoTrade.

## Next

1. Convert `holdext_long_range_normal_ny` from a post-hold no-replacement block into an execution-time proxy or a model-used-aware extension veto.
2. Add selector/admission diagnostics for the 00308 branch, including support-aware classification and strict NoTrade-first blockers.
3. Diagnose remaining sparse negative months without broad month-warmup or confidence hard gate.
4. Keep `--require-model-used` enabled for aggressive hold-extension thresholds.

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_hold_extension_stateful_replay.py tests/test_entry_ev_hold_extension_stateful_replay.py`: OK
- `uv run python -m unittest tests.test_entry_ev_hold_extension_stateful_replay tests.test_docs_reports`: OK
- `git diff --check`: OK
- replacement path enrichment runs: OK, prediction match share `1.0`
- replacement isolated exit-capture diagnostics run: OK
- replacement hold-extension target run: OK
- stateful hold-extension replay with and without model-used guard: OK
- post-hold block overlay with and without model-used guard: OK
