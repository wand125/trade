# Entry EV 00358 Thin Month Candidate Audit

日時: 2026-07-03 14:26 JST
更新日時: 2026-07-03 14:26 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00358後の本流に戻り、残る `month_pnl_below_floor`, `role_trades_low`, `side_share_high` が候補生成不足かselection問題かを診断した。
- `entry_ev_support_repair_thin_month_candidate_diagnostics.py` にdiagnostic-onlyの `needed_top_oracle_actual_*` 列を追加した。actual PnLはoracle/teacher/evaluation用であり、実行policy featureやselector tie-breakerには使わない。
- 00358 best EV2 stateful surfaceでは、残target 4件に候補0。つまり既存bestをrerankしても `fresh2024 2024-03`, `fresh2024 2024-08`, `fresh2024 2024-11`, `refit2025 2025-03` は修復できない。
- 00358 EV -2 + `singleton_720_pred_pnl_lt2` ではtarget pool 12 unique / model-used 12 / relaxed guarded 11 / oracle positive 8だが、すべて実質 `fresh2024 2024-08` に集中する。known singleton lossを止めても、他の薄い月は解けない。
- 00324 external horizon coverageを足すと `fresh2024 2024-03` には51 unique / oracle positive 18 / oracle positive sum `+90.5230` が見える。しかし model-used 0、top predicted PnLは60m `-12.7920`、oracle bestは240m `+13.4900` で、fallback/non-modelかつEV calibration不足。
- `fresh2024 2024-11` と `refit2025 2025-03` は、00358 stateful surfaceにも00324 external horizon coverageにも候補0。rerankingではなく新しい候補生成pathが必要。
- 判断: 00358の残blockerはgate不足ではなく、target-local calibration / fallback confidence / candidate generation不足。標準policyはNoTrade。

## Artifacts

Updated script:

- `scripts/experiments/entry_ev_support_repair_thin_month_candidate_diagnostics.py`

Updated tests:

- `tests/test_entry_ev_support_repair_thin_month_candidate_diagnostics.py`

Runs:

- `data/reports/backtests/20260703_052549_20260703_entry_ev_00359_thin_month_candidates_00358_ev2_stateful_v2/`
- `data/reports/backtests/20260703_052549_20260703_entry_ev_00359_thin_month_candidates_00358_evm2_singleton_stateful_v2/`
- `data/reports/backtests/20260703_052549_20260703_entry_ev_00359_thin_month_candidates_00358_ev2_with00324_v2/`
- `data/reports/backtests/20260703_052549_20260703_entry_ev_00359_thin_month_candidates_00358_evm2_singleton_with00324_v2/`

Outputs per run:

- `thin_month_targets.csv`
- `thin_month_candidate_summary.csv`
- `thin_month_candidate_examples.csv`
- `thin_month_overall_summary.csv`
- `thin_month_candidate_universe.csv`
- `config.json`

## Method

Target months are selected from 00358 monthly metrics where any of these holds:

```text
month pnl < 0
month trade count < 2
max side share > 0.95
```

Main scenarios:

```text
EV2 best:
available_candidates_p0p45_ev2_tail0p3_reqmodel_ranker_pnl

EV -2 with singleton guard:
available_candidates_p0p45_evm2_tail0p3_reqmodel_ranker_pnl__ppg_singleton_720_pred_pnl_lt2
```

Candidate sources:

1. 00358 stateful additions/rejections.
2. 00358 stateful additions/rejections + 00324 external horizon coverage.

The ranking columns used for executable readings are observable predictions:

```text
hv_chosen_pred_pnl
hv_chosen_pred_executable_prob
hv_chosen_pred_tail_loss_prob
hv_chosen_pred_model_used
singleton_720_pred_pnl_lt2
```

`needed_top_oracle_actual_*` is diagnostic-only and uses actual PnL to locate teacher candidates.

## Overall Results

| run | targets | target unique | model-used unique | relaxed guarded | oracle positive | oracle positive sum | top predicted actual sum | top oracle actual sum | target unique actual sum |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| EV2 stateful | `4` | `0` | `0` | `0` | `0` | `0.0000` | `0.0000` | `0.0000` | `0.0000` |
| EV -2 singleton stateful | `4` | `12` | `12` | `11` | `8` | `+15.4770` | `+2.9500` | `+4.8500` | `-12.1914` |
| EV2 + 00324 external | `4` | `51` | `0` | `0` | `18` | `+90.5230` | `-12.7920` | `+13.4900` | `-188.7170` |
| EV -2 singleton + 00324 external | `4` | `63` | `12` | `11` | `26` | `+106.0000` | `-9.8420` | `+18.3400` | `-200.9084` |

Target list under 00358 best:

| target | reason | needed side | month PnL | trades | long / short |
|---|---|---|---:|---:|---:|
| `fresh2024_validation 2024-11` | month floor, month trades, side share | long | `-0.6120` | `1` | `0 / 1` |
| `refit2025_validation 2025-03` | month floor | short | `-0.4730` | `9` | `5 / 4` |
| `fresh2024_validation 2024-03` | month floor, month trades, side share | long | `-0.3636` | `1` | `0 / 1` |
| `fresh2024_validation 2024-08` | month trades, side share | long | `+9.3100` | `1` | `0 / 1` |

## Target Details

| target | 00358 EV2 stateful | EV -2 singleton stateful | With 00324 external | reading |
|---|---|---|---|---|
| `fresh2024 2024-11 long` | candidate 0 | candidate 0 | candidate 0 | new candidate generation path required |
| `refit2025 2025-03 short` | candidate 0 | candidate 0 | candidate 0 | new candidate generation path required |
| `fresh2024 2024-03 long` | candidate 0 | candidate 0 | 51 candidates, model-used 0, oracle positive 18 | fallback/non-model confidence and EV calibration problem |
| `fresh2024 2024-08 long` | candidate 0 | 12 candidates, model-used 12, relaxed guarded 11 | same 12 plus external context | singleton guard helps only this target |

Key examples:

| target | top predicted | actual | model used | top oracle | oracle actual | model used |
|---|---|---:|---|---|---:|---|
| `fresh2024 2024-03 long` | 60m pred `-0.4480` | `-12.7920` | false | 240m pred `-1.0312` | `+13.4900` | false |
| `fresh2024 2024-08 long` | 60m pred `-0.4473` | `+2.9500` | true | 240m pred `-0.4473` | `+4.8500` | true |

## Interpretation

- 00358 EV2 best is not failing because the selection order is wrong; the remaining target months have no candidates in the inspected stateful surface.
- EV -2 + singleton guard opens a useful relaxed surface for `fresh2024 2024-08`, but it does not create candidates for `fresh2024 2024-11` or `refit2025 2025-03`.
- `fresh2024 2024-03` has many oracle positives only when external horizon coverage is added, but every such row is non-model/fallback. Treating those as executable edge would repeat the known leakage/fallback mistake.
- The next implementation should build candidate generators for absent targets and a target-local confidence/calibration layer for fallback rows. More global gates or scalar penalties are not the main path.

## Decision

- Thin-month oracle-top diagnostic columns are accepted infrastructure.
- 00358 best remains a diagnostic branch, not a standard policy.
- `singleton_720_pred_pnl_lt2` remains a narrow diagnostic guard for the known 2024-08 failure only.
- Global threshold relaxation, fallback adoption, and reranking of absent targets are rejected.
- Standard policy remains NoTrade.

## Next

1. Build a candidate-generation path for `fresh2024 2024-11` and `refit2025 2025-03`.
2. For `fresh2024 2024-03`, build fallback/non-model confidence features and evaluate them chronologically before any replay.
3. For `fresh2024 2024-08`, keep `singleton_720_pred_pnl_lt2` as diagnostic and test whether relaxed negative-EV 60/240m candidates can be admitted without hurting other targets.
4. Keep actual PnL out of executable selectors; use `needed_top_oracle_actual_*` only for teacher design and audit.

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_support_repair_thin_month_candidate_diagnostics.py tests/test_entry_ev_support_repair_thin_month_candidate_diagnostics.py`: OK
- `uv run python -m unittest tests.test_entry_ev_support_repair_thin_month_candidate_diagnostics`: OK
- 00359 four thin-month candidate audit runs: OK
