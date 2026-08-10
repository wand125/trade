# 00032 Model-disagreement confidence ensemble

日時: 2026-08-10 13:15 JST

## 目的

異なる加工法・教師・学習器が同じ方向へ出す確率を集約し、モデル間の一致をconfidenceへ変換できるか確認する。単一モデルの履歴値を直接使うのではなく、複数モデルのbaseline方向に沿った確率edgeの平均と分散へ加工する。

## 固定した入力

同じ145,140行・M15 2020〜2026途中の7 OOS foldに完全整列する次の5モデルを使った。

1. baseline binary HGB
2. clear-body-filtered binary HGB
3. Extra Trees classifier
4. signed-body HGB regressor
5. intrabar-structure binary HGB

モデルやfoldごとの再学習・重み探索は行わず、全モデルを等重みとした。実装は `src/trade_data/next_bar_disagreement.py`、CLIは `methods/next_bar/scripts/disagreement_ensemble.py`、共通比較器は `methods/next_bar/scripts/analyze_candidate.py` である。

## 事前の主要仮説: 1 sigma lower bound

baseline予測方向を符号 `s`、各モデル確率を `p_i` とし、baseline方向へ揃えたedgeを `e_i = s * (p_i - 0.5)` とした。主要仮説ではconfidence edgeを次で定義した。

`max(mean(e_i) - population_std(e_i), epsilon)`

方向はbaselineに固定する。この1 sigma版は不一致を強く罰し、全体confidence 0.515 laneのscoreはbaselineとほぼ同じだったが、developmentでは0.02048から0.02011へ悪化した。proper scoreのfold改善もBrier 3/7、log loss 3/7、ECE 2/7であり棄却する。

## 等重み確率平均の方向評価

方向を固定しない単純平均は、developmentでは方向accuracyを52.014%から52.105%へ改善したが、confirmationでは51.501%から51.490%へ6件悪化した。全体では51.816%から51.868%へ改善したものの、誤り修正5,984件、新規誤り5,909件、McNemar exact p=0.497で、独立した方向edgeとは判断できない。

一方、確率品質はdevelopmentとconfirmationの両方で改善した。

| period | metric | baseline | equal mean |
|---|---|---:|---:|
| development | Brier | 0.2493466 | 0.2492151 |
| development | log loss | 0.6918398 | 0.6915741 |
| development | ECE | 0.377% | 0.055% |
| confirmation | Brier | 0.2495525 | 0.2495369 |
| confirmation | log loss | 0.6922506 | 0.6922194 |
| confirmation | ECE | 0.298% | 0.103% |

したがって平均は方向置換ではなく、confidence加工としてのみ調べる価値がある。

## 構造ablation: 平均edge + baseline方向固定

1 sigmaが過剰にcoverageを落としていたため、結果確認後の構造診断として標準偏差罰則を0へ固定した。confidence edgeは `max(mean(e_i), epsilon)` とし、平均がbaselineを否定する行はbaseline側0.50直上まで落とす。この比較は事後ablationであり、良い結果でもforward採用根拠にはしない。

方向accuracyはbaselineと完全に同じで、確率品質は次の通りだった。

| period | metric | baseline | direction-preserved mean |
|---|---|---:|---:|
| development | Brier | 0.2493466 | 0.2492138 |
| development | log loss | 0.6918398 | 0.6915714 |
| development | ECE | 0.377% | 0.005% |
| confirmation | Brier | 0.2495525 | 0.2495361 |
| confirmation | log loss | 0.6922506 | 0.6922178 |
| confirmation | ECE | 0.298% | 0.068% |
| all | Brier | 0.2494261 | 0.2493383 |
| all | log loss | 0.6919985 | 0.6918211 |
| all | ECE | 0.347% | 0.030% |

Brier/log lossは6/7 fold、ECEは3/7 foldで改善した。ECEの合算改善は大きいが、年別安定性はまだ不足する。

## developmentで選んだconfidence 0.515 lane

| period | model | rows | coverage | accuracy | selection score |
|---|---|---:|---:|---:|---:|
| development | baseline | 52,243 | 58.645% | 53.102% | 0.02048 |
| development | disagreement | 45,892 | 51.516% | 53.561% | 0.02228 |
| confirmation | baseline | 27,681 | 49.380% | 52.574% | 0.01395 |
| confirmation | disagreement | 24,567 | 43.825% | 52.766% | 0.01418 |
| all | baseline | 79,924 | 55.067% | 52.919% | 0.01909 |
| all | disagreement | 70,459 | 48.546% | 53.283% | 0.02031 |

accuracyは6/7 fold、selection scoreは5/7 foldで改善した。2026途中ではaccuracy 53.270%から53.153%、score 0.01499から0.01375へ悪化した。

## 既存候補との比較

clear-body HGB confidence 0.525はconfirmation coverage 24.714%、accuracy 54.201%、selection score 0.01675であり、今回の0.515 laneの43.825%、52.766%、0.01418を目的関数で上回る。今回の方式はcoverage用途が異なるものの、既存のsigned-body 0.52広coverage候補のconfirmation score 0.01580にも届かない。

## 判断

- 1 sigma lower boundは棄却する。モデル分散をそのまま1倍罰する方式はこの予測集合では過剰だった。
- 等重み平均による方向置換は棄却する。confirmationの純改善とpaired testが不十分である。
- 平均edge + baseline方向固定の0.515は、確率校正と広い選別laneの研究shadowとして固定する。
- `config/m15_disagreement_confidence_shadow_v1.json` に再現条件を保存するが、今回の0 penaltyは事後ablationなのでforward候補へは昇格しない。
- authoritative confidence、fair odds、現行採用policy、paper policyは変更しない。完全未使用期間では固定0.515のaccuracy、coverage、selection score、Brier/log loss/ECEを追跡する。
- 同じ履歴でモデル部分集合、等重み以外のweight、penalty、閾値を再探索しない。損失倍率は標準1.0のみとする。
