# 00110 M15/M30 Fixed Component Consensus Filter

日時: 2026-08-11 15:45 JST

## 目的

Prequential Selective Correctnessで学習済みconfidenceが期間ドリフトしたため、係数・fit・確率再校正を一切使わない固定consensus filterを検証した。基準confidence候補をそのまま使い、内部candidate 3本の方向一致だけで予測採用をvetoする。

## 固定仕様と品質

M15はSigned-body Quantile 0.525、M30はIntrabar Pressure 0.52を基準とした。基準candidate、Volatility Shape candidate、Intrabar Profile candidateの各OOS確率を基準のup/down方向へ向け、次の2規則だけを事前固定した。

- majority: 3本中2本以上が基準方向を支持
- unanimous: 3本すべてが基準方向を支持

元confidenceが固定閾値以上でもsupport不足ならconfidenceを0.5±machine epsilonへ戻して棄権させる。supportを通る行の確率とconfidenceは基準値を変更しない。target、correct、次足情報、development/confirmation結果は規則に使わない。方向一致許容値は1e-15、損失倍率は標準1.0のみである。

M15 145,140行、M30 71,260行で3ソースのfold/timestamp/decision/target timestamp/target/方向/正誤を完全整列した。future target変更不影響、2/3・3/3厳密support、方向維持、確率和1、confidence/class confidence一致、0.5 tieをテストした。

## M15 majority 2/3

M15では元confidence 0.525以上のうちdevelopmentで21件だけをvetoし、confirmationでは0件だった。

| period | candidate accuracy / coverage / score | reference accuracy / coverage / score |
|---|---:|---:|
| development | 54.08762% / 37.6918% / 0.021820 | 54.07762% / 37.7154% / 0.021767 |
| confirmation | 54.08631% / 26.4552% / 0.016888 | 54.08631% / 26.4552% / 0.016888 |
| all | 54.08722% / 33.3519% / 0.021039 | 54.08028% / 33.3664% / 0.021004 |

confirmationで完全同一であり、増分filterとして実質的な作用がない。2/3を採用しない。

## M15 unanimous 3/3

| period | candidate accuracy / coverage / score | reference accuracy / coverage / score |
|---|---:|---:|
| development | 54.16376% / 37.0295% / 0.022062 | 54.07762% / 37.7154% / 0.021767 |
| confirmation | 54.07568% / 26.3054% / 0.016773 | 54.08631% / 26.4552% / 0.016888 |
| all | 54.13655% / 32.8876% / 0.021157 | 54.08028% / 33.3664% / 0.021004 |

developmentではaccuracy +0.08614ptの日次95%区間が+0.01308〜+0.16001pt、Brier/log lossも改善側で、3/3不一致は有効なdevelopment vetoだった。all accuracy +0.05627ptも区間+0.00167〜+0.11204pt、proper score改善も支持された。

一方、selection score差区間はdevelopment -0.000151〜+0.000748、all -0.000162〜+0.000473で0を跨いだ。confirmationではaccuracy -0.01063pt、coverage -0.14985pt、score -0.000114で全て点悪化し、proper score差区間も0を跨いだ。年別accuracyは4/7でもselection scoreは3/7対4/7だった。

特に元0.525 laneからvetoした集合はdevelopment 611件・accuracy 49.4272%だったが、confirmation 84件・55.9524%へ反転した。確認期間では誤りではなく正解を多く除外しており、forward採用条件を満たさない。3/3もconfidence候補へ採用しない。

## M30 majority 2/3

| period | candidate accuracy / coverage / score | reference accuracy / coverage / score |
|---|---:|---:|
| development | 53.75929% / 39.2004% / 0.018852 | 53.76890% / 40.1959% / 0.019210 |
| confirmation | 53.65015% / 30.5050% / 0.014276 | 53.73451% / 30.6388% / 0.014787 |
| all | 53.72322% / 35.8251% / 0.018621 | 53.75769% / 36.4861% / 0.019034 |

development、confirmation、allのaccuracy・coverage・selection scoreがすべて低下した。年別accuracy/scoreも3/7対4/7である。Brier/log lossも3期間で基準より悪く、2/3を棄却する。

## M30 unanimous 3/3

| period | candidate accuracy / coverage / score | reference accuracy / coverage / score |
|---|---:|---:|
| development | 53.79877% / 36.8609% / 0.018379 | 53.76890% / 40.1959% / 0.019210 |
| confirmation | 53.72990% / 29.9013% / 0.014512 | 53.73451% / 30.6388% / 0.014787 |
| all | 53.77537% / 34.1594% / 0.018402 | 53.75769% / 36.4861% / 0.019034 |

僅かなdevelopment/all accuracy上昇よりcoverage減少が大きく、selection scoreはdevelopment -0.000831、confirmation -0.000276、all -0.000632だった。年別scoreは2/7対5/7で、Brier/log lossも全期間区分で悪化した。3/3を棄却する。

## 判断

非学習consensusは、M15 developmentで誤りの多い小集合を特定し、全期間accuracyとproper scoreを有意に改善した。しかしそのveto対象はconfirmationで55.95%正解へ反転し、confirmationのaccuracy・coverage・selection scoreをすべて下げた。M15 2/3はほぼ無作用、M30の両規則は主目的を一貫して悪化させた。

したがって固定Component Consensus FilterはM15/M30とも研究再現専用とする。support本数、candidate組合せ、edge許容値、元confidence threshold、union規則を同じ履歴で再探索しない。Signed-body Quantile、Structure、Pressureの既存役割を維持し、config、registry、authoritative confidence、fair odds、adoption/paper/live policy、runtime artifactを変更しない。

## 成果物

- implementation: `src/trade_data/next_bar_consensus_filter.py`
- CLI: `methods/next_bar/scripts/component_consensus_filter.py`
- tests: `tests/test_next_bar_consensus_filter.py`
- M15: `experiments/next_bar/component_consensus_m15_2of3_fixed_001`, `experiments/next_bar/component_consensus_m15_3of3_fixed_001`
- M30: `experiments/next_bar/component_consensus_m30_2of3_fixed_001`, `experiments/next_bar/component_consensus_m30_3of3_fixed_001`
- bootstrap: `experiments/next_bar/component_consensus_vs_signed_body_quantile_m15_3of3_0525_bootstrap.json`
