# Stateful Downside Mean Match Risk Budget

日時: 2026-06-29 12:23 JST
更新日時: 2026-06-29 12:25 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻である `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## 目的

`00139` では `session_floor_lowered` が防御signalとして有望だったが、probabilityの平均が実際のprevalenceを大きく下回り、`risk=10` では利益を削りすぎた。

今回は、stateful downside riskにmean-match calibrationを追加し、risk budgetを小さくしたときに「合計PnLを大きく削らずに最悪月を抑える」候補になるか確認する。

## 実装

`oof-stateful-risk-model` に `--probability-calibration none|mean_match` を追加した。

`mean_match` は、予測probabilityをlogitへ変換し、scored fold内の平均がfit済みtarget prevalenceへ合うようinterceptだけを二分探索でずらす。fold内の順位は保つが、fold間のスケールは変わるため、OOF全体AUCは少し動き得る。未来のholdout prevalenceは使わない。

## OOF校正

対象は `session` contextの `walkforward_floor_lowered`。expanding OOF、`--min-train-months 2`。

| calibration | candidate count | prevalence | predicted mean | bias | brier | AUC |
|---|---:|---:|---:|---:|---:|---:|
| none | 1220 | `0.2754` | `0.1051` | `-0.1703` | `0.2181` | `0.6473` |
| mean_match | 1220 | `0.2754` | `0.1214` | `-0.1540` | `0.2129` | `0.6371` |

Brierとbiasは少し改善した。一方でfold間のprior補正により、全体AUCは `0.6473 -> 0.6371` へ低下した。rank signalは維持されているが、校正はまだ完全ではない。

## Policy接続

条件は `00139` と同じ6ヶ月診断セット。

- months: `2024-11`, `2024-12`, `2025-01`, `2025-02`, `2025-03`, `2025-04`
- policy: `timed_ev`
- entry threshold: `12`
- short offset: `6`
- side margin: `5`
- holding: `pred_mlp_long_exit_event_minutes`, `pred_mlp_short_exit_event_minutes`
- max predicted hold: `480`
- min entry rank: `0.5`
- side EV penalty: `short:combined_regime=down_low_vol:5`, `short:combined_regime=up_low_vol:10`
- risk signal: `pred_stateful_risk_wf_exp_session_mm_walkforward_floor_lowered_*_risk`

集計:

| cost case | risk penalty | total PnL | min month | trades | max DD | forced |
|---|---:|---:|---:|---:|---:|---:|
| base | `0` | `543.9972` | `-18.7168` | 517 | `249.9600` | 4 |
| base | `5` | `542.4796` | `+8.0868` | 498 | `218.4530` | 4 |
| base | `10` | `430.1004` | `-14.8642` | 471 | `252.4060` | 4 |
| base | `15` | `190.5686` | `-75.7344` | 438 | `328.0436` | 5 |
| base | `20` | `158.9708` | `-146.3326` | 405 | `333.9484` | 6 |
| highcost | `0` | `391.2374` | `-34.3748` | 521 | `259.0392` | 4 |
| highcost | `5` | `407.8172` | `-16.9006` | 502 | `224.7524` | 4 |
| highcost | `10` | `312.1200` | `-40.4058` | 475 | `253.7434` | 4 |
| highcost | `15` | `102.5456` | `-84.4244` | 443 | `296.2158` | 5 |
| highcost | `20` | `63.7336` | `-127.7490` | 411 | `303.5608` | 6 |

`risk=5` はbase合計をほぼ維持しながら最悪月を `-18.7168 -> +8.0868` に改善し、high costでは合計も `391.2374 -> 407.8172` へ改善した。max DDも base/highcost ともに低下した。

## Candidate Selection

同じ6ヶ月のbase/high cost sweepsを `model-candidate-selection` へ渡した。条件はbase 6fold、cost 6fold、月30trades以上、forced exit rate `<=0.05`、max DD `<=260`、base min月 `>=0`、cost min月 `>=-20`。

| risk penalty | eligible | base sum | base min | cost sum | cost min | max DD |
|---:|---|---:|---:|---:|---:|---:|
| `5` | true | `542.4796` | `+8.0868` | `407.8172` | `-16.9006` | `224.7524` |
| `0` | false | `543.9972` | `-18.7168` | `391.2374` | `-34.3748` | `259.0392` |
| `10` | false | `430.1004` | `-14.8642` | `312.1200` | `-40.4058` | `253.7434` |
| `15` | false | `190.5686` | `-75.7344` | `102.5456` | `-84.4244` | `328.0436` |
| `20` | false | `158.9708` | `-146.3326` | `63.7336` | `-127.7490` | `333.9484` |

`risk=5` だけが通過した。ただし、この候補は同じ6ヶ月診断セット上で観測・選抜している。標準policyへ昇格せず、次の未使用月または事前登録foldで固定確認する。

## 判断

`mean_match + session_floor_lowered risk=5` は、`00139` のrisk直結より明確に良い。特に、合計PnLをほぼ削らずにbase最悪月を正にし、high costの合計・最悪月・drawdownを同時に改善した点は重要。

ただし標準採用はまだしない。

理由:

- 6ヶ月診断セットを見たうえで `risk=5` を選んでいるため、選抜過適合の可能性がある。
- AUCは校正前より少し下がっており、signalのrank安定性は追加月で確認が必要。
- `risk=10` 以上は利益を削りすぎ、penalty台地は広くない。
- 次の評価は、この候補を固定してfresh month / high cost / drawdown / trade-delta preflightで反証する必要がある。

今後の扱いは、標準policyではなく「事前登録candidate」とする。これ以上この6ヶ月でrisk penaltyを細かく調整しない。

## Artifacts

- mean-match OOF compare: `data/reports/modeling/20260629_031819_stateful_risk_expanding_session_floor_lowered_mean_match_compare/`
- mean-match OOF predictions: `data/reports/modeling/20260629_031821_stateful_risk_expanding_session_floor_lowered_mean_match_predictions/`
- policy summary: `data/reports/backtests/20260629_stateful_downside_risk_mean_match_policy/stateful_downside_risk_mean_match_policy_summary.csv`
- policy aggregate: `data/reports/backtests/20260629_stateful_downside_risk_mean_match_policy/stateful_downside_risk_mean_match_policy_aggregate.csv`
- candidate selection: `data/reports/backtests/20260629_stateful_downside_risk_mean_match_selection/20260629_032015_model_candidate_selection/`

## 検証

- `python3 -m unittest tests.test_meta_model tests.test_docs_reports`: OK, 44 tests
- `python3 -m trade_data.meta_model oof-stateful-risk-model --help`: OK
- `git diff --check`: OK

## 次の作業

1. `mean_match + session_floor_lowered risk=5` を固定し、未使用月または次のwalk-forward foldでbase/high costを検証する。
2. 合格条件は合計PnLではなく、min month、max DD、forced exit rate、high cost retention、trade-delta preflightを含める。
3. 同じ6ヶ月上でrisk penaltyやthresholdを追加最適化しない。
4. 失敗した場合は、単独risk penaltyではなくcandidate ranking featureかdiagnostic featureへ降格する。
