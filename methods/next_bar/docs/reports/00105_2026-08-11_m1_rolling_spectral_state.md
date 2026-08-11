# 00105 M1 Rolling Spectral State

日時: 2026-08-11 12:13 JST

## 目的

直近M1 returnの時系列を価格履歴のまま渡さず、固定周波数帯のenergy構成と位相へ加工して、次足方向およびconfidence rankingへ独立情報を追加できるか検証した。既存のM15 `intrabar_frequency_shape` は1本のM15内部にあるM1系列を加工するのに対し、今回は連続する完成M1足64本を時間軸として扱う。

## 固定仕様と品質

各decision時点までの直近64本のlog returnを平均除去し、DFT energyを総分散で正規化した。追加した12列は次のとおりである。

- low energy比 k1〜2、mid energy比 k3〜6、残差high energy比 k7以上
- low−high balance
- k=1/2/4/8（周期64/32/16/8本）の正規化cos/sin成分8列

window、band、frequency、HGB/Platt、通常/方向維持25% blendをOOS結果前に固定した。損失倍率は標準1.0のみである。全列は価格scale不変かつ[-1, 1]の有限値で、flat/不正/gapを含む64本窓は0へ戻す。未来行を改変しても過去特徴が変わらないこと、NumPy FFTの厳密式、10倍価格scale、gap後64行、stationary feature guard、保存artifactからのlatest推論をテストした。

2019年以降train、2020〜2026途中testの固定7foldで、baselineと同じ2,183,717行を生成した。fold/timestamp/targetの重複・欠損はない。

成果物QAで、共通OOS ensemble関数が更新後の `probability_up` / `confidence` に対し、`probability_down` / `class_confidence` をbaseline値のまま残す既存不整合を検出した。評価は `probability_up` を使用するため下記結果には影響しないが、共通実装を補数・同一confidenceで再計算するよう修正し、回帰テストを追加した。今回の5 prediction artifactはすべて再生成し、2,183,717行のkey整列、重複0、有限[0,1]、up+down=1、class confidence一致を確認した。

## 単体とbaseline blend

| candidate | development accuracy | confirmation accuracy | all accuracy | all Brier |
|---|---:|---:|---:|---:|
| baseline | 50.93738% | 50.60001% | 50.80695% | 0.249868880 |
| Spectral単体 | 50.92693% | 50.60048% | 50.80072% | 0.249869205 |
| baseline 75% + Spectral 25% | 50.94821% | 50.61280% | 50.81854% | 0.249862990 |

単体はbaselineを下回るため採用しない。通常25% blendはbaseline比development +145件、confirmation +108件、all +253件で、accuracyは5/7fold改善した。ただしexact paired p=0.3052、UTC日paired bootstrap 20,000回のall accuracy差95%区間は-0.01115〜+0.03410ptで、方向改善は確定しない。

一方、通常blendのBrier差はall -0.000005890、95%区間[-0.000007829, -0.000003994]、confirmationも[-0.000004313, -0.000000559]で、log lossとともにdevelopment/confirmation/allで改善した。周波数状態には弱い確率整形情報がある。

## 既存方向・proper-score候補との比較

Path Persistence 25%はall accuracy 50.85009%で、Spectral 25%の50.81854%を上回った。Spectralはaccuracy 1/7fold、all差95%区間-0.05519〜-0.00819ptで、方向point championを置換できない。

Distribution Shift 25%はall accuracy 50.84629%、Brier 0.249857850で、Spectralをaccuracy 7/7fold、proper scoreでも上回った。Spectral−Shiftのall Brier差95%区間は[+0.000002250, +0.000008025]、confirmationも[+0.000000298, +0.000006229]でSpectral悪化が確定した。baseline比proper-score改善だけでは既存stability/proper-score役割への追加根拠にならない。

## confidenceと高信頼度tail

development gridでは方向維持Spectralの0.51が最大selection scoreだった。

| period | threshold | accuracy | coverage | selection score |
|---|---:|---:|---:|---:|
| development | 0.510 | 51.61858% | 43.5276% | 0.009832 |
| confirmation | 0.510 | 51.79330% | 23.7587% | 0.007675 |
| all | 0.510 | 51.66330% | 35.8848% | 0.009301 |
| confirmation | 0.525 | 54.78223% | 1.3598% | — |
| confirmation | 0.535 | 56.58915% | 0.2598% | — |
| confirmation | 0.550 | 54.83871% | 0.0147% | — |
| all | 0.550 | 55.27407% | 0.7953% | — |

confidence上昇に伴うaggregate精度上昇は見えるが、confirmation 0.55は124件しかない。all 0.55もmean confidence 56.1976%に対してaccuracy 55.2741%で約0.924pt過信しており、odds用途の根拠にはならない。

同coverage役割のDistribution Shift 0.51はall accuracy 51.75361% / coverage 35.6128% / score 0.009802で、Spectralよりaccuracy +0.0903pt、score +0.000501だった。直接比較はSpectral 1/7fold、all日次bootstrapのSpectral−Shift accuracy差区間-0.13340〜-0.04645pt、score差区間-0.000759〜-0.000239で、Shift優位が確定した。

## 直交成分としての追加監査

置換ではなく多様化成分として使える可能性を調べるため、weight探索をせず、Distribution Shift 25% blendとSpectral 25% blendを50/50平均した。実質weightはbaseline 75%、Shift 12.5%、Spectral 12.5%である。

三者blendはall accuracy 50.82852%、Brier 0.249859318で、Shift 25%の50.84629% / 0.249857850を下回り、accuracy 1/7foldだった。0.51 confidenceも51.71436% / coverage 35.6561% / score 0.009574で、Shiftの51.75361% / 35.6128% / 0.009802に負けた。all score差95%区間は-0.000411〜-0.000044で、単純な多様化追加にも増分edgeはない。

## 判断

`rolling_spectral_state` を再現・将来の独立研究用feature setとして残すが、方向、confidence、oddsの候補には採用しない。baseline比proper scoreの改善は再現したものの、Pathの方向精度、Distribution Shiftの方向安定性・proper score・0.51目的関数をすべて下回り、等重み追加でも改善しなかった。

同じ履歴でwindow、frequency、band、phase subset、blend weight、thresholdを再探索しない。config、candidate registry、authoritative方向/confidence、fair odds、adoption/paper/live policyは変更しない。runtime latestも発行しない。

## 成果物

- feature/test: `src/trade_data/next_bar.py`, `tests/test_next_bar.py`
- OOS: `experiments/next_bar/walk_forward_rolling_spectral_state_m1_fixed_001`
- baseline blends: `experiments/next_bar/rolling_spectral_state_m1_blend_fixed_001`, `experiments/next_bar/rolling_spectral_state_m1_confidence_fixed_001`
- candidate/subgroup analysis: `experiments/next_bar/rolling_spectral_state_m1_candidate_analysis.json`, `experiments/next_bar/rolling_spectral_state_m1_confidence_subgroups.json`
- champion comparisons: `experiments/next_bar/rolling_spectral_state_vs_path_persistence_m1_direction_*`, `experiments/next_bar/rolling_spectral_state_vs_distribution_shift_m1_*`
- equal diversification: `experiments/next_bar/distribution_shift_spectral_equal_m1_*`
