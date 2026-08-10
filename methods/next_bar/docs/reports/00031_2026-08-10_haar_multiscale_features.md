# 00031 Haar multiscale features

日時: 2026-08-10 13:07 JST

## 目的

履歴の数値をそのまま並べず、直近経路の加速・減速・反転を複数スケールの前半対後半差へ圧縮し、M15次足方向とconfidence選別を改善できるか確認する。

## 結果前に固定した方法

- feature set: `--feature-set haar_multiscale`
- model: baselineと同じHGB、Platt calibration、expanding training。
- 4/8/16/32本の各窓を前半・後半へ二分し、次の3系列をHaar detailとして追加した。
  - 合計log return差を窓内volatilityで標準化
  - absolute return合計差を窓全体absolute returnで標準化
  - return方向平均差を[-1, 1]へ標準化
- 合計12特徴。raw OHLC価格水準は含めない。
- M15 2020〜2026途中の同一7fold。通常25% blendとbaseline方向を維持する25% confidence blendを比較した。
- confidence閾値はdevelopment 2020〜2023の固定gridで選び、confirmation 2024〜2026途中へ固定した。

未来側OHLCを改変しても過去特徴が変わらないこと、stationary feature guard、artifact保存、最新推論をテストした。

## 評価フローの恒久化

従来の一時ファイルによるcandidate比較を `methods/next_bar/scripts/analyze_candidate.py` としてリポジトリへ移した。このスクリプトは入力整列を検証し、development/confirmation、固定grid、Wilson下限を使うselection score、年別改善、Brier/log loss/ECE、通常blendのpaired exact testを同じ形式で出力する。今回の結果は `experiments/next_bar/haar_multiscale_candidate_analysis.json` に保存した。

## 単体と通常blend

| period | model | accuracy | Brier | log loss | ECE |
|---|---|---:|---:|---:|---:|
| development | baseline | 52.014% | 0.2493466 | 0.6918398 | 0.377% |
| development | Haar single | 52.016% | 0.2493864 | 0.6919211 | 0.355% |
| confirmation | baseline | 51.501% | 0.2495525 | 0.6922506 | 0.298% |
| confirmation | Haar single | 51.362% | 0.2495783 | 0.6923023 | 0.436% |
| all | baseline | 51.816% | 0.2494261 | 0.6919985 | 0.347% |
| all | Haar single | 51.763% | 0.2494605 | 0.6920684 | 0.386% |

単体はconfirmationと全体で全主要指標が悪化したため方向モデルとして棄却する。

通常25% blendはdevelopment accuracyを52.014%から52.053%へ上げたが、confirmationは51.501%から51.446%へ低下した。全体の純改善は3件だけで、誤り修正1,905件、新規誤り1,902件、McNemar exact p=0.974であり方向edgeではない。

## 方向維持型confidence blend

| period | metric | baseline | candidate |
|---|---|---:|---:|
| development | Brier | 0.2493466 | 0.2493302 |
| development | log loss | 0.6918398 | 0.6918067 |
| development | ECE | 0.377% | 0.337% |
| confirmation | Brier | 0.2495525 | 0.2495471 |
| confirmation | log loss | 0.6922506 | 0.6922398 |
| confirmation | ECE | 0.298% | 0.278% |
| all | Brier | 0.2494261 | 0.2494139 |
| all | log loss | 0.6919985 | 0.6919740 |
| all | ECE | 0.347% | 0.314% |

proper scoreはdevelopment/confirmationの両方で改善したが、fold改善はBrier 5/7、log loss 5/7、ECE 6/7だった。

## developmentで選んだconfidence 0.525 lane

| period | model | rows | coverage | accuracy | selection score |
|---|---|---:|---:|---:|---:|
| development | baseline | 33,770 | 37.908% | 53.858% | 0.02048 |
| development | Haar blend | 33,267 | 37.344% | 53.996% | 0.02115 |
| confirmation | baseline | 14,785 | 26.375% | 53.777% | 0.01527 |
| confirmation | Haar blend | 14,600 | 26.045% | 53.733% | 0.01492 |
| all | baseline | 48,555 | 33.454% | 53.834% | 0.01961 |
| all | Haar blend | 47,867 | 32.980% | 53.916% | 0.01992 |

developmentの改善はconfirmationで反転した。accuracyとselection scoreのfold改善は4/7である。confidence 0.60以上の全体accuracy 59.722%は360件、coverage 0.248%しかなく、採用根拠には使わない。

## 既存候補との比較

clear-body HGB 0.525はconfirmation coverage 24.714%、accuracy 54.201%、selection score 0.01675、全体31.419%、54.182%、0.02088である。Haar版はcoverageを広く取るがconfirmation accuracyとscoreがbaseline以下で、clear-bodyを超えない。

## 最新推論確認

全期間60%/20%/20%で別artifactを作成し、データ末尾まで `predict-latest` を実行した。2026-06-01 04:45 UTC判定はup、model confidence 0.55930だった。これは保存・推論経路の機能確認値で、有効なempirical oddsではない。

## 判断

- Haar単体と通常方向blendは棄却する。
- 方向維持型blendはproper scoreを改善するが、developmentで選んだ0.525 laneがconfirmationで悪化するため採用しない。
- forward/shadow configは発行しない。実装は再現用に残し、同じ履歴で窓長、系列、blend weight、閾値を再探索しない。
- authoritative confidence、odds、現行policy、paper policyは変更しない。損失倍率は標準1.0のみとする。
