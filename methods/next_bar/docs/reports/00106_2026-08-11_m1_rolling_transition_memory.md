# 00106 M1 Rolling Transition Memory

日時: 2026-08-11 12:45 JST

## 目的

価格履歴そのものではなく、現在の完成M1足に似た定常ローソク状態が直近でどの方向へ遷移したかを局所学習する加工を検証した。global train全体で固定transition tableを学ぶDirection Transition Bayesとは異なり、各decision時点で既に結果が確定した直近32/128本だけから更新する非パラメトリックなmemoryである。

## 固定仕様と品質

各完成足を次の4 bit、16状態へ固定離散化した。

- close-to-close return方向
- `abs(body) / range >= 0.5`
- closeが足rangeの上半分か
- true rangeが現在足を除く直前20本中央値以上か

現在行 `t` の特徴には、状態行 `i` とその次の結果 `i+1` がともに `t` までに完成した遷移だけを使う。timestamp gapを跨ぐ遷移、0 return、非有限値はsupportから除外した。同一状態のnext-up率を同window全遷移のup率へ固定強度8で縮約し、32/128本それぞれのup edge、support fraction、local−global差、reversal edgeと、短長差の固定9列を作った。

window 32/128、状態境界0.5、range基準20、prior strength 8、HGB/Platt、通常/方向維持25% blendをOOS結果前に固定した。損失倍率は標準1.0のみである。手計算の厳密値、価格10倍scale不変、未来行改変不影響、flat全0、gap行全0、[-1, 1]有限値、stationary guard、保存artifact/latest推論をテストした。

2019年以降train、2020〜2026途中testの固定7foldで、baselineと完全整列した2,183,717行を生成した。

## 単体とbaseline blend

| candidate | development accuracy | confirmation accuracy | all accuracy | all Brier |
|---|---:|---:|---:|---:|
| baseline | 50.93738% | 50.60001% | 50.80695% | 0.249868880 |
| Transition Memory単体 | 50.90856% | 50.59255% | 50.78639% | 0.249872687 |
| baseline 75% + Memory 25% | 50.96851% | 50.60593% | 50.82834% | 0.249864980 |

単体はbaseline比all -449件で棄却する。通常25% blendはdevelopment +417件、confirmation +50件、all +467件、accuracy 6/7fold、Brier/log loss各6/7fold改善した。exact paired p=0.04003だった。

UTC日paired bootstrap 20,000回でもall accuracy差+0.02139ptの95%区間は+0.00068〜+0.04259pt、Brier差は[-0.000005543, -0.000002267]、log loss差も全区間改善側だった。ただしconfirmation accuracy区間は-0.02676〜+0.03864pt、proper scoreも0を跨ぎ、後半期間だけの改善は確定しない。

## 既存方向候補との比較

Path Persistence 25%のall accuracy 50.85009%に対しMemoryは50.82834%、年別accuracy 2/7だった。Memory−Pathのconfirmation accuracy差95%区間は-0.07707〜-0.00357ptでPath優位、allも-0.04495〜+0.00150ptでMemory採用を支持しない。

Distribution Shift 25%のall accuracy 50.84629%、Brier 0.249857850に対し、Memoryはaccuracy 3/7、Brier 0.249864980だった。方向差区間は0を跨ぐが、Memory−ShiftのBrier差95%区間はall [+0.000004328, +0.000009959]、confirmation [+0.000001556, +0.000007362]でMemory悪化が確定した。baseline比改善は既存stability/proper-score役割を超えない。

## confidenceと高信頼度tail

development selection score最大は方向維持0.515だった。

| period | candidate | accuracy | coverage | selection score |
|---|---|---:|---:|---:|
| development | Memory 0.515 | 52.01855% | 28.2934% | 0.009891 |
| confirmation | Memory 0.515 | 52.63184% | 9.4356% | 0.007019 |
| all | Memory 0.515 | 52.12507% | 21.0029% | 0.009076 |
| all | baseline 0.515 | 52.05067% | 21.3852% | 0.008820 |

baseline比ではaccuracy 6/7、score 4/7foldだった。all日次bootstrapはaccuracy差区間+0.03086〜+0.11749pt、score差+0.000056〜+0.000454で改善を支持した。confirmation accuracyも下端+0.00062ptで改善側だが、scoreとproper score区間は0を跨いだ。

既存Disagreement 0.515はall accuracy 52.3090% / coverage 19.8959% / score 0.009636で、Memoryよりaccuracy +0.1838pt、score +0.000560、accuracy/score各6/7foldだった。日次bootstrapでもMemory−Disagreementのaccuracy差区間-0.2611〜-0.1062pt、score差-0.000907〜-0.000213で既存候補優位が確定した。Transition guard × Disagreement champion 0.515にはaccuracy 0/7、score 1/7で、all accuracyは52.5827%、score 0.009674だった。

Memoryのall 0.55以上は17,525件、accuracy 54.9330%、mean confidence 56.2174%で約1.285pt過信した。confirmationは143件・57.3427%、0.60以上はall 328件だけである。疎なtailをfair odds根拠にしない。

## 固定多様化監査

weight探索をせず、Memory 25%とPath 25%、Memory 25%とShift 25%をそれぞれ50/50平均した。実質baseline 75% + 各candidate 12.5%ずつである。

Path+Memoryはall accuracy 50.82737%、accuracy 1/7foldで、Path比差95%区間-0.03910〜-0.00628ptと明確に悪化した。Shift+Memoryはall accuracy 50.83470%、年別4/7でもShiftの50.84629%を下回り、Brier/log lossはdevelopment・confirmation・allすべてShiftより有意に悪化した。単純な多様化追加にも増分edgeはない。

## 判断

`rolling_transition_memory` はbaselineを方向・proper score・0.515目的関数で改善する有効な加工感度として再現可能に残す。しかし単体は弱く、Pathの方向精度、Distribution Shiftのproper score、Disagreement/Transition guardのconfidence精度と目的関数を超えず、固定多様化でも親候補を上積みしなかった。さらに単純rollingより前処理負荷が大きい。

したがって方向・confidence候補へ採用せず、研究再現専用とする。同じ履歴でwindow、16状態、state bit、閾値、prior strength、blend/stack weight、confidence thresholdを再探索しない。config、registry、authoritative方向/confidence、fair odds、adoption/paper/live policyを変更せず、runtime latestも発行しない。

## 成果物

- feature/test: `src/trade_data/next_bar.py`, `tests/test_next_bar.py`
- OOS: `experiments/next_bar/walk_forward_rolling_transition_memory_m1_fixed_001`
- baseline blends: `experiments/next_bar/rolling_transition_memory_m1_blend_fixed_001`, `experiments/next_bar/rolling_transition_memory_m1_confidence_fixed_001`
- candidate/subgroup: `experiments/next_bar/rolling_transition_memory_m1_candidate_analysis.json`, `experiments/next_bar/rolling_transition_memory_m1_confidence_subgroups.json`
- direct comparisons: `experiments/next_bar/rolling_transition_memory_vs_*`
- fixed diversification: `experiments/next_bar/path_transition_memory_equal_*`, `experiments/next_bar/distribution_shift_transition_memory_equal_*`
