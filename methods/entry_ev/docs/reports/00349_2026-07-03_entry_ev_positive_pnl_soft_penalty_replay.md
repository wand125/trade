# Entry EV Positive PnL Soft Penalty Replay

日時: 2026-07-03 11:43 JST
更新日時: 2026-07-03 11:43 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00348でpositive-PnL failure hard gateがno-opまたは悪化だったため、候補を削らずrepair scoreだけを下げるsoft penaltyをstateful replayへ追加した。
- `--positive-pnl-penalty-specs` を追加し、`mode:weight` 形式で `none:0`, `residual_bias_tail_miss:0.05/0.10/0.25`, `tail_prob:1/2/5` を比較した。
- replayは2016条件を実行。selector passは `0 / 2016`。
- `residual_bias_tail_miss` はbest EV2 scenarioで勝ち候補にもpenaltyを与えるが、weight `0.25` までbest trade setは変わらず、combined `+400.1440` のまま。改善ではなくno-op。
- `tail_prob` はweight `1/2` ではbest no-op、weight `5` でbestが4 tradesへ減り、combined `+399.8040` に悪化。
- 判断: positive-PnL soft penalty replay infrastructureはaccepted。今回のglobal soft penalty群は標準policy候補としてreject。次はglobal penaltyではなく、winnerを巻き込まないhorizon/context別calibrationまたはover-gating detectorへ進む。標準policyはNoTrade。

## Artifacts

Changed script:

- `scripts/experiments/entry_ev_broad_prior_horizon_choice_replay.py`

Changed tests:

- `tests/test_entry_ev_broad_prior_horizon_choice_replay.py`

Run:

- `data/reports/backtests/20260703_023929_20260703_entry_ev_00349_positive_pnl_soft_penalty_replay/`

Main outputs:

- `broad_prior_horizon_choice_replay_summary.csv`
- `broad_prior_horizon_choice_positive_pnl_penalty_summary.csv`
- `broad_prior_horizon_choice_additions.csv`
- `ranker_replay_candidates_{mode}__ppp_{penalty}.csv`
- `config.json`

## Method

New replay hook:

- `positive_pnl_penalty_mode="none"`: no soft penalty.
- `positive_pnl_penalty_mode="residual_bias_tail_miss"`:
  - signal = `max(chosen residual bias, 0) * chosen residual tail miss rate`
  - amount = `weight * signal`
- `positive_pnl_penalty_mode="tail_prob"`:
  - signal = `hv_chosen_pred_tail_loss_prob`
  - amount = `weight * signal`

The amount is added to `repair_duration_risk_penalty_amount` before `add_repair_utility_columns(...)`, so candidates remain available but their `repair_score` is reduced. Actual PnL is used only for diagnostics, not for scoring.

## Results

Best by penalty label:

| penalty | added | added PnL | combined | month min | role PnL min | extra trades needed | blockers |
|---|---:|---:|---:|---:|---:|---:|---|
| `none` | `5` | `+60.8530` | `+400.1440` | `-0.6120` | `+0.5354` | `3` | month / role trades / side share |
| `residual_bias_tail_miss_w0p05` | `5` | `+60.8530` | `+400.1440` | `-0.6120` | `+0.5354` | `3` | month / role trades / side share |
| `residual_bias_tail_miss_w0p1` | `5` | `+60.8530` | `+400.1440` | `-0.6120` | `+0.5354` | `3` | month / role trades / side share |
| `residual_bias_tail_miss_w0p25` | `5` | `+60.8530` | `+400.1440` | `-0.6120` | `+0.5354` | `3` | month / role trades / side share |
| `tail_prob_w1` | `5` | `+60.8530` | `+400.1440` | `-0.6120` | `+0.5354` | `3` | month / role trades / side share |
| `tail_prob_w2` | `5` | `+60.8530` | `+400.1440` | `-0.6120` | `+0.5354` | `3` | month / role trades / side share |
| `tail_prob_w5` | `4` | `+60.5130` | `+399.8040` | `-0.6120` | `+0.5354` | `4` | month / role trades / side share |

Selector pass count:

- `0 / 2016`

Best EV2 trade set impact:

| penalty | affected trade | penalty amount | repair score after penalty | actual PnL | effect |
|---|---|---:|---:|---:|---|
| `residual_bias_tail_miss_w0p05` | `refit2025_validation 2025-08 long 720m` | `0.8592` | `3.2964` | `+12.7200` | still selected |
| `residual_bias_tail_miss_w0p1` | same | `1.7184` | `2.4373` | `+12.7200` | still selected |
| `residual_bias_tail_miss_w0p25` | same | `4.2960` | `-0.1403` | `+12.7200` | still in best set through scenario selection |
| `tail_prob_w5` | many positive-pred rows | p0.45 EV2 penalty sum `40.6889` | lower score surface | p0.45 EV2 added PnL `+47.4930` | best moves to p0.6 EV2, 4 trades |

Scenario-level readings for `pnl / none / available_candidates`:

| penalty | prob | EV | tail | added PnL | combined | penalty rows | penalized actual PnL | penalized wins | penalized losses |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `residual_bias_tail_miss_w0p05` | `0.45` | `2` | `0.3` | `+60.8530` | `+400.1440` | `4` | `+43.4600` | `4` | `0` |
| `residual_bias_tail_miss_w0p1` | `0.45` | `2` | `0.3` | `+60.8530` | `+400.1440` | `4` | `+43.4600` | `4` | `0` |
| `residual_bias_tail_miss_w0p25` | `0.45` | `2` | `0.3` | `+60.8530` | `+400.1440` | `4` | `+43.4600` | `4` | `0` |
| `tail_prob_w1` | `0.45` | `2` | `0.3` | `+60.8530` | `+400.1440` | `31` | `+85.1660` | `22` | `9` |
| `tail_prob_w2` | `0.45` | `2` | `0.3` | `+60.8530` | `+400.1440` | `31` | `+85.1660` | `22` | `9` |
| `tail_prob_w5` | `0.45` | `2` | `0.3` | `+47.4930` | `+386.7840` | `31` | `+85.1660` | `22` | `9` |

Key reading:

- `residual_bias_tail_miss` is directionally useful on the broad candidate surface, but on the best EV2 scenario it penalizes only winners. That explains why hard gate damaged 00348 and why soft weights are no better than no-op.
- `tail_prob` is too broad. At high weight it lowers many winners along with losses and reduces activity/support.
- No tested soft penalty fixes `month_pnl_below_floor`, `role_trades_low`, or `side_share_high`.

## Decision

- `--positive-pnl-penalty-specs`: accepted infrastructure.
- `broad_prior_horizon_choice_positive_pnl_penalty_summary.csv`: accepted diagnostic output.
- Global `residual_bias_tail_miss` soft penalty: reject as policy candidate in current form. Light weights are no-op; stronger use risks winner damage.
- Global `tail_prob` soft penalty: reject. Weight `5` worsens best outcome and support.
- Standard policy remains NoTrade.

## Next

1. Stop trying global positive-PnL cutoff/penalty as the main route.
2. Build over-gating diagnostics: explicitly flag cases where risk signals penalize realized winners in best/near-best scenarios.
3. Split risk calibration by horizon/side/regime/session. In particular, `refit2025 2025-08 long 720m` should not share a global residual-bias rule with losing 720m short contexts.
4. Move back to structural blockers: month floor, role trades, side share, and candidate generation gaps.

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_broad_prior_horizon_choice_replay.py tests/test_entry_ev_broad_prior_horizon_choice_replay.py`: OK
- `uv run python -m unittest tests.test_entry_ev_broad_prior_horizon_choice_replay`: OK
- 00349 positive PnL soft penalty replay: OK
