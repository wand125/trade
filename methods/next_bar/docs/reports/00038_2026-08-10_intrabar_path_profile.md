# 00038 Intrabar path profile

日時: 2026-08-10 14:07 JST

## 目的

既存intrabar structureがM15内部の高値・安値時刻、反転率、経路効率を要約した後に捨てていた途中経路の形を利用する。完成済み15本のM1を価格水準ではなくM15レンジ内の正規化trajectoryへ加工し、次足方向とconfidenceのcoverage-aware objectiveを改善できるか検証する。

## 結果前に固定した特徴

既存intrabar 15特徴へ次の12特徴を追加した。

- M15始値から各M1終値までの変位を完成M15 high-low rangeで割った20%、40%、60%、80%地点のlevel。
- M15始値から最終終値までを結ぶ直線trajectoryに対する同4地点のdeviation。
- 全15地点のmean deviation、RMS deviation、maximum deviation、minimum deviation。

M15が完成した判定時に同じ足内の15本だけを使用する。raw価格水準を特徴へ含めず、全OHLCへの一定加算で特徴が変わらない。未来側M1を変更しても過去完成M15特徴が変わらないこと、54特徴すべてのstationary guard、artifact保存・最新推論をテストした。実装名は `--feature-set intrabar_profile`。

HGB parameter、Platt校正、M15 2020〜2026途中の7fold、candidate weight 25%、固定confidence gridは既存candidate規則と同じにした。結果後にprofile地点、特徴subset、weightは変更していない。

## 単体と通常blend

| period | model | accuracy | Brier | log loss | ECE |
|---|---|---:|---:|---:|---:|
| development | baseline | 52.014% | 0.2493466 | 0.6918398 | 0.377% |
| development | profile single | 52.063% | 0.2492663 | 0.6916789 | 0.421% |
| development | normal 25% blend | 52.089% | 0.2492845 | 0.6917146 | 0.280% |
| confirmation | baseline | 51.501% | 0.2495525 | 0.6922506 | 0.298% |
| confirmation | profile single | 51.394% | 0.2495533 | 0.6922525 | 0.474% |
| confirmation | normal 25% blend | 51.439% | 0.2495352 | 0.6922161 | 0.349% |
| all | baseline | 51.816% | 0.2494261 | 0.6919985 | 0.347% |
| all | profile single | 51.804% | 0.2493771 | 0.6919004 | 0.441% |
| all | normal 25% blend | 51.838% | 0.2493813 | 0.6919083 | 0.307% |

profile単体はdevelopmentだけ改善し、confirmation方向精度とproper scoreが悪化したため方向モデルとして棄却する。通常blendは全体方向精度を+0.021pt、Brier/log loss/ECEも改善したが、confirmation方向精度は-0.062ptだった。baseline誤り修正2,392件、新規誤り2,361件、McNemar exact p=0.663で方向edgeとして採用しない。

## 方向維持型confidence

方向をbaseline HGBへ固定した25% blendは、accuracyを変えず確率edgeの強さだけを補正した。

| period | metric | baseline | profile confidence |
|---|---|---:|---:|
| development | Brier | 0.2493466 | 0.2492852 |
| development | log loss | 0.6918398 | 0.6917161 |
| development | ECE | 0.377% | 0.347% |
| confirmation | Brier | 0.2495525 | 0.2495356 |
| confirmation | log loss | 0.6922506 | 0.6922169 |
| confirmation | ECE | 0.298% | 0.281% |
| all | Brier | 0.2494261 | 0.2493819 |
| all | log loss | 0.6919985 | 0.6919095 |
| all | ECE | 0.347% | 0.321% |

Brier/log lossは6/7、ECEは5/7 fold改善した。

## developmentで選んだconfidence 0.515

| period | model | rows | coverage | accuracy | selection score |
|---|---|---:|---:|---:|---:|
| development | baseline | 52,243 | 58.645% | 53.102% | 0.02048 |
| development | profile | 52,026 | 58.402% | 53.221% | 0.02134 |
| confirmation | baseline | 27,681 | 49.380% | 52.574% | 0.01395 |
| confirmation | profile | 27,651 | 49.327% | 52.743% | 0.01513 |
| all | baseline | 79,924 | 55.067% | 52.919% | 0.01909 |
| all | profile | 79,677 | 54.897% | 53.055% | 0.02007 |

accuracyとselection scoreは6/7 foldでbaselineを改善した。confirmationでもaccuracy +0.169pt、selection score +8.45%を再現し、coverage減少は0.054ptに留まる。

## Signed-body broad candidateとの比較

| period | model | threshold | coverage | accuracy | selection score |
|---|---|---:|---:|---:|---:|
| development | profile | 0.515 | 58.402% | 53.221% | 0.02134 |
| development | signed-body | 0.520 | 40.231% | 53.807% | 0.02087 |
| confirmation | profile | 0.515 | 49.327% | 52.743% | 0.01513 |
| confirmation | signed-body | 0.520 | 30.745% | 53.594% | 0.01580 |
| all | profile | 0.515 | 54.897% | 53.055% | 0.02007 |
| all | signed-body | 0.520 | 36.567% | 53.738% | 0.02004 |

profileはdevelopmentの目的関数とcoverage、全体目的関数で僅かに上回る。signed-bodyは全期間でaccuracyが高く、confirmation目的関数も高い。両方ともPareto非劣位であり、candidate registryではprofileをdevelopment objective champion、signed-bodyをaccuracy leader兼challengerとした。

## 最新推論確認

全期間60%/20%/20%でprofile単体artifactを学習し、2026-06-01 04:45 UTC判定の最新推論を実行した。出力はup、model confidence 0.546996だった。これは保存・推論経路の確認値で、profile confidence blendやempirical fair oddsではないため `odds_valid=false` のままである。

## 成果物と判断

- OOS単体: `experiments/next_bar/walk_forward_intrabar_profile_001`
- 通常25% blend: `experiments/next_bar/ensemble_intrabar_profile_25_001`
- 方向維持25% blend: `experiments/next_bar/intrabar_profile_confidence_blend_001`
- 分析: `experiments/next_bar/intrabar_profile_candidate_analysis.json`
- 最新artifact: `experiments/next_bar/intrabar_profile_latest_artifact_001`
- 固定設定: `methods/next_bar/config/m15_intrabar_profile_confidence_candidate_v1.json`

単体と通常方向blendは棄却する。方向維持0.515はdevelopment・confirmation、proper score、fold安定性を満たしたためbroad coverage forward candidateへ採用する。registryのbroad objective championをprofileへ更新し、signed-bodyをaccuracy challengerとして併走させる。authoritative confidence、fair odds、現行policy、paper policyは完全未使用期間まで置換しない。損失倍率は標準1.0のみとする。
