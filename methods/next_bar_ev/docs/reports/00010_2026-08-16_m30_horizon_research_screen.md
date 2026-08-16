# 00010 M30 horizon research screen

日時: 2026-08-16 09:41 JST

## 目的

M30 baseline confidence 0.55がaggregateでは実spread後に僅かに正だったため、独立M60以上のモデルを新規学習する前に、同じM30方向を固定1/2/4本保有した場合のcost余力を診断した。これはreport 00009の結果後に行うresearch-priority screenであり、好結果でも売買policyには採用しない。

## 固定仕様

- source: Windows canonical M30 baseline OOS 71,260行
- confidence: 0.55
- evaluation: `test2021`〜`test2026_partial`、seed `test2020`除外
- holding: 1/2/4 M30 bars（30/60/120分）
- entry: decision M30 bar open
- exit: 指定本数目のM30 bar close
- direction: decision時点のM30予測を保有中固定
- round-trip spread: `0.260/oz`
- loss multiplier: 1.0

途中に欠損barがある区間は除外する。holding、threshold、directionを結果に合わせて変更しない。

## 結果

| holding | rows | accuracy | gross mean / oz | spread後 mean / oz | gross positive folds | spread後 positive folds | all-fold cost ceiling / oz |
|---|---:|---:|---:|---:|---:|---:|---:|
| 30分 | 4,253 | 54.6203% | +0.28154 | +0.02154 | 5/6 | 3/6 | -0.06162 |
| 60分 | 4,136 | 54.1828% | +0.19974 | -0.06026 | 4/6 | 3/6 | -0.20269 |
| 120分 | 3,851 | 53.8821% | +0.36225 | +0.10225 | 6/6 | 4/6 | +0.03700 |

60分は30分よりaccuracy、gross、fold安定性が悪化した。120分は全6 foldでgross positiveとなりaggregate spread後も正だが、test2021/2022は`-0.22300/-0.11847/oz`である。最弱fold gross `+0.036996/oz`はspread中央値`0.260/oz`の約14.2%だけで、commission/slippage前でもall-fold gateに届かない。

120分の改善はこのscreenで観測した結果であり、独立M120モデルや8本以上の延長を履歴内で追跡する採用根拠にはしない。overlapする保有損益でもあり、独立tradeのstateful capital利用を表さない。

## 判断

固定60分・120分保有は **reject / NoTrade**。独立M60/M120モデルの新規学習も現時点では見送る。60分は方向edgeが減衰し、120分も実spreadに対する最弱期間の余力が不足するため、計算資源と候補数を増やす価値がない。

XAUUSD-mについて追加holding、閾値、session、volatility filterを探索しない。M30 prediction candidateは予測品質のfresh監視に限定し、利益率研究はFX shortlistの実測cost-first screenを優先する。

## 成果物

- `experiments/next_bar_ev/m30_baseline_055_fixed_horizon_diagnostic_001.json`
- 実行: low-priority worker、CPU only、再学習なし
