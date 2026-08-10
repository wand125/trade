# 00087 M1 Disagreement Chronological Odds Recalibration

日時: 2026-08-11 JST

## 目的

採用したM1 Five-model Disagreement confidenceを、予測方向が正しい確率としてさらに再校正できるか検証した。現在foldの正解は使わず、各評価foldより前の全OOSだけで `confidence -> correct` を学ぶisotonic regressionとglobal correctness Plattを比較した。

## 方法と品質

test2020はprior OOSがないため除外し、test2021〜2026途中のnested 1,838,693行を評価した。isotonicは単調 `[0,1]`、範囲外clip、Plattはconfidence 1変数のunregularized相当logistic regressionである。方向と元の正誤列は変更しない。

再校正器がcurrent/future foldの正解を参照しない因果性は既存テストで確認済みである。今回、開発・確認・all nestedの固定0.515 accuracy、coverage、Wilson下限、selection scoreを共通出力へ追加した。さらにcorrectness確率をUTC日単位でpaired bootstrapできる経路、選択行0件を未定義として安全に報告する経路、manifestの任意予測filenameを読む経路、任意confidence列の固定subgroup監査を追加した。

## 全nested確率品質

| method | mean confidence | Brier | log loss | ECE |
|---|---:|---:|---:|---:|
| raw Disagreement | 50.8134% | 0.24989796 | 0.69294306 | 0.1463% |
| chronological isotonic | 50.6503% | 0.24990383 | 0.69295481 | 0.0260% |
| chronological Platt | 50.8942% | 0.24994465 | 0.69303648 | 0.2328% |

isotonicはECEを改善するが、Brier/log lossは6/6評価foldでrawより悪化した。PlattはBrier/log lossを1/6foldだけ改善し、合算3指標も悪化した。平均的な実績水準へ寄せるだけでは年次shiftを追えない。

## 固定0.515 lane

| period | method | coverage | accuracy | selection score |
|---|---|---:|---:|---:|
| nested development | raw | 20.350% | 51.778% | 0.007040 |
| nested development | isotonic | 11.429% | 52.124% | 0.006198 |
| nested development | Platt | 14.361% | 51.846% | 0.006015 |
| confirmation | raw | 8.759% | 53.031% | 0.007904 |
| confirmation | isotonic | 4.550% | 53.835% | 0.007115 |
| confirmation | Platt | 0.000% | - | - |
| all nested | raw | 15.028% | 52.114% | 0.007471 |
| all nested | isotonic | 8.271% | 52.556% | 0.006629 |
| all nested | Platt | 7.767% | 51.846% | 0.004424 |

isotonicは高い点accuracyと引き換えにcoverageをall nestedで-6.757pt、confirmationで-4.209pt失った。selection scoreは6fold中test2021だけrawを上回り、残り5foldはrawが勝った。Plattはtest2023以降の4fold、つまりconfirmation全体で0.515以上を1件も出さず、採用laneとして機能しない。

UTC日paired bootstrap 20,000回ではisotonic−rawのselection score差95%区間がnested development -0.001547〜-0.000138、confirmation -0.001572〜-0.000007、all -0.001360〜-0.000324だった。all Brier差は+0.00000202〜+0.00000969、log loss差は+0.00000405〜+0.00001940で、いずれもrawより悪い。Plattのall score差は-0.003605〜-0.002494、Brier/log lossも明確に悪化した。

## 固定6セル

isotonic 0.515のconfirmationでもdown-normal 758行はaccuracy 50.000%、up-low 580行は49.310%でWilson edgeを通らず、rawで弱かった局所セルを解消しなかった。down-lowは98行・53.061%でもsupport不足である。up/down × low/normal/highから事後filterは作らない。

## 判断

isotonicとcorrectness Plattをともに棄却する。isotonicのECE改善だけを理由にオッズ写像へ採用すると、proper scoreとcoverage-aware目的関数を悪化させる。Plattはconfirmation 0.515 laneを消失させる。

`m1_disagreement_confidence_candidate_v1.json` の元equal-mean confidenceを維持する。authoritative fair odds、売買policy、採用閾値は変更しない。完全未使用期間で元confidenceのglobal/local整合が確認できるまでオッズ認可しない。同じ履歴でisotonic smoothing、Platt regularization、rolling期間、別の写像、閾値を再探索しない。

## 成果物

- recalibration predictions/report: `experiments/next_bar/disagreement_m1_chronological_odds_recalibration_001`
- isotonic fixed subgroups: `experiments/next_bar/disagreement_m1_isotonic_confidence_subgroups.json`
- Platt fixed subgroups: `experiments/next_bar/disagreement_m1_platt_confidence_subgroups.json`
- implementation: `src/trade_data/next_bar_odds_recalibration.py`
- CLI: `methods/next_bar/scripts/chronological_odds_recalibration.py`
