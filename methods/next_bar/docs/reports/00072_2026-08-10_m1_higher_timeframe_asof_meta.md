# 00072 M1 × Higher-timeframe as-of meta

日時: 2026-08-10 20:23 JST

## 目的

M15での特徴追加が飽和しつつあるため、予測対象をM1へ移し、判定時点で確定済みのM5/M15方向確率を上位足contextとして加工することで、M1方向精度または高信頼帯のaccuracy×coverageを改善できるか検証した。

## 実装と時系列制約

cross-timeframe metaへ任意の `--target-timeframe` と `--context-timeframes` を追加し、M1をtarget、M5/M15をas-of contextにできるようにした。exact/as-of間の重複、contextの重複、target自身のcontext再利用は停止する。CLI、未来不参照、age計算をテストした。

各M1 decision timestampに対し、その時刻以前で最新のM5/M15 OOS予測だけをbackward as-of joinし、age上限を14分に固定した。M5 ageは通常0〜4分で、市場データの空白時だけ最大14分、M15 ageは0〜14分だった。評価元1,838,730行のうち1,801,567行、97.979%を保持し、context欠損37,163行を除外した。

meta logistic regressionは各test foldより前のOOS foldだけで学習した。C=0.10、M1 target確率75% + meta確率25%を事前固定し、評価期間は2021〜2026途中の6fold。損失倍率は標準1.0のみである。

## 全方向と確率品質

| metric | M1 target | M5/M15 meta 25% blend | delta |
|---|---:|---:|---:|
| accuracy | 50.64430% | 50.63220% | -0.01210pt |
| balanced accuracy | 50.63542% | 50.61948% | -0.01593pt |
| Brier | 0.24991795 | 0.24992032 | +0.00000237 |
| log loss | 0.69298310 | 0.69298784 | +0.00000474 |
| ECE | 0.22441% | 0.21148% | -0.01293pt |

blendはbaselineの誤り22,687件を直した一方、正解22,905件を壊し、純-218件、McNemar exact p=0.3095だった。方向accuracyの改善は1/6 fold、Brier/log lossは各3/6、ECEは4/6で、ECEだけの改善では採用できない。

学習済み係数はM1が0.561〜0.710、M5が全fold正の0.116〜0.195だったが、M15は-0.0446〜+0.0079で正負が安定しなかった。M5には弱い増分情報があるものの、25% blendでM1方向を置換する強さはない。

## 高信頼度帯

| confidence | M1 coverage / accuracy | blend coverage / accuracy |
|---:|---:|---:|
| 0.51 | 32.393% / 51.449% | 31.011% / 51.478% |
| 0.52 | 8.227% / 52.418% | 7.693% / 52.419% |
| 0.53 | 2.371% / 53.247% | 2.206% / 53.047% |
| 0.55 | 0.277% / 53.612% | 0.261% / 53.671% |

閾値が上がるほどbaseline自体のaccuracyは概ね上がり、M1 confidenceに弱い順位付け能力があることは確認できた。しかしblendはcoverageを一貫して減らし、0.53ではaccuracyも低下した。0.55の+0.059ptは4,699行だけで、coverageも低いためedgeの増分とは判断しない。

development 2021〜2023だけで事前gridから選ぶと、blendの最大selection scoreは0.51だった。

| period | M1 accuracy / coverage / score | blend accuracy / coverage / score |
|---|---:|---:|
| development | 51.354% / 38.712% / 0.007429 | 51.358% / 37.922% / 0.007368 |
| confirmation | 51.621% / 25.034% / 0.007038 | 51.709% / 22.964% / 0.007115 |
| all | 51.449% / 32.393% / 0.007519 | 51.478% / 31.011% / 0.007501 |

confirmationではaccuracy +0.088pt、score +0.000077だったが、development scoreが悪化し、全期間scoreも僅かに低い。0.51のaccuracy/score改善foldは各2/6で、期間安定性も採用条件を満たさない。

## 判断

M1 × M5/M15 as-of metaは不採用とする。未来不参照で上位足を利用できる実装経路と、M1 baselineのconfidence上昇に伴うaccuracy上昇は確認できたが、固定25% metaは全方向、proper score、高信頼selection scoreを安定して改善しない。

今回の結果を見てcontext subset、age、regularization、weight、閾値を同じ履歴で再探索しない。config、registry、latest artifactは発行せず、成果物は再現専用に残す。次のM1研究では同じ確率の再混合ではなく、M1内の確定済みmicrostructureやregime加工を独立候補として扱う。

## 成果物

- meta OOS: `experiments/next_bar/cross_timeframe_meta_m1_asof_m5_m15_001`
- target/context OOS: `experiments/next_bar/context_confirmation_001`, `experiments/next_bar/walk_forward_001`
