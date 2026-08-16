# 00012 M15 broad lane live-cost audit

日時: 2026-08-16 18:49 JST

## 目的

既存M15 candidate registryのbroad laneを、TitanFX XAUUSD-mの実spreadで固定診断する。閾値、モデル、方向、保有期間を履歴結果に合わせて変更せず、保存済みWindows canonical予測だけを使う。

## 固定対象

同一Windows platformに揃うProfileとDistribution Shiftの方向維持confidence 0.515を比較した。評価は従来のlive-cost auditと同じ`test2021`〜`test2026_partial`の6 foldで、EV学習seedの`test2020`を除外した。entryはdecision bar open、exitは同bar close、holdingは1本（15分）、loss multiplierは1.0、round-trip costはEA snapshot 9,458件（2026-08-11〜08-15）の実spread中央値`0.260/oz`である。

registryのbalanced/selective championが指定するprediction parquetは現在の`/srv/trade/experiments`にない。不要な再学習を避け、取得済みbroad artifactだけを監査した。

## 結果

| lane | rows | accuracy | gross mean / oz | spread後 mean / oz | gross positive folds | spread後 positive folds | all-fold cost ceiling / oz | cost headroom / oz |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Profile 0.515 | 67,497 | 52.5653% | +0.03323 | -0.22677 | 6/6 | 0/6 | +0.00050 | -0.25950 |
| Distribution Shift 0.515 | 66,189 | 52.6946% | +0.03952 | -0.22048 | 6/6 | 0/6 | +0.00972 | -0.25028 |

Distribution Shiftは点値でaccuracyを+0.1293pt、gross meanを`+0.00629/oz`上回った。ただし採用集合が異なるためpairedな増分効果とは解釈しない。両laneともgrossは6/6 fold正だが、spread後は全fold負である。Shiftのall-fold cost ceiling `0.00972/oz`も実spread中央値の約3.7%にすぎない。

## 判断

Profile 0.515とDistribution Shift 0.515は予測品質研究上のbroad candidateとして維持するが、TitanFX XAUUSD-mの売買laneとしては両方を **reject / NoTrade** とする。広いcoverageの小さなgross edgeは実spreadを吸収できない。閾値を上げる、subgroupを除く、holdingを変えるなどの履歴内救済探索は行わない。

authoritative confidence、fair odds、candidate registry、paper/live policyは変更しない。balanced/selectiveはprediction artifactが安全に取得できた場合だけ同じ固定診断へ通す。

## 成果物と検証

- Profile: `experiments/next_bar_ev/m15_profile_windows_0515_cost_audit_001.json`
- Distribution Shift: `experiments/next_bar_ev/m15_distribution_shift_windows_0515_cost_audit_001.json`
- source predictions: Windows canonical confidence blend 2本
- cost診断は`run_low_priority_worker.sh`、CPU only、再学習なし
- runtime/account/credential変更なし
