# 00071 Full Path Temporal Uncertainty

日時: 2026-08-10 20:14 JST

## 目的

特徴や異種学習器をさらに増やす代わりに、同じIntrabar Full Path HGBをexpanding履歴と直近3年履歴で学習し、時系列学習範囲への感応度をepistemic uncertaintyとしてconfidenceへ反映できるか検証した。方向はFull Path expandingのまま維持する。

## 固定仕様

既存rolling-window研究で事前固定済みの1095日を変更せず、Full Path 76特徴、HGB/Platt、7fold境界も共通にした。各行でexpandingとrecentモデルの確率をFull Path方向へ符号合わせし、固定等重みのmean edgeからpopulation standard deviationを1倍引いた。

2モデルの場合、両者がFull Path方向へ正edgeなら、これはほぼ小さい方のedgeを採用する保守的minimumになる。recentが反対方向ならconfidenceを0.5直上へ落とす。future fold、正解ラベル、結果後に調整したpenaltyは使わない。既存 `next_bar_disagreement` の整列・方向維持実装とテスト済み式を再利用した。損失倍率は標準1.0のみである。

## Recent Full Path単体

固定3年Full Pathの全期間accuracyは51.2905%、Brier 0.2496695、log loss 0.6924866だった。expanding Full Pathの51.9650%、0.2493521、0.6918504を大きく下回り、accuracyは7/7 foldで負けた。recentモデル自体を方向やconfidenceとして採用する余地はない。

## Temporal uncertainty overlay

方向はexpanding Full Pathへ固定されるためaccuracyは完全に同じである。確率品質は次のように悪化した。

| period | Full Path Brier / log loss / ECE | temporal overlay Brier / log loss / ECE |
|---|---:|---:|
| development | 0.2492482 / 0.6916428 / 0.255% | 0.2494331 / 0.6920123 / 1.015% |
| confirmation | 0.2495173 / 0.6921801 / 0.235% | 0.2496701 / 0.6924867 / 0.568% |
| all | 0.2493521 / 0.6918504 / 0.248% | 0.2495246 / 0.6921956 / 0.842% |

Brier/log loss/ECEは各2/7 foldしか改善しなかった。弱いrecentモデルのedgeを下限にすると、正しいconfidenceまで過度に0.5へ縮め、校正を改善しなかった。

development gridでoverlayの最大scoreは0.515だった。

| period | Full Path accuracy / coverage / score | temporal overlay accuracy / coverage / score |
|---|---:|---:|
| development | 53.074% / 60.737% / 0.02067 | 54.096% / 32.368% / 0.02003 |
| confirmation | 52.620% / 47.587% / 0.01394 | 53.208% / 23.885% / 0.01154 |
| all | 52.924% / 55.658% / 0.01924 | 53.814% / 29.091% / 0.01801 |

accuracyは7/7 fold上がるが、coverageがほぼ半減し、selection scoreは3/7しか改善しなかった。accuracyだけを上げる強いabstentionで、ユーザー目的のaccuracy×coverage最大化にはならない。

## 異種disagreementとの比較

既存の5異種モデル平均edge shadowと同じ0.515で比較した。

| period | temporal accuracy / coverage / score | heterogeneous accuracy / coverage / score |
|---|---:|---:|
| development | 54.096% / 32.368% / 0.02003 | 53.561% / 51.516% / 0.02228 |
| confirmation | 53.208% / 23.885% / 0.01154 | 52.766% / 43.825% / 0.01418 |
| all | 53.814% / 29.091% / 0.01801 | 53.283% / 48.546% / 0.02031 |

temporal overlayはaccuracyを上げるが、scoreはdevelopment/confirmation/allすべてで低く、年別scoreも3/7対4/7だった。Full Pathの0.53 selective championはさらに高いall score 0.02076を持つ。

## 判断

固定3年recent modelとのagreementは、予測可能性よりrecent modelの情報不足を測っており、有効なepistemic uncertaintyにならなかった。recent単体、1σ temporal overlayとも不採用とする。成果物は再現用に残すがconfig、registry、latest artifactは発行しない。

同じ履歴でwindow長、複数window、penalty、重み、閾値を再探索しない。expanding Full Path 0.53 selective championと既存異種disagreement shadowを維持する。

## 成果物

- recent Full Path: `experiments/next_bar/walk_forward_intrabar_full_path_rolling_3y_m15_001`
- temporal overlay: `experiments/next_bar/intrabar_full_path_temporal_uncertainty_m15_001`
- baseline analysis: `experiments/next_bar/intrabar_full_path_temporal_uncertainty_m15_analysis.json`
- heterogeneous比較: `experiments/next_bar/intrabar_full_path_temporal_uncertainty_vs_disagreement_m15_0515_analysis.json`
