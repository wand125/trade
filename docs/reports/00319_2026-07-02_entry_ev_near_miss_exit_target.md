# Entry EV Near-Miss Exit Target

日時: 2026-07-02 20:26 JST
更新日時: 2026-07-02 20:26 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00318の次アクションとして、near-miss support candidatesをexit timing / EV calibration targetへ変換した。
- `scripts/experiments/entry_ev_near_miss_exit_target_diagnostics.py` を追加し、00318候補に `fixed 60/240/720` の最良target、oracle gap、prediction parquet上のfixed-horizon予測選択をjoinした。
- greedy selected 11本は、future-labelでfixed horizonを最適選択できればfixed-best合計 `+77.1400`。一方、単純fixed60は `-26.4512`、fixed240は `-31.5870`、fixed720は `-46.0898`。
- ただし現predicted fixed horizonで選ぶと、greedy selectedの実現合計は `-6.8562`。one-fail strict 8本では `-41.1822` まで悪化する。
- 判断: near-miss exit target diagnosticsはaccepted infrastructure。actual fixed-bestは教師labelとして有望だが、現predicted fixed horizon choiceはpolicy evidenceではなくreject。次はnear-miss pool用のchronological exit-viability / horizon headを作る。

## Artifacts

- New script:
  - `scripts/experiments/entry_ev_near_miss_exit_target_diagnostics.py`
- New tests:
  - `tests/test_entry_ev_near_miss_exit_target_diagnostics.py`
- Run:
  - `data/reports/backtests/20260702_112532_20260702_entry_ev_00319_near_miss_exit_target_00318_s1/`

## Method

Input:

```text
candidate rows = 00318 strict/relaxed/one-fail candidate rows
selected rows = 00318 greedy selection rows
prediction parquet = 00314 fixed60 uncertainty margin enriched predictions
horizons = 60, 240, 720 minutes
```

For each candidate row:

1. Keep side-specific actual fixed-horizon labels:
   `side_fixed_60m_adjusted_pnl`, `side_fixed_240m_adjusted_pnl`, `side_fixed_720m_adjusted_pnl`.
2. Add target columns:
   - `target_fixed_best_adjusted_pnl`
   - `target_fixed_best_horizon_minutes`
   - `target_fixed_executable`
   - `target_fixed_best_vs_60m_delta`
   - `target_oracle_gap_vs_fixed_best`
3. Join side-specific prediction columns from parquet:
   - `pred_fixed_60m_adjusted_pnl`
   - `pred_fixed_240m_adjusted_pnl`
   - `pred_fixed_720m_adjusted_pnl`
4. Compute predicted horizon choice and realized PnL at that chosen horizon.

Actual fixed labels and oracle best are diagnostic / supervised targets only. They are not execution-time features.

## Main Results

Greedy selected 11 rows:

| bucket | rows | fixed-best | fixed60 | fixed240 | fixed720 | oracle best | actual at predicted horizon |
|---|---:|---:|---:|---:|---:|---:|---:|
| one-fail strict | `8` | `+42.8140` | `-17.7984` | `-31.7138` | `-80.4158` | `+86.0590` | `-41.1822` |
| relaxed | `2` | `+14.3900` | `-8.9688` | `-1.3532` | `+14.3900` | `+22.5390` | `+14.3900` |
| strict | `1` | `+19.9360` | `+0.3160` | `+1.4800` | `+19.9360` | `+35.2160` | `+19.9360` |
| total | `11` | `+77.1400` | `-26.4512` | `-31.5870` | `-46.0898` | `+143.8140` | `-6.8562` |

Reading:

- 00318で見えたfixed60/fixed240/fixed720の悪化は、single fixed horizon問題でもある。
- future-labelでbest fixed horizonを選べれば、selected rowsのfixed-horizon upper boundはかなり改善する。
- しかし現prediction parquetのfixed-horizon予測で選ぶと、one-fail strictでは `+42.8140` のfixed-best targetに対して実現 `-41.1822`。このままexit choiceに使うのは危険。

Available candidates 132 rows:

| scope | fixed-best | fixed60 | fixed240 | fixed720 | oracle best | actual at predicted horizon |
|---|---:|---:|---:|---:|---:|---:|
| available candidates | `+572.2276` | `-305.5378` | `-579.2936` | `-1546.4292` | `+1676.3210` | `-681.7860` |

The target pool is rich, but current predicted fixed-horizon choice is strongly miscalibrated.

## Calibration Notes

Score summaries:

| scope | score | target | rows | bias | MAE | Spearman |
|---|---|---|---:|---:|---:|---:|
| available | side score | fixed-best | `132` | `+0.0530` | `6.2753` | `0.1613` |
| available | predicted fixed-best | fixed-best | `76` | `-0.7785` | `9.0119` | `0.2457` |
| available | predicted fixed720 | actual fixed720 | `132` | `+9.8945` | `18.4024` | `-0.0279` |
| greedy selected | predicted fixed-best | fixed-best | `9` | `-3.0641` | `7.9189` | `0.1000` |
| greedy selected | predicted fixed720 | actual fixed720 | `11` | `+6.5671` | `15.0998` | `0.3909` |

Threshold notes for greedy selected rows:

| predicted fixed-best threshold | flagged | actual at predicted horizon | fixed-best target | executable rate |
|---:|---:|---:|---:|---:|
| `>= 5` | `4` | `+6.3590` | `+47.1390` | `0.7500` |
| `>= 10` | `1` | `-39.9600` | `+0.8200` | `0.0000` |

The threshold surface is not monotone enough to use as a simple hard gate. The `>=10` case picks the hybrid 2025-11 short where predicted 720m is high but actual 720m is `-39.9600`.

## Decision

Accepted:

- near-miss exit target diagnostics
- fixed-best horizon target generation for near-miss candidates
- prediction-horizon choice audit against actual fixed-horizon labels
- oracle gap / fixed-horizon capture diagnostics

Rejected:

- using current predicted fixed-horizon maximum as an executable exit selector
- promoting one-fail strict support overlay before exit-viability calibration
- treating fixed-best target or oracle best as policy evidence without chronological prediction

Standard policy remains NoTrade.

## Next

1. Train a chronological exit-viability / horizon head on the near-miss candidate pool.
2. Predict `target_fixed_executable`, `target_fixed_best_horizon_minutes`, and calibrated EV for selected horizon using only decision-time features.
3. Replay side-balanced support overlay only when the predicted exit head improves fixed-horizon realization without using actual fixed labels.
4. Keep 00317 repair target and month floor gate active; filling support count while worsening month floor remains failure.

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_near_miss_exit_target_diagnostics.py tests/test_entry_ev_near_miss_exit_target_diagnostics.py`: OK
- `uv run python -m unittest tests.test_entry_ev_near_miss_exit_target_diagnostics`: OK
- `uv run python -m unittest tests.test_entry_ev_near_miss_exit_target_diagnostics tests.test_entry_ev_thin_month_opposite_candidate_diagnostics tests.test_docs_reports`: OK
- `git diff --check`: OK
- 00319 near-miss exit target diagnostics run: OK
