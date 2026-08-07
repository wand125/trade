# 00006 Context abstention confirmation

日時: 2026-08-07 18:21 JST
更新日時: 2026-08-07 18:21 JST

## 目的

方向モデルを変更せず、加工contextに基づいて弱い局面を見送り、次足予測のaccuracyとcoverageを管理する。

## 候補固定

2022〜2026途中の5fold診断から、追加確認前に以下を固定した。

- M1: calibration期間のvolatility_20分位に対するhigh regime
- M5: decision UTC hour 21
- M15: high volatility regime
- M30: decision UTC hour 21

M30のhigh-volatility AND hour21は合算52.76%へ低下したため候補に含めなかった。

確認には条件発見に使っていない2020/2021 foldを使用した。

## 確認fold

| TF/context | 2020 accuracy | 2020 balanced | 2021 accuracy | 2021 balanced |
|---|---:|---:|---:|---:|
| M1 high vol | 51.72% | 51.80% | 51.26% | 51.24% |
| M5 UTC21 | 52.66% | 53.22% | 53.79% | 54.18% |
| M15 high vol | 53.22% | 53.07% | 52.70% | 52.65% |
| M30 UTC21 | 56.14% | 56.53% | 59.04% | 59.42% |

## 7fold合算

| TF/context | rows | coverage | accuracy | balanced | worst fold |
|---|---:|---:|---:|---:|---:|
| M1 high vol | 920,234 | 42.14% | 51.15% | 51.13% | 50.56% |
| M5 UTC21 | 16,825 | 3.82% | 52.35% | 52.50% | 49.52% |
| M15 high vol | 62,035 | 42.74% | 52.08% | 51.89% | 50.74% |
| M30 UTC21 | 2,720 | 3.82% | 55.29% | 55.14% | 51.33% |

## 判断

- `context_policy_v1.json` として予測abstention層へ採用する。
- M1/M15/M30は全7foldで50%超。M30が最も強い。
- M5は確認foldでは再現したが、2025 foldが49.52%のため暫定採用・監視対象。
- これは売買policyではない。context外でも方向値は計算するが、`prediction_eligible=false`として正答率評価の対象から見送る。
- 出力にはモデル固有confidenceと、7foldのcontext reference accuracy/worst-fold accuracyを別々に保持する。
