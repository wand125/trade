# Stateful Downside Mean Match 2025-05 Fixed

日時: 2026-06-29 12:36 JST
更新日時: 2026-06-29 12:38 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻である `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## 目的

`00140` で事前登録candidateにした `mean_match + session_floor_lowered risk=5` を、同じ6ヶ月内で追加調整せず、次の固定月 `2025-05` へ外挿確認する。

2025-05は過去の別系統実験では使われているが、このstateful downside mean-match候補の選抜には使っていない。したがって「完全な初見月」ではなく、「今回候補に対する未使用固定月」として扱う。

## 生成

2025-03/04 applyと同じsplit/settingsで、同一形式のHGB entry/side + MLP exit predictionを作った。

- dataset: `xauusd_m1_p1_l1p2_policy_combined`, `2025-05`
- rows: `30147`
- label counts: `short=15364`, `flat=1095`, `long=13688`
- train months: `2023-01..2024-06`, `2024-08`, `2024-10`
- validation months: `2024-07`, `2024-09`, `2024-11`, `2025-01`
- test/apply month: `2025-05`
- purge / embargo: label overlap purge enabled, embargo `24h`
- HGB config: `max_iter=80`, `learning_rate=0.05`, `max_leaf_nodes=15`, `max_depth=4`, `min_samples_leaf=100`, `l2=0.2`, `max_features=0.8`, `sample_weighting=month_label`
- MLP config: hidden layers `32,16`, `alpha=0.01`, `max_iter=40`, `sample_frac=0.15`

Prediction diagnostics:

| model | item | value |
|---|---|---:|
| HGB | best_side balanced accuracy | `0.4571` |
| HGB | selected side accuracy | `0.4924` |
| HGB | long exit minutes R2 | `0.1332` |
| HGB | short exit minutes R2 | `0.1289` |
| MLP | selected side accuracy | `0.4674` |
| MLP | long exit minutes R2 | `0.1177` |
| MLP | short exit minutes R2 | `0.1361` |

2025-04ほどではないが、MLP exit minutesは外挿がまだ荒い。

| holding column | mean | median | `<30m` rate |
|---|---:|---:|---:|
| `pred_mlp_long_exit_event_minutes` | `63.30` | `-82.44` | `0.5931` |
| `pred_mlp_short_exit_event_minutes` | `61.90` | `-76.93` | `0.5892` |

今回も `min_valid_predicted_hold_minutes=30` のfail-close guardが重要な安全制約として働いている。

## Fixed Policy

条件は `00140` のcandidateを固定。

- policy: `timed_ev`
- entry threshold: `12`
- short offset: `6`
- side margin: `5`
- max predicted hold: `480`
- min valid predicted hold: `30`
- min entry rank: `0.5`
- side EV penalty: `short:combined_regime=down_low_vol:5`, `short:combined_regime=up_low_vol:10`
- risk signal: `pred_stateful_risk_wf_exp_session_mm_walkforward_floor_lowered_*_risk`

結果:

| cost case | risk | adjusted PnL | trades | win rate | PF | max DD | long PnL | short PnL |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| base | `0` | `13.9990` | 107 | `0.5607` | `1.0275` | `121.5172` | `-48.4930` | `62.4920` |
| base | `5` | `25.3104` | 105 | `0.5619` | `1.0504` | `123.2528` | `-34.1840` | `59.4944` |
| highcost | `0` | `-66.1420` | 107 | `0.5140` | `0.8782` | `134.6226` | `-73.2330` | `7.0910` |
| highcost | `5` | `-52.9764` | 105 | `0.5238` | `0.9016` | `137.4392` | `-61.2416` | `8.2652` |

`risk=5` はbase/highcostとも改善した。特にlong側損失はbase `-48.4930 -> -34.1840`、highcost `-73.2330 -> -61.2416` に縮んだ。

ただし、highcostはまだNoTrade `0` に届かず、max DDも `risk=5` の方がわずかに悪化している。`00140` の合格条件だった cost min `>= -20` には届かない。

## Delta

`risk=5` と `risk=0` のtrade delta:

| cost case | base trades | risk5 trades | PnL delta | removed positive | removed negative | added positive | added negative |
|---|---:|---:|---:|---:|---:|---:|---:|
| base | 107 | 105 | `+11.3114` | `82.9610` | `-25.6476` | `83.0900` | `-11.4996` |
| highcost | 107 | 105 | `+13.1656` | `79.4900` | `-27.5952` | `87.5300` | `-15.4116` |

改善は少数の入れ替えで出ている。risk=5は悪い取引だけを落としたわけではなく、良い取引もかなり捨てている。

残った主な損失:

| cost case | status | direction/regime | adjusted PnL |
|---|---|---|---:|
| base | common | `long:down_low_vol` | `-106.4684` |
| base | common | `short:up_normal_vol` | `-86.0010` |
| highcost | common | `short:up_normal_vol` | `-117.7136` |
| highcost | common | `long:down_low_vol` | `-114.3840` |

stateful candidate examplesのtarget mean:

| cost case | candidate count | target mean | positive-cost mean | blocking cost sum |
|---|---:|---:|---:|---:|
| base | 105 | `0.0481` | `-0.0840` | `34.1340` |
| highcost | 105 | `-0.6984` | `-0.8521` | `36.4930` |

高コスト込みでは、risk=5後のcandidate集合自体のstateful target meanが負。これはcost-aware実運用候補として弱い。

## 判断

`mean_match + session_floor_lowered risk=5` は2025-05でも防御方向には働いた。これは `00140` の「最悪月を抑える補助signal」という仮説を一部支持する。

ただし標準policyへは採用しない。

理由:

- highcostで `-52.9764` とNoTradeを下回り、事前のcost min基準 `>= -20` を満たさない。
- risk=5後も `long:down_low_vol` と `short:up_normal_vol` のcommon trade損失が大きい。
- MLP exit minutesは中央値が負で、fail-close guard頼みの状態が続いている。
- HGB best_side balanced accuracy `0.4571`、selected side accuracy `0.4924` で、entry/sideの月外汎化が弱い。
- 改善は少数の入れ替えに依存し、良い取引も多く落としている。

今後の扱い:

- `risk=5` は標準採用せず、candidate ranking / diagnostic featureへ降格寄りに扱う。
- 次は同じrisk penaltyを増やして調整しない。2025-05を見た後のrisk閾値最適化はpost-hocになる。
- 本流は、common tradeに残る `long:down_low_vol`, `short:up_normal_vol` のような損失を、未来情報なしのwalk-forward context/downside targetで扱う方向へ戻す。
- MLP holdingは引き続き `min_valid_predicted_hold_minutes=30` を固定安全制約とする。exit target自体はlog/bin/hazard系への置換を優先する。

## Artifacts

- dataset: `data/processed/datasets/xauusd_m1_p1_l1p2_policy_combined/xauusd_m1_2025-05_h24_edge15.parquet`
- HGB 2025-05: `experiments/20260629_033233_policy_combined_side_exit_test_2025_05/`
- MLP 2025-05: `experiments/20260629_033050_shared_mlp_hgb_split_test_2025_05/`
- hybrid predictions: `data/reports/modeling/20260629_hgb_mlp_exit_hybrid_2025_05/`
- forced predictions: `data/reports/modeling/20260629_hgb_mlp_exit_hybrid_forced_targets/predictions_hgb_entry_mlp_exit_2025_05_forced.parquet`
- stateful risk apply: `data/reports/modeling/20260629_033349_stateful_risk_mean_match_session_floor_lowered_apply_2025_05/`
- policy sweeps:
  - `data/reports/backtests/20260629_stateful_downside_mean_match_2025_05/base/20260629_033428_model_sweep_2025-05/`
  - `data/reports/backtests/20260629_stateful_downside_mean_match_2025_05/highcost/20260629_033428_model_sweep_2025-05/`
- fixed policy runs:
  - `data/reports/backtests/20260629_stateful_downside_mean_match_2025_05/fixed_base_risk0/`
  - `data/reports/backtests/20260629_stateful_downside_mean_match_2025_05/fixed_base_risk5/`
  - `data/reports/backtests/20260629_stateful_downside_mean_match_2025_05/fixed_highcost_risk0/`
  - `data/reports/backtests/20260629_stateful_downside_mean_match_2025_05/fixed_highcost_risk5/`
- trade deltas:
  - `data/reports/backtests/20260629_stateful_downside_mean_match_2025_05/trade_delta_base_risk5/20260629_033615_trade_delta_base_risk5_vs_risk0/`
  - `data/reports/backtests/20260629_stateful_downside_mean_match_2025_05/trade_delta_highcost_risk5/20260629_033615_trade_delta_highcost_risk5_vs_risk0/`

## 検証

- `python3 -m trade_data.dataset build-range`: OK for `2025-05`
- `python3 -m trade_data.modeling train`: OK for HGB `2025-05`
- `python3 -m trade_data.modeling train-shared-mlp`: OK for MLP `2025-05`
- `python3 -m trade_data.modeling enrich-predictions`: OK for forced targets
- `python3 -m trade_data.meta_model oof-stateful-risk-model`: OK for `2025-05` apply
- `python3 -m trade_data.backtest model-sweep`: OK for base/highcost
- `python3 -m trade_data.backtest model-policy`: OK for fixed risk `0/5`
- `python3 -m trade_data.backtest model-trade-delta`: OK for base/highcost deltas
- `python3 -m unittest tests.test_docs_reports`: OK, 2 tests
- `git diff --check`: OK

## 次の作業

1. `risk=5` の直接policy採用は止める。追加月で同じ固定評価を続ける場合も、採用判断ではなく診断として扱う。
2. 2025-05で残った `common long:down_low_vol` / `common short:up_normal_vol` 損失を、post-hoc blockではなくwalk-forward downside/context targetへ戻す。
3. MLP exit minutesは回帰値直結を続けず、log/bin/hazard targetとfail-close条件を評価する。
4. highcostを最初から満たす候補選抜に戻し、NoTrade未満の候補を「改善したから採用」としない。
