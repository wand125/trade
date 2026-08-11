# 00123 M5 Directional Follow-through Sample Weighting

日時: 2026-08-11 16:59 JST

## 目的

M30で高信頼度選別に増分があったDirectional Follow-through教師重みを、式、HGB、25% blend、評価閾値gridを変更せずM5へ移植した。既存M5 Pressure方向候補、Profile broad confidence候補に対して、方向正答率と信頼度のオッズ品質を独立評価した。

## 固定仕様と品質

解決済みtrain次足だけで `clarity = abs(close - open) / (high - low)` と方向側close到達度を計算し、積を0〜1へ制限した。raw sample weightは `0.5 + clarity * direction_aligned_close_location`、範囲0.5〜1.5、sampled train内平均1である。次足OHLCはtrain sample weight以外へ渡さず、入力特徴、calibration、test、latest推論には使わない。

baseline加工38特徴、HGB 200 iteration、31 leaves、learning rate 0.05、min leaf 100、L2 1、seed 42、expanding、最大train 750,000行、Platt、全教師、標準損失1.0を固定した。test2020〜test2026途中の7fold、439,881 OOS行をtimestamp/targetで既存候補と完全整列した。M30結果を見た後にM5用の重み式、model parameter、25%/50%比率、閾値を探索していない。

保存artifactのlatest推論は2026-06-01 04:50 UTCから次M5をup、probability up 53.0523%とした。経験的校正とruntime blendを接続していないため `odds_valid=false` である。

## 単体と方向用途

| model | development accuracy | confirmation accuracy | all accuracy | all Brier | all log loss | all ECE |
|---|---:|---:|---:|---:|---:|---:|
| HGB baseline | 51.8795% | 51.0408% | 51.5564% | 0.249547231 | 0.692239998 | 0.3687% |
| Follow-through weighted単体 | 51.8196% | 51.1028% | 51.5435% | 0.249620456 | 0.692386844 | 0.8024% |
| baseline 75% + Follow-through 25% | 51.8809% | 51.0686% | 51.5680% | 0.249539253 | 0.692223876 | 0.4338% |

単体はbaseline比development -162件、confirmation +105件、all -57件、accuracy 3/7foldで、proper scoreとECEも悪化した。通常25% blendは+4/+47/+51件でもMcNemar exact p=0.702、accuracy 4/7foldで方向増分は未確定だった。

現行Pressure 25%方向候補との直接比較では、通常blendがdevelopment -115件、confirmation +30件、all -85件、accuracy 1/7対6/7だった。日次bootstrapのall accuracy差95%区間は-0.0797〜+0.0403ptで、Brier/log lossはFollow-through側の悪化を支持した。Pressure親とFollow-through単体の固定50/50平均もall +81件だったが3/7fold、proper score悪化、accuracy区間0跨ぎである。M5方向候補には追加しない。

## Broad confidence 0.515

baseline方向を維持した25% confidenceを、現行Profile broad候補と同じ固定0.515で比較した。

| period | Follow-through coverage / accuracy / score | Profile coverage / accuracy / score |
|---|---:|---:|
| development | 59.6820% / 52.7706% / 0.019522 | 58.4023% / 52.7936% / 0.019467 |
| confirmation | 41.1625% / 52.2884% / 0.012303 | 37.1154% / 52.4115% / 0.012313 |
| all | 52.5488% / 52.6251% / 0.017554 | 50.2031% / 52.6848% / 0.017547 |

Follow-throughはcoverageを増やしたが、confirmation scoreは僅かに低く、all score差+0.0000064の日次区間は-0.000498〜+0.000497で同等域だった。accuracyは年別3/7対4/7、all -0.0597ptで、全確率のBrier/log loss/ECEもProfileより悪い。broad confidenceを置換せず、固定50/50 confidence平均もall scoreとconfirmation accuracy/scoreを下げたため使わない。

## 高信頼度0.55

事前gridに含めた0.55では異なる結果になった。

| period | Follow-through coverage / accuracy / score | Profile coverage / accuracy / score |
|---|---:|---:|
| development | 9.0213% / 56.0825% / 0.016396 | 8.5901% / 55.8282% / 0.015207 |
| confirmation | 0.7537% / 57.6351% / 0.004259 | 0.3943% / 57.7844% / 0.002515 |
| all | 5.8368% / 56.1597% / 0.013413 | 5.4333% / 55.8828% / 0.012243 |

Follow-throughはaccuracy 3/7、selection score 7/7foldだった。Profile比の日次bootstrap 20,000回では、development score差95%区間+0.000393〜+0.001970、all accuracy +0.0007〜+0.5567pt、coverage +0.3598〜+0.4471pt、score +0.000521〜+0.001831で改善を支持した。confirmation score区間は-0.000201〜+0.003631で未確定である。

allの25,675件はaccuracy 56.1597%、mean confidence 56.3320%、絶対差0.1724ptでWilson区間内だった。Profileが選ばずFollow-throughだけが選んだ3,391件も56.9154%正解、逆の1,616件は53.6510%であり、追加coverageは診断上の品質を保った。ただしconfirmationは1,277件、2025年は172件、2026途中は182件と疎く、同じ履歴から追加guardを作らない。

## 判断

単体と通常25% blendは再現専用とし、既存Pressure方向候補を維持する。0.515 broad confidenceもProfileよりaccuracy、confirmation objective、proper scoreが弱いため置換しない。Profileとの固定50/50 confidence平均も採用しない。

方向維持25% blendの固定0.55だけを `m5_directional_follow_through_high_confidence_shadow_v1.json` のparallel forward high-confidence shadowとして採用する。これはauthoritative confidence、Profile 0.515 broad候補、fair odds、adoption/paper/live policyを変更しない。full runtime ensemble parityを実装し、完全未使用期間でProfile 0.55以上のaccuracy、coverage、selection scoreを下回らず、global/local calibrationも通るまで実利用しない。

## 成果物

- implementation: `src/trade_data/next_bar.py`
- tests: `tests/test_next_bar.py`
- Follow-through OOS/latest: `experiments/next_bar/walk_forward_directional_follow_through_weighted_m5_fixed_001`, `experiments/next_bar/directional_follow_through_weighted_m5_latest_prediction.json`
- normal/confidence blends and analysis: `experiments/next_bar/directional_follow_through_weighted_m5_*`
- Pressure direction comparisons: `experiments/next_bar/directional_follow_through_m5_direction_vs_pressure*`
- Profile 0.515/0.55 comparisons: `experiments/next_bar/directional_follow_through_m5_confidence_vs_profile*`
- fixed diversification checks: `experiments/next_bar/pressure_directional_follow_through_equal_m5_*`, `experiments/next_bar/profile_directional_follow_through_equal_m5_*`
- adopted shadow config: `methods/next_bar/config/m5_directional_follow_through_high_confidence_shadow_v1.json`
