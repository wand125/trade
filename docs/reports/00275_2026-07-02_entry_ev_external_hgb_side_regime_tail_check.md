# Entry EV External HGB Side Regime Tail Check

日時: 2026-07-02 08:36 JST
更新日時: 2026-07-02 08:36 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00274の次アクションとして、`direction_regime` tail-risk headを別chronologyの00269 external HGB preflightへ固定適用した。
- 途中で、tail-risk score生成時に既存pre-block side-gap quantileが引き継がれず、priorなしのHGB 2024側までtrade pathが変わる不整合を発見した。
- `scripts/experiments/entry_ev_side_regime_tail_policy_inputs.py` に `--side-gap-source-score-kind` を追加し、既存score kindの `side_gap_pct_*` を新score kindへコピーできるようにした。
- 修正後、HGB 2024-03..06はno-priorで完全にno-opになり、00269 baselineと同一の `-36.1556`, 31 tradesに戻った。
- HGB 2025-08では、`exit_capture_failure_target` s0.1が `+26.5800 -> +26.9600` と小幅改善しただけ。`direction_side_inversion_target` s0.25は `+18.5300` へ悪化した。
- overallは baseline `-9.5756` に対し exit-cap s0.1 `-9.1956`、dir-inv s0.25 `-17.6256`。admissionはNoTrade。
- 判断: 00274のcoarse tail-risk headは外部HGB chronologyでは再現的な改善を示さない。side-gap継承オプションはaccepted infrastructure。標準policyはNoTrade。

## Artifacts

- Updated script:
  - `scripts/experiments/entry_ev_side_regime_tail_policy_inputs.py`
- Updated test:
  - `tests/test_entry_ev_side_regime_tail_policy_inputs.py`
- Corrected input generation:
  - `data/reports/backtests/20260701_233448_20260702_entry_ev_external_hgb_side_regime_dirinv_tail_inputs_sidegapcopy_s1/`
  - `data/reports/backtests/20260701_233448_20260702_entry_ev_external_hgb_side_regime_exitcap_tail_inputs_sidegapcopy_s1/`
- Corrected replay:
  - `data/reports/backtests/20260701_233509_20260702_entry_ev_external_hgb_side_regime_dirinv_s0p25_sidegapcopy_replay_s1/`
  - `data/reports/backtests/20260701_233509_20260702_entry_ev_external_hgb_side_regime_exitcap_s0p1_sidegapcopy_replay_s1/`
- Admission:
  - `data/reports/backtests/20260701_233544_20260702_entry_ev_external_hgb_side_regime_exitcap_s0p1_sidegapcopy_admission_match_s1/`
- Support:
  - `data/reports/backtests/20260701_233534_20260702_entry_ev_external_hgb_side_regime_exitcap_s0p1_sidegapcopy_support_s1/`
- Trade enrichment:
  - `data/reports/backtests/20260701_233601_20260702_entry_ev_external_hgb_side_regime_exitcap_s0p1_sidegapcopy_trade_enrichment_s1/`
- Delta:
  - `data/reports/backtests/20260701_233617_20260702_entry_ev_external_hgb_side_regime_exitcap_s0p1_hgb2025_delta_s1/`

## Method

Fixed settings from 00274:

```text
direction_regime = direction + combined_regime
dir-inv:  target=direction_side_inversion_target, strength=0.25
exit-cap: target=exit_capture_failure_target, strength=0.10
candidate: q99_sg95_rank90_floor5_side_regime_session_month
```

The correction:

```text
--side-gap-source-score-kind exit_regret_selector_replguard_preblockgap_confidenceexit_bucket_t0p4
```

This preserves the 00269 pre-block side-gap quantile gate while recalculating selected-score quantiles for the tail-risk-adjusted score.

Why this matters:

- HGB 2024-03..06 is earlier than the common target history, so `tail_prediction_source=no_prior`.
- With no prior and bucket-only penalty, score scaling is neutral.
- Therefore HGB 2024 should be no-op. If it changes, the experiment is confounded by side-gap quantile recomputation rather than tail-risk.

## Risk Distribution

Corrected `direction_regime` / dir-inv:

| family | side | risk mean | support mean | bucket share | global share | no-prior |
|---|---|---:|---:|---:|---:|---:|
| hgb2024_0306 | long |  | `0.0000` | `0.0000` | `0.0000` | `1.0000` |
| hgb2024_0306 | short |  | `0.0000` | `0.0000` | `0.0000` | `1.0000` |
| hgb2025_08 | long | `0.6359` | `3.3654` | `0.8107` | `0.1893` | `0.0000` |
| hgb2025_08 | short | `0.6353` | `0.7962` | `0.3602` | `0.6398` | `0.0000` |

Corrected `direction_regime` / exit-cap:

| family | side | risk mean | support mean | bucket share | global share | no-prior |
|---|---|---:|---:|---:|---:|---:|
| hgb2024_0306 | long |  | `0.0000` | `0.0000` | `0.0000` | `1.0000` |
| hgb2024_0306 | short |  | `0.0000` | `0.0000` | `0.0000` | `1.0000` |
| hgb2025_08 | long | `0.8479` | `3.3654` | `0.8107` | `0.1893` | `0.0000` |
| hgb2025_08 | short | `0.7823` | `0.7962` | `0.3602` | `0.6398` | `0.0000` |

## Replay

Compared with 00269 pre-block no-guard q99:

| run | role | total | worst month | trades | max DD | max side share |
|---|---|---:|---:|---:|---:|---:|
| 00269 base | hgb2024_0306 | `-36.1556` | `-56.1766` | `31` | `56.1766` | `0.6452` |
| dir-inv s0.25 | hgb2024_0306 | `-36.1556` | `-56.1766` | `31` | `56.1766` | `0.6452` |
| exit-cap s0.1 | hgb2024_0306 | `-36.1556` | `-56.1766` | `31` | `56.1766` | `0.6452` |
| 00269 base | hgb2025_08 | `+26.5800` | `+26.5800` | `4` | `0.0000` | `0.7500` |
| dir-inv s0.25 | hgb2025_08 | `+18.5300` | `+18.5300` | `3` | `0.0000` | `0.6667` |
| exit-cap s0.1 | hgb2025_08 | `+26.9600` | `+26.9600` | `4` | `0.0000` | `0.7500` |

Overall:

| run | total | worst month | trades | max DD | max side share |
|---|---:|---:|---:|---:|---:|
| 00269 base | `-9.5756` | `-56.1766` | `35` | `56.1766` | `0.6571` |
| dir-inv s0.25 | `-17.6256` | `-56.1766` | `34` | `56.1766` | `0.6471` |
| exit-cap s0.1 | `-9.1956` | `-56.1766` | `35` | `56.1766` | `0.6571` |

Reading:

- The HGB 2024 no-prior branch is now a true no-op, validating the side-gap copy fix.
- The only possible improvement comes from HGB 2025-08.
- The best improvement is `+0.3800`, too small to matter and not enough to offset HGB 2024 losses.

## Support And Admission

Best branch support, exit-cap s0.1:

| family | quantile all | quantile hold | candidate rows | long rows | short rows |
|---|---:|---:|---:|---:|---:|
| hgb2024_0306 | `142` | `142` | `142` | `21` | `121` |
| hgb2025_08 | `11` | `11` | `11` | `1` | `10` |

Admission with 00269-matched gates:

| eligible | blockers | total | min role total | min month | trades | max side share |
|---|---|---:|---:|---:|---:|---:|
| false | `positive_roles_low;total_pnl_below_floor;role_total_pnl_below_floor;month_pnl_below_floor` | `-9.1956` | `-36.1556` | `-56.1766` | `35` | `0.6571` |

Selected policy:

```text
no_trade
```

## Trade Enrichment

Best branch, exit-cap s0.1:

| family | trades | total | win rate | direction error | exit regret sum | EV overestimate mean | exit capture ratio mean |
|---|---:|---:|---:|---:|---:|---:|---:|
| hgb2024_0306 | `31` | `-36.1556` | `0.4516` | `0.3548` | `751.5366` | `15.0224` | `0.0655` |
| hgb2025_08 | `4` | `+26.9600` | `1.0000` | `0.0000` | `49.3630` | `18.2931` | `0.3589` |

HGB 2025-08 delta vs 00269:

| base trades | candidate trades | base pnl | candidate pnl | delta | removed positive | added positive |
|---:|---:|---:|---:|---:|---:|---:|
| `4` | `4` | `+26.5800` | `+26.9600` | `+0.3800` | `0.0000` | `0.0000` |

The delta shows no meaningful replacement effect. This is not a new robust edge.

## Decision

Accepted:

- `--side-gap-source-score-kind` in side-regime tail input generation.
- no-prior no-op check as a required diagnostic when layering score heads after a selector.
- HGB fixed-apply result as a negative/weak replication check.

Rejected:

- treating 00274's q99 positive result as externally replicated.
- promoting `direction_regime` tail-risk head to standard policy.
- further threshold tuning on HGB 2025-08, which is a single positive month.

Standard policy remains NoTrade.

## Next

1. Keep `direction_regime` tail-risk as a diagnostic feature candidate, not a policy candidate.
2. Re-run 00274-style positive result with side-gap inheritance if it is used as evidence later.
3. Move the main branch to exit timing / exit regret reduction, because HGB 2024 losses and 00274 residual trades still have large exit regret.
4. Prefer broader chronology or more data before evaluating another tail-risk gate.

## Verification

- `python3 -m py_compile scripts/experiments/entry_ev_side_regime_tail_policy_inputs.py tests/test_entry_ev_side_regime_tail_policy_inputs.py`: OK
- `python3 -m unittest tests.test_entry_ev_side_regime_tail_policy_inputs`: OK
- corrected HGB side-regime tail input generation: OK
- corrected q99 stateful replays: OK
- support/admission/trade enrichment/delta diagnostics: OK
