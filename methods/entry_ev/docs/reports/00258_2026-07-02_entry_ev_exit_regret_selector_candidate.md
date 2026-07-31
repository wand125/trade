# Entry EV Exit Regret Selector Candidate

日時: 2026-07-02 01:54 JST
更新日時: 2026-07-02 01:54 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00257の次アクションとして、exit-regret riskをprediction rowへ戻す入力生成を実装した。
- `scripts/experiments/entry_ev_forced_exit_policy_inputs.py` を拡張し、`confidence_exit`, `profit_exit`, `context_confidence` risk specsと `side_confidence_gap_bucket` を追加した。
- broad s0.5 target `same_side_large_regret_loss_target` から `exit_regret` riskを作り、`confidence_exit` / `side_context` のprior-month bucket rateをprediction rowsへ付与した。
- target calibration overallは `confidence_exit` mean AUC `0.7239`, bucket prediction share `0.4093`; `side_context` mean AUC `0.5086`。
- soft penalty `exit_regret_confexit_bucket_s0p5` は悪化。broad q99/floor5は baseline `-142.3776` から `-153.6806`、q95/floor5は `-84.1626` から `-96.2626`。
- hard selector `exit_regret_selector_confidenceexit_bucket_t0p4` は大きく改善。broad q99/floor5は `-142.3776 -> +18.9072`, max DD `162.1992 -> 54.5368`。q95/floor5も `-84.1626 -> -30.2972`。
- fixed 2025-03..12でも q99/floor5は `-177.3790 -> +19.1218`, max DD `388.6412 -> 54.5368`。q95/floor5は `-160.8606 -> -67.8612`。
- 判断: `exit_regret_selector_confidenceexit_bucket_t0p4` q99/floor5をpre-registered diagnostic candidateへ昇格。ただし broad targets由来であり、標準policyにはしない。標準policyはNoTrade。

## Artifacts

- Code:
  - `scripts/experiments/entry_ev_forced_exit_policy_inputs.py`
- Test:
  - `tests/test_entry_ev_forced_exit_policy_inputs.py`
- Risk input artifact:
  - `data/reports/backtests/20260701_164144_20260702_entry_ev_exit_regret_risk_s0p5_broad_policy_inputs_s1/`
- Soft penalty broad replay:
  - `data/reports/backtests/20260701_164333_20260702_entry_ev_exit_regret_confexit_bucket_s0p5_broad_validation_backtest_s1/`
- Hard selector inputs:
  - `data/reports/backtests/20260701_164713_20260702_entry_ev_exit_regret_selector_s0p5_broad_inputs_s1/`
- Hard selector broad replay:
  - `data/reports/backtests/20260701_164827_20260702_entry_ev_exit_regret_selector_confexit_t0p4_broad_validation_backtest_s1/`
- Hard selector fixed 2025 replay:
  - `data/reports/backtests/20260701_165213_20260702_entry_ev_exit_regret_selector_confexit_t0p4_fixed2025_03_12_backtest_s1/`

## Implementation

Added risk specs to the existing forced-exit risk input path:

```text
confidence_exit    := direction + side_confidence_gap_bucket + loss_first_prob_bucket + time_exit_prob_bucket
profit_exit        := direction + pred_profit_barrier_bucket + loss_first_prob_bucket + pred_exit_hold_bucket
context_confidence := direction + combined_regime + session_regime + side_confidence_gap_bucket
```

`side_confidence_gap_bucket` is computed per long/short side from:

```text
long gap  = pred_best_side_prob_1  - pred_best_side_prob_-1
short gap = pred_best_side_prob_-1 - pred_best_side_prob_1
```

Risk input target:

```text
target    = same_side_large_regret_loss_target
risk_name = exit_regret
specs     = confidence_exit,side_context
```

The risk table is chronological by month: prediction month uses only target rows from earlier months.

## Calibration

Target calibration overall:

| risk spec | folds | rows | target rate | mean AUC | mean Brier | bucket share |
|---|---:|---:|---:|---:|---:|---:|
| `confidence_exit` | `16` | `215` | `0.2512` | `0.7239` | `0.1857` | `0.4093` |
| `side_context` | `16` | `215` | `0.2512` | `0.5086` | `0.1917` | `0.3535` |

`confidence_exit` is the useful spec here. `side_context` remains a weak fallback.

## Selector Input

Hard selector thresholds tested as coarse input generation:

```text
thresholds = 0.30, 0.40, 0.50
source     = bucket only
```

For `confidence_exit t0.4`, block share:

| family | long block | short block | base-selected block | selected-side changed |
|---|---:|---:|---:|---:|
| cal2024 | `0.0473` | `0.0000` | `0.0197` | `0.0197` |
| fresh2024 | `0.2005` | `0.0000` | `0.1399` | `0.1399` |
| refit2025 | `0.1895` | `0.1009` | `0.1681` | `0.1418` |

Reading:

- The selector mostly blocks long candidates.
- It changes enough refit2025 selected sides to affect the stateful path.
- Threshold `0.4` was chosen from coarse block-share behavior, not by scanning PnL.

## Broad Replay

Broad replay comparison:

| run | candidate | total PnL | worst role | trades | max DD | side share |
|---|---|---:|---:|---:|---:|---:|
| baseline s0.5 | q99 floor5 | `-142.3776` | `-162.1992` | `70` | `162.1992` | `0.6000` |
| soft confexit s0.5 | q99 floor5 | `-153.6806` | `-205.6640` | `60` | `205.6640` | `0.6167` |
| hard confexit t0.4 | q99 floor5 | `+18.9072` | `-54.2268` | `36` | `54.5368` | `0.6944` |
| baseline s0.5 | q95 floor5 | `-84.1626` | `-233.2854` | `112` | `233.2854` | `0.6071` |
| soft confexit s0.5 | q95 floor5 | `-96.2626` | `-164.5472` | `104` | `190.4684` | `0.5865` |
| hard confexit t0.4 | q95 floor5 | `-30.2972` | `-66.7024` | `72` | `74.5524` | `0.7500` |

Reading:

- Soft penalty is rejected.
- Hard selector improves q99/floor5 total, worst role, and max DD.
- q95/floor5 improves but remains negative and side concentration rises.

## Fixed 2025 Stress

Fixed 2025-03..12 comparison:

| run | candidate | total PnL | worst month | trades | max DD | side share |
|---|---|---:|---:|---:|---:|---:|
| baseline s0.5 | q99 floor5 | `-177.3790` | `-177.3790` family total | `53` | `388.6412` | `0.5849` |
| hard confexit t0.4 | q99 floor5 | `+19.1218` | `-54.2268` | `21` | `54.5368` | `0.7143` |
| baseline s0.5 | q95 floor5 | `-160.8606` | `-160.8606` family total | `80` | `501.3372` | `0.6000` |
| hard confexit t0.4 | q95 floor5 | `-67.8612` | `-66.7024` | `43` | `74.5524` | `0.7907` |

Reading:

- q99/floor5 is the promising candidate.
- q95/floor5 still loses and side share becomes high.
- The improvement is partly exposure reduction, so it must be checked against NoTrade and trade-count floors.

## Decision

Accepted:

- `confidence_exit` / `profit_exit` / `context_confidence` risk specs in prediction-row input generation.
- `side_confidence_gap_bucket` generation on prediction rows.
- `exit_regret` risk input generation from `same_side_large_regret_loss_target`.
- `exit_regret_selector_confidenceexit_bucket_t0p4` as a diagnostic candidate.

Rejected:

- soft `exit_regret_confexit_bucket_s0p5` penalty.
- `side_context` as the primary exit-regret risk spec.
- q95/floor5 as the promoted candidate.
- standard-policy promotion from this same broad target/replay loop.

Standard policy remains NoTrade.

## Next

1. Treat `exit_regret_selector_confidenceexit_bucket_t0p4` q99/floor5 as pre-registered and replay on an additional non-overlapping chronology if available.
2. Run trade-delta diagnostics against baseline s0.5 q99/floor5 to separate removed losses, removed wins, and replacement losses.
3. Check monthly distribution, side share, and whether the improvement is concentrated in a few removed trades.
4. Compare against s1 exposure-reduction baseline; the selector must beat simple exposure reduction, not just trade less.
5. Do not tune `0.3/0.4/0.5` further on the same broad validation rows.

## Verification

- `python3 -m unittest tests.test_entry_ev_forced_exit_policy_inputs`: OK
- `python3 -m unittest tests.test_docs_reports`: OK
- `python3 -m py_compile scripts/experiments/entry_ev_forced_exit_policy_inputs.py`: OK
- `git diff --check`: OK
- risk input generation: OK
- hard selector input generation: OK
- broad hard selector replay: OK
- fixed 2025 hard selector replay: OK
