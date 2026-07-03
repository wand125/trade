# Entry EV Context H/S Support2 Positive PnL Gate Replay

日時: 2026-07-03 12:53 JST
更新日時: 2026-07-03 12:53 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00352でpre-registered候補にした `horizon,side` + support2 + `positive_bias_and_tail_miss_ge_0p10` をstateful replayへ接続した。
- `--positive-pnl-gate-rules context_hs_support2_positive_bias_tail_miss_ge_0p10` を追加した。
- gateはscenario / chosen horizon / side / month単位で、過去月だけのmonthly prior confidenceを作る。support2条件は `prior_observed_month >= 2`, `prior_flagged_month >= 2`, `prior_decision_count >= 5` を含む。
- 候補段階では各score/abstentionで82 rowsをvetoし、vetoed actual PnLは `-1222.4120`、loss 78 / win 4。risk候補検出としては強い。
- ただしstateful replayの最終採用tradeには当たらず、`none` vs new gateの最終summary差分は `0 / 288` scenarios。bestはどちらも5 trades / added PnL `+60.8530` / combined `+400.1440`。
- 判断: contextual positive-bias gate infrastructureはaccepted。ただし現時点では標準policy改善なし。標準policyはNoTrade。

## Artifacts

Updated script:

- `scripts/experiments/entry_ev_broad_prior_horizon_choice_replay.py`

Updated tests:

- `tests/test_entry_ev_broad_prior_horizon_choice_replay.py`

Final run:

- `data/reports/backtests/20260703_035118_20260703_entry_ev_00353_context_hs_support2_positive_pnl_gate_replay/`

Superseded run:

- `data/reports/backtests/20260703_034223_20260703_entry_ev_00353_context_hs_support2_positive_pnl_gate_replay/`
- 理由: 初回は00352のmonthly contextual confidenceではなく、selected residual priorのcontext specを直接見てしまい、gate発火0だった。00352の意図と違うため破棄。

## Method

New gate rule:

- `context_hs_support2_positive_bias_tail_miss_ge_0p10`

Pointwise rule flag:

- `hv_chosen_pred_pnl > 0`
- chosen horizon residual bias `> 0`
- chosen horizon residual tail miss rate `>= 0.10`

Monthly confidence context:

- scenario columns: `row_scope`, `prob_threshold`, `ev_threshold`, `tail_prob_threshold`, `require_model_used`
- context columns: `hv_chosen_horizon_minutes`, `side`
- prior uses only months strictly before the target month
- synthetic `market_candidate_key` dedup is used before monthly prior aggregation

Confidence thresholds:

- `prior_observed_month_count >= 2`
- `prior_flagged_month_count >= 2`
- `prior_decision_count >= 5`
- `prior_flagged_count >= 5`
- `prior_pointwise_gate_delta >= 10.0`
- `prior_loss_precision >= 0.60`
- `prior_winner_damage_ratio <= 0.25`
- `prior_selected_flagged_win_count <= 0`

Replay settings:

- base branch: 00314 fixed60 margin w5 position quality overlay
- broad horizon viability predictions: 00322
- broad train rows: 00328
- score modes: `pnl`, `pnl_tail_reliability_gated`, `pnl_delta_tail_reliability_gated`, `pnl_delta_tail`
- abstention: `none`, `pred_pnl_lt0_switch_veto`
- gates: `none`, `context_hs_support2_positive_bias_tail_miss_ge_0p10`
- positive PnL penalty: `none:0`
- residual prior support: `min_residual_prior_rows=5`, `min_residual_prior_months=2`

## Results

Final replay comparison:

| metric | gate none | contextual gate |
|---|---:|---:|
| scenarios | `288` | `288` |
| changed scenarios | - | `0` |
| best added count | `5` | `5` |
| best added PnL | `+60.8530` | `+60.8530` |
| best combined PnL | `+400.1440` | `+400.1440` |
| best month min | `-0.6120` | `-0.6120` |
| best blockers | month / role-trades / side-share | month / role-trades / side-share |

Gate candidate-stage totals per score/abstention:

| score/abstention group | veto rows | veto PnL | loss rows | loss PnL | win rows |
|---|---:|---:|---:|---:|---:|
| each of 8 score/abstention groups | `82` | `-1222.4120` | `78` | `-1224.9720` | `4` |

Largest scenario-level veto clusters:

| row scope | prob | EV | tail | veto rows | veto PnL | loss rows | loss PnL | win rows |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| available | `0.45` | `-2` | `0.50` | `26` | `-493.0220` | `25` | `-493.6620` | `1` |
| available | `0.45` | `0` | `0.50` | `26` | `-493.0220` | `25` | `-493.6620` | `1` |
| available | `0.50` | `-2` | `0.50` | `15` | `-118.1840` | `14` | `-118.8240` | `1` |
| available | `0.50` | `0` | `0.50` | `15` | `-118.1840` | `14` | `-118.8240` | `1` |

Interpretation:

- 00352のclean diagnostic signalはstateful replay候補面でも再現した。
- しかし現行repair selectorは、これらのveto対象を最終追加tradeとして選んでいなかった。
- したがってhard prefilterとしては現bestを改善しない。risk score / selector feature / admission explanationとして使うほうが自然。

## Decision

- Monthly contextual positive-bias gate hook is accepted infrastructure.
- Residual context spec/keyをranker candidateへ残す変更もaccepted。vetoed rowsの監査に使える。
- `context_hs_support2_positive_bias_tail_miss_ge_0p10` は候補risk検出としては有効。
- ただし現stateful replayの最終PnL改善は0なので、標準policyへは昇格しない。
- 標準policyはNoTrade。

## Next

1. Hard prefilterではなく、contextual confidenceをrepair scoreのrisk featureまたはlistwise selector featureとして入れる。
2. Veto対象がnear-selectedか、quota group内でどの順位にいるかを診断する。
3. `selected_addition` を持つreplay後candidate fileで同じmonthly confidenceを再集計し、selected winner damageの評価をstateful結果に合わせる。
4. Harmful/residual/tail rulesは引き続きhard gateに戻さず、contextual feature/calibrationとして扱う。

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_broad_prior_horizon_choice_replay.py tests/test_entry_ev_broad_prior_horizon_choice_replay.py`: OK
- `uv run python -m unittest tests.test_entry_ev_broad_prior_horizon_choice_replay`: OK
- final 00353 contextual gate replay: OK
