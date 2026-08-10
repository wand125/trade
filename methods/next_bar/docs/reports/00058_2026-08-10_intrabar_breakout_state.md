# 00058 Intrabar Breakout State

日時: 2026-08-10 17:50 JST

## 目的

完成M15内のM1足について、価格やreturnの大きさではなく、直前M1高安値に対する突破・押し戻し・range state・方向継続をイベント比率へ加工する。既存Intrabar Profileへ固定12列を追加し、親に対する増分edgeを検証する。

## 特徴

`intrabar_breakout_state` はProfileまでの27 intrabar列へ次の12列を追加し、intrabar 39列、全77特徴を使う。

- close breakout up/down比率
- high/low更新後に終値が直前rangeへ戻ったrejection比率
- inside/outside bar比率
- range expansion、upward/downward range expansion比率
- M1 body方向のcontinuation/reversal比率
- 最長up runとdown runの正規化差

各M15 bucketの最初のM1には直前比較を定義せず、残り14本を固定分母とする。6本の手作りOHLCで全イベント比率を厳密照合し、価格10倍で完全一致、未来改変不影響、flat足有限0、artifact/latest経路をテストした。

## 方法

- HGB/Platt、7fold境界、25% blend weightは既存実験と同一。
- developmentは2020〜2023、confirmationは2024〜2026-06、合計145,140 OOS行。
- confidence閾値は事前gridからdevelopment selection scoreだけで選ぶ。
- 親Profile 0.515との小差はUTC日paired bootstrap 5,000回、seed 42で監査する。

## 方向結果

| model | development accuracy | confirmation accuracy | all accuracy |
|---|---:|---:|---:|
| 正式baseline | 52.014% | 51.501% | 51.816% |
| 親Profile | 52.063% | 51.394% | 51.804% |
| Breakout State | 52.097% | 51.457% | 51.850% |
| Volatility Shape方向候補 | 52.275% | 51.583% | 52.008% |

Breakout StateはProfileを全期間で66件上回ったがexact p=0.567で、親への方向増分は弱い。Volatility Shapeにはdevelopment/confirmation/allで負け、全期間-229件、p=0.059だった。

baseline 75% + Breakout State 25%の通常blendはdevelopmentでbaselineより-8件、confirmation +12件、全期間+4件、p=0.966だった。方向候補には採用しない。

## Confidence 0.515

development gridで最大だった0.515を固定した。baseline方向を維持した25% confidence blendはbaseline gateを通過した。

| period / candidate | accuracy | coverage | selection score |
|---|---:|---:|---:|
| development baseline | 53.102% | 58.645% | 0.02048 |
| development Breakout | 53.174% | 58.186% | 0.02093 |
| development Profile | 53.221% | 58.402% | 0.02134 |
| confirmation baseline | 52.574% | 49.380% | 0.01395 |
| confirmation Breakout | 52.785% | 49.132% | 0.01538 |
| confirmation Profile | 52.743% | 49.327% | 0.01513 |
| all Breakout | 53.039% | 54.689% | 0.01990 |
| all Profile | 53.055% | 54.897% | 0.02007 |

Breakoutはbaselineに対しlane accuracy/score 6/7、Brier/log loss 6/7、ECE 5/7 fold改善した。しかし親Profileとの直接比較ではaccuracy 3/7、selection score 2/7しか勝たず、developmentとallのobjectiveはProfileが上である。選択集合Jaccardは93.35%で、ほぼ同じ行を僅かに入れ替える候補だった。

Breakout minus Profileの日次bootstrapでは、confirmation score差+0.000255の95%区間は-0.000819〜+0.001341で未確定だった。全期間Brier差+0.00001151の区間は+0.00000004〜+0.00002305、log loss差+0.00002323の区間は+0.00000024〜+0.00004647で、proper scoreはBreakoutが悪いことを支持した。

## 判断

`intrabar_breakout_state` は加工方法と再現経路を残すが、方向・confidenceとも採用しない。

- baselineには良い候補でも、親Profileへの安定した増分を示さない。
- broad roleはdevelopment objective、全期間proper score、年別安定性でProfile 0.515が優位。
- broad accuracy challengerのsigned-body 0.52も維持する。
- breakout定義、特徴subset、blend weight、閾値を同じ履歴へ合わせて再探索しない。
- candidate config、registry entry、latest artifactは発行しない。

主要成果物:

- `experiments/next_bar/walk_forward_intrabar_breakout_state_m15_001`
- `experiments/next_bar/intrabar_breakout_state_m15_candidate_analysis.json`
- `experiments/next_bar/intrabar_breakout_state_vs_profile_m15_0515_analysis.json`
- `experiments/next_bar/intrabar_breakout_state_vs_profile_m15_0515_daily_bootstrap.json`
- `experiments/next_bar/intrabar_breakout_state_vs_profile_single_m15_0515_analysis.json`

