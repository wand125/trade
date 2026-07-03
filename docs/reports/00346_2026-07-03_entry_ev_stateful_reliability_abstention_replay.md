# Entry EV Stateful Reliability Abstention Replay

日時: 2026-07-03 10:49 JST
更新日時: 2026-07-03 10:49 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00345で有望に見えた `ranker_pred_pnl < 0` horizon-switch vetoを、post-hoc診断ではなく `entry_ev_broad_prior_horizon_choice_replay.py` のstateful replay経路へ入れた。
- `--abstention-rules none,pred_pnl_lt0_switch_veto` と `--baseline-score-mode pnl` を追加し、defaultは `none` のまま既存挙動を維持した。
- replayは288条件を実行したが、bestはplain `pnl` / reliability-gated / veto有無で同じ5 trades、added PnL `+60.8530`、combined total `+400.1440`、month min `-0.6120`、role total min `+0.5354` に収束した。
- `pred_pnl_lt0_switch_veto` はprediction/replay候補上では発火したが、best scenarioに追加された5 tradesでは発火0件だった。selector passも0件で、blockersは `month_pnl_below_floor,role_trades_low,side_share_high` のまま。
- 判断: stateful horizon-switch abstention replay infrastructureはaccepted。`ranker_pred_pnl < 0` vetoはpost-hoc diagnosticsとしては有用だが、現stateful bestを改善しないため標準policyへ昇格しない。標準policyはNoTrade。

## Artifacts

Changed script:

- `scripts/experiments/entry_ev_broad_prior_horizon_choice_replay.py`

Changed tests:

- `tests/test_entry_ev_broad_prior_horizon_choice_replay.py`

Run:

- `data/reports/backtests/20260703_014724_20260703_entry_ev_00346_stateful_reliability_abstention_replay/`

Main outputs:

- `broad_prior_horizon_choice_replay_summary.csv`
- `broad_prior_horizon_choice_selection_summary.csv`
- `broad_prior_horizon_choice_additions.csv`
- `ranker_predictions_{score_mode}.csv`
- `ranker_predictions_{score_mode}__pred_pnl_lt0_switch_veto.csv`
- `ranker_replay_candidates_{score_mode}.csv`
- `ranker_replay_candidates_{score_mode}__pred_pnl_lt0_switch_veto.csv`
- `config.json`

## Method

New replay hook:

- `apply_switch_abstention(...)`
- `abstention_rule="none"`: score modeのraw choice scoreをそのまま使う。
- `abstention_rule="pred_pnl_lt0_switch_veto"`: raw score modeがbaseline `pnl` と異なるhorizonを選び、かつraw chosen horizonの `ranker_pred_pnl < 0` なら、そのdecision group全体のfinal choice scoreをbaseline `pnl` scoreへ戻す。

Runtime metadata:

- `ranker_abstention_rule`
- `ranker_abstention_veto`
- `ranker_abstention_pre_veto_horizon_minutes`
- `ranker_abstention_baseline_horizon_minutes`
- `ranker_abstention_pre_veto_pred_pnl`

Actual PnL is used only by replay evaluation. The veto condition itself uses prediction-time fields.

## Results

Best per score mode / abstention rule:

| score mode | abstention | row scope | prob | EV | tail | added | added PnL | combined | month min | role PnL min | extra trades needed | blockers |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| `pnl` | `none` | available | `0.50` | `2.0` | `0.5` | `5` | `+60.8530` | `+400.1440` | `-0.6120` | `+0.5354` | `3` | month / role trades / side share |
| `pnl` | `pred_pnl_lt0_switch_veto` | available | `0.45` | `2.0` | `0.3` | `5` | `+60.8530` | `+400.1440` | `-0.6120` | `+0.5354` | `3` | month / role trades / side share |
| `pnl_tail_reliability_gated` | `none` | available | `0.45` | `2.0` | `0.3` | `5` | `+60.8530` | `+400.1440` | `-0.6120` | `+0.5354` | `3` | month / role trades / side share |
| `pnl_tail_reliability_gated` | `pred_pnl_lt0_switch_veto` | available | `0.50` | `2.0` | `0.3` | `5` | `+60.8530` | `+400.1440` | `-0.6120` | `+0.5354` | `3` | month / role trades / side share |
| `pnl_delta_tail_reliability_gated` | `none` | available | `0.45` | `2.0` | `0.5` | `5` | `+60.8530` | `+400.1440` | `-0.6120` | `+0.5354` | `3` | month / role trades / side share |
| `pnl_delta_tail_reliability_gated` | `pred_pnl_lt0_switch_veto` | available | `0.50` | `2.0` | `0.5` | `5` | `+60.8530` | `+400.1440` | `-0.6120` | `+0.5354` | `3` | month / role trades / side share |
| `pnl_delta_tail` | `none` | available | `0.45` | `2.0` | `0.3` | `5` | `+50.2400` | `+389.5310` | `-0.6120` | `+0.5354` | `3` | month / role trades / side share |
| `pnl_delta_tail` | `pred_pnl_lt0_switch_veto` | available | `0.50` | `2.0` | `0.5` | `5` | `+50.2400` | `+389.5310` | `-0.6120` | `+0.5354` | `3` | month / role trades / side share |

Selector pass count:

- `0 / 288`

Veto activity in prediction artifacts:

| predictions file | veto groups |
|---|---:|
| `ranker_predictions_pnl__pred_pnl_lt0_switch_veto.csv` | `0` |
| `ranker_predictions_pnl_delta_tail__pred_pnl_lt0_switch_veto.csv` | `9` |
| `ranker_predictions_pnl_delta_tail_reliability_gated__pred_pnl_lt0_switch_veto.csv` | `13` |
| `ranker_predictions_pnl_tail_reliability_gated__pred_pnl_lt0_switch_veto.csv` | `12` |

Aggregate selected candidate summary:

| score mode | abstention | row scope | chosen | chosen PnL | veto count |
|---|---|---|---:|---:|---:|
| `pnl` | `none` | available | `132` | `-769.2526` | `0` |
| `pnl` | `pred_pnl_lt0_switch_veto` | available | `132` | `-769.2526` | `0` |
| `pnl_delta_tail` | `none` | available | `132` | `-802.9004` | `0` |
| `pnl_delta_tail` | `pred_pnl_lt0_switch_veto` | available | `132` | `-838.0318` | `8` |
| `pnl_tail_reliability_gated` | `none` | available | `132` | `-862.8754` | `0` |
| `pnl_tail_reliability_gated` | `pred_pnl_lt0_switch_veto` | available | `132` | `-731.3504` | `11` |
| `pnl_delta_tail_reliability_gated` | `none` | available | `132` | `-906.9442` | `0` |
| `pnl_delta_tail_reliability_gated` | `pred_pnl_lt0_switch_veto` | available | `132` | `-712.1944` | `12` |

Key reading:

- Candidate-level aggregateでは、reliability-gated系のvetoは悪いswitchをかなり減らす。ただしこれは候補面全体の話であり、最終repair/admissionで採用されるbest setの改善ではない。
- Best scenarioの5 additionsは、vetoありでもすべて `ranker_abstention_veto=False`。pre-veto horizonとbaseline horizonも720mで一致しており、00345のpost-hocで回復した悪いswitch群はbest repairに入っていない。
- `pnl_delta_tail` はvetoによりavailable chosen PnLが `-802.9004 -> -838.0318` へ悪化する。negative predicted PnL switch vetoはscore modeにより効き方が違う。
- 00345の改善は「reliability-gated choice deltaをbaselineへ戻せばcandidate-levelでは改善する」という発見であり、「stateful support repairのbestを改善する」という証拠ではなかった。

## Decision

- `apply_switch_abstention` と `--abstention-rules`: accepted infrastructure。
- `pred_pnl_lt0_switch_veto`: diagnostic candidateとして残すが、現stateful replayの標準policyにはしない。
- `pnl_delta_tail_reliability_gated + pred_pnl_lt0_switch_veto`: best combinedはplain `pnl` と同点で、blockersも同じ。優位性なし。
- `pnl_tail_reliability_gated + pred_pnl_lt0_switch_veto`: candidate aggregateは改善するが、best replayはplain `pnl` と同点。優位性なし。
- Standard policy remains NoTrade。

## Next

1. `ranker_pred_pnl < 0` vetoで止まらない positive predicted PnL failureへ進む。例: 00345で残った `hybrid2025 2025-10 long`。
2. tail/overestimate/context reliabilityを、global multiplierではなく「positive predicted PnLをどの条件で信用しないか」の校正問題として扱う。
3. `fresh2024 2024-11` / `refit2025 2025-03` は候補生成不足なので、abstentionではなくcandidate generation pathを追加する。
4. support repair objectiveへ `role_trades_low` / `side_share_high` を直接反映する。ただしEV-2の負け候補をsupport目的だけで入れない。

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_broad_prior_horizon_choice_replay.py tests/test_entry_ev_broad_prior_horizon_choice_replay.py`: OK
- `uv run python -m unittest tests.test_entry_ev_broad_prior_horizon_choice_replay`: OK
- 00346 stateful replay: OK
