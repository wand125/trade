# Entry EV Thin Month Opposite Candidates

日時: 2026-07-02 20:12 JST
更新日時: 2026-07-02 20:12 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00317の次アクションとして、thin monthに反対側candidateがprediction rows上に存在するかを診断した。
- `scripts/experiments/entry_ev_thin_month_opposite_candidate_diagnostics.py` を追加し、repair target、現行trade interval、prediction parquetを突き合わせた。
- strict条件では、8 repair target中 `refit2025_validation 2025-08 short` の1件しか埋まらない。
- `one_failed_strict_stage` まで緩めると8 targetすべてに候補は存在するが、8本合計のfixed60実現は `-17.7984`、fixed240は `-31.7138`、fixed720は `-80.4158`。oracle bestだけは `+86.0590`。
- fresh2024の3ヶ月は主にscore floor `5` 未満のnear-missで、fixed60では `-14.1240`, `-11.0604`, `+0.3000`。supportを埋めるためにfloorを下げるのは危険。
- 判断: thin-month opposite candidate diagnosticsはaccepted infrastructure。side-balanced support overlayはまだ標準候補にしない。次はnear-miss support candidate用のexit timing / EV calibration targetを作る。

## Artifacts

- New script:
  - `scripts/experiments/entry_ev_thin_month_opposite_candidate_diagnostics.py`
- New tests:
  - `tests/test_entry_ev_thin_month_opposite_candidate_diagnostics.py`
- Final runs:
  - strict/standard-relaxed: `data/reports/backtests/20260702_111114_20260702_entry_ev_00318_thin_month_opposite_candidates_00314_w5_s2/`
  - loose coverage audit: `data/reports/backtests/20260702_111134_20260702_entry_ev_00318_thin_month_opposite_candidates_loose_00314_w5_s2/`

## Method

Target branch:

```text
00314 fixed60_margin_w5
candidate = q95_sg95_rank90_floor5_side_regime_session_month
selector_variant contains loss_exit30_cd15__holdext_isolated_large_loss_long_t-5_h720
entry_block_rule = long_range_normal_ny_fixed60_pred_gt0
```

For each 00317 repair target side:

1. Load prediction rows for the same family/month.
2. Expand rows into side-specific long/short rows.
3. Apply the same short side EV penalty rule:
   `short:entryblock_short_rollover_or_london_midloss=true:1000000`
4. Recompute side-specific quantiles by `month + side + combined_regime + session_regime`.
5. Exclude rows whose decision interval overlaps the current selected trade path.
6. Greedily select up to the required extra side count, avoiding overlap among added candidates.

Buckets:

| bucket | definition |
|---|---|
| strict | q95 score, q95 side-margin, rank90, score floor `5`, holding `30..720m`, side margin `>=0` |
| relaxed | q90 score, q90 side-margin, rank80, score floor `5`, side margin `>=0` |
| one-failed strict | exactly one strict condition fails |
| loose audit | relaxed score q80 / rank50 / no side-margin requirement, diagnostic only |

PnL columns are labels for diagnosis. `side_best_adjusted_pnl` is an oracle upper bound and must not be treated as executable policy evidence.

## Main Results

Standard strict/relaxed run:

| role | month | needed side | strict selected | relaxed selected | one-fail selected | one-fail fixed60 | one-fail fixed240 | one-fail fixed720 | one-fail oracle best |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| `fresh2024_validation` | `2024-03` | long | `0` | `0` | `1` | `-14.1240` | `-3.5280` | `-10.3440` | `+1.7500` |
| `fresh2024_validation` | `2024-08` | long | `0` | `0` | `1` | `-11.0604` | `+3.1230` | `-21.7452` | `+7.3500` |
| `fresh2024_validation` | `2024-11` | long | `0` | `0` | `1` | `+0.3000` | `+2.4500` | `-5.2800` | `+6.0200` |
| `hybrid2025_0912_external` | `2025-10` | long | `0` | `0` | `1` | `+1.3200` | `-9.2880` | `+13.5100` | `+31.2700` |
| `hybrid2025_0912_external` | `2025-11` | short | `0` | `0` | `1` | `+0.8200` | `-8.9760` | `-39.9600` | `+6.0800` |
| `refit2025_validation` | `2025-07` | short | `0` | `0` | `1` | `-2.4240` | `-20.3448` | `-45.4596` | `+0.7200` |
| `refit2025_validation` | `2025-08` | long | `0` | `1` | `1` | `+6.5200` | `+3.6500` | `+13.7800` | `+16.6000` |
| `refit2025_validation` | `2025-08` | short | `1` | `1` | `1` | `+0.8500` | `+1.2000` | `+15.0830` | `+16.2690` |

Aggregates for one-fail greedy additions:

| selected trades | fixed60 | fixed240 | fixed720 | oracle best |
|---:|---:|---:|---:|---:|
| `8` | `-17.7984` | `-31.7138` | `-80.4158` | `+86.0590` |

Reading:

- Support count can be filled only by weakening the strict policy surface.
- The gap between oracle best and fixed horizons is very large, so this is not an entry-only problem.
- The fresh2024 support candidates are especially dangerous under short fixed horizons.

## Failure Stage

The fresh2024 one-fail candidates failed only score floor:

| month | selected score | failed strict stage | fixed60 | oracle best |
|---|---:|---|---:|---:|
| `2024-03` | `2.6428` | score floor `5` | `-14.1240` | `+1.7500` |
| `2024-08` | `3.2124` | score floor `5` | `-11.0604` | `+7.3500` |
| `2024-11` | `2.5148` | score floor `5` | `+0.3000` | `+6.0200` |

This is a useful signal for a target, not a reason to lower the entry floor.

## Decision

Accepted:

- thin-month opposite candidate diagnostics
- side-specific quantile reconstruction for repair target sides
- stateful availability / greedy non-overlap diagnostic
- one-fail strict bucket as a near-miss error-analysis surface

Rejected:

- lowering score floor just to fill side/support repair targets
- treating oracle best PnL of near-miss rows as executable policy evidence
- promoting side-balanced support overlay before exit timing / EV calibration is solved

Standard policy remains NoTrade.

## Next

1. Build an exit timing target for near-miss support candidates: distinguish rows whose fixed60/fixed240/fixed720 path is viable from rows that only look good under oracle best.
2. Use one-fail strict rows as a candidate pool for training/diagnostics, not as immediate entries.
3. Add a side-balanced support overlay only after it can choose exit timing without using oracle labels.
4. Keep repair target and fixed-horizon sensitivity in the gate: support repair that worsens month floor is not progress.

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_thin_month_opposite_candidate_diagnostics.py tests/test_entry_ev_thin_month_opposite_candidate_diagnostics.py`: OK
- `uv run python -m unittest tests.test_entry_ev_thin_month_opposite_candidate_diagnostics`: OK
- `uv run python -m unittest tests.test_entry_ev_thin_month_opposite_candidate_diagnostics tests.test_docs_reports`: OK
- `git diff --check`: OK
- 00318 thin-month opposite candidate diagnostics runs: OK
