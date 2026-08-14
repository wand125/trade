# 00162 M5 Causal GRU Fixed Transfer

日時: 2026-08-15 02:19 JST

## 目的

M1で固定済みの小型causal GRUを、未検証のM5へ定義を変えず移植する。木系学習器や局面分割とは異なる再帰状態で、直近16完成足の加工系列から方向edgeまたはconfidence順位付けの増分が出るかを確認する。既存M5 TCNと近いmodel容量で比較し、単体、baseline 25% blend、Profileとの固定50/50 confidence blendを分離して評価する。

## 固定仕様と資源品質

- 完成M5足16本 x 5加工channel
- ATR正規化return/body/range、中心化close location、ATR正規化wick balance
- baseline 38列 + sequence 80列 = 118加工特徴
- 各foldのtrainだけでchannel mean/stdを推定
- 単層causal GRU、hidden 16、1,121 parameter
- AdamW、8 epoch、batch 2,048、learning rate 0.001、weight decay 0.0001、seed 42
- expanding、最大750,000 train行、後続calibration期間のPlatt、uniform weighting、全教師
- raw OHLC水準、volume、未来足を特徴へ含めない
- 標準損失1.0

test2020〜test2026途中の固定7fold、439,881 OOS行をWindows canonical環境で学習し、baseline/TCN/既存候補とtimestamp/targetを完全整列した。単独worker、最大8 threads、nice 10、ionice 7、GPU非表示、memory/load gate付きで実行し、ComfyUI/Ollamaは停止していない。

## 単体と通常25%方向blend

| period | baseline | GRU単体 | baseline 75% + GRU 25% |
|---|---:|---:|---:|
| development | 51.91385% | 51.82732% | 51.94195% |
| confirmation | 51.03316% | 50.99539% | 51.06267% |
| all | 51.57463% | 51.50688% | 51.60327% |

GRU単体はbaseline比development -234件、confirmation -64件、all -298件、McNemar exact p=0.20546だった。accuracy/Brier/log loss各1/7foldで方向用途へ使わない。

通常25% blendは+76/+50/+126件、p=0.27470で、accuracy 6/7、Brier/log loss各4/7、ECE 5/7foldを改善した。baseline比all accuracy差+0.02864ptのUTC日bootstrap 20,000回区間は-0.02320〜+0.08080ptで0を跨いだ。一方all Brier差-0.000009911とlog loss差-0.000019784の区間は改善側だったが、confirmation proper scoreは点悪化して区間も0を跨いだ。

既存Pressure方向候補に対してGRUはdevelopment -6件、confirmation +36件、all +30件だった。しかしaccuracy/selection scoreは3/7対4/7、all accuracy差+0.00682ptの区間は-0.04429〜+0.05825ptで、Brier/log loss差も未確定かつ点劣後だった。固定Pressure x GRU 50/50方向平均はall accuracy 51.59577%となり両親を上回らず、GRUへ1/7、Pressureへ3/7foldだった。新しい方向candidateを追加しない。

## GRU方向維持confidence 0.515

baseline方向を固定し、GRUを25%だけconfidence edgeへ混ぜた。development固定gridで0.515を選び、confirmationを選択へ使っていない。

| period | rows | coverage | accuracy | selection score |
|---|---:|---:|---:|---:|
| development | 156,058 | 57.70309% | 52.80665% | 0.019438 |
| confirmation | 61,851 | 36.50513% | 52.47126% | 0.012552 |
| all | 217,909 | 49.53817% | 52.71145% | 0.017608 |

baseline比all accuracyは+0.06745ptだがcoverage -0.92411ptである。Brier/log loss各4/7、ECE 5/7foldだった。Profile 0.515へaccuracy 4/7でもselection score 2/7、confirmation score 0.012552対0.013020で負け、Profile x Transitionにはaccuracy/score各1/7対6/7だった。

固定0.55は20,617件、coverage 4.68695%、accuracy 55.76466%、score 0.011010。Follow-throughは24,328件、5.53059%、56.19040%、0.013090で、GRUはaccuracy/score各2/7foldしか勝てない。GRU単独confidenceをbroad/high-confidence roleへ使わない。

## Profile x GRU固定50/50 confidence

Profile方向維持25% confidenceとGRU方向維持25% confidenceを、方向を変えず固定50/50で確率edge平均した。最終確率はbaseline 75%、Profile 12.5%、GRU 12.5%に等価で、weight探索はしていない。

| period | Profile rows / accuracy / score | Profile x GRU rows / accuracy / score |
|---|---:|---:|
| development | 158,360 / 52.74754% / 0.019142 | 157,049 / 52.81154% / 0.019543 |
| confirmation | 63,484 / 52.51559% / 0.013020 | 62,609 / 52.52280% / 0.012957 |
| all | 221,844 / 52.68116% / 0.017565 | 219,658 / 52.72924% / 0.017811 |

親Profileへaccuracy/selection score各6/7fold勝った。all accuracy差+0.04808ptのbootstrap区間は+0.00081〜+0.09503ptだが、coverage差-0.49695ptは悪化側、score差+0.0002458の区間は-0.0000879〜+0.0005773で0を跨いだ。confirmation accuracy/score/proper scoreは全て未確定で、score点値は僅かに反転した。

既存Profile x TCNにはaccuracy/score各4/7対3/7、all coverage +0.29894ptだけがbootstrapで確定し、accuracy・score・proper score差は全て0を跨いだ。既存Profile x Transitionにはaccuracy/score各3/7対4/7。all accuracy差-0.08251ptの区間は-0.14118〜-0.02359pt、Brier/log loss悪化区間も確定し、selection scoreも低い。現行broad shadowを置換・追加しない。

## 信頼度品質とruntime

Profile x GRUの累積accuracyはdevelopment/confirmation/allで0.515→0.525→0.535→0.55の順に単調上昇した。confirmation 0.515は62,609件、実測52.52280%、mean confidence 52.45392%で局所整合し、0.525/0.535/0.55も局所整合した。一方development 0.515は実測52.81154%に対し53.32004%で過信し、期間横断のfair odds条件を満たさない。

predicted up/down x low/normal/high volatilityの固定6セルでは、confirmation 0.515のdown-normalが4,302件・50.7903%でWilson edge未確認だった。0.55はup-high 515件以外が4〜82件と疎い。同じ履歴から局面guardを後付けしない。

最終fold GRU artifactの別process latest推論は成功し、2026-06-01 04:55 UTCのM5はup、`p(up)=0.5186858105` だった。odds/policyを発行していないため `odds_valid=false`、`strict_prediction_eligible=false` である。

## 判断

GRU通常方向blendはbaselineへ6/7fold改善し、再帰系列の方向感度として保存する。しかしPressureを直接上回らず、accuracy差は未確定、confirmation proper scoreも再現しない。GRU単独confidenceとProfile x GRUも既存Profile x Transition/Follow-throughを上回らない。

GRU単体、通常/方向維持25%、Pressure x GRU方向平均、Profile x GRU confidence平均を再現専用とする。新config、registry候補、authoritative方向/confidence、fair odds、paper/live policyを発行・変更しない。sequence、hidden、epoch、learning rate、weight、閾値、subgroup filterを同じ履歴へ合わせて再探索しない。

## 検証

WindowsでGRU artifact/latest round-trip test 1件が成功した。全suiteは既知のEntry EV文書内部時刻1件だけを除外し、1,401件成功、1件除外、53.26秒だった。Macは共有中の高負荷処理へ追加負荷をかけないため全suiteを重ねなかった。

## 成果物

- OOS: `experiments/next_bar/gru_m5_windows_canonical_001`
- normal/confidence blends: `experiments/next_bar/gru_m5_{direction,confidence}_blend_windows_canonical_001`
- candidate分析: `experiments/next_bar/gru_m5_candidate_analysis.json`
- Profile x GRU: `experiments/next_bar/profile_gru_equal_m5_confidence_windows_canonical_001`
- Pressure x GRU: `experiments/next_bar/pressure_gru_equal_m5_direction_windows_canonical_001`
- 直接比較: `experiments/next_bar/{gru,profile_gru,pressure_gru}_m5_vs_*.json`
- 20,000回bootstrap: `experiments/next_bar/{gru,profile_gru}_m5_*_bootstrap_20000.json`
- reliability/subgroups: `experiments/next_bar/profile_gru_m5_vs_profile_reliability.json`, `profile_gru_m5_confidence_subgroups.json`
- latest: `experiments/next_bar/gru_m5_latest_prediction.json`
