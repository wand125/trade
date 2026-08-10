# 00093 M1 Causal Transformer

日時: 2026-08-11 06:46 JST

## 目的

手動のDistribution Shift特徴とは独立した系列学習経路として、M15で事前固定した小型causal TransformerをM1へ仕様変更せず移植した。同じ16本×5加工系列を使うTCN/GRUとのarchitecture比較であり、M1結果を見てwindow、dimension、head、epoch、学習率、blend weight、confidence閾値を再調整しない。

## 固定仕様と品質

入力は直近16完成足のATR正規化return/body/range、中心化close location、ATR正規化wick balanceで、生価格水準とvolumeを使わない。各foldのtrainだけでchannel標準化し、learned position、dimension 16、4-head、encoder 1層、feed-forward 32、dropout 0、last-token pooling、2,625 parameter、8 epoch、batch 2,048、AdamW、learning rate 0.0005、weight decay 0.0001、seed 42、train上限750,000、後続Plattを固定した。

2020〜2026途中の7foldでsource 6,025,170行、usable 5,737,928行、OOS 2,183,717行を生成した。baselineとのtimestamp、decision/target timestamp、target、foldは全件一致し、重複0、確率欠損0だった。7 artifactすべて2,625 parameter、8 loss点で、train lossは約0.6962〜0.6964から0.6924〜0.6927へ低下した。既存テストで未来足改変に対する系列因果性、flat区間の有限0、同一seed完全一致、保存artifactからのlatest推論を確認している。

## 単体と通常方向blend

| period | baseline | Transformer単体 | 通常25% blend |
|---|---:|---:|---:|
| development | 50.93738% | 50.82316% | 50.95985% |
| confirmation | 50.60001% | 50.58378% | 50.62026% |
| all | 50.80695% | 50.73061% | 50.82856% |

単体はbaseline比-1,667件、accuracy改善2/7fold、McNemar exact p=0.0188で明確に悪いため棄却した。通常25% blendはdevelopment +301、confirmation +171、all +472件でaccuracy 6/7、Brier/log loss各6/7foldを改善したが、all McNemar p=0.1776だった。UTC日paired bootstrap 20,000回のaccuracy差95%区間はdevelopment -0.0210〜+0.0655pt、confirmation -0.0321〜+0.0718pt、all -0.0115〜+0.0542ptで、方向改善を支持しなかった。

Path Persistence方向blendに対してはall accuracy -0.0215ptで差の区間は0を跨いだ。一方、Transformer blendのBrier/log lossはPathより明確に良かったが、既存Distribution Shift blendは方向accuracyを7/7foldかつ日次区間で改善している。方向accuracyの独立edgeとして既存候補を置換しない。

## 方向維持confidence 0.51

baseline方向を完全に維持し、baseline 75% + Transformer 25%でedge強度だけを補正した。developmentの固定grid `0.51, 0.515, 0.525, 0.535, 0.55` からcoverage-aware score最大の0.51を選び、confirmationへ一度だけ適用した。

| period | baseline accuracy / coverage / score | Transformer accuracy / coverage / score |
|---|---:|---:|
| development | 51.5790% / 44.0150% / 0.009629 | 51.6676% / 42.5470% / 0.010031 |
| confirmation | 51.8000% / 24.2132% / 0.007791 | 51.9332% / 21.2337% / 0.007842 |
| all | 51.6359% / 36.3595% / 0.009202 | 51.7312% / 34.3071% / 0.009477 |

accuracyはbaseline比7/7fold、selection scoreは5/7fold、全行Brier/log lossは6/7fold改善した。日次bootstrapでaccuracy差はdevelopment +0.0321〜+0.1451pt、confirmation +0.0232〜+0.2429pt、all +0.0453〜+0.1454ptと改善側だった。一方、selection score差はdevelopmentだけ+0.000033〜+0.000772で、confirmation -0.000466〜+0.000564、all -0.000020〜+0.000569は0を跨いだ。確認期間ではcoverage減少に見合う目的関数改善が確定しない。

同じultra-broad 0.51のDistribution Shiftに対し、Transformerはdevelopment score 0.010031対0.010357、confirmation 0.007842対0.008142、all 0.009477対0.009802だった。fold勝敗もaccuracy 3/7、score 2/7である。all score差はDistribution Shift優位の区間だった。現Transition guard champion 0.515にはaccuracy 0/7、development score 0.010031対0.010447で下回り、all Brier/log lossも悪化区間が確定した。

## 信頼度品質

0.51 laneのmean confidence / accuracyはdevelopment 52.0249% / 51.6676%で過信、confirmation 51.4813% / 51.9332%で過小評価となり、局所校正が時期で反転した。confirmationのaccuracyは0.51→0.515→0.525→0.535で51.93%→52.99%→55.56%→56.68%と単調に上がったが、coverageは21.23%→7.55%→0.88%→0.13%へ急減した。0.55は24件・58.33%、Wilson下限38.83%でedge未確認だった。

固定side×volatilityのconfirmation 0.51ではdown-high、down-normal、up-high、up-normalだけがWilson edgeを通り、down-low 3,167件とup-low 8,515件は未確認だった。confirmationを見た後のsubgroup filterは作らない。aggregate確率品質や高閾値の点精度だけをfair oddsの根拠にせず、oddsは非認可とする。

## 判断

M1 causal Transformer単体、通常方向blend、方向維持confidenceを再現専用として棄却する。0.51はbaseline accuracyを安定改善したが、confirmationのcoverage-aware scoreが確定せず、既存Distribution Shift 0.51とTransition guard 0.515を超えない。Transformerのwindow、dimension、head、layer、epoch、学習率、weight、閾値を同じ履歴で再探索せず、config、latest shadow、fair odds、authoritative confidence、paper/live policyを発行・変更しない。損失倍率は標準1.0のみとする。

## 成果物

- OOS: `experiments/next_bar/walk_forward_causal_transformer_m1_fixed_001`
- direction blend: `experiments/next_bar/causal_transformer_m1_blend_fixed_001`
- direction-preserving confidence: `experiments/next_bar/causal_transformer_m1_confidence_fixed_001`
- candidate analysis: `experiments/next_bar/causal_transformer_m1_candidate_analysis.json`
- baseline bootstraps: `experiments/next_bar/causal_transformer_vs_baseline_m1_direction_bootstrap.json`, `experiments/next_bar/causal_transformer_vs_baseline_m1_confidence_051_bootstrap.json`
- existing-candidate comparisons: `experiments/next_bar/distribution_shift_051_vs_transformer_051_m1_analysis.json`, `experiments/next_bar/distribution_shift_051_vs_transformer_051_m1_bootstrap.json`, `experiments/next_bar/transformer_051_vs_transition_guard_champion_0515_m1_analysis.json`, `experiments/next_bar/transformer_051_vs_transition_guard_champion_0515_m1_bootstrap.json`
- reliability/subgroups: `experiments/next_bar/distribution_shift_vs_transformer_m1_confidence_reliability.json`, `experiments/next_bar/causal_transformer_m1_confidence_subgroups.json`
