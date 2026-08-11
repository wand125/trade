# 00107 M5 Rolling Transition Memory固定移植

日時: 2026-08-11 13:11 JST

## 目的

M1で固定して再現専用としたRolling Transition Memoryが、同じ価格履歴加工を時間足だけ変えたM5でも汎化するか検証した。同じM1履歴でwindowや状態を再探索せず、M1仕様の32/128本、4 bit・16状態、prior range median 20本、global shrinkage strength 8、HGB/Platt、25% blendをそのまま移植した。

## 品質と固定条件

特徴はreturn方向、body/range 0.5、close上/下半分、現在足を除くprior 20本range中央値の4 bitで現在の完成M5足を16状態へ離散化する。現在時点までに結果が確定した直前32/128遷移だけから、同一状態のnext-up率をglobal up率へ固定強度8で縮約し、up/reversal edge、support、local-global差、短長差の9列を作る。raw価格水準と未来足は使わない。

M5 resample、5分timestamp gap、47特徴、有限値、保存artifactとM1/M5 latest推論を回帰テストへ追加した。正式M5 baselineと同じtest2020〜test2026途中の固定7foldを使い、fold、timestamp、decision/target timestamp、targetを完全一致させた439,881 OOS行を生成した。5つの派生成果物でも重複なし、確率和1、confidence=max probability、class confidence一致を確認した。損失倍率は標準1.0のみである。

## 単体と通常方向blend

| candidate | development accuracy | confirmation accuracy | all accuracy | all Brier |
|---|---:|---:|---:|---:|
| baseline | 51.87946% | 51.04084% | 51.55644% | 0.249547231 |
| Memory単体 | 51.86726% | 51.03493% | 51.54667% | 0.249546712 |
| baseline 75% + Memory 25% | 51.89351% | 51.07979% | 51.58009% | 0.249537921 |

単体はbaseline比all -43件で棄却する。通常25% blendはdevelopment +38件、confirmation +66件、all +104件だったが、accuracy 4/7fold、exact paired p=0.2427である。UTC日bootstrap 20,000回のall accuracy差+0.02364ptの95%区間は-0.01585〜+0.06244pt、confirmationも-0.02994〜+0.10708ptで方向改善は未確定だった。

Brier/log lossはbaseline比development、confirmation、allの全期間で日次区間が改善側だった。しかし既存M5 Intrabar Pressure方向blendのall accuracy 51.58736%、Brier 0.249529615に対し、Memoryはaccuracy -0.00727pt、proper scoreもdevelopment/allで有意に悪い。confirmation方向の+0.02892ptは区間が0を跨いだ。PressureとMemoryを固定50/50平均してもall 51.57122%、年別2/7でPressureを上積みしなかった。

## 0.515 broad confidence

developmentの既定gridで最大selection scoreは0.515だった。

| period | candidate | accuracy | coverage | selection score |
|---|---|---:|---:|---:|
| development | baseline | 52.74974% | 58.3997% | 0.019131 |
| development | Memory | 52.76523% | 58.1997% | 0.019214 |
| confirmation | baseline | 52.35499% | 37.2423% | 0.011993 |
| confirmation | Memory | 52.45330% | 36.5559% | 0.012454 |
| all | baseline | 52.63706% | 50.2504% | 0.017218 |
| all | Memory | 52.67715% | 49.8630% | 0.017429 |

Memoryはbaseline比accuracy/selection scoreを5/7、Brier/log lossを6/7fold改善した。日次bootstrapもproper scoreの3期間改善を支持した。一方、accuracy差とselection score差はdevelopment、confirmation、allの全区間が0を跨ぎ、coverageは一貫して減った。

既存M5 Profile 0.515のall accuracy 52.68482%、coverage 50.2031%、score 0.017547に対し、Memoryはaccuracy -0.00768pt、coverage -0.3401pt、score -0.000119だった。Memoryはaccuracy 4/7でもscore 3/7、Profileはscore 4/7で、MemoryのBrier/log lossはdevelopment/allで有意に悪い。固定50/50平均はProfile比all accuracy +0.00600pt、score +0.000004に過ぎず、development scoreは低下し、日次区間は全指標で0を跨いだ。Profile broad confidence候補を置換・拡張しない。

## 高信頼度tail

Memory 0.55はall 23,700件、coverage 5.3878%、accuracy 56.0633%、mean confidence 56.3692%だった。confirmationは613件、58.7276%、mean confidence 55.6034%と点推定は良いが、既存Profileとの差+0.9431ptの日次区間は-1.2650〜+3.1740ptで未確定である。

さらにbaseline 0.55はall 24,481件、accuracy 56.0761%、score 0.012865で、Memoryの56.0633%、0.012605を上回った。Memoryはbaselineにaccuracy/score 3/7対4/7で、test2026途中は108件・49.0741%まで反転した。0.60はall 437件・61.3272%でもconfirmation 0件であり、継続的な高信頼度edgeではない。高信頼tailをprecision候補、fair odds、policyへ使わない。

## 判断

固定仕様のM5移植はbaselineのproper scoreとconfirmation点精度を改善し、局所遷移加工が時間足を跨いで補完情報を持つことは確認できた。しかし単体は弱く、通常方向差は未確定で既存Pressureに負け、0.515は既存Profileを上回らず、0.55もbaseline未達かつ最新foldで反転した。固定等分多様化も既存候補を上積みしない。

したがってM5でも研究再現専用とする。window、state bit、range基準、prior strength、blend weight、confidence thresholdを同じ履歴で再探索しない。M5 Profile broad confidenceとPressure方向候補を維持し、config、registry、authoritative方向/confidence、fair odds、adoption/paper/live policy、runtime latestを変更しない。

## 成果物

- OOS: `experiments/next_bar/walk_forward_rolling_transition_memory_m5_fixed_001`
- baseline blends: `experiments/next_bar/rolling_transition_memory_m5_blend_fixed_001`, `experiments/next_bar/rolling_transition_memory_m5_confidence_fixed_001`
- analysis/reliability: `experiments/next_bar/rolling_transition_memory_m5_candidate_analysis.json`, `experiments/next_bar/rolling_transition_memory_m5_confidence_subgroups.json`, `experiments/next_bar/rolling_transition_memory_vs_*_m5_*`
- fixed diversification: `experiments/next_bar/profile_transition_memory_equal_m5_confidence_fixed_001`, `experiments/next_bar/pressure_transition_memory_equal_m5_direction_fixed_001`
- feature/test: `src/trade_data/next_bar.py`, `tests/test_next_bar.py`
