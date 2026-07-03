# Entry EV Support Repair Thin Month Candidates

日時: 2026-07-03 09:06 JST
更新日時: 2026-07-03 09:06 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00338の次アクションとして、leak-free support repair後に残る負け月/薄い月へ、代替候補がどの候補面に存在するかを診断した。
- `scripts/experiments/entry_ev_support_repair_thin_month_candidate_diagnostics.py` を追加し、00335のstateful候補面と00324のrow x horizon coverage候補を同じsummaryへ正規化した。
- stateful-onlyでは、EV2 scenarioの残target 4件に候補0。EV -2 scenarioでは `fresh2024 2024-08` だけ13 unique候補があり、他の `fresh2024 2024-03`, `fresh2024 2024-11`, `refit2025 2025-03` は候補0。
- 00324 external horizon候補を混ぜると、`fresh2024 2024-03 long` には51 unique候補、oracle positive 18本、positive sum `+90.5230`、best `+13.4900` が見える。ただし model-used unique 0、strict/relaxed guarded pass 0。予測EV上位は60m損失側で、actual topではない。
- EV -2では `fresh2024 2024-08` にmodel-used候補13 uniqueがあり、relaxed guarded passは11本。ただしtop predicted PnLは720m selected `-29.1360` で、00338の `singleton_720_pred_pnl_lt2` guardを入れると、60/240mの小幅positive候補へ戻る。
- 判断: thin-month candidate diagnosticsはaccepted infrastructure。fresh/thin monthの問題は「候補が全くない」だけではなく、「良い候補が非model/fallbackまたは負EV側に沈む」問題。単純なthreshold緩和やfallback採用はしない。標準policyはNoTrade。

## Artifacts

Added script:

- `scripts/experiments/entry_ev_support_repair_thin_month_candidate_diagnostics.py`

Added tests:

- `tests/test_entry_ev_support_repair_thin_month_candidate_diagnostics.py`

Stateful-only runs:

- `data/reports/backtests/20260703_000317_20260703_entry_ev_00339_thin_month_candidates_ev2/`
- `data/reports/backtests/20260703_000317_20260703_entry_ev_00339_thin_month_candidates_evm2/`

Stateful + 00324 external horizon runs:

- `data/reports/backtests/20260703_000518_20260703_entry_ev_00339_thin_month_candidates_ev2_with00324/`
- `data/reports/backtests/20260703_000518_20260703_entry_ev_00339_thin_month_candidates_evm2_with00324/`

Outputs:

```text
thin_month_targets.csv
thin_month_candidate_summary.csv
thin_month_candidate_examples.csv
thin_month_overall_summary.csv
thin_month_candidate_universe.csv
config.json
```

## Method

Target months are selected from 00335 monthly metrics when any of these holds:

```text
month pnl < 0
month trade count < 2
max side share > 0.95
```

The candidate summary uses only observable fields for ranking/gates:

```text
hv_chosen_pred_pnl
hv_chosen_pred_executable_prob
hv_chosen_pred_tail_loss_prob
hv_chosen_pred_model_used
singleton_720_pred_pnl_lt2
```

Actual PnL is used only in `oracle_*` or `*_actual_pnl` evaluation columns. It is not used as a selector tie-breaker.

Two candidate sources are compared:

1. 00335 stateful surface: selected rows plus `quota_full`, `overlap`, `pred_pnl_floor` rejections.
2. 00324 external horizon coverage: row x horizon candidates from `available_candidates`, mapped into the same schema.

## Results

Stateful-only:

| scenario | targets | target pool unique | model-used unique | strict guarded | relaxed guarded | reading |
|---|---:|---:|---:|---:|---:|---|
| EV2 | `4` | `0` | `0` | `0` | `0` | current stateful surface cannot repair remaining thin/negative months |
| EV -2 | `4` | `13` | `13` | `0` | `11` | candidates exist only for `fresh2024 2024-08`; top predicted PnL is bad 720m singleton |

Stateful + 00324 external horizon:

| scenario | targets | target pool unique | model-used unique | strict guarded | relaxed guarded | oracle positive | oracle positive sum |
|---|---:|---:|---:|---:|---:|---:|---:|
| EV2 | `4` | `51` | `0` | `0` | `0` | `18` | `+90.5230` |
| EV -2 | `4` | `64` | `13` | `0` | `11` | `26` | `+106.0000` |

Target details:

| target | candidate surface | executable reading |
|---|---|---|
| `fresh2024 2024-03 long` | 00324 external has 51 unique and oracle positive 18 | all model-used false; top predicted PnL chooses 60m losses; oracle 240m positives are hidden/fallback evidence |
| `fresh2024 2024-08 long` | EV -2 stateful has 13 model-used unique | selected 720m is `-29.1360`; singleton guard redirects attention to 60/240m `+2.9500` / `+4.8500`, but this is relaxed EV negative surface |
| `fresh2024 2024-11 long` | no stateful candidate in 00335 target surface | 00324 known single candidate is not present in current stateful target set; still not robust |
| `refit2025 2025-03 short` | no candidate in both inspected surfaces | needs a new candidate-generation path, not reranking |

Best oracle examples, explicitly not policy evidence:

| target | timestamp | horizon | actual | pred PnL | prob | tail | model-used |
|---|---|---:|---:|---:|---:|---:|---|
| fresh2024 2024-03 long | 2024-03-21 15:05 UTC | 240 | `+13.4900` | `-1.0312` | `0.4203` | `0.2826` | false |
| fresh2024 2024-03 long | 2024-03-21 15:08 UTC | 240 | `+13.0000` | `-1.0312` | `0.4203` | `0.2826` | false |
| fresh2024 2024-08 long | 2024-08-22 03:39 UTC | 240 | `+4.8500` | `-0.4473` | `0.5931` | `0.1498` | true |
| fresh2024 2024-08 long | 2024-08-22 03:39 UTC | 60 | `+2.9500` | `-0.4473` | `0.5931` | `0.1252` | true |

## Interpretation

- `fresh2024 2024-03` is not solved by reranking. The profitable rows exist, but the learned horizon heads mark them as fallback/non-model with negative EV.
- `fresh2024 2024-08` is a different failure mode: model-used candidates exist, but the top predicted choice overprefers the 720m singleton. The 00338 guard catches that specific bad path, but the independent support is still one unique negative case.
- `fresh2024 2024-11` and `refit2025 2025-03` are still candidate-generation gaps in the inspected surfaces.
- The next useful work is not global threshold relaxation. It is target-local calibration / confidence modeling for fallback rows, plus a new candidate generator for months absent from the support-repair surface.

## Decision

- Thin-month candidate diagnostics: accepted infrastructure.
- Stateful-only reranking/replacement for remaining thin months: insufficient.
- 00324 external oracle positives: teacher/diagnostic only, not policy evidence.
- Global fallback or EV threshold relaxation: reject.
- Standard policy remains NoTrade.

## Next

1. Build target-local confidence labels for fallback/non-model horizon rows, starting with `fresh2024 2024-03`.
2. Add a candidate-generation path for `fresh2024 2024-11` and `refit2025 2025-03`, because they are absent from the 00335 stateful surface.
3. Re-run EV -2 with `singleton_720_pred_pnl_lt2` as a pre-registered diagnostic guard, but keep it out of standard policy until more unique singleton cases exist.
4. Keep actual PnL strictly in oracle/teacher/evaluation columns.

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_support_repair_thin_month_candidate_diagnostics.py tests/test_entry_ev_support_repair_thin_month_candidate_diagnostics.py`: OK
- `uv run python -m unittest tests.test_entry_ev_support_repair_thin_month_candidate_diagnostics`: OK
- stateful-only EV2 / EV -2 diagnostics run: OK
- stateful + 00324 external horizon EV2 / EV -2 diagnostics run: OK
