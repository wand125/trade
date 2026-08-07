# 00011 M30 as-of context for the M15 high-confidence lane

日時: 2026-08-08 01:16 JST

## 目的

M15/M5/M1 cross-timeframe metaへ、そのM15判定時点で既に発行済みのM30方向確率を追加し、M15の高信頼帯を改善できるか確認する。

## 時刻と漏洩防止

M30の予測は30分ごと、M15の判定は15分ごとなので、完全一致joinだけでは半数を失う。次の固定規則でas-of joinした。

```text
M30 prediction decision_timestamp <= M15 decision_timestamp
prediction age <= 15 minutes
future prediction is prohibited
```

M30予測のageは0分または15分だけとなった。市場ギャップなどで15分以内のM30予測がない行は欠損とし、古い値を無制限に持ち越さない。実装にはfutureを選ばないこととstale値を落とすunit testを追加した。

最初のpilotでは既存M30成果物に2020〜2021 foldが無く、meta評価が2023年開始へ後退した。比較期間を揃えるため、同じbaseline HGB設定で `context_confirmation_m30_001` の2020・2021 OOS予測を補完し、再実行した。欠損pilotは `cross_timeframe_meta_m30_asof_pilot_missing_early_001` として判断対象外に分離した。

## モデル

```text
features = logit(P_M15), logit(P_M5), logit(P_M1), logit(P_M30_latest)
P_final = 0.75 * P_M15 + 0.25 * P_meta
```

C=0.10、meta weight=0.25は現行3時間足candidateと同じ。M30追加以外は変更していない。各test foldは、それ以前のdirection-model OOS foldだけでmeta modelを学習する。

M30係数は全foldで正となり、test2021の0.247からtest2026途中の0.128へ縮小した。情報はあるが、M5の係数0.51前後より弱い。

## 同一117,599行の全体比較

| metric | M15/M5/M1 meta | + M30 as-of | delta |
|---|---:|---:|---:|
| accuracy | 51.684% | 51.666% | -0.018pt |
| balanced accuracy | 51.620% | 51.602% | -0.018pt |
| Brier | 0.2495625 | 0.2495580 | 改善 |
| log loss | 0.6922725 | 0.6922636 | 改善 |
| ECE | 0.441% | 0.465% | -0.024pt |

全体accuracyは2/6 foldだけ改善、1fold同値。pairedでは旧誤りを558件修正した一方、新規誤りが579件で純21件悪化、McNemar近似p=0.553。全体方向モデルの置換材料にはならない。

## 高信頼lane

実運用ではM30が15分以内に無い時刻も全M15機会の分母に含める。fresh M30のavailabilityは97.980%。高信頼laneは、fresh M30があれば4時間足meta、無ければ現行3時間足metaへfallbackする。

| period | policy | rows | coverage | accuracy | selection score |
|---|---|---:|---:|---:|---:|
| 2021–2023 | base | 12,571 | 19.469% | 54.093% | 0.01421 |
| 2021–2023 | M30/fallback | 12,671 | 19.624% | 54.250% | 0.01498 |
| 2024–2026途中 | base | 4,105 | 7.403% | 55.664% | 0.01126 |
| 2024–2026途中 | M30/fallback | 4,074 | 7.347% | 55.842% | 0.01169 |
| all | base | 16,676 | 13.894% | 54.479% | 0.01388 |
| all | M30/fallback | 16,745 | 13.951% | 54.637% | 0.01450 |

全期間selection scoreは4.50%改善。fold単位では2021、2022、2024、2025の4/6で改善し、2023と2026途中は悪化した。developmentとconfirmationの合算値がともに改善したため、高信頼専用forward candidateとして固定する。

M30 age別にもaccuracy改善は残り、age 0分は53.956%から54.048%、age 15分は54.913%から55.164%。特定ageだけを追加選択する最適化は行わない。

## 通常損益の補助診断

損失倍率は1.0。高信頼laneの次足open-to-close通常損益を1ozで比較した。

| policy | gross mean / oz | all-fold cost ceiling / oz | cost 0.05 positive folds |
|---|---:|---:|---:|
| base meta | 0.11357 | 0.04962 | 5/6 |
| M30/fallback | 0.11663 | 0.05140 | 6/6 |

改善したが、最悪foldのcost 0.05後余力は0.00140/ozしかない。売買policy昇格には弱い。

## 判断

- `m15_cross_tf_m30_high_conf_candidate_v1.json` として高信頼laneだけforward candidate化する。
- confidence 0.54未満の方向出力は現行M15/M5/M1 metaを維持する。
- 全体方向モデルは置換しない。全体accuracy低下とECE悪化を許容しない。
- paper売買policyは置換しない。損益は補助診断であり、主評価はaccuracy、coverage、Wilson下限、selection scoreとする。
- 次の完全未使用期間へ設定を固定し、高信頼selection scoreとECEを再確認する。
