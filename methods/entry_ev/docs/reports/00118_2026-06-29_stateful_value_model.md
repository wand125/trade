# Stateful Value Model

日時: 2026-06-29 08:59 JST
更新日時: 2026-06-29 08:59 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻である `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## 目的

`00117` の次手として、`stateful_candidate_examples.csv` から `stateful_entry_value` を月抜きOOFで学習する。

狙いは raw EV の過大評価を抑えること。ただし、この段階では標準policyへの採用ではなく、校正力、順位付け能力、direct replacementの危険性を確認する。

## 実装

`trade_data.meta_model oof-stateful-value-model` を追加した。

入力:

- `stateful_candidate_examples.csv`
- optional validation prediction parquet
- optional apply prediction parquet

出力:

- `validation_oof_stateful_value_examples.csv`
- `validation_fit_stateful_value_examples.csv`
- `predictions_validation_oof_stateful_value_model.parquet`
- `predictions_apply_stateful_value_model.parquet`
- `stateful_value_model.joblib`
- `metrics.json`

prediction parquetには `pred_candidate_quality_stateful_entry_<side>_*` 列を追加する。

## 実行

```bash
PYTHONPATH=src python3 -m trade_data.meta_model oof-stateful-value-model \
  --examples data/reports/backtests/20260628_234917_stateful_candidate_examples_validation/stateful_candidate_examples.csv \
  --validation-predictions data/reports/modeling/20260628_230654_20260629_side_outcome_stack_fixed_component/predictions_validation_oof_candidate_quality_model.parquet \
  --apply-predictions data/reports/modeling/20260628_230654_20260629_side_outcome_stack_fixed_component/predictions_apply_candidate_quality_model.parquet \
  --validation-months 2024-07,2024-09,2024-11,2025-01 \
  --apply-months 2024-12,2025-02,2025-03 \
  --output-dir data/reports/modeling \
  --label stateful_entry_value_model \
  --target-column stateful_entry_value \
  --prediction-prefix stateful_entry \
  --source-mode columns \
  --long-column pred_long_best_adjusted_pnl \
  --short-column pred_short_best_adjusted_pnl
```

artifacts:

- model: `data/reports/modeling/20260628_235629_stateful_entry_value_model/`
- report: `data/reports/modeling/20260628_235645_stateful_entry_value_model_report/`
- direct validation sweep: `data/reports/backtests/stateful_entry_value_direct_sweep_validation/`
- direct apply threshold 3.5: `data/reports/backtests/stateful_entry_value_direct_apply_t3p5/`

## OOF Metrics

| metric | raw EV | stateful mean | stateful lower |
|---|---:|---:|---:|
| predicted mean | `16.4274` | `2.4875` | `-3.9444` |
| bias | `14.0151` | `0.0753` | `-6.3567` |
| overestimate mean | `15.0311` | `4.2816` | `1.8360` |
| MAE | - | `8.4879` | - |
| R2 | - | `-0.0141` | - |
| lower coverage | - | - | `0.7520` |

raw EVの平均過大評価は大きく縮んだ。一方でR2は負で、候補間の順位付け能力はまだ弱い。

## Direct Replacement Smoke

`pred_candidate_quality_stateful_entry_*_adjusted_pnl` をそのままentry EV列として使い、threshold `2.0/2.5/3.0/3.5` をvalidation 4ヶ月で試した。

| threshold | validation sum | validation min | trades | max DD | note |
|---:|---:|---:|---:|---:|---|
| `2.0` | `17.7072` | `-100.4676` | `3193` | `163.4510` | 取引過多 |
| `2.5` | `70.7906` | `-91.1482` | `2101` | `146.1156` | 取引過多 |
| `3.0` | `169.9048` | `-91.6760` | `987` | `187.4288` | 月別不安定 |
| `3.5` | `148.5810` | `-0.4126` | `481` | `89.4030` | 2024-09は0 trade |

threshold `3.5` はvalidation minだけ見ると壊れにくいが、2024-09が0 tradeでNoTrade寄り。apply 3ヶ月では同じ `3.5` が全月0 tradeになった。

apply predictionのstateful mean分布:

| month | long mean | long max | short mean | short max |
|---|---:|---:|---:|---:|
| 2024-12 | `1.7413` | `3.1074` | `1.6636` | `3.1888` |
| 2025-02 | `1.5425` | `2.9547` | `1.5262` | `3.0841` |
| 2025-03 | `1.6124` | `3.0975` | `1.5925` | `3.0975` |

## 判断

`oof-stateful-value-model` は実装として採用する。raw EV過大評価を下げる校正信号として有用。

ただし、現時点の `stateful_entry_value` mean列をentry EVへ直接置換する方針は採用しない。理由:

- OOF mean biasは良いがR2が負で、順位付け能力が弱い。
- mean predictionが全て正寄りで、見送り判定には鈍い。
- thresholdが月に強く依存する。
- validationで良い `3.5` はholdout applyで全月NoTrade化する。

次は direct replacement ではなく、raw EVとの混合またはcandidate ranking/tie-breakに進む。

候補:

1. `blended_ev = raw_ev - alpha * max(raw_ev - stateful_mean, 0)` を `alpha=0.1/0.25/0.5` で検証する。
2. `stateful_lower` をhard gateにせず、near-tie時のtie-breakまたはrisk budgetにだけ使う。
3. targetを `stateful_positive_cost_value` に替え、勝ち機会の取り逃しを強めに見る。
4. examplesが254件しかないため、追加月のstateful examplesを増やしてから深いモデルを検討する。
