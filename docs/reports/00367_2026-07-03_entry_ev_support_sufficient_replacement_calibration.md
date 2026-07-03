# Entry EV Support-Sufficient Replacement Calibration

日時: 2026-07-03 16:20 JST
更新日時: 2026-07-03 16:20 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00366でbroad horizon abstentionを本線vetoに使えないと分かったため、00363のsupport-sufficient negative month laneへ戻り、replacement candidateのexpected PnL calibrationを診断した。
- `entry_ev_support_sufficient_replacement_calibration_diagnostics.py` を追加し、target月より前のside-row実績だけでcontext別 `actual - predicted` bias / MAE / prior actual meanを作り、replacement candidate rankingを比較した。
- 対象は `refit2025_validation 2025-03`。baseline month PnL `-0.4730`、loss trades 4本、candidate rows `1710`、prior rows `664` / prior months `2`。
- min prior count `20` では、`bias_corrected` が4 lossすべてで `2025-03-11 04:22 long 720m` を選び、mean month PnL `+22.1670`、best `+23.6370`。top side-score replacementのbest `+4.2170` を大きく上回る。
- ただし min20 の `downside_bias_corrected` / `conservative` は `2025-03-31 short 720m` を選び、mean month PnL `-18.7634` へ悪化した。細かすぎるcontextのpositive prior biasを過信すると危険。
- min prior count `50` では、`prior_actual_mean` がmean month PnL `+18.3040`、best `+19.7740`。`bias_corrected` もmean `+8.0640`、best `+9.5340`。`conservative` / `downside` はraw pred fixedと同じ mean `+3.0870` へ戻る。
- 判断: prior-calibrated replacement ranking diagnosticsはaccepted infrastructure。support-sufficient negative monthのreplacement selector候補として有望。ただしprior monthsが2ヶ月しかなく、one-fail candidatesに依存するため標準policyではない。標準policyはNoTrade。

## Artifacts

Added script:

- `scripts/experiments/entry_ev_support_sufficient_replacement_calibration_diagnostics.py`

Added tests:

- `tests/test_entry_ev_support_sufficient_replacement_calibration_diagnostics.py`

Runs:

- main min20: `data/reports/backtests/20260703_071906_20260703_entry_ev_00367_support_sufficient_replacement_calibration/`
- sensitivity min50: `data/reports/backtests/20260703_072000_20260703_entry_ev_00367_support_sufficient_replacement_calibration_min50/`

Outputs:

- `support_sufficient_replacement_calibrated_candidates.csv`
- `support_sufficient_replacement_calibration_choices.csv`
- `support_sufficient_replacement_calibration_score_summary.csv`
- `support_sufficient_replacement_calibration_targets.csv`
- `support_sufficient_replacement_calibration_meta.json`

## Method

For each replacement candidate:

```text
raw_pred = candidate_pred_fixed_best_pred_pnl
prior_bias = mean(prior actual_at_pred_horizon - prior predicted_pnl)
prior_actual_mean = mean(prior actual_at_pred_horizon)
prior_mae = mean(abs(prior actual_at_pred_horizon - prior predicted_pnl))
```

Scoring modes:

```text
side_score
raw_pred_fixed
bias_corrected = raw_pred + prior_bias
downside_bias_corrected = raw_pred + min(prior_bias, 0)
conservative = downside_bias_corrected - prior_mae
prior_actual_mean
```

Context search order:

```text
side, pred_horizon, combined_regime, session_regime
side, combined_regime, session_regime
side, pred_horizon, session_regime
side, pred_horizon
side, session_regime
side
```

Important:

- Prior rows are strictly `month < target_month`.
- Target-month actual fixed-horizon PnL is used only for evaluation.
- Replacement still assumes one existing loss trade is replaced. Choosing that loss requires a separate loss-risk selector.
- All chosen candidates in this run are `one_failed_strict_stage`, not strict candidates.

## Main Result

min prior count `20`:

| score mode | mean month PnL | best month PnL | worst month PnL | mean actual | positive choices | reading |
|---|---:|---:|---:|---:|---:|---|
| `bias_corrected` | `+22.1670` | `+23.6370` | `+21.4686` | `+21.7700` | `4/4` | strongest, but support-sensitive |
| `prior_actual_mean` | `+8.9470` | `+10.4170` | `+8.2486` | `+8.5500` | `4/4` | useful prior signal |
| `raw_pred_fixed` | `+3.0870` | `+4.5570` | `+2.3886` | `+2.6900` | `4/4` | improves vs side score |
| `side_score` | `+2.7470` | `+4.2170` | `+2.0486` | `+2.3500` | `4/4` | 00363 reference |
| `conservative` | `-18.7634` | `-17.2934` | `-19.4618` | `-19.1604` | `0/4` | harmful under min20 context |
| `downside_bias_corrected` | `-18.7634` | `-17.2934` | `-19.4618` | `-19.1604` | `0/4` | harmful under min20 context |

min prior count `50`:

| score mode | mean month PnL | best month PnL | worst month PnL | mean actual | positive choices | reading |
|---|---:|---:|---:|---:|---:|---|
| `prior_actual_mean` | `+18.3040` | `+19.7740` | `+17.6056` | `+17.9070` | `4/4` | robust best in sensitivity |
| `bias_corrected` | `+8.0640` | `+9.5340` | `+7.3656` | `+7.6670` | `4/4` | still improves |
| `raw_pred_fixed` | `+3.0870` | `+4.5570` | `+2.3886` | `+2.6900` | `4/4` | reference |
| `side_score` | `+2.7470` | `+4.2170` | `+2.0486` | `+2.3500` | `4/4` | reference |
| `conservative` | `+3.0870` | `+4.5570` | `+2.3886` | `+2.6900` | `4/4` | falls back to raw pred |
| `downside_bias_corrected` | `+3.0870` | `+4.5570` | `+2.3886` | `+2.6900` | `4/4` | falls back to raw pred |

## Candidate Findings

Useful choices:

- min20 `bias_corrected` selects `2025-03-11 04:22 long`, pred horizon `720m`, pred PnL `+2.1087`, actual `+21.7700`.
- min50 `prior_actual_mean` selects `2025-03-11 06:39 long`, pred horizon `720m`, pred PnL `+0.1889`, actual `+17.9070`.
- Both are `one_failed_strict_stage` candidates, so this is a replacement selector signal, not a direct standard entry signal.

Failure mode:

- min20 `downside_bias_corrected` / `conservative` selects `2025-03-31 03:45 short 720m`, pred PnL `+9.0097`, actual `-19.1604`.
- This happens because some context-specific positive prior bias is not penalized while broader negative-bias candidates are penalized.
- Therefore "downside-only" calibration is not automatically safer; support threshold and context selection matter.

## Decision

Accepted:

- support-sufficient replacement calibration diagnostics
- vectorized candidate horizon construction for full prior side rows
- prior context bias / prior actual mean as replacement selector features
- min prior count sensitivity as mandatory check

Rejected:

- treating min20 best as policy evidence
- direct use of `conservative` / `downside_bias_corrected` without support sensitivity
- standardizing one-fail replacement candidates from one target month

Standard policy remains NoTrade.

## Next

1. Add prior month count / support threshold into the replacement selector surface.
2. Combine replacement selector with loss-risk selector: replacement only matters if the losing current trade is identifiable before/at entry.
3. Test the calibrated replacement selector across all support-sufficient negative months, not just `refit2025 2025-03`.
4. Keep target-month actual PnL out of features; it remains teacher/evaluation only.

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_support_sufficient_replacement_calibration_diagnostics.py tests/test_entry_ev_support_sufficient_replacement_calibration_diagnostics.py`: OK
- `uv run python -m unittest tests.test_entry_ev_support_sufficient_replacement_calibration_diagnostics`: OK
- 00367 min20 replacement calibration run: OK
- 00367 min50 replacement calibration sensitivity run: OK
