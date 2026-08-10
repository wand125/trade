# 00084 M1 Bar Breakout / Rejection

日時: 2026-08-11 JST

## 目的

M1完成足が直前の価格境界を終値で突破したのか、ヒゲだけ更新して範囲内へ戻されたのかを分離する。平均的な形状圧力ではなく、prior-onlyな境界イベントが次足方向またはconfidenceへ増分情報を持つか確認した。

## 固定特徴と品質

現在足を含まない直前1/5/20本の高値・安値を1本shiftして固定し、各窓についてclose breakout up/down、high/low rejectionの12 binary特徴を作った。さらに直前足に対するinside/outside、方向付きrange expansionの4特徴、直前20本high/lowまでのATR正規化close距離2特徴を追加した。合計18列、baselineと合わせて56特徴である。

価格scale不変、未来行変更が過去特徴へ影響しない因果性、完全無変動をイベント証拠なしの全0とする有限値、binary列が0/1だけであること、raw OHLCがmodel featureへ入らないこと、保存artifactからのlatest推論をテストした。

source 6,025,170行、usable 5,737,928行、baselineと完全整列したOOS 2,183,717行を、同じ7fold、最大750,000行expanding HGB、fold別Plattで評価した。損失係数は標準1.0で、窓・特徴・weightは結果確認後に変更していない。

## 単体と固定25%方向blend

| period | baseline | Breakout single | HGB 75% + Breakout 25% |
|---|---:|---:|---:|
| development accuracy | 50.93738% | 50.93701% | 50.95186% |
| confirmation accuracy | 50.60001% | 50.60119% | 50.60392% |
| all accuracy | 50.80695% | 50.80718% | 50.81734% |

単体はdevelopment -5件、confirmation +10件、all +5件・p=0.993で、Brier/log lossもaggregate悪化したため不採用とする。

通常25% blendはdevelopment +194件・p=0.248、confirmation +33件・p=0.813、all +227件・p=0.293。accuracyは5/7fold改善したが、方向edgeは弱い。一方、Brier/log lossは7/7fold、ECEは4/7fold改善した。

UTC日paired bootstrap 20,000回のblend−baseline accuracy差95%区間はdevelopment -0.0102〜+0.0392pt、confirmation -0.0285〜+0.0360pt、all -0.00918〜+0.0298ptで全て0を跨いだ。all Brier差は-0.00000432〜-0.00000142、log loss差は-0.00000866〜-0.00000285で確率平滑化は支持されたが、confirmation proper score区間も0を僅かに跨ぐ。

## 既存方向・確率品質候補との比較

Session Relative 25%との直接比較ではBreakoutがaccuracy 1/7、Sessionが6/7勝った。Breakoutはdevelopment、confirmation、allのaccuracy・Brier・log lossを全てSessionに負け、all accuracyは50.8173%対50.8374%、Brierは0.2498660対0.2498561だった。

したがって、Breakoutはbaseline確率を少し平滑化しても、Path/LightGBMの点精度、Extra Treesのstability、Volatility/Sessionのproper-score役割を上積みしない。aggregate proper scoreだけを理由に新しいshadowを増やさない。

## Confidence用途

developmentの固定候補0.51〜0.53では0.51が最大selection scoreとなった。developmentはaccuracy 51.5790%→51.6268%、score 0.009629→0.009928へ改善した。

しかしconfirmationではcoverage 24.21%→24.10%、accuracy 51.8000%→51.7889%、score 0.007791→0.007716と3項目すべて反転した。fold比較もaccuracy 5/7でもscore 4/7に留まる。development選択をconfirmationで再調整せず、confidence用途は不採用とする。既存TCN 0.515を維持する。

## 判断

Bar Breakout / Rejectionは確率平滑化の情報を持つが、方向accuracyと高信頼目的関数の確認期間再現性が足りず、既存probability-quality候補にも明確に負ける。feature set、OOS、通常blend、方向維持blend、analysis、bootstrap、Session比較は再現用に残すが、forward config、registry、latest artifact、odds calibrationは発行しない。

1/5/20窓、18列subset、距離clip、HGB parameter、25% weight、0.51以外のconfidence閾値を同じ履歴へ合わせて再探索しない。authoritative方向、confidence、fair odds、採用policy、paper/live売買は変更しない。

## 成果物

- OOS: `experiments/next_bar/walk_forward_bar_breakout_rejection_m1_fixed_001`
- normal blend: `experiments/next_bar/bar_breakout_rejection_m1_blend_current_001`
- direction-preserving blend: `experiments/next_bar/bar_breakout_rejection_m1_confidence_blend_current_001`
- candidate analysis: `experiments/next_bar/bar_breakout_rejection_m1_candidate_analysis.json`
- baseline bootstrap: `experiments/next_bar/bar_breakout_rejection_m1_direction_bootstrap.json`
- Session comparison: `experiments/next_bar/bar_breakout_rejection_vs_session_m1_direction_analysis.json`
