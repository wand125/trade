# Training Time and Generalization

日時: 2026-06-28 06:10 JST
更新日時: 2026-06-28 08:02 JST

## 目的

汎化性能を高めるため、過学習を避けるパラメータ設定を導入し、学習時間を伸ばすことで改善するかを確認する。

あわせて、データを数倍に増やす準備として 2019-01 から 2022-12 のdatasetを生成した。ただし今回の主比較は、時間的に古いデータの効果ではなく、同じsplitで学習反復数を増やす効果を見る。

## 実装

`src/trade_data/modeling.py`:

- HGBに過学習抑制パラメータを追加。
  - `--max-depth`
  - `--max-features`
  - `--early-stopping`
  - `--validation-fraction`
  - `--n-iter-no-change`
  - `--tol`
- defaultを保守的に変更。
  - `max_iter=200`
  - `learning_rate=0.03`
  - `max_leaf_nodes=15`
  - `max_depth=4`
  - `min_samples_leaf=100`
  - `l2_regularization=0.2`
  - `max_features=0.8`
  - `target_clip_quantile=0.99`
  - `sample_weighting=month_label`
- `--target-set policy` を追加。
  - executable policyに必要なtargetだけを学習し、長時間学習の比較を速くする。
- prediction frameに低次元regime特徴を残す。
- `model_diagnostics` に targetごとの `n_iter`, `hit_max_iter`, final score を保存する。
- `--label` でexperiment directory名を明示できるようにした。

`src/trade_data/meta_model.py`:

- base predictionに残したregime特徴をmeta inputとして利用可能にした。
- `month_side` sample weightingを追加。
- prediction shrinkageを追加。
- defaultをより保守的にした。
  - `max_leaf_nodes=7`
  - `max_depth=3`
  - `min_samples_leaf=300`
  - `l2_regularization=1.0`
  - `target_clip_quantile=0.98`
  - `prediction_shrinkage=0.75`

## Data Scale

追加生成:

- 2019-01 から 2022-12
- artifact summary: `data/processed/datasets/xauusd_m1/build_range_2019-01_2022-12_edge15.summary.json`

利用可能dataset:

- edge15 monthly datasets: 2019-01 から 2025-12
- months: 84
- rows: 2,433,133

68ヶ月trainのfull target学習も試したが、時間がかかりすぎるため中断した。古いデータ追加は比較軸として残すが、今回の本流ではない。

## Training Time Experiment

Split:

- train: 2023-01..2023-12, 2024-01..2024-06, 2024-08, 2024-10
- valid: 2024-07, 2024-09, 2024-11, 2025-01
- test: 2024-12, 2025-02
- train rows: 546,537
- target set: `policy`
- evaluation multipliers: profit 1.0 / loss 1.25

Common params:

- `learning_rate=0.03`
- `max_leaf_nodes=15`
- `max_depth=4`
- `min_samples_leaf=300`
- `l2_regularization=0.5`
- `max_features=0.8`
- `early_stopping=true`
- `validation_fraction=0.15`
- `target_clip_quantile=0.99`
- `sample_weighting=month_label`

Artifacts:

- iter80: `experiments/20260627_201301_policy_iter80_base_train/`
- iter320: `experiments/20260627_201455_policy_iter320_base_train/`

Model diagnostics:

| run | targets | hit max_iter | min iter | max iter |
|---|---:|---:|---:|---:|
| iter80 | 14 | 14 | 80 | 80 |
| iter320 | 14 | 14 | 320 | 320 |

すべてのtargetが `max_iter` に到達した。内部early stoppingは発火していないため、反復数だけを見ると学習時間を伸ばす余地はある。

Selection metric:

| run | valid long r2 | valid short r2 | valid selected pnl | valid side acc | test long r2 | test short r2 | test selected pnl | test side acc |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| iter80 | -0.0196 | 0.0640 | 401,423.6509 | 0.5401 | -0.0072 | -0.0623 | 297,549.3014 | 0.4529 |
| iter320 | 0.0087 | 0.0386 | 787,915.4966 | 0.5157 | -0.0065 | -0.0451 | 517,566.6426 | 0.4515 |

iter320はselection pnlを増やしたが、test side accuracyは改善していない。これは予測EVの強さが増えても、方向汎化が改善していないことを示す。

## Executable Backtest

iter80:

- validation 4fold sweep
- strict 30 trades/fold: eligibleなし
- relaxed 10 trades/fold: eligibleなし

iter320:

- strict 30 trades/fold: eligibleなし
- relaxed 10 trades/fold: eligibleあり

min fold pnl優先の選択候補:

| policy | entry | side margin | risk | max wait regret | min entry rank | barrier | mean pnl | min pnl | min trades | max DD | forced max |
|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|
| timed_ev | 15 | 0 | 0 | 4 | 0 | true | 41.8295 | 26.2700 | 15 | 51.2338 | 0.0000 |

Test:

| test month | adjusted pnl | raw pnl | trades | win rate | profit factor | max DD | forced exits |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2024-12 | -99.9843 | -77.1590 | 16 | 0.3125 | 0.1239 | 99.9843 | 0 |
| 2025-02 | -38.9125 | -21.3300 | 12 | 0.5833 | 0.5574 | 40.0975 | 0 |

平均P/L優先候補も確認したが、testはさらに悪かった。

| test month | adjusted pnl | raw pnl | trades | win rate | profit factor | max DD | forced exits |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2024-12 | -125.5185 | -96.7850 | 12 | 0.3333 | 0.1263 | 125.5185 | 1 |
| 2025-02 | -46.2038 | -25.1330 | 12 | 0.4167 | 0.5614 | 71.6038 | 0 |

## 判断

- 学習時間を80から320へ伸ばすと、validationでは候補が出るようになった。
- ただしtestではNoTradeを超えず、2024-12/2025-02ともマイナス。
- すべてのtargetがmax_iterに到達しているため、純粋な収束不足の可能性は残る。
- しかし320でtest side accuracyが改善していないため、単純に長く学習するだけでは汎化性能は改善しにくい。
- 学習時間をさらに伸ばす場合は、validation-internal OOFや追加test月を使い、反復数増加がvalidation過適合になっていないかを必ず確認する。

## 1280 Iter Follow-up

`max_iter=320` でも全targetがmax_iterに到達していたため、同じ条件で `max_iter=1280` を追加確認した。

Artifact:

- `experiments/20260627_202929_policy_iter1280_base_train/`

Settings:

- train/valid/test splitはiter80/iter320と同一。
- target set: `policy`
- `max_iter=1280`
- その他の正則化パラメータはiter320と同一。

Model diagnostics:

| run | targets | hit max_iter | min iter | max iter |
|---|---:|---:|---:|---:|
| iter80 | 14 | 14 | 80 | 80 |
| iter320 | 14 | 14 | 320 | 320 |
| iter1280 | 14 | 14 | 1280 | 1280 |

1280でも全targetがmax_iterに到達し、内部early stoppingは発火しなかった。train/validation内部lossは進んでいるが、外部評価は改善しなかった。

Selection metric:

| run | valid long r2 | valid short r2 | valid selected pnl | valid side acc | test long r2 | test short r2 | test selected pnl | test side acc |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| iter80 | -0.0196 | 0.0640 | 401,423.6509 | 0.5401 | -0.0072 | -0.0623 | 297,549.3014 | 0.4529 |
| iter320 | 0.0087 | 0.0386 | 787,915.4966 | 0.5157 | -0.0065 | -0.0451 | 517,566.6426 | 0.4515 |
| iter1280 | 0.0014 | -0.0107 | 1,025,559.2831 | 0.5173 | -0.0213 | -0.0591 | 621,918.7119 | 0.4744 |

1280はselection対象数とoracle-exit pnlを増やしたが、R2はiter320より悪化した。test side accuracyは少し上がったが、実行可能backtestでは改善しなかった。

Executable validation sweep:

- strict 30 trades/fold: eligibleなし
- relaxed 10 trades/fold: eligibleなし

最悪foldが最もましだった参考候補:

| policy | entry | side margin | risk | max wait regret | min entry rank | barrier | mean pnl | min pnl | min trades | max DD | forced max |
|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|
| timed_ev | 15 | 0 | 0.2 | 4 | 0 | true | 49.4420 | -9.7723 | 44 | 72.3265 | 0.0227 |

この候補は1foldがマイナスのため採用不可。参考としてtestへ固定適用した。

| test month | adjusted pnl | raw pnl | trades | win rate | profit factor | max DD | forced exits |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2024-12 | -97.7620 | -54.9400 | 48 | 0.5000 | 0.5434 | 112.4120 | 1 |
| 2025-02 | -97.0460 | -45.7700 | 70 | 0.5429 | 0.6215 | 140.4965 | 0 |

1280判断:

- 1280でも収束しきっていないように見えるが、外部評価は320より悪い。
- validationの対象数とoracle-exit pnlは増えるが、実行可能backtestの安定性は落ちる。
- これは「長く回すほど良い」という状況ではなく、現状の特徴量・target・policyでは反復数増加が過適合方向に働いている可能性が高い。
- 次に長時間学習を試すなら、`learning_rate` を下げる、OOFで選ぶ、またはvalidation損失ではなく月別backtestをearly stopping指標にする必要がある。

次の方針:

1. `max_iter` をさらに伸ばす場合は、同時に `learning_rate` を下げ、OOF validationで比較する。
2. 30 trades/foldを満たせない候補は本採用しない。
3. 古いデータ追加は、full targetではなく `target-set policy` から検証する。
4. test side accuracyが上がらない限り、entry/exit policyの閾値調整だけでは解決しない。

## Aligned 1.0/1.2 Target/Evaluation

旧datasetは教師生成に profit 0.9 / loss 1.3 を使い、validation/test は緩和評価で profit 1.0 / loss 1.25 を使っていた。この差が、予測EVと実行評価のずれを大きくしている可能性があるため、教師生成とvalidation/testを profit 1.0 / loss 1.2 に揃えた。

Dataset:

- `data/processed/datasets/xauusd_m1_p1_l1p2/`
- months: 2023-01 から 2025-02
- summary: `data/processed/datasets/xauusd_m1_p1_l1p2/build_range_2023-01_2025-02_edge15.summary.json`

1.0/1.2 datasetでは旧0.9/1.3 datasetより `stay_flat` が減り、long/short正例が増えた。これはNoTrade寄りに潰れすぎる問題を緩和する狙いには合っている。

Artifacts:

- iter80: `experiments/20260627_203932_policy_iter80_p1_l1p2/`
- iter320: `experiments/20260627_204140_policy_iter320_p1_l1p2/`

Training:

- splitは前回と同一。
- target set: `policy`
- common paramsは前回のregularized HGBと同一。
- train/validation/test/backtest multipliers: profit 1.0 / loss 1.2

Model diagnostics:

| run | targets | hit max_iter | min iter | max iter |
|---|---:|---:|---:|---:|
| iter80 | 14 | 14 | 80 | 80 |
| iter320 | 14 | 14 | 320 | 320 |

今回も全targetがmax_iterに到達した。320iterでも内部early stoppingは発火していない。

Selection metric:

| run | valid long r2 | valid short r2 | valid selected pnl | valid side acc | test long r2 | test short r2 | test selected pnl | test side acc |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| iter80 | -0.0393 | 0.0670 | 787,226.9478 | 0.5096 | -0.0083 | -0.0825 | 538,799.8284 | 0.4414 |
| iter320 | -0.0026 | 0.0429 | 1,259,477.9458 | 0.5154 | 0.0012 | -0.0612 | 731,975.2148 | 0.4531 |

iter320はiter80よりselection量を増やしたが、test side accuracyはまだ低い。倍率を揃えても方向汎化は十分に改善していない。

Executable validation sweep:

- iter80: 10 trades/fold条件でもeligibleなし。
- iter320: 10 trades/fold条件でeligible 31件。

min fold pnl優先の選択候補:

| policy | entry | side margin | risk | max wait regret | min entry rank | barrier | mean pnl | min pnl | min trades | max DD | forced max |
|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|
| timed_ev | 5 | 0 | 0.1 | inf | 0.5 | true | 31.5473 | 16.5412 | 38 | 73.3766 | 0.0000 |

`min pnl=16.5412` は4つのvalidation月へ同一policyを適用したときの、最悪月の `total_adjusted_pnl`。1オンス前提のXAUUSDなので、単位は概ねUSD。ただしraw PnLではなく、利益を1.0倍、損失を1.2倍に補正した後の月間合計であり、割合でも1trade平均でもない。

Test fixed application:

| test month | adjusted pnl | raw pnl | trades | win rate | profit factor | max DD | forced exits |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2024-12 | -131.6996 | -102.5750 | 35 | 0.3714 | 0.2463 | 135.1108 | 0 |
| 2025-02 | -71.2528 | -42.0540 | 39 | 0.5128 | 0.5933 | 103.3232 | 0 |

Test診断sweep:

- 2024-12のtopは `+25.6710` だが1tradeのみ。
- 2025-02のtopは `+14.8710` だが7tradesのみ。
- test 2ヶ月summaryでは、10 trades/fold以上かつ各fold PnL 0以上を満たすeligible候補はなし。

判断:

- train/valid/testを1.0/1.2に揃えることで、validationでは320iterの候補が出た。
- しかしholdout testでは2ヶ月ともNoTradeに負けた。
- 80iterは10 trades/foldまで緩めても候補なし。
- 320iterはユーザー指定どおり検証したが、test崩れが大きいため採用しない。
- `min trades=10` は探索条件として許容する。ただしtestで10 trades/月以上の候補が残らない場合は、偶然の少数tradeをedgeとして扱わない。
- 次は倍率差よりも、validation選択そのものの過適合、月別regime差、exit timingとEV calibrationの崩れを優先して診断する。

## Long Training Diagnostic on 1.0/1.2

ユーザー要望により、1.0/1.2 aligned datasetで長時間学習を追加診断した。目的は採用ではなく、学習時間不足かvalidation過適合かを切り分けること。

Artifacts:

- same LR long run: `experiments/20260627_205602_policy_iter1280_p1_l1p2/`
- low LR long run: `experiments/20260627_210612_policy_iter1280_lr001_p1_l1p2/`

Settings:

- splitは1.0/1.2の80/320比較と同一。
- target set: `policy`
- same LR: `max_iter=1280`, `learning_rate=0.03`
- low LR: `max_iter=1280`, `learning_rate=0.01`
- その他の正則化パラメータは320iterと同一。

Model diagnostics:

| run | targets | hit max_iter | min iter | max iter |
|---|---:|---:|---:|---:|
| iter80 lr0.03 | 14 | 14 | 80 | 80 |
| iter320 lr0.03 | 14 | 14 | 320 | 320 |
| iter1280 lr0.03 | 14 | 14 | 1280 | 1280 |
| iter1280 lr0.01 | 14 | 14 | 1280 | 1280 |

全runで全targetがmax_iterに到達した。内部early stoppingは発火していない。

Model metric summary:

| run | valid long r2 | valid short r2 | valid cal long r2 | valid cal short r2 | test long r2 | test short r2 | test side acc | test selected pnl |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| iter80 lr0.03 | -0.0393 | 0.0670 | 0.0768 | 0.0707 | -0.0083 | -0.0825 | 0.4414 | 538,799.8284 |
| iter320 lr0.03 | -0.0026 | 0.0429 | 0.0670 | 0.0516 | 0.0012 | -0.0612 | 0.4531 | 731,975.2148 |
| iter1280 lr0.03 | -0.0114 | -0.0061 | 0.0412 | 0.0270 | -0.0181 | -0.0716 | 0.4792 | 810,608.6956 |
| iter1280 lr0.01 | -0.0002 | 0.0320 | 0.0618 | 0.0438 | 0.0007 | -0.0469 | 0.4619 | 761,472.2850 |

同一LRの1280は、selection量は増えたがvalid R2とcalibrated R2が320より悪化した。低LR1280は同一LR1280より健全だが、320を明確には超えていない。test side accuracyはいずれも0.5未満で、方向を読めているとは言いにくい。

### Same LR 1280

Validation summary:

- strict 30 trades/fold: eligibleなし
- relaxed 10 trades/fold: eligible 1件

10 trades/fold候補:

| policy | entry | side margin | risk | max wait regret | min entry rank | barrier | mean pnl | min pnl | min trades | max DD | forced max |
|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|
| timed_ev | 20 | 5 | 0.1 | 4 | 0.5 | true | 15.6527 | 1.1964 | 20 | 71.1210 | 0.0000 |

Test fixed application:

| test month | adjusted pnl | raw pnl | trades | win rate | profit factor | max DD | forced exits |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2024-12 | -69.7450 | -40.1070 | 30 | 0.4000 | 0.6078 | 74.5420 | 0 |
| 2025-02 | -137.1102 | -95.9690 | 40 | 0.4500 | 0.4446 | 146.4156 | 0 |

Test sweep診断では、10 trades/fold以上かつ各foldプラスの候補が後付けなら1件出たが、これはtestで選んだ候補であり採用不可。

### Low LR 1280

Validation summary:

- strict 30 trades/fold: eligible 2件
- relaxed 10 trades/fold: eligible 3件

min fold pnl優先の選択候補:

| policy | entry | side margin | risk | max wait regret | min entry rank | barrier | mean pnl | min pnl | min trades | max DD | forced max |
|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|
| timed_ev | 15 | 0 | 0 | inf | 0 | true | 48.2348 | 40.8376 | 46 | 87.6726 | 0.0179 |

このvalid候補は320の1.0/1.2候補より明確に強い。特に30 trades/fold条件でも通っている点は改善。ただしtest固定適用では崩れた。

Test fixed application:

| test month | adjusted pnl | raw pnl | trades | win rate | profit factor | max DD | forced exits |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2024-12 | -134.5306 | -101.4610 | 55 | 0.4000 | 0.3220 | 143.4870 | 1 |
| 2025-02 | -110.0922 | -66.1180 | 72 | 0.5278 | 0.5827 | 130.8148 | 0 |

Test sweep診断:

| policy | entry | side margin | risk | max wait regret | min entry rank | barrier | mean pnl | min pnl | min trades | max DD | forced max |
|---|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|
| timed_ev | 15 | 0 | 0.2 | 2 | 0.5 | false | 17.5052 | 11.0620 | 18 | 29.9154 | 0.0000 |

このtest上位候補は、validationでは `mean pnl=2.5216`, `min pnl=-28.2506`, `min trades=10`, `eligible=false` だった。つまり、testで良い閾値はvalidationで選べない。これはモデル本体だけでなく、policy threshold selectionも分布差に過適合していることを示す。

## Direction Review

長時間学習中にdocsを再読し、方向性レビューを作成した。

- report: `docs/reports/00008_2026-06-28_research_direction_review.md`

要点:

- 研究の大枠はずれていない。
- HGB反復数と同一validation sweepの繰り返しは袋小路になりやすい。
- 低LR長時間学習でもtestが改善しないため、HGB反復数探索はいったん打ち切る。
- 次は失敗trade分解、OOF標準化、side/regime別EV calibration、exit timing target、shared representationへ進む。

## Updated Judgment

- 長時間学習は、validationスコアを良くする効果はある。
- しかしtestでNoTradeを超えず、2024-12/2025-02とも大きく負ける。
- 低LR1280はvalid上は最も良いが、test固定適用では今回最悪級に崩れた。
- したがって現状の特徴量、target、policy selectionでは「学習時間不足」が主因とは判断しない。
- 主因は、validation policy selectionの過適合、regime shift、EV calibration崩れ、exit timing未解決と見る。

次の作業:

1. 2024-12/2025-02のtrade failure analyzerを作る。
2. train期間にもOOF predictionsを作り、meta calibrationの学習量を増やす。
3. side/regime別EV calibrationとshrinkageを追加する。
4. exit timing targetをhazard/fixed horizon/barrier timeへ拡張する。
5. 独立HGBではなく、shared trunkを持つ小型MLP/TCNへ進む。
