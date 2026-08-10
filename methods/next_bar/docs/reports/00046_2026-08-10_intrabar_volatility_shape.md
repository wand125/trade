# 00046 Intrabar volatility shape

日時: 2026-08-10 15:55 JST

## 目的

完成M15内部のM1変動を、途中終値の軌跡とは別に「値幅・分散が足内のどこへ集中したか」へ加工し、Intrabar Profileに対する増分方向edgeと信頼度用途を検証する。

## 結果前に固定した特徴

`--feature-set intrabar_volatility_shape` はIntrabar Profileへ14特徴を追加する。M1 high-lowとM1 close-to-close log return二乗について、集中度、上位3本の構成比、時間重心、序盤・終盤1/3の構成比、終盤−序盤を作り、range側には相対分散、variance側との差も加える。

すべて完成済みM1だけを使い、足内合計または平均で正規化する。raw価格水準とvolumeは使わない。OHLCを10倍しても不変、未来M1改変が過去特徴へ影響しない、flat足は有限な意味的ゼロ、41 intrabar特徴、artifact保存とlatest推論をテストした。HGB、Platt、M15 7fold、25% blend、confidence閾値gridは既存条件を変更していない。

## 単体方向モデル

| period | baseline accuracy | Shape single accuracy |
|---|---:|---:|
| development | 52.014% | 52.275% |
| confirmation | 51.501% | 51.583% |
| all | 51.816% | 52.008% |

accuracyは6/7、Brierとlog lossは5/7 fold改善した。全体でbaseline誤りを10,138件修正し、正解を9,860件失い、純改善278件。paired exact p=0.0501である。confirmation単独は46件純改善、p=0.602なので、全履歴の探索回数も考えると現行方向の即時置換根拠にはしない。

親Profile単体に対してもdevelopment 52.063%→52.275%、confirmation 51.394%→51.583%、全体51.804%→52.008%と改善した。5/7 fold勝ち、純改善295件、paired p=0.0135で、14特徴の方向情報は親trajectory特徴への増分と判断できる。ただしProfileよりBrier/log lossは悪いため、Shapeのclass probabilityを信頼度として優先しない。

## 通常25% blendは棄却

baseline 75% + Shape 25%はdevelopment accuracyを52.014%から52.065%へ上げたが、confirmationは51.501%から51.487%へ下げた。全体純改善37件、p=0.610である。単体で現れた方向境界の変更が25%混合では消えるため、weightを履歴へ合わせて再探索せず棄却した。

## Confidence用途は棄却

方向をbaselineへ固定したShape confidenceは、developmentで固定gridから0.515を選び、baseline比ではdevelopment/confirmationのaccuracy・selection scoreを改善した。しかし同じ0.515で既存Profileと直接比較するとShapeのaccuracy/score勝敗は3/7対4/7で、developmentと全体のscoreはProfileが高かった。

さらにProfileとShapeのconfidenceを50/50平均すると、confirmation scoreは0.01513から0.01549へ上がった一方、developmentは0.02134から0.02090、全体は0.02007から0.01992へ下がった。結果後に平均weightや閾値を調整せず、Profile 0.515をbroad confidence championとして維持する。Shapeをcandidate registryやfair oddsへ追加しない。

## 既存Pressure方向候補との関係

Shape単体はPressure 25% blendよりdevelopment、confirmation、全体のaccuracyが高いが、年別勝敗は4/7、paired p=0.146で、Brier/log lossも全体ではPressureが良い。履歴だけでPressureを置換せず、独立したparallel direction candidateとしてfresh期間でhead-to-headする。

## 最新推論

baselineと同じ60/20/20 split・主要学習設定でShape artifactを生成し、candidate weight 1.0の共通runtime経路を通した。2026-06-01 04:45 UTCはbaseline up 0.577254、Shape up 0.564871で、ともにup。artifact parityは通過した。

Shape probabilityには独立したodds校正を接続していないため `odds_valid=false`、`strict_prediction_eligible=false` である。

## 成果物と判断

- OOS単体: `experiments/next_bar/walk_forward_intrabar_volatility_shape_m15_001`
- 通常25% blend: `experiments/next_bar/ensemble_intrabar_volatility_shape_m15_25_001`
- 方向維持confidence: `experiments/next_bar/intrabar_volatility_shape_m15_confidence_blend_001`
- baseline比較: `experiments/next_bar/intrabar_volatility_shape_m15_candidate_analysis.json`
- 親Profile方向比較: `experiments/next_bar/intrabar_volatility_shape_vs_profile_m15_direction_analysis.json`
- Pressure方向比較: `experiments/next_bar/intrabar_volatility_shape_vs_pressure_m15_direction_analysis.json`
- Profile confidence平均比較: `experiments/next_bar/intrabar_profile_vs_profile_volatility_shape_m15_0515_analysis.json`
- latest artifact/runtime: `experiments/next_bar/intrabar_volatility_shape_m15_latest_artifact_001`, `experiments/next_bar/intrabar_volatility_shape_m15_latest_ensemble_001`
- 固定設定: `methods/next_bar/config/m15_intrabar_volatility_shape_direction_candidate_v1.json`

Shape単体だけをM15 parallel direction candidateとして採用する。通常25% blend、confidence、Profileとのconfidence平均は棄却する。現行方向・authoritative confidence・fair odds・paper policyは置換しない。損失倍率は標準1.0のみとする。
