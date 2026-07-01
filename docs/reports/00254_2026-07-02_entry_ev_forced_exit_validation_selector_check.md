# Entry EV Forced Exit Validation Selector Check

日時: 2026-07-02 01:06 JST
更新日時: 2026-07-02 01:06 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00253の次アクションとして、fixed 2025で有望だった forced-exit hard selector を chronological validation family へ戻した。
- 既存validation runは family ごとに別prediction parquetを使っていたため、`scripts/experiments/entry_ev_multifamily_policy_trade_enrichment.py` を追加した。
- この補助スクリプトは `monthly_policy_metrics.csv` の `family` に従って各trade CSVを正しいprediction parquetへjoinし、exit-shortening/forced-exit diagnosticsで使う `selected_*` columnsを生成する。
- validation selected trades 77 rowsでは `forced_exit_loss_target` は 3件 / target PnL `-8.4240` と小さい。chronological calibrationは `exit_risk` mean AUC `0.9167`, pooled AUC `0.9444` と強く見えるが、supportは薄い。
- selector replayでは、baseline `side_prior_pressure_s0p5` q95/floor5 total `+68.0000` を上回る設定はなかった。
- `exitrisk_bucket_t0p02/t0p04` は q95/floor5 total `+41.4470`, trades `28` でbaselineより悪化。`exitrisk_bucket_t0p01` は q95/floor5 total `-5.3622` まで崩れた。
- `evexit_bucket_t0p01` も q95/floor5 total `+54.8862` でbaseline未満。`evexit_bucket_t0p02/t0p04` と `exitrisk_bucket_t0p20` はbaseline同一。
- 判断: multi-family validation trade enrichment infrastructureはaccepted。validation forced-exit selectorは標準採用しない。00253のfixed 2025 positive resultは、このvalidation windowでは再現しなかった。

## Artifacts

- Script:
  - `scripts/experiments/entry_ev_multifamily_policy_trade_enrichment.py`
- Test:
  - `tests/test_entry_ev_multifamily_policy_trade_enrichment.py`
- Baseline validation with trades:
  - `data/reports/backtests/20260701_155226_20260702_entry_ev_side_prior_pressure_s0p5_validation_trades_for_forced_exit_s1/`
- Multi-family enriched trades:
  - `data/reports/backtests/20260701_155806_20260702_entry_ev_side_prior_pressure_s0p5_validation_trade_enrichment_s1/`
- Validation target diagnostics:
  - `data/reports/backtests/20260701_155815_20260702_entry_ev_forced_exit_validation_target_diagnostics_s1/`
- Forced-exit risk prediction rows:
  - `data/reports/backtests/20260701_155837_20260702_entry_ev_forced_exit_validation_policy_inputs_s1/`
- Selector prediction rows:
  - `data/reports/backtests/20260701_155922_20260702_entry_ev_forced_exit_validation_selector_inputs_s1/`
- Backtest summary CSV:
  - `data/reports/backtests/20260702_forced_exit_validation_selector_backtest_summary_s1.csv`

## Method

Validation family:

```text
cal2024  : 2024-01..2024-02
fresh2024: 2024-03..2024-04
refit2025: 2025-01..2025-02
```

Baseline score:

```text
pred_side_prior_pressure_s0p5_{long,short}_best_adjusted_pnl
```

Policy candidates:

```text
q99_sg95_rank90_floor5_side_regime_session_month
q95_sg95_rank90_floor5_side_regime_session_month
q99_sg95_rank90_floor10_side_regime_session_month
q95_sg95_rank90_floor10_side_regime_session_month
```

Forced-exit target generation:

- selected validation trades only.
- target: `forced_exit_loss_target = is_forced_exit and adjusted_pnl < 0`.
- risk specs: `exit_risk`, `ev_exit`.
- calibration is chronological by month: target month uses only earlier target rows.
- selector uses `bucket` source only. global fallback is not used for direct/block decisions.

Thresholds:

- pre-registered carry-over band from 00253: `0.10`, `0.15`, `0.20`.
- validation support was much lower than fixed 2025, so diagnostic low thresholds `0.01`, `0.02`, `0.04` were also tested to observe where the selector starts acting.

## Baseline

Baseline `side_prior_pressure_s0p5` validation replay:

| candidate | total | worst month | trades | max DD | side share |
|---|---:|---:|---:|---:|---:|
| q95/floor5 | `+68.0000` | `-1.8000` | `30` | `26.9590` | `0.6667` |
| q99/floor5 | `+35.0014` | `-1.8000` | `17` | `14.0472` | `0.6471` |
| q99/floor10 | `+8.5684` | `-1.8000` | `9` | `4.9846` | `0.6667` |
| q95/floor10 | `-11.2600` | `-9.4600` | `21` | `37.6890` | `0.6190` |

Role split for baseline q95/floor5:

| role | total | worst | trades | max DD | side share |
|---|---:|---:|---:|---:|---:|
| cal2024_calibration_validation | `-1.6986` | `-1.8000` | `21` | `26.9590` | `0.6190` |
| fresh2024_validation | `+24.0400` | `0.0000` | `1` | `0.0000` | `1.0000` |
| refit2025_validation | `+45.6586` | `0.0000` | `8` | `7.3884` | `0.8750` |

Reading:

- baseline itself is not standard because support is small and fixed 2025 later broke.
- In this validation slice, however, the profits are concentrated in a few trades that a broad selector can easily remove.

## Target Calibration

Validation selected-trade target summary:

| target | rows | target count | target rate | target true PnL | target false PnL |
|---|---:|---:|---:|---:|---:|
| `forced_exit_loss_target` | `77` | `3` | `0.0390` | `-8.4240` | `+108.7338` |
| `late_exit_regret_loss_target` | `77` | `8` | `0.1039` | `-57.6552` | `+157.9650` |
| `hold_too_long_loss_target` | `77` | `9` | `0.1169` | `-55.9920` | `+156.3018` |

Forced-exit calibration:

| risk spec | fold count | rows | target rate | mean AUC | pooled AUC | bucket share |
|---|---:|---:|---:|---:|---:|---:|
| `exit_risk` | `4` | `77` | `0.0390` | `0.9167` | `0.9444` | `0.2078` |
| `ev_exit` | `4` | `77` | `0.0390` | `0.5000` | `0.3333` | `0.0000` |

Reading:

- `exit_risk` looks strong as a classifier, but only 3 positives exist.
- `ev_exit` has no bucket support in this validation target calibration and should not be treated as confirmed.
- High AUC alone is not enough: the later replay shows that blocking high-risk rows can remove winning trades or change replacement paths.

## Selector Replay

Best candidate per tested score kind:

| score kind | best candidate | total | worst month | trades | max DD | side share |
|---|---|---:|---:|---:|---:|---:|
| `exitrisk_bucket_t0p01` | q99/floor10 | `+8.5684` | `-1.8000` | `9` | `4.9846` | `0.6667` |
| `exitrisk_bucket_t0p02` | q95/floor5 | `+41.4470` | `-1.8000` | `28` | `26.9590` | `0.6786` |
| `exitrisk_bucket_t0p04` | q95/floor5 | `+41.4470` | `-1.8000` | `28` | `26.9590` | `0.6786` |
| `exitrisk_bucket_t0p20` | q95/floor5 | `+68.0000` | `-1.8000` | `30` | `26.9590` | `0.6667` |
| `evexit_bucket_t0p01` | q95/floor5 | `+54.8862` | `-1.8000` | `28` | `26.9590` | `0.6071` |
| `evexit_bucket_t0p02` | q95/floor5 | `+68.0000` | `-1.8000` | `30` | `26.9590` | `0.6667` |
| `evexit_bucket_t0p04` | q95/floor5 | `+68.0000` | `-1.8000` | `30` | `26.9590` | `0.6667` |

Role split for q95/floor5:

| run | cal2024 total | fresh2024 total | refit2025 total | trades |
|---|---:|---:|---:|---:|
| baseline | `-1.6986` | `+24.0400` | `+45.6586` | `21 / 1 / 8` |
| `exitrisk_t0p01` | `-1.6986` | `0.0000` | `-3.6636` | `21 / 0 / 8` |
| `exitrisk_t0p02` | `-1.6986` | `0.0000` | `+43.1456` | `21 / 0 / 7` |
| `evexit_t0p01` | `-1.6986` | `+24.0268` | `+32.5580` | `21 / 2 / 5` |

Reading:

- `exitrisk_t0p02/t0p04` delete the single fresh2024 winning trade and one refit2025 trade, so total drops from `+68.0000` to `+41.4470`.
- `exitrisk_t0p01` is too broad. It removes fresh2024 profit and breaks the refit2025 path, dropping q95/floor5 to `-5.3622`.
- `evexit_t0p01` is less destructive but still removes refit2025 profit.
- The 00253 fixed 2025 plateau did not reproduce on this chronological validation family.

## Decision

Accepted:

- Multi-family policy trade enrichment script.
- Unit test proving family-specific prediction join.
- Validation target generation path for forced-exit/exit-shortening labels.
- Forced-exit selector validation replay artifacts.

Rejected for standard policy:

- validation forced-exit hard selector settings tested here.
- lowering thresholds to compensate for low forced-exit target base rate.
- using `ev_exit` as primary selector when bucket support is absent.

Standard policy remains NoTrade.

## Next

1. Do not continue tuning forced-exit thresholds on this validation slice. The baseline profits are too sparse and threshold changes mostly remove winning trades.
2. Treat forced-exit risk as a diagnostic feature, not a primary selector, until tested on a wider chronological family with more target support.
3. Move the next modeling effort to broader residual targets: `late_exit_regret_loss_target`, `hold_too_long_loss_target`, direction-side inversion, and same-side oracle edge / large exit regret.
4. Add more validation months before using forced-exit risk as an entry blocker. A 3-positive target is too small for stable selector decisions.

## Verification

- `python3 -m unittest tests/test_entry_ev_multifamily_policy_trade_enrichment.py`: OK
- multi-family validation trade enrichment: OK, prediction match share `1.0` for all non-empty trade groups.
- validation forced-exit target diagnostics: OK
- forced-exit validation policy input generation: OK
- forced-exit validation selector input generation: OK
- validation selector replay for 7 score kinds: OK
