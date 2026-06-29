# Prior Context Floor Risk Target

日時: 2026-06-29 14:23 JST
更新日時: 2026-06-29 14:23 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻である `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## 目的

`00142` で追加した `target_walkforward_prior_context_mean_floor` を、stateful downside riskの学習targetへ戻す。

狙いは、直近holdoutへの反転ではなく「過去月全体で一貫して弱い文脈」を、future-safeな分類targetとして扱えるか確認すること。

## 実装

`oof-stateful-risk-model` に2つのtargetを追加した。

| target | definition |
|---|---|
| `walkforward_prior_floor_nonpositive` | `target_walkforward_prior_context_mean_floor <= 0` |
| `walkforward_prior_floor_lowered` | `target_walkforward_prior_context_mean_floor < target` |

既存の `walkforward_floor_lowered` は直近pseudo-holdout floorを使う。今回のprior targetは全prior context mean floorを使うため、より慢性的な弱さを拾う。

## Examples再生成

`stateful-examples-walkforward-stress` を再実行し、prior floor列入りのexamplesを生成した。

| context | rows | profiled months | stress rows | prior loss flags | prior floor mean |
|---|---:|---:|---:|---:|---:|
| available | 1544 | 6 | 397 | 142 | `-2.1919` |
| session | 1544 | 6 | 208 | 322 | `-2.1393` |

sessionではprior loss flagが322件あり、直近反転stressより広く拾う。

## OOF分類

`00140` と同じHGB設定、expanding OOF、`min_train_months=2`、`mean_match`。

| target | prevalence | predicted mean | bias | brier | AUC |
|---|---:|---:|---:|---:|---:|
| `walkforward_floor_lowered` | `0.2754` | `0.1214` | `-0.1540` | `0.2129` | `0.6371` |
| `walkforward_prior_floor_lowered` | `0.3705` | `0.2539` | `-0.1166` | `0.2394` | `0.6063` |
| `walkforward_prior_floor_nonpositive` | `0.6074` | `0.5332` | `-0.0741` | `0.2346` | `0.6240` |

prior targetはcalibration biasが小さい。特に `prior_floor_nonpositive` はAUCも `0.6240` あり、signalとしては残る。ただし既存の `floor_lowered` のAUC `0.6371` は上回らない。

## 2025-05 Quick Screen

`risk=0/5/10`、base/highcostで単月確認した。

| cost | target | risk | PnL | trades | max DD |
|---|---|---:|---:|---:|---:|
| base | none | 0 | `13.9990` | 107 | `121.5172` |
| base | `floor_lowered` | 5 | `25.3104` | 105 | `123.2528` |
| base | `prior_lowered` | 5 | `-2.1962` | 100 | `128.1134` |
| base | `prior_nonpositive` | 5 | `-109.5876` | 87 | `150.5380` |
| highcost | none | 0 | `-66.1420` | 107 | `134.6226` |
| highcost | `floor_lowered` | 5 | `-52.9764` | 105 | `137.4392` |
| highcost | `prior_lowered` | 5 | `-65.0848` | 100 | `136.6016` |
| highcost | `prior_nonpositive` | 5 | `-171.5662` | 87 | `202.5922` |

`prior_nonpositive` は取りすぎで、良い取引も削る。`prior_lowered risk=5` はhighcostでbaseline付近に戻るだけで、既存 `floor_lowered risk=5` を上回らない。

## 7ヶ月Policy確認

2024-11..2025-05で `risk=5` を比較した。

| cost | policy | total PnL | min month | trades | max DD | forced |
|---|---|---:|---:|---:|---:|---:|
| base | none | `557.9962` | `-18.7168` | 624 | `249.9600` | 4 |
| base | `floor_lowered` | `567.7900` | `+8.0868` | 603 | `218.4530` | 4 |
| base | `prior_lowered` | `491.7438` | `-2.1962` | 571 | `233.6980` | 5 |
| highcost | none | `325.0954` | `-66.1420` | 628 | `259.0392` | 4 |
| highcost | `floor_lowered` | `354.8408` | `-52.9764` | 607 | `224.7524` | 4 |
| highcost | `prior_lowered` | `278.3902` | `-65.0848` | 576 | `247.8424` | 5 |

prior floorは単独risk penaltyとしては不採用。7ヶ月合計、min month、max drawdownのいずれでも既存 `floor_lowered risk=5` に負ける。

## 判断

`target_walkforward_prior_context_mean_floor` は、学習targetとしては情報を持つ。しかし、直接penaltyにするとsignalが広すぎて、2025-02/03の利益を削り、2025-05の未解決損失も十分に抑えられない。

扱いは以下にする。

1. 単独risk penaltyには採用しない。
2. `walkforward_prior_floor_nonpositive` はcalibration biasが比較的小さいため、EV calibrationやranking feature候補として残す。
3. 2025-05で残る `short:up_normal_vol:london` はprior contextでは捕捉できないため、exit timing / EV overestimate / side-confidence interactionへ戻す。

## Artifacts

- regenerated available examples: `data/reports/backtests/20260629_051624_stateful_examples_available_context_walkforward_prior_floor/`
- regenerated session examples: `data/reports/backtests/20260629_051624_stateful_examples_session_context_walkforward_prior_floor/`
- OOF compare: `data/reports/modeling/20260629_051701_stateful_risk_expanding_session_prior_floor_mean_match_compare/`
- prediction columns: `data/reports/modeling/20260629_051944_stateful_risk_expanding_session_prior_floor_mean_match_predictions/`
- 2025-05 screen: `data/reports/backtests/20260629_prior_floor_policy_screen_2025_05/`
- 7-month policy: `data/reports/backtests/20260629_prior_floor_policy_7m/`

## 検証

- `python3 -m unittest tests.test_meta_model tests.test_docs_reports`: OK, 45 tests
- `python3 -m trade_data.meta_model oof-stateful-risk-model --help`: OK
- `git diff --check`: OK

## 次の作業

1. `prior_floor_nonpositive` を直接penaltyではなく、EV calibration / candidate rankingの補助特徴として入れる。
2. `short:up_normal_vol:london` の残存損失を、exit timing target、EV過大評価、side confidence、session interactionで診断する。
3. `floor_lowered risk=5` は現時点の防御candidateとして維持するが、標準採用は引き続きfresh month / highcost / trade-deltaで反証する。
