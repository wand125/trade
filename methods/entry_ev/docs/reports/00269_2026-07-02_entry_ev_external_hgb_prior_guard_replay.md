# Entry EV External HGB Prior Guard Replay

日時: 2026-07-02 04:01 JST
更新日時: 2026-07-02 04:01 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00268でrank緩和をrejectしたため、次は同じq99/floor5/rank90方針を別familyへ固定適用した。
- `entry_ev_validation_inventory.py` を再実行し、既存entry-EV sweepでclean full-rank validationとして再利用できるのは既知の `2024-03..04` と `2025-01..02` だけだと確認した。
- そこで、既存の標準HGB predictionを外部family preflightとして使い、exit-regret selector / pre-block side-gap / prior `direction_regime` guardを固定適用した。
- `scripts/experiments/entry_ev_base_policy_input_aliases.py` を追加し、生HGB predictionへ quantile列、`pred_mlp_*exit_event_minutes` alias、ゼロのbase risk列を付けられるようにした。
- 外部HGB q99/floor5/rank90はsupport不足ではない。HGB 2024-03..06では142 candidate rows / 58 episodes / 4 active months。
- しかしstateful replayは HGB 2024-03..06 `-36.1556`, HGB 2025-08 `+26.5800`, overall `-9.5756` でNoTrade未満。
- prior guardはHGB 2025-08で1 candidate rowをblockしたが、実行trade経路はno-guardと同一だった。
- 判断: base alias infrastructureはaccepted。外部HGB fixed replayはq99 prior guardの標準採用を支持しない。標準policyはNoTrade。

## Artifacts

- Added script:
  - `scripts/experiments/entry_ev_base_policy_input_aliases.py`
- Added test:
  - `tests/test_entry_ev_base_policy_input_aliases.py`
- Validation inventory refresh:
  - `data/reports/backtests/20260701_185401_20260702_entry_ev_validation_inventory_refresh_s1/`
- External HGB base inputs:
  - `data/reports/backtests/20260701_185903_20260702_entry_ev_external_hgb_base_inputs_s1/`
- External HGB exit-regret risk:
  - `data/reports/backtests/20260701_185915_20260702_entry_ev_external_hgb_exit_regret_risk_s1/`
- External HGB selector inputs:
  - `data/reports/backtests/20260701_185935_20260702_entry_ev_external_hgb_preblock_selector_t0p4_s1/`
  - `data/reports/backtests/20260701_185935_20260702_entry_ev_external_hgb_postblock_selector_t0p4_s1/`
- External HGB prior guard inputs:
  - `data/reports/backtests/20260701_185956_20260702_entry_ev_external_hgb_prior_guard_inputs_s1/`
- External HGB replay:
  - `data/reports/backtests/20260701_190022_20260702_entry_ev_external_hgb_q99_preblock_noguard_s1/`
  - `data/reports/backtests/20260701_190022_20260702_entry_ev_external_hgb_q99_prior_guard_s1/`
- External HGB support/admission:
  - `data/reports/backtests/20260701_190056_20260702_entry_ev_external_hgb_q99_support_s1/`
  - `data/reports/backtests/20260701_190055_20260702_entry_ev_external_hgb_q99_episode_support_s1/`
  - `data/reports/backtests/20260701_190055_20260702_entry_ev_external_hgb_q99_prior_guard_admission_s1/`

## Inventory

`entry_ev_validation_inventory.py` refresh:

| status | windows |
|---|---|
| usable full-rank validation | `2024-03..04`, `2025-01..02` |
| fixed/not reusable for same audit | `2024-05..12`, `2025-03..12` |
| calibration/not clean holdout | `2024-01..02` |

Reading:

- Local artifacts do not contain a fresh independent full pipeline chronology beyond the windows already used.
- The HGB replay below is an external-family preflight, not a clean promotion test.

## Base Inputs

External HGB families:

| family | months | rows | selected score q99 | holding missing |
|---|---|---:|---:|---:|
| hgb2024_0306 | `2024-03..06` | `116918` | `16.8183` | `0` |
| hgb2025_08 | `2025-08` | `28971` | `33.5306` | `0` |

The alias script writes:

- `pred_mlp_long_exit_event_minutes`
- `pred_mlp_short_exit_event_minutes`
- `pred_base_long_predicted_ev_overestimate_risk = 0`
- `pred_base_short_predicted_ev_overestimate_risk = 0`
- quantile columns for `base_calibrated`

This lets existing exit-regret selector scripts run on HGB-only predictions without changing their internal contracts.

## Exit-Regret Risk

Fixed target/spec:

```text
target: same_side_large_regret_loss_target
risk spec: confidence_exit
threshold: 0.4
replacement guard buckets: strong, nonpositive
side-gap quantile: pre_block
```

Calibration summary:

| risk spec | folds | rows | target rate | mean AUC | mean brier | bucket share |
|---|---:|---:|---:|---:|---:|---:|
| confidence_exit | `16` | `215` | `0.2512` | `0.7106` | `0.1938` | `0.4837` |

Risk distribution:

| family | side | risk mean | bucket share | global share |
|---|---|---:|---:|---:|
| hgb2024_0306 | long | `0.1376` | `0.5000` | `0.5000` |
| hgb2024_0306 | short | `0.1130` | `0.4094` | `0.5906` |
| hgb2025_08 | long | `0.2848` | `0.7665` | `0.2335` |
| hgb2025_08 | short | `0.2431` | `0.2828` | `0.7172` |

## Prior Guard Inputs

q99/floor5/rank90:

| family | pre pass | post pass | newly admitted | newly admitted short | blocked rows |
|---|---:|---:|---:|---:|---:|
| hgb2024_0306 | `142` | `46` | `102` | `102` | `0` |
| hgb2025_08 | `11` | `12` | `1` | `1` | `1` |

The prior context guard is mostly inactive in this external HGB preflight. It has no executed-trade effect in the replay below.

## Replay

q99/floor5/rank90 pre-block no-guard and prior-guard are identical:

| family | total pnl | worst month | trades | max DD | max side share |
|---|---:|---:|---:|---:|---:|
| hgb2024_0306 | `-36.1556` | `-56.1766` | `31` | `56.1766` | `0.6452` |
| hgb2025_08 | `+26.5800` | `+26.5800` | `4` | `0.0000` | `0.7500` |
| overall | `-9.5756` | `-56.1766` | `35` | `56.1766` | `0.6571` |

Admission with two external roles:

| candidate | eligible | blockers |
|---|---|---|
| q99/floor5/rank90 | false | `positive_roles_low;total_pnl_below_floor;role_total_pnl_below_floor;month_pnl_below_floor` |

## Support

Candidate support:

| family | candidate rows | long rows | short rows |
|---|---:|---:|---:|
| hgb2024_0306 | `142` | `21` | `121` |
| hgb2025_08 | `11` | `1` | `10` |

Episode support:

| family | rows | episodes | active months | max episode rows | long episodes | short episodes |
|---|---:|---:|---:|---:|---:|---:|
| hgb2024_0306 | `142` | `58` | `4` | `20` | `13` | `45` |
| hgb2025_08 | `11` | `7` | `1` | `4` | `1` | `6` |

Reading:

- Unlike 00268 fresh2024, the HGB 2024 window has broad enough row/episode support.
- The failure is PnL/regime robustness, not a sparse candidate-row artifact.
- HGB 2025-08 is positive but too small to offset HGB 2024-03..06.

## Decision

Accepted:

- base policy input alias infrastructure
- external HGB replay as a diagnostic preflight
- keeping support diagnostics at row/episode/trade levels

Rejected:

- q99 prior guard standard promotion
- interpreting HGB 2025-08 positive PnL as sufficient
- treating prior guard as universally effective

Standard policy remains NoTrade.

## Next

1. Generate a true independent full pipeline chronology if standard promotion is desired; raw HGB alias replay is only a preflight.
2. Keep q99 prior guard frozen; do not tune thresholds to rescue HGB 2024.
3. Diagnose HGB 2024-03..06 losses by context only as an explanatory step, not as a new blacklist source.
4. Prefer adding/newly generating windows over lowering q/rank/floor thresholds on the same family.

## Verification

- `python3 -m unittest tests.test_entry_ev_base_policy_input_aliases`: OK
- `python3 -m py_compile scripts/experiments/entry_ev_base_policy_input_aliases.py tests/test_entry_ev_base_policy_input_aliases.py`: OK
- validation inventory refresh: OK
- external HGB base input generation: OK
- external HGB exit-regret risk input generation: OK
- pre/post selector input generation: OK
- prior guard input generation: OK
- no-guard and prior-guard q99 replay: OK
- support, episode, and admission diagnostics: OK
