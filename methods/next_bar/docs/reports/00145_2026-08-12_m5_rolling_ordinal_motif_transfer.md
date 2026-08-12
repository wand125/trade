# 00145 M5 Rolling Ordinal Motif固定移植

日時: 2026-08-12 22:42 JST

## 目的

M15/M30で固定済みのRolling Ordinal MotifをM5へ無調整で移植し、次足方向、broad confidence、高信頼度、既存confidence候補への多様化に増分価値があるかを確認した。履歴returnの値そのものではなく、連続3本を6種類の順位patternへ加工して使う。

## 固定仕様と品質

連続3 returnを値、同値時は位置の辞書順で `012/021/102/120/201/210` へ分類する。直前32/128 motifについて6比率、正規化entropy、現在motif頻度を作り、短長entropy差・頻度差を加えた固定18特徴とした。baseline 38特徴と合わせて56特徴であり、生価格水準、volume、未来足はmodel featureへ使わない。

M1で確認済みの厳密式、flat/gap reset、artifact/latestに加え、M5について18列の完全な集合、56特徴、定常性、有限 `[-1,1]`、価格10倍scale不変、未来側M1価格の改変が過去M5特徴へ影響しないことを回帰テストした。対象テストは2件成功した。

HGB 200 iteration、learning rate 0.05、31 leaves、min leaf 100、L2 1、最大750,000 train行、Platt、expanding、uniform weighting、全教師、seed 42、標準損失1.0を固定した。通常/方向維持blendはbaseline 75% + Motif 25%。confidence gridは事前固定の0.51/0.515/0.525/0.535/0.55、developmentはtest2020〜2023、confirmationはtest2024〜2026_partialであり、window、pattern、model parameter、weight、閾値、subgroup filterを結果に合わせて再探索していない。

Windows/WSL canonical環境で439,881 OOS行を既存baselineと完全整列した。共有中のComfyUI、Claude、Open WebUI、Ollamaを停止せず、GPUを非表示、単独8 thread、nice 10、ionice 7、空きmemory 16GiB・load 8 gateで実行した。開始時は空き27GiB、load 0.09だった。

## 単体と方向

| model | development accuracy | confirmation accuracy | all accuracy | all Brier | all log loss |
|---|---:|---:|---:|---:|---:|
| baseline | 51.91385% | 51.03316% | 51.57463% | 0.249535053 | 0.692215561 |
| Motif単体 | 51.89351% | 50.99008% | 51.54553% | 0.249547053 | 0.692239972 |
| baseline 75% + Motif 25% | 51.91015% | 51.03789% | 51.57418% | 0.249530892 | 0.692207262 |

単体はbaseline比development -55件、confirmation -73件、all -128件だった。通常25%方向blendもdevelopment -10件、confirmation +8件、all -2件で、fix 3,131 / harm 3,133、McNemar p=0.9899、accuracy 4/7foldだった。developmentのBrier/log loss日次区間は改善側だったが、confirmationは点値が悪化し、all区間も0を跨いだ。方向用途へ採用しない。

## broad confidence 0.515

developmentの固定gridでselection score最大は0.515だった。

| period | model | rows | coverage | accuracy | Wilson lower | selection score |
|---|---|---:|---:|---:|---:|---:|
| development | baseline | 158,280 | 58.52468% | 52.75588% | 52.50986% | 0.0192008 |
| development | Motif | 157,729 | 58.32095% | 52.76265% | 52.51621% | 0.0192158 |
| confirmation | baseline | 63,694 | 37.59288% | 52.36600% | 51.97800% | 0.0121277 |
| confirmation | Motif | 63,448 | 37.44769% | 52.47762% | 52.08890% | 0.0127829 |
| all | baseline | 221,974 | 50.46228% | 52.64400% | 52.43624% | 0.0173063 |
| all | Motif | 221,177 | 50.28110% | 52.68088% | 52.47276% | 0.0175341 |

baseline比confirmation accuracy差+0.11162ptの日次95%区間は+0.01455〜+0.20892pt、selection score差+0.0006552の区間も+0.0000632〜+0.0012517で改善を支持した。一方coverageは-0.14519ptへ確定低下した。all accuracy、selection score、Brier、log loss区間は僅かに0を跨ぎ、fold勝敗はaccuracy/score各4/7、proper score各4/7に留まった。

## 既存broad候補との比較

| candidate | all rows | coverage | accuracy | selection score | Motif accuracy/score fold勝敗 |
|---|---:|---:|---:|---:|---:|
| Motif | 221,177 | 50.28110% | 52.68088% | 0.0175341 | — |
| Profile | 221,844 | 50.43273% | 52.68116% | 0.0175648 | 3/7, 3/7 |
| EWMA | 221,618 | 50.38135% | 52.69382% | 0.0176449 | 2/7, 3/7 |
| Haar | 221,540 | 50.36362% | 52.69838% | 0.0176739 | 3/7, 3/7 |
| Profile × TCN | 218,343 | 49.63683% | 52.72988% | 0.0177572 | 0/7, 1/7 |

Profileに対するMotifのall accuracy差は-0.00028ptで区間が0を跨いだが、coverageは-0.15163ptへ確定低下した。Brier差+0.00000890の95%区間は+0.00000282〜+0.00001510、log loss差+0.00001786は+0.00000563〜+0.00003034で、確率品質はProfileより明確に悪かった。EWMA、Haar、Profile×TCNにもaggregate accuracy/scoreを更新せず、特にProfile×TCNにはaccuracy 0/7foldだった。

Profile confidenceとMotif confidenceの固定50/50平均も、Profile比development/confirmation/all selection scoreを全て下げ、accuracy/score各2/7foldだった。既存候補への多様化成分として採用しない。

## 高信頼度と校正

Motifのconfirmation cumulative accuracyは0.515で52.47762%、0.525で53.24819%、0.535で54.95951%、0.55で58.50575%と単調に上昇した。各閾値でmean confidenceは52.47694%、53.33900%、54.20622%、55.53147%であり、Wilson区間内に入った。0.515のaggregate校正は非常に良く、accuracy−mean confidenceは+0.00068ptだった。

ただし0.55はconfirmation 870件、all 23,604件・56.14726%・coverage 5.36600%・score 0.0127713である。既存Directional Follow-throughはconfirmation 940件・58.51064%、all 24,328件・56.19040%・coverage 5.53059%・score 0.0130897で、Motifはaccuracy 2/7、score 1/7foldに留まった。all Brier/log lossも日次区間でFollow-throughより悪化側だった。test2026_partialはMotif 196件・48.97959%、Follow-through 228件・49.12281%で、直近tailはいずれもedge未確認だった。

固定方向×volatilityの0.515 confirmationでは6セル中5セルがWilson下限50%超だった。`down × normal` は4,336件・50.80720%、Wilson下限49.31906%で唯一edge未確認だった。確認後の除外filterは作らない。development/allでは0.515以上が平均confidenceに対して過信であり、global/localに一貫したfair oddsとは認可しない。

## latest

保存modelの最新M5は2026-06-01 04:55 UTC判定、up、`p(up)=0.5243282041`、volatility highだった。0.515は通るがこれはMotif単体modelであり、方向維持25% full runtime blendではない。`odds_valid=false`、`strict_prediction_eligible=false`であり、運用へ接続しない。

## 判断

M5 Motif単体、通常25%方向blend、方向維持0.515/0.55、Profileとの固定50/50 confidence平均をすべて再現専用とする。0.515のconfirmationでbaseline改善と良好な校正が再現したため、順位pattern加工がM5にも情報を持つことは確認できた。しかしbaselineのall採用gateが未確定で、Profileよりproper scoreが有意に悪く、Profile×TCNおよびFollow-throughの各roleを超えず、固定多様化も親を上積みしなかった。

新しいconfig、registry、authoritative方向/confidence、fair odds、adoption/paper/live policyは発行・変更しない。同じ履歴でmotif長、window、tie、feature subset、model parameter、weight、閾値、subgroup filterを再探索しない。

## 成果物

- 実装・テスト: `src/trade_data/next_bar.py`, `tests/test_next_bar.py`
- 単体OOS: `experiments/next_bar/rolling_ordinal_motif_m5_windows_canonical_001`
- 方向/方向維持blend: `experiments/next_bar/rolling_ordinal_motif_m5_{direction,confidence}_blend_windows_canonical_001`
- candidate分析: `experiments/next_bar/rolling_ordinal_motif_m5_candidate_analysis_windows.json`
- baseline/Profile/Follow-through bootstrap: `experiments/next_bar/rolling_ordinal_motif_m5_*_bootstrap_*.json`
- 既存候補比較: `experiments/next_bar/rolling_ordinal_motif_vs_{profile,ewma,haar,profile_tcn,follow_through}_m5_*_windows_comparison.json`
- 固定平均: `experiments/next_bar/profile_ordinal_motif_equal_m5_confidence_windows_canonical_001`
- reliability/subgroup: `experiments/next_bar/rolling_ordinal_motif_*_windows.json`
- latest: `experiments/next_bar/rolling_ordinal_motif_m5_latest_prediction_windows.json`

## 検証

- 対象テスト: `2 passed, 92 deselected`
- 全テスト（Mac）: `1390 passed, 1 deselected, 280 warnings, 83 subtests passed`、123.62秒。
- 全テスト（Windows）: `1390 passed, 1 deselected, 280 warnings, 83 subtests passed`、48.70秒。
- deselectは今回と無関係な既存 `entry_ev` レポート `00384_2026-07-08_mql5_mt5_paid_expert_top_analysis.md` の内部時刻欠落1件。通常実行でも新規テストを含む1390件は成功した。
- Mac/Windows同期、秘密情報scan、commit/pushは最終commitで確認する。
