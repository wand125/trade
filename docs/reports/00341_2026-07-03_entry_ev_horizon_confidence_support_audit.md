# Entry EV Horizon Confidence Support Audit

日時: 2026-07-03 09:30 JST
更新日時: 2026-07-03 09:30 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00340で見えた `fresh2024 2024-03` の240m優位を、target-local ruleではなく、00329/00341 scored examples上のhorizon-confidence監査として広げた。
- `scripts/experiments/entry_ev_horizon_confidence_support_audit.py` を追加し、target別に candidate availability、horizon別actual、prediction scoreだけで選んだhorizon、fixed horizon / oracle比較、fold supportを出力するようにした。
- 00329 baselineでは `fresh2024 2024-03 long` は51 rows / 17 decisionsが全て `ranker_core_model_used=false` で、scoreは60mを17/17選び `-137.9060`。fixed 240mは `+49.0950`。
- `min_train_months=1` / `min_train_rows=50` まで緩めるとfresh03はmodel-used 17/17になり、`score_pnl` は240mを7/17選んで `-69.6140` まで改善する。ただし固定240m `+49.0950` には遠く、標準policy候補ではない。
- 同じfresh03でtail-aware scoreは悪化した。`score_pnl_minus_tail` は `-128.0160`、`score_pnl_delta_tail` は `-111.0260`。fold summaryでも `tail_loss` AUCは `0.2384` と悪く、early supportのtail calibrationが逆向きに近い。
- `fresh2024 2024-11 long` はavailable rowsがなく、`refit2025 2025-03 short` はavailable / greedy rowsとも0。これはhorizon rerankingではなく候補生成不足として扱う。
- 判断: horizon-confidence support auditはaccepted infrastructure。`min_train_months=1` は診断のみで、global early-support relaxationとしては採用しない。tail-aware early scoreもreject。標準policyはNoTrade。

## Artifacts

Added script:

- `scripts/experiments/entry_ev_horizon_confidence_support_audit.py`

Added tests:

- `tests/test_entry_ev_horizon_confidence_support_audit.py`

Runs:

- `data/reports/backtests/20260703_002805_20260703_entry_ev_00341_broad_prior_horizon_choice_mintrain1/`
- `data/reports/backtests/20260703_003050_20260703_entry_ev_00341_horizon_confidence_support_audit_00329_reg/`
- `data/reports/backtests/20260703_003050_20260703_entry_ev_00341_horizon_confidence_support_audit_mintrain1/`

Outputs:

```text
horizon_confidence_audit_rows.csv
horizon_confidence_horizon_summary.csv
horizon_confidence_choice_summary.csv
horizon_confidence_candidate_choices.csv
horizon_confidence_missing_targets.csv
horizon_confidence_fold_support.csv
config.json
```

## Method

Inputs:

```text
00329 baseline scored examples:
data/reports/backtests/20260702_213026_20260703_entry_ev_00329_broad_prior_horizon_choice_replay_reg_s1/broad_prior_horizon_choice_scored_examples.csv

00341 mintrain1 scored examples:
data/reports/backtests/20260703_002805_20260703_entry_ev_00341_broad_prior_horizon_choice_mintrain1/broad_prior_horizon_choice_scored_examples.csv
```

Audit targets:

```text
fresh2024_validation:2024-03:long
fresh2024_validation:2024-08:long
fresh2024_validation:2024-11:long
refit2025_validation:2025-03:short
refit2025_validation:2025-07:short
```

The audit evaluates candidate choice with prediction-only scores:

```text
score_pnl = ranker_pred_pnl
score_pnl_minus_tail = ranker_pred_pnl - 2.0 * ranker_pred_tail_loss_prob
score_pnl_delta_tail = ranker_pred_pnl + 0.25 * positive_delta_vs_60 + 0.5 * beats60_prob - 2.0 * tail_loss_prob
score_executable_pnl_tail = ranker_pred_pnl + executable_prob - 2.0 * tail_loss_prob
```

Actual PnL is used only for evaluation, oracle comparison, fixed-horizon comparison, and teacher diagnostics. It is not used as an executable feature or tie-breaker.

## Candidate Availability

Missing target summary was identical for the baseline and mintrain1 runs:

| target | available rows | available decisions | greedy rows | greedy decisions | reading |
|---|---:|---:|---:|---:|---|
| `fresh2024 2024-03 long` | `51` | `17` | `3` | `1` | horizon confidence problem with enough row x horizon examples |
| `fresh2024 2024-08 long` | `42` | `14` | `3` | `1` | model-used rows exist, but bad 720m choice remains |
| `fresh2024 2024-11 long` | `0` | `0` | `3` | `1` | available candidate generation gap |
| `refit2025 2025-03 short` | `0` | `0` | `0` | `0` | candidate generation gap |
| `refit2025 2025-07 short` | `30` | `10` | `3` | `1` | horizon choice still fails under current scores |

## Results

### fresh2024 2024-03 long

Baseline 00329:

| score | candidates | chosen actual | oracle actual | fixed 60m | fixed 240m | fixed 720m | chosen 60m | chosen 240m | model-used |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `score_pnl` | `17` | `-137.9060` | `+49.0950` | `-137.9060` | `+49.0950` | `-99.9060` | `17` | `0` | `0` |

Mintrain1 sensitivity:

| score | candidates | chosen actual | oracle actual | fixed 60m | fixed 240m | fixed 720m | chosen 60m | chosen 240m | model-used |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `score_pnl` | `17` | `-69.6140` | `+49.0950` | `-137.9060` | `+49.0950` | `-99.9060` | `10` | `7` | `17` |
| `score_pnl_minus_tail` | `17` | `-128.0160` | `+49.0950` | `-137.9060` | `+49.0950` | `-99.9060` | `16` | `1` | `17` |
| `score_pnl_delta_tail` | `17` | `-111.0260` | `+49.0950` | `-137.9060` | `+49.0950` | `-99.9060` | `14` | `3` | `17` |
| `score_executable_pnl_tail` | `17` | `-128.0160` | `+49.0950` | `-137.9060` | `+49.0950` | `-99.9060` | `16` | `1` | `17` |

Fold support:

| target | train months | train rows | model-used | PnL actual mean | PnL pred mean | PnL MAE | executable AUC | tail-loss AUC | beats60 AUC |
|---|---:|---:|---|---:|---:|---:|---:|---:|---:|
| baseline fresh03 | `1` | `828` | `false` | `-4.0132` | fallback constant | `6.9643` | `0.5000` | `0.5000` | `0.5000` |
| mintrain1 fresh03 | `1` | `828` | `true` | `-4.0132` | `0.0606` | `6.9643` | `0.6667` | `0.2384` | `0.9052` |

Reading:

- Lowering train support turns on a weak but real PnL / beats60 signal for fresh03.
- The same early support produces bad tail-loss calibration. Tail-aware scores therefore push the selector back toward 60m and worsen the result.
- This is support-threshold sensitivity, not a robust policy improvement.

### Other Targets

| target | key result | reading |
|---|---|---|
| `fresh2024 2024-08 long` | available `score_pnl` remains `-46.3536`; 720m choices remain present | current horizon ranker still fails a model-used month |
| `fresh2024 2024-11 long` | no available rows; greedy 1 decision has oracle/fixed240 `+2.4500` vs chosen `+0.3000` | candidate generation first, horizon confidence second |
| `refit2025 2025-03 short` | no rows | not solvable by reranking this surface |
| `refit2025 2025-07 short` | available `score_pnl` `-185.5712`; greedy `-45.4596` vs fixed60 `-2.4240` | current score can be badly wrong outside fresh03 |

## Interpretation

- 00340のtarget-local diagnosisは方向性として正しかった。fresh03の主問題はentry directionではなく、horizon confidence / exit timing / expected PnL calibration。
- ただし、単純に `min_train_months=1` へ緩めるだけでは汎化に足りない。fresh03のPnL signalは一部拾えるが、tail riskの校正が崩れている。
- `tail_loss` AUCが悪い状態でtail penaltyを入れると、理論上は安全側に見えても実際には良い240m候補を削る。
- `fresh11` / `refit03` のようにcandidate rowsが存在しないtargetは、ranker/headの改善だけでは解けない。別の候補生成pathが必要。

## Decision

- Horizon-confidence support audit: accepted infrastructure.
- `min_train_months=1` sensitivity: diagnostic only, not policy.
- Global early-support relaxation: reject for now.
- Tail-aware early score in the current head: reject for policy.
- Fixed 240m / target-local rule: teacher/hypothesis only.
- Standard policy remains NoTrade.

## Next

1. Build an early-support robust horizon-confidence head that separates PnL / beats60 signal from tail-risk calibration.
2. Calibrate tail-loss by horizon / side / session / regime / support bucket before using it as a score penalty.
3. Add candidate-generation diagnostics for `fresh2024 2024-11` and `refit2025 2025-03`; do not treat missing rows as successful abstention.
4. Keep fixed 240m and actual fixed-best outcomes as teacher/oracle labels only.
5. Recheck whether any new horizon-confidence head improves role/month floor and side-share blockers, not just fresh03 point diagnostics.

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_horizon_confidence_support_audit.py tests/test_entry_ev_horizon_confidence_support_audit.py tests/test_docs_reports.py`: OK
- `uv run python -m unittest tests.test_entry_ev_horizon_confidence_support_audit tests.test_entry_ev_support_repair_target_local_confidence_diagnostics tests.test_docs_reports`: OK
- 00341 mintrain1 broad-prior horizon-choice replay: OK
- 00329 baseline horizon-confidence audit: OK
- 00341 mintrain1 horizon-confidence audit: OK
