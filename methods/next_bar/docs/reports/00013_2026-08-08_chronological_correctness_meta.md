# 00013 Chronological correctness meta-model

日時: 2026-08-08 01:28 JST

## 目的

方向モデルを変えず、HGB方向が正しい確率を過去のOOS実績から直接学習してconfidenceと採用条件を改善できるか確認する。

## 設計

各test foldについて、それ以前のdirection-model OOS foldだけでL2 logistic regressionを学習した。

入力:

- HGBとlogisticのclass confidence
- 2モデルの確率差と方向一致
- 各モデルの予測方向
- 現在足のbody ratioとvolatility
- UTC時刻と曜日の周期特徴

targetはHGB方向の `correct`。C=0.10。meta単体と、HGB confidence 75% + correctness meta 25%を比較した。2020 foldを最初のmeta学習に使うため、評価は2021〜2026途中の121,950行。

## 結果

| confidence | Brier | log loss | ECE |
|---|---:|---:|---:|
| HGB | 0.2495873 | 0.6923225 | 0.525% |
| correctness meta | 0.2499790 | 0.6931360 | 1.106% |
| 25% blend | 0.2496355 | 0.6924208 | 0.633% |

2021 foldではmeta平均confidenceが55.15%に対して実accuracyは52.46%となり、時期ドリフトを強く過大評価した。confirmation期間だけでもmetaのBrier、log loss、ECEはすべてHGBより悪い。

confidence 0.55以上のselection scoreは一部集計でわずかに上がったが、複数source/thresholdから結果を見て選ぶことはしない。過去OOS foldだけで次foldのsourceと閾値を選ぶnested selectorを追加した。

候補:

```text
source = HGB / correctness meta / 25% blend
threshold = 0.53 / 0.54 / 0.55
```

2022〜2026途中の全5foldで `HGB confidence >= 0.53` が選ばれ、correctness metaとblendは一度も選ばれなかった。augmented selectorの結果はbase-only selectorと完全に同一だった。

| nested aggregate | rows | coverage | accuracy | selection score |
|---|---:|---:|---:|---:|
| base-only | 20,667 | 20.928% | 53.835% | 0.01443 |
| augmented | 20,667 | 20.928% | 53.835% | 0.01443 |

## 判断

- correctness meta単体と25% blendを棄却する。
- candidate設定やdeployment modelは作らない。
- HGB/logistic disagreementをconfidenceへ利用する場合は、前実験の単純な方向維持blendを優先する。
- expanding OOS correctnessの関係は時期ドリフトが大きく、追加の複雑さに見合うforward改善がない。
