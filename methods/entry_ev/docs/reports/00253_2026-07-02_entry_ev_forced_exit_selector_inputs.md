# Entry EV Forced Exit Selector Inputs

日時: 2026-07-02 00:45 JST
更新日時: 2026-07-02 00:45 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00252の反省を受け、forced-exit riskをscore penaltyではなく side candidate hard selector としてprediction rowへ接続した。
- `scripts/experiments/entry_ev_forced_exit_selector_inputs.py` を追加し、bucket-supported riskが閾値以上のsideだけscoreを `blocked_score` へ落とす列を生成した。
- `bucket` sourceだけを使用した。global fallbackは00252と同じ理由でdirect decisionには使わない。
- fixed 2025-03..12 replayでは、`exit_risk bucket t0.10..t0.20` が大きく改善した。
- best q99は `exitrisk_bucket_t0p15/t0p20` total `+161.5908`, worst month `-74.7354`, trades `85`, max DD `79.9540`。
- t0.10もほぼ同水準で、q99 total `+160.7678`, q95 total `+143.0104`。side shareは t0.15/t0.20 より穏当。
- `ev_exit` はtailを縮めるがtotalを削る。`evexit_bucket_t0p1` q99は worst month `-48.1024`, max DD `55.0276` だが total `-90.8702`。
- 判断: forced-exit hard selector infrastructureはaccepted。fixed 2025上の有望候補は `exit_risk bucket t0.10..t0.20`。ただし同一windowで得た結果なので標準policyにはしない。次は別validation windowへ戻す。

## Artifacts

- Script: `scripts/experiments/entry_ev_forced_exit_selector_inputs.py`
- Test: `tests/test_entry_ev_forced_exit_selector_inputs.py`
- Input predictions:
  - `data/reports/backtests/20260701_145909_20260701_entry_ev_forced_exit_policy_inputs_s1/enriched_predictions/refit2025_predictions_forced_exit.parquet`
- Selector prediction-row artifact:
  - `data/reports/backtests/20260701_152625_20260702_entry_ev_forced_exit_selector_inputs_s1/`
- Summary replay artifacts:
  - `data/reports/backtests/20260701_152852_20260702_entry_ev_forced_exit_selector_exitrisk_bucket_t0p1_fixed2025_03_12_s1/`
  - `data/reports/backtests/20260701_153015_20260702_entry_ev_forced_exit_selector_exitrisk_bucket_t0p15_fixed2025_03_12_s1/`
  - `data/reports/backtests/20260701_153125_20260702_entry_ev_forced_exit_selector_exitrisk_bucket_t0p2_fixed2025_03_12_s1/`
  - `data/reports/backtests/20260701_153515_20260702_entry_ev_forced_exit_selector_evexit_bucket_t0p1_fixed2025_03_12_s1/`
- Trade replay artifacts:
  - `data/reports/backtests/20260701_154039_20260702_entry_ev_forced_exit_selector_exitrisk_bucket_t0p1_fixed2025_03_12_trades_s1/`
  - `data/reports/backtests/20260701_154149_20260702_entry_ev_forced_exit_selector_evexit_bucket_t0p1_fixed2025_03_12_trades_s1/`
- Residual diagnostics:
  - `data/reports/backtests/20260701_154339_20260702_entry_ev_forced_exit_selector_exitrisk_t0p1_residual_s1/`
  - `data/reports/backtests/20260701_154358_20260702_entry_ev_forced_exit_selector_evexit_t0p1_residual_s1/`
  - `data/reports/backtests/20260701_154412_20260702_entry_ev_forced_exit_selector_exitrisk_t0p1_may_residual_s1/`
  - `data/reports/backtests/20260701_154442_20260702_entry_ev_forced_exit_selector_evexit_t0p1_may_residual_s1/`

## Method

00252 direct penalty:

```text
adjusted_score = base_score * (1 - strength * forced_exit_risk)
```

00253 hard selector:

```text
if source == bucket and forced_exit_risk >= threshold:
    side_score = blocked_score
else:
    side_score = base_score
```

This is not the same as lowering confidence. If one side is blocked and the opposite side remains attractive, stateful replay can take the replacement side. If both sides are blocked, the selected score falls below threshold and the model stays flat. This matches the one-position constraint better than a smooth score penalty.

## Selector Coverage

Prediction-row block summary:

| score kind | long block | short block | any side | both sides | base selected block | side changed |
|---|---:|---:|---:|---:|---:|---:|
| `exitrisk_bucket_t0p05` | `0.0782` | `0.2607` | `0.3149` | `0.0240` | `0.1101` | `0.0925` |
| `exitrisk_bucket_t0p10` | `0.0048` | `0.0819` | `0.0865` | `0.0002` | `0.0306` | `0.0306` |
| `exitrisk_bucket_t0p15` | `0.0000` | `0.0819` | `0.0819` | `0.0000` | `0.0263` | `0.0263` |
| `exitrisk_bucket_t0p30` | `0.0000` | `0.0557` | `0.0557` | `0.0000` | `0.0165` | `0.0165` |
| `evexit_bucket_t0p05` | `0.1539` | `0.3904` | `0.4131` | `0.1313` | `0.1971` | `0.0953` |
| `evexit_bucket_t0p10` | `0.0000` | `0.1850` | `0.1850` | `0.0000` | `0.0488` | `0.0488` |
| `evexit_bucket_t0p30` | `0.0000` | `0.1377` | `0.1377` | `0.0000` | `0.0360` | `0.0360` |

Reading:

- `exit_risk t0.10..t0.20` only changes the selected side on roughly `2.6%..3.1%` of rows.
- The gain is not caused by broad no-trade suppression. It is a narrow side-candidate selector.
- `ev_exit` is much more aggressive on short-side rows and behaves like a tail reducer.

## Stateful Replay

Baseline from 00252:

| score | candidate | total | worst month | trades | max DD |
|---|---|---:|---:|---:|---:|
| direction s0.1 | q99 | `-147.3314` | `-153.9192` | `50` | `153.9192` |
| direction s0.1 | q95 | `-163.3410` | `-206.7934` | `73` | `207.6746` |
| forced-exit direct penalty best total | q95 | `-60.7862` | `-223.3346` | `74` | `223.3346` |
| forced-exit direct penalty best tail | q99 | `-185.0306` | `-86.6640` | `42` | `86.6640` |

Hard selector fixed 2025-03..12:

| score kind | candidate | total | worst month | trades | max DD | side share |
|---|---|---:|---:|---:|---:|---:|
| `exitrisk_bucket_t0p15` | q99 | `+161.5908` | `-74.7354` | `85` | `79.9540` | `0.6000` |
| `exitrisk_bucket_t0p20` | q99 | `+161.5908` | `-74.7354` | `85` | `79.9540` | `0.6000` |
| `exitrisk_bucket_t0p10` | q99 | `+160.7678` | `-74.7354` | `88` | `79.9540` | `0.5682` |
| `exitrisk_bucket_t0p15` | q95 | `+150.1034` | `-98.8414` | `135` | `99.4640` | `0.6222` |
| `exitrisk_bucket_t0p10` | q95 | `+143.0104` | `-98.8414` | `141` | `99.4640` | `0.5957` |
| `exitrisk_bucket_t0p05` | q99 | `+122.1940` | `-74.7354` | `93` | `79.9540` | `0.5269` |
| `evexit_bucket_t0p10` | q95 | `+30.7238` | `-50.1596` | `139` | `60.0196` | `0.5755` |
| `evexit_bucket_t0p10` | q99 | `-90.8702` | `-48.1024` | `84` | `55.0276` | `0.6190` |

Reading:

- Hard selector reverses the 00252 direct penalty result. The same forced-exit risk is useful when used to remove side candidates, not when used as a smooth score penalty.
- `exit_risk` is the total-PnL candidate. `ev_exit` is the tail candidate.
- `t0.10..t0.20` forms a small plateau for `exit_risk`, which is a better sign than a single isolated threshold.
- Still not standard: all of this is fixed 2025 evidence after prior exploration.

## Month Residual

`exitrisk_bucket_t0p10` month results:

| candidate | May total | May trades | May direction error | May same-side oracle profitable | May large exit regret |
|---|---:|---:|---:|---:|---:|
| q99 | `-74.7354` | `12` | `0.7500` | `1.0000` | `9/12` |
| q95 | `-98.8414` | `20` | `0.7000` | `0.9500` | `15/20` |

May combined residual:

| selector | trades | total | loss PnL | direction error rate | same-side oracle profitable | large exit regret |
|---|---:|---:|---:|---:|---:|---:|
| `exitrisk_t0p10` | `32` | `-173.5768` | `-248.9928` | `0.7188` | `0.9688` | `0.7500` |
| `evexit_t0p10` | `24` | `-98.1072` | `-132.7872` | `0.5833` | `1.0000` | `0.7083` |

Reading:

- `exit_risk t0.10` leaves May losses where the selected-side forced-exit block is already zero. The remaining problem is not the original forced-exit bucket.
- May residual is mostly direction/exit-capture: high direction error, high same-side oracle edge, high exit regret.
- `ev_exit t0.10` cuts May tail further but sacrifices full-window total PnL.

## Decision

Accepted:

- Forced-exit hard selector input generation.
- Bucket-only forced-exit side-candidate blocking.
- Fixed 2025 replay sweep for `exit_risk` and `ev_exit`.
- Representative trade-output replay and May residual diagnostics.

Not accepted:

- Promoting `exitrisk_bucket_t0p10..t0p20` to standard policy from fixed 2025 alone.
- Using `ev_exit` as a primary total-PnL selector.
- Reintroducing global fallback into direct/block decisions.

Standard policy remains NoTrade.

## Next

1. Move `exitrisk_bucket_t0p10..t0p20` back to chronological validation windows, pre-registering the threshold band before looking at new fixed-test results.
2. Treat `evexit_bucket_t0p10` as tail-risk diagnostic, not a primary policy.
3. For May residual, build a target around direction/exit-capture with same-side oracle edge and large exit regret, because forced-exit selection no longer covers the remaining losses.
4. Add validation criteria that include total PnL, worst month, max DD, trade count, side share, and NoTrade comparison.

## Verification

- `python3 -m py_compile scripts/experiments/entry_ev_forced_exit_selector_inputs.py tests/test_entry_ev_forced_exit_selector_inputs.py`: OK
- `python3 -m unittest tests.test_entry_ev_forced_exit_selector_inputs tests.test_entry_ev_forced_exit_policy_inputs tests.test_docs_reports`: OK
- `git diff --check`: OK
- Selector prediction-row input generation: OK
- Fixed 2025-03..12 stateful replay for 10 score settings: OK
- Representative trade-output replays: OK
- May residual diagnostics: OK
