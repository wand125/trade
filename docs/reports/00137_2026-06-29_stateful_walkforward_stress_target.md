# Stateful Walk-Forward Stress Target

日時: 2026-06-29 11:42 JST
更新日時: 2026-06-29 11:42 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻である `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## 目的

`00136` の `target_context_stress_adjusted` はholdoutを見た事後監査列であり、そのまま学習に入れるとfuture leakageになる。

今回は、各対象月より前の月だけを使ってstress profileを作り、学習target候補にできるwalk-forward版のstress targetを生成する。

## 実装

`trade_data.backtest stateful-examples-walkforward-stress` を追加した。

各 `target_month` について:

- 対象月より前の月だけを使用する。
- 直前 `--holdout-month-count` ヶ月をpseudo holdoutにする。
- それ以前の月をpseudo validationにする。
- pseudo validation meanが正、pseudo holdout meanが負に反転したcontextにpenaltyを付ける。
- support不足のcontextはpenaltyなしにする。

出力:

- `walkforward_stateful_examples.csv`
- `walkforward_context_stressed_examples.csv`
- `walkforward_profile_drift.csv`
- `walkforward_month_summary.csv`
- `summary.json`

主な列:

- `walkforward_context_stress_flag`
- `walkforward_context_stress_penalty`
- `target_walkforward_context_stress_adjusted`
- `target_walkforward_context_holdout_mean_floor`
- `walkforward_profile_validation_months`
- `walkforward_profile_holdout_months`

## 実行

available context:

```bash
python3 -m trade_data.backtest stateful-examples-walkforward-stress \
  --examples data/reports/backtests/20260629_014012_guard_fixed_parent_validation_base_delta,data/reports/backtests/20260629_014012_guard_fixed_parent_validation_highcost_delta,data/reports/backtests/20260628_234917_stateful_candidate_examples_validation,data/reports/backtests/20260629_014012_guard_fixed_parent_apply_base_delta,data/reports/backtests/20260629_014012_guard_fixed_parent_apply_highcost_delta,data/reports/backtests/20260628_234210_stateful_candidate_examples_smoke \
  --group-columns candidate_side,combined_regime \
  --min-validation-support 20 \
  --min-holdout-support 10 \
  --label stateful_examples_available_context_walkforward_stress \
  --top-n 20
```

session context:

```bash
python3 -m trade_data.backtest stateful-examples-walkforward-stress \
  --examples data/reports/backtests/20260629_014012_guard_fixed_parent_validation_base_delta,data/reports/backtests/20260629_014012_guard_fixed_parent_validation_highcost_delta,data/reports/backtests/20260628_234917_stateful_candidate_examples_validation,data/reports/backtests/20260629_014012_guard_fixed_parent_apply_base_delta,data/reports/backtests/20260629_014012_guard_fixed_parent_apply_highcost_delta,data/reports/backtests/20260628_234210_stateful_candidate_examples_smoke \
  --group-columns candidate_side,combined_regime,session_regime \
  --min-validation-support 10 \
  --min-holdout-support 5 \
  --label stateful_examples_session_context_walkforward_stress \
  --top-n 20
```

## 結果

共通:

| item | value |
|---|---:|
| rows | 1544 |
| months | 8 |
| profiled months | 6 |
| target mean | `+0.6154` |

summary:

| grouping | support | stress rows | penalty mean | penalty sum | stress-adjusted mean |
|---|---:|---:|---:|---:|---:|
| `candidate_side + combined_regime` | `20/10` | 397 | `1.8977` | `2930.0926` | `-1.2823` |
| `candidate_side + combined_regime + session_regime` | `10/5` | 208 | `1.3989` | `2159.8375` | `-0.7835` |

available context month summary:

| month | profile holdout | stress rows | target mean | stress-adjusted mean |
|---|---|---:|---:|---:|
| 2024-07 | none | 0 | `+1.8297` | `+1.8297` |
| 2024-09 | none | 0 | `+2.2224` | `+2.2224` |
| 2024-11 | 2024-09 | 0 | `+2.7789` | `+2.7789` |
| 2024-12 | 2024-11 | 44 | `+0.7767` | `+0.4235` |
| 2025-01 | 2024-12 | 41 | `+1.7981` | `+0.4903` |
| 2025-02 | 2025-01 | 48 | `-1.9543` | `-3.3509` |
| 2025-03 | 2025-02 | 212 | `-0.3812` | `-6.4580` |
| 2025-04 | 2025-03 | 52 | `-2.3350` | `-5.5266` |

session context month summary:

| month | profile holdout | stress rows | target mean | stress-adjusted mean |
|---|---|---:|---:|---:|
| 2024-11 | 2024-09 | 21 | `+2.7789` | `+2.0452` |
| 2024-12 | 2024-11 | 34 | `+0.7767` | `-0.9294` |
| 2025-01 | 2024-12 | 22 | `+1.7981` | `+1.0284` |
| 2025-02 | 2025-01 | 20 | `-1.9543` | `-3.2264` |
| 2025-03 | 2025-02 | 89 | `-0.3812` | `-3.6568` |
| 2025-04 | 2025-03 | 22 | `-2.3350` | `-4.1469` |

主なstress context:

| target month | grouping | validation mean | pseudo-holdout mean | penalty |
|---|---|---:|---:|---:|
| 2025-03 | short / up_normal_vol | `+0.6868` | `-11.1049` | `11.7917` |
| 2025-03 | long / up_low_vol | `+1.6273` | `-6.9910` | `8.6183` |
| 2025-03 | long / up_low_vol / london | `+3.8459` | `-15.2251` | `19.0710` |
| 2025-03 | short / down_normal_vol / london | `+9.0370` | `-4.6826` | `13.7196` |
| 2025-04 | short / range_normal_vol | `+5.3006` | `-3.9706` | `9.2712` |
| 2025-04 | long / down_low_vol / asia | `+3.5207` | `-9.3208` | `12.8415` |

## 判断

未来月を見ない制約でもstress signalは残った。特に2025-03/04の悪化局面に対して、過去月だけで作ったprofileが強くpenaltyを出している。

available contextは広く拾うため、targetをかなり保守的にする。session contextは行数が半分程度で、時間帯依存の壊れ方をより局所的に表す。次の学習では両方を別targetとして比較し、policyに直接gateとして使わない。

次の作業:

- `target`, `target_walkforward_context_stress_adjusted`, `target_walkforward_context_holdout_mean_floor` をstateful value model targetとして比較する。
- OOF metricsだけでなく、実行policyのdeltaで良い取引を削りすぎていないか確認する。
- 月数がまだ少ないため、追加examplesを増やしてprofileの安定性を見る。

## Artifacts

- available context walk-forward stress: `data/reports/backtests/20260629_024156_stateful_examples_available_context_walkforward_stress/`
- session context walk-forward stress: `data/reports/backtests/20260629_024156_stateful_examples_session_context_walkforward_stress/`

## Verification

- `python3 -m unittest tests.test_backtest.BacktestTests.test_stateful_examples_walkforward_stress_uses_only_prior_months tests.test_backtest.BacktestTests.test_stateful_examples_drift_metrics_compare_validation_and_holdout_context`: OK
- `python3 -m unittest tests.test_backtest tests.test_docs_reports`: OK, 79 tests
- `git diff --check`: OK
