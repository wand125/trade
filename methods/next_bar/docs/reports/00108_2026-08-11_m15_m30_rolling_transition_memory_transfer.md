# 00108 M15/M30 Rolling Transition Memory固定移植

日時: 2026-08-11 14:05 JST

## 目的

M1で固定し、M5では既存候補を超えなかったRolling Transition Memoryを、同じ仕様のままM15/M30へ移植した。時間足ごとの再探索は行わず、局所的な状態遷移加工がより長い時間足でも方向精度またはconfidenceの増分edgeを持つかを確認した。

## 固定条件と品質

window 32/128、return方向・body/range 0.5・close上下半分・prior 20本range中央値の4 bit/16状態、global shrinkage strength 8、9特徴、HGB/Platt、通常/方向維持25% blendをM1仕様から変更していない。損失倍率は標準1.0のみである。

正式baselineと同じtest2020〜test2026途中の固定7foldを使い、M15 145,140行、M30 71,260行のOOS予測を生成した。fold、timestamp、decision/target timestamp、targetは完全一致した。特徴は各時間足の完成足だけから作り、未来不参照、timestamp gap reset、確率和1、confidenceとclass confidenceの整合を成果物で確認した。

## M15方向

| candidate | development accuracy | confirmation accuracy | all accuracy | all Brier |
|---|---:|---:|---:|---:|
| baseline | 52.01441% | 51.50115% | 51.81618% | 0.249426100 |
| Memory単体 | 52.07728% | 51.52077% | 51.86234% | 0.249438110 |
| baseline 75% + Memory 25% | 52.02788% | 51.41196% | 51.79000% | 0.249409080 |

単体はbaseline比development +56件、confirmation +11件、all +67件、accuracy 5/7foldだった。しかしall accuracy差+0.04616ptの日次bootstrap 95%区間は-0.11472〜+0.21020ptで、方向改善は未確定だった。all Brier/log lossはbaselineより悪く、proper score改善は2/7foldに留まった。通常25% blendはall -38件、confirmation -50件、accuracy 3/7fold、exact paired p=0.5447で棄却する。

既存Intrabar Pressure 25%はall accuracy 51.87612%、Brier 0.249383440で、Memory単体の51.86234%、0.249438110を上回った。Memoryは年別accuracy 4/7対3/7でも、confirmation accuracy、all accuracy、development/confirmation/allのBrier・log loss・ECEがすべてPressureより悪く、方向候補を置換しない。Volatility Shape 25%にはMemoryが点accuracyで5/7勝ったが、all差は+0.02067ptに過ぎず、proper scoreはShapeが明確に良い。既存役割を増やすほどの一貫した品質差ではない。

## M15 confidenceと固定多様化

developmentの既定gridでMemoryの最大selection scoreは0.525だった。

| period | candidate | accuracy | coverage | selection score |
|---|---|---:|---:|---:|
| development | Memory 0.525 | 53.99338% | 37.3023% | 0.021114 |
| confirmation | Memory 0.525 | 53.75341% | 26.1876% | 0.015076 |
| all | Memory 0.525 | 53.91985% | 33.0095% | 0.019955 |
| all | Signed-body Quantile 0.525 | 54.08028% | 33.3664% | 0.021004 |

Memoryはbaseline比developmentでaccuracyとscoreを上げたが、confirmationではaccuracy・coverage・scoreがすべて反転した。既存Signed-body Quantileにdevelopment、confirmation、allのaccuracy・coverage・score・proper scoreで負け、年別accuracy/scoreも2/7対5/7だった。

両候補を固定50/50平均してもall accuracy 54.01492%、coverage 33.1632%、score 0.020555となり、Signed-body Quantile単独の54.08028%、33.3664%、0.021004を下回った。単独が年別accuracy/score 5/7で勝ち、Memory追加は採用しない。0.54〜0.55でもMemoryは既存Intrabar Structure 0.55、Body/ATR系0.54のprecision候補を超えなかった。

## M30方向と通常confidence

| candidate | development accuracy | confirmation accuracy | all accuracy | all Brier |
|---|---:|---:|---:|---:|
| baseline | 51.98972% | 51.52019% | 51.80747% | 0.249497879 |
| Memory単体 | 51.58605% | 51.49850% | 51.55206% | 0.249500564 |
| baseline 75% + Memory 25% | 51.88651% | 51.49488% | 51.73449% | 0.249472303 |

単体はdevelopmentで-176件、exact paired p=0.0272と有意に悪化し、allも-182件だった。通常25% blendもall -52件、accuracy 3/7fold、p=0.2821で棄却する。

方向維持Memoryのdevelopment grid最良は0.515だったが、baselineに対してdevelopment、confirmation、allのaccuracy・coverage・scoreがすべて低下した。固定0.52では既存Intrabar Pressureのall accuracy 53.75769%、coverage 36.4861%、score 0.019034に対しMemoryは53.59641%、36.3079%、0.018006だった。

PressureとMemoryの固定50/50平均もall accuracy 53.53387%、coverage 36.2953%、score 0.017625で、Pressure単独より全指標が低かった。年別accuracy/scoreはPressureが7/7で勝ち、Memoryは多様化要員にも採用しない。

## M30高信頼度tail

Memory 0.575はdevelopment 873件・56.3574%、confirmation 117件・67.5214%、all 990件・57.6768%、coverage 1.3893%だった。baselineはall 1,114件・57.1813%、Pressureは936件・57.2650%であり、Memoryの点精度は高く見えた。

しかしMemory−baselineのall accuracy差+0.49544ptの日次bootstrap 95%区間は-0.86594〜+1.84542pt、selection score差区間も-0.001585〜+0.001697で0を跨いだ。Memory−Pressureもaccuracy差+0.41181ptの区間は-1.18462〜+1.99806pt、score差区間は-0.001145〜+0.002569だった。test2020はMemory 21件・47.6190%、test2023/2024は0件で、fold scoreはbaselineに1勝4敗2分だった。all mean confidence 59.0096%に対してaccuracy 57.6768%と約1.33pt過信でもある。

0.60以上はMemory all 186件、confirmation 9件に過ぎない。confirmationの高い点accuracyを継続的edgeまたはfair oddsと解釈せず、precision候補、odds、policyへ使わない。

## 判断

固定Transition MemoryはM15単体方向でbaselineを僅かに上回り、M30 0.575の薄いtailでも高い点精度を示した。しかしM15方向差は日次区間が0を跨ぎproper scoreが悪化し、既存Pressureを超えない。M15 0.525、M30 0.515/0.52、固定50/50多様化はいずれも既存候補へ負けた。M30 0.575は990件、年別空fold、過信、広い区間のため品質条件を満たさない。

したがってM15/M30でも研究再現専用とする。window、state bit、range基準、prior strength、blend weight、confidence thresholdを同じ履歴で再探索しない。M15の既存Pressure/Volatility Shape方向とSigned-body Quantile等のconfidence、M30 Pressure 0.52を維持し、config、registry、authoritative方向/confidence、fair odds、adoption/paper/live policy、runtime latestを変更しない。

## 成果物

- OOS: `experiments/next_bar/walk_forward_rolling_transition_memory_m15_m30_fixed_001`
- baseline blends: `experiments/next_bar/rolling_transition_memory_m15_*_fixed_001`, `experiments/next_bar/rolling_transition_memory_m30_*_fixed_001`
- analysis/subgroups: `experiments/next_bar/rolling_transition_memory_m15_candidate_analysis.json`, `experiments/next_bar/rolling_transition_memory_m30_candidate_analysis.json`, `experiments/next_bar/rolling_transition_memory_m15_confidence_subgroups.json`, `experiments/next_bar/rolling_transition_memory_m30_confidence_subgroups.json`
- direct/bootstrap: `experiments/next_bar/rolling_transition_memory_vs_*_m15_*`, `experiments/next_bar/rolling_transition_memory_vs_*_m30_*`
- fixed diversification: `experiments/next_bar/signed_body_quantile_transition_memory_equal_m15_confidence_fixed_001`, `experiments/next_bar/pressure_transition_memory_equal_m30_confidence_fixed_001`
