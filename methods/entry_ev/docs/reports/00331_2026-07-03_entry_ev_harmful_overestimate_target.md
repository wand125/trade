# Entry EV Harmful Overestimate Target Diagnostics

日時: 2026-07-03 07:13 JST
更新日時: 2026-07-03 07:13 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00330の次アクションとして、harmful overestimate と profitable high-variance 720m を分離するtarget診断を追加した。
- `scripts/experiments/entry_ev_horizon_overestimate_target_diagnostics.py` を追加した。horizon-level examplesへ `harmful_overestimate`, `support_harmful_overestimate`, `profitable_high_variance_720`, `dangerous_high_variance_720` を付ける。
- 00330のlower-boundで見えた問題は再確認された。residual priorの大きさだけでflagすると、有害720mと勝ち720mを同時に拾う。
- 既存horizon-choice rankerに `target_horizon_harmful_overestimate` classifier headを追加し、`pnl_harmful_guard` 系score modeを試した。
- harmful head自体は識別力が出た。available candidatesでは AUC が60m `0.8859`, 240m `0.9391`, 720m `0.8758`。
- しかしdirect penalty replayは00329 baseline `+403.2680` を超えなかった。weight 1 bestは `+397.3780`、weight 5 bestは `+394.7840`。
- 結論: harmful-overestimate target/head infrastructureはaccepted。現時点のdirect harmful penaltyはpolicy候補としてreject。標準policyはNoTrade。

## Artifacts

- New diagnostic script:
  - `scripts/experiments/entry_ev_horizon_overestimate_target_diagnostics.py`
- Updated ranker script:
  - `scripts/experiments/entry_ev_broad_prior_horizon_choice_replay.py`
- Tests:
  - `tests/test_entry_ev_horizon_overestimate_target_diagnostics.py`
  - `tests/test_entry_ev_broad_prior_horizon_choice_replay.py`
- Target diagnostics:
  - `data/reports/backtests/20260702_220556_20260703_entry_ev_00331_horizon_overestimate_target_diagnostics_s1/`
- Harmful guard replay, weight 5:
  - `data/reports/backtests/20260702_221028_20260703_entry_ev_00331_harmful_overestimate_guard_s1/`
- Harmful guard replay, weight 1:
  - `data/reports/backtests/20260702_221234_20260703_entry_ev_00331_harmful_overestimate_guard_w1_s1/`

## Target Definition

For each horizon example:

```text
ranker_overestimate_amount = ranker_pred_pnl - horizon_actual_pnl

harmful_overestimate =
  ranker_pred_pnl >= min_executable_pnl
  and ranker_overestimate_amount >= overestimate_threshold
  and (
    horizon_actual_pnl < max(min_executable_pnl, target_pnl_hurdle)
    or horizon_actual_delta_vs_60 <= -underperform_60_threshold
    or target_horizon_tail_loss
  )

support_harmful_overestimate =
  support_needed and harmful_overestimate and not support_success

profitable_high_variance_720 =
  horizon == 720m
  and residual prior is high variance
  and horizon_actual_pnl >= min_profitable_pnl
```

For the model head inside `entry_ev_broad_prior_horizon_choice_replay.py`, the target is intentionally executable with training rows:

```text
target_horizon_harmful_overestimate =
  fixed_horizon_prediction >= min_executable_pnl
  and fixed_horizon_prediction - actual >= overestimate_threshold
  and (
    actual < min_executable_pnl
    or actual_delta_vs_60 <= -underperform_60_threshold
    or actual <= tail_loss_threshold
  )
```

The model target does not use future support-hurdle fields that are absent from broad training rows.

## Diagnostics

Horizon-level target summary on 00330 tiny scored examples:

| scope | horizon | rows | actual PnL | harmful count | harmful PnL | support success | support success PnL | profitable HV720 | profitable HV720 PnL | dangerous HV720 PnL |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| available | 60m | `132` | `-305.5378` | `29` | `-158.4516` | `56` | `+207.5680` | `0` | `0.0000` | `0.0000` |
| available | 240m | `132` | `-579.2936` | `37` | `-327.7068` | `47` | `+370.6140` | `0` | `0.0000` | `0.0000` |
| available | 720m | `132` | `-1546.4292` | `41` | `-1074.3240` | `47` | `+357.4860` | `19` | `+267.7170` | `-1068.6792` |
| greedy | 720m | `11` | `-46.0898` | `3` | `-107.1648` | `6` | `+76.6990` | `5` | `+73.6090` | `-107.1648` |

Important context split:

| context | harmful PnL | profitable HV720 PnL | interpretation |
|---|---:|---:|---|
| 720m short / up_normal_vol / asia / one_failed | `-330.4680` | `0.0000` | strongly harmful |
| 720m short / down_normal_vol / asia / one_failed | `0.0000` | `+89.4930` | profitable high variance |
| 720m long / down_normal_vol / ny_late / one_failed | `0.0000` | `+52.5500` | profitable high variance |
| 720m short / down_normal_vol / london / one_failed | `-178.0692` | `+54.4840` | mixed, needs context/sequence not global penalty |
| 720m short / range_normal_vol / london / one_failed | `-162.0144` | `+16.3600` | mostly harmful but not pure |

Threshold sensitivity confirms why 00330 lower-bound failed:

| scope | rule | flagged PnL | flagged harmful PnL | harmful precision | profitable HV720 damage |
|---|---|---:|---:|---:|---:|
| 720m | `residual_mae >= 10` | `-1512.3072` | `-1175.8440` | `0.3559` | `100.0%` |
| 720m | `tail_miss >= 0.10` | `-1279.6876` | `-997.7748` | `0.3619` | `83.3%` |
| 720m | `positive_bias & tail_miss >= 0.10` | `-1029.7160` | `-823.9644` | `0.4138` | `54.2%` |
| 720m | `positive_bias >= 10` | `-275.3330` | `-335.8668` | `0.5333` | `20.8%` |

Residual thresholds can find bad zones, but they still damage too many profitable 720m rows.

## Harmful Head Results

The new classifier head was added to the chronological ranker target set:

```text
ranker_pred_harmful_overestimate_prob
```

Horizon-level metric summary:

| scope | horizon | actual rate | pred mean | MAE | Spearman | AUC |
|---|---:|---:|---:|---:|---:|---:|
| available | 60m | `0.2045` | `0.1969` | `0.2184` | `0.5458` | `0.8859` |
| available | 240m | `0.2803` | `0.2267` | `0.2093` | `0.6972` | `0.9391` |
| available | 720m | `0.1818` | `0.2060` | `0.2098` | `0.5065` | `0.8758` |
| greedy | 720m | `0.0909` | `0.2909` | `0.2944` | `0.2000` | `0.7000` |

Fold diagnostics:

| target month | target rows | actual rate | pred mean | AUC |
|---|---:|---:|---:|---:|
| 2024-08 | `45` | `0.0222` | `0.0171` | `1.0000` |
| 2025-07 | `33` | `0.4848` | `0.3282` | `0.9577` |
| 2025-08 | `207` | `0.1836` | `0.2220` | `0.8616` |
| 2025-10 | `15` | `0.0667` | `0.1813` | `0.6429` |
| 2025-11 | `72` | `0.5417` | `0.3340` | `0.8310` |

The head has useful signal. The problem is conversion to policy.

## Replay Results

| run | mode | best combined | added PnL | added count | month min | min hurdle | pass |
|---|---|---:|---:|---:|---:|---:|---:|
| baseline | `pnl` | `+403.2680` | `+63.9770` | `5` | `-0.6120` | `1.4486` | `0` |
| w1 | `pnl_harmful_guard` | `+397.3780` | `+58.0870` | `5` | `-0.6120` | `1.4486` | `0` |
| w1 | `pnl_delta_harmful_guard` | `+394.7840` | `+55.4930` | `5` | `-0.6120` | `1.4486` | `0` |
| w1 | `pnl_delta_tail_harmful_guard` | `+384.1710` | `+44.8800` | `5` | `-0.6120` | `1.4486` | `0` |
| w5 | `pnl_delta_harmful_guard` | `+394.7840` | `+55.4930` | `5` | `-0.6120` | `1.4486` | `0` |
| w5 | `pnl_harmful_guard` | `+366.5810` | `+27.2900` | `2` | `-0.7200` | `2.1686` | `0` |
| w5 | `pnl_delta_tail_harmful_guard` | `+366.5810` | `+27.2900` | `2` | `-0.7200` | `2.1686` | `0` |

No harmful guard score mode passed admission gates or beat the baseline.

## Decision

Accepted:

- harmful-overestimate target diagnostics
- horizon/context split of harmful vs profitable high-variance 720m
- chronological harmful-overestimate classifier head
- harmful guard score modes as diagnostics

Rejected as policy evidence:

- residual prior threshold as a hard/global 720m suppressor
- `pnl_harmful_guard` as current policy score
- `pnl_delta_harmful_guard` as current policy score
- `pnl_delta_tail_harmful_guard` as current policy score

Standard policy remains NoTrade.

## Interpretation

The research direction is correct: target separation improved. But direct score subtraction is still too blunt.

The head detects harmful overestimate, but policy conversion loses because:

- profitable 720m rows often live near high-risk residual contexts
- the support objective is still implicit
- replacing a bad horizon choice with no trade or 60m is not enough if the thin month still needs positive opposite-side entries
- penalty changes global ranking but does not explicitly solve `role_trades_low` or `side_share_high`

The next implementation should treat harmful probability as a feature in a support-aware objective, not as a direct scalar penalty.

## Next

1. Add support-aware horizon-choice score terms:
   - reward `support_needed`
   - reward `support_success` proxy
   - penalize harmful probability only when it conflicts with support repair
2. Diagnose remaining target months with the new target labels:
   - `fresh2024 2024-03`
   - `fresh2024 2024-11`
   - `refit2025 2025-03`
3. Build a candidate-level selector that optimizes:
   ```text
   EV + support_reduction_value - harmful_risk_when_not_support_repair
   ```
4. Keep 00329 low-complexity `pnl` ranker as diagnostic best until support-aware objective beats it.

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_horizon_overestimate_target_diagnostics.py tests/test_entry_ev_horizon_overestimate_target_diagnostics.py`: OK
- `uv run python -m unittest tests.test_entry_ev_horizon_overestimate_target_diagnostics`: OK
- `uv run python -m py_compile scripts/experiments/entry_ev_broad_prior_horizon_choice_replay.py tests/test_entry_ev_broad_prior_horizon_choice_replay.py`: OK
- `uv run python -m unittest tests.test_entry_ev_broad_prior_horizon_choice_replay`: OK
- 00331 target diagnostics: OK
- 00331 harmful guard weight 5 replay: OK
- 00331 harmful guard weight 1 replay: OK
