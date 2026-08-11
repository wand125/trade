# 00120 M30 Directional-Clarity Sample Weighting

日時: 2026-08-11 16:13 JST

## 目的

M1で通常25% blendがaccuracy・Brier・log lossを7/7fold改善した教師品質加工をM30へ固定移植した。曖昧な足を捨てず、明瞭な次足ほど過去教師として重く扱う学習フローが、M30の方向候補または信頼度へ独立した増分を持つか検証した。

## 固定仕様と品質

trainで解決済みの次足について `directional_clarity = abs(next close - next open) / (next high - next low)` を0〜1へ制限し、raw weightを `0.5 + directional_clarity` とした。重み範囲0.5〜1.5、最大比3倍で、sampled train内の平均1へ正規化する。次足range/bodyはtrain sample weightだけへ使い、特徴、calibration、test入力、latest推論へ渡さない。

baseline 38加工特徴、HGB 200 iteration、31 leaves、learning rate 0.05、min leaf 100、L2 1、seed 42、expanding、最大train 750,000行、全教師、Platt、標準損失1.0を固定した。M1からweight式、model parameter、25% weight、confidence grid `0.51,0.515,0.525,0.535,0.55` を変更していない。

test2020〜test2026途中の7fold、71,260 OOS行をbaseline・既存候補とtimestamp/targetで完全整列した。最終fold artifactから2026-06-01 04:30 UTCを再推論し、up、probability up 53.4110%を確認した。経験的オッズ検証はないため `odds_valid=false` である。

## 単体と通常方向blend

| model | development accuracy | confirmation accuracy | all accuracy | all Brier | all log loss | all ECE |
|---|---:|---:|---:|---:|---:|---:|
| HGB baseline | 51.9897% | 51.5202% | 51.8075% | 0.249497879 | 0.692142533 | 0.1608% |
| Clarity weighted単体 | 52.1411% | 51.7986% | 52.0081% | 0.249419982 | 0.691985814 | 0.2351% |
| baseline 75% + Clarity 25% | 52.0517% | 51.5383% | 51.8524% | 0.249447647 | 0.692041674 | 0.1479% |

単体はbaseline比development +66件、confirmation +77件、all +143件だったが、accuracy/Brier/log loss/ECEは各4/7fold、McNemar exact p=0.1423だった。日次bootstrap 20,000回のall accuracy差+0.2007ptの95%区間は-0.0673〜+0.4725pt、Brier差区間-0.00016956〜+0.00001349、log loss差-0.00034151〜+0.00002727で、いずれも0を跨いだ。

通常25% blendは+27/+5/+32件、accuracy 4/7foldだった。Brier/log lossは6/7fold改善し、日次bootstrapもdevelopment/allのproper score改善を支持したが、all accuracy差+0.0449ptの区間は-0.0915〜+0.1849ptだった。方向edgeとしては弱い。

現行Haar入り方向co-challengerとの直接比較では、単体がdevelopment 52.1411%対52.1939%、confirmation 51.7986%対51.6756%、all 52.0081%対51.9927%だった。件数差は-23/+34/+11、年別accuracyは3/7対4/7、all accuracy差区間は-0.2471〜+0.2741ptであり、置換根拠はない。Extra Trees単体にはaccuracy 4/7で全体+71件だったが、Brier/log lossはExtra Treesが良く、standalone probability-quality役割も置換しない。

## 固定方向多様化

現行Haar入り候補とClarity単体の確率を固定50/50平均した。

| model | development accuracy | confirmation accuracy | all accuracy | all Brier | all log loss | all ECE |
|---|---:|---:|---:|---:|---:|---:|
| Haar入り現行候補 | 52.1939% | 51.6756% | 51.9927% | 0.249427476 | 0.692000846 | 0.0729% |
| Haar + Clarity固定平均 | 52.2328% | 51.7154% | 52.0320% | 0.249387573 | 0.691920731 | 0.0195% |

固定平均はbaseline比development +106件、confirmation +54件、all +160件、accuracy 5/7foldだった。baseline比日次bootstrapではdevelopment/allのBrier/log loss改善を支持し、all accuracy差+0.2245ptの区間は-0.0042〜+0.4496ptと僅かに0を跨いだ。

親候補比では+17/+11/+28件でも年別accuracyは3/7対4/7だった。all accuracy差+0.0393ptの区間は-0.1441〜+0.2253pt、Brier差区間は-0.00008247〜+0.00000279、log loss差は-0.00016571〜+0.00000576で、親への増分を確定できない。baseline改善を既存候補へ重複して説明する新candidateは発行しない。

## confidence

development gridのselection score最大は0.51だった。

| period | baseline coverage / accuracy / score | Clarity coverage / accuracy / score |
|---|---:|---:|
| development | 67.0979% / 52.6014% / 0.016619 | 68.1598% / 52.7106% / 0.017689 |
| confirmation | 58.9711% / 52.4461% / 0.012895 | 59.5785% / 52.4090% / 0.012705 |
| all | 63.9433% / 52.5458% / 0.016689 | 64.8288% / 52.6030% / 0.017290 |

allではcoverage +0.8855pt、accuracy +0.0572pt、score +0.000601で、Brier/log loss/ECEも6/7fold改善した。しかしconfirmationのaccuracy -0.0371pt、score -0.000190へ反転した。日次区間で確定したのはcoverageとdevelopment/all proper scoreだけで、accuracy/score区間は0を跨いだ。

Pressure 0.52との比較ではClarity 0.51がall coverage 64.8288%対36.4861%と広い一方、accuracy 52.6030%対53.7577%、score 0.017290対0.019034だった。accuracy 0/7、score 1/7であり、broad confidence役割へ追加しない。

Clarity 0.55は4,921件、coverage 6.9057%、accuracy 55.8220%、score 0.011643だった。Pressure + AR 0.55は4,412件、6.1914%、56.1423%、0.011629で、Clarityはdevelopment score -0.000320、confirmation +0.000840、all +0.000014、年別accuracy 3/7、score 4/7だった。直接bootstrapではcoverage増加だけが確定し、accuracy・score・proper score差は全期間区分で0を跨いだ。

PressureとClarity confidenceの固定50/50平均は0.52でPressureにaccuracy 1/7、score 2/7だった。0.55ではall coverage 6.3837%、accuracy 56.1002%、score 0.011758でも、confirmation scoreが0.004427対0.004997へ悪化し、年別accuracy/score各2/7だった。日次bootstrapもcoverage増加以外を支持せず、固定平均を採用しない。

## 判断

Clarity weighted単体、通常25%方向blend、方向維持0.51/0.55、Pressureとの固定50/50 confidence平均を再現専用とする。Haar入り候補との固定50/50方向平均はbaselineに対する有効な教師品質感度として保存するが、親候補へのincremental edgeが年別3/7で不確定なため新しい方向candidateへ追加しない。

weight式、feature、model parameter、blend weight、thresholdを同じ履歴へ合わせて再探索しない。config、registry、authoritative方向/confidence、現行Haar入り方向co-challenger、Pressure 0.52、Pressure + AR 0.55 shadow、fair odds、adoption/paper/live policyは変更しない。

## 成果物

- Clarity OOS: `experiments/next_bar/walk_forward_directional_clarity_weighted_m30_fixed_001`
- normal/confidence blends: `experiments/next_bar/directional_clarity_weighted_m30_*_fixed_001`
- candidate分析: `experiments/next_bar/directional_clarity_weighted_m30_candidate_analysis.json`
- baseline/既存候補比較: `experiments/next_bar/directional_clarity_weighted*_vs_*_m30_*`
- rejected direction average: `experiments/next_bar/haar_directional_clarity_equal_m30_direction_fixed_001`
- direction average comparison/bootstrap: `experiments/next_bar/haar_directional_clarity_equal_vs_*`
- rejected confidence average: `experiments/next_bar/pressure_directional_clarity_equal_m30_confidence_fixed_001`
- confidence average comparison/bootstrap: `experiments/next_bar/pressure_directional_clarity_equal_vs_*`
- latest artifact check: `experiments/next_bar/directional_clarity_weighted_m30_latest_prediction.json`
