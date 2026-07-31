# Entry EV Contextual Positive PnL Soft Penalty Replay

日時: 2026-07-03 13:09 JST
更新日時: 2026-07-03 13:09 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00353の次アクションとして、contextual positive-bias confidenceをhard gateではなくrepair scoreのsoft penaltyへ接続した。
- `--positive-pnl-penalty-specs` に `contextual_confidence` と `contextual_confidence_delta` を追加した。
- `contextual_confidence` はconfidenceが立った候補にbinary signal `1.0` を与える。
- `contextual_confidence_delta` はconfidenceが立った候補に `prior_pointwise_gate_delta / 100` を与える。00353 veto rowsのdeltaはおおむね `70..174` なので、signalは `0.7..1.74` 程度。
- 00353と同じreplay条件で `none`, `contextual_confidence:1/2/5`, `contextual_confidence_delta:1/2/5` を比較した。
- 候補段階では各labelで656 rowsをpenalizeし、penalized PnLは `-9779.2960`、loss 624 / win 32。候補risk signalは再現した。
- ただし選択された additions で `positive_pnl_penalty_amount > 0` は0件。最終summary差分は全penalty labelで `0 / 288` scenarios、best combinedはすべて `+400.1440`。
- 判断: contextual soft penalty hookはaccepted infrastructure。ただし現行repair selectorの最終採用集合とは交差せず、標準policy改善なし。標準policyはNoTrade。

## Artifacts

Updated script:

- `scripts/experiments/entry_ev_broad_prior_horizon_choice_replay.py`

Updated tests:

- `tests/test_entry_ev_broad_prior_horizon_choice_replay.py`

Run:

- `data/reports/backtests/20260703_040425_20260703_entry_ev_00354_contextual_positive_pnl_soft_penalty_replay/`

## Method

New penalty modes:

- `contextual_confidence`
- `contextual_confidence_delta`

Contextual confidence definition:

- Same as 00353:
  - pointwise flag: positive predicted PnL + chosen residual bias > 0 + chosen residual tail miss rate >= 0.10
  - context: scenario + chosen horizon + side + month
  - prior: months strictly before target month
  - support2 and confidence thresholds:
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
- positive PnL gate: `none`
- positive PnL penalties:
  - `none:0`
  - `contextual_confidence:1`
  - `contextual_confidence:2`
  - `contextual_confidence:5`
  - `contextual_confidence_delta:1`
  - `contextual_confidence_delta:2`
  - `contextual_confidence_delta:5`
- residual prior support: `min_residual_prior_rows=5`, `min_residual_prior_months=2`

## Results

Best summary by penalty:

| penalty label | best combined | best added | best month min | scenarios |
|---|---:|---:|---:|---:|
| `none` | `+400.1440` | `+60.8530` | `-0.6120` | `288` |
| `contextual_confidence_w1` | `+400.1440` | `+60.8530` | `-0.6120` | `288` |
| `contextual_confidence_w2` | `+400.1440` | `+60.8530` | `-0.6120` | `288` |
| `contextual_confidence_w5` | `+400.1440` | `+60.8530` | `-0.6120` | `288` |
| `contextual_confidence_delta_w1` | `+400.1440` | `+60.8530` | `-0.6120` | `288` |
| `contextual_confidence_delta_w2` | `+400.1440` | `+60.8530` | `-0.6120` | `288` |
| `contextual_confidence_delta_w5` | `+400.1440` | `+60.8530` | `-0.6120` | `288` |

Delta vs no penalty:

| penalty label | changed scenarios | best delta | worst delta | mean delta |
|---|---:|---:|---:|---:|
| all contextual labels | `0` | `0.0000` | `0.0000` | `0.0000` |

Penalty scope:

| penalty label group | penalized rows | penalized PnL | loss rows | loss PnL | win rows | win PnL |
|---|---:|---:|---:|---:|---:|---:|
| each contextual label | `656` | `-9779.2960` | `624` | `-9799.7760` | `32` | `+20.4800` |

Selection intersection:

| check | value |
|---|---:|
| selected additions with `positive_pnl_penalty_amount > 0` | `0` |
| scenarios whose final replay summary changed vs `none` | `0` |

Interpretation:

- 00353と同じrisk signalはsoft penaltyでも候補面に出ている。
- しかし現行のrepair selectorは、このrisk surfaceを最終採用候補として選んでいない。
- よってhard gateでもsoft penaltyでも、現在のbest additionsには届かない。
- 次の問題はrisk signalの良し悪しではなく、「penalized rowsがquota group内でどの順位にいるか」「near-selectedなのか」「候補生成不足targetと交差しているか」である。

## Decision

- `contextual_confidence` / `contextual_confidence_delta` penalty modes are accepted infrastructure.
- 今回のsoft penalty labelsは標準policy候補としてreject。改善なし。
- Contextual confidenceはrepair score scalar penaltyではなく、listwise/near-selected diagnostics、quota group feature、admission explanationへ回す。
- 標準policyはNoTrade。

## Next

1. Penalized rowsがquota group内で何位か、selected rowとの差分がどれだけあるかを診断する。
2. Penalized rowsがthin-month targetの候補生成不足 (`fresh2024 2024-11`, `refit2025 2025-03`) と交差しているか確認する。
3. Contextual confidenceを直接penaltyにせず、candidate coverage / near-selected risk / support repair objectiveの説明変数として使う。

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_broad_prior_horizon_choice_replay.py tests/test_entry_ev_broad_prior_horizon_choice_replay.py`: OK
- `uv run python -m unittest tests.test_entry_ev_broad_prior_horizon_choice_replay`: OK
- 00354 contextual positive PnL soft penalty replay: OK
