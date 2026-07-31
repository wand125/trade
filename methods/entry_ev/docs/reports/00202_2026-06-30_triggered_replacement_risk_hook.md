# Triggered Replacement Risk Hook

日時: 2026-06-30 11:38 JST
更新日時: 2026-06-30 11:39 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00201の次アクションとして、`side_context_interaction_guard_apply.py` に prior deterioration trigger 後だけ発火する replacement risk hook を追加した。
- 新しい `match_mode` は `signal_short_raw_gap_or_triggered_low_ev` と `signal_short_raw_gap_or_triggered_profit_miss`。
- trigger は target 月より前の `summary_by_run.csv` だけを使い、`gap5/budget0` の直近3ヶ月 `short_adjusted_pnl < 0` が1ヶ月以上なら発火する。履歴が少なすぎる初期月を避けるため、標準は `min_prior_months=4`。
- 2025-01..12 coststress 260 / p10 replacement-margin10 familyでは、baseline `gap5/budget0` total `+508.9838`, worst `-215.1172` に対し、triggered profit-miss min4 は total `+790.3634`, worst `-46.0150`, max DD `129.7364`。
- triggered low-EV は total `+540.5594` で小改善だが、worst `-215.1172` が残る。現時点の本命は low-EV ではなく triggered profit-miss。
- `pred_short_profit_barrier_hit` は0/1列なので、0.40..0.60のthreshold sweepは完全に同じ結果になった。これは微小な閾値最適化ではなく、予測profit barrier miss (`0`) を止めるルール。

## Artifacts

- Main min4 dynamic hook: `data/reports/backtests/20260630_023600_20260630_113600_triggered_replacement_risk_hook_min4/`
- Initial no-min-prior dynamic hook: `data/reports/backtests/20260630_023335_20260630_113300_triggered_replacement_risk_hook/`
- Threshold stability:
  - `data/reports/backtests/20260630_023718_20260630_113800_triggered_profit_miss_t040_min4/`
  - `data/reports/backtests/20260630_023719_20260630_113800_triggered_profit_miss_t045_min4/`
  - `data/reports/backtests/20260630_023719_20260630_113800_triggered_profit_miss_t055_min4/`
  - `data/reports/backtests/20260630_023719_20260630_113800_triggered_profit_miss_t060_min4/`

Inputs:

- Source monthly runs: `data/reports/backtests/20260629_140836_side_drift_guard_admission_margin_isolated_2025_01_12_coststress_260/coststress_side_guard_p10_replm10/`
- Trigger summary: `data/reports/backtests/20260630_000340_short_raw_gap_entry_budget_zero_p10_margin10/summary_by_run.csv`
- Data: `data/processed/histdata/xauusd/xauusd_m1.parquet`

## Method

Dynamic hook:

```text
active = signal_short_raw_gap(short_gap >= 5)
         OR (
              prior_trigger_active
              AND final_signal == short
              AND replacement risk condition
            )
```

Trigger:

```text
trigger source: match_mode = signal_short_raw_gap
trigger source: short_gap_threshold = 5
trigger source: context_entry_budget = 0
min_prior_months = 4
recent_month_count = 3
trigger if recent_short_losing_months >= 1
```

Risk conditions:

```text
low_ev: pred_short_best_adjusted_pnl < 15
profit_miss: pred_short_profit_barrier_hit < 0.5
```

The hook is causal at month level: for target month `M`, only rows with `month < M` in the trigger summary are used. It still needs fresh / unseen validation because the rule family was developed on the same 2025 experiment sequence.

## Results

All 2025-01..12:

| variant | trades | total PnL | worst month | max DD | short PnL | triggered months |
|---|---:|---:|---:|---:|---:|---:|
| `gap5/budget0` baseline | `738` | `+508.9838` | `-215.1172` | `215.1172` | `+164.7278` | `4` |
| triggered low-EV min4 | `736` | `+540.5594` | `-215.1172` | `215.1172` | `+196.3034` | `4` |
| triggered profit-miss min4 | `699` | `+790.3634` | `-46.0150` | `129.7364` | `+446.1074` | `4` |
| defensive `gap0/budget0` | `558` | `+418.2596` | `-45.4774` | `126.7826` | `+74.0036` | n/a |
| fixed `gap5 -> gap0` min4, target 2025-05..12 | `374` | `+232.2466` | `-46.0150` | `129.7364` | `+154.7572` | `4` |

No-min-prior version:

| variant | total PnL | worst month | note |
|---|---:|---:|---|
| triggered profit-miss, min prior omitted | `+660.4748` | `-46.0150` | 2025-02..04の少数履歴で発火し、勝ちを削った |
| triggered profit-miss, min4 | `+790.3634` | `-46.0150` | 初期月の過剰発火を避けた |

Monthly PnL, min4:

| month | baseline gap5 | triggered low-EV | triggered profit-miss | trigger |
|---|---:|---:|---:|---|
| 2025-01 | `+66.4738` | `+66.4738` | `+66.4738` | no |
| 2025-02 | `+109.9632` | `+109.9632` | `+109.9632` | no |
| 2025-03 | `+107.3596` | `+107.3596` | `+107.3596` | no |
| 2025-04 | `+255.6200` | `+255.6200` | `+255.6200` | no |
| 2025-05 | `+47.3538` | `+47.3538` | `+47.3538` | no |
| 2025-06 | `+158.5812` | `+158.5812` | `+158.5812` | no |
| 2025-07 | `+87.3370` | `+87.3370` | `+87.3370` | no |
| 2025-08 | `-46.0150` | `-46.0150` | `-46.0150` | no |
| 2025-09 | `-215.1172` | `-215.1172` | `-12.7028` | yes |
| 2025-10 | `+4.1924` | `+22.6640` | `+5.5176` | yes |
| 2025-11 | `-36.4850` | `-30.6410` | `+33.3790` | yes |
| 2025-12 | `-30.2800` | `-23.0200` | `-22.5040` | yes |

## Interpretation

- 00201では `profit_hit_lt0p5` は全期間だと良いreplacementも消すため危険だった。今回、prior deterioration triggerと `min_prior_months=4` を組み合わせると、初期の勝ちを温存しながら late bad replacement を削れた。
- low-EV hookは低容量だが、2025-09の最大損失を止めない。`pred_ev_lt15` のsupportが少なすぎるため、現実のdynamic policyでは主防御にならない。
- `profit_miss` は強いが、`pred_short_profit_barrier_hit` が0/1列であり、校正済み確率ではない。次に同一familyの2024側または追加未使用月へ再探索なしで適用し、壊れ方を見る必要がある。
- この結果は標準採用ではなく、候補軸の昇格。採用条件は、未使用期間でも worst/DD を壊さず、NoTradeと `gap0/budget0` を上回ること。

## Decision

- `signal_short_raw_gap_or_triggered_profit_miss` は最有力candidateとして残す。
- `signal_short_raw_gap_or_triggered_low_ev` は診断候補に降格。tailが残るため本線ではない。
- `replacement_trigger_min_prior_months=4` を標準CLIデフォルトにする。少数履歴で発火させると、2025-02..04の勝ちを削る。
- 標準policyにはまだ採用しない。次は同一familyの未使用期間で固定適用する。

## Next

1. coststress 260 + stateful risk5 + replacement margin10 の2024同一family monthly prediction/backtestを生成する。
2. 00202の `profit_miss` hookを、閾値・trigger条件を再探索せず2024側へ適用する。
3. 2024側で壊れる場合、`pred_short_profit_barrier_hit` を0/1ではなく確率または校正済み確率に差し替える。

## Verification

- `python3 -m py_compile scripts/experiments/side_context_interaction_guard_apply.py tests/test_side_context_interaction_guard_apply.py`: OK
- `python3 -m unittest tests.test_side_context_interaction_guard_apply`: OK, 9 tests
- `python3 -m unittest tests.test_side_context_interaction_guard_apply tests.test_docs_reports tests.test_backtest`: OK, 112 tests
- `git diff --check`: OK
- Dynamic hook artifact生成: OK
- Threshold stability artifacts生成: OK
