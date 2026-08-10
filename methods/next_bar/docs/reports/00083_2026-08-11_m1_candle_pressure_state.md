# 00083 M1 Candle Pressure State

日時: 2026-08-11 JST

## 目的

M1完成足の実体、上下ヒゲ、終値位置をrange内の買い／売り圧力へ変換し、直近複数足での持続と加速を次足方向へ利用できるか確認した。Path Persistenceの終値return系列とは異なり、各足内部の形状を時系列集約する加工である。

## 固定特徴と品質

各完成足について次の3系列を[-1, 1]で作った。

- body pressure: `(close - open) / (high - low)`
- wick pressure: `(lower wick - upper wick) / (high - low)`
- close pressure: `(2 * close - high - low) / (high - low)`

3/8/21本の各固定窓で3系列の平均、range加重body/wick pressureを作り、さらに3本平均−8本平均のbody/wick/close加速度を追加した。合計18列、baselineと合わせて56特徴である。窓長・subsetは結果確認後に変更していない。

価格scale不変、未来行改変が過去特徴へ影響しない因果性、完全無変動足の0/0を圧力証拠なしの0とする有限値、raw OHLCがmodel featureへ入らないこと、保存artifactからのlatest推論をテストした。source 6,025,170行、usable 5,737,928行、baselineと完全整列したOOS 2,183,717行を同じ7fold、最大750,000行expanding HGB、fold別Plattで評価した。損失係数は標準1.0である。

## 単体と固定25%方向blend

| period | baseline | Pressure State single | HGB 75% + Pressure State 25% |
|---|---:|---:|---:|
| development accuracy | 50.93738% | 50.94895% | 50.97217% |
| confirmation accuracy | 50.60001% | 50.57987% | 50.61375% |
| all accuracy | 50.80695% | 50.80626% | 50.83360% |

単体はdevelopment +155件、confirmation -170件、all -15件・p=0.977で、accuracy/Brier/log loss各4/7foldのため不採用とする。

通常25% blendはdevelopment +466件・p=0.0166、confirmation +116件・p=0.448、all +582件・p=0.0184。accuracy/Brier/log lossを6/7、ECEを5/7fold改善した。UTC日paired bootstrap 20,000回ではall accuracy差95%区間が+0.00519〜+0.0484pt、all Brier差が-0.00000773〜-0.00000394、log loss差が-0.0000155〜-0.00000793で、baseline補完性は再現した。一方、confirmation accuracy・Brier・log lossの各区間は0を跨ぐ。

## 既存候補との比較

Path 25%に対してdevelopment -0.00672pt、confirmation -0.0320pt、all -0.0165ptで、accuracyは2/7対5/7だった。all accuracy差bootstrap区間は-0.0389〜+0.00605ptで0を跨ぐが、既存point championを上積みしない。

新しいExtra Trees 25% stability候補にはdevelopment、confirmation、allの全期間で負け、accuracy 1/7対6/7だった。Extra Treesはbaseline比accuracy/Brier/log lossを7/7fold改善しており、Pressure Stateの6/7より安定している。

Session Relativeにはaccuracy 5/7勝つが、confirmation accuracyは50.6137%対50.6386%、allは50.8336%対50.8374%。SessionのBrier/log lossもdevelopment、confirmation、allで一貫して良い。Pressure Stateはpoint champion、stability challenger、probability-quality specialistのどの役割も置換しない。

## Confidence用途

development gridの目的関数最大は固定候補中0.515だった。方向維持blendはconfirmationでcoverage 9.91%、accuracy 52.607%、selection score 0.007139となりbaselineの52.509%、0.006837を上回った。全期間でもaccuracy/scoreを5/7fold改善した。

しかしTCN 0.515はconfirmation accuracy 53.041%、score 0.007506、all accuracy 52.303%であり、Pressure Stateはaccuracy・scoreとも0/7対7/7。日次bootstrapのPressure State−TCN accuracy差95%区間はconfirmation -0.649〜-0.221pt、all -0.242〜-0.0923ptで明確に劣る。all Brier/log lossもTCNが有意に良い。coverageが約2.27pt広いだけでは主評価を補えないためconfidence用途も不採用とする。

## 判断

Candle Pressure Stateはbaselineを補完する情報を持つが、既存採用候補への増分edgeがない。feature set、OOS、通常blend、方向維持blend、直接比較、bootstrapは再現用に残すが、forward config、candidate registry、latest artifact、odds calibrationは発行しない。

3/8/21窓、18列subset、HGB parameter、25% weight、0.515以外のconfidence閾値を同じ履歴へ合わせて再探索しない。Path/LightGBM、Extra Trees、Volatility/Session、TCNの既存役割とauthoritative方向・confidence・fair odds・売買policyを維持する。

## 成果物

- OOS: `experiments/next_bar/walk_forward_candle_pressure_state_m1_fixed_001`
- normal blend: `experiments/next_bar/candle_pressure_state_m1_blend_current_001`
- direction-preserving blend: `experiments/next_bar/candle_pressure_state_m1_confidence_blend_current_001`
- candidate analysis: `experiments/next_bar/candle_pressure_state_m1_candidate_analysis.json`
- baseline bootstrap: `experiments/next_bar/candle_pressure_state_m1_direction_bootstrap.json`
- Path comparison/bootstrap: `experiments/next_bar/candle_pressure_state_vs_path_m1_direction_analysis.json`, `experiments/next_bar/candle_pressure_state_vs_path_m1_direction_bootstrap.json`
- Extra Trees comparison: `experiments/next_bar/candle_pressure_state_vs_extra_trees_m1_direction_analysis.json`
- Session comparison: `experiments/next_bar/candle_pressure_state_vs_session_m1_direction_analysis.json`
- TCN confidence comparison/bootstrap: `experiments/next_bar/candle_pressure_state_vs_tcn_m1_confidence_0515_analysis.json`, `experiments/next_bar/candle_pressure_state_vs_tcn_m1_confidence_0515_bootstrap.json`
