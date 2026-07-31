# Entry EV Direction Inversion Policy Inputs

日時: 2026-07-01 22:57 JST
更新日時: 2026-07-01 22:57 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00246で有望だった `direction_side_inversion_target` をprediction rowへ接続する `scripts/experiments/entry_ev_direction_inversion_policy_inputs.py` を追加した。
- 00246のcommon-entry targetから、対象月より前だけで `direction + selected_risk_bucket + support_bucket + pressure_bucket` の低容量bucket rateをfitし、long/short side rowへ `predicted_direction_inversion_risk` を付与した。
- 00246でglobal fallback high-risk rowsが利益側にも出ていたため、score penaltyは既定でbucket-supported riskだけに適用し、global/no-prior rowsは `no_prior_risk=0` として扱った。
- fixed 2025-03..12では、s0.1がq99/floor5を `-177.3790 -> -147.3314` に改善した。q95/floor5は `-160.8606 -> -163.3410` とほぼ横ばい。
- s0.25はq99/floor5 `-159.2316` と改善するがq95/floor5 `-292.1924` を大きく悪化。s0.5はq99/floor5 `-204.4412` と過剰penalty。
- path診断では、s0.1 q99の改善はreplacement差 `+33.5480` が主で、common-entry差は `-3.5004` と小さい。s0.25ではreplacement差 `+76.2274` の一方でcommon-entry差 `-58.0800` が大きく悪化した。
- 判断: direction inversion risk prediction-row接続はaccepted。direct score penaltyは標準policyにしない。s0.1はdiagnostic baselineとして残し、次はcandidate selector/ranking feature化、またはreplacement qualityとの併用へ進む。

## Artifacts

- Script: `scripts/experiments/entry_ev_direction_inversion_policy_inputs.py`
- Test: `tests/test_entry_ev_direction_inversion_policy_inputs.py`
- Common target source:
  - `data/reports/backtests/20260701_133922_20260701_entry_ev_common_loss_target_diagnostics_s1/common_entry_targets.csv`
- Input generation:
  - `data/reports/backtests/20260701_134903_20260701_entry_ev_direction_inversion_policy_inputs_s1/`
  - `data/reports/backtests/20260701_135325_20260701_entry_ev_direction_inversion_policy_inputs_s0p1_s1/`
- Fixed backtests:
  - `data/reports/backtests/20260701_135349_20260701_entry_ev_direction_inversion_s0p1_fixed2025_03_12_trades_s1/`
  - `data/reports/backtests/20260701_134936_20260701_entry_ev_direction_inversion_s0p25_fixed2025_03_12_trades_s1/`
  - `data/reports/backtests/20260701_135129_20260701_entry_ev_direction_inversion_s0p5_fixed2025_03_12_trades_s1/`
- Path diagnostics:
  - `data/reports/backtests/20260701_135644_20260701_entry_ev_direction_inversion_s0p1_path_diagnostics_s1/`
  - `data/reports/backtests/20260701_135308_20260701_entry_ev_direction_inversion_s0p25_path_diagnostics_s1/`

## Method

Input prediction file:

```text
data/reports/backtests/20260630_232706_20260701_entry_ev_side_prior_pressure_policy_inputs_s1/enriched_predictions/refit2025_predictions_side_prior_pressure.parquet
```

Target:

```text
direction_side_inversion_target
```

Group:

```text
direction
selected_risk_bucket
selected_side_support_bucket
selected_side_pressure_bucket
```

Prediction-row side features:

```text
selected_risk_bucket = bucket(pred_side_prior_pressure_{side}_predicted_ev_overestimate_risk)
support_bucket = pred_side_prior_pressure_{side}_support_bucket
pressure_bucket = pred_side_prior_pressure_{side}_pressure_bucket
```

Score:

```text
base_score = side_prior_pressure_s0p5 score
score_scale = clip(1 - strength * bucket_supported_direction_inversion_risk, 0, 1)
direction_inversion_score = base_score * score_scale
```

Important:

- `direction_inversion_prediction_source == bucket` の行だけpenaltyに使う。
- `global` / `no_prior` はrisk列として残すが、score penaltyには使わない。
- これはstandard policyではなく、ranking/selector feature化のためのdiagnostic input。

## Risk Distribution

s0.1 input generation:

| family | side | rows | risk mean | p50 | p90 | bucket share | global share | no-prior share |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| refit2025 | long | `351,190` | `0.5976` | `0.6250` | `0.8182` | `0.4465` | `0.3148` | `0.2388` |
| refit2025 | short | `351,190` | `0.6447` | `0.6250` | `0.8182` | `0.2231` | `0.5382` | `0.2388` |

Bucket-supported risk only:

| score kind | strength | long scale mean | short scale mean | long risk mean used | short risk mean used |
|---|---:|---:|---:|---:|---:|
| `direction_inversion_bucket_s0p1` | `0.1` | `0.9756` | `0.9853` | `0.2441` | `0.1470` |
| `direction_inversion_bucket_s0p25` | `0.25` | `0.9390` | `0.9632` | `0.2441` | `0.1470` |
| `direction_inversion_bucket_s0p5` | `0.5` | `0.8779` | `0.9265` | `0.2441` | `0.1470` |

The risk estimate is high on global rows, but those rows are intentionally not penalized in this experiment.

## Fixed 2025 Results

Compared against 00244 `side_prior_pressure_s0p5` fixed 2025-03..12.

| run | candidate | total | min month | trades | max DD | max side share |
|---|---|---:|---:|---:|---:|---:|
| side_prior | q99/floor5 | `-177.3790` | `-162.1992` | `53` | `162.1992` | `0.5849` |
| dir s0.1 | q99/floor5 | `-147.3314` | `-153.9192` | `50` | `153.9192` | `0.5800` |
| dir s0.25 | q99/floor5 | `-159.2316` | `-153.3172` | `46` | `153.3172` | `0.5652` |
| dir s0.5 | q99/floor5 | `-204.4412` | `-154.6852` | `41` | `154.6852` | `0.5122` |
| side_prior | q95/floor5 | `-160.8606` | `-233.2854` | `80` | `233.2854` | `0.6000` |
| dir s0.1 | q95/floor5 | `-163.3410` | `-206.7934` | `73` | `207.6746` | `0.5890` |
| dir s0.25 | q95/floor5 | `-292.1924` | `-225.1554` | `67` | `225.1554` | `0.5821` |
| dir s0.5 | q95/floor5 | `-288.7030` | `-192.7518` | `55` | `192.7518` | `0.5273` |

Reading:

- s0.1 improves q99 total and worst month slightly, but remains well below NoTrade.
- q95 does not improve total. s0.1 reduces worst month / DD, but total stays negative.
- Larger strengths lower side concentration but damage total, especially q95.

## Path Diagnostics

s0.1 vs side-prior:

| candidate | common entry delta | replacement delta | total delta | base trades | candidate trades |
|---|---:|---:|---:|---:|---:|
| q99/floor5 | `-3.5004` | `+33.5480` | `+30.0476` | `53` | `50` |
| q95/floor5 | `-17.8304` | `+15.3500` | `-2.4804` | `80` | `73` |

s0.25 vs side-prior:

| candidate | common entry delta | replacement delta | total delta | base trades | candidate trades |
|---|---:|---:|---:|---:|---:|
| q99/floor5 | `-58.0800` | `+76.2274` | `+18.1474` | `53` | `46` |
| q95/floor5 | `-67.8314` | `-63.5004` | `-131.3318` | `80` | `67` |

The signal helps replacement choice, especially q99, but direct penalty can damage common-entry outcomes. This matches the earlier warning that direction inversion risk should first be a selector/ranking feature rather than a hard score multiplier.

## Decision

Accepted:

- Direction inversion risk prediction-row connection.
- Bucket-supported risk/source/support columns.
- Quantile columns for direction-inversion-adjusted score.
- s0.1 as a diagnostic baseline.

Not accepted:

- `direction_inversion_bucket_s0p1` as standard policy.
- Stronger direct penalties `s0.25` / `s0.5`.
- Applying global fallback risk directly to score.
- Treating direction inversion risk as a hard block.

Standard policy remains NoTrade.

## Next

1. Use direction inversion risk as candidate-level selector/ranking feature instead of direct score penalty.
2. Combine with `replacement_positive_quality_target` so replacement improvement does not create new common-entry loss.
3. Add source-aware constraints: bucket-supported high risk and global high risk must be separated.
4. Diagnose q99 s0.1 residual common losses: `down_normal_vol/london`, `range_normal_vol/ny_overlap`, `down_normal_vol/rollover`.
5. Keep s0.1 as the next comparison baseline, not as an adoptable policy.

## Verification

- `python3 -m py_compile scripts/experiments/entry_ev_direction_inversion_policy_inputs.py tests/test_entry_ev_direction_inversion_policy_inputs.py`: OK
- `python3 -m unittest tests.test_entry_ev_direction_inversion_policy_inputs`: OK
- Direction inversion input generation: OK
- Fixed 2025 stateful backtests for s0.1/s0.25/s0.5: OK
- s0.1/s0.25 path diagnostics: OK
