# Stateful Secondary Tie-Break

日時: 2026-06-29 09:22 JST
更新日時: 2026-06-29 09:22 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻である `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## 目的

`00120` の判断どおり、`stateful_positive_cost_value` をentry EVへ直接置換せず、primary raw EVの近接時だけsecondary scoreとして使う。

狙い:

- primary raw EVでentry可否と通常のside marginを維持する。
- `abs(long_raw_ev - short_raw_ev) <= secondary_score_tie_margin` のときだけ、stateful positive-cost scoreでlong/short sideを選び直す。
- hard gateやscalar penaltyでentry集合を削りすぎる問題を避ける。

## 実装

`ModelPolicyConfig` と `model-policy` / `model-sweep` に次を追加した。

- `long_secondary_score_column`
- `short_secondary_score_column`
- `secondary_score_tie_margin`
- sweep用の `secondary_score_tie_margins`

挙動:

- defaultは `secondary_score_tie_margin=-inf` で無効。既存policy互換。
- secondary有効時も、entry thresholdには選ばれたsideのprimary EVを使う。
- `side_gap >= side_margin` はprimary EV gapで判定する。
- secondary scoreはnear-tie時のside選択だけに使い、entry scoreそのものは作り替えない。

追加テスト:

- secondary scoreがnear-tieだけでsideを反転すること。
- secondaryがshortを選んでも、short側primary EVがshort entry thresholdを満たさなければentryしないこと。

## 実行

```bash
PYTHONPATH=src python3 -m trade_data.backtest model-sweep \
  --month <2024-07|2024-09|2024-11|2025-01> \
  --predictions data/reports/modeling/20260629_000824_stateful_positive_cost_value_model/predictions_validation_oof_stateful_value_model.parquet \
  --output-dir data/reports/backtests/stateful_positive_cost_tiebreak_validation \
  --policies timed_ev \
  --entry-thresholds 12 \
  --short-entry-threshold-offsets 6 \
  --side-margins 5 \
  --min-entry-ranks 0.5 \
  --risk-penalties 0 \
  --secondary-score-tie-margins=-inf,5,10,15,20 \
  --long-secondary-score-column pred_candidate_quality_stateful_positive_cost_long_adjusted_pnl \
  --short-secondary-score-column pred_candidate_quality_stateful_positive_cost_short_adjusted_pnl \
  --long-column pred_long_best_adjusted_pnl \
  --short-column pred_short_best_adjusted_pnl \
  --max-predicted-hold-minutes 480 \
  --long-holding-column pred_mlp_long_exit_event_minutes \
  --short-holding-column pred_mlp_short_exit_event_minutes \
  --side-ev-penalty-rules short:combined_regime=down_low_vol:5,short:combined_regime=up_low_vol:10 \
  --loss-multiplier 1.2 \
  --top-n 5
```

artifacts:

- validation: `data/reports/backtests/stateful_positive_cost_tiebreak_validation/`

## Validation Results

固定条件は `timed_ev`, entry `12`, short offset `6`, side margin `5`, rank `0.5`, max hold `480`, loss multiplier `1.2`, short low-vol penalty `down5/up10`。

| secondary tie margin | sum pnl | min month pnl | trades | max DD | forced max |
|---:|---:|---:|---:|---:|---:|
| `-inf` | `622.6486` | `138.0338` | `275` | `85.0166` | `0.0000` |
| `5` | `622.6486` | `138.0338` | `275` | `85.0166` | `0.0000` |
| `10` | `563.7984` | `115.1392` | `278` | `87.6406` | `0.0152` |
| `15` | `582.0794` | `120.2830` | `280` | `87.6406` | `0.0152` |
| `20` | `582.2844` | `120.2830` | `280` | `87.6406` | `0.0152` |

月別では `secondary_score_tie_margin=10/15/20` は2024-07を少し改善する一方、2024-09, 2024-11, 2025-01を落とした。

代表例:

- `20`: 2024-07 `198.1782 -> 212.7450`
- `20`: 2024-09 `138.0338 -> 124.8792`
- `20`: 2024-11 `142.8264 -> 124.3772`
- `20`: 2025-01 `143.6102 -> 120.2830`

`5` はbaseと完全一致した。これは現在のentry side marginが `5` であり、primary gapが5未満の候補はどのみちentry条件を満たさないため、反転余地がほぼないためと考えられる。

## 判断

near-tie secondary score実装は採用するが、`stateful_positive_cost_value` を使った今回のtie-break設定は標準policyに採用しない。

理由:

- validation合計PnL、最低月PnL、max drawdownのいずれもbaselineを上回らない。
- 改善が2024-07に偏り、他のvalidation月へ外挿していない。
- forced exitが `0` から `0.0152` に増えるmarginがあり、exit timing側の副作用も出ている。

したがってapply holdoutは実行しない。validationで棄却された設定をholdoutで探すと、未使用期間への後付け最適化になりやすい。

次にやること:

1. secondary scoreをside反転ではなく、同時刻候補のentry優先順位やrisk budget配分へ使う。
2. stateful examplesを追加月へ増やし、254例の小規模教師から脱する。
3. side選択そのものではなく、`hold or skip` / `replacement regret` / `blocking cost` の二段目判定を作る。
4. near-tieの候補だけに限定したOOF評価を作り、secondary scoreの順位付け能力を局所的に測る。
