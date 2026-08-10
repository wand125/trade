# 00066 Intrabar full path

日時: 2026-08-10 19:23 JST

## 目的

Intrabar Profileは完成M15内の15本のM1 close経路を20/40/60/80%地点と偏差要約へ圧縮するため、反転順序の一部を失う。Profileの定義を親として維持し、欠けている11地点を追加して15点の経路を復元したとき、次足方向と高信頼度順位付けへ増分edgeがあるかを検証した。

## 固定特徴

完成M15のopenを原点、完成M15のhigh-low rangeを尺度として、各M1 closeを `(close - M15 open) / M15 range` に変換する。既存Profileが3/15、6/15、9/15、12/15地点を持つため、1、2、4、5、7、8、10、11、13、14、15/15の11列だけを追加した。親27 intrabar列＋11列＝38 intrabar、全76 model特徴である。

結果を見る前に地点数・位置・正規化を固定した。価格10倍一致、未来M1改変が過去完成足へ不影響、flat時有限0、15点の元M1との厳密対応、artifact/latest推論をテストした。

## 方向結果

| period | 正式baseline | Full Path | 親Profile |
|---|---:|---:|---:|
| development | 52.0144% | 52.2692% | 52.0627% |
| confirmation | 51.5012% | 51.4815% | 51.3941% |
| all | 51.8162% | 51.9650% | 51.8045% |

Full Path単体は親Profileへaccuracy 6/7 fold、proper scoreとECEも全期間で勝ち、経路点追加のincremental edgeは確認できた。正式baselineにはdevelopmentで純改善+227件、p=0.0423だったが、confirmationは-11件、全体+216件、p=0.123である。正式baseline 75% + Full Path 25%の通常blendも全体-45件、p=0.526だった。方向候補としては採用せず、既存Volatility Shape単体を維持する。

## 方向維持confidence

baseline方向を固定した25% blendはBrier/log lossを7/7、ECEを6/7 fold改善した。developmentの事前gridで0.53が最大selection scoreとなった。

| period | baseline accuracy / coverage / score | Full Path accuracy / coverage / score |
|---|---:|---:|
| development | 54.309% / 29.868% / 0.02027 | 54.580% / 29.801% / 0.02173 |
| confirmation | 54.479% / 18.438% / 0.01511 | 54.905% / 17.311% / 0.01628 |
| all | 54.357% / 25.453% / 0.01942 | 54.667% / 24.977% / 0.02076 |

固定0.53ではbaselineへaccuracy 7/7、selection score 5/7、Brier/log loss 7/7 fold勝った。全期間36,252件を採用し、正答率54.667%、coverage 24.977%、Wilson下限54.154%、score 0.02076である。

## 既存候補・親との直接比較

| comparator | Full Path / comparator all accuracy | Full Path / comparator all score | fold accuracy / score勝敗 |
|---|---:|---:|---:|
| 親Profile 0.53 | 54.667% / 54.504% | 0.02076 / 0.02005 | 6/1、4/3 |
| Distribution Shape 0.53 | 54.667% / 54.568% | 0.02076 / 0.02018 | 5/2、5/2 |
| Extra Trees 0.53 | 54.667% / 54.522% | 0.02076 / 0.02006 | 4/3、4/3 |

Profileに対してdevelopment/confirmation/allのaccuracy・scoreがすべて正で、単体方向でも6/7勝ったため、親に対する増分edgeがある。Distributionに対してはdevelopment objectiveとconfirmation accuracy/scoreを同時に上回り、選択集合Jaccardは88.45%だった。Extra TreesよりBrier/log lossも全期間で低い。

## 日次block bootstrapとsubgroup

各UTC日をpaired blockとして20,000回再標本化した。

- 正式baseline比は全期間accuracy差+0.311ptの95%区間が+0.121〜+0.502pt、selection score差+0.001347が+0.000395〜+0.002311、Brier差の区間も全て負で、主要改善がすべて支持された。
- Distribution比は全期間accuracy差+0.099pt、score差+0.000585の区間が0を跨いだが、Brier/log loss差は全区間負だった。confirmation accuracy差+0.354ptの区間は+0.018〜+0.688ptでFull Path優位を支持した。
- Extra Trees比も全期間accuracy/scoreの区間は0を跨いだが、Brier/log loss改善は95%区間で支持された。
- 親Profile比はconfirmation accuracy差+0.386ptの区間が+0.066〜+0.701ptだった。全期間accuracy差は下端-0.001pt、優位確率97.37%で、境界的である。

固定side × volatility監査では、confirmationのup全regimeとdown-highがWilson edgeを通った。Distributionで49.942%かつ局所不整合だったdown-normalは、Full Pathでは796件、accuracy 51.256%、mean confidence 53.779%となり局所整合を回復した。ただしdown-low/normalのWilson下限は50%以下なのでedge確定ではなく、結果後のsubgroup除外ruleも作らない。

## Runtime parityと判断

baselineと同じsplit・HGB・Platt設定でlatest artifactを生成し、parity検査を通した。最新2026-06-01 04:45 UTCはbaseline up 0.577254、Full Path up 0.551126、方向維持blend up 0.570722で固定0.53 laneを通る。odds校正・運用認可は接続していないため `odds_valid=false` のままである。

方向単体と通常方向blendは棄却する。方向維持0.53は、事前規定のdevelopment objective、confirmation gate、親incremental比較、baseline日次bootstrapを通ったためselective confidence forward candidateとして採用する。candidate registryでは15候補中のselective履歴championになった。Distribution ShapeとExtra Treesは比較対象として残すが、authoritative confidence、現行adoption policy、paper/live売買policyは変更しない。完全未使用期間でFull Pathのaccuracy・selection score・Brier、down-normal局所整合を同じ固定条件で再確認する。

損失倍率は標準1.0のみであり、1.2倍の特別規則は使用していない。

## 成果物

- config: `methods/next_bar/config/m15_intrabar_full_path_confidence_candidate_v1.json`
- OOS: `experiments/next_bar/walk_forward_intrabar_full_path_m15_001`
- 通常blend: `experiments/next_bar/ensemble_intrabar_full_path_m15_25_001`
- 方向維持confidence: `experiments/next_bar/intrabar_full_path_m15_confidence_blend_001`
- 比較・bootstrap: `experiments/next_bar/intrabar_full_path_vs_*`
- subgroup: `experiments/next_bar/intrabar_full_path_m15_053_subgroup_reliability.json`
- latest artifact/output: `experiments/next_bar/intrabar_full_path_m15_latest_artifact_001`, `experiments/next_bar/intrabar_full_path_m15_latest_ensemble_001`
