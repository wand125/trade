# 00125 M1 Directional Follow-through Weighting

日時: 2026-08-11 17:44 JST

## 目的

次足の方向明瞭度だけでなく、終値が方向側の高安へ到達した度合いも教師品質へ加工するDirectional Follow-through sample weightingをM1へ固定移植した。M30/M5/M15の結果を見た後で式や閾値を変えず、M1の方向精度、coverage-aware confidence、校正へ独立した増分があるか検証した。

## 固定仕様と品質

解決済みtrain教師だけについて、`clarity = abs(next close - next open) / (next high - next low)` と方向側close locationの積を0〜1へ制限し、raw weightを `0.5 + clarity * direction_aligned_close_location` とする。sampled train内で平均1へ正規化し、全教師を残す。未来OHLCはtrain sample weightだけへ使い、特徴、calibration、test、latest推論へ渡さない。

baseline加工38特徴、HGB 200 iteration、learning rate 0.05、31 leaves、min leaf 100、L2 1、最大train 750,000行、expanding、Platt、seed 42、通常/方向維持25% blend、標準損失1.0を固定した。test2020〜test2026途中の7foldでbaselineとtimestamp、decision/target timestamp、target、foldが一致する2,183,717 OOS行を生成した。

## 方向結果

| period | baseline | Follow単体 | 通常25% blend |
|---|---:|---:|---:|
| development | 50.93738% | 50.93813% | 50.95985% |
| confirmation | 50.60001% | 50.67534% | 50.62074% |
| all | 50.80695% | 50.83653% | 50.82875% |

単体はbaseline比development +10件、confirmation +636件、all +646件でaccuracy 4/7、Brier/log loss 6/7foldだった。通常blendは+301/+175/+476件でaccuracy、Brier、log lossを7/7fold改善し、全期間McNemar exact p=0.04454だった。日次bootstrapではall accuracy差+0.00033〜+0.04280ptとproper score改善を支持したが、development/confirmation accuracy区間は0を跨いだ。

通常blendは既存Pathにall -466件、accuracy 2/7対5/7、Distribution Shiftに-383件、2/7対5/7だった。Directional-Clarityにはall -392件、accuracy 0/7対6/7、1 tieで、日次bootstrapのall accuracy差95%区間も-0.03633〜-0.00018ptだった。Follow-throughはbaseline感度を再現したが、既存方向役割を上回らない。

## Confidence 0.515

development固定grid `0.51, 0.515, 0.525, 0.535, 0.55` の評価関数最大は0.515だった。

| period | baseline coverage / accuracy / score | Follow coverage / accuracy / score |
|---|---:|---:|
| development | 28.6110% / 51.9505% / 0.009587 | 28.8639% / 52.0031% / 0.009916 |
| confirmation | 9.9208% / 52.5091% / 0.006837 | 9.9625% / 52.6710% / 0.007365 |
| all | 21.3852% / 52.0507% / 0.008820 | 21.5565% / 52.1224% / 0.009192 |

baseline比はaccuracy/score 6/7、Brier/log loss 7/7foldで、日次bootstrapはdevelopment、confirmation、allのaccuracy、coverage、score、proper scoreを全て支持した。教師品質加工がconfidence rankingにも有効という感度は確認できた。

一方、Transition guard 0.515はall coverage 16.0178%、accuracy 52.5827%、score 0.009674で、Followはaccuracy 0/7、score 1/7だった。Follow−Transitionの日次区間はall accuracy -0.5527〜-0.3681pt、score -0.000853〜-0.000103、Brier/log lossもFollow悪化を支持した。Disagreement 0.515にもaccuracy/score 0/7、Distribution Shift 0.51には精度6/7でもscore 2/7だった。

Transition guardとFollow confidenceの固定50/50平均はall coverage 18.6186%、accuracy 52.3461%、score 0.009460で、親の16.0178% / 52.5827% / 0.009674を下回った。accuracy 0/7、score 2/7で分散効果も採用しない。

## 高信頼度と校正

Follow 0.55はall 18,075件、coverage 0.8277%、accuracy 54.8769%、mean confidence 56.2057%で1.3288pt過信した。confirmationは119件、accuracy 53.7815%、Wilson edge未確認だった。0.575はall 2,361件、accuracy 57.2639%、mean confidence 58.7505%だが全件developmentで、confirmationは0件だった。

0.515のconfirmationは84,107件でaccuracy 52.6710%、mean confidence 52.0276%と全体では過小評価だが、固定side×volatility 6セルのうちdown-low 702件・49.0028%、down-normal 2,752件・50.0363%、up-low 1,667件・50.6299%はWilson edge未確認だった。結果を見た後のsubgroup除外ruleは作らない。Transition guardは0.55 allで56.1506%、0.575 allで60.4087%とFollowを上回り、Follow tailをfair oddsへ使う根拠はない。

latest artifactは2026-06-01 04:59 UTC判定でdown、probability down 50.5756%を返した。経験的odds未接続のため `odds_valid=false` である。

## 判断

M1 Directional Follow-throughは通常方向blendと方向維持0.515でbaselineを時系列的に改善し、教師品質加工の有効な感度を再現した。ただし方向はPath/Distribution Shift/Directional-Clarity、confidenceはTransition guard/Disagreement/Distribution Shiftの既存役割を超えず、固定平均も親を改善しない。高信頼tailはconfirmationへ移行せず校正も弱いため、単体、通常blend、confidence、固定平均を全て再現専用とする。

M1 candidate config、registry、authoritative方向/confidence、fair odds、paper/live policyは変更しない。同じ履歴で式、weight、blend、閾値、subgroupを再探索しない。損失倍率は標準1.0のみである。

## 成果物

- OOS/latest: `experiments/next_bar/walk_forward_directional_follow_through_weighted_m1_fixed_001`, `experiments/next_bar/directional_follow_through_weighted_m1_latest_prediction.json`
- normal/confidence blends and candidate analysis: `experiments/next_bar/directional_follow_through_weighted_m1_*`
- direction comparisons/bootstrap: `experiments/next_bar/directional_follow_through_m1_direction_*`, `experiments/next_bar/directional_follow_through_vs_*_m1_direction_bootstrap.json`
- confidence role comparisons/bootstrap/reliability: `experiments/next_bar/directional_follow_through_0515_*`, `experiments/next_bar/directional_follow_through_vs_*_m1_confidence_0515_bootstrap.json`, `experiments/next_bar/directional_follow_through_vs_transition_guard_m1_reliability.json`
- subgroup/high-confidence audit: `experiments/next_bar/directional_follow_through_m1_confidence_subgroups.json`, `experiments/next_bar/directional_follow_through_055_vs_baseline_055_m1.json`
- fixed diversification: `experiments/next_bar/transition_guard_directional_follow_through_equal_m1_*`
