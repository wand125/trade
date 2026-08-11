# 00104 M1 Path × Distribution Shift Pairwise Correctness Gate

日時: 2026-08-11 11:26 JST

## 目的

新しい特徴モデルを増やす代わりに、既存M1方向候補の誤りを直接学習する残差フローを検証した。point accuracy championのPath Persistenceとstability/proper-score候補のDistribution Shiftが反対方向を出した行だけで、各評価foldより前のOOS正誤から「Pathが正しい確率」を学び、現在行でPath/Shiftのどちらを採るか決める。

これは全候補から方向確率を再学習するchronological stackingや、volatility regime単位で候補を選ぶrouterとは異なる。合意行はPathを維持し、不一致行だけをrow-levelで切り替える。

## 固定仕様と品質

Path/Shiftの通常25%方向blendは同じbaseline 75%を共有する。2,183,717行をfold/timestampのone-to-oneで結合し、decision/target timestamp、target、baseline probability、volatility regime/valueが完全一致することを要求した。不一致は96,591行、全体の4.4232%だった。

入力は判定時点で利用可能な固定15列である。

- baseline、Path candidate、Shift candidateのlogit
- Path/Shift blendの絶対edge、candidate probability差、Path方向
- volatility 20とlow/normal/high one-hot
- UTC時刻・曜日のsin/cos

target、correct、未来足値は特徴へ入れない。当初含めたblend probability差はcandidate差の厳密な定数倍だったため、最終判定前の品質監査で完全共線列として除外し、最終artifactを再生成した。

学習器は標準化Logistic Regression、C=0.10、seed 42、選択閾値0.5に固定した。各test foldではそれ以前のOOS不一致行だけをfitする。prior OOSのないtest2020はPath固定fallback、test2021〜2026_partialだけが学習gateである。C、特徴subset、閾値のgrid searchは行っていない。損失倍率は標準1.0のみである。

future foldのtargetを反転しても同foldのgate probabilityが変わらないこと、source target不一致を拒否すること、最初のfoldがPathと一致することをテストした。

## 方向結果

| period | Path | pairwise gate | 差 |
|---|---:|---:|---:|
| development | 50.97889% | 50.98807% | +123件 |
| confirmation | 50.64573% | 50.64478% | -8件 |
| all | 50.85009% | 50.85535% | +115件 |

Path比accuracyは4勝2敗1分、Brier/log lossは3/7fold改善だった。all exact pairedはfix 16,599、harm 16,484、p=0.53082である。UTC日paired bootstrap 20,000回のall accuracy差95%区間は-0.01136〜+0.02181pt、Brier/log lossも0を跨いだ。developmentの+123件はconfirmationで-8件へ反転し、Pathを置換する根拠にならない。

Distribution Shiftとの比較ではgateがdevelopment +194件、confirmation +4件、all +198件、accuracy 4勝3敗だった。しかしall accuracy差95%区間は-0.01287〜+0.03104ptで未確定である。Brier差95%区間は+0.00000412〜+0.00000963、log loss差は+0.00000828〜+0.00001931で、development/confirmation/allすべてDistribution Shift優位が確定した。方向point差が未確定なまま確率品質を明確に失う。

## 不一致残差とconfidence

test2020 fallbackを除く学習gate対象83,639不一致行を期間分離した。

| period | rows | Path accuracy | gate accuracy | gate choice mean confidence |
|---|---:|---:|---:|---:|
| development test2021〜2023 | 45,893 | 50.0251% | 50.2931% | 50.7808% |
| confirmation test2024〜2026_partial | 37,746 | 50.0159% | 49.9947% | 50.5931% |
| all learned | 83,639 | 50.0209% | 50.1584% | 50.6961% |

開発期には小さな残差信号があったが、確認期ではchance未満へ消失した。確認期でgate choice confidence 0.51以上は6,227件、0.52以上は247件しかなく、信頼度を上げても安定したcandidate選択edgeにならない。

最終方向確率のdevelopment選択confidenceは0.51だったが、Pathとほぼ同一だった。gateはdevelopment 51.6520% / coverage 43.7499% / score 0.010081、confirmation 51.7075% / 23.9426% / 0.007289である。Path比はconfirmationでaccuracyとscoreが僅かに悪化し、0.525以上は完全一致する。独立したconfidence ranking情報は得られなかった。

## 判断

M1 Path × Distribution Shift pairwise correctness gateを再現専用として棄却する。残差分類は開発期にPathを上積みし、全期間point accuracyもPath/Shiftを僅かに上回ったが、confirmationへ移らず統計区間も未確定だった。Distribution Shiftよりproper scoreを明確に悪化させ、不一致gate confidenceも確認期でchance未満である。

Pathをdirection point champion、Distribution Shiftをstability/proper-score方向候補として独立維持する。pairwise gateのC、時刻/volatility特徴、candidate subset、選択閾値、hard/soft gateを同じ履歴で再探索しない。config、registry、authoritative方向/confidence、fair odds、paper/live policyを変更しない。保存したfinal modelはresearch-onlyでruntime latestを発行しない。

## 成果物

- implementation: `src/trade_data/next_bar_pairwise_gate.py`
- CLI: `methods/next_bar/scripts/pairwise_correctness_gate.py`
- OOS/models/metrics: `experiments/next_bar/path_shift_pairwise_gate_m1_fixed_001`
- candidate analysis: `experiments/next_bar/path_shift_pairwise_gate_m1_candidate_analysis.json`
- Path comparison: `experiments/next_bar/path_shift_pairwise_gate_vs_path_m1_direction_analysis.json`, `experiments/next_bar/path_shift_pairwise_gate_vs_path_m1_direction_bootstrap.json`
- Distribution Shift comparison: `experiments/next_bar/path_shift_pairwise_gate_vs_distribution_shift_m1_direction_analysis.json`, `experiments/next_bar/path_shift_pairwise_gate_vs_distribution_shift_m1_direction_bootstrap.json`
