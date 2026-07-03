# Entry EV Positive PnL Gate Stateful Replay

日時: 2026-07-03 11:26 JST
更新日時: 2026-07-03 11:26 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00347のpointwise診断で有望だった positive predicted PnL failure gateを、`entry_ev_broad_prior_horizon_choice_replay.py` のstateful replay経路へ入れた。
- `--positive-pnl-gate-rules` を追加し、defaultは `none` のまま既存挙動を維持した。今回比較したruleは `none`, `positive_bias_and_tail_miss_ge_0p10`, `tail_prob_ge_0p30`。
- replayは864条件を実行。selector passは `0 / 864`。
- `tail_prob_ge_0p30` はcandidate surfaceでは負け候補を多く削るが、best scenarioはgateなしと同じ5 trades、combined `+400.1440`、added PnL `+60.8530` で変化なし。
- `positive_bias_and_tail_miss_ge_0p10` はcandidate surfaceでは大きな負け候補群を削る一方、best EV2 scenarioでは勝ち720m候補を削る。best overallもcombined `+393.2940`、added PnL `+54.0030` へ悪化。
- 判断: positive-PnL gate replay infrastructureはaccepted。`tail_prob_ge_0p30` はbest no-op、`positive_bias_and_tail_miss_ge_0p10` はhard gateとしてreject。次はhard gateではなく、horizon/context別のcalibration/soft penalty/abstention confidenceへ進む。標準policyはNoTrade。

## Artifacts

Changed script:

- `scripts/experiments/entry_ev_broad_prior_horizon_choice_replay.py`

Changed tests:

- `tests/test_entry_ev_broad_prior_horizon_choice_replay.py`

Run:

- `data/reports/backtests/20260703_022403_20260703_entry_ev_00348_positive_pnl_gate_stateful_replay/`

Main outputs:

- `broad_prior_horizon_choice_replay_summary.csv`
- `broad_prior_horizon_choice_positive_pnl_gate_summary.csv`
- `broad_prior_horizon_choice_additions.csv`
- `ranker_replay_candidates_{mode}.csv`
- `ranker_replay_candidates_{mode}__ppg_{rule}.csv`
- `ranker_positive_pnl_gate_vetoed_{mode}__ppg_{rule}.csv`
- `config.json`

## Method

New replay hook:

- `positive_pnl_gate_rule="none"`: no candidate veto.
- `positive_pnl_gate_rule="positive_bias_and_tail_miss_ge_0p10"`:
  - `hv_chosen_pred_pnl > 0`
  - chosen horizonの `ranker_hv_{h}m_residual_bias > 0`
  - chosen horizonの `ranker_hv_{h}m_residual_tail_miss_rate >= 0.10`
- `positive_pnl_gate_rule="tail_prob_ge_0p30"`:
  - `hv_chosen_pred_pnl > 0`
  - `hv_chosen_pred_tail_loss_prob >= 0.30`

The gate uses prediction-time fields and chronological residual priors. Actual PnL is used only for replay evaluation and gate diagnostics.

## Results

Best per score mode / abstention / gate:

| score mode | abstention | gate | added | added PnL | combined | month min | role PnL min | extra trades needed | blockers |
|---|---|---|---:|---:|---:|---:|---:|---:|---|
| `pnl` | `none` | `none` | `5` | `+60.8530` | `+400.1440` | `-0.6120` | `+0.5354` | `3` | month / role trades / side share |
| `pnl` | `none` | `tail_prob_ge_0p30` | `5` | `+60.8530` | `+400.1440` | `-0.6120` | `+0.5354` | `3` | month / role trades / side share |
| `pnl` | `none` | `positive_bias_and_tail_miss_ge_0p10` | `5` | `+54.0030` | `+393.2940` | `-0.6120` | `+0.5354` | `3` | month / role trades / side share |
| `pnl_tail_reliability_gated` | `none` | `none` | `5` | `+60.8530` | `+400.1440` | `-0.6120` | `+0.5354` | `3` | month / role trades / side share |
| `pnl_tail_reliability_gated` | `none` | `tail_prob_ge_0p30` | `5` | `+60.8530` | `+400.1440` | `-0.6120` | `+0.5354` | `3` | month / role trades / side share |
| `pnl_tail_reliability_gated` | `none` | `positive_bias_and_tail_miss_ge_0p10` | `5` | `+54.0030` | `+393.2940` | `-0.6120` | `+0.5354` | `3` | month / role trades / side share |
| `pnl_delta_tail_reliability_gated` | `none` | `none` | `5` | `+60.8530` | `+400.1440` | `-0.6120` | `+0.5354` | `3` | month / role trades / side share |
| `pnl_delta_tail_reliability_gated` | `none` | `tail_prob_ge_0p30` | `5` | `+60.8530` | `+400.1440` | `-0.6120` | `+0.5354` | `3` | month / role trades / side share |
| `pnl_delta_tail_reliability_gated` | `none` | `positive_bias_and_tail_miss_ge_0p10` | `5` | `+54.0030` | `+393.2940` | `-0.6120` | `+0.5354` | `3` | month / role trades / side share |
| `pnl_delta_tail` | `none` | `none` | `5` | `+50.2400` | `+389.5310` | `-0.6120` | `+0.5354` | `3` | month / role trades / side share |
| `pnl_delta_tail` | `none` | `tail_prob_ge_0p30` | `5` | `+50.2400` | `+389.5310` | `-0.6120` | `+0.5354` | `3` | month / role trades / side share |
| `pnl_delta_tail` | `none` | `positive_bias_and_tail_miss_ge_0p10` | `5` | `+54.0030` | `+393.2940` | `-0.6120` | `+0.5354` | `3` | month / role trades / side share |

`pred_pnl_lt0_switch_veto` 有無はbestを変えなかった。bestはplain `pnl` / reliability-gated / veto有無で同じ結果に収束した。

Selector pass count:

- `0 / 864`

Scenario-weighted gate effect by score mode:

| score mode | gate | before rows | after rows | positive pred count | positive pred actual PnL | positive pred losses | veto count | veto actual PnL | veto positive losses | veto wins |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `pnl` | `positive_bias_and_tail_miss_ge_0p10` | `1751` | `962` | `1581` | `-6018.8514` | `870` | `789` | `-6135.8956` | `563` | `226` |
| `pnl` | `tail_prob_ge_0p30` | `1751` | `1344` | `1581` | `-6018.8514` | `870` | `407` | `-5949.1134` | `318` | `89` |
| `pnl_tail_reliability_gated` | `positive_bias_and_tail_miss_ge_0p10` | `1747` | `958` | `1573` | `-5900.2914` | `862` | `789` | `-6135.8956` | `563` | `226` |
| `pnl_tail_reliability_gated` | `tail_prob_ge_0p30` | `1747` | `1340` | `1573` | `-5900.2914` | `862` | `407` | `-5949.1134` | `318` | `89` |

Key reading:

- Candidate surfaceでは両gateとも負け候補を大量に削る。00347のpointwise診断は間違っていない。
- しかしstateful bestでは、`tail_prob_ge_0p30` はbest EV2/tail0.3候補に発火せずno-op。
- `positive_bias_and_tail_miss_ge_0p10` はbest EV2/tail0.3で4件をvetoし、veto actual PnLは `+43.4600`。勝ち候補を削ったため、EV2 scenarioはcombined `+400.1440 -> +387.4240` に悪化した。
- positive-bias gateのbestはEV -2へ移動し、5 trades / added PnL `+54.0030` / combined `+393.2940`。gateなしbestより `-6.8500` 低い。
- 00347で見えた「正の予測PnL候補全体は負けやすい」という問題は本物。ただしglobal hard gateでは、少数の良いsupport repair候補も一緒に削る。

Best trade set comparison:

| gate | role | month | side | horizon | pred PnL | tail prob | actual PnL | residual bias | residual tail miss |
|---|---|---|---|---:|---:|---:|---:|---:|---:|
| `none` | `refit2025_validation` | `2025-07` | short | `720` | `+3.9724` | `0.2962` | `+26.4000` | `-8.4610` | `0.1715` |
| `none` | `refit2025_validation` | `2025-08` | long | `720` | `+3.3697` | `0.2141` | `+12.7200` | `+30.9603` | `0.5550` |
| `none` | `refit2025_validation` | `2025-08` | short | `720` | `+2.7232` | `0.2683` | `+0.3400` | `-8.5328` | `0.1705` |
| `none` | `hybrid2025_0912_external` | `2025-11` | short | `60` | `+2.3420` | `0.2411` | `+10.4400` | `-0.7721` | `0.1476` |
| `none` | `hybrid2025_0912_external` | `2025-10` | long | `720` | `+2.3111` | `0.2573` | `+10.9530` | `-6.1346` | `0.1347` |
| `positive_bias_and_tail_miss_ge_0p10` | `refit2025_validation` | `2025-08` | long | `60` | `+1.3456` | `0.1971` | `+5.8700` | `+1.5500` | `0.0338` |

The positive-bias gate removed the profitable `refit2025_validation 2025-08 long 720m` row because its residual prior warned strongly. It then selected the weaker 60m alternative in the EV -2 scenario.

## Decision

- `--positive-pnl-gate-rules`: accepted infrastructure.
- `broad_prior_horizon_choice_positive_pnl_gate_summary.csv`: accepted diagnostic output.
- `positive_bias_and_tail_miss_ge_0p10`: reject as a hard stateful candidate gate for the current policy surface.
- `tail_prob_ge_0p30`: no-op on best; keep as diagnostic/soft feature, not as standard hard gate.
- Direct positive-PnL trust gates are too coarse. The next useful direction is not another global hard cutoff but calibrated expected PnL / downside confidence by horizon and context.
- Standard policy remains NoTrade.

## Next

1. Replace global hard gate with soft penalty or calibrated lower-bound score using the same positive-PnL failure signals.
2. Split calibration by horizon/context; 720m long `refit2025 2025-08` should not be treated the same as 720m short `hybrid2025 2025-11`.
3. Add scenario-level diagnostics for "gate removes winner" cases and use them as over-gating tests.
4. Continue addressing structural blockers: month floor, role trades, side share. Gate-only changes are not solving these blockers.

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_broad_prior_horizon_choice_replay.py tests/test_entry_ev_broad_prior_horizon_choice_replay.py`: OK
- `uv run python -m unittest tests.test_entry_ev_broad_prior_horizon_choice_replay`: OK
- 00348 positive PnL gate stateful replay: OK
