# 00008 Prediction odds calibration

日時: 2026-08-07 19:20 JST

## 目的

各UP/DOWN予測と一緒に「その予測方向が正しい確率」を出し、フェアオッズへ変換できるか検証する。

## 手順

- 元のconfidenceは方向確率を後続calibration期間でPlatt校正済み。
- 追加候補としてconfidence 10分位、予測方向、volatility regimeの階層実績テーブルを構築した。
- cellは最低500件。少数cellはside/bin、bin、全体へfallbackする。
- cell accuracyは全体accuracyをprior strength 500として縮約する。
- 過去out-of-sample foldだけで校正し、次foldでBrier、log loss、ECEを評価した。
- 追加校正が3指標すべて改善した場合だけ採用し、それ以外は元のmodel confidenceを使う。

## Nested結果

| TF | rows | actual accuracy | mean confidence | Brier | null Brier | log loss | ECE |
|---|---:|---:|---:|---:|---:|---:|---:|
| M1 | 1,144,773 | 50.618% | 50.718% | 0.249916 | 0.249962 | 0.692979 | 0.100% |
| M5 | 229,657 | 51.139% | 51.346% | 0.249743 | 0.249870 | 0.692633 | 0.207% |
| M15 | 75,522 | 51.480% | 51.692% | 0.249568 | 0.249781 | 0.692281 | 0.212% |
| M30 | 36,919 | 51.543% | 51.571% | 0.249577 | 0.249762 | 0.692299 | 0.041% |

全時間足でECEは0.21%以下、Brierは定数accuracyを使うnull Brierを改善した。予測confidenceと実測accuracyの差も0.03〜0.21 percentage pointである。

## 校正方式の選択

追加の階層実績オッズは、全時間足で元のmodel confidenceよりBrierとlog lossが悪化した。そのため全時間足で `selected_source=model_confidence` とした。過剰な再校正を避け、元のPlatt probabilityを `confidence=P(predicted direction is correct)` として使う。

ただし全体校正が良くても局所条件が同様とは限らない。推論時には同方向・同volatility・同confidence binの実績区間、support count、model confidenceとの整合性を返す。

## 出力

```json
{
  "predicted_direction": "up",
  "probability_up": 0.5548,
  "model_confidence": 0.5548,
  "confidence": 0.5548,
  "confidence_lower": 0.5210,
  "confidence_upper": 0.5615,
  "fair_decimal_odds": 1.8025,
  "odds_ratio": 1.2462,
  "odds_support": 1815,
  "odds_valid": true,
  "odds_edge_confirmed": true
}
```

`odds_valid=true` は確率推定と履歴が整合すること、`odds_edge_confirmed=true` は局所実績区間の下限も50%を超えることを表す。売買損益のオッズではなく、次足方向の的中オッズである。

## 判断

- 現モデルは強い確率を頻繁には出さないが、出した確率の全体校正は良い。
- 正答率だけでなくproper scoring ruleでも確率品質を確認できた。
- `strict_prediction_eligible` を、optimized adoption ruleかつodds validかつ局所下限50%超として出力する。
- 元データは2026-06-01で停止しているため、最新JSONはruntime wiring確認用である。
