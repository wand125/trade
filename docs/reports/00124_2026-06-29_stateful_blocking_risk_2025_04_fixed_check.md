# Stateful Blocking Risk 2025-04 Fixed Check

日時: 2026-06-29 09:53 JST
更新日時: 2026-06-29 09:53 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻である `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## 目的

`00123` では `positive_blocking risk=5` がvalidationでは改善したが、apply 3ヶ月では合計PnLとdrawdownを悪化させた。

今回は同じmodelを固定し、まだstateful risk列を付与していなかった 2025-04 に外挿する。これはpost-hoc tuningではなく、`00123` で事前登録した「追加walk-forward foldで固定値評価する」確認。

## 実行

まず validation 4ヶ月 examples で同じ `oof-stateful-risk-model` を再実行し、2025-04 forced predictionへfinal modelを適用した。

入力:

- examples: `data/reports/backtests/20260628_234917_stateful_candidate_examples_validation/stateful_candidate_examples.csv`
- apply prediction: `data/reports/modeling/20260629_hgb_mlp_exit_hybrid_forced_targets/predictions_hgb_entry_mlp_exit_2025_04_forced.parquet`

artifacts:

- scored prediction: `data/reports/modeling/20260629_005251_stateful_blocking_risk_model_apply_2025_04/`
- sweep: `data/reports/backtests/stateful_blocking_risk_positive_blocking_apply_2025_04/20260629_005307_model_sweep_2025-04/`

policy条件は `00123` と同じ。

- `timed_ev`
- entry threshold `12`
- short offset `6`
- side margin `5`
- min entry rank `0.5`
- max predicted hold `480`
- side EV penalty: `short:down_low_vol=5`, `short:up_low_vol=10`
- profit/loss: `1.0 / 1.20`

## 2025-04 Result

| risk | adjusted PnL | trades | profit factor | max DD | forced exit rate |
|---:|---:|---:|---:|---:|---:|
| `0` | `-503.8224` | `2484` | `0.8145` | `718.7252` | `0.0004` |
| `5` | `-509.6742` | `2470` | `0.8116` | `729.0912` | `0.0004` |
| `10` | `-494.0544` | `2443` | `0.8151` | `701.7802` | `0.0004` |
| `20` | `-486.2782` | `2375` | `0.8148` | `701.4004` | `0.0004` |

`positive_blocking risk=5` は追加月で改善せず、baselineより `-5.8518` 悪化した。`risk=20` は損失を少し縮めるが、まだ `-486.2782` であり、risk modelが解決すべき種類の失敗ではない。

2025-04はtrade countが `2484` と異常に多く、median holdingも `2` 分。これは過去の `00095` / `00100` 系の観察と同じで、MLP exit holdingの外挿破綻により高回転化した月として扱うべき。

## Extended Apply Summary

2024-12 / 2025-02 / 2025-03 / 2025-04 を合わせると次の通り。

| risk | sum PnL | min month PnL | trades | max DD |
|---:|---:|---:|---:|---:|
| `0` | `-261.3216` | `-503.8224` | `2910` | `718.7252` |
| `5` | `-310.6882` | `-509.6742` | `2887` | `729.0912` |
| `10` | `-321.6562` | `-494.0544` | `2846` | `701.7802` |
| `20` | `-458.9534` | `-486.2782` | `2745` | `701.4004` |

`risk=5` の月別delta:

| month | baseline | risk 5 | delta |
|---|---:|---:|---:|
| `2024-12` | `-20.8252` | `-3.5260` | `+17.2992` |
| `2025-02` | `179.2484` | `141.2374` | `-38.0110` |
| `2025-03` | `84.0776` | `61.2746` | `-22.8030` |
| `2025-04` | `-503.8224` | `-509.6742` | `-5.8518` |

`risk=5` は1ヶ月だけ保護し、残り3ヶ月で削る。追加walk-forward確認により、標準policy候補からはさらに遠のいた。

## 判断

`positive_blocking risk=5` は標準policyにも事前登録候補にも昇格しない。

理由:

- validationでは良かったが、apply 4ヶ月では合計、最低月、drawdownのすべてでbaseline未満。
- 2025-04の壊れ方は「entry候補のblocking risk」ではなく、holding prediction外挿による異常高回転が主因。
- risk penaltyを強くしてもtrade数は `2484 -> 2375` 程度しか下がらず、根本的な執行/holding破綻を止められない。

次にやること:

1. stateful risk分類は診断列として残すが、policy penaltyには使わない。
2. 2025-04型の高回転破綻を先に止める。具体的には `min_valid_predicted_hold_minutes`、holding fallback、time-bin/log holdingなどのfail-closeを標準policy候補として再評価する。
3. 追加examplesでsupportを増やす場合も、holding guardを固定した後に行う。破綻holdingのままexamplesを増やすと、entry riskではなくexit model failureを教師に混ぜる危険がある。
