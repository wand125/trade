# Entry EV Capture Shrink Overlay

日時: 2026-07-02 10:35 JST
更新日時: 2026-07-02 10:35 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00280の次アクションとして、raw `loss_exit30_cd15` を固定benchmarkにし、prior-only exit-capture risk / executable EV calibration / score shrink overlayを検証した。
- `entry_ev_exit_capture_target_diagnostics.py` と `entry_ev_executable_ev_*` 系に `--context-columns` を追加し、`direction,combined_regime,session_regime` と `family,direction,combined_regime,session_regime` を切り替えられるようにした。
- `entry_ev_executable_ev_policy_inputs.py` に `--capture-shrink-strength` を追加した。`1.0` は従来通りhistorical capture factorをそのまま掛け、`0.25` なら `factor = 1 - 0.25 * (1 - historical_capture)` の弱い補正になる。
- prior exit-capture riskはfailure precisionが高いが、flagged集合のPnLがプラスだった。hard blockにすると勝ちtradeも落とす。
- executable EV calibrationはMAEを強く改善するが、low calibrated EV thresholdもプラスPnL集合を削る。
- score shrink overlayは full shrink / family-conditioned full shrink / weak shrink `0.25` の全てで raw cd15 benchmarkを下回った。
- 判断: prior capture factorを直接entry rankingへ掛けるoverlayはreject。capture factorは「実行可能EVの尺度補正・特徴量」として残し、次はsupervised EV shrinkage / exit-capture modelへ進む。

## Baseline

Raw `loss_exit30_cd15` fixed benchmark:

| metric | value |
|---|---:|
| candidate | `q95_sg95_rank90_floor5_side_regime_session_month` |
| variant | `loss_exit30_cd15` |
| profit/loss | `1.0 / 1.20` |
| total adjusted pnl | `+118.6900` |
| month min | `-6.8324` |
| trades | `266` |
| positive roles | `6/6` |

このbenchmarkはまだ標準policyではないが、現時点の固定診断候補として維持する。

## Prior Exit-Capture Risk

Artifacts:

- `data/reports/backtests/20260702_011640_20260702_entry_ev_raw_cd15_exit_capture_risk_context_side_regime_session_s1/`
- `data/reports/backtests/20260702_011640_20260702_entry_ev_raw_cd15_exit_capture_risk_context_side_regime_s1/`
- `data/reports/backtests/20260702_011640_20260702_entry_ev_raw_cd15_exit_capture_risk_context_family_side_regime_session_s1/`
- `data/reports/backtests/20260702_011640_20260702_entry_ev_raw_cd15_exit_capture_risk_context_family_side_regime_s1/`

代表結果:

| context | threshold | flagged trades | flagged pnl | failure precision | recall |
|---|---:|---:|---:|---:|---:|
| side/regime/session | `0.50` | `90` | `+71.2176` | `0.9000` | `0.3266` |
| side/regime/session | `0.25` | `146` | `+89.4530` | `0.9247` | `0.5444` |
| side/regime | `0.75` | `106` | `+18.9796` | `0.9340` | `0.3992` |
| family/side/regime/session | `0.75` | `19` | `+16.7862` | high | low |

Reading:

- prior riskはexit-capture failureを拾うが、同時にopportunity-rich contextも拾う。
- `flagged pnl` がプラスなので、block ruleにすると期待値を落とす。
- これはhard gateではなく、continuous feature / calibration priorとして扱うべき。

## Executable EV Calibration

Artifacts:

- `data/reports/backtests/20260702_011815_20260702_entry_ev_raw_cd15_executable_ev_calibration_diagnostics_s1/`
- `data/reports/backtests/20260702_011904_20260702_entry_ev_raw_cd15_executable_ev_calibration_on_capture_targets_s1/`

代表結果:

| role | raw EV MAE | calibrated EV MAE |
|---|---:|---:|
| HGB 2025-08 | `26.8483` | `0.8909` |
| HGB 2024-03..06 | `13.0712` | `2.3669` |
| refit2025 | `7.2132` | `2.8997` |
| hybrid 2025-09..12 | `5.5076` | `2.9130` |

Threshold診断:

| score | threshold | flagged trades | flagged pnl | failure precision |
|---|---:|---:|---:|---:|
| raw EV | `< 6` | `72` | `+41.2144` | `0.9583` |
| raw EV | `< 8` | `124` | `+111.0936` | high |
| capture calibrated EV | `< 0` | `155` | `+43.0344` | `0.9484` |
| capture calibrated EV | `< 2` | `229` | `+103.3826` | high |

Reading:

- calibrationはEV scale correctionとして有効。
- ただしlow-EV thresholdは、failure率が高くてもPnLプラス集合を削る。
- `pred_taken_ev` の尺度を直すことと、entryを止めることは別問題。

## Score Shrink Replay

Artifacts:

- full side/regime/session shrink:
  - inputs: `data/reports/backtests/20260702_012510_20260702_entry_ev_raw_cd15_capture_shrink_srs_internal_inputs_s1/`
  - inputs: `data/reports/backtests/20260702_012510_20260702_entry_ev_raw_cd15_capture_shrink_srs_hgb_inputs_s1/`
  - inputs: `data/reports/backtests/20260702_012510_20260702_entry_ev_raw_cd15_capture_shrink_srs_hybrid_inputs_s1/`
  - replay: `data/reports/backtests/20260702_012610_20260702_entry_ev_raw_cd15_capture_shrink_srs_replay_s1/`
- full family/side/regime/session shrink:
  - inputs: `data/reports/backtests/20260702_012905_20260702_entry_ev_raw_cd15_capture_shrink_family_srs_internal_inputs_s1/`
  - inputs: `data/reports/backtests/20260702_012905_20260702_entry_ev_raw_cd15_capture_shrink_family_srs_hgb_inputs_s1/`
  - inputs: `data/reports/backtests/20260702_012905_20260702_entry_ev_raw_cd15_capture_shrink_family_srs_hybrid_inputs_s1/`
  - replay: `data/reports/backtests/20260702_012951_20260702_entry_ev_raw_cd15_capture_shrink_family_srs_replay_s1/`
- weak side/regime/session shrink `strength=0.25`:
  - inputs: `data/reports/backtests/20260702_013259_20260702_entry_ev_raw_cd15_capture_shrink_srs_a25_internal_inputs_s1/`
  - inputs: `data/reports/backtests/20260702_013259_20260702_entry_ev_raw_cd15_capture_shrink_srs_a25_hgb_inputs_s1/`
  - inputs: `data/reports/backtests/20260702_013259_20260702_entry_ev_raw_cd15_capture_shrink_srs_a25_hybrid_inputs_s1/`
  - replay: `data/reports/backtests/20260702_013345_20260702_entry_ev_raw_cd15_capture_shrink_srs_a25_replay_s1/`

Candidate sweep:

| overlay | best row by selector ordering | total pnl | role min | month min | trades | decision |
|---|---|---:|---:|---:|---:|---|
| full side/regime/session | `q95 floor1` | `+10.8662` | `-12.3484` | `-19.9608` | `80` | reject |
| full side/regime/session | `q95 floor5` | `+9.5344` | `-1.4280` | `-1.4280` | `34` | reject: support too low |
| full family/side/regime/session | `q95 floor2` | `+10.8600` | `-1.4280` | `-1.4280` | `41` | reject: support too low |
| weak side/regime/session `0.25` | `q95 floor5` | `-0.2380` | `-16.2258` | `-12.8000` | `132` | reject |

Full variant totals across all swept candidates were negative:

| overlay | total pnl across swept candidates | trades |
|---|---:|---:|
| full side/regime/session | `-165.8418` | `927` |
| full family/side/regime/session | `-110.1876` | `807` |
| weak side/regime/session `0.25` | `-207.6342` | `1975` |

Reading:

- full shrink collapses score scale too much and reduces support.
- family-conditioned full shrink avoids some side switching but remains far below raw benchmark.
- weak shrink preserves scale but still worsens ranking and expands bad exposure.
- Direct multiplicative capture shrink is not the right policy overlay.

## Decision

Accepted:

- configurable prior context columns for exit-capture diagnostics and executable EV policy inputs
- partial capture shrink infrastructure for controlled ablations
- prior capture factor as a diagnostic/calibration feature

Rejected:

- hard blocking by prior exit-capture risk
- low executable EV threshold as an admission gate
- direct multiplicative score shrink overlay on raw cd15

Standard policy remains NoTrade.

Fixed diagnostic benchmark remains q95 + raw `loss_exit30_cd15`.

## Next

1. Treat capture ratio / capture failure as supervised targets, not as a direct multiplicative prior.
2. Train a supervised shrinkage head for realized/captured PnL using prior capture factor, loss-first probability, predicted holding, side confidence gap, regime/session/family, and fixed-horizon proxies.
3. Evaluate shrinkage as a model feature under chronological walk-forward and keep raw cd15 as frozen benchmark.
4. Keep no-edge entry as a separate rare-event target; do not conflate it with exit-capture failure.

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_executable_ev_calibration_diagnostics.py scripts/experiments/entry_ev_executable_ev_policy_inputs.py scripts/experiments/entry_ev_exit_capture_target_diagnostics.py`: OK
- `uv run python -m unittest tests.test_entry_ev_executable_ev_policy_inputs tests.test_entry_ev_executable_ev_calibration_diagnostics tests.test_entry_ev_exit_capture_target_diagnostics`: OK
- prior exit-capture risk diagnostics: OK
- executable EV calibration diagnostics: OK
- full side/regime/session shrink replay: OK
- full family/side/regime/session shrink replay: OK
- weak side/regime/session shrink replay: OK
