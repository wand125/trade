# Entry EV Contextual Risk Confidence Diagnostics

日時: 2026-07-03 12:17 JST
更新日時: 2026-07-03 12:17 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00350で見えたcontext-specific tail riskを、そのままgate化せず「過去月の同一contextで損失捕捉が十分に確認できた時だけ信用する」診断へ進めた。
- `entry_ev_contextual_risk_confidence_diagnostics.py` を追加し、risk rule x context x monthでprior-only confidenceを計算した。
- 初回row-weighted集計ではconfident contextが出たが、同じmarket candidateが複数replay scenarioで重複してsupportを水増ししていた。実装を修正し、prior confidenceは既定で `market_candidate_key` dedupにした。
- market dedup後のdefault条件では、全ruleで `confident_context_count=0`、`context_risk_flag_count=0`。selected additionを直接削るcaseも0。
- `min_prior_flagged=4` へ緩めると、`720m short / down_normal_vol / london / one_failed_strict_stage` がconfidentになるが、focus側では勝ち候補だけをflagし、scenario-weighted `+465.8400` を削る。薄いprior context gateは壊れやすい。
- `720m short / up_normal_vol / asia / one_failed_strict_stage` は2025-11に明確な損失clusterがあるが、priorが0なのでchronological gate evidenceにはならない。
- 結論: context-specific risk confidence infrastructureはaccepted。今回の exact-context abstention gate は標準policyとしてreject。標準policyはNoTrade。

## Artifacts

Added script:

- `scripts/experiments/entry_ev_contextual_risk_confidence_diagnostics.py`

Added tests:

- `tests/test_entry_ev_contextual_risk_confidence_diagnostics.py`

Main run:

- `data/reports/backtests/20260703_031558_20260703_entry_ev_00351_contextual_risk_confidence_diagnostics/`

Sensitivity run:

- `data/reports/backtests/20260703_031648_20260703_entry_ev_00351_contextual_risk_confidence_min4_sensitivity/`

Superseded initial diagnostic:

- `data/reports/backtests/20260703_031214_20260703_entry_ev_00351_contextual_risk_confidence_diagnostics/`
- This used row-weighted prior support and is not a decision basis.

Main outputs:

- `contextual_risk_monthly_context_summary.csv`
- `contextual_risk_prior_context_summary.csv`
- `contextual_risk_rule_summary.csv`
- `contextual_risk_scenario_summary.csv`
- `contextual_risk_context_summary.csv`
- `contextual_risk_selected_cases.csv`
- `config.json`

## Method

Inputs:

- 00349 `ranker_replay_candidates_*.csv`
- 00349 `broad_prior_horizon_choice_additions.csv`
- 00350 `over_gating_focus_scenarios.csv`

Default context:

- `hv_chosen_horizon_minutes`
- `side`
- `combined_regime`
- `session_regime`
- `near_miss_bucket`

Default confidence thresholds:

- `prior_dedup_mode=market_candidate_key`
- `min_prior_flagged=5`
- `min_prior_gate_delta=10.0`
- `min_prior_loss_precision=0.60`
- `max_prior_winner_damage_ratio=0.25`
- `max_prior_selected_win_count=0`

The confidence decision uses only months before the target month within the same exact context and rule. Actual PnL is diagnostic target/evaluation only.

## Results

Default market-dedup rule summary:

| rule | confident contexts | context risk flags | flagged PnL | selected flagged win PnL | reading |
|---|---:|---:|---:|---:|---|
| `tail_prob_ge_0p30` | `0` | `0` | `0.0000` | `0.0000` | no confident context |
| `tail_prob_ge_0p40` | `0` | `0` | `0.0000` | `0.0000` | no confident context |
| `harmful_prob_ge_0p30` | `0` | `0` | `0.0000` | `0.0000` | no confident context |
| `harmful_prob_ge_0p50` | `0` | `0` | `0.0000` | `0.0000` | no confident context |
| `positive_bias_and_tail_miss_ge_0p10` | `0` | `0` | `0.0000` | `0.0000` | no confident context |
| `residual_tail_miss_ge_0p10` | `0` | `0` | `0.0000` | `0.0000` | no confident context |
| `horizon_720m` | `0` | `0` | `0.0000` | `0.0000` | no confident context |

Target context audit:

| context | rule | month | current flagged unique | current flagged PnL | prior flagged | prior gate delta | default confident | reading |
|---|---|---|---:|---:|---:|---:|---|---|
| `720m short / down_normal_vol / london / one_failed_strict_stage` | `tail_prob_ge_0p30` | `2025-07` | `4` | `-178.0692` | `0` | `0.0000` | false | first evidence month |
| `720m short / down_normal_vol / london / one_failed_strict_stage` | `tail_prob_ge_0p30` | `2025-08` | `1` | `+12.9400` | `4` | `+178.0692` | false | min5 avoids a bad gate |
| `720m short / up_normal_vol / asia / one_failed_strict_stage` | `tail_prob_ge_0p30` | `2025-11` | `5` | `-330.4680` | `0` | `0.0000` | false | strong current loss, no prior evidence |

Sensitivity `min_prior_flagged=4`:

| rule | confident contexts | context risk flags | flagged PnL | flagged losses | flagged wins | reading |
|---|---:|---:|---:|---:|---:|---|
| `tail_prob_ge_0p30` | `1` | `36` | `+465.8400` | `0` | `36` | prior loss context flips to winner surface |
| `horizon_720m` | `1` | `36` | `+465.8400` | `0` | `36` | one thin prior month is not enough |

## Decision

- `entry_ev_contextual_risk_confidence_diagnostics.py`: accepted infrastructure.
- Prior support for confidence must be deduplicated by unique market candidate by default. Row-weighted scenario support is not acceptable evidence.
- Exact-context risk gates are not adopted. Default threshold yields no confident contexts; loosening to 4 prior flagged examples immediately creates winner over-gating.
- `tail_prob_ge_0p30` remains useful as a diagnostic context risk signal, not as a standard hard gate.
- Standard policy remains NoTrade.

## Next

1. Add `prior_month_count` / unique decision count diagnostics so support is not only row count.
2. Replace exact-context hard confidence with hierarchical/shrunk context risk: horizon/side first, then regime/session only when support is real.
3. Treat 2025-11 `720m short / up_normal_vol / asia` as a holdout-style warning cluster until another prior month supports it.
4. Continue focusing on candidate generation, exit timing, and expected PnL calibration instead of thin post-hoc risk gates.

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_contextual_risk_confidence_diagnostics.py tests/test_entry_ev_contextual_risk_confidence_diagnostics.py`: OK
- `uv run python -m unittest tests.test_entry_ev_contextual_risk_confidence_diagnostics`: OK
- 00351 default market-dedup contextual risk confidence diagnostics: OK
- 00351 `min_prior_flagged=4` sensitivity diagnostics: OK
