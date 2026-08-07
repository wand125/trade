# 00004 Standard-PnL reassessment

日時: 2026-08-07 20:05 JST

## 変更

損失1.2倍を標準採用条件から廃止した。標準は通常損益とall-in round-trip cost控除後損益。倍率指定は任意stress testだけに残す。

## M15結果

| policy | rows | accuracy | gross mean | positive folds | cost 0.05 mean | cost 0.05 positive folds | all-fold cost ceiling |
|---|---:|---:|---:|---:|---:|---:|---:|
| confidence >= 0.54 | 17,354 | 54.30% | +0.09781 | 6/6 | +0.04781 | 6/6 | 0.05415 |
| expected EV > 0 | 13,335 | 53.98% | +0.12794 | 6/6 | +0.07794 | 4/6 | 0.04122 |
| mean EV after cost > 0 | 10,450 | 54.14% | +0.13913 | 6/6 | +0.08913 | 4/6 | 0.04311 |

direction-onlyはcost 0.05後も全fold positive。ただし最弱foldのnet meanは `+0.00415`だけ。cost 0.10ではaggregate net mean `-0.00219`、positive fold 4/6へ落ちる。

EV選別はaggregate meanを上げるが、2021/2022年がcost 0.05後negativeになり、期間再現性を損なった。conservative EV after costは該当0件。

## 判断

`M15 / confidence >= 0.54 / next bar open-to-close / fixed 1 oz` をpaper candidateへ昇格する。実測all-in costが0.05以下であることと、新規forward期間のpositiveを確認するまでライブ発注はしない。Kelly sizingは無効。

固定設定: `methods/next_bar_ev/config/m15_paper_policy_v1.json`
