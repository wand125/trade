# Next-bar research status

更新日時: 2026-08-07 19:40 JST

## 現在の状態

- M1 共通データから M1/M5/M15/M30 の完成足を生成できる。
- 次の連続完成足の up/down ラベルを作り、時間境界をまたぐラベルを purge できる。
- 各時間足の独立モデルを学習し、後続期間で確率校正し、完全未使用期間で評価できる。
- 保存済みモデルから各時間足の最新予測と校正済み信頼度を出力できる。
- 正式ベースライン `experiments/next_bar/baseline_001` を完了した。
- 2022〜2026年途中を未知testとする5foldの `experiments/next_bar/walk_forward_001` を完了した。
- 生のOHLC価格水準がモデル特徴量に入ると停止するガードを実装した。
- 加工特徴を追加した `walk_forward_enhanced_manual_001` を同じ5foldで比較し、全時間足一括採用を棄却した。
- 方向別Platt confidenceとcontext HGB confidenceを比較し、どちらも全時間足共通方式として棄却した。
- 同じ加工入力を使う2層MLPをM15/M30で比較し、HGBより悪化したため棄却した。
- 7foldで確認したabstention条件を `methods/next_bar/config/context_policy_v1.json` に固定した。
- `experiments/next_bar/deployment_candidate_001` を生成し、policy付き最新推論まで通した。
- accuracyとcoverageを同時に扱う採用条件optimizerを実装した。Wilson正答率下限を使い、少数サンプルの見かけ上の高精度を罰する。
- 5foldのout-of-sample予測から `methods/next_bar/config/optimized_policy_v1.json` を生成し、過去foldで選択して次foldで測るnested chronological validationを完了した。
- 予測方向が正しい確率をフェアオッズとして検証するnested odds calibrationを実装し、`methods/next_bar/config/odds_calibration_v1.json` を生成した。
- 追加の階層実績校正は全時間足でBrier/log lossを悪化させたため採用せず、既存Platt model confidenceをオッズ源として選択した。全時間足でnested ECE 0.21%以下、null Brierを改善した。
- 最新出力へconfidence interval、fair decimal odds、odds ratio、support、odds validity、strict eligibilityを追加した。
- 方向オッズを売買へ変換する独立層 `next_bar_ev` を追加した。値幅、tail risk、損失重み付きEV、損益分岐確率、Kelly参考値を方向モデルとは別に学習する。
- M15の次足単独売買、ATR stop、既存Entry EVへの単純方向overlayをchronological OOSで検証した。損失1.2倍は標準条件から廃止。通常損益ではM15 confidence 0.54以上が6/6 fold positive、cost 0.05後も6/6 positiveだがcost ceilingが0.05415と薄いためpaper candidateに留めた。

## ベースライン評価

2025-01-01〜2026-06-01 の test では、校正後 accuracy は M1 50.89%、M5 51.32%、M15 51.86%、M30 51.65%。balanced accuracy は 50.75%〜51.27%であり、現時点の方向エッジは小さい。

確率校正は全時間足で ECE、Brier score、log loss を改善した。一方、confidence 0.55 以上の coverage は M1 0.006%、M5 0.063%、M15 4.95%、M30 6.73%。M1/M5 は実用的な高信頼度帯をまだ作れていない。

## 次の作業

1. optimized policyとodds calibrationを新規データで固定運用し、accuracy/coverage/Brier/ECEを継続監視する。
2. `coverage_power` は0、0.5、1の事前固定候補だけを比較し、目的に合うquality/coverage比を決める。
3. `next_bar_ev` は新しい完全未使用期間で方向edge、cost headroom、EV biasを監視する。
4. M1/M5 entry delayは実装済みだがadmission fail。現条件を変更せず追加期間で確認する。
5. 次の方向モデル候補は、平坦化MLPではなく正規化系列を直接扱うsequence architectureとして別計画にする。
