# Entry EV Scale Quantile Diagnostics

日時: 2026-06-30 15:14 JST
更新日時: 2026-06-30 15:14 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00217の次アクションとして、絶対EV閾値ではなく、fold内quantileでentry admission候補を比較する診断を追加した。
- `scripts/experiments/entry_ev_scale_quantile_diagnostics.py` は raw / calibrated EV の分布、selected side、side gap、entry rankを月別・regime/session別に集計し、quantile gateのstateless entry countを出す。
- quantile scopeは `month`, `side_month`, `side_regime_session_month` を実装した。局所groupの過剰なsingleton採用を避けるため `min_scope_rows=20` を標準にした。
- calibrated EVの絶対scaleは大きくズレている。selected score q95は cal2024 `11.16..11.22`、fresh2024 `12.08..15.86`、refit2025 `23.52..23.73`。
- side gap q95も cal2024 `2.48..2.91`、fresh2024 `3.18..6.49`、refit2025 `10.03..10.28` とズレる。00217でcal2024が `side_gap>=5` で消えた理由はここでも確認できる。
- month-local quantile gateはcal2024の候補消失を解消するが、side偏りは残る。`score>=q99`, `side_gap>=q95`, `rank>=q90` では cal2024 `103` entries、fresh2024 `738` entries、refit2025 `50` entries。
- 同じ条件を `side_regime_session_month` scopeにすると、cal2024 `41` entries、fresh2024 `316` entries、refit2025 `32` entriesまで近づき、side構成もやや改善する。
- 判断: quantile admissionは次にbacktestへ接続する価値がある。ただし今回の出力はprediction入力側のstateless診断であり、標準policyはまだNoTrade。

## Artifacts

- Script: `scripts/experiments/entry_ev_scale_quantile_diagnostics.py`
- Tests: `tests/test_entry_ev_scale_quantile_diagnostics.py`
- Run:
  - `data/reports/backtests/20260630_entry_ev_scale_quantile_diagnostics/20260630_061343_entry_ev_scale_quantile_diagnostics/`
- Outputs:
  - `score_distribution_summary.csv`
  - `group_distribution_summary.csv`
  - `monthly_quantile_gate_summary.csv`
  - `family_quantile_gate_summary.csv`
  - `diagnostics.json`

## Distribution Drift

Calibrated selected score q95:

| family | months | selected score q95 | side gap q95 | selected long share |
|---|---|---:|---:|---:|
| `cal2024` | `2024-01..02` | `11.16..11.22` | `2.48..2.91` | `0.344..0.406` |
| `fresh2024` | `2024-03..12` | `12.08..15.86` | `3.18..6.49` | `0.146..0.291` |
| `refit2025` | `2025-01..02` | `23.52..23.73` | `10.03..10.28` | `0.915..0.917` |

Raw EV is also unstable:

| family | selected score q95 | side gap q95 | selected long share |
|---|---:|---:|---:|
| `cal2024` | `14.50..14.60` | `4.67..6.15` | `0.543..0.660` |
| `fresh2024` | `16.53..27.50` | `6.48..15.37` | `0.195..0.464` |
| `refit2025` | `20.70..23.93` | `6.46..8.39` | `0.380..0.512` |

Interpretation:

- calibrated EV reduces some raw volatility, but refit2025 long score scale is still far larger than cal/fresh.
- absolute side margin `5` is too high for cal2024 calibrated distribution and too permissive for refit2025.
- entry rank q95 is relatively stable near `0.57..0.60`, but high rank thresholds still remove many rows because the upper tail is very thin.

## Quantile Gate

The table below is stateless. It does not include one-position blocking, exit timing, cost path, or realized PnL.

Calibrated gate `score>=q99`, `side_gap>=q95`, `rank>=q90`, `min_scope_rows=20`:

| quantile scope | family | entries | long | short | active months |
|---|---|---:|---:|---:|---:|
| `month` | `cal2024` | `103` | `43` | `60` | `2` |
| `month` | `fresh2024` | `738` | `0` | `738` | `10` |
| `month` | `refit2025` | `50` | `50` | `0` | `1` |
| `side_month` | `cal2024` | `95` | `43` | `52` | `2` |
| `side_month` | `fresh2024` | `539` | `88` | `451` | `10` |
| `side_month` | `refit2025` | `53` | `53` | `0` | `1` |
| `side_regime_session_month` | `cal2024` | `41` | `23` | `18` | `2` |
| `side_regime_session_month` | `fresh2024` | `316` | `59` | `257` | `10` |
| `side_regime_session_month` | `refit2025` | `32` | `26` | `6` | `2` |

Less strict calibrated gate `score>=q95`, `side_gap>=q95`, `rank>=q90`:

| quantile scope | family | entries | long | short | active months |
|---|---|---:|---:|---:|---:|
| `month` | `cal2024` | `209` | `137` | `72` | `2` |
| `month` | `fresh2024` | `2,669` | `71` | `2,598` | `10` |
| `month` | `refit2025` | `59` | `59` | `0` | `2` |
| `side_regime_session_month` | `cal2024` | `206` | `111` | `95` | `2` |
| `side_regime_session_month` | `fresh2024` | `1,125` | `244` | `881` | `10` |
| `side_regime_session_month` | `refit2025` | `125` | `105` | `20` | `2` |

Interpretation:

- month-local quantile already fixes the cal2024 no-entry problem, but it inherits selected-side skew.
- side-month quantile reintroduces some minority-side entries, especially fresh2024 long entries, but refit2025 remains long-heavy.
- side/regime/session-local quantile is the best next candidate axis because it reduces fold-level scale drift and prevents one side/regime bucket from dominating purely by absolute EV scale.
- This is still not evidence of profitability. It only shows that a comparable admission surface can be created without using fixed-test PnL.

## Decision

Accepted:

- EV scale / quantile diagnostics infrastructure.
- `month`, `side_month`, `side_regime_session_month` quantile scopes.
- `min_scope_rows` support guard for local quantile groups.

Not accepted as standard policy:

- Any quantile gate as a trading policy before stateful backtest.
- Month-local quantile alone, because it still produces severe side skew.
- Treating restored candidate count as restored edge.

Current standard remains NoTrade.

## Next

1. Add quantile columns to prediction artifacts or backtest input path, then run stateful timed-EV backtests using `selected_score_pct`, `side_gap_pct`, and `selected_rank_pct`.
2. Start with `side_regime_session_month` scope and `min_scope_rows>=20`.
3. Compare quantile policy against NoTrade, existing absolute EV gates, fixed-test hindsight rows, side balance, worst month, and cost stress.
4. Keep fixed-test windows out of selector training; use them only after the quantile admission rule is pre-registered.

## Verification

- `python3 -m unittest tests.test_entry_ev_scale_quantile_diagnostics`: OK, `4` tests
- `python3 -m unittest tests.test_entry_ev_scale_quantile_diagnostics tests.test_entry_ev_admission_input_diagnostics tests.test_docs_reports`: OK, `10` tests
- `python3 -m py_compile scripts/experiments/entry_ev_scale_quantile_diagnostics.py tests/test_entry_ev_scale_quantile_diagnostics.py`: OK
- `python3 -m py_compile scripts/experiments/entry_ev_scale_quantile_diagnostics.py scripts/experiments/entry_ev_admission_input_diagnostics.py tests/test_entry_ev_scale_quantile_diagnostics.py tests/test_entry_ev_admission_input_diagnostics.py`: OK
- `git diff --check`: OK
- Diagnostic run: OK, output in `data/reports/backtests/20260630_entry_ev_scale_quantile_diagnostics/20260630_061343_entry_ev_scale_quantile_diagnostics/`
