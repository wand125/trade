# Entry EV Context Calibration Sweep

日時: 2026-07-01 08:16 JST
更新日時: 2026-07-01 08:16 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00242で得た「EV-overestimate high-riskはside/contextで反転する」という結果を、低容量calibration specとして比較する `scripts/experiments/entry_ev_context_calibration_sweep.py` を追加した。
- `base`, `side`, `side_drift`, `side_prior_pressure`, `full_context` を同じ chronological month / role holdout 指標で比較した。
- 最も良かったのは `side_prior_pressure = direction + support_bucket + pressure_bucket + prior_support_bucket + feature_pressure_bucket`。
- `side_drift` と `full_context` はbucketが細かくなりすぎ、chronological / role holdout のAUCが大きく悪化した。
- 判断: `side_prior_pressure` を次のEV-overestimate calibration / ranking headの候補にする。`side_drift_bucket` をbucket keyへ直接入れるのは現データ量では採用しない。

## Artifacts

- Script: `scripts/experiments/entry_ev_context_calibration_sweep.py`
- Test: `tests/test_entry_ev_context_calibration_sweep.py`
- Input:
  - `data/reports/backtests/20260630_145606_20260630_entry_ev_composite_target_decomposition_s1/component_trade_targets.csv`
- Diagnostic artifact:
  - `data/reports/backtests/20260630_231603_20260701_entry_ev_context_calibration_sweep_s2/`

Outputs:

```text
calibration_specs.csv
context_calibration_metric_summary.csv
context_calibration_fold_metrics.csv
context_calibration_predictions.csv
validation_role_month_context_risk.csv
validation_candidate_context_risk_summary.csv
validation_pointwise_context_screen_effects.csv
config.json
```

## Method

Target:

```text
executable_ev_overestimate_target
```

Specs:

| spec | columns |
|---|---|
| `base` | `support_bucket`, `pressure_bucket` |
| `side` | `direction`, `support_bucket`, `pressure_bucket` |
| `side_drift` | `direction`, `support_bucket`, `pressure_bucket`, `side_drift_bucket` |
| `side_prior_pressure` | `direction`, `support_bucket`, `pressure_bucket`, `prior_support_bucket`, `feature_pressure_bucket` |
| `full_context` | `direction`, `support_bucket`, `pressure_bucket`, `prior_support_bucket`, `feature_pressure_bucket`, `side_drift_bucket` |

Chronological month uses only earlier months for the fold. Role holdout trains on the other roles. Validation candidate summaries use chronological predictions only.

Pointwise screens zero-fill role/month groups that become empty after screening. They still do not model one-position replacement.

## Calibration Result

| spec | fold | brier | AUC | bucket share | global share |
|---|---|---:|---:|---:|---:|
| `side_prior_pressure` | chronological | `0.2753` | `0.7261` | `0.2696` | `0.2348` |
| `base` | chronological | `0.2862` | `0.6741` | `0.3478` | `0.1565` |
| `side` | chronological | `0.2974` | `0.6807` | `0.3043` | `0.2000` |
| `full_context` | chronological | `0.3043` | `0.3489` | `0.0870` | `0.4174` |
| `side_drift` | chronological | `0.3235` | `0.3102` | `0.1217` | `0.3826` |
| `side_prior_pressure` | role holdout | `0.2589` | `0.7015` | `0.8000` | `0.2000` |
| `base` | role holdout | `0.2676` | `0.6401` | `0.9304` | `0.0696` |
| `side` | role holdout | `0.2740` | `0.6134` | `0.8348` | `0.1652` |
| `full_context` | role holdout | `0.2787` | `0.4903` | `0.5826` | `0.4174` |
| `side_drift` | role holdout | `0.2978` | `0.3883` | `0.6522` | `0.3478` |

Reading:

- `side_prior_pressure` improves both chronological and role-holdout AUC versus `base`.
- Adding `direction` alone improves chronological AUC slightly but hurts role holdout.
- Adding `side_drift_bucket` directly overfits badly. The signal seen in 00242 should be used later as a feature or regularized interaction, not as a sparse bucket key in this small dataset.

## Pointwise Screen Diagnostic

These are diagnostic only. They remove selected trades without replacement replay.

For `side_prior_pressure`, q99/floor5 at threshold `0.50`:

| candidate | removed trades | removed pnl | kept trades | kept total | kept min role | kept min month |
|---|---:|---:|---:|---:|---:|---:|
| `q99_sg95_rank90_floor5_side_regime_session_month` | `14` | `-60.0334` | `15` | `+49.8048` | `+0.1230` | `0.0000` |

For `side_prior_pressure`, q95/floor5:

| threshold | removed trades | removed pnl | kept trades | kept total | kept min role | kept min month |
|---:|---:|---:|---:|---:|---:|---:|
| `0.45` | `29` | `-33.7216` | `24` | `+48.3354` | `0.0000` | `0.0000` |
| `0.50` | `26` | `-69.3132` | `27` | `+83.9270` | `-11.7284` | `-11.7284` |
| `0.55` | `17` | `-59.9888` | `36` | `+74.6026` | `-13.9484` | `-11.7284` |

The q99/floor5 threshold `0.50` screen is a useful near-miss clue, but it is still not a policy. It may allow replacement trades in a true stateful replay, and those replacement trades can recreate losses.

## Decision

Accepted:

- Context calibration sweep infrastructure.
- `side_prior_pressure` as the next low-capacity EV-overestimate calibration spec.
- Zero-filled role/month accounting for pointwise screens.

Not accepted:

- `side_drift` or `full_context` as direct bucket keys with the current small dataset.
- Any pointwise screen as a policy.
- Treating the q99/floor5 near-miss as a standard candidate before replacement-aware replay.

Standard policy remains NoTrade.

## Next

1. Attach the `side_prior_pressure` EV-overestimate risk to prediction rows.
2. Use it as a rank / score calibration penalty, not a hard block first.
3. Run one-position stateful replay for q99/floor5 and q95/floor5 with this risk feature.
4. Compare against NoTrade and prior diagnostic baselines with zero-filled role/month accounting.

## Verification

- `python3 -m py_compile scripts/experiments/entry_ev_context_calibration_sweep.py tests/test_entry_ev_context_calibration_sweep.py`: OK
- `python3 -m unittest tests.test_entry_ev_context_calibration_sweep`: OK
- Context calibration sweep run: OK
