# 00141 M5 Path Persistence Fixed Transfer

日時: 2026-08-12 13:13 JST

## 結論

M1方向候補、M15加工特徴として既に定義した `path_persistence` 14特徴を、窓・式・HGB/Platt・25% blend・閾値grid・標準損失1.0を変更せずM5へ固定移植した。Windows/WSL2 canonical環境でbaseline、Path、Intrabar Pressure、EWMA Asymmetry、Intrabar Profile、Directional Follow-throughを同じ439,881 OOS行・7foldから比較した。

Pathはbaselineに対して通常25%方向blendを64件、方向維持0.515の選別精度を僅かに改善し、Brier/log lossにも改善感度があった。しかし方向は現行Pressureに全期間32件負け、PathのBrier/log lossも日次bootstrapで有意に悪かった。0.515 confidenceはEWMAにaccuracy/selection score各2/7、Profileに各3/7だった。0.55もWindowsで再構築したFollow-throughに全期間accuracy -0.2590pt、selection score -0.000678で、両差の95%区間が劣後側だった。

M5 Pathは新candidateへ採用せず再現専用とする。Pressure方向、Profile/EWMA 0.515、Follow-through 0.55、authoritative confidence、fair odds、paper/live policyを変更しない。

## 固定仮説と加工特徴

価格履歴そのものを入力せず、完成M5足の経路を次の定常量へ圧縮した。

- 5/10/20/50本の符号付きefficiency 4列
- 10/20本return autocorrelation 2列
- 10/20本方向転換率 2列
- 50本内の2/5/10本variance ratio 3列
- 20本up/down persistence 2列
- 20本signed return streak 1列
- baseline 38列 + Path 14列 = 52加工特徴

raw OHLC水準、volume、target、未来足は特徴へ含めない。完全flatや片方向窓の0/0は「追加の持続性証拠なし」の0とし、M5移植について14列、全52列、scale不変、有限性、raw OHLC除外を自動テストへ追加した。

## 固定学習・評価条件

- M5、test2020〜test2026_partialの7fold、439,881 OOS行
- development=test2020〜2023、confirmation=test2024〜2026_partial
- HGB 200 iteration、learning rate 0.05、31 leaves、min leaf 100、L2 1
- expanding、最大750,000 train行、Platt、seed 42、uniform weighting、全教師
- baseline 75% + Path 25%、標準損失1.0
- confidenceはbaseline方向を維持し、閾値0.51/0.515/0.525/0.535/0.55をdevelopmentだけで評価
- 主目的関数 `sqrt(coverage) * (Wilson95Lower(accuracy) - 0.50)`
- 候補差はUTC日をblockとする20,000回paired bootstrapで確認

結果を見た後のwindow、特徴subset、weight、閾値、subgroup filter再探索は行っていない。

## 方向結果

| period | baseline | Path単体 | Path 25% blend |
|---|---:|---:|---:|
| development | 51.91385% | 51.91311% | 51.92161% |
| confirmation | 51.03316% | 51.06740% | 51.05854% |
| all | 51.57463% | 51.58736% | 51.58918% |

単体はbaseline比-2/+58/+56件、通常blendは+21/+43/+64件だった。通常blendはaccuracy 5/7、Brier/log loss各6/7fold改善したが、all accuracy差+0.01455ptのbootstrap区間は-0.02241〜+0.05220ptで0を跨いだ。all Brier差-0.00000748、log loss差-0.00001503の区間は改善側であり、経路加工による確率平滑化感度は確認した。

### 現行Intrabar Pressureとの同一platform比較

旧artifactのplatform差を混ぜず、PressureをWindows canonicalで同じ7foldから再学習した。

| period | Path 25% | Pressure 25% | Path − Pressure |
|---|---:|---:|---:|
| development | 51.92161% | 51.94417% | -0.02256pt |
| confirmation | 51.05854% | 51.04143% | +0.01712pt |
| all | 51.58918% | 51.59645% | -0.00727pt |

Pathは年別accuracy 3/7対4/7、全期間32件負けだった。all accuracy差のbootstrap区間は-0.05176〜+0.03657ptで未確定だが、Path − PressureのBrier差+0.00000627は区間+0.00000016〜+0.00001243、log loss差+0.00001257は+0.00000029〜+0.00002494で、確率品質はPressureが有意に良かった。方向候補を置換・追加しない。

## Broad confidence 0.515

development目的関数最大の固定閾値は0.515だった。

| period | model | rows | coverage | accuracy | selection score |
|---|---|---:|---:|---:|---:|
| development | baseline | 158,280 | 58.52468% | 52.75588% | 0.019201 |
| development | Path | 158,424 | 58.57793% | 52.75842% | 0.019230 |
| confirmation | baseline | 63,694 | 37.59288% | 52.36600% | 0.012128 |
| confirmation | Path | 63,240 | 37.32493% | 52.45572% | 0.012624 |
| all | baseline | 221,974 | 50.46228% | 52.64400% | 0.017306 |
| all | Path | 221,664 | 50.39181% | 52.67206% | 0.017492 |

Pathはbaselineにaccuracy/score各5/7、Brier/log loss各6/7fold勝った。confirmation accuracy差+0.08972ptの95%区間は-0.00452〜+0.18338pt、score差+0.000497は-0.000083〜+0.001074で、ともに僅かに0を跨いだ。allもaccuracy・score区間は未確定で、coverageは-0.07047ptだった。all Brier/log lossの改善区間だけは正だった。

### 既存broad候補との比較

| period | Path accuracy / score | EWMA accuracy / score | Profile accuracy / score |
|---|---:|---:|---:|
| development | 52.75842% / 0.019230 | 52.77837% / 0.019369 | 52.74754% / 0.019142 |
| confirmation | 52.45572% / 0.012624 | 52.48281% / 0.012808 | 52.51559% / 0.013020 |
| all | 52.67206% / 0.017492 | 52.69382% / 0.017645 | 52.68116% / 0.017565 |

PathはEWMAにaccuracy/score各2/7、Profileに各3/7だった。Path − EWMAは3期間すべて点値で負け、all accuracy差-0.02176pt、score差-0.000153のbootstrap区間は0を跨いだ。Path − Profileはall accuracy -0.00910pt、score -0.000072で未確定だが、all Brier差+0.00000603とlog loss差+0.00001204の95%区間は全てPath劣後側だった。重複するbroad候補を増やさない。

## High confidence 0.55

Path 0.55はall 24,092件・coverage 5.47694%・accuracy 55.93143%、confirmation 923件・58.61322%だったため、高信頼roleも別途監査した。旧platform成果物を使わず、現行Directional Follow-throughをWindows canonicalで再学習して方向維持25% blendを再構築した。

| period | Path rows / accuracy / score | Follow-through rows / accuracy / score |
|---|---:|---:|
| development | 23,169 / 55.82459% / 0.015174 | 23,388 / 56.09714% / 0.016057 |
| confirmation | 923 / 58.61322% / 0.003990 | 940 / 58.51064% / 0.003972 |
| all | 24,092 / 55.93143% / 0.012412 | 24,328 / 56.19040% / 0.013090 |

Pathはconfirmationだけごく僅かに上回ったが、fold勝敗はaccuracy 3/7、score 1/7だった。all Path − Follow-through accuracy差-0.25897ptの区間は-0.48965〜-0.02820pt、score差-0.000678は-0.001226〜-0.000137で、両方とも劣後が確定した。developmentでもaccuracy・coverage・score差が全て劣後側だった。test2026_partialはPath 229件・51.0917%、Follow-through 228件・49.1228%で、どちらもprecision edgeを確認できない。Pathをhigh-confidence shadowへ追加しない。

## 信頼度のオッズ整合とsubgroup

Pathの累積精度はdevelopment、confirmation、allの固定帯で閾値とともに単調上昇した。confirmationは次の通りだった。

| threshold | rows | coverage | accuracy | mean confidence | Wilson lower |
|---:|---:|---:|---:|---:|---:|
| 0.515 | 63,240 | 37.32493% | 52.45572% | 52.47921% | 52.06636% |
| 0.525 | 24,293 | 14.33799% | 53.43515% | 53.34485% | 52.80738% |
| 0.535 | 7,913 | 4.67034% | 54.92228% | 54.21733% | 53.82383% |
| 0.550 | 923 | 0.54476% | 58.61322% | 55.53281% | 55.40642% |

confirmationは4帯ともmean confidenceがWilson区間内で、Wilson下限も50%超だった。一方development 0.515は実測52.75842%に対しmean 53.37285%、allも52.67206%対53.11790%で過信し、期間横断のfair odds認可条件を満たさない。

方向×volatility固定6セルのconfirmation 0.515ではdown-normalが4,256件・50.4934%・Wilson下限48.9915%でedge未確認だった。0.55ではup-highの678件だけがedgeを確認し、他5セルは各5〜98件またはWilson下限50%未満だった。この診断後セルを同じ履歴へ合わせた除外・採用filterには変換しない。

## Runtime parity

baselineと同じsplit境界、HGB/Platt設定でPath latest artifactを生成し、52特徴から最新推論を実行した。2026-06-01 04:55 UTCのM5は次の通りだった。

- baseline `p(up)=0.5332709162`
- Path `p(up)=0.5296754678`
- baseline方向維持25% blend `p(up)=0.5323720541`

split境界と主要設定のparityは通過した。経験的oddsは接続せず、`odds_valid=false`、`strict_prediction_eligible=false` のままである。

## 共有計算資源

Path/Pressure/Follow-through学習、blend、比較、20,000回bootstrap、reliability、subgroup、latest推論はWindows/WSL2の単独workerで順番に実行した。標準8 thread、nice 10、I/O低優先度、CPU only、available memory 16GiB/load 8 gateを維持し、画像生成・ローカルAI・他処理を停止していない。

## 判断

- M5 Path単体、通常25%方向、方向維持0.515/0.55を再現専用とする。
- Pathのbaseline proper-score改善は、経路加工がM5でも情報を持つ感度として保存する。
- 方向はIntrabar Pressure、broad confidenceはProfile/EWMA 0.515、high-confidenceはFollow-through 0.55を維持する。
- window、特徴subset、25% weight、閾値、subgroup filterを同じ履歴で再探索しない。
- config、registry、authoritative予測、fair odds、paper/live policyを変更しない。
- 大きなmodel/parquet、比較、bootstrap、reliability成果物はWindows側だけに保存する。

MacとWindows/WSLの全体testはどちらも `1386 passed, 1 deselected, 83 subtests passed` だった。deselectは今回と無関係のentry-EV既存レポートに内部時刻がないdocs検査1件である。変更4ファイルとWindows側の新規JSON/manifestをaccount、login、password、token、secret、private keyの代入形式で走査し、実値を含む一致は0件だった。口座runtime・credentialは同期していない。
