# 00057 Intrabar Flow Shape fixed union

日時: 2026-08-10 17:40 JST

## 目的

別々に検証済みのIntrabar PressureとIntrabar Volatility Shapeは、同じM15足内でも異なる情報を表す。PressureはM1足のCLV・wick・body圧力、Shapeは値幅・分散の集中位置を表すため、両者の固定unionに増分edgeがあるかを検証する。

## 方法

- `intrabar_flow_shape` を追加し、Pressure 11列とVolatility Shape 14列を同時に使う。
- 共通のManual 7列、Structure 8列、Profile 12列を含め、intrabar 52列、全90特徴とする。
- 特徴subset、HGB/Platt設定、7fold境界、25% blend weight、confidence gridは結果を見る前に固定した。
- developmentは2020〜2023、confirmationは2024〜2026-06、合計145,140 OOS行。
- 正式baseline、両親モデル、現行selective championのDistribution Shape 0.53と比較する。
- 小差はUTC日paired block bootstrap 5,000回、seed 42でも監査する。

価格10倍で同値、60分以降の未来改変が先行特徴へ不影響、flat足で有限0、artifact学習とlatest予測を単体テストした。

## 方向結果

| model | development accuracy | confirmation accuracy | all accuracy |
|---|---:|---:|---:|
| 正式baseline | 52.014% | 51.501% | 51.816% |
| Pressure | 52.040% | 51.560% | 51.855% |
| Volatility Shape | 52.275% | 51.583% | 52.008% |
| Flow Shape union | 52.072% | 51.569% | 51.877% |

Flow Shapeはbaselineを両期間で上回ったが、強い親であるVolatility Shapeにdevelopment/allで負けた。Shapeに対するpaired方向差はdevelopment -181件、confirmation -8件、all -189件、all exact p=0.105である。Pressureとはall +33件、p=0.785で実質同等だった。

baseline 75% + Flow 25%の通常blendはdevelopmentを52.014%から52.054%へ上げた一方、confirmationを51.501%から51.455%へ下げた。方向用途では親Shapeもbaselineも置換しない。

## 信頼度結果

development gridでFlow Shape方向維持25% blendが最大化した閾値は0.53だった。同じ固定0.53で比較した。

| period / candidate | accuracy | coverage | selection score |
|---|---:|---:|---:|
| development baseline | 54.309% | 29.868% | 0.02027 |
| development Flow | 54.623% | 29.429% | 0.02181 |
| development Distribution | 54.575% | 29.111% | 0.02141 |
| confirmation baseline | 54.479% | 18.438% | 0.01511 |
| confirmation Flow | 54.276% | 17.919% | 0.01397 |
| confirmation Distribution | 54.551% | 17.894% | 0.01512 |
| all baseline | 54.357% | 25.453% | 0.01942 |
| all Flow | 54.527% | 24.983% | 0.02006 |
| all Distribution | 54.568% | 24.779% | 0.02018 |

Flowはdevelopmentで最良だったが、confirmationでbaselineとDistributionの両方に負けた。Distributionとの年別比較もlane accuracyは2/7対5/7である。baseline比Brier/log lossは7/7 fold改善したが、主目的の確認期間selection score悪化を補えない。

Flow minus Distributionの日次bootstrapでは、confirmation accuracy差 -0.275ptの95%区間が-0.602〜+0.076pt、selection score差 -0.001153が-0.002534〜+0.000334だった。区間は0を跨ぐが、Flow優位確率はそれぞれ6.0%、6.3%しかなく、確認期間で優れる根拠はない。

## 判断

`intrabar_flow_shape` は再現用feature setとして残すが、方向・confidenceとも棄却する。単純unionは特徴数を増やしても親Shapeの方向edgeを上積みせず、developmentで見えた0.53 confidence改善もconfirmationで反転した。

- candidate config、registry entry、latest artifactは発行しない。
- 現行方向候補はVolatility Shape単体を維持する。
- selective confidenceはDistribution Shape 0.53とExtra Trees 0.53を維持する。
- Pressure/Shape subset、union weight、閾値を同じ履歴へ合わせて再探索しない。

主要成果物:

- `experiments/next_bar/walk_forward_intrabar_flow_shape_m15_001`
- `experiments/next_bar/intrabar_flow_shape_m15_candidate_analysis.json`
- `experiments/next_bar/intrabar_flow_shape_vs_volatility_shape_m15_053_analysis.json`
- `experiments/next_bar/intrabar_flow_shape_vs_pressure_m15_053_analysis.json`
- `experiments/next_bar/intrabar_flow_shape_vs_distribution_shape_m15_053_analysis.json`
- `experiments/next_bar/intrabar_flow_shape_vs_volatility_shape_m15_053_daily_bootstrap.json`
- `experiments/next_bar/intrabar_flow_shape_vs_distribution_shape_m15_053_daily_bootstrap.json`

