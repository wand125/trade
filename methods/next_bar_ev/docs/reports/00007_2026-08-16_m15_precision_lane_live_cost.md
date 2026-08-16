# 00007 M15 precision lane live-cost audit

日時: 2026-08-16 03:37 JST

## 目的

M15 baseline confidence 0.54と保有延長がTitanFX XAUUSD-mの実spreadで成立しなかったため、既存candidate registryの固定precision championならcostを吸収できるか確認した。候補、閾値、モデル、方向、保有期間は履歴結果に合わせて変更しない。

## 固定対象

`m15_candidate_registry_v1.json` がprecision roleのchampionとして固定した `Intrabar Structure` の方向維持confidence 0.55を使う。比較対象は同じbaseline方向確率の固定0.55 laneとした。評価はreport 00004/00006と同じ `test2021`〜`test2026_partial` の6 foldで、EV学習seedの `test2020` を除外する。entryはdecision bar open、exitは同bar close、loss multiplierは1.0、round-trip costは実spread中央値 `0.260/oz` である。

registryのbroad/balanced/selective championは設定JSONだけが残り、指定prediction parquetは現在の `/srv/trade/experiments` から取得できなかった。不要な再学習を避け、現存するprecision championだけを監査した。

## 結果

| lane | rows | accuracy | gross mean / oz | spread後 mean / oz | gross positive folds | spread後 positive folds | all-fold cost ceiling / oz | cost headroom / oz |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| baseline 0.55 | 9,840 | 54.6748% | +0.13095 | -0.12905 | 5/6 | 3/6 | -0.03431 | -0.29431 |
| Structure 0.55 | 9,523 | 55.0982% | +0.15625 | -0.10375 | 5/6 | 3/6 | -0.02731 | -0.28731 |

Structureは点値でaccuracyを+0.4234pt、gross meanを`+0.02530/oz`改善した。ただし採用集合が異なるため、この差をpairedな増分効果とは解釈しない。両laneともtest2023がcost前からnegativeで、Structureも127件・gross `-0.02731/oz`だった。実spread後は3/6 foldだけpositiveで、aggregateも`-0.10375/oz`である。

## 判断

`Intrabar Structure 0.55` は方向精度用の既存forward candidateとしては維持するが、TitanFX XAUUSD-mの売買laneとしては **reject / NoTrade** とする。高精度選別はgross edgeを増やしたものの、実spreadを超えず、全fold positive gateにも失敗した。閾値をさらに上げる、subgroupを除く、保有期間を変えるなどの履歴内救済探索は行わない。

authoritative confidence、fair odds、candidate registry、paper/live policyは変更しない。完全未使用期間の予測精度監視と、spreadの薄い別銘柄のcost-first監査を分離して続ける。

## 成果物と検証

- baseline: `experiments/next_bar_ev/m15_baseline_055_cost_audit_001.json`
- Structure: `experiments/next_bar_ev/m15_intrabar_structure_055_cost_audit_001.json`
- source prediction: `experiments/next_bar/intrabar_structure_confidence_blend_001/m15_walk_forward_predictions.parquet`
- fixed config: `methods/next_bar/config/m15_intrabar_structure_confidence_candidate_v1.json`
- registry: `methods/next_bar/config/m15_candidate_registry_v1.json`
- cost診断はlow-priority worker、CPU only、再学習なしで実行
