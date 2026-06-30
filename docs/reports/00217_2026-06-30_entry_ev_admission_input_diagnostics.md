# Entry EV Admission Input Diagnostics

日時: 2026-06-30 15:01 JST
更新日時: 2026-06-30 15:01 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00216の次アクションとして、cal2024で高threshold/rank候補が消える理由を、backtest結果ではなくprediction row入力側で診断した。
- `scripts/experiments/entry_ev_admission_input_diagnostics.py` を追加し、calibrated EV、side gap、entry rank、MLP exit holding validity、stateless admission countをfamily/month/config単位で出力する。
- これはone-position制約や実際の決済PnLを含まない。入場候補がgate前にどこで消えているかを分解するための入力診断である。
- cal2024は `56,077` prediction rows中、`side_gap >= 5` を満たすselected-side rowが `11` しかなく、`entry10/short9/min_rank0.0` はstateless entry `0`。
- holding validityは主因ではない。cal2024は long/short とも `56,077` rowsすべてが `min_valid_predicted_hold_minutes=30` を満たす。
- refit2025は逆に long calibrated EV scale が大きく、`entry10/short9/min_rank0.0` で stateless entry `29,567`、うち `29,522` がlong。fold間のEV scale/side選択のズレが大きい。
- fixed-positiveに見えた sparse high-rank row `entry14/short9/min_rank0.6` は、validation入力側でも支持されない。fresh2024はstateless entry `0`、refit2025は `25` entriesすべてlong。
- 判断: 現状の絶対EV threshold + side margin + rank gateはfold間のscale driftに弱い。標準policyはNoTradeのまま。次はEV絶対値ではなく、side/regime別quantile/rank正規化と新しいchronological foldでのactive validation evidenceを優先する。

## Artifacts

- Script: `scripts/experiments/entry_ev_admission_input_diagnostics.py`
- Tests: `tests/test_entry_ev_admission_input_diagnostics.py`
- Diagnostics run:
  - `data/reports/backtests/20260630_entry_ev_admission_input_diagnostics/20260630_060014_entry_ev_admission_input_diagnostics/`
- Main outputs:
  - `monthly_base_summary.csv`
  - `monthly_config_summary.csv`
  - `family_config_summary.csv`
  - `diagnostics.json`

## Method

Input prediction files:

| family | prediction file | role |
|---|---|---|
| `cal2024` | `data/reports/modeling/20260630_chrono_hgb_mlp_exit_2024_01_02/predictions_hgb_entry_mlp_exit_2024_01_02.parquet` | calibration-validation |
| `fresh2024` | `data/reports/modeling/20260630_chrono_hgb_mlp_exit_2024_03_12/predictions_hgb_entry_mlp_exit_2024_03_12.parquet` | fresh chronological 2024 comparison |
| `refit2025` | `data/reports/modeling/20260630_chrono_hgb_mlp_exit_2025_03_12/predictions_hgb_entry_mlp_exit_2025_valid.parquet` | 2025 refit validation |

Stateless admission rule:

```text
selected_side = long if calibrated_long_ev >= calibrated_short_ev else short
selected_threshold = entry_threshold for long, entry_threshold + short_offset for short
enter if:
  valid calibrated EV
  abs(long_ev - short_ev) >= side_margin
  selected MLP holding minutes >= 30
  selected entry rank >= min_entry_rank
  selected_score > selected_threshold
```

This is intentionally not the final backtest. It does not model one-position blocking, replacement trades, exit fill, or monthly PnL. It only explains whether the model output even creates admissible entry rows.

## Base Distribution

| family | rows | selected side profile | EV scale | side margin support | holding validity |
|---|---:|---|---|---:|---:|
| `cal2024` | `56,077` | long share `0.344..0.406` | long q95 `11.06..11.13`, short q95 `10.69..10.88`, short max `14.89` | `11` | `56,077 / 56,077` |
| `fresh2024` | `296,756` | long share `0.146..0.291` | long q95 `11.09..11.45`, short q95 `11.79..15.86`, short max `23.84` | `17,201` | `293,483 / 296,756` selected-side rows |
| `refit2025` | `54,877` | long share `0.915..0.917` | long q95 `23.52..23.71`, short q95 `15.65..17.45`, long max `38.87` | `29,701` | `54,751 / 54,877` selected-side rows |

Interpretation:

- cal2024 is not failing because MLP holding is invalid. It is failing because selected long/short EVs are close and absolute EV thresholds do not leave a side-margin-supported entry set.
- fresh2024 is mostly short-selected, but high short offsets make entries sparse and month-dependent.
- refit2025 is mostly long-selected with a much larger long EV scale. This explains why the relaxed multi-window row can look strong in refit2025 while failing elsewhere.

## Config Diagnostics

Representative stateless entry counts:

| config | family | entries | long | short | side margin ok | long above long threshold | short above short threshold |
|---|---|---:|---:|---:|---:|---:|---:|
| `entry8/short3/rank0.0` | `cal2024` | `5` | `0` | `5` | `11` | `47,469` | `1,529` |
| `entry8/short3/rank0.0` | `fresh2024` | `14,164` | `22` | `14,142` | `17,201` | `261,380` | `90,158` |
| `entry8/short3/rank0.0` | `refit2025` | `29,584` | `29,522` | `62` | `29,701` | `52,360` | `51,345` |
| `entry10/short9/rank0.0` | `cal2024` | `0` | `0` | `0` | `11` | `20,070` | `0` |
| `entry10/short9/rank0.0` | `fresh2024` | `323` | `22` | `301` | `17,201` | `109,938` | `498` |
| `entry10/short9/rank0.0` | `refit2025` | `29,567` | `29,522` | `45` | `29,701` | `51,460` | `804` |
| `entry12/short6/rank0.0` | `cal2024` | `0` | `0` | `0` | `11` | `144` | `0` |
| `entry12/short6/rank0.0` | `fresh2024` | `818` | `22` | `796` | `17,201` | `2,563` | `1,173` |
| `entry12/short6/rank0.0` | `refit2025` | `29,567` | `29,522` | `45` | `29,701` | `51,006` | `1,077` |
| `entry14/short9/rank0.6` | `cal2024` | `0` | `0` | `0` | `11` | `0` | `0` |
| `entry14/short9/rank0.6` | `fresh2024` | `0` | `0` | `0` | `17,201` | `77` | `2` |
| `entry14/short9/rank0.6` | `refit2025` | `25` | `25` | `0` | `29,701` | `50,133` | `257` |

Rank support also collapses quickly:

| family | `entry10/short9/rank0.6` entries | `rank>=0.6` support | `rank>=0.7` support |
|---|---:|---:|---:|
| `cal2024` | `0` | `1,976` | `58` |
| `fresh2024` | `49` | `8,759` | `109` |
| `refit2025` | `25` | `406` | `17` |

Thus high-rank rows are not merely low-frequency; they are often absent or side-mismatched in validation.

## Decision

Accepted:

- Input-side diagnostics for entry EV admission.
- CSV outputs separating base prediction distribution from config-level stateless admission counts.
- Compact stdout columns for repeatable experiment logs.

Not accepted as standard policy:

- Any policy selected only by fixed-test PnL.
- Relaxed `entry10/short9/min_rank0.0`, because refit2025 contributes a massive long-skewed entry set while fixed tests already failed.
- Sparse `entry14/short9/min_rank0.6`, because validation input support is zero or long-only, not short-positive.
- Freezing an absolute side-balance or rank threshold from the current three windows.

Current standard remains NoTrade.

## Next

1. Add EV scale diagnostics that compare raw EV, calibrated EV, EV quantile, side gap quantile, and entry-rank quantile across folds.
2. Evaluate admission thresholds in side/regime-local quantile space instead of absolute EV dollars only.
3. Create an additional chronological fold with a new reserved outer test; do not promote existing fixed-test windows to validation.
4. Re-run multi-window selection only after active validation evidence exists in more than two independent windows.

## Verification

- `python3 -m unittest tests.test_entry_ev_admission_input_diagnostics`: OK, `3` tests
- `python3 -m unittest tests.test_entry_ev_admission_input_diagnostics tests.test_entry_ev_validation_inventory tests.test_docs_reports`: OK, `12` tests
- `python3 -m py_compile scripts/experiments/entry_ev_admission_input_diagnostics.py tests/test_entry_ev_admission_input_diagnostics.py`: OK
- `python3 -m py_compile scripts/experiments/entry_ev_admission_input_diagnostics.py scripts/experiments/entry_ev_validation_inventory.py tests/test_entry_ev_admission_input_diagnostics.py tests/test_entry_ev_validation_inventory.py`: OK
- `git diff --check`: OK
- Diagnostic run: OK, output in `data/reports/backtests/20260630_entry_ev_admission_input_diagnostics/20260630_060014_entry_ev_admission_input_diagnostics/`
