# Augmented Stateful Blocking Examples

日時: 2026-06-29 16:47 JST
更新日時: 2026-06-29 16:50 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻である `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## 目的

`00152` で high-overestimate probability の単独risk化は失敗した。次に戻るべき本線は、selected tradeの点予測ではなく、一玉制約で逃す機会を扱う `stateful_candidate_examples.csv` の拡張である。

今回は複数の `stateful_candidate_examples.csv` をまとめて読み込めるようにし、supportを増やした時に `blocking_cost` / `replacement_regret` 系の分類targetが改善するか確認した。

## 実装

`oof-stateful-value-model` / `oof-stateful-risk-model` の `--examples` をカンマ区切り入力に対応した。

- CSVファイルを複数指定できる。
- `stateful_candidate_examples.csv` を含むディレクトリも指定できる。
- 読み込んだ各行に `example_source` を付与する。
- metricsへ `example_source_rows` を保存する。

これにより、どのpolicy deltaから作ったexamplesがtarget分布を歪めているか後から診断できる。

## Data

使用したexamples:

| source | rows |
|---|---:|
| `trade_overestimate_q90_w2p0_delta_validation` | `529` |
| `trade_overestimate_chronological_fold_q75_w2p0_delta_validation` | `285` |
| `trade_overestimate_high_q75_w1p0_delta_validation` | `279` |
| total | `1093` |

月別:

| month | rows |
|---|---:|
| 2024-11 | `82` |
| 2024-12 | `88` |
| 2025-01 | `70` |
| 2025-02 | `319` |
| 2025-03 | `308` |
| 2025-04 | `226` |

2025-02..2025-04が厚く、2024-11..2025-01はq90 delta由来が中心。したがって、これは「support増加の診断」であり、採用候補の証明ではない。

## OOF Metrics

`expanding`, `min_train_months=3` で2025-02..2025-04をholdout評価した。prediction側は highcost risk5 系のvalidation OOF predictionを使用。

| target | candidate count | prevalence | predicted mean | bias | brier | AUC |
|---|---:|---:|---:|---:|---:|---:|
| `positive_blocking` | `853` | `0.0281` | `0.0314` | `+0.0033` | `0.0274` | `0.4751` |
| `blocking_cost_high` | `853` | `0.0211` | `0.0198` | `-0.0013` | `0.0210` | `0.5439` |
| `replacement_regret_high` | `853` | `0.2485` | `0.2383` | `-0.0102` | `0.1878` | `0.4795` |
| `positive_replacement_regret_high` | `853` | `0.2591` | `0.2543` | `-0.0048` | `0.1948` | `0.4445` |
| `stateful_nonpositive` | `853` | `0.4783` | `0.4792` | `+0.0009` | `0.2492` | `0.5070` |

supportは増えたが、rank能力は大きく改善しない。唯一 `blocking_cost_high` がAUC `0.5439` で少し使えそうに見える。

## Source Target Rates

source別の差が大きい。

| source | positive blocking | blocking cost high | replacement regret high | stateful nonpositive |
|---|---:|---:|---:|---:|
| q90 w2.0 delta | `0.0359` | `0.0208` | `0.2268` | `0.4707` |
| chrono q75 w2.0 delta | `0.0035` | `0.0035` | `0.2596` | `0.4772` |
| high q75 w1.0 delta | `0.0430` | `0.0358` | `0.2581` | `0.4875` |

`blocking_cost_high` はsourceによって `0.0035` から `0.0358` まで動く。これはpolicy context依存が強く、複数sourceを混ぜれば単純に汎化するわけではないことを示す。

## Policy Check

薄くsignalが見えた `blocking_cost_high` だけを、既存stateful risk5へ追加した。

`EV -= 5 * existing_stateful_prob + w * blocking_cost_high_prob` になるようcombined risk列を作成し、2025-02..2025-04の固定policyで評価した。

| label | total PnL | min month PnL | trades | max DD |
|---|---:|---:|---:|---:|
| baseline | `154.6374` | `14.3072` | `281` | `224.7524` |
| aug blockcost w5 | `123.7672` | `2.6652` | `280` | `224.7524` |
| aug blockcost w10 | `92.1764` | `2.7732` | `280` | `227.6004` |

月別:

| label | 2025-02 | 2025-03 | 2025-04 |
|---|---:|---:|---:|
| baseline | `113.1642` | `27.1660` | `14.3072` |
| aug blockcost w5 | `94.1830` | `26.9190` | `2.6652` |
| aug blockcost w10 | `52.1592` | `37.2440` | `2.7732` |

`w10` は2025-03だけ少し改善するが、2025-02と2025-04を削りすぎる。合計、最低月、maxDDのいずれもbaselineを超えない。

## 判断

1. 複数examples入力の実装は採用する。追加supportを使った検証を再現可能にする基盤として有用。
2. supportを254件から1093件へ増やしても、stateful downside分類のrank能力は大きく改善しなかった。
3. `blocking_cost_high` はAUC `0.5439` だが、policy接続ではbaselineを下回る。標準riskには採用しない。
4. sourceごとのtarget率がかなり違うため、追加examplesは「量を増やす」だけでは不十分。policy contextを区別するか、同一設計のwalk-forward examplesを増やす必要がある。
5. 次は、複数source混合ではなく、同一固定policyからwalk-forwardでexamplesを増やし、source driftを抑えた上で `blocking_cost_high` / `stateful_nonpositive` を再評価する。

## Artifacts

- augmented stateful risk model: `data/reports/modeling/20260629_074521_stateful_risk_augmented_examples_expanding_min3_highcost/`
- combined risk predictions and summaries: `data/reports/modeling/20260629_1648_augmented_stateful_blocking_cost_combined_risk/`
- w5 backtests: `data/reports/backtests/20260629_augmented_stateful_blockcost_w5p0_validation/`
- w10 backtests: `data/reports/backtests/20260629_augmented_stateful_blockcost_w10p0_validation/`

## 検証

- `python3 -m unittest tests.test_meta_model`: pass
- `python3 -m py_compile src/trade_data/meta_model.py`: pass
- `python3 -m unittest tests.test_meta_model tests.test_backtest tests.test_docs_reports`: pass, 130 tests
- `git diff --check`: pass

## 次の作業

1. 同一固定policyのwalk-forward trade deltaからexamplesを増やす。
2. source policyを混ぜる場合は、source別target率・source別AUC・month別AUCを必ず併記する。
3. `blocking_cost_high` は即riskではなく、同一policy sourceで再評価するまで保留。
