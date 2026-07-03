# Entry EV Tail Selected Residual Diagnostics

日時: 2026-07-03 13:56 JST
更新日時: 2026-07-03 13:56 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00356の次アクションとして、tail ceiling通過後のpositive predicted PnL failureを、実際のselector boundary周辺に限定して診断した。
- `entry_ev_tail_selected_residual_diagnostics.py` を追加し、00354 no-penalty candidatesを00354 `broad_prior_horizon_choice_additions.csv` / `rejections.csv` とscenario/candidate keyで突き合わせた。
- 重要な修正として、row-weighted集計だけでなく `candidate_identity_key` dedupを追加した。同じmarket eventがscore mode / threshold scenarioで何十回も数えられるため、policy判断はdedup側を主に見る。
- candidate identity dedupでは、tail pass positiveは118件 / `-90.3858`、loss 61件 / `-365.8848`、win 57件 / `+275.4990`。
- actual selected additionsに絞ると、tail pass positiveは8件 / `+59.0070`、lossは1件 / `-29.1360`、winは7件 / `+88.1430`。selected lossは `fresh2024_validation 2024-08 long 720m` の1件だけ。
- selected lossの特徴は `pred_pnl < 2`, prior mean `< 0`, prior tail `0.414536`, prior risk `9.977267`。このうち `pred_pnl_lt_2` はcandidate identity dedupのselected additionsでは1件だけをflagし、win damage 0だった。
- ただし支持はunique 1件だけ。`pred_pnl_lt_2` を標準policyへ昇格せず、pre-registered stateful replay候補として扱う。
- 判断: tail-pass residual failureは全候補面では広いが、実際のselected損失はsingleton。次は `selected tail-pass pred_pnl_lt2` 系のabstentionをstateful replayに戻す。ただし標準policyはNoTrade。

## Artifacts

Added script:

- `scripts/experiments/entry_ev_tail_selected_residual_diagnostics.py`

Added tests:

- `tests/test_entry_ev_tail_selected_residual_diagnostics.py`

Run:

- `data/reports/backtests/20260703_045520_20260703_entry_ev_00357_tail_selected_residual_diagnostics/`

Key outputs:

- `tail_selected_residual_overall_summary.csv`
- `tail_selected_residual_outcome_summary.csv`
- `tail_selected_residual_group_summary.csv`
- `tail_selected_residual_rule_summary.csv`
- `tail_selected_residual_cases.csv`
- `tail_selected_residual_unique_cases.csv`
- `tail_selected_residual_failure_rows.csv`
- `config.json`

## Method

- Candidate scope: 00354 `ranker_replay_candidates_*.csv` 全56本。
- Label filter: `positive_pnl_penalty_label=none`。
- Additions: 00354 `broad_prior_horizon_choice_additions.csv`。
- Rejections: 00354 `broad_prior_horizon_choice_rejections.csv`。
- Tail ceiling: `hv_chosen_pred_tail_loss_prob <= 0.3`。
- Focus scopes:
  - all tail-pass positive candidates
  - selected additions
  - near selected boundary
  - within quota
  - quota or near selected boundary
- Dedup modes:
  - `row_weighted`
  - `candidate_identity_key`
- Rank order:
  - `repair_score desc`
  - `support_reduction_value desc`
  - `repair_expected_pnl desc`
  - `decision_timestamp asc`
  - `entry_timestamp asc`
  - `hv_chosen_horizon_minutes asc`
- Near window: selected boundary + 3 rank。

## Results

Overall comparison:

| dedup | scope | tail pass positive | tail pass PnL | loss count | loss PnL | selected tail pass | selected PnL | selected loss | selected loss PnL | near-boundary count | near-boundary PnL | near-boundary loss |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| row-weighted | overall | `9308` | `-120.6816` | `4360` | `-28128.7296` | `1040` | `+9044.3480` | `96` | `-2797.0560` | `2876` | `+12833.4064` | `600` |
| candidate identity | overall | `118` | `-90.3858` | `61` | `-365.8848` | `8` | `+59.0070` | `1` | `-29.1360` | `28` | `+62.9114` | `8` |

Selection outcome, candidate identity dedup:

| selection outcome | row scope | tail pass count | PnL | loss count | loss PnL | win PnL | selected count |
|---|---|---:|---:|---:|---:|---:|---:|
| `selected` | `available_candidates` | `6` | `+31.7170` | `1` | `-29.1360` | `+60.8530` | `6` |
| `selected` | `greedy_selected` | `2` | `+27.2900` | `0` | `0.0000` | `+27.2900` | `2` |
| `quota_full` | `available_candidates` | `104` | `-157.6648` | `59` | `-327.4608` | `+169.7960` | `0` |
| `quota_full` | `greedy_selected` | `6` | `+8.2720` | `1` | `-9.2880` | `+17.5600` | `0` |

Unique selected tail-pass failure:

| role/month | side | timestamp UTC | horizon | pred PnL | actual PnL | tail prob | prior mean | prior tail | prior risk | rank |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `fresh2024_validation 2024-08` | long | `2024-08-22 03:39` | `720m` | `+1.4813` | `-29.1360` | `0.167651` | `-3.499252` | `0.414536` | `9.977267` | `1 / 1` |

Selected-addition rule summary, candidate identity dedup:

| rule | evaluated | flagged | flagged PnL | failure precision | failure recall | flagged win PnL | kept PnL |
|---|---:|---:|---:|---:|---:|---:|---:|
| `pred_pnl_lt_2` | `8` | `1` | `-29.1360` | `1.0000` | `1.0000` | `0.0000` | `+88.1430` |
| `prior_mean_lt_0` | `8` | `3` | `-2.6360` | `0.3333` | `1.0000` | `+26.5000` | `+61.6430` |
| `prior_tail_ge_0p30` | `8` | `3` | `-2.6360` | `0.3333` | `1.0000` | `+26.5000` | `+61.6430` |
| `positive_bias_and_tail_miss_ge_0p10` | `8` | `3` | `-2.6360` | `0.3333` | `1.0000` | `+26.5000` | `+61.6430` |
| `horizon_720m` | `8` | `7` | `+48.5670` | `0.1429` | `1.0000` | `+77.7030` | `+10.4400` |

Near-boundary rule summary, candidate identity dedup:

| rule | evaluated | flagged | flagged PnL | failure precision | failure recall | flagged win PnL | kept PnL |
|---|---:|---:|---:|---:|---:|---:|---:|
| `pred_pnl_lt_2` | `28` | `13` | `-69.0904` | `0.4615` | `0.7500` | `+22.4300` | `+132.0018` |
| `pred_pnl_lt_1` | `28` | `1` | `-12.0000` | `1.0000` | `0.1250` | `0.0000` | `+74.9114` |
| `prior_mean_lt_0` | `28` | `16` | `-2.9404` | `0.3125` | `0.6250` | `+76.5800` | `+65.8518` |
| `positive_bias_and_tail_miss_ge_0p10` | `28` | `11` | `+7.5120` | `0.1818` | `0.2500` | `+65.8200` | `+55.3994` |

## Interpretation

- 00356の「全候補ではtail-pass residual failureが広い」という見え方は正しいが、実際のselected additionsではかなり狭い。candidate identity dedupではselected tail-pass lossは1件だけ。
- この1件は以前のsingleton negative `fresh2024_validation 2024-08 long 720m -29.1360` と同じ問題で、00337/00338で見た `singleton_720_pred_pnl_lt2` 系の診断と整合する。
- `pred_pnl_lt_2` はselected additions dedupではcleanだが、支持がunique 1件に過ぎない。標準化するには過学習リスクが大きい。
- near-boundaryまで広げると `pred_pnl_lt_2` は13件 / `-69.0904` をflagし、kept PnL `+132.0018` なので有用なscreen候補ではある。ただしfailure precisionは `0.4615` で、選択近傍でもwin damageが残る。
- prior/risk/residual系ruleはselected lossを拾うが、同時にselected winnersも削る。global hard gateではなく、singleton/selected-specific abstentionとして再検証する。
- `greedy_selected` row_scopeだけを見るとselected loss 0になるが、selection artifact上のactual additionsでは `available_candidates` 側にselected lossが存在する。この2つを混同しない。

## Decision

- tail selected residual diagnostics are accepted infrastructure.
- `selected tail-pass pred_pnl_lt2` / `singleton_720_pred_pnl_lt2` は次のpre-registered stateful replay候補。
- ただしunique selected failure 1件だけなので、標準policyにはしない。
- prior mean/tail/risk、positive-bias residual ruleはselected-specific featureとして保持するが、global hard gateとしてはreject。
- 標準policyはNoTrade。

## Next

1. `selected tail-pass pred_pnl_lt2` をstateful replayへ戻し、actual selected lossを止めてもreplacement / skipped future winner / support blockersが悪化しないか確認する。
2. 同時に `singleton_720_pred_pnl_lt2` と比較し、00337/00338のsingleton診断と00357のselected residual診断が同じfailureだけを拾っているか確認する。
3. near-boundary `pred_pnl_lt2` はfeature候補に留め、global hard gateとしては採用しない。
4. `fresh2024_validation 2024-08 long 720m` はexit/horizon calibrationとentry abstentionの両方で追跡する。

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_tail_selected_residual_diagnostics.py tests/test_entry_ev_tail_selected_residual_diagnostics.py`: OK
- `uv run python -m unittest tests.test_entry_ev_tail_selected_residual_diagnostics`: OK
- 00357 tail selected residual diagnostics: OK
