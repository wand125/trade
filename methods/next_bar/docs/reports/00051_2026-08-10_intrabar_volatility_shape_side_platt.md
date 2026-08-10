# 00051 Intrabar Volatility Shape side Platt confidence

日時: 2026-08-10 16:46 JST

## 目的

M15 Shape confidenceのconfirmationで、0.535以上のupは全volatility regimeでWilson edgeを通る一方、downはhighだけが通った。confirmationで見つけたside/regimeを後付けfilterにはせず、既に実装済みの固定 `side_platt` をShapeへそのまま転用する。各foldのcalibration期間だけでpredicted up/down別にcorrectnessをPlatt校正し、方向モデル、Shape特徴、7fold、HGB/Platt設定、固定信頼度帯は変更しない。

## 実装上の補強

side correctnessは0.5未満も出力できる。従来のreliability監査はclass confidenceの `[0.5, 1]` を前提としていたため、オッズ確率として `[0, 1]` を受け入れ、0.5未満を `below_first_edge` としてcoverage、accuracy、mean confidence、Brier、log loss、ECE、Wilson区間とともに別表示するよう拡張した。固定0.5以上の帯・閾値定義は変更していない。

## Overall correctness probability

方向予測はclass confidence版と完全一致し、accuracyも同じである。比較するproper scoreは「その方向が正しい確率」に対する値である。

| period | confidence | Brier | log loss | ECE | mean confidence |
|---|---|---:|---:|---:|---:|
| development | Shape class | 0.24929525 | 0.69173755 | 0.1706% | 52.4454% |
| development | Shape side Platt | 0.24931863 | 0.69178510 | 0.2425% | 52.4410% |
| confirmation | Shape class | 0.24957199 | 0.69228983 | 0.2354% | 51.8172% |
| confirmation | Shape side Platt | 0.24961790 | 0.69238191 | 0.4833% | 51.8237% |

side PlattはBrier、log loss、ECEをdevelopment/confirmationの両方で悪化させた。121,950件のnested oddsでもclass confidenceはBrier 0.24958237、log loss 0.69231269、ECE 0.4199%に対し、side Plattは0.24962172、0.69239223、0.5303%で3指標すべて悪化した。side Plattへの追加階層実績校正もさらに悪化した。

## 0.5未満の推定

side Plattは全145,140件のうち7,421件、5.113%をconfidence 0.5未満にした。この帯の実accuracyは51.031%、mean confidenceは49.670%で、避けるべき行を作れていない。confirmationでは2,857件、accuracy 52.048%、mean confidence 49.693%、Wilson下限50.214%となり、むしろ50%超edgeのある行を過小評価した。

これは「方向別補正なら非対称を直せる」という仮説に反し、calibration年のside biasが次年へ安定して移らないことを示す。

## 固定閾値

| threshold | period | class accuracy | class coverage | class score | side accuracy | side coverage | side score |
|---:|---|---:|---:|---:|---:|---:|---:|
| 0.515 | development | 53.064% | 59.878% | 0.02043 | 53.037% | 62.109% | 0.02066 |
| 0.515 | confirmation | 52.525% | 50.438% | 0.01380 | 52.249% | 55.832% | 0.01267 |
| 0.525 | development | 53.847% | 39.468% | 0.02089 | 53.869% | 37.555% | 0.02044 |
| 0.525 | confirmation | 53.428% | 27.165% | 0.01373 | 53.626% | 26.420% | 0.01450 |
| 0.535 | development | 54.718% | 24.803% | 0.02023 | 54.793% | 22.894% | 0.01966 |
| 0.535 | confirmation | 54.237% | 12.716% | 0.01098 | 54.501% | 10.304% | 0.01032 |
| 0.550 | development | 55.345% | 11.277% | 0.01468 | 55.313% | 10.681% | 0.01409 |
| 0.550 | confirmation | 56.158% | 3.027% | 0.00659 | 56.240% | 2.173% | 0.00507 |

0.515はdevelopment scoreだけ、0.525はconfirmation scoreだけ改善した。0.535はaccuracyがdevelopment/confirmationと6/7 foldで上がるがcoverage低下が大きくscoreは両期間で低下、score改善は3/7 foldだった。0.550もconfirmation accuracyの改善は0.082ptだけでscoreは両期間低下した。固定閾値のどれにも両期間・foldで安定した採用根拠がない。

side × volatilityの0.535でもdown-low/normalのWilson edge未達は解消しなかった。down-highはclass 56.026%からside 54.522%へ悪化したため、発端の非対称への直接的な改善にもなっていない。

## 成果物と判断

- OOS: `experiments/next_bar/walk_forward_intrabar_volatility_shape_side_platt_m15_001`
- reliability: `experiments/next_bar/intrabar_volatility_shape_side_platt_m15_reliability_analysis.json`
- nested odds: `experiments/next_bar/intrabar_volatility_shape_side_platt_m15_odds_calibration.json`
- subgroup: `experiments/next_bar/intrabar_volatility_shape_side_platt_m15_subgroup_reliability.json`
- fixed thresholds: `experiments/next_bar/intrabar_volatility_shape_side_platt_m15_0515_analysis.json`, `..._0525_analysis.json`, `..._0535_analysis.json`, `..._055_analysis.json`

Shape side Plattは棄却し、Shape自身のclass confidenceを非認可odds shadowとして維持する。side/regime filter、side Platt、追加経験的再校正のいずれもauthoritative oddsや採用policyへ入れない。同じ履歴でside別正則化や閾値を再探索せず、非対称は固定subgroupのfresh監視で扱う。損失倍率は標準1.0のみとする。
