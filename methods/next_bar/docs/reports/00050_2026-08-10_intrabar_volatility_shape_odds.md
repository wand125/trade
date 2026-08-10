# 00050 Intrabar Volatility Shape direction odds

日時: 2026-08-10 16:33 JST

## 目的

M15 Volatility Shapeはbaselineと予測方向が変わる独立方向候補である。このため、baseline方向を維持するconfidence blendではなく、Shape自身が出した方向の正答確率を直接オッズとして評価する。固定信頼度帯の再現性、時系列nested校正、baselineとの同一行比較、最新推論の局所gateを分けて検証した。

## 固定帯の信頼度

development 89,083件では全体accuracy 52.275%、mean confidence 52.445%で全体区間は整合した。帯別accuracyは信頼度とともに単調増加し、順序付け自体は良い。一方、累積閾値0.515、0.525、0.550はmean confidenceがWilson上限を超え、0.535だけが局所整合した。特に0.550以上はaccuracy 55.345%に対してmean 56.692%で、強い側を過信している。

confirmation 56,057件では全体accuracy 51.583%、mean confidence 51.817%で局所整合した。累積0.515〜0.550もすべて局所整合し、Wilson下限が50%を超えた。

| threshold | rows | coverage | accuracy | mean confidence | Wilson lower | locally consistent |
|---:|---:|---:|---:|---:|---:|:---:|
| 0.515 | 28,274 | 50.438% | 52.525% | 52.891% | 51.943% | yes |
| 0.525 | 15,228 | 27.165% | 53.428% | 53.690% | 52.635% | yes |
| 0.535 | 7,128 | 12.716% | 54.237% | 54.524% | 53.078% | yes |
| 0.550 | 1,697 | 3.027% | 56.158% | 55.855% | 53.786% | yes |

ただしbaselineとの選別比較では、confirmationの0.515、0.525、0.535 accuracyはbaselineの52.574%、53.777%、54.935%がShapeを上回った。Shapeが上回る0.550も56.158%対55.750%だが1,697件とsupportが小さい。Shape confidenceは自身の方向確率として使えるが、高信頼選別championにはしない。

## Nested odds

各評価foldより前のOOS foldだけを校正資料にした121,950件で比較した。Shapeの生model confidenceが選ばれ、追加の階層実績校正は棄却された。

| source | accuracy | mean confidence | Brier | log loss | ECE |
|---|---:|---:|---:|---:|---:|
| Shape model confidence | 51.7532% | 52.1731% | 0.24958237 | 0.69231269 | 0.4199% |
| Shape empirical recalibration | 51.7532% | 52.5744% | 0.24977470 | 0.69269988 | 0.9363% |
| baseline model confidence | 51.6220% | 52.1469% | 0.24958731 | 0.69232248 | 0.5250% |

Shape model confidenceは同一121,950件でbaselineよりaccuracy +0.1312pt、Brier -0.00000494、log loss -0.00000979、ECE -0.1051ptだった。null Brier 0.24969264も下回り、全体gateは通る。ただし2022 foldのECEは1.012%で、全fold一律の強い校正ではない。経験的再校正はBrier、log loss、ECEをすべて悪化させたため使わない。

baseline完全OOSを2020確認foldと2021以降foldの2ディレクトリから安全に結合できるよう、`build-odds-calibration --predictions-dir` と信頼度比較CLIをrepeatable引数へ拡張した。fold/timestampが重複する入力は拒否する。

## Side × volatility監査

aggregateの良さが特定局面だけで作られていないか確認するため、固定したpredicted direction × volatility regimeごとに同じ信頼度帯を再集計する汎用CLIを追加した。confirmationの0.535以上は次の通りだった。

| direction | volatility | rows | accuracy | mean confidence | Wilson lower | edge |
|---|---|---:|---:|---:|---:|:---:|
| up | high | 3,778 | 54.685% | 54.675% | 53.094% | yes |
| up | low | 414 | 55.797% | 54.337% | 50.982% | yes |
| up | normal | 1,354 | 53.028% | 54.492% | 50.365% | yes |
| down | high | 755 | 56.026% | 54.239% | 52.464% | yes |
| down | low | 263 | 51.331% | 54.278% | 45.314% | no |
| down | normal | 564 | 51.950% | 54.228% | 47.828% | no |

upは全volatilityでedge下限を通る一方、downはhighだけが通った。down-low/normalはdevelopmentの同閾値ではedgeが見えていたため、固定的なモデル特性ではなく期間driftの可能性が高い。また同じ0.535でbaselineはupの全3 regimeでShapeよりaccuracyが高く、Shapeが高信頼選別championでない判断とも整合する。

この非対称性を使って「upまたはdown-highだけ」に絞るとconfirmation後付けになるため、採用gateにはしない。fresh期間では同じ6セルを変更せず監視し、少数supportでWilson区間が広いセルを平均accuracyへ混ぜて隠さない。

## Runtime shadow

Shape単体weight 1.0を保存artifactから最新推論し、nested oddsを接続した。最新2026-06-01 04:45 UTCはup、confidence 56.4871%、fair decimal odds表示値1.7703だった。対応するside/regime/binは5,260件、実績55.1743%、Wilson区間53.8869〜56.4547%である。

model confidenceが局所上限を0.0324ptだけ上回ったため `odds_locally_consistent=false`、`odds_calibration_gate_passed=false` となった。さらに運用認可を与えていないため `odds_valid=false`、`strict_prediction_eligible=false` のままである。局所gateが実際に過信を止めることを確認した。

再現コマンド:

```bash
env PYTHONPATH=src .venv/bin/python methods/next_bar/scripts/predict_latest_ensemble.py \
  --input data/processed/histdata/xauusd/xauusd_m1.parquet \
  --baseline-model-dir experiments/next_bar/baseline_m15_latest_artifact_001 \
  --candidate-model-dir experiments/next_bar/intrabar_volatility_shape_m15_latest_artifact_001 \
  --candidate-weight 1.0 \
  --odds-calibration experiments/next_bar/intrabar_volatility_shape_m15_direction_odds_calibration.json \
  --output experiments/next_bar/intrabar_volatility_shape_m15_latest_odds_shadow_001/latest_prediction.json \
  --parity-output experiments/next_bar/intrabar_volatility_shape_m15_latest_odds_shadow_001/parity.json
```

## 判断

Shape自身のPlatt model confidenceを、Shape方向に対応する非認可odds shadowとして採用する。階層実績再校正は使わず、authoritative fair odds、高信頼選別candidate、paper/live policyは変更しない。完全未使用期間でglobal Brier/log loss/ECE、固定帯の局所整合、Wilson edge、baselineとの方向精度を同時に確認し、すべて通るまで `--authorize-odds` は使わない。損失倍率は標準1.0のみとする。
