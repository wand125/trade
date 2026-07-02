# Entry EV Prior Residual Pressure

日時: 2026-07-02 15:02 JST
更新日時: 2026-07-02 15:02 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00300で見えた危険contextを、同一windowのstatic blacklistではなく、対象月より前だけで作るprior residual pressureとして診断した。
- `scripts/experiments/entry_ev_selected_trade_prior_residual_pressure.py` を追加し、context別に `month < target_month` のみで prior PnL、loss rate、large-loss rate、bias、pressureを作るようにした。同月内のtrade結果はpriorに含めない。
- 対象は00299 residual combo selected-trade calibration artifact。
- 最良診断ruleは factor mode / `direction,combined_regime,session_regime` / `prior_count_ge5_lossrate_ge0p5_bias_pos`。6 tradesをflagし、flagged PnL `-10.8380`、kept PnL `+340.2728`、loss precision `0.6667`、large-loss recall `0.0870`。
- 同じ細粒度contextでも PnL modeでは同ruleが flagged PnL `+1.5620` と悪化。`prior_count_ge5_total_neg_bias_pos` はfactor/PnLとも 9 trades / flagged PnL `-4.3360` の小幅改善。
- 広いdirection/sessionやdirection/combined rulesは勝ちtradeを大きく削る。例: `direction,session_regime` の `prior_count_ge3_lossrate_ge0p5` は69 trades / flagged PnL `+152.2132` で大幅悪化。
- 判断: prior residual pressure diagnosticsはaccepted infrastructure。best ruleはdiagnostic candidateだが、mode依存とcoverage薄さにより標準policyにはしない。標準policyはNoTrade。

## Artifacts

- New script:
  - `scripts/experiments/entry_ev_selected_trade_prior_residual_pressure.py`
- New test:
  - `tests/test_entry_ev_selected_trade_prior_residual_pressure.py`
- Main run:
  - `data/reports/backtests/20260702_060145_20260702_entry_ev_residual_combo_prior_residual_pressure_s1/`

## Input

```text
data/reports/backtests/20260702_053852_20260702_entry_ev_residual_combo_selected_trade_calibration_s1/selected_trade_supervised_shrinkage_predictions.csv
```

Prior construction:

```text
target trade month M:
  context prior = all selected trades with same context and month < M
  current month trades are excluded
```

Context specs:

```text
direction,session_regime
direction,combined_regime
combined_regime,session_regime
direction,combined_regime,session_regime
```

## Best Diagnostic Rules

Top prior-only rules by no-replacement flagged PnL:

| mode | context spec | rule | flagged trades | flagged PnL | kept PnL | delta | loss precision | loss recall | large loss recall |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| factor | `direction,combined_regime,session_regime` | `prior_count_ge5_lossrate_ge0p5_bias_pos` | `6` | `-10.8380` | `+340.2728` | `+10.8380` | `0.6667` | `0.0412` | `0.0870` |
| factor | `direction,combined_regime,session_regime` | `prior_count_ge5_pressure_ge4` | `2` | `-7.6200` | `+337.0548` | `+7.6200` | `1.0000` | `0.0206` | `0.0435` |
| factor | `direction,combined_regime,session_regime` | `prior_count_ge5_total_neg_bias_pos` | `9` | `-4.3360` | `+333.7708` | `+4.3360` | `0.5556` | `0.0515` | `0.0870` |
| pnl | `direction,combined_regime,session_regime` | `prior_count_ge5_total_neg_bias_pos` | `9` | `-4.3360` | `+333.7708` | `+4.3360` | `0.5556` | `0.0515` | `0.0870` |
| pnl | `direction,combined_regime,session_regime` | `prior_count_ge5_pressure_ge4` | `9` | `-4.3360` | `+333.7708` | `+4.3360` | `0.5556` | `0.0515` | `0.0870` |

Reading:

- prior-onlyの細粒度contextは、00300の `long|range_normal_vol|ny_overlap` residualを一部事前に拾える。
- ただし改善は最大でも `+10.8380` で、232 trades全体に対するcoverageは小さい。
- `factor` と `pnl` で同じruleの挙動がずれるため、calibration mode依存が残る。

## Best Rule Flagged Rows

Best rule:

```text
mode: factor
context: direction,combined_regime,session_regime
rule: prior_count_ge5_lossrate_ge0p5_bias_pos
```

Flagged rows:

| context | month | adjusted PnL | score error | prior trades | prior PnL | prior bias | prior loss rate | prior pressure |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `long|range_normal_vol|ny_overlap` | `2025-12` | `-7.5480` | `+8.0701` | `7` | `-4.8840` | `+1.4472` | `0.5714` | `5.6486` |
| `long|range_normal_vol|ny_overlap` | `2025-10` | `-2.9880` | `+3.5228` | `6` | `-1.8960` | `+1.1013` | `0.5000` | `3.4066` |
| `short|down_normal_vol|asia` | `2025-12` | `-1.8600` | `+1.9847` | `7` | `-0.5780` | `+0.6114` | `0.5714` | `2.0371` |
| `long|range_normal_vol|ny_overlap` | `2025-12` | `-0.0720` | `+0.8258` | `7` | `-4.8840` | `+1.4472` | `0.5714` | `5.6486` |
| `short|down_normal_vol|asia` | `2025-12` | `+0.1700` | `-0.1866` | `7` | `-0.5780` | `+0.6114` | `0.5714` | `2.0371` |
| `short|down_normal_vol|asia` | `2025-11` | `+1.4600` | `-1.1201` | `6` | `-2.0380` | `+0.8999` | `0.6667` | `3.0608` |

Reading:

- The rule catches the two material `long|range_normal_vol|ny_overlap` losses.
- It also flags small winners in `short|down_normal_vol|asia`.
- This is not a clean loss selector. It is a useful residual-risk locator.

## Broad Rule Failure

Broad prior-risk rules do not work:

| mode | context spec | rule | flagged trades | flagged PnL | delta |
|---|---|---|---:|---:|---:|
| pnl | `direction,session_regime` | `prior_count_ge3_lossrate_ge0p5` | `69` | `+152.2132` | `-152.2132` |
| factor | `direction,session_regime` | `prior_count_ge3_lossrate_ge0p5` | `69` | `+152.2132` | `-152.2132` |
| factor | `direction,combined_regime` | `prior_count_ge3_lossrate_ge0p5` | `80` | `+133.3874` | `-133.3874` |
| pnl | `direction,combined_regime` | `prior_count_ge3_lossrate_ge0p5` | `80` | `+133.3874` | `-133.3874` |

Pressure quantiles are also not directly useful. For the fine context spec, highest pressure bin q4 still has positive total:

| mode | pressure bin | pressure range | trades | flagged PnL |
|---|---|---:|---:|---:|
| factor | q4 | `0.7304..29.4687` | `47` | `+74.7334` |
| pnl | q4 | `0.8477..29.9639` | `47` | `+94.3244` |

Reading:

- Broad context risk mostly removes profitable trades.
- Pressure as a continuous hard gate is not enough.
- The usable information is context-local and sparse.

## Decision

Accepted:

- prior-only residual pressure diagnostics
- month-excluding context history construction
- best factor fine-context rule as a diagnostic candidate

Rejected:

- broad prior context risk gates
- pressure quantile hard gates
- using the best prior-only diagnostic rule as standard policy without additional chronology
- treating prior residual pressure as a replacement for role/month floor admission

Standard policy remains NoTrade.

## Next

1. Convert prior residual pressure into a feature, not a hard gate.
2. Use it for an uncertainty / large-loss head or candidate-level selector.
3. Keep `long|range_normal_vol|ny_overlap` and `short|down_normal_vol|asia` as audit contexts.
4. Any policy use must go back through stateful replay, role/month floor, side share, and NoTrade-first gate.

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_selected_trade_prior_residual_pressure.py tests/test_entry_ev_selected_trade_prior_residual_pressure.py`: OK
- `uv run python -m unittest tests.test_entry_ev_selected_trade_prior_residual_pressure`: OK
- `uv run python -m unittest tests.test_entry_ev_selected_trade_prior_residual_pressure tests.test_entry_ev_selected_trade_calibration_diagnostics tests.test_docs_reports`: OK
- `git diff --check`: OK
- prior residual pressure diagnostics run: OK
