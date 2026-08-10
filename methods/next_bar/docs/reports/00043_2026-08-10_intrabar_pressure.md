# 00043 Intrabar pressure

日時: 2026-08-10 15:09 JST

## 目的

Intrabar Profileで有効だった完成M15内のM1情報を、途中終値trajectoryとは別の買い／売り圧力proxyへ加工する。M1 volumeは全履歴で0なので使わず、M1 OHLCのclose location、body、wick、rangeだけを定常化し、Profileへの増分とM15方向精度を検証する。

## 結果前に固定した特徴

`--feature-set intrabar_pressure` は親のIntrabar Profileへ次の11特徴を追加する。

- M1 close-location valueの平均、標準偏差。
- 序盤1/3、終盤1/3の平均と終盤−序盤。
- M1 rangeで重み付けしたclose-location。
- M1方向×rangeのsigned range pressure。
- lower wick−upper wickを総M1 rangeで割ったwick pressure。
- M1 body合計を総M1 rangeで割ったbody pressure。
- range-weighted close-locationとbody pressureの乖離。
- M1 close-location方向とbody方向の一致率。

すべて完成済みM1だけを使い、raw価格水準を含まない。OHLC全体のscale変更で特徴が変わらないこと、未来M1改変で過去特徴が変わらないこと、flat足で有限な意味的ゼロになること、38 intrabar特徴のstationary guard、artifact保存・最新推論をテストした。

HGB、Platt、M15 7fold、25% blendは既存固定条件を使い、結果後に特徴subset、weight、閾値を変更していない。

## 単体方向モデル

| period | baseline accuracy | pressure single accuracy |
|---|---:|---:|
| development | 52.014% | 52.040% |
| confirmation | 51.501% | 51.560% |
| all | 51.816% | 51.855% |

単体はdevelopment/confirmationの両方、5/7 foldで改善したが、全体fixes 9,875対harms 9,819、p=0.695で差は弱い。単体置換はしない。

## 通常25%方向blend

| period | model | accuracy | Brier | log loss | ECE |
|---|---|---:|---:|---:|---:|
| development | baseline | 52.014% | 0.2493466 | 0.6918398 | 0.377% |
| development | pressure blend | 52.072% | 0.2492915 | 0.6917288 | 0.276% |
| confirmation | baseline | 51.501% | 0.2495525 | 0.6922506 | 0.298% |
| confirmation | pressure blend | 51.565% | 0.2495295 | 0.6922047 | 0.230% |
| all | baseline | 51.816% | 0.2494261 | 0.6919985 | 0.347% |
| all | pressure blend | 51.876% | 0.2493834 | 0.6919126 | 0.258% |

accuracyは5/7、Brier/log lossは7/7、ECEは4/7 fold改善した。baseline誤り修正2,548件、新規誤り2,461件、純改善87件、McNemar exact p=0.224である。

方向精度の差は統計的に強くないが、事前固定した同じ式がdevelopmentとconfirmationの両方でaccuracy・Brier・log lossを改善し、年別proper scoreも全foldで再現した。現行置換ではなく、完全未使用期間へ出すparallel direction candidateとする。

## 親Profile方向blendとの比較

| period | Profile blend accuracy | Pressure blend accuracy |
|---|---:|---:|
| development | 52.089% | 52.072% |
| confirmation | 51.439% | 51.565% |
| all | 51.838% | 51.876% |

PressureはdevelopmentでProfileを0.017pt下回るが、confirmationで+0.127pt、全体で+0.039pt。confirmation paired p=0.0577で、親Profileが失った期間外方向edgeを回復した。一方、fold勝敗は4/7、親に対するBrier/log loss改善も2/7なので、親を一貫して上回るとは判断しない。

## Confidence用途は棄却

development目的関数が選んだ方向維持threshold 0.53は、development scoreを0.02027から0.02148へ上げたが、confirmationではaccuracy 54.479%から54.134%、score 0.01511から0.01364へ悪化した。

親Profileと同じ0.515でもPressureはProfileにdevelopment、confirmation、allのaccuracy/scoreをすべて下回り、fold勝敗3/7だった。Pressure特徴をconfidence registryへ追加しない。

## 最新推論

同じ60/20/20 splitと主要学習設定のbaseline/Pressure artifactを作り、共通runtime blend経路を通した。2026-06-01 04:45 UTC判定はbaseline up 0.577254、Pressure up 0.583284、75/25 blend up 0.578761だった。artifact parityは通過した。

このdirection candidateには経験的odds校正を接続していないため `odds_valid=false`、`strict_prediction_eligible=false` である。

## 成果物と判断

- OOS単体: `experiments/next_bar/walk_forward_intrabar_pressure_001`
- 通常25% blend: `experiments/next_bar/ensemble_intrabar_pressure_25_001`
- 方向維持blend: `experiments/next_bar/intrabar_pressure_confidence_blend_001`
- 分析: `experiments/next_bar/intrabar_pressure_candidate_analysis.json`
- Profile 0.515比較: `experiments/next_bar/intrabar_pressure_vs_profile_0515_analysis.json`
- latest baseline: `experiments/next_bar/baseline_m15_latest_artifact_001`
- latest Pressure: `experiments/next_bar/intrabar_pressure_m15_latest_artifact_001`
- latest ensemble: `experiments/next_bar/intrabar_pressure_m15_latest_ensemble_001`
- 固定設定: `methods/next_bar/config/m15_intrabar_pressure_direction_candidate_v1.json`

通常25%方向blendだけをparallel forward candidateとして採用する。単体方向、0.53 confidence、0.515 confidenceは棄却する。fresh期間でaccuracy、Brier、log lossがbaseline以上の場合だけauthoritative方向候補への昇格を検討する。損失倍率は標準1.0のみとする。
