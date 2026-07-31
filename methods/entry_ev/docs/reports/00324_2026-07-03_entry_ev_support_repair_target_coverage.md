# Entry EV Support Repair Target Coverage

日時: 2026-07-03 05:15 JST
更新日時: 2026-07-03 05:15 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00323で残ったtarget月 `fresh2024 2024-03`, `fresh2024 2024-11`, `refit2025 2025-07` について、00322 s2 broad horizon viability predictions上のcoverageを分解した。
- `scripts/experiments/entry_ev_support_repair_target_coverage_diagnostics.py` を追加し、target rows、row x horizon、threshold gate、best candidatesを出力する診断を作った。
- `refit2025 2025-07 short` はtarget-awareに拾える候補がある。available candidatesでは fixed-best positiveが3本、oracle non-overlap PnL `+31.8900`。p0.5 / EV0 / tail0.3 / model-used yesで `2025-07-21 06:38 short 240m +4.6900` を選べる。
- `fresh2024 2024-03 long` はavailable candidatesに fixed-best positiveが12本、fixed-best max `+13.4900`、positive sum `+68.2230` あるが、全horizonで `model_used=0` かつpredicted EVが負。require-model-usedなら0 choices、require-model-usedを外してp0.3 / EV-2まで緩めると17 choicesで `-137.9060` になり、winnerだけを分離できない。
- `fresh2024 2024-11 long` は候補がgreedy selected 1本だけ。actual 240mは `+2.4500` だが、予測は p `0.3952`, EV `-0.4546`, tail `0.4964`。p0.3 / EV-2 / tail0.5まで緩めると720m `-5.2800` を選び、positive horizonを選べない。
- 判断: target coverage diagnosticsはaccepted infrastructure。次はtarget-aware repair utilityへ進むが、2024-03/2024-11は単純threshold緩和で拾わない。標準policyはNoTrade。

## Artifacts

- New script:
  - `scripts/experiments/entry_ev_support_repair_target_coverage_diagnostics.py`
- New tests:
  - `tests/test_entry_ev_support_repair_target_coverage_diagnostics.py`
- Run:
  - `data/reports/backtests/20260702_201447_20260703_entry_ev_00324_support_repair_target_coverage_00322_s2/`

Outputs:

- `support_repair_target_coverage_summary.csv`
- `support_repair_target_threshold_coverage.csv`
- `support_repair_target_horizon_rows.csv`
- `support_repair_target_best_candidates.csv`

## Method

Input:

```text
00322 s2 broad horizon viability predictions
data/reports/backtests/20260702_121505_20260702_entry_ev_00322_broad_horizon_viability_00321_s2_include_onefail/broad_horizon_viability_predictions.csv
```

Target rows:

```text
fresh2024_validation:2024-03
fresh2024_validation:2024-11
refit2025_validation:2025-07
target_only = side == needed_side and extra_side_needed > 0
row_scopes = available_candidates, greedy_selected
horizons = 60, 240, 720
```

Threshold grid:

```text
prob thresholds = 0.3, 0.4, 0.5, 0.6
EV thresholds = -2, 0, 2
tail thresholds = 0.3, 0.5, 0.7
require_model_used = true, false
```

This diagnostic is not an admission replay. It only tells whether remaining target months have usable target-side horizon candidates and where the current horizon head blocks them.

## Target Coverage

| target | row scope | rows | fixed-best positive | fixed-best max | positive sum | oracle non-overlap | key blocker |
|---|---|---:|---:|---:|---:|---:|---|
| fresh2024 2024-03 long | available | `17` | `12` | `+13.4900` | `+68.2230` | `+13.4900` | model-used 0, predicted EV negative |
| fresh2024 2024-03 long | greedy | `1` | `0` | `-3.5280` | `0.0000` | `-3.5280` | selected row itself is bad |
| fresh2024 2024-11 long | greedy | `1` | `1` | `+2.4500` | `+2.4500` | `+2.4500` | only 1 row; head chooses bad 720m when relaxed |
| refit2025 2025-07 short | available | `10` | `3` | `+26.4000` | `+31.8900` | `+31.8900` | p0.6 EV-2 chooses losing 60m; EV0 chooses safer 240m |
| refit2025 2025-07 short | greedy | `1` | `0` | `-2.4240` | `0.0000` | `-2.4240` | selected row itself is bad |

## Threshold Findings

Useful target-aware candidate:

```text
refit2025_validation 2025-07 short
decision = 2025-07-21 06:38 UTC
horizon = 240m
actual = +4.6900
pred prob = 0.5281
pred EV = +1.7808
pred tail = 0.2601
model_used = true
passes p0.5 / EV0 / tail0.3
```

Dangerous relaxed choices:

```text
fresh2024 2024-03 available
require_model_used=false, p0.3, EV-2, tail0.3
choices = 17
positive choices = 3
negative choices = 14
actual sum = -137.9060
```

```text
fresh2024 2024-11 greedy
require_model_used=true, p0.3, EV-2, tail0.5
choice = 720m
actual = -5.2800
```

Best hidden / oracle-like positives:

| target | decision | horizon | actual | predicted state |
|---|---|---:|---:|---|
| fresh2024 2024-03 long | 2024-03-21 15:05 UTC | 240 | `+13.4900` | p `0.4203`, EV `-1.0312`, tail `0.2826`, model_used false |
| fresh2024 2024-03 long | 2024-03-21 15:08 UTC | 240 | `+13.0000` | p `0.4203`, EV `-1.0312`, tail `0.2826`, model_used false |
| fresh2024 2024-11 long | 2024-11-29 03:22 UTC | 240 | `+2.4500` | p `0.3952`, EV `-0.4546`, tail `0.4964`, model_used true |
| refit2025 2025-07 short | 2025-07-28 04:10 UTC | 720 | `+26.4000` | p `0.5102`, EV `-2.3561`, tail `0.3863`, model_used true |
| refit2025 2025-07 short | 2025-07-21 06:38 UTC | 240 | `+4.6900` | p `0.5281`, EV `+1.7808`, tail `0.2601`, model_used true |

## Decision

Accepted:

- support-repair target coverage diagnostics
- row x horizon gate breakdown
- explicit separation of hidden oracle positives from executable threshold choices

Rejected:

- relaxing thresholds globally to recover `fresh2024 2024-03`
- using fallback/non-model rows from `fresh2024 2024-03` as policy evidence
- treating `fresh2024 2024-11` as solved by broad horizon head
- using p0.6 / EV-2 on `refit2025 2025-07` when it selects the losing 60m candidate

Standard policy remains NoTrade.

## Next

1. Build target-aware support repair utility and feed it into 00323 replay.
2. Require non-negative predicted and realized diagnostic contribution for `refit2025 2025-07`; prefer the p0.5 / EV0 / tail0.3 240m candidate over p0.6 / EV-2 60m.
3. For `fresh2024 2024-03`, do not lower global thresholds. The issue is calibration/fallback; train a target-local or feature-level confidence signal before replay.
4. For `fresh2024 2024-11`, expand candidate coverage or add a horizon-choice calibration guard; current broad head chooses 720m loss under relaxed gates.

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_support_repair_target_coverage_diagnostics.py tests/test_entry_ev_support_repair_target_coverage_diagnostics.py`: OK
- `uv run python -m unittest tests.test_entry_ev_support_repair_target_coverage_diagnostics`: OK
- 00324 target coverage diagnostics run: OK
