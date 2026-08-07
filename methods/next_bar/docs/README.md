# Next-bar direction research

M1、M5、M15、M30 の「次に確定する1本」の方向と、その予測の信頼度を研究する独立手法。
`entry_ev` の売買期待値・決済最適化とはモデルも評価も分離し、共通の UTC M1 OHLC データだけを再利用する。

## 目的と境界

- 各時間足を別々の二値分類問題として扱う。
- 判定時点までに確定済みの足だけを特徴量に使う。
- 生の `open/high/low/close` 価格水準はモデルへ渡さない。リターン、比率、rolling統計、指標へ変換し、価格水準の暗記を防ぐ。
- 正解は、直後の連続した完成足について `close > open` なら up、それ以外なら down とする。
- `abs(close - open) <= flat_tolerance` は曖昧足として学習・評価から除外する。既定値は 0。
- 予測信頼度は、学習期間より後の calibration 期間で Platt calibration した「予測方向が正しい確率」とする。
- この段階では売買損益を最適化しない。方向予測が検証できた後に、別の policy 層で複数時間足の確率、コスト、見送り、リスクを売買へ変換する。

## 時系列分割

```text
train           calibration             test
モデル学習       確率の校正                完全未使用の最終評価
```

境界をまたいで次足ラベルが未来側へ入る行は除外する。モデルの early stopping は内部ランダム分割を避けるため無効にしている。最終判断は test の一回の数字ではなく、次段階で expanding walk-forward を複数窓実行して行う。

## 実行

リポジトリルートから実行する。

```bash
uv run python methods/next_bar/scripts/run.py train-evaluate \
  --input data/processed/histdata/xauusd/xauusd_m1.parquet \
  --output-dir experiments/next_bar/baseline_01 \
  --timeframes 1,5,15,30 \
  --train-end 2023-01-01 \
  --calibration-end 2024-01-01 \
  --test-end 2026-01-01
```

日付を省略した場合は、全期間を時刻順に 60% / 20% / 20% に分ける。研究結果を比較するときは明示日付を使う。

学習成果物:

- `manifest.json`: モデル一覧と特徴量
- `metrics.json`: 時間足別の精度・校正・信頼度別カバレッジ
- `m*_model.joblib`: モデルと確率校正器
- `m*_test_predictions.parquet`: 完全未使用期間の行単位予測

最新の完成足から推論する:

```bash
uv run python methods/next_bar/scripts/run.py predict-latest \
  --input data/processed/histdata/xauusd/xauusd_m1.parquet \
  --model-dir experiments/next_bar/baseline_01 \
  --context-policy methods/next_bar/config/context_policy_v1.json \
  --output runtime/latest_next_bar_predictions.json
```

context policyは方向予測を変更せず、検証済みcontext以外を `prediction_eligible=false` として見送る。これは売買policyではなく、次足予測のaccuracy/coverageを管理するabstention層である。

walk-forwardのout-of-sample予測から採用条件を最適化する:

```bash
uv run python methods/next_bar/scripts/run.py optimize-policy \
  --predictions-dir experiments/next_bar/walk_forward_001 \
  --output methods/next_bar/config/optimized_policy_v1.json \
  --min-rows 500 \
  --min-coverage 0.01 \
  --coverage-power 0.5
```

最適化する評価関数は次の通り。

```text
selection_score = coverage^coverage_power
                  * (Wilson accuracy lower bound - break-even accuracy)
```

既定値はcoverage power 0.5、break-even 0.50、Wilson z 1.96。`coverage-power=1` は全予測機会あたりの正答超過を重視し、0に近づけるほど狭い高品質条件を重視する。候補はconfidence閾値、予測方向、volatility regime、UTC hour/6時間帯から選ぶ。最低件数と最低coverageを満たさない候補は除外する。

条件選択のリークを避けるため、レポートには「過去のout-of-sample foldで条件選択し、次foldだけで評価」するnested chronological validationを含める。全foldから作る最終ruleのreference値より、nested summaryを実運用品質の判断に優先する。

複数の expanding walk-forward 窓を実行する:

```bash
uv run python methods/next_bar/scripts/run.py walk-forward \
  --input data/processed/histdata/xauusd/xauusd_m1.parquet \
  --output-dir experiments/next_bar/walk_forward_001 \
  --fold wf2022,2021-01-01,2022-01-01,2023-01-01 \
  --fold wf2023,2022-01-01,2023-01-01,2024-01-01 \
  --fold wf2024,2023-01-01,2024-01-01,2025-01-01 \
  --fold wf2025,2024-01-01,2025-01-01,2026-01-01
```

各foldは、それ以前をtrain、次の期間を確率校正、その次をtestにする。出力にはfold別・全fold合算の精度と、月、UTC hour、volatility regime、実際の方向別診断を含む。

加工特徴candidateを比較する場合は、同じfoldへ `--feature-set enhanced_manual` を追加する。追加されるのは方向系列、実体/ATR、rolling up比率、trend/volatility比、volatility/ATR比、return autocorrelation/skew、EMA差/ATRであり、生価格水準は含まれない。

同じ加工特徴を2層MLPで比較する場合は `--model-type mlp --max-iter 50` を使う。MLPにもOHLC価格水準は渡さず、HGBと同じ加工済みfeature matrixを標準化して入力する。

## 主評価指標

- accuracy と balanced accuracy
- log loss と Brier score
- expected calibration error (ECE)
- 信頼度閾値ごとの coverage と accuracy
- 採用条件のWilson accuracy lower bound、selection score、quality score
- 学習期間の多数派予測、および前足方向の継続予測との比較

高信頼度だけを選ぶと見かけの正答率は上がりやすいため、accuracy と coverage を必ず対で扱う。
`quality_score` はWilson下限の50%超過分を0〜100へ正規化した値で、0は統計下限が偶然水準以下、100は下限100%を表す。売買収益性のqualityではない。

## 予測オッズ

walk-forwardのout-of-sample予測だけを使って、予測方向が正しい確率を検証・校正する:

```bash
uv run python methods/next_bar/scripts/run.py build-odds-calibration \
  --predictions-dir experiments/next_bar/walk_forward_001 \
  --output methods/next_bar/config/odds_calibration_v1.json \
  --bins 10 \
  --min-support 500 \
  --prior-strength 500
```

最新推論では `--odds-calibration methods/next_bar/config/odds_calibration_v1.json` を追加する。出力の意味は次の通り。

- `model_confidence`: 方向モデルをPlatt校正した予測方向の確率。
- `confidence`: nested検証で選ばれた最終オッズ確率。今回は全時間足でmodel confidenceが選ばれた。
- `fair_decimal_odds`: `1 / confidence`。
- `odds_ratio`: `confidence / (1 - confidence)`。
- `confidence_lower/upper`: 同方向・同volatility・同confidence binの縮約実績区間。
- `odds_valid`: nested全体の校正が有効で、現在値が局所実績区間内にある。
- `odds_edge_confirmed`: 局所実績区間の下限が50%を超える。
- `strict_prediction_eligible`: 採用policy、odds validity、odds edgeの3条件をすべて満たす。

`odds_valid` はオッズ推定が整合していることを表し、50%超のedgeを保証しない。強い採用判定には `strict_prediction_eligible` を使う。

## 記録

- `status.md`: 現在の到達点と次の作業
- `reports/`: 実験ごとの番号付きレポート。`00001_YYYY-MM-DD_slug.md` の形式で保存する。
