# Stateful Near-Tie Local Diagnostics

日時: 2026-06-29 09:30 JST
更新日時: 2026-06-29 09:30 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻である `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## 目的

`00121` では `stateful_positive_cost_value` をnear-tieのside反転に使うとvalidation PnLが悪化した。

今回は売買シミュレーションを増やす前に、候補単位で次を診断する。

- primary raw EVが近い候補だけに絞ったとき、secondary scoreがtargetを順位付けできているか。
- secondary scoreはbias補正だけでなく、entry優先順位やrisk budget配分に使えるか。
- near-tieでの悪化が、実装/閾値の問題か、score自体のrank能力不足かを切り分ける。

この診断はpolicy再現ではなく、`stateful_candidate_examples.csv` 上の局所順位付け診断として扱う。

## 実装

`trade_data.meta_model stateful-near-tie-report` を追加した。

入力:

- `stateful_candidate_examples.csv`
- side別secondary score列を持つprediction parquet

出力:

- `scored_examples.csv`
- `overall_metrics.csv`
- `month_metrics.csv`
- `bucket_metrics.csv`
- `summary.json`

主な指標:

- `primary_target_spearman`
- `secondary_target_spearman`
- `primary_bias` / `secondary_bias`
- `primary_overestimate_mean` / `secondary_overestimate_mean`
- `secondary_top_0p25_target_lift`
- `secondary_top_bottom_0p25_target_spread`

## 実行

```bash
PYTHONPATH=src python3 -m trade_data.meta_model stateful-near-tie-report \
  --examples data/reports/backtests/20260628_234917_stateful_candidate_examples_validation/stateful_candidate_examples.csv \
  --predictions data/reports/modeling/20260629_000824_stateful_positive_cost_value_model/predictions_validation_oof_stateful_value_model.parquet \
  --output-dir data/reports/modeling \
  --label stateful_positive_cost_near_tie_entry12_report \
  --target-column stateful_positive_cost_value \
  --tie-margins 5,10,15,20 \
  --min-primary-score 12 \
  --top-fractions 0.25,0.5 \
  --bucket-count 5 \
  --min-bucket-support 5
```

artifacts:

- all candidates: `data/reports/modeling/20260629_003006_stateful_positive_cost_near_tie_report/`
- entry12: `data/reports/modeling/20260629_003021_stateful_positive_cost_near_tie_entry12_report/`

`min_primary_score=12` でもusable examplesは254件のままで、既存examplesは全てentry threshold相当を満たしていた。

## Overall Results

entry12診断:

| tie margin | support | target mean | primary bias | secondary bias | primary overestimate | secondary overestimate | primary Spearman | secondary Spearman | secondary top25 lift | secondary top-bottom25 spread | primary top25 lift |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `5` | `172` | `1.5625` | `12.8179` | `0.0193` | `13.5815` | `4.2658` | `0.0562` | `-0.1349` | `-1.5925` | `-2.7632` | `0.6748` |
| `10` | `243` | `1.6562` | `14.2953` | `0.0709` | `15.1095` | `4.1775` | `0.0143` | `-0.1123` | `0.1624` | `-1.3873` | `1.2152` |
| `15` | `253` | `1.7042` | `14.6687` | `0.0375` | `15.5499` | `4.2583` | `0.0017` | `-0.1275` | `0.6484` | `-0.9951` | `0.0875` |
| `20` | `254` | `1.6588` | `14.7685` | `0.0853` | `15.6463` | `4.2896` | `-0.0071` | `-0.1327` | `0.4830` | `-1.2899` | `0.2128` |

secondary scoreはbiasを大きく下げている。一方でrank指標は弱く、Spearmanは全marginで負。

特に重要なのは `secondary_top_bottom_0p25_target_spread` が全marginで負であること。secondary score上位25%のtarget平均が下位25%より低く、候補順位付けとしては逆に働きやすい。

## Bucket Check

margin `20` のsecondary score 5分位:

| bucket | support | target mean | target<=0 rate | secondary min | secondary max |
|---|---:|---:|---:|---:|---:|
| `q01` | `51` | `2.6477` | `0.4314` | `-0.7786` | `1.3471` |
| `q02` | `51` | `2.3047` | `0.2941` | `1.3471` | `1.4357` |
| `q03` | `50` | `1.7331` | `0.4000` | `1.4391` | `1.8282` |
| `q04` | `51` | `1.7345` | `0.4510` | `1.8678` | `2.3747` |
| `q05` | `51` | `-0.1244` | `0.5882` | `2.3747` | `3.8343` |

最高score bucket `q05` が最悪で、target meanはマイナス。これは `stateful_positive_cost_value` meanをentry優先順位やrisk budgetへ直接使うのも危険という証拠。

## Month Breakdown

secondary Spearmanは各月でも概ね負。

- margin `20`, 2024-07: `-0.2377`
- margin `20`, 2024-09: `-0.0867`
- margin `20`, 2024-11: `-0.1113`
- margin `20`, 2025-01: `-0.0519`

2024-11のtop25 liftだけは一部大きく見えるが、全体のbucket単調性と月横断のSpearmanが弱いため、採用根拠にはしない。

## 判断

`stateful_positive_cost_value` は校正値として有用だが、ranking scoreとしては使わない。

理由:

- raw EVの過大評価は下げるが、targetとの順位相関は負。
- top25 liftはmarginにより不安定で、top-bottom spreadは全marginで負。
- score上位bucketがtarget負になっており、entry優先順位に使うと悪い候補を前に出す可能性が高い。
- `00121` のvalidation PnL悪化は、tie-break実装の問題というより、secondary scoreのrank能力不足と整合している。

次にやること:

1. `stateful_positive_cost_value` meanを順位付けに使う案は止める。
2. 追加examplesを作り、`blocking_cost` / `replacement_regret` を直接分類・分位で扱う。
3. targetを「値の平均」ではなく、`skip_if_blocks_positive_trade` や `replacement_regret_high` のような二値/下方リスクに切り替える。
4. その前に追加月examplesを作り、supportを254件から増やす。
