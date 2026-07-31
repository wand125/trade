# Entry EV Selected Tail Pred PnL Gate Replay

日時: 2026-07-03 14:12 JST
更新日時: 2026-07-03 14:12 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00357のpre-registered候補をstateful replayへ戻した。
- `entry_ev_broad_prior_horizon_choice_replay.py` にpositive PnL gate ruleを2つ追加した。
  - `selected_tail_pass_pred_pnl_lt2`: `0 < hv_chosen_pred_pnl < 2` and `hv_chosen_pred_tail_loss_prob <= 0.30`
  - `singleton_720_pred_pnl_lt2`: 上記 + `hv_chosen_horizon_minutes == 720`
- ルール名は00357診断由来だが、実行時に `selected_addition` やactual PnLは使わない。
- replayでは両gateともbest combined `+400.1440` で、既存no-gate bestと同点。selector passは全gateで `0 / 288`。
- `singleton_720_pred_pnl_lt2` はscenario差分で悪化0、改善96、同値192。EV -2 / 0で入っていた `fresh2024_validation 2024-08 long 720m -29.1360` を止め、EV2 no-gateと同じ5 trades / `+60.8530` に戻す。
- ただしbestは既存no-gate EV2と同じで、blockersは `month_pnl_below_floor,role_trades_low,side_share_high` のまま。標準policyにはしない。
- `selected_tail_pass_pred_pnl_lt2` は候補面では強いが広すぎる。scenario差分で改善96、悪化32。selected winnersを削るためglobal gateとしてreject。
- 判断: `singleton_720_pred_pnl_lt2` はaccepted diagnostic replay candidate、標準policyはNoTrade。次はこのnarrow guardを未使用surface / 追加chronologyで再検証しつつ、残るsupport blockersを解く候補生成へ戻る。

## Artifacts

Updated script:

- `scripts/experiments/entry_ev_broad_prior_horizon_choice_replay.py`

Updated tests:

- `tests/test_entry_ev_broad_prior_horizon_choice_replay.py`

Run:

- `data/reports/backtests/20260703_050907_20260703_entry_ev_00358_selected_tail_pred_pnl_gate_replay/`

Key outputs:

- `broad_prior_horizon_choice_replay_summary.csv`
- `broad_prior_horizon_choice_positive_pnl_gate_summary.csv`
- `broad_prior_horizon_choice_additions.csv`
- `broad_prior_horizon_choice_rejections.csv`
- `ranker_positive_pnl_gate_vetoed_*selected_tail_pass_pred_pnl_lt2.csv`
- `ranker_positive_pnl_gate_vetoed_*singleton_720_pred_pnl_lt2.csv`

## Method

Replay settings:

- base branch: 00314 fixed60 margin w5 position quality overlay
- predictions: 00322 broad horizon viability
- broad train rows: 00328
- score modes: `pnl`, `pnl_tail_reliability_gated`, `pnl_delta_tail_reliability_gated`, `pnl_delta_tail`
- abstention: `none`, `pred_pnl_lt0_switch_veto`
- positive PnL gate rules: `none`, `selected_tail_pass_pred_pnl_lt2`, `singleton_720_pred_pnl_lt2`
- positive PnL penalty: `none:0`
- residual prior support: `min_residual_prior_rows=5`, `min_residual_prior_months=2`
- head reliability: `min_head_reliability_months=1`
- model: `max_iter=80`, `max_leaf_nodes=4`, `l2_regularization=5.0`, `min_train_months=1`, `min_train_rows=50`

## Results

Best by gate:

| gate | scenarios | selector pass | best combined | best added PnL | best added count | best month min | role min | remaining extra trades | remaining month hurdle |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `none` | `288` | `0` | `+400.1440` | `+60.8530` | `5` | `-0.6120` | `+0.5354` | `3` | `1.4486` |
| `selected_tail_pass_pred_pnl_lt2` | `288` | `0` | `+400.1440` | `+60.8530` | `5` | `-0.6120` | `+0.5354` | `3` | `1.4486` |
| `singleton_720_pred_pnl_lt2` | `288` | `0` | `+400.1440` | `+60.8530` | `5` | `-0.6120` | `+0.5354` | `3` | `1.4486` |

Scenario delta vs no-gate:

| gate | changed | improved | worse | same | best delta | worst delta | mean delta |
|---|---:|---:|---:|---:|---:|---:|---:|
| `selected_tail_pass_pred_pnl_lt2` | `128 / 288` | `96` | `32` | `160` | `+29.1360` | `-6.5200` | `+8.9876` |
| `singleton_720_pred_pnl_lt2` | `96 / 288` | `96` | `0` | `192` | `+29.1360` | `0.0000` | `+9.7120` |

Gate veto summary, row-weighted:

| gate | veto rows | veto PnL | veto losses | veto loss PnL | veto wins |
|---|---:|---:|---:|---:|---:|
| `selected_tail_pass_pred_pnl_lt2` | `5648` | `-16023.0816` | `3496` | `-23220.6336` | `2152` |
| `singleton_720_pred_pnl_lt2` | `624` | `-4170.1632` | `240` | `-5778.2592` | `384` |

Gate veto summary, candidate identity dedup:

| gate | veto unique | veto PnL | losses | wins |
|---|---:|---:|---:|---:|
| `selected_tail_pass_pred_pnl_lt2` | `86` | `-217.6618` | `53` | `33` |
| `singleton_720_pred_pnl_lt2` | `9` | `-27.6444` | `3` | `6` |

Additions aggregate:

| gate | addition rows | addition PnL | losses | loss PnL | wins | win PnL |
|---|---:|---:|---:|---:|---:|---:|
| `none` | `1040` | `+9044.3480` | `96` | `-2797.0560` | `944` | `+11841.4040` |
| `selected_tail_pass_pred_pnl_lt2` | `912` | `+11632.7640` | `0` | `0.0000` | `912` | `+11632.7640` |
| `singleton_720_pred_pnl_lt2` | `944` | `+11841.4040` | `0` | `0.0000` | `944` | `+11841.4040` |

Representative scenario, `available_candidates / pnl / no abstention / p0.45 / tail0.3`:

| gate | EV threshold | additions | added PnL | min addition PnL | losses |
|---|---:|---:|---:|---:|---:|
| `none` | `-2` | `6` | `+31.7170` | `-29.1360` | `1` |
| `none` | `0` | `6` | `+31.7170` | `-29.1360` | `1` |
| `none` | `2` | `5` | `+60.8530` | `+0.3400` | `0` |
| `selected_tail_pass_pred_pnl_lt2` | `-2` | `5` | `+60.8530` | `+0.3400` | `0` |
| `selected_tail_pass_pred_pnl_lt2` | `0` | `5` | `+60.8530` | `+0.3400` | `0` |
| `selected_tail_pass_pred_pnl_lt2` | `2` | `5` | `+60.8530` | `+0.3400` | `0` |
| `singleton_720_pred_pnl_lt2` | `-2` | `5` | `+60.8530` | `+0.3400` | `0` |
| `singleton_720_pred_pnl_lt2` | `0` | `5` | `+60.8530` | `+0.3400` | `0` |
| `singleton_720_pred_pnl_lt2` | `2` | `5` | `+60.8530` | `+0.3400` | `0` |

Blocker distribution:

| gate | blocker | scenarios |
|---|---|---:|
| `none` | `month_pnl_below_floor,role_trades_low,month_trades_low,side_share_high` | `16` |
| `none` | `month_pnl_below_floor,role_trades_low,side_share_high` | `176` |
| `none` | `role_total_pnl_below_floor,month_pnl_below_floor,side_share_high` | `96` |
| `selected_tail_pass_pred_pnl_lt2` | `month_pnl_below_floor,role_trades_low,month_trades_low,side_share_high` | `48` |
| `selected_tail_pass_pred_pnl_lt2` | `month_pnl_below_floor,role_trades_low,side_share_high` | `240` |
| `singleton_720_pred_pnl_lt2` | `month_pnl_below_floor,role_trades_low,month_trades_low,side_share_high` | `16` |
| `singleton_720_pred_pnl_lt2` | `month_pnl_below_floor,role_trades_low,side_share_high` | `272` |

## Interpretation

- `singleton_720_pred_pnl_lt2` は00357で見えたactual selected singleton lossをstateful replay上でも止めた。EV -2 / 0の低threshold scenarioは、既存no-gate EV2 scenarioと同じ5 trades / `+60.8530` へ戻る。
- ただしこれは新しいbestではない。既存のEV2 thresholdがすでに同じ効果を持っており、best combinedはno-gateと同点。
- `singleton_720_pred_pnl_lt2` はscenario deltaで悪化0なので、`selected_tail_pass_pred_pnl_lt2` より安全なdiagnostic guard。ただしcandidate identity dedupでは9件だけ、かつselected failure支持は実質1件なので標準化には足りない。
- `selected_tail_pass_pred_pnl_lt2` はcandidate surfaceでは損失を大きく削るが、720m以外や低PnL winnerも削る。scenario deltaで32件悪化したため、global hard gateとしてはreject。
- additions aggregateでloss 0に見えるのは有用だが、標準admissionは依然として `month_pnl_below_floor`, `role_trades_low`, `side_share_high` で落ちる。損失削除だけではsupport修復にならない。

## Decision

- `selected_tail_pass_pred_pnl_lt2` gate infrastructure is accepted, but the broad rule is rejected as a standard policy because it worsens 32 scenarios.
- `singleton_720_pred_pnl_lt2` is accepted as a diagnostic replay candidate. It has no scenario degradation in this replay and removes the known selected singleton loss.
- `singleton_720_pred_pnl_lt2` is not a standard policy. It ties the existing no-gate EV2 best and still fails NoTrade-first admission.
- Standard policy remains NoTrade.

## Next

1. Keep `singleton_720_pred_pnl_lt2` as a narrow diagnostic guard and test it on additional support-repair surfaces / chronology before any promotion.
2. Do not use broad `selected_tail_pass_pred_pnl_lt2` as a global hard gate.
3. Return to support repair: the remaining blockers are role trade count, side share, and shallow month floor, not the known singleton loss alone.
4. Treat EV2 threshold and singleton guard as equivalent for the known 2024-08 failure; prefer the simpler threshold unless a future surface needs the targeted guard.

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_broad_prior_horizon_choice_replay.py tests/test_entry_ev_broad_prior_horizon_choice_replay.py`: OK
- `uv run python -m unittest tests.test_entry_ev_broad_prior_horizon_choice_replay`: OK
- 00358 selected tail pred PnL gate stateful replay: OK
