# Entry EV Replacement Quality Policy Inputs

日時: 2026-07-01 23:25 JST
更新日時: 2026-07-01 23:25 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00248の次アクションとして、`replacement_positive_quality_target` をprediction rowへ接続する `scripts/experiments/entry_ev_replacement_quality_policy_inputs.py` を追加した。
- replacement-only 43 rowsから、対象月より前だけで低容量bucket rateをfitし、long/short side rowへ `predicted_replacement_quality` を付与した。
- direction inversion riskは、replacement qualityが低い時だけ使うcombined scoreとして `direction_risk * (1 - replacement_quality)` をpenalty化した。
- `risk_pressure` quality headは chronological mean AUC `0.3542` と逆向きに近く、単体headとして弱い。`side_context` / `side_context_risk` も `0.4722` で強くない。
- fixed 2025-03..12 stateful replayでは、q99/floor5の最良は引き続きdirection s0.1 `-147.3314`。combined最良は `risk_pressure drbucket_or_global/qbucket_or_global s0.25` の `-156.6124` で及ばない。
- q95/floor5は `side_context drbucket_or_global/qbucket_or_global s0.25` が total `-156.9854` とside-prior `-160.8606` を僅かに上回ったが、min month `-223.9294`、max DD `223.9294` でNoTrade未満。
- 判断: replacement-quality prediction-row inputとcombined stateful replay infrastructureはaccepted。現行の `replacement_positive_quality_target` head と combined scoreは標準policyにしない。

## Artifacts

- Script: `scripts/experiments/entry_ev_replacement_quality_policy_inputs.py`
- Test: `tests/test_entry_ev_replacement_quality_policy_inputs.py`
- Replacement target source:
  - `data/reports/backtests/20260701_133922_20260701_entry_ev_common_loss_target_diagnostics_s1/replacement_targets.csv`
- Input generation:
  - `data/reports/backtests/20260701_141851_20260701_entry_ev_replacement_quality_policy_inputs_s1/`
  - `data/reports/backtests/20260701_142327_20260701_entry_ev_replacement_quality_side_context_policy_inputs_s1/`
- Fixed 2025 stateful replays:
  - `data/reports/backtests/20260701_142014_20260701_entry_ev_replacement_quality_combo_drbucket_qbucket_s0p5_fixed2025_03_12_trades_s1/`
  - `data/reports/backtests/20260701_142014_20260701_entry_ev_replacement_quality_combo_drbucket_qbucketorglobal_s0p5_fixed2025_03_12_trades_s1/`
  - `data/reports/backtests/20260701_142014_20260701_entry_ev_replacement_quality_combo_drbucketorglobal_qbucket_s0p5_fixed2025_03_12_trades_s1/`
  - `data/reports/backtests/20260701_142014_20260701_entry_ev_replacement_quality_combo_drbucketorglobal_qbucketorglobal_s0p25_fixed2025_03_12_trades_s1/`
  - `data/reports/backtests/20260701_142423_20260701_entry_ev_replacement_quality_side_context_combo_drbucket_qbucketorglobal_s0p5_fixed2025_03_12_trades_s1/`
  - `data/reports/backtests/20260701_142423_20260701_entry_ev_replacement_quality_side_context_combo_drbucketorglobal_qbucketorglobal_s0p25_fixed2025_03_12_trades_s1/`

## Method

Quality target:

```text
replacement_positive_quality_target = replacement_adjusted_pnl > 0
```

Primary quality spec:

```text
risk_pressure =
direction
selected_risk_bucket
selected_side_support_bucket
selected_side_pressure_bucket
```

Comparison quality specs:

```text
side_context = direction + combined_regime + session_regime
side_context_risk = side_context + selected_risk_bucket
```

Combined score:

```text
bad_replacement_penalty = direction_inversion_risk * (1 - replacement_quality)
combined_score = side_prior_pressure_s0p5_score * (1 - strength * bad_replacement_penalty)
```

Source modes:

| mode | meaning |
|---|---|
| `bucket` | bucket-supported prediction only; global/no-prior is neutral |
| `bucket_or_global` | bucket and global fallback are both used; no-prior is neutral |

No-prior defaults:

```text
direction risk = 0
replacement quality = 1
```

This means unknown replacement quality does not create a penalty.

## Target Calibration

Chronological calibration uses only prior months in `replacement_targets.csv`.

| quality spec | rows | target rate | mean AUC | mean Brier | bucket share |
|---|---:|---:|---:|---:|---:|
| `side_context` | `43` | `0.5349` | `0.4722` | `0.3057` | `0.3256` |
| `side_context_risk` | `43` | `0.5349` | `0.4722` | `0.3057` | `0.3256` |
| `risk_pressure` | `43` | `0.5349` | `0.3542` | `0.3005` | `0.6279` |

Reading:

- `risk_pressure` has higher bucket coverage but worse ranking, so it is not a reliable quality head.
- `side_context` is less wrong but still below useful discrimination.
- 43 replacement rows are too few for a stable low-capacity positive-quality head.

## Prediction Distribution

`risk_pressure` quality prediction:

| side | rows | quality mean | p10 | p50 | bucket share | global share | no-prior |
|---|---:|---:|---:|---:|---:|---:|---:|
| long | `351,190` | `0.5125` | `0.3361` | `0.4872` | `0.1792` | `0.5820` | `0.2388` |
| short | `351,190` | `0.4866` | `0.2758` | `0.4000` | `0.4859` | `0.2754` | `0.2388` |

`side_context` quality prediction:

| side | rows | quality mean | p10 | p50 | bucket share | global share | no-prior |
|---|---:|---:|---:|---:|---:|---:|---:|
| long | `351,190` | `0.5148` | `0.3846` | `0.4706` | `0.0657` | `0.6955` | `0.2388` |
| short | `351,190` | `0.5237` | `0.3846` | `0.4706` | `0.1644` | `0.5968` | `0.2388` |

The row-level distribution is dominated by global fallback for `side_context`, while `risk_pressure` has better support on short rows but worse target ranking.

## Fixed 2025 Results

Compared against side-prior baseline and direction s0.1 diagnostic baseline.

| run | candidate | total | min month | trades | max DD | max side share |
|---|---|---:|---:|---:|---:|---:|
| direction s0.1 | q99/floor5 | `-147.3314` | `-153.9192` | `50` | `153.9192` | `0.5800` |
| risk_pressure drbg/qbg s0.25 | q99/floor5 | `-156.6124` | `-162.1992` | `44` | `162.1992` | `0.6591` |
| risk_pressure drb/qbg s0.5 | q99/floor5 | `-171.6056` | `-153.9312` | `45` | `153.9312` | `0.5778` |
| risk_pressure drb/qb s0.5 | q99/floor5 | `-173.0804` | `-162.1992` | `46` | `162.1992` | `0.6522` |
| side_context drbg/qbg s0.25 | q99/floor5 | `-173.2000` | `-180.2748` | `46` | `180.2748` | `0.6522` |
| side-prior | q99/floor5 | `-177.3790` | `-162.1992` | `53` | `162.1992` | `0.5849` |
| risk_pressure drbg/qb s0.5 | q99/floor5 | `-188.4116` | `-173.9460` | `45` | `173.9460` | `0.6667` |
| side_context drb/qbg s0.5 | q99/floor5 | `-188.6072` | `-153.9312` | `45` | `153.9312` | `0.5778` |
| side_context drbg/qbg s0.25 | q95/floor5 | `-156.9854` | `-223.9294` | `65` | `223.9294` | `0.6308` |
| side-prior | q95/floor5 | `-160.8606` | `-233.2854` | `80` | `233.2854` | `0.6000` |
| direction s0.1 | q95/floor5 | `-163.3410` | `-206.7934` | `73` | `207.6746` | `0.5890` |
| risk_pressure drbg/qbg s0.25 | q95/floor5 | `-175.5026` | `-225.4834` | `66` | `225.4834` | `0.6364` |
| risk_pressure drbg/qb s0.5 | q95/floor5 | `-252.7062` | `-217.8026` | `68` | `217.8026` | `0.6471` |
| risk_pressure drb/qb s0.5 | q95/floor5 | `-315.9344` | `-233.2854` | `72` | `233.2854` | `0.6250` |
| risk_pressure drb/qbg s0.5 | q95/floor5 | `-316.1104` | `-209.1814` | `66` | `209.1814` | `0.5606` |
| side_context drb/qbg s0.5 | q95/floor5 | `-340.3600` | `-209.1814` | `67` | `209.1814` | `0.5672` |

Abbreviations:

```text
drb  = direction risk source bucket
drbg = direction risk source bucket_or_global
qb   = replacement quality source bucket
qbg  = replacement quality source bucket_or_global
```

## Decision

Accepted:

- Replacement positive-quality prediction-row input generation.
- Source-aware `bucket` vs `bucket_or_global` handling.
- Combined stateful score replay that uses direction risk only through low replacement quality.
- Unit coverage for the new input-generation path.

Not accepted:

- `replacement_positive_quality_target` as currently defined as a standard head.
- `risk_pressure` replacement quality as a direct selector feature.
- Any tested combined replacement-quality score as standard policy.
- Treating q95's small total improvement as meaningful while min month and DD remain deeply negative.

Standard policy remains NoTrade.

## Next

1. Do not tune replacement quality strength further on this fixed 2025 window.
2. Reframe replacement quality from binary positive PnL to a richer target: replacement value over stay-flat, replacement regret, or candidate-only replacement downside.
3. Return to q99 direction s0.1 residual common losses: `down_normal_vol/london`, `range_normal_vol/ny_overlap`, `down_normal_vol/rollover`.
4. Split exit capture into narrower heads before combining: same-side missed profit, forced-exit loss, predicted hold mismatch.
5. Keep global fallback source as a diagnostic feature, but avoid direct score use unless it passes stateful replay across a separate validation window.

## Verification

- `python3 -m py_compile scripts/experiments/entry_ev_replacement_quality_policy_inputs.py tests/test_entry_ev_replacement_quality_policy_inputs.py`: OK
- `python3 -m unittest tests.test_entry_ev_replacement_quality_policy_inputs`: OK
- `risk_pressure` replacement-quality input generation: OK
- `side_context` replacement-quality input generation: OK
- Fixed 2025 stateful replays for six combined configurations: OK
