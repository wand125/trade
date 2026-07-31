# Entry EV Forced Exit Policy Inputs

日時: 2026-07-02 00:15 JST
更新日時: 2026-07-02 00:15 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00251の次アクションとして、`forced_exit_loss_target` をprediction rowへ接続する `scripts/experiments/entry_ev_forced_exit_policy_inputs.py` を追加した。
- 00251の `exit_shortening_targets.csv` から、対象月より前だけで `exit_risk` / `ev_exit` bucket rateを作り、long/short side rowへ `predicted_forced_exit_loss_risk` を付与した。
- base scoreは 00247/00250 のdiagnostic baselineである `direction_inversion_bucket_s0p1`。forced-exit riskで `score * (1 - strength * risk)` のsoft penaltyをかけた。
- all q95/q99 selected-trade target 123 rowsでは、chronological mean AUCが `ev_exit 0.9500`, `exit_risk 0.8667` と強く出た。
- しかし fixed 2025-03..12 stateful replayでは、NoTradeを超える候補はない。総損益ベストは `forced_exit_loss_exitrisk_bucket_s0p5` q95 の `-60.7862` だが、worst month `-223.3346` とtailが悪い。
- q99総損益ベストは `forced_exit_loss_exitrisk_bucket_s0p25` の `-93.3284`。baseline q99 `-147.3314` から改善するが、worst month `-162.0092` が残る。
- q99 worst monthベストは `forced_exit_loss_evexit_bucket_s1` の `-86.6640`。ただしtotalは `-185.0306` で、4月・11月の勝ちを削りすぎる。
- 判断: forced-exit prediction-row inputとstateful replay infrastructureはaccepted。現penalty scoreは標準policyにしない。forced-exit riskはdirect scoreよりも candidate selector / tail-risk objective / hold-cap adjustment のfeatureへ回す。

## Artifacts

- Script: `scripts/experiments/entry_ev_forced_exit_policy_inputs.py`
- Test: `tests/test_entry_ev_forced_exit_policy_inputs.py`
- Input targets:
  - `data/reports/backtests/20260701_144816_20260701_entry_ev_exit_shortening_target_diagnostics_s1/exit_shortening_targets.csv`
- Input predictions:
  - `data/reports/backtests/20260701_135325_20260701_entry_ev_direction_inversion_policy_inputs_s0p1_s1/enriched_predictions/refit2025_predictions_direction_inversion.parquet`
- Prediction-row artifact:
  - `data/reports/backtests/20260701_145909_20260701_entry_ev_forced_exit_policy_inputs_s1/`
- Summary replay artifacts:
  - `data/reports/backtests/20260701_150229_20260701_entry_ev_forced_exit_loss_exitrisk_bucket_s0p25_fixed2025_03_12_summary_s1/`
  - `data/reports/backtests/20260701_150328_20260701_entry_ev_forced_exit_loss_exitrisk_bucket_s0p5_fixed2025_03_12_summary_s1/`
  - `data/reports/backtests/20260701_150647_20260701_entry_ev_forced_exit_loss_exitrisk_bucketorglobal_s1_fixed2025_03_12_summary_s1/`
  - `data/reports/backtests/20260701_150919_20260701_entry_ev_forced_exit_loss_evexit_bucket_s1_fixed2025_03_12_summary_s1/`
- Trade replay artifacts:
  - `data/reports/backtests/20260701_151322_20260701_entry_ev_forced_exit_loss_exitrisk_bucket_s0p5_fixed2025_03_12_trades_s1/`
  - `data/reports/backtests/20260701_151425_20260701_entry_ev_forced_exit_loss_evexit_bucket_s1_fixed2025_03_12_trades_s1/`

## Method

Target:

```text
forced_exit_loss_target = forced exit and realized loss
```

Risk specs:

| spec | features |
|---|---|
| `exit_risk` | direction, loss-first probability bucket, predicted profit-barrier bucket, predicted fixed 60m to 720m slope bucket |
| `ev_exit` | direction, EV-overestimate bucket, predicted fixed slope bucket, predicted 720m PnL bucket |

Prediction-row score:

```text
adjusted_score = direction_s0p1_score * (1 - penalty_strength * forced_exit_risk)
```

Source modes:

| mode | meaning |
|---|---|
| `bucket` | apply only bucket-supported risk; no-prior/global becomes 0 risk |
| `bucket_or_global` | apply bucket risk when available, otherwise global prior; no-prior becomes 0 risk |

This is still a diagnostic over a fixed window. The target uses selected-trade outcomes, and replay is not enough for standardization.

## Target Calibration

From all q95/q99 target rows:

| spec | rows | target rate | mean AUC | mean Brier | bucket share |
|---|---:|---:|---:|---:|---:|
| `ev_exit` | `123` | `0.0650` | `0.9500` | `0.0420` | `0.5935` |
| `exit_risk` | `123` | `0.0650` | `0.8667` | `0.0427` | `0.5772` |

Prediction-row risk distribution:

| spec | side | risk mean | p50 | p90 | bucket share | global share | no-prior |
|---|---|---:|---:|---:|---:|---:|---:|
| `exit_risk` | long | `0.0424` | `0.0257` | `0.0822` | `0.5722` | `0.1890` | `0.2388` |
| `exit_risk` | short | `0.0943` | `0.0630` | `0.2132` | `0.3983` | `0.3629` | `0.2388` |
| `ev_exit` | long | `0.0557` | `0.0493` | `0.0882` | `0.5534` | `0.2078` | `0.2388` |
| `ev_exit` | short | `0.1285` | `0.0630` | `0.3635` | `0.5451` | `0.2162` | `0.2388` |

Reading:

- Short side risk is much higher, especially `ev_exit` p90.
- OOF AUC is strong because forced-exit losses are a narrow target.
- This does not automatically mean score penalty is correct; it can remove profitable high-risk trades too.

## Stateful Replay

Baseline direction s0.1:

| candidate | total | worst month | trades | max DD |
|---|---:|---:|---:|---:|
| q99 | `-147.3314` | `-153.9192` | `50` | `153.9192` |
| q95 | `-163.3410` | `-206.7934` | `73` | `207.6746` |

Top fixed 2025-03..12 forced-exit settings:

| score kind | candidate | total | worst month | trades | max DD | read |
|---|---|---:|---:|---:|---:|---|
| `exitrisk_bucket_s0p5` | q95 | `-60.7862` | `-223.3346` | `74` | `223.3346` | total best, tail worse |
| `exitrisk_bucket_s0p25` | q99 | `-93.3284` | `-162.0092` | `47` | `162.0092` | q99 total best |
| `exitrisk_bucket_s0p5` | q99 | `-98.4020` | `-151.9704` | `46` | `151.9704` | modest q99 improvement |
| `exitrisk_bucketorglobal_s1` | q99 | `-127.4442` | `-109.6020` | `37` | `117.5760` | better tail, worse total |
| `evexit_bucket_s1` | q99 | `-185.0306` | `-86.6640` | `42` | `86.6640` | best tail, over-defensive |

Worst settings:

| score kind | candidate | total | worst month |
|---|---|---:|---:|
| `evexit_bucket_s1` | q95 | `-301.7516` | `-190.7588` |
| `evexit_bucketorglobal_s1` | q95 | `-286.9820` | `-142.8598` |
| `exitrisk_bucketorglobal_s0p25` | q95 | `-251.5830` | `-202.6054` |

Reading:

- `exit_risk` bucket-only is better for total PnL than `ev_exit`.
- `ev_exit` with high strength can shrink q99 tail but destroys too much upside.
- Global fallback is dangerous for total PnL. It can reduce worst-month loss by applying broader penalty, but it is too coarse.

## Month Comparison

q99 baseline vs representative runs:

| month | baseline | `exitrisk_bucket_s0p5` | `evexit_bucket_s1` |
|---|---:|---:|---:|
| 2025-03 | `-1.7876` | `-1.7876` | `-1.7876` |
| 2025-04 | `+86.5920` | `+56.0420` | `+14.0500` |
| 2025-05 | `-153.9192` | `-151.9704` | `-52.2468` |
| 2025-06 | `-73.2276` | `-56.8452` | `-86.6640` |
| 2025-07 | `-5.3880` | `-3.2640` | `-3.2640` |
| 2025-08 | `-0.0552` | `-0.0552` | `-4.3032` |
| 2025-09 | `+31.1100` | `+31.1100` | `+31.1100` |
| 2025-10 | `-48.0740` | `-33.0560` | `-55.9548` |
| 2025-11 | `+60.2590` | `+66.0656` | `-13.3550` |
| 2025-12 | `-42.8408` | `-4.6412` | `-12.6152` |

q95 baseline vs `exitrisk_bucket_s0p5`:

| month | baseline | `exitrisk_bucket_s0p5` |
|---|---:|---:|
| 2025-04 | `+93.8108` | `+123.6868` |
| 2025-05 | `-206.7934` | `-223.3346` |
| 2025-06 | `-85.3676` | `-68.9852` |
| 2025-09 | `+43.7200` | `+70.0660` |
| 2025-10 | `-55.8494` | `-26.1388` |
| 2025-11 | `+84.7050` | `+97.8690` |
| 2025-12 | `-25.8754` | `-11.4502` |

Reading:

- `exitrisk_bucket_s0p5` improves many months and keeps 4月/11月 upside, but it does not fix May.
- `evexit_bucket_s1` fixes May q99 and shrinks drawdown, but over-penalizes profitable months.
- The remaining issue is not only forced exit. May still needs direction/exit/regime handling.

## Decision

Accepted:

- Forced-exit prediction-row input generation.
- `exit_risk` / `ev_exit` OOF target calibration.
- Fixed 2025 stateful replay sensitivity.

Not accepted:

- Any forced-exit penalty score as standard policy.
- Global fallback forced-exit risk as a direct score penalty.
- Treating high target AUC as enough for policy adoption.

Standard policy remains NoTrade.

## Next

1. Use forced-exit risk as a candidate-level selector/tail-risk feature instead of direct score penalty.
2. Combine total and tail objectives: `exitrisk_bucket_s0p5` improves total, while `evexit_bucket_s1` improves q99 tail. A selector should choose between them only using prior/validation evidence.
3. Diagnose May 2025 residual path after forced-exit penalty; it remains the main blocker.
4. Keep global fallback risk out of direct score until it passes another validation window.

## Verification

- `python3 -m py_compile scripts/experiments/entry_ev_forced_exit_policy_inputs.py tests/test_entry_ev_forced_exit_policy_inputs.py`: OK
- `python3 -m unittest tests.test_entry_ev_forced_exit_policy_inputs tests.test_entry_ev_exit_shortening_target_diagnostics tests.test_docs_reports`: OK
- `git diff --check`: OK
- Forced-exit prediction-row input generation: OK
- Fixed 2025-03..12 stateful replay for 12 score settings: OK
- Representative trade-output replays: OK
