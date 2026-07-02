# Entry EV Horizon Duration Penalty Calibration

日時: 2026-07-03 05:55 JST
更新日時: 2026-07-03 05:55 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00326の次アクションとして、row x horizon support repairにduration penaltyを時系列校正する仕組みを追加した。
- `scripts/experiments/entry_ev_horizon_duration_penalty_calibration.py` を追加し、各scenario / target monthごとに、target月より前の候補だけで `repair_horizon_penalty_weight_effective` を選ぶようにした。
- strict校正(min prior 10 rows / 2 months)もloose校正(min prior 1 row / 1 month)も、best replayはpred-only no-penaltyと同じで、added PnL `+3.2340`、combined `+342.5250`、month min `-19.8260`、role min `-20.8016` だった。
- 主因はfresh2024 2024-08にprior候補がなく、悪い720m `-29.1360` を止めるための `0.25` penaltyを時系列的に学べなかったこと。
- fallback `0.25` を事前固定すると00326 hpen0.25と同じ added PnL `+35.3200` / combined `+374.6110` を再現するが、これはlearned calibrationではなく保守的事前値の診断である。
- 結論: chronological duration-penalty calibration infrastructureはaccepted。support-repair対象行だけでduration penaltyを学ぶ方針は現時点ではreject。標準policyはNoTrade。

## Artifacts

- New script:
  - `scripts/experiments/entry_ev_horizon_duration_penalty_calibration.py`
- Updated script:
  - `scripts/experiments/entry_ev_support_repair_horizon_replay.py`
- New tests:
  - `tests/test_entry_ev_horizon_duration_penalty_calibration.py`
- Strict chronological calibration:
  - `data/reports/backtests/20260702_205234_20260703_entry_ev_00327_horizon_duration_penalty_calibration_strict_00322_s2/`
- Loose chronological calibration:
  - `data/reports/backtests/20260702_205234_20260703_entry_ev_00327_horizon_duration_penalty_calibration_loose_00322_s2/`
- Fixed fallback `0.25` diagnostic:
  - `data/reports/backtests/20260702_205516_20260703_entry_ev_00327_horizon_duration_penalty_calibration_fallback025_00322_s2/`

## Method

For each threshold scenario and target month:

```text
1. Use only rows with month < target_month.
2. Sweep penalty_weight in 0, 0.1, 0.25, 0.5, 0.75, 1.0.
3. Within each original row, choose the best 60/240/720m horizon by:
   support_reduction + pred_pnl - tail_prob - penalty_weight * horizon/60
4. Pick the weight with best prior realized PnL.
5. Apply the chosen weight to the target month.
```

This uses realized PnL only inside prior months for calibration diagnostics. It does not use the target month realized PnL to select its weight.

Replay then uses the same support repair constraints as 00326:

```text
choice_input_mode = row_horizon_grid
selection_mode = repair_score
min_chosen_pred_pnl = 0
max_chosen_tail_prob = 0.3
actual floor = none
```

## Results

| run | best scenario | added | added PnL | combined total | month min | role min | remaining extra | remaining hurdle | blockers |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| strict prior 10 rows / 2 months | available p0.3 EV-2 tail0.3 model-used | `6` | `+3.2340` | `+342.5250` | `-19.8260` | `-20.8016` | `2` | `+21.2746` | role, month, side-share |
| loose prior 1 row / 1 month | available p0.4 EV-2 tail0.3 model-used | `6` | `+3.2340` | `+342.5250` | `-19.8260` | `-20.8016` | `2` | `+21.2746` | role, month, side-share |
| fallback0.25 diagnostic | available p0.4 EV-2 tail0.3 model-used | `6` | `+35.3200` | `+374.6110` | `-0.6120` | `+0.5354` | `2` | `+1.4486` | month, side-share |

Key calibration choices for the loose run:

| target month | chosen weight | reason | prior months | prior candidate rows | prior row choices | prior choice PnL |
|---|---:|---|---:|---:|---:|---:|
| 2024-08 | `0.00` | fallback insufficient prior | `0` | `0` | n/a | n/a |
| 2025-07 | `0.25` | prior best | `1` | `4` | `2` | `-40.9904` |
| 2025-08 | `0.25` | prior best | `2` | `6` | `3` | `-36.3004` |
| 2025-10 | `0.00` | prior best | `3` | `34` | `22` | `-37.9158` |
| 2025-11 | `0.00` | prior best | `4` | `37` | `23` | `-33.1858` |

The critical selected trade in loose/strict is still:

| role | month | side | decision UTC | horizon | effective penalty | actual |
|---|---|---|---|---:|---:|---:|
| fresh2024_validation | 2024-08 | long | 2024-08-22 03:39 | 720 | `0.00` | `-29.1360` |

With fallback0.25, the same row is instead scored with the pre-registered penalty and selects 60m:

| role | month | side | decision UTC | horizon | effective penalty | actual |
|---|---|---|---|---:|---:|---:|
| fresh2024_validation | 2024-08 | long | 2024-08-22 03:39 | 60 | `0.25` | `+2.9500` |

## Decision

Accepted:

- chronological duration-penalty calibration infrastructure
- row-specific `repair_horizon_penalty_weight_effective`
- fallback penalty diagnostics as a controlled sensitivity check

Rejected:

- treating learned chronological duration penalty as successful on the current support-repair-only universe
- treating fallback0.25 as learned evidence
- standardizing hpen0.25 from this result
- learning duration risk only from sparse support-repair target rows

Standard policy remains NoTrade.

## Interpretation

The 00326 hpen0.25 improvement is real as a mechanism but not yet justified as a learned rule.

The failure mode is informative:

```text
The row that needs protection appears before there is enough comparable prior support.
```

Therefore, duration risk cannot be learned only from the few rows that happen to be selected for support repair. It needs a broader chronological training universe, such as near-miss rows and broad candidate rows from prior months, then used as a feature or prior in the support repair replay.

## Next

1. Train duration risk / short-horizon-overestimate features on the broader 00322 candidate universe, not only support repair target rows.
2. Add duration-risk prior into the horizon head or repair score as a continuous feature.
3. Keep fallback0.25 as a diagnostic sensitivity, not as a standard policy value.
4. Preserve target-month blindness: target month realized PnL must never decide its own penalty.
5. Re-run support repair only after the duration-risk signal is learned from broader prior data.

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_horizon_duration_penalty_calibration.py scripts/experiments/entry_ev_support_repair_horizon_replay.py tests/test_entry_ev_horizon_duration_penalty_calibration.py tests/test_entry_ev_support_repair_horizon_replay.py`: OK
- `uv run python -m unittest tests.test_entry_ev_horizon_duration_penalty_calibration tests.test_entry_ev_support_repair_horizon_replay`: OK
- 00327 strict chronological calibration run: OK
- 00327 loose chronological calibration run: OK
- 00327 fallback0.25 diagnostic run: OK
