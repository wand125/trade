# 00037 Chronological expert stacking

日時: 2026-08-10 13:58 JST

## 目的

複数の有力モデルを等重みで平均する代わりに、各test foldより前のOOS予測と正解だけからモデルweightを学習し、方向精度とconfidence選別を改善できるか検証する。現在foldの正解をweight学習へ使わないchronological stackingとする。

## 結果前に固定した方法

- 対象はM15、2020〜2026途中の145,140 OOS行・7fold。
- 入力はbaseline HGB、clear-body HGB、Extra Trees、signed-body HGB regression、intrabar-structure HGBのup確率をlogit変換した5特徴。
- 各test foldのstackerは、それ以前のtest foldだけでStandardScalerとL2 logistic regressionを学習する。
- L2 logisticの `C=0.10`、random seed 42を固定する。
- 過去OOSが存在しないtest2020はbaseline確率へfallbackする。
- stack単体、baseline 75% + stack 25%の通常blend、同じ25% blendをbaseline方向へ固定したconfidence blendを比較する。
- confidence閾値は0.515、0.52、0.525、0.53、0.54、0.55、0.60の固定gridから2020〜2023 developmentだけで選ぶ。2024〜2026途中confirmationは選択に使わない。

学習器が現在・未来foldをtrainへ含めないこと、最初のfoldがbaseline fallbackになること、expert target不整列を拒否することを単体テストした。

## 方向と確率品質

| period | model | accuracy | Brier | log loss | ECE |
|---|---|---:|---:|---:|---:|
| development | baseline | 52.014% | 0.2493466 | 0.6918398 | 0.377% |
| development | stack single | 52.093% | 0.2495521 | 0.6922672 | 0.757% |
| development | normal 25% blend | 52.086% | 0.2493435 | 0.6918342 | 0.388% |
| development | direction-preserved | 52.014% | 0.2493465 | 0.6918403 | 0.454% |
| confirmation | baseline | 51.501% | 0.2495525 | 0.6922506 | 0.298% |
| confirmation | stack single | 51.251% | 0.2495822 | 0.6923102 | 0.456% |
| confirmation | normal 25% blend | 51.358% | 0.2495477 | 0.6922411 | 0.398% |
| confirmation | direction-preserved | 51.501% | 0.2495468 | 0.6922393 | 0.252% |
| all | baseline | 51.816% | 0.2494261 | 0.6919985 | 0.347% |
| all | stack single | 51.768% | 0.2495637 | 0.6922838 | 0.641% |
| all | normal 25% blend | 51.805% | 0.2494223 | 0.6919914 | 0.392% |
| all | direction-preserved | 51.816% | 0.2494239 | 0.6919944 | 0.376% |

stack単体はconfirmationで全指標が悪化した。通常25% blendはdevelopmentの方向精度とBrier/log lossを僅かに改善したがconfirmation精度を0.143pt下げた。全体のpaired比較はbaseline誤り修正1,832件、新規誤り1,848件、McNemar exact p=0.805で方向edgeではない。

方向維持版はconfirmationのBrier、log loss、ECEを改善したが、development log lossとECE、全体ECEは悪化した。proper scoreのfold改善はBrier/log loss/ECEすべて4/7に留まる。

## developmentで選んだconfidence 0.53

| period | model | rows | coverage | accuracy | selection score |
|---|---|---:|---:|---:|---:|
| development | baseline | 26,607 | 29.868% | 54.309% | 0.02027 |
| development | stacking confidence | 27,546 | 30.922% | 54.309% | 0.02069 |
| confirmation | baseline | 10,336 | 18.438% | 54.479% | 0.01511 |
| confirmation | stacking confidence | 9,757 | 17.405% | 54.330% | 0.01394 |
| all | baseline | 36,943 | 25.453% | 54.357% | 0.01942 |
| all | stacking confidence | 37,303 | 25.701% | 54.315% | 0.01931 |

developmentではcoverage増加によりscoreが上がったが、confirmationはcoverage、accuracy、Wilson下限、selection scoreがすべて悪化した。年別ではaccuracy改善3/7、score改善4/7である。既存Extra Trees 0.53のconfirmationはcoverage 18.148%、accuracy 54.664%、score 0.01574でstackingを明確に上回る。

## 学習weight診断

StandardScaler後係数はtest2021以降、baselineが負、clear-bodyとExtra Treesとintrabar structureが正、signed-bodyがほぼ0という形になった。test2026途中用ではbaseline -0.005、clear-body +0.034、Extra Trees +0.027、signed-body -0.000002、intrabar structure +0.051だった。

各expertは同じ加工OHLCから作られ相関が強い。履歴が増えても係数が独立edgeを抽出できず、stack単体の確率が過大化した。これは「学習weightなら固定平均より必ず良い」という仮説を支持しない。

## 成果物と判断

- 実装: `src/trade_data/next_bar_stacking.py`
- CLI: `methods/next_bar/scripts/chronological_stacking.py`
- 単体: `experiments/next_bar/chronological_stacking_single_001`
- 通常25% blend: `experiments/next_bar/chronological_stacking_001`
- 方向維持25% blend: `experiments/next_bar/chronological_stacking_direction_preserved_001`
- 共通分析: `experiments/next_bar/chronological_stacking_candidate_analysis.json`

stack単体、通常方向blend、方向維持confidenceのすべてを採用しない。forward/shadow configは発行せず再現実装だけを残す。同じ履歴でC、expert subset、stack weight、閾値を再探索しない。candidate registryの役割別champion、authoritative confidence、fair odds、paper policyは変更しない。損失倍率は標準1.0のみとする。
