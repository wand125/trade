# Entry EV Positive Predicted PnL Failure Diagnostics

日時: 2026-07-03 11:04 JST
更新日時: 2026-07-03 11:04 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00346で `ranker_pred_pnl < 0` vetoがbest replayを改善しなかったため、次の弱点である「予測PnLは正なのに実損益が負」の候補面を診断した。
- `entry_ev_positive_pnl_failure_diagnostics.py` を追加し、00346の `ranker_replay_candidates_*.csv` を横断して、positive predicted PnL failureをtail / harmful / prior / residual / support reliabilityで集計した。
- market candidate dedupでは positive predicted PnL 205件中124件が実損失、合計PnLは `-1104.5216`。candidate-key dedupでも1623件中981件が実損失、合計 `-8781.2836`。
- `positive_bias_and_tail_miss_ge_0p10` はmarket dedupで109件をflagし、実損失84件 / failure precision `0.7706` / failure recall `0.6774` / flagged PnL `-1044.5162`。ただし勝ち候補25件 / `+124.2130` も削る。
- `tail_prob_ge_0p30` はmarket dedupで86件をflagし、実損失62件 / precision `0.7209` / recall `0.5000` / flagged PnL `-999.3158`。勝ち候補24件 / `+219.3130` も削る。
- 判断: positive predicted PnL failure diagnosticsはaccepted infrastructure。positive pred PnLをそのまま信用するのは危険。`positive_bias_and_tail_miss` / `tail_prob_ge_0p30` は次のstateful gate/penalty候補だが、現時点ではpointwise診断であり標準policyではない。標準policyはNoTrade。

## Artifacts

Changed script:

- `scripts/experiments/entry_ev_positive_pnl_failure_diagnostics.py`

Changed tests:

- `tests/test_entry_ev_positive_pnl_failure_diagnostics.py`

Run:

- `data/reports/backtests/20260703_020424_20260703_entry_ev_00347_positive_pnl_failure_diagnostics/`

Main outputs:

- `positive_pnl_failure_candidates.csv`
- `positive_pnl_failure_overall_summary.csv`
- `positive_pnl_failure_context_summary.csv`
- `positive_pnl_failure_rule_summary.csv`
- `positive_pnl_failure_cases.csv`
- `config.json`

## Method

Input:

- 00346の8個の `ranker_replay_candidates_*.csv`

Definitions:

- `predicted_positive_pnl`: `hv_chosen_pred_pnl > 0`
- `positive_pred_loss`: `predicted_positive_pnl` かつ `actual_pnl_at_hv_chosen_horizon < 0`
- `positive_pred_win`: `predicted_positive_pnl` かつ `actual_pnl_at_hv_chosen_horizon > 0`
- `positive_pred_overestimate`: `hv_chosen_pred_pnl - actual_pnl_at_hv_chosen_horizon`

Dedup scopes:

- `row_weighted`: threshold / scenario重複込み。
- `candidate_key`: `decision_key + horizon + score_mode + abstention_rule` でdedup。
- `market_candidate_key`: `decision_key + horizon` でdedup。相場イベント寄りの読み。

Rule diagnostics are pointwise. They show what a condition flags on the candidate surface, not what a one-position stateful replay would realize after the candidate surface changes.

## Results

Overall:

| scope | rows | decisions | positive pred | positive pred PnL | loss count | loss rate | loss PnL | win count | win PnL | h60 | h240 | h720 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| row weighted | `14006` | `113` | `12544` | `-47285.8192` | `6878` | `0.5483` | `-81833.8752` | `5666` | `+34548.0560` | `4048` | `3364` | `5132` |
| candidate key | `2260` | `113` | `1623` | `-8781.2836` | `981` | `0.6044` | `-12729.6216` | `642` | `+3948.3380` | `516` | `501` | `606` |
| market candidate key | `290` | `113` | `205` | `-1104.5216` | `124` | `0.6049` | `-1599.3336` | `81` | `+494.8120` | `65` | `64` | `76` |

Available candidate-key by score mode:

| score mode | abstention | positive pred | positive pred PnL | loss count | loss rate | loss PnL | win count | win PnL |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `pnl` | `none` | `192` | `-1040.6908` | `119` | `0.6198` | `-1479.3528` | `73` | `+438.6620` |
| `pnl` | `pred_pnl_lt0_switch_veto` | `192` | `-1040.6908` | `119` | `0.6198` | `-1479.3528` | `73` | `+438.6620` |
| `pnl_delta_tail` | `none` | `185` | `-1017.4014` | `114` | `0.6162` | `-1453.9644` | `71` | `+436.5630` |
| `pnl_delta_tail` | `pred_pnl_lt0_switch_veto` | `187` | `-1025.2494` | `116` | `0.6203` | `-1461.8124` | `71` | `+436.5630` |
| `pnl_delta_tail_reliability_gated` | `none` | `191` | `-1025.8708` | `118` | `0.6178` | `-1464.5328` | `73` | `+438.6620` |
| `pnl_delta_tail_reliability_gated` | `pred_pnl_lt0_switch_veto` | `191` | `-1025.8708` | `118` | `0.6178` | `-1464.5328` | `73` | `+438.6620` |
| `pnl_tail_reliability_gated` | `none` | `191` | `-1025.8708` | `118` | `0.6178` | `-1464.5328` | `73` | `+438.6620` |
| `pnl_tail_reliability_gated` | `pred_pnl_lt0_switch_veto` | `191` | `-1025.8708` | `118` | `0.6178` | `-1464.5328` | `73` | `+438.6620` |

Rule diagnostics, market candidate dedup:

| rule | flagged | flagged PnL | kept PnL | flagged losses | loss PnL | precision | recall | flagged wins | win PnL |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `positive_bias_and_tail_miss_ge_0p10` | `109` | `-1044.5162` | `-60.0054` | `84` | `-1168.7292` | `0.7706` | `0.6774` | `25` | `+124.2130` |
| `residual_bias_gt_0` | `146` | `-1018.9970` | `-85.5246` | `102` | `-1300.3140` | `0.6986` | `0.8226` | `44` | `+281.3170` |
| `tail_prob_ge_0p30` | `86` | `-999.3158` | `-105.2058` | `62` | `-1218.6288` | `0.7209` | `0.5000` | `24` | `+219.3130` |
| `tail_prob_ge_0p30_or_harmful_ge_0p30` | `120` | `-949.8656` | `-154.6560` | `75` | `-1298.2356` | `0.6250` | `0.6048` | `45` | `+348.3700` |
| `residual_tail_miss_ge_0p10` | `154` | `-945.4782` | `-159.0434` | `97` | `-1264.9272` | `0.6299` | `0.7823` | `57` | `+319.4490` |
| `tail_prob_ge_0p40` | `35` | `-328.7230` | `-775.7986` | `27` | `-400.3800` | `0.7714` | `0.2177` | `8` | `+71.6570` |
| `tail_reliability_not_used` | `16` | `-90.7580` | `-1013.7636` | `13` | `-103.0080` | `0.8125` | `0.1048` | `3` | `+12.2500` |

Worst contexts:

| role | month | side | horizon | regime | session | positive pred | PnL | losses | loss PnL | wins |
|---|---|---|---:|---|---|---:|---:|---:|---:|---:|
| `hybrid2025_0912_external` | `2025-11` | short | `720` | `up_normal_vol` | asia | `5` | `-330.4680` | `5` | `-330.4680` | `0` |
| `refit2025_validation` | `2025-07` | short | `720` | `range_normal_vol` | london | `4` | `-162.0144` | `4` | `-162.0144` | `0` |

Worst cases show the mechanism:

- `hybrid2025_0912_external 2025-11 short 720m`: predicted PnL `+12.1675`, actual as low as `-80.0400`, tail probability `0.4518`, harmful probability `0.5447`, prior mean `-6.9211`, prior tail `0.5760`, residual bias `+12.8538`, residual MAE `24.6017`, residual tail miss `0.4809`.
- `refit2025_validation 2025-07 short 720m`: predicted PnL `+9.1013` to `+22.9117`, actual around `-47` to `-45`, tail probability around `0.33..0.37`, but harmful probability near `0.0048`; harmful head alone misses these.

## Decision

- `entry_ev_positive_pnl_failure_diagnostics.py`: accepted infrastructure.
- Positive predicted PnL is not enough for entry/horizon admission. In 00346 candidate surface, it is negative in aggregate even after dedup.
- `positive_bias_and_tail_miss_ge_0p10`: strongest next diagnostic gate candidate. It catches many failures with relatively small winner damage in pointwise terms, but still removes winners and needs stateful replay.
- `tail_prob_ge_0p30`: also a candidate. It is lower recall than residual-bias/tail-miss, but cleaner than broad harmful probability.
- `harmful_prob_ge_0p30`: weaker as standalone; it misses `refit2025 2025-07 short` because harmful probability is near zero despite large losses.
- Direct hard gate is not adopted yet. These are pointwise candidate-surface diagnostics, not one-position stateful policy evidence.
- Standard policy remains NoTrade.

## Next

1. Add stateful replay sensitivity for `positive_bias_and_tail_miss_ge_0p10` and `tail_prob_ge_0p30` as candidate admission vetoes.
2. Keep `harmful_prob` as a feature, but do not use it alone as the positive-PnL trust gate.
3. Split positive predicted PnL calibration by horizon/context: 720m up-normal-vol asia short, 720m range-normal-vol london short, and 720m down-low-vol asia long should not share one global trust threshold.
4. Verify whether these gates improve actual best additions, not just candidate aggregate.

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_positive_pnl_failure_diagnostics.py tests/test_entry_ev_positive_pnl_failure_diagnostics.py`: OK
- `uv run python -m unittest tests.test_entry_ev_positive_pnl_failure_diagnostics`: OK
- 00347 positive PnL failure diagnostics: OK
