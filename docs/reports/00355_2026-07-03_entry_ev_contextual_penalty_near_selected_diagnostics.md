# Entry EV Contextual Penalty Near-Selected Diagnostics

日時: 2026-07-03 13:26 JST
更新日時: 2026-07-03 13:26 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00354の次アクションとして、contextual penalty rowsがquota group内で何位にいるか、selected rowとの差分がどれだけあるかを診断した。
- `entry_ev_contextual_penalty_near_selected_diagnostics.py` を追加し、00354の全56 candidate files、additions、rejectionsをscenario/candidate keyで突き合わせた。
- 各contextual labelは656 rows / 26 unique candidate identitiesをpenalizeし、penalized PnL `-9779.2960`, loss 624 / win 32。00354のrisk signalを再確認した。
- selected additionsとの交差は引き続き0件。
- ただし今回の主因は「score順位が遠すぎる」ではなかった。penalized rowsは全件 `tail_prob_ceiling` でpre-filter rejectされていた。
- 00354のreplay configは `max_chosen_tail_prob=0.3`。penalized rowsのtail probabilityは min `0.312885`, median `0.381267`, max `0.451762` で全件が既存tail hard filterを超過していた。
- 一部はquota rank 1にいる。最悪例は `hybrid2025_0912_external 2025-11 short` の720m候補で、quota rank 1、actual `-59.4360`、tail prob `0.366923`。この候補も `tail_prob_ceiling` で落ちていた。
- 判断: contextual positive-bias confidenceは、現行standard replayでは既存tail ceilingと強く重複している。soft penaltyが効かなかった理由は、repair score以前にhard tail filterが候補を全て除外していたため。標準policyはNoTrade。

## Artifacts

Added script:

- `scripts/experiments/entry_ev_contextual_penalty_near_selected_diagnostics.py`

Added tests:

- `tests/test_entry_ev_contextual_penalty_near_selected_diagnostics.py`

Run:

- `data/reports/backtests/20260703_042545_20260703_entry_ev_00355_contextual_penalty_near_selected_diagnostics/`

Key outputs:

- `contextual_penalty_near_selected_label_summary.csv`
- `contextual_penalty_near_selected_score_mode_summary.csv`
- `contextual_penalty_near_selected_outcome_summary.csv`
- `contextual_penalty_near_selected_group_summary.csv`
- `contextual_penalty_near_selected_cases.csv`
- `contextual_penalty_penalized_rows.csv`

## Method

- Candidate scope: 00354 `ranker_replay_candidates_*.csv` 全56本。
- Selection match: `broad_prior_horizon_choice_additions.csv` と `broad_prior_horizon_choice_rejections.csv` をscenario/candidate keyでjoin。
- Scenario columns:
  - `row_scope`
  - `prob_threshold`
  - `ev_threshold`
  - `tail_prob_threshold`
  - `require_model_used`
  - `ranker_score_mode`
  - `ranker_abstention_rule`
  - `positive_pnl_gate_rule`
  - `positive_pnl_penalty_label`
- Quota rank columns:
  - `scenario_key, role, month, side`
- Rank order:
  - `repair_score desc`
  - `support_reduction_value desc`
  - `repair_expected_pnl desc`
  - `decision_timestamp asc`
  - `entry_timestamp asc`
  - `hv_chosen_horizon_minutes asc`
- Near-selected window: selected boundary rank + 3。

## Results

Label-level summary:

| label group | rows | unique candidates | penalized rows | penalized PnL | loss rows | win rows | selected penalized | within quota | near quota | near selected boundary |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| each contextual label | `14006` | `290` | `656` | `-9779.2960` | `624` | `32` | `0` | `16` | `64` | `80..96` |
| `none` | `14006` | `290` | `0` | `0.0000` | `0` | `0` | `0` | `0` | `0` | `0` |

Outcome summary:

| label group | selection outcome | penalized rows | penalized PnL | loss rows | win rows |
|---|---|---:|---:|---:|---:|
| each contextual label | `tail_prob_ceiling` | `656` | `-9779.2960` | `624` | `32` |

Tail probability:

| scope | count | min | median | mean | max |
|---|---:|---:|---:|---:|---:|
| all penalized rows | `3936` | `0.312885` | `0.381267` | `0.367171` | `0.451762` |
| near quota penalized rows | `384` | `0.366923` | `0.377819` | `0.393581` | `0.451762` |

Interpretation:

- contextual risk signalは候補面では強いが、現行standard replayでは `max_chosen_tail_prob=0.3` が先に全件を止めている。
- `tail_prob_ceiling` は今回のcontextual positive-bias failuresに対してすでに十分強いhard filterになっている。
- contextual penaltyをrepair scoreへ入れても、pre-filterを通らない候補には影響できない。
- quota rank 1の危険候補があるため、tail filterを外した場合は大損候補が即座に選択面へ戻るリスクがある。
- したがって次に試すなら「contextual penaltyを強める」ではなく、tail ceilingなし/緩和時のcounterfactual、またはtail filter通過後の残存failureに対象を絞るべき。

## Decision

- contextual penalty near-selected diagnostics are accepted infrastructure.
- 00354のsoft penalty labelsは引き続き標準policy候補としてreject。
- contextual positive-bias confidenceは、現standard replayではtail ceilingの説明/監査signalとして扱う。
- `max_chosen_tail_prob=0.3` を安易に外さない。外す場合は必ずcounterfactual replayとtail-filter通過後のresidual failure診断を先に行う。
- 標準policyはNoTrade。

## Next

1. Tail ceiling通過後にも残るpositive-PnL overestimate/failureを抽出し、contextual confidenceとは別の残存riskを診断する。
2. `max_chosen_tail_prob` を緩めるcounterfactualでは、contextual penalty単体ではなくtail ceilingとの役割分担を明示して比較する。
3. Remaining weak monthsの候補生成不足へ戻る。特に `fresh2024 2024-03`, `fresh2024 2024-11`, `refit2025 2025-03` をtail-filter通過後の候補面で分解する。

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_contextual_penalty_near_selected_diagnostics.py tests/test_entry_ev_contextual_penalty_near_selected_diagnostics.py`: OK
- `uv run python -m unittest tests.test_entry_ev_contextual_penalty_near_selected_diagnostics`: OK
- 00355 contextual penalty near-selected diagnostics: OK
