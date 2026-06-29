# Stateful Examples Drift

日時: 2026-06-29 11:23 JST
更新日時: 2026-06-29 11:23 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻である `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## 目的

`00134` ではavailable contextが一部反転することを確認したが、既存validation OOFだけでは悪い文脈として学べていなかった。

今回は複数の `stateful_candidate_examples.csv` をvalidation/holdout splitとして直接まとめ、context別にtarget分布がどう崩れるかを確認する。これはモデル採用前のstress-aware target設計と追加walk-forward監査に使う。

## 実装

`trade_data.backtest stateful-examples-drift` を追加した。

入力:

- `--validation-examples`
- `--holdout-examples`
- `--group-columns`
- `--target-column`
- `--raw-prediction-column`

出力:

- `combined_stateful_examples.csv`
- `split_group_metrics.csv`
- `month_group_metrics.csv`
- `group_drift.csv`
- `summary.json`

主な指標:

- support / month count
- target sum / mean / min / q10
- downside rate / large downside rate
- raw EV bias / raw overestimate
- validation-positive / holdout-negative flag

## 実行

available context:

```bash
python3 -m trade_data.backtest stateful-examples-drift \
  --validation-examples data/reports/backtests/20260629_014012_guard_fixed_parent_validation_base_delta,data/reports/backtests/20260629_014012_guard_fixed_parent_validation_highcost_delta,data/reports/backtests/20260628_234917_stateful_candidate_examples_validation \
  --holdout-examples data/reports/backtests/20260629_014012_guard_fixed_parent_apply_base_delta,data/reports/backtests/20260629_014012_guard_fixed_parent_apply_highcost_delta,data/reports/backtests/20260628_234210_stateful_candidate_examples_smoke \
  --label stateful_examples_available_context_drift \
  --top-n 20
```

session context:

```bash
python3 -m trade_data.backtest stateful-examples-drift \
  --validation-examples data/reports/backtests/20260629_014012_guard_fixed_parent_validation_base_delta,data/reports/backtests/20260629_014012_guard_fixed_parent_validation_highcost_delta,data/reports/backtests/20260628_234917_stateful_candidate_examples_validation \
  --holdout-examples data/reports/backtests/20260629_014012_guard_fixed_parent_apply_base_delta,data/reports/backtests/20260629_014012_guard_fixed_parent_apply_highcost_delta,data/reports/backtests/20260628_234210_stateful_candidate_examples_smoke \
  --group-columns candidate_side,combined_regime,session_regime \
  --label stateful_examples_session_context_drift \
  --top-n 20
```

## 結果

共通summary:

| item | value |
|---|---:|
| total rows | 1544 |
| validation rows | 710 |
| holdout rows | 834 |

available context:

| group | validation sum | holdout sum | holdout - validation | validation mean | holdout mean | holdout downside - validation |
|---|---:|---:|---:|---:|---:|---:|
| short / range_normal_vol | `+501.7660` | `-298.2216` | `-799.9876` | `+10.9080` | `-2.6160` | `+0.1918` |
| long / down_low_vol | `+358.3530` | `-234.8292` | `-593.1822` | `+2.6743` | `-3.0106` | `+0.1770` |
| long / up_low_vol | `+368.1008` | `-107.0144` | `-475.1152` | `+1.8044` | `-0.5324` | `+0.0461` |
| short / down_normal_vol | `+303.8836` | `-19.4788` | `-323.3624` | `+6.7530` | `-0.2497` | `+0.2171` |
| short / up_normal_vol | `+45.0356` | `-143.6358` | `-188.6714` | `+1.0723` | `-1.0882` | `+0.0465` |
| long / up_normal_vol | `+63.3320` | `-9.9444` | `-73.2764` | `+10.5553` | `-3.3148` | `+1.0000` |

session context:

| group | validation sum | holdout sum | holdout - validation | validation mean | holdout mean | holdout downside - validation |
|---|---:|---:|---:|---:|---:|---:|
| long / up_low_vol / london | `+254.3226` | `-284.4936` | `-538.8162` | `+3.7959` | `-6.0531` | `+0.2480` |
| short / range_normal_vol / rollover | `+125.9528` | `-227.1028` | `-353.0556` | `+17.9933` | `-22.7103` | `+0.0286` |
| short / down_normal_vol / london | `+217.6102` | `-43.9704` | `-261.5806` | `+8.0596` | `-0.9559` | `+0.2496` |
| short / range_normal_vol / asia | `+91.0686` | `-126.9878` | `-218.0564` | `+5.6918` | `-3.5274` | `+0.2083` |
| long / down_low_vol / ny_overlap | `+39.1028` | `-175.0746` | `-214.1774` | `+4.3448` | `-9.7264` | `+0.3889` |
| short / up_normal_vol / asia | `+20.8284` | `-189.3692` | `-210.1976` | `+1.3886` | `-5.4105` | `-0.0476` |

## 判断

追加examplesをまとめると、validation内で良く見えるcontextがholdout/stressで反転する構造がより明確になった。特に `short/range_normal_vol`, `long/down_low_vol`, `long/up_low_vol`, `short/down_normal_vol` は、単一preflightだけでなくexamples集計でも崩れている。

ただし、これはまだ「悪いcontextを見つけた」ではなく「validation単独では信頼できないcontext」を見つけた段階。これをhard blockにすると、validationで実際に寄与している取引も削る。

扱い:

- hard ruleにはしない。
- `stateful-examples-drift` をcandidate採用前の監査に使う。
- 次の学習では、単月target meanではなく、contextのholdout/stress崩れを反映するtargetやsample weightingを検討する。
- examplesをさらに追加し、walk-forward単位で `validation positive -> next split negative` が再現するかを見る。

## Artifacts

- available context drift: `data/reports/backtests/20260629_022317_stateful_examples_available_context_drift/`
- session context drift: `data/reports/backtests/20260629_022328_stateful_examples_session_context_drift/`

## Verification

- targeted stateful examples drift test: OK
- `python3 -m unittest tests.test_backtest tests.test_docs_reports`: OK, 78 tests
