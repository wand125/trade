# Entry EV Support-Aware Harmful Objective

日時: 2026-07-03 07:38 JST
更新日時: 2026-07-03 07:38 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00331の次アクションとして、harmful probabilityをsupport-aware objectiveへ入れた。
- まずhorizon-choice score側に `pnl_support_harmful_guard` 系modeを追加した。
- 次に、より本筋としてsupport repair層へ `repair_harmful_penalty_weight` と `repair_harmful_penalty_threshold` を追加した。
- repair層では `support_reduction_value`, executable probability, tail probabilityから `repair_support_success_proxy` を作り、support成功見込みがある候補ではharmful penaltyを割り引く。
- 結果、support-aware score modeは00329/00331 baseline `+403.2680` を超えなかった。
- repair harmful continuous penaltyもweight `0.1` 以上で勝ち候補を落とし、best `+396.9280` へ悪化した。
- threshold `0.5` / `0.7` はbaseline `+403.2680` を維持したが、改善ではなくほぼno-opだった。
- 結論: support-aware harmful objective infrastructureはaccepted。現形のscore-side / repair-side harmful penaltyはpolicy候補としてreject。標準policyはNoTrade。

## Artifacts

- Updated scripts:
  - `scripts/experiments/entry_ev_broad_prior_horizon_choice_replay.py`
  - `scripts/experiments/entry_ev_support_repair_horizon_replay.py`
- Updated tests:
  - `tests/test_entry_ev_broad_prior_horizon_choice_replay.py`
  - `tests/test_entry_ev_support_repair_horizon_replay.py`
- Score-side support harmful objective:
  - `data/reports/backtests/20260702_222509_20260703_entry_ev_00332_support_harmful_objective_w2h5_s1/`
  - `data/reports/backtests/20260702_222510_20260703_entry_ev_00332_support_harmful_objective_w5h5_s1/`
  - `data/reports/backtests/20260702_222510_20260703_entry_ev_00332_support_harmful_objective_w2h2_s1/`
- Repair-side continuous harmful penalty:
  - `data/reports/backtests/20260702_223418_20260703_entry_ev_00332_repair_harmful_penalty_w0_s2/`
  - `data/reports/backtests/20260702_223418_20260703_entry_ev_00332_repair_harmful_penalty_w0p1_s1/`
  - `data/reports/backtests/20260702_223417_20260703_entry_ev_00332_repair_harmful_penalty_w0p25_s1/`
  - `data/reports/backtests/20260702_223114_20260703_entry_ev_00332_repair_harmful_penalty_w1_s1/`
  - `data/reports/backtests/20260702_223114_20260703_entry_ev_00332_repair_harmful_penalty_w2_s1/`
  - `data/reports/backtests/20260702_223113_20260703_entry_ev_00332_repair_harmful_penalty_w5_s1/`
- Repair-side thresholded harmful penalty:
  - `data/reports/backtests/20260702_223805_20260703_entry_ev_00332_repair_harmful_penalty_w1_thr0p5_s1/`
  - `data/reports/backtests/20260702_223806_20260703_entry_ev_00332_repair_harmful_penalty_w5_thr0p5_s1/`
  - `data/reports/backtests/20260702_223806_20260703_entry_ev_00332_repair_harmful_penalty_w5_thr0p7_s1/`

## Implementation

Score-side modes:

```text
pnl_support_harmful_guard
pnl_delta_support_harmful_guard
pnl_delta_tail_support_harmful_guard
```

These use:

```text
support_needed =
  side == needed_side
  and extra_side_needed > 0

support_success_proxy =
  support_needed
  * ranker_pred_executable_prob
  * (1 - ranker_pred_tail_loss_prob)

score =
  base_horizon_score
  + support_score_weight * support_success_proxy
  - harmful_score_weight
    * ranker_pred_harmful_overestimate_prob
    * (1 - support_success_proxy)
```

This is useful as a diagnostic, but it mixes non-PnL support value into `pred_hv_*m_pnl`, so EV gates and expected-PnL ordering can be distorted.

Repair-side penalty:

```text
repair_support_success_proxy =
  support_reduction_value
  * hv_chosen_pred_executable_prob
  * (1 - hv_chosen_pred_tail_loss_prob)

repair_harmful_penalty =
  max(0, harmful_prob - threshold) / (1 - threshold)

repair_score =
  support_weight * support_reduction_value
  + expected_pnl_weight * hv_chosen_pred_pnl
  - tail_weight * hv_chosen_pred_tail_loss_prob
  - horizon_penalty
  - duration_risk_penalty
  - harmful_weight
    * repair_harmful_penalty
    * (1 - repair_support_success_proxy)
```

This keeps EV gates based on predicted PnL and applies harmful probability at the support-repair choice layer.

## Results

Baseline:

| run | best combined | added PnL | added count | month min | role min | remaining extra | blockers |
|---|---:|---:|---:|---:|---:|---:|---|
| 00329/00331 low-complexity `pnl` | `+403.2680` | `+63.9770` | `5` | `-0.6120` | `+0.5354` | `3` | `month_pnl_below_floor,role_trades_low,side_share_high` |

Score-side support harmful objective:

| support weight | harmful weight | mode | best combined | added PnL | added count | blockers |
|---:|---:|---|---:|---:|---:|---|
| `2.0` | `5.0` | `pnl_support_harmful_guard` | `+370.0040` | `+30.7130` | `4` | `month_pnl_below_floor,side_share_high` |
| `2.0` | `5.0` | `pnl_delta_support_harmful_guard` | `+367.5800` | `+28.2890` | `5` | `month_pnl_below_floor,side_share_high` |
| `5.0` | `5.0` | `pnl_support_harmful_guard` | `+367.5800` | `+28.2890` | `5` | `month_pnl_below_floor,side_share_high` |
| `2.0` | `2.0` | `pnl_support_harmful_guard` | `+367.7920` | `+28.5010` | `6` | `role_total_pnl_below_floor,month_pnl_below_floor,side_share_high` |

Repair-side harmful penalty:

| repair harmful weight | threshold | best combined | added PnL | added count | month min | remaining extra | interpretation |
|---:|---:|---:|---:|---:|---:|---:|---|
| `0.00` | `0.0` | `+403.2680` | `+63.9770` | `5` | `-0.6120` | `3` | baseline reproduced |
| `0.10` | `0.0` | `+396.9280` | `+57.6370` | `5` | `-0.6120` | `3` | winner damaged |
| `0.25` | `0.0` | `+396.9280` | `+57.6370` | `5` | `-0.6120` | `3` | same damage |
| `1.00` | `0.0` | `+396.9280` | `+57.6370` | `5` | `-0.6120` | `3` | same damage |
| `2.00` | `0.0` | `+396.9280` | `+57.6370` | `5` | `-0.6120` | `3` | same damage |
| `5.00` | `0.0` | `+396.9280` | `+57.6370` | `5` | `-0.6120` | `3` | same damage |
| `1.00` | `0.5` | `+403.2680` | `+63.9770` | `5` | `-0.6120` | `3` | no-op |
| `5.00` | `0.5` | `+403.2680` | `+63.9770` | `5` | `-0.6120` | `3` | no-op |
| `5.00` | `0.7` | `+403.2680` | `+63.9770` | `5` | `-0.6120` | `3` | no-op |

## Failure Analysis

Continuous repair penalty changed two selected trades:

| month | side | baseline time | baseline actual | penalty time | penalty actual | harmful baseline | harmful penalty |
|---|---|---|---:|---|---:|---:|---:|
| 2025-08 | long | `17:28` | `+13.2500` | `17:26` | `+12.8000` | `0.3948` | `0.3948` |
| 2025-11 | short | `01:35` | `+10.4400` | `01:43` | `+4.5500` | `0.4101` | `0.0045` |

The second replacement is the important failure: the harmful head assigned moderate risk (`0.4101`) to an actually profitable 60m support trade. Even weight `0.1` was enough to change ordering because the repair scores were close. Threshold `0.5` protects this trade, but then the penalty does not improve the policy.

This confirms the 00331 diagnosis:

- harmful head has useful aggregate signal
- direct scalar penalty is too blunt
- profitable support trades can carry moderate harmful probability
- policy conversion needs a richer action target than `subtract risk`

## Decision

Accepted:

- support-aware harmful score modes as diagnostics
- `hv_chosen_pred_harmful_overestimate_prob` propagation into support repair candidates
- repair-side harmful penalty infrastructure
- thresholded harmful penalty infrastructure
- `repair_support_success_proxy` diagnostic column

Rejected as current policy:

- score-side `pnl_support_harmful_guard`
- score-side `pnl_delta_support_harmful_guard`
- score-side `pnl_delta_tail_support_harmful_guard`
- repair-side continuous harmful penalty
- repair-side thresholded harmful penalty as improvement evidence

Standard policy remains NoTrade.

## Next

1. Move from scalar penalty to pairwise / listwise choice diagnostics:
   - compare chosen vs near alternative within the same `(role, month, side, decision cluster)`
   - train whether switching actually improves realized support repair PnL
2. Calibrate harmful probability by context before using it:
   - especially horizon, side, session, regime, and 60m vs 720m
   - do not use global harmful probability as direct penalty
3. Diagnose remaining standard blockers under 00329 baseline:
   - role trade count low
   - side share high
   - month floor breach `-0.6120`
4. Treat harmful head as an input to a candidate-level meta-selector, not as an additive score term.

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_support_repair_horizon_replay.py scripts/experiments/entry_ev_broad_prior_horizon_choice_replay.py tests/test_entry_ev_support_repair_horizon_replay.py tests/test_entry_ev_broad_prior_horizon_choice_replay.py`: OK
- `uv run python -m unittest tests.test_entry_ev_support_repair_horizon_replay tests.test_entry_ev_broad_prior_horizon_choice_replay`: OK
- 00332 support harmful score experiments: OK
- 00332 repair harmful penalty experiments: OK
- 00332 thresholded repair harmful penalty experiments: OK
