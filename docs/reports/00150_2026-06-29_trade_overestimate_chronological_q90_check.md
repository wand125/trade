# Trade Overestimate Chronological Q90 Check

日時: 2026-06-29 16:05 JST
更新日時: 2026-06-29 16:08 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻である `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## 目的

`00148` / `00149` の `q90 w2.0` はleave-one-month OOF validationと2025-05 fixed applyでPnLを改善した。

ただし、leave-one-month OOFではholdout月より後ろの月もfit側に入る。今回は `oof-trade-overestimate-model` にchronological / expanding OOFを追加し、対象月より前だけでfitしたときに `q90 w2.0` がまだ機能するかを確認する。

## 実装

`oof-trade-overestimate-model` に以下を追加した。

- `--oof-scheme leave_one_month|expanding`
- `--min-train-months`

デフォルトは従来通り `leave_one_month`。`expanding` ではholdout月より前の月だけをfitに使い、訓練月数が足りないfoldはskipしてmetricsへ記録する。

今回は `min_train_months=3` とし、以下のfoldだけを評価した。

| holdout | fit months |
|---|---|
| 2025-02 | 2024-11, 2024-12, 2025-01 |
| 2025-03 | 2024-11, 2024-12, 2025-01, 2025-02 |
| 2025-04 | 2024-11, 2024-12, 2025-01, 2025-02, 2025-03 |

## Chronological Model Metrics

対象は2025-02..2025-04のselected trades 281件。

| metric | leave-one-month OOF | chronological OOF |
|---|---:|---:|
| trade count | `502` | `281` |
| target mean | `18.2772` | `5.3943` |
| predicted mean | `17.7814` | `4.3290` |
| bias | `-0.4958` | `-1.0652` |
| MAE | `8.3937` | `5.5006` |
| RMSE | `11.6532` | `8.9442` |
| R2 | `0.1273` | `0.0145` |
| high-overestimate AUC | `0.6814` | `0.6328` |

AUCは残っているが、R2と予測スケールが大きく落ちた。特にtarget meanが低い後半3ヶ月だけを見ると、leave-one-monthで見えていたamount水準は維持されない。

## Fixed Q90 W2.0 Apply

`q90 w2.0` のthresholdとlambdaは `00148` の候補から固定し、今回のchronological結果では再調整しない。

| side | fixed threshold | chronological prediction max | active rows |
|---|---:|---:|---:|
| long | `18.8171` | `7.1065` | `0 / 85361` |
| short | `21.1886` | `7.8064` | `0 / 85361` |

固定q90 thresholdを超える行が一つもなく、overestimate penaltyは発火しなかった。

backtest結果:

| month | baseline PnL | leave-one-month q90 PnL | chronological q90 PnL | chrono - base | chrono - LOO |
|---|---:|---:|---:|---:|---:|
| 2025-02 | `113.1642` | `114.1328` | `113.1642` | `0.0000` | `-0.9686` |
| 2025-03 | `27.1660` | `26.1734` | `27.1660` | `0.0000` | `0.9926` |
| 2025-04 | `14.3072` | `25.6666` | `14.3072` | `0.0000` | `-11.3594` |
| total | `154.6374` | `165.9728` | `154.6374` | `0.0000` | `-11.3354` |

`model-trade-delta` でも3ヶ月すべて `common` のみで、`only_base` / `only_candidate` は0。stateful blocking costも0。chronological q90はbaselineと完全に同じ取引になった。

## Target Quantile Threshold Check

次候補として置いていた「fit側selected-trade target分位でthresholdを決める方式」も確認した。apply月やholdout月の分布は使わず、各foldのfit月だけからside別target q90を計算した。

| holdout | long target q90 | short target q90 |
|---|---:|---:|
| 2025-02 | `10.9981` | `13.3550` |
| 2025-03 | `12.8793` | `13.4113` |
| 2025-04 | `11.0345` | `13.5405` |

これもchronological prediction maxより高く、q90方式としては発火しない。したがって問題はthresholdの参照元だけではなく、chronological fit時のamount prediction scaleが低く潰れる点にある。

## 判断

1. `q90 w2.0` は候補から完全には捨てないが、標準policyへ昇格しない。
2. leave-one-month OOFの改善 `+11.3354` は、過去fitだけのchronological条件では再現しなかった。
3. 2025-05 fixed applyの改善は残っているが、`00149` のdelta診断でonly_candidateが弱く、今回のchronological反証も出たため、単独採用するには根拠が不足している。
4. 次は q90 thresholdの微調整ではなく、chronologicalでcalibration可能なamount/risk scaleを作る。候補はclassification化、fold-local calibration、support-aware shrinkage、またはstateful/context downside targetとの統合。
5. 追加未使用月が作れる場合は、今回のchronological設計を優先し、未来月をfitに入れない。

## Artifacts

- chronological overestimate model: `experiments/20260629_070057_trade_overestimate_amount_expanding_min3_highcost_risk5/`
- chronological fixed q90 predictions: `data/reports/modeling/20260629_1601_trade_overestimate_chronological_excess_risk/`
- chronological q90 backtests: `data/reports/backtests/20260629_trade_overestimate_chronological_q90_w2p0_validation/`
- chronological delta: `data/reports/backtests/20260629_070355_trade_overestimate_chronological_q90_w2p0_delta_validation/`

## 検証

- `python3 -m unittest tests.test_meta_model`: pass
- `python3 -m unittest tests.test_backtest tests.test_docs_reports`: pass
- `git diff --check`: pass

## 次の作業

1. chronologicalでamount予測スケールが潰れる理由を、月別target分布・fit sample size・shrinkage・high target偏在で分解する。
2. amount回帰を直接penaltyに使わず、high-overestimate分類やfold-local calibrated riskへ変換する。
3. `q90 w2.0` は単独標準候補ではなく、stateful/context downside targetとのstacking/ranking特徴として扱う。
