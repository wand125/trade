# Entry EV Horizon Reliability Diagnostics

日時: 2026-07-03 10:17 JST
更新日時: 2026-07-03 10:17 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00343の次アクションとして、reliabilityをdirect score multiplierにするのではなく、score modeごとのhorizon選択差分とhead errorを診断するスクリプトを追加した。
- `entry_ev_horizon_reliability_diagnostics.py` は、baseline score modeとの選択差分、悪化case、horizon/head別のprediction error、missing target coverageをCSV化する。
- target subsetでは、`pnl_delta_tail_reliability_gated` はplain `pnl` に対して available candidates合計 `-131.8792` 悪化。`pnl_tail_reliability_gated` も `-87.8104` 悪化。
- all rowsでも同じ傾向で、`pnl_delta_tail_reliability_gated` はavailable candidates合計 `-137.6916`、`pnl_tail_reliability_gated` は `-93.6228` 悪化。
- 主因は、positive reliabilityが「PnL上の正しいhorizon」ではなく、beats60やtail headの限定的な過去識別力をhorizon選択に過剰反映すること。特に60mが相対的にましな局面で240mへ動く失敗が大きい。
- 判断: horizon reliability diagnosticsはaccepted infrastructure。reliabilityはdirect score multiplierではなく、head selection / abstention / confidence report / candidate generation priorityへ回す。標準policyはNoTrade。

## Artifacts

Changed script:

- `scripts/experiments/entry_ev_horizon_reliability_diagnostics.py`

Changed tests:

- `tests/test_entry_ev_horizon_reliability_diagnostics.py`

Runs:

- target subset: `data/reports/backtests/20260703_011643_20260703_entry_ev_00344_horizon_reliability_diagnostics/`
- all rows: `data/reports/backtests/20260703_011716_20260703_entry_ev_00344_horizon_reliability_diagnostics_allrows/`

Main outputs:

- `horizon_reliability_choice_summary.csv`
- `horizon_reliability_choice_deltas.csv`
- `horizon_reliability_failure_cases.csv`
- `horizon_reliability_head_summary.csv`
- `horizon_reliability_missing_targets.csv`

## Method

For each decision, compare chosen horizon under:

```text
pnl
pnl_delta_tail
pnl_tail_reliability_gated
pnl_delta_tail_reliability_gated
```

Baseline is plain `pnl`. The script records:

- baseline horizon and actual PnL
- chosen horizon and actual PnL for each score mode
- delta versus baseline
- changed / worse / better flags
- chosen head predictions and reliability scores
- horizon-level actual PnL, predicted PnL error, delta error, beats60 error, tail error
- missing target coverage for candidate-generation failures

This is diagnostic only. Actual PnL is used to evaluate choices, not to make a runtime decision.

## Results

### Target Subset

Targets:

```text
fresh2024_validation 2024-03 long
fresh2024_validation 2024-08 long
fresh2024_validation 2024-11 long
refit2025_validation 2025-03 short
refit2025_validation 2025-07 short
hybrid2025_0912_external 2025-10 long
hybrid2025_0912_external 2025-11 short
```

Aggregate versus plain `pnl`:

| score mode | row scope | decisions | delta vs `pnl` | changed | worse | better |
|---|---|---:|---:|---:|---:|---:|
| `pnl_delta_tail` | available | `68` | `-63.0506` | `6` | `6` | `0` |
| `pnl_tail_reliability_gated` | available | `68` | `-87.8104` | `7` | `5` | `2` |
| `pnl_delta_tail_reliability_gated` | available | `68` | `-131.8792` | `13` | `6` | `7` |
| `pnl_delta_tail_reliability_gated` | greedy | `6` | `+2.1500` | `1` | `0` | `1` |

The greedy improvement is only one decision in `fresh2024 2024-11`, while available candidates show broader deterioration.

### All Rows Check

All 00343 scored examples:

| score mode | row scope | decisions | delta vs `pnl` | changed | worse | better |
|---|---|---:|---:|---:|---:|---:|
| `pnl_delta_tail` | available | `132` | `-33.6478` | `13` | `10` | `3` |
| `pnl_tail_reliability_gated` | available | `132` | `-93.6228` | `17` | `10` | `7` |
| `pnl_delta_tail_reliability_gated` | available | `132` | `-137.6916` | `23` | `11` | `12` |
| `pnl_delta_tail_reliability_gated` | greedy | `11` | `+2.1500` | `1` | `0` | `1` |

This confirms the target subset result is not only a hand-picked local problem.

### Worst Failure Cases

Large negative changes versus plain `pnl`:

| score mode | target | baseline -> chosen | baseline actual | chosen actual | delta | reliability driver |
|---|---|---:|---:|---:|---:|---|
| `pnl_delta_tail_reliability_gated` | `fresh2024 2024-08 long` | `60m -> 240m` | `+9.4600` | `-43.9404` | `-53.4004` | `beats60 +0.5786`, delta +0.3910 |
| `pnl_delta_tail_reliability_gated` | `hybrid2025 2025-11 short` | `60m -> 240m` | `+2.5570` | `-25.0320` | `-27.5890` | `beats60 +0.2748` |
| `pnl_tail_reliability_gated` | `hybrid2025 2025-11 short` | `60m -> 240m` | `+2.5570` | `-25.0320` | `-27.5890` | `beats60 +0.2748` via changed score surface |
| `pnl_delta_tail_reliability_gated` | `refit2025 2025-07 short` | `60m -> 720m` | `-9.5400` | `-36.9996` | `-27.4596` | reliability 0; falls back to PnL/tail surface |
| `pnl_delta_tail_reliability_gated` | `hybrid2025 2025-10 long` | `60m -> 240m` | `+3.5800` | `-12.0000` | `-15.5800` | `beats60 +0.3067` |

### Head Error Reading

Important horizon-level summaries:

| target | horizon | actual PnL sum | actual beats60 rate | pred beats60 mean | beats60 reliability | actual tail rate | pred tail mean |
|---|---:|---:|---:|---:|---:|---:|---:|
| `fresh2024 2024-08 long` available | `60m` | `+28.7330` | `1.0000` | `0.9921` | `0.5786` | `0.0000` | `0.2532` |
| `fresh2024 2024-08 long` available | `240m` | `-37.5262` | `0.2857` | `0.5350` | `0.5786` | `0.1429` | `0.3067` |
| `fresh2024 2024-08 long` available | `720m` | `-218.0040` | `0.0000` | `0.5245` | `0.5786` | `1.0000` | `0.4112` |
| `refit2025 2025-07 short` available | `60m` | `-24.5992` | `1.0000` | `0.9936` | `0.0000` | `0.1000` | `0.2359` |
| `refit2025 2025-07 short` available | `240m` | `-156.8936` | `0.2000` | `0.4554` | `0.3647` | `0.8000` | `0.3455` |
| `refit2025 2025-07 short` available | `720m` | `-334.3956` | `0.1000` | `0.4597` | `0.0000` | `0.9000` | `0.3523` |
| `hybrid2025 2025-11 short` available | `60m` | `-26.2960` | `1.0000` | `0.9937` | `0.0000` | `0.4348` | `0.2857` |
| `hybrid2025 2025-11 short` available | `240m` | `-190.0142` | `0.4348` | `0.5098` | `0.2748` | `0.5217` | `0.3593` |
| `hybrid2025 2025-11 short` available | `720m` | `-558.5768` | `0.3913` | `0.5191` | `0.0000` | `0.5652` | `0.3871` |

Interpretation:

- `beats60` reliability is positive because the head has some historical ordering signal, but the current target can still have 60m as the least bad or only positive horizon.
- tail probability is poorly calibrated in severe target months: 720m actual tail rate can be `0.9000` to `1.0000` while predicted tail stays near `0.35` to `0.41`.
- Reliability has to become a confidence report or head-selection veto, not a continuous PnL score addend.

## Decision

- `entry_ev_horizon_reliability_diagnostics.py`: accepted infrastructure.
- Horizon/head reliability error summaries: accepted diagnostics.
- Direct reliability multiplier remains rejected as policy.
- Standard policy remains NoTrade.

## Next

1. Use reliability diagnostics to build a head-selection report: which head is active, which head is ignored, and why.
2. Add an abstention-style diagnostic that refuses horizon switches when the target head has high positive reliability but the current horizon's actual class base rate is weak in the same prior context.
3. Continue candidate generation for `fresh2024 2024-11` and `refit2025 2025-03`; 00344 confirms missing rows remain a separate problem.
4. Keep plain `pnl` low-complexity ranker as the baseline for support repair until a reliability-aware method beats it outside target-local diagnostics.

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_horizon_reliability_diagnostics.py tests/test_entry_ev_horizon_reliability_diagnostics.py tests/test_docs_reports.py`: OK
- `uv run python -m unittest tests.test_entry_ev_horizon_reliability_diagnostics tests.test_docs_reports`: OK
- `git diff --check`: OK
- 00344 target subset diagnostics: OK
- 00344 all rows diagnostics: OK
