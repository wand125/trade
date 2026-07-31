# Stateful Context Stress Target

日時: 2026-06-29 11:30 JST
更新日時: 2026-06-29 11:30 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻である `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## 目的

`00135` で確認したvalidation-positive / holdout-negativeのcontext反転を、単なる一覧ではなく、candidate examplesに戻せる監査targetとして出力する。

今回の列はholdoutを見た事後監査であり、そのままlive学習targetにはしない。次にwalk-forwardで過去foldだけから同じpenaltyを作るための設計確認として扱う。

評価方針は現行標準の利益倍率 `1.0`、損失倍率 `1.20` を前提にする。既存examplesの `target` は各artifactに保存された条件の実現値なので、倍率条件はartifact configと合わせて確認する。

## 実装

`trade_data.backtest stateful-examples-drift` が `combined_stateful_examples.csv` へ以下を追加する。

- `context_*`: group drift metricsをexample行へjoinした監査列
- `context_stress_flag`: validation meanが正、holdout meanが負のcontext
- `context_stress_penalty`: `max(validation_target_mean - holdout_target_mean, 0)` をflag行だけに適用
- `target_context_stress_adjusted`: `target - context_stress_penalty`
- `target_context_holdout_mean_floor`: `min(target, context_holdout_target_mean)`
- `context_stressed_examples.csv`: stress flag行だけの抽出

元のcontext列はjoin用に文字列上書きせず、監査CSV上の値を保持する。

## 実行

available context:

```bash
python3 -m trade_data.backtest stateful-examples-drift \
  --validation-examples data/reports/backtests/20260629_014012_guard_fixed_parent_validation_base_delta,data/reports/backtests/20260629_014012_guard_fixed_parent_validation_highcost_delta,data/reports/backtests/20260628_234917_stateful_candidate_examples_validation \
  --holdout-examples data/reports/backtests/20260629_014012_guard_fixed_parent_apply_base_delta,data/reports/backtests/20260629_014012_guard_fixed_parent_apply_highcost_delta,data/reports/backtests/20260628_234210_stateful_candidate_examples_smoke \
  --label stateful_examples_available_context_stress_target \
  --top-n 20
```

session context:

```bash
python3 -m trade_data.backtest stateful-examples-drift \
  --validation-examples data/reports/backtests/20260629_014012_guard_fixed_parent_validation_base_delta,data/reports/backtests/20260629_014012_guard_fixed_parent_validation_highcost_delta,data/reports/backtests/20260628_234917_stateful_candidate_examples_validation \
  --holdout-examples data/reports/backtests/20260629_014012_guard_fixed_parent_apply_base_delta,data/reports/backtests/20260629_014012_guard_fixed_parent_apply_highcost_delta,data/reports/backtests/20260628_234210_stateful_candidate_examples_smoke \
  --group-columns candidate_side,combined_regime,session_regime \
  --label stateful_examples_session_context_stress_target \
  --top-n 20
```

## 結果

共通:

| item | value |
|---|---:|
| total rows | 1544 |
| validation rows | 710 |
| holdout rows | 834 |
| target mean | `+0.6154` |

stress summary:

| grouping | groups | flip groups | stress rows | penalty mean | penalty sum | stress-adjusted mean |
|---|---:|---:|---:|---:|---:|---:|
| `candidate_side + combined_regime` | 15 | 6 | 1083 | `3.6772` | `5677.5214` | `-3.0618` |
| `candidate_side + combined_regime + session_regime` | 52 | 10 | 387 | `2.7589` | `4259.8072` | `-2.1435` |

available contextの主なstress group:

| group | validation mean | holdout mean | penalty |
|---|---:|---:|---:|
| short / range_normal_vol | `+10.9080` | `-2.6160` | `13.5239` |
| long / down_low_vol | `+2.6743` | `-3.0106` | `5.6849` |
| long / up_low_vol | `+1.8044` | `-0.5324` | `2.3368` |
| short / down_normal_vol | `+6.7530` | `-0.2497` | `7.0027` |

session contextの主なstress group:

| group | validation mean | holdout mean | penalty |
|---|---:|---:|---:|
| long / up_low_vol / london | `+3.7959` | `-6.0531` | `9.8489` |
| short / range_normal_vol / rollover | `+17.9933` | `-22.7103` | `40.7035` |
| short / down_normal_vol / london | `+8.0596` | `-0.9559` | `9.0155` |
| short / range_normal_vol / asia | `+5.6918` | `-3.5274` | `9.2192` |

## 判断

available contextはstress対象が広く、training targetにすると保守的になりすぎる可能性が高い。一方、session contextは行数を387行まで絞り、壊れる時間帯やsession依存の文脈を監査するには使いやすい。

ただし、両方ともholdoutを参照しているので、これをそのまま学習に入れるとfuture leakageになる。採用はしない。次は、walk-forward内で「過去foldのvalidation -> next split崩れ」だけからpenaltyを作り、各月のOOF exampleに付ける。

次の実験候補:

- rolling/walk-forward stress profileを作る
- `target_context_stress_adjusted` 相当をOOFだけで生成する
- stateful value modelのtargetとして元target、stress-adjusted target、holdout mean floorを比較する
- policy評価ではstress列を直接gateにせず、candidate採用前監査とcalibration diagnosticsに使う

## Artifacts

- available context stress: `data/reports/backtests/20260629_023150_stateful_examples_available_context_stress_target/`
- session context stress: `data/reports/backtests/20260629_023150_stateful_examples_session_context_stress_target/`

## Verification

- `python3 -m unittest tests.test_backtest.BacktestTests.test_stateful_examples_drift_metrics_compare_validation_and_holdout_context`: OK
- `python3 -m unittest tests.test_backtest tests.test_docs_reports`: OK, 78 tests
- `git diff --check`: OK
