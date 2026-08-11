# 00109 M15/M30 Prequential Selective Correctness

日時: 2026-08-11 15:10 JST

## 目的

既存方向予測を作り直さず、「この予測を採用するか」だけを独立学習する選択・棄権モデルを検証した。M15/M30を別々に学習し、現在の基準confidence候補、baseline、Volatility Shape、Intrabar ProfileのOOS確率から、基準方向が正解する確率を推定した。

## 固定仕様と未来非参照

各時間足で次の情報を基準方向へ向けた符号付きedgeへ加工した。

- baseline、基準candidate、Shape candidate、Profile candidateの確率edge
- 基準・Shape・Profileの方向維持blend edge
- candidate edgeのmean/min/max/std、一致率、基準対peer差、Shape対Profile差
- 現在足body ratio、20本volatility、予測方向
- UTC時刻・曜日のsin/cos、volatility regime 3区分

固定24特徴、StandardScaler + Logistic Regression C=0.10、標準損失のみを使った。target、correct、次足bodyは特徴に含めない。M15はSigned-body Quantile方向維持候補を基準、M30はIntrabar Pressure方向維持候補を基準とした。

test2020は過去OOSがないため元confidenceへfallbackし、閾値選択とnested評価から除外した。test2021はtest2020だけ、test2022はtest2020〜2021だけというように、各test foldより前のOOS正誤だけでfitした。閾値grid 0.50/0.505/0.51/0.515/0.52/0.525/0.53/0.54/0.55/0.575/0.60を固定し、test2021〜2023のselection score最大を選び、test2024〜2026途中をconfirmationとした。

元方向を変えずに正解確率を方向確率へ戻す。正解確率0.5未満は棄権値へ丸めるが、初回成果物監査でdown側のちょうど0.5が確率tie規則ではupになる不整合を検出した。0.5±machine epsilonで元方向を厳密維持するよう修正し、成果物を全再生成した。修正後は`predicted_up == probability_up >= 0.5`、確率和1、`confidence == max(probability)`、target/時刻整列を確認した。初回数値は採否に使っていない。

## M15の主目的

developmentで選ばれた閾値は0.53だった。比較対象は固定Signed-body Quantile 0.525である。

| period | candidate | accuracy | coverage | selection score |
|---|---|---:|---:|---:|
| nested development | Selective 0.53 | 53.44736% | 34.1614% | 0.016337 |
| nested development | Signed Quantile 0.525 | 53.53280% | 37.8887% | 0.017935 |
| confirmation | Selective 0.53 | 54.10875% | 18.8647% | 0.013715 |
| confirmation | Signed Quantile 0.525 | 54.08631% | 26.4552% | 0.016888 |
| all nested | Selective 0.53 | 53.65876% | 27.1300% | 0.016256 |
| all nested | Signed Quantile 0.525 | 53.73907% | 32.6330% | 0.018559 |

confirmation点accuracyは+0.0224ptだが、coverage -7.5905pt、score -0.003173である。年別accuracyはSelective 4/6でもselection scoreは1/6、proper scoreはnested development、confirmation、all nestedで基準より悪化した。主目的候補として棄却する。

## M15 0.55 precision tail

既存Intrabar Structure 0.55と比較した。

| period | Selective accuracy / coverage / score | Structure accuracy / coverage / score |
|---|---:|---:|
| development | 55.1017% / 14.4012% / 0.016089 | 55.9336% / 10.8876% / 0.016311 |
| confirmation | 56.7568% / 3.6962% / 0.008869 | 56.4368% / 3.1040% / 0.007215 |
| all | 55.3319% / 10.2666% / 0.014522 | 56.0101% / 7.8814% / 0.014314 |

confirmationの点scoreは高いが、accuracy差+0.3200ptのUTC日bootstrap 95%区間は-1.5681〜+2.1941pt、score差区間も-0.001802〜+0.005081で未確定だった。development accuracy差-0.8319ptの区間は-1.5360〜-0.1207pt、all差-0.6783ptの区間も-1.3312〜-0.0080ptで既存Structure優位だった。Brier/log lossはdevelopmentとallでSelectiveの悪化が確定した。

Selective 0.55のnested development accuracy 54.2982%に対しmean confidenceは58.3140%で約4.02pt過信し、confirmationはaccuracy 56.7568%に対し55.9638%と過小評価へ反転した。precision role、fair oddsへ採用しない。

## M30の主目的

developmentのselection score最大は0.50、すなわち全件採用だった。選択モデルとして識別できていない。

| period | Selective 0.50 accuracy / coverage / score | Pressure 0.52 accuracy / coverage / score |
|---|---:|---:|
| nested development | 51.8538% / 100.0000% / 0.013077 | 53.2463% / 43.3198% / 0.015909 |
| confirmation | 51.5202% / 100.0000% / 0.009311 | 53.7345% / 30.6388% / 0.014787 |
| all nested | 51.6996% / 100.0000% / 0.012991 | 53.4309% / 37.4578% / 0.016998 |

accuracyは同じ基準方向の全件精度であり、候補の識別品質を示さない。年別accuracy 0/6、selection score 1/6でPressure 0.52を下回り、主目的候補として棄却する。

## M30 0.55 precision tail

| period | Selective accuracy / coverage / score | Pressure accuracy / coverage / score |
|---|---:|---:|
| development | 54.0673% / 16.8330% / 0.012002 | 56.0918% / 7.7938% / 0.012332 |
| confirmation | 57.9161% / 2.6716% / 0.007069 | 55.5944% / 3.1018% / 0.003966 |
| all | 54.4194% / 11.3360% / 0.011217 | 55.9915% / 5.9725% / 0.010986 |

confirmation点accuracy差+2.3217ptは魅力的に見えるが、日次95%区間は-0.6064〜+5.2165pt、score差区間も-0.001834〜+0.007974で0を跨いだ。development accuracy差-2.0245ptの区間は-3.3135〜-0.7501pt、all差-1.5721ptの区間は-2.7533〜-0.4030ptで、既存Pressure優位が確定した。Brier/log lossもdevelopment/allでSelectiveが有意に悪い。

nested developmentではaccuracy 53.6796%に対してmean confidence 58.2626%と約4.58pt過信し、confirmationでは57.9161%対55.8859%と約2.03pt過小評価へ反転した。期間移行で信頼度の意味が変わっており、precision role、fair oddsへ採用しない。

## 判断

過去OOSだけから正解確率を学ぶ流れ自体は、方向非変更、予測確率と信頼度の同一化、未来非参照を保って実装できた。しかし最初の学習foldではM15 ECE 2.55%、M30 ECE 3.18%まで不安定になり、後続foldでも確率rangeと平均値が大きく変化した。M15 0.53とM30 0.50は既存候補のselection scoreをdevelopment/confirmationとも下回る。0.55 tailのconfirmation点改善も日次区間が0を跨ぎ、development/all accuracyとproper scoreが悪化した。

したがってPrequential Selective CorrectnessはM15/M30とも研究再現専用として棄却する。特徴subset、C、学習window、minimum prior folds、threshold、モデル種別を同じOOS履歴で再探索しない。config、registry、authoritative confidence、fair odds、adoption/paper/live policy、runtime artifactを変更しない。

## 成果物

- implementation: `src/trade_data/next_bar_selective_correctness.py`
- CLI: `methods/next_bar/scripts/selective_correctness.py`
- tests: `tests/test_next_bar_selective_correctness.py`
- OOS/model/report: `experiments/next_bar/selective_correctness_m15_fixed_001`, `experiments/next_bar/selective_correctness_m30_fixed_001`
- direct/bootstrap: `experiments/next_bar/selective_correctness_vs_structure_m15_055_*`, `experiments/next_bar/selective_correctness_vs_pressure_m30_055_*`
