# Entry EV Exit Regret Replacement Guard Replay

日時: 2026-07-02 02:28 JST
更新日時: 2026-07-02 02:28 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00260の `conf_gap_extreme` replacement-risk screenを、実際のselector inputへ接続してstateful replayした。
- `entry_ev_forced_exit_selector_inputs.py` に `--replacement-guard-conf-gap-buckets` を追加した。
- guardの動作は、exit-regret riskで片側がblockされ、残った反対側の `side_confidence_gap_bucket` が `strong` または `nonpositive` のときだけ、その反対側もblockする。exit-regret thresholdは `t0.4` のまま変更していない。
- broad replayでは q99/floor5 が `+18.9072 -> +27.1222`、q95/floor5 が `-30.2972 -> +63.5468` に改善した。
- fixed 2025-03..12 replayでは q99/floor5 が `+19.1218 -> +27.3368`、q95/floor5 が `-67.8612 -> +25.9828` に改善した。
- guard vs no-guard deltaでは、q95/floor5の改善が大きく broad/fixed とも `+93.8440`。q99/floor5は `+8.2150`。
- ただし、guardは00260のsame-window replacement-risk診断から選んだ。よって標準policyにはしない。次は追加chronologyまたは別familyへ、threshold `t0.4` と `strong,nonpositive` を固定して適用する。
- 標準policyはNoTrade。

## Artifacts

- Updated script:
  - `scripts/experiments/entry_ev_forced_exit_selector_inputs.py`
- Updated test:
  - `tests/test_entry_ev_forced_exit_selector_inputs.py`
- Guard input:
  - `data/reports/backtests/20260701_172323_20260702_entry_ev_exit_regret_selector_replguard_confextreme_t0p4_inputs_s1/`
- Broad replay:
  - `data/reports/backtests/20260701_172413_20260702_entry_ev_exit_regret_selector_replguard_confextreme_t0p4_broad_backtest_s1/`
- Fixed 2025 replay:
  - `data/reports/backtests/20260701_172413_20260702_entry_ev_exit_regret_selector_replguard_confextreme_t0p4_fixed2025_backtest_s1/`
- Broad guard vs no-guard delta:
  - `data/reports/backtests/20260701_172752_20260702_entry_ev_exit_regret_selector_replguard_vs_noguard_broad_delta_s1/`
- Fixed guard vs no-guard delta:
  - `data/reports/backtests/20260701_172803_20260702_entry_ev_exit_regret_selector_replguard_vs_noguard_fixed2025_delta_s1/`

## Method

Base selector:

```text
score_kind = exit_regret_selector_confidenceexit_bucket_t0p4
risk       = exit_regret / confidence_exit / bucket
threshold  = 0.4
base score = side_prior_pressure_s0p5
```

Replacement guard:

```text
if long is risk-blocked and short side_confidence_gap_bucket in {strong, nonpositive}:
    block short too

if short is risk-blocked and long side_confidence_gap_bucket in {strong, nonpositive}:
    block long too
```

This is intentionally narrower than blocking all `conf_gap_extreme` entries. It targets the replacement path where the selector creates a new alternative side after blocking the original side.

## Block Summary

Selector block share:

| family | long risk block | short risk block | any replacement guard | long final block | short final block | selected side changed |
|---|---:|---:|---:|---:|---:|---:|
| cal2024 | `0.047328` | `0.000000` | `0.004797` | `0.047328` | `0.004797` | `0.018617` |
| fresh2024 | `0.200451` | `0.000000` | `0.010814` | `0.200451` | `0.010814` | `0.144223` |
| refit2025 | `0.189538` | `0.100925` | `0.027629` | `0.198536` | `0.119556` | `0.130508` |

Reading:

- Guard activation is small in row-share terms.
- Refit2025 is where the guard mostly matters, matching the replacement harm found in 00260.

## Replay Results

Broad validation:

| candidate | no-guard total | guard total | delta | worst month | trades | max DD | max side share |
|---|---:|---:|---:|---:|---:|---:|---:|
| q99/floor5 | `+18.9072` | `+27.1222` | `+8.2150` | `-54.2268` | `36` | `54.5368` | `0.6944` |
| q95/floor5 | `-30.2972` | `+63.5468` | `+93.8440` | `-59.8792` | `71` | `59.8792` | `0.7324` |
| q99/floor10 | `+1.0804` | `+1.0804` | `0.0000` | `-7.4880` | `10` | `7.4880` | `0.7000` |
| q95/floor10 | `-39.7360` | `-39.7360` | `0.0000` | `-28.4760` | `23` | `37.6890` | `0.6522` |

Fixed 2025-03..12:

| candidate | no-guard total | guard total | delta | worst month | trades | max DD | max side share |
|---|---:|---:|---:|---:|---:|---:|---:|
| q99/floor5 | `+19.1218` | `+27.3368` | `+8.2150` | `-54.2268` | `21` | `54.5368` | `0.7143` |
| q95/floor5 | `-67.8612` | `+25.9828` | `+93.8440` | `-59.8792` | `42` | `59.8792` | `0.7619` |

Reading:

- q99/floor5 improves, but only modestly.
- q95/floor5 changes from rejected to positive on both broad and fixed 2025.
- Worst month remains around `-55..-60`, so the guard improves total PnL but does not solve tail risk.
- Side concentration remains high, especially q95/floor5 fixed at `0.7619`.

## Delta vs No-Guard

Broad guard delta:

| candidate | base trades | guard trades | no-guard PnL | guard PnL | delta | removed positive | removed negative | added positive | added negative |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| q99/floor5 | `36` | `36` | `+18.9072` | `+27.1222` | `+8.2150` | `+24.8230` | `0.0000` | `+16.1900` | `0.0000` |
| q95/floor5 | `72` | `71` | `-30.2972` | `+63.5468` | `+93.8440` | `+35.6130` | `-91.0920` | `+27.6730` | `-6.1560` |

Month-level notes:

- q99/floor5 improves in 2025-03 `+7.1900`, 2025-06 `+16.8480`, 2025-09 `+9.0000`.
- q99/floor5 degrades in 2025-11 `-20.6930` and 2025-12 `-4.1300` by removing winning trades.
- q95/floor5 gets the largest benefit in 2025-10 `+72.0120` through removed negative PnL.
- q95/floor5 also degrades in 2025-11 `-7.7690` and 2025-12 `-13.5200`.

Reading:

- Guard does improve the actual stateful path.
- It is not clean: it removes winners in late 2025 and leaves May tail unchanged.
- q95/floor5 may be a stronger diagnostic candidate than q99/floor5 after guard, but that choice is same-window and must not be standardized yet.

## Decision

Accepted:

- Replacement guard implementation in selector input generation.
- Stateful replay evidence that `conf_gap_extreme` guard improves the no-guard exit-regret selector on broad and fixed 2025.
- `exit_regret_selector_replguard_confidenceexit_bucket_t0p4` as a diagnostic replay candidate.

Not accepted:

- Standard-policy promotion.
- Choosing q95/floor5 as standard because it is now best on the same broad/fixed rows.
- Treating the guard as solved tail control; worst month and side concentration remain material.

Standard policy remains NoTrade.

## Next

1. Pre-register `exit_regret_selector_replguard_confidenceexit_bucket_t0p4` with `strong,nonpositive` guard and apply it to additional chronology / another family without changing thresholds.
2. Run admission selector gates with role/month floor, side share cap, and NoTrade-first comparison.
3. Diagnose remaining May 2025 tail; guard did not fix it.
4. Do not tune between q95/q99 on the same replay. Treat q95/floor5 as a diagnostic candidate until external validation.

## Verification

- `python3 -m unittest tests.test_entry_ev_forced_exit_selector_inputs tests.test_entry_ev_replacement_risk_delta_diagnostics tests.test_entry_ev_policy_trade_delta_diagnostics tests.test_docs_reports`: OK
- `python3 -m py_compile scripts/experiments/entry_ev_forced_exit_selector_inputs.py scripts/experiments/entry_ev_replacement_risk_delta_diagnostics.py scripts/experiments/entry_ev_policy_trade_delta_diagnostics.py`: OK
- `git diff --check`: OK
- guard selector input generation: OK
- broad guard replay: OK
- fixed 2025 guard replay: OK
- broad guard vs no-guard delta: OK
- fixed guard vs no-guard delta: OK
