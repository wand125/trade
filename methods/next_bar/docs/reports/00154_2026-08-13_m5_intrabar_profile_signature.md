# 00154 M5 Intrabar Profile Signature

日時: 2026-08-13 15:49 JST

## 目的

M15で検証済みの時間×正規化close経路signatureをM5へ移し、完成M5内5本のM1 closeの順序関係を3個の加工指標へ圧縮する。既存M5 Intrabar Profileに対して、次足方向またはconfidenceの増分edgeがあるかを確認した。

## 重複監査と固定仕様

M15 Full Pathの固定11地点をM5へそのまま移すと、時間位置の丸めによって5地点へ縮退する。最初の4地点はProfileの20/40/60/80% level、終点も完成M5の実体/range情報と重なるため、11列を追加する案は結果を見る前に中止した。

代わりにM5始値を `(time, price)=(0, 0)`、5本の完成M1 closeをM5 high-low rangeで正規化した等間隔経路とし、Chen積から次の非線形・順序感応3列だけを既存Profileへ追加した。

- level 2のtime-price signed area
- level 3のtime-time-price bracket
- level 3のprice-time-price bracket

実装名は `--feature-set intrabar_profile_signature`。Profile 65列 + signature 3列の全68特徴であり、M15用Full Path 11列は含めない。生OHLC価格水準、volume、未来M1、学習済み特徴変換は使わない。HGB 200 iteration、learning rate 0.05、31 leaves、min leaf 100、L2 1、Platt、expanding、uniform weighting、全教師、最大750,000 train行、seed 42、標準損失1.0を固定した。通常/方向維持blendはbaseline 75% + candidate 25%、confidence gridは0.51/0.515/0.525/0.535/0.55、developmentはtest2020〜2023、confirmationはtest2024〜2026_partialである。

M5で追加3列以外がProfileと完全同一、全68列stationary、価格10倍scale不変、未来側M1改変が過去完成M5特徴へ影響しないこと、有限値、artifact保存・latest推論をテストした。Windows canonicalでbaselineと完全整列する439,881 OOS行・7foldを生成した。共有中の画像生成等を停止せず、GPU非表示、単独8 thread、nice 10、ionice 7、空きmemory 16GiB・load 8 gateを維持した。

## 単体方向と通常25% blend

| period | baseline | Signature単体 | 通常25% blend |
|---|---:|---:|---:|
| development | 51.91385% | 51.89795% | 51.93936% |
| confirmation | 51.03316% | 51.14412% | 51.01369% |
| all | 51.57463% | 51.60759% | 51.58281% |

Signature単体はbaseline比development -43件、confirmation +188件、all +145件、McNemar `p=0.4412`。通常blendは+69/-33/+36件、accuracy 2/7fold、`p=0.7076`で、確認期間を改善しなかった。

親Profile単体に対してはdevelopment -164件、confirmation +194件、all +30件、accuracy 5/7foldだった。confirmation accuracy差の日次区間は+0.0140〜+0.2141ptだが、developmentは逆向き、all差は-0.0551〜+0.0699ptで未確定だった。全期間Brier/log lossは親より悪く、差の95%区間も悪化側だった。方向モデルとして既存PressureまたはProfileを置換しない。

## development選択0.525

事前固定gridでSignature方向維持blendのdevelopment目的関数が最大となった0.525を一度だけ選択した。

| period | model | rows | coverage | accuracy | selection score |
|---|---|---:|---:|---:|---:|
| development | baseline | 100,503 | 37.16140% | 53.36955% | 0.0186599 |
| development | Signature | 100,282 | 37.07968% | 53.46623% | 0.0192262 |
| confirmation | baseline | 24,626 | 14.53453% | 53.22017% | 0.0098990 |
| confirmation | Signature | 24,456 | 14.43419% | 53.31207% | 0.0102059 |
| all | baseline | 125,129 | 28.44610% | 53.34015% | 0.0163398 |
| all | Signature | 124,738 | 28.35721% | 53.43600% | 0.0168226 |

baseline比ではaccuracy/selection scoreを6/7fold、Brier/log loss/ECEを5/7fold改善した。20,000回UTC日bootstrapではdevelopmentとallのaccuracy、selection score、Brier、log loss改善が支持された。confirmationはaccuracy +0.09190pt、score +0.0003069だが両区間は0を跨ぎ、coverage -0.10034ptだけが確定した。baselineに対しては有効な加工感度である。

## 親Profileへの増分gate

同じ0.525で親Profileと直接比較した。

| period | model | coverage | accuracy | selection score |
|---|---|---:|---:|---:|
| development | Signature | 37.07968% | 53.46623% | 0.0192262 |
| development | Profile | 37.12590% | 53.48332% | 0.0193436 |
| confirmation | Signature | 14.43419% | 53.31207% | 0.0102059 |
| confirmation | Profile | 14.46548% | 53.36407% | 0.0104175 |
| all | Signature | 28.35721% | 53.43600% | 0.0168226 |
| all | Profile | 28.39768% | 53.45993% | 0.0169632 |

Signatureは3期間のaccuracy・coverage・selection score・Brier・log lossが全て親の点値を下回り、accuracy/score各3/7foldだった。選択集合Jaccardは全期間95.12%で、追加情報は強く重複した。

日次bootstrapのSignature−Profile差は、全期間accuracy -0.02392pt（95% -0.08644〜+0.03908pt）、score -0.0001406（-0.0004711〜+0.0001944）で未確定だった。一方coverage -0.04047pt（-0.07658〜-0.00462pt）、Brier +0.00000373、log loss +0.00000746は悪化側で確定した。confirmationでもSignatureが良い確率はaccuracy 26.5%、score 24.9%、proper score約3.3%に留まった。

Profile confidenceとSignature confidenceの固定50/50平均はdevelopment 0.515 scoreを0.0191423から0.0192562へ上げたが、confirmationは0.0130197から0.0127529へ反転した。all scoreも0.0175648から0.0175515へ低下し、Brier/log loss/ECE改善は各0/7foldだった。親を増分改善するensembleにも採用しない。

## 既存role、高信頼度、局所整合

現行Profile × Transition 0.515はall coverage 47.95297%、accuracy 52.81175%、score 0.0179952で、Signature 0.525の高いaccuracy 53.43600%と引き換えに、coverage-aware主目的を上回った。Signatureはaccuracy 7/7foldでもselection score 2/7foldだけであり、broad roleを更新しない。

0.55はall 23,817件・coverage 5.41442%・accuracy 56.15317%・score 0.0128492、confirmation 889件・57.59280%だった。Directional Follow-throughはall 24,328件・56.19040%・0.0130897、confirmation 940件・58.51064%で上回った。Signatureはtest2026_partial 215件・49.30233%でWilson edgeもなく、high-confidence roleにも使わない。

Signatureのconfirmation累積accuracyは0.51から順に51.85963%、52.45966%、53.31207%、54.81145%、57.59280%と単調上昇した。0.525はmean confidence 53.34039%、実測53.31207%で局所整合しWilson下限52.68631%も50%超だった。ただし固定6セルではdown×normalが739件・51.28552%、Wilson下限47.68440%でedge未確認である。結果後のセルをfilterへ変換しない。

保存済み最終foldモデルの最新M5は2026-06-01 04:55 UTC判定、up、`p(up)=0.5165796540`、volatility highだった。単体artifactの機能確認値で、fair odds校正を付けていないため`odds_valid=false`、`strict_prediction_eligible=false`である。

## 判断

Profile Signatureは5本のM1順序を3列へ圧縮し、baseline比0.525 accuracy・selection score・proper scoreを改善した。しかし直接の親Profile 0.525には全期間とconfirmationの主点値が全て負け、coverageとproper scoreの悪化が確定した。固定平均もconfirmationで反転し、Profile × Transition broad roleとFollow-through high-confidence roleを上回らない。

`intrabar_profile_signature` feature setとOOS成果物は再現用に残すが、config、registry、authoritative予測、fair odds、paper/live policyは変更しない。同じ履歴でsignature level、基底組合せ、特徴subset、blend weight、閾値、subgroup filterを再探索しない。損失倍率は標準1.0のみとする。

## 成果物

- 実装・テスト: `src/trade_data/next_bar.py`, `tests/test_next_bar.py`
- 単体OOS: `experiments/next_bar/intrabar_profile_signature_m5_windows_canonical_001`
- 通常/方向維持blend: `experiments/next_bar/intrabar_profile_signature_m5_{direction,confidence}_blend_windows_canonical_001`
- Profile固定平均: `experiments/next_bar/profile_profile_signature_equal_m5_confidence_windows_canonical_001`
- candidate分析・親/既存候補比較・20,000回UTC日bootstrap: `experiments/next_bar/*intrabar_profile_signature*_windows*.json`
- reliability/subgroup: `experiments/next_bar/intrabar_profile_signature_{vs_profile_m5_reliability,m5_subgroups}_windows.json`
- latest: `experiments/next_bar/intrabar_profile_signature_m5_latest_prediction_windows.json`

## 検証

- 対象テスト `pytest tests/test_next_bar.py -k 'm5_intrabar_profile_signature or intrabar_path_signature'`: Mac/Windows各2 passed。
- 既知の無関係なEntry EV docs時刻検査1件だけを明示deselectした全テスト: Mac/Windows各1,399 passed / 1 deselected / 83 subtests（Mac 161.95秒、Windows 53.39秒）。
- Windows OOSはbaselineと同じ439,881行・7fold、68特徴、標準損失1.0、同一canonical platformで評価した。
- 口座runtime、login、password、token、secret、API key、private key、Windows Codex認証状態は同期・commit対象に含めない。
