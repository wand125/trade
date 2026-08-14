# 00155 M5 Intrabar Extrema Dwell

日時: 2026-08-14 21:16 JST

## 目的

完成M5の最終high-low range付近へM1値幅が滞在する時間と広がりを加工し、単なる極値到達時刻やclose経路とは異なるauction persistenceが次足方向・confidenceを改善するか検証した。結果を見る前にzone幅20%、親Intrabar Profile、HGB/Platt設定、25% blend、confidence gridを固定した。

## 重複監査と固定仕様

最終M5 rangeの上端20%・下端20%と各M1 high-lowの重なりを全M1 range合計で割るrange occupancy、各zoneへtouchしたM1本数比、最初と最後のtouch位置差を上下各3列、合計6列にした。生OHLC価格水準、未完成足、未来M1、volume、学習済み特徴変換は使わない。flat rangeは全6列を0とする。

当初候補のtouch位置center-of-mass 2列は、全履歴1,182,985 M1本・295,724完成M5の事前監査で既存 `intrabar_high_position` / `intrabar_low_position` と絶対Pearson相関0.92666 / 0.92717だったため、OOSを見る前に除外した。採用した6列に完全重複はなく、親65列との最大絶対相関は次の範囲だった。

- upper/lower range occupancy: 0.35148 / 0.34994
- upper/lower touch fraction: 0.38373 / 0.38702
- upper/lower touch span: 0.23523 / 0.23721

実装名は `--feature-set intrabar_extrema_dwell`。Profile 65列 + 固定6列の全71特徴である。HGB 200 iteration、learning rate 0.05、31 leaves、min leaf 100、L2 1、Platt、expanding、uniform weighting、全教師、最大750,000 train行、seed 42、標準損失1.0を固定した。通常/方向維持blendはbaseline 75% + candidate 25%、gridは0.51/0.515/0.525/0.535/0.55、developmentはtest2020〜2023、confirmationはtest2024〜2026_partialとした。

## 単体方向と通常25% blend

| period | baseline | Dwell単体 | 通常25% blend |
|---|---:|---:|---:|
| development | 51.91385% | 51.93899% | 51.92050% |
| confirmation | 51.03316% | 51.04792% | 50.99185% |
| all | 51.57463% | 51.59577% | 51.56281% |

Dwell単体はbaseline比all +93件でもMcNemar `p=0.6245`、通常blendはall -52件・`p=0.5913`で方向置換の根拠にならない。通常blendは既存Pressureにdevelopment、confirmation、allすべて負け、accuracy/score 1/7fold、all差 -0.03365ptだった。Pressure方向候補は維持する。

## development選択0.515

事前固定gridで方向維持blendのdevelopment selection scoreが最大となった0.515を一度だけ選択した。

| period | model | rows | coverage | accuracy | selection score |
|---|---|---:|---:|---:|---:|
| development | baseline | 158,280 | 58.52468% | 52.75588% | 0.0192008 |
| development | Dwell | 158,541 | 58.62119% | 52.77121% | 0.0193356 |
| confirmation | baseline | 63,694 | 37.59288% | 52.36600% | 0.0121277 |
| confirmation | Dwell | 63,226 | 37.31667% | 52.49423% | 0.0128579 |
| all | baseline | 221,974 | 50.46228% | 52.64400% | 0.0173063 |
| all | Dwell | 221,767 | 50.41523% | 52.69224% | 0.0176401 |

baseline比confirmationの日次bootstrap差はaccuracy +0.12823pt（95% +0.01860〜+0.23822pt）、score +0.0007302（+0.0000591〜+0.0014036）で改善側だった。all accuracy/scoreは点改善でも区間が0を跨いだが、Brier差 -0.00001254、log loss差 -0.00002512は改善側で確定した。baselineへの加工感度は確認できた。

## 親Profileへの増分gate

同じ0.515で親Profileと直接比較した。

| period | model | coverage | accuracy | selection score |
|---|---|---:|---:|---:|
| development | Dwell | 58.62119% | 52.77121% | 0.0193356 |
| development | Profile | 58.55426% | 52.74754% | 0.0191423 |
| confirmation | Dwell | 37.31667% | 52.49423% | 0.0128579 |
| confirmation | Profile | 37.46894% | 52.51559% | 0.0130197 |
| all | Dwell | 50.41523% | 52.69224% | 0.0176401 |
| all | Profile | 50.43273% | 52.68116% | 0.0175648 |

Dwellはaccuracy 4/7、score 3/7fold。全期間accuracy +0.01108pt、score +0.0000754の日次区間は0を跨ぎ、confirmationは両点値が反転した。confirmation coverage -0.15227ptの悪化だけが確定し、Brier/log lossにも親への増分はない。選択Jaccardは全期間96.10%である。

ProfileとDwell confidenceの事前固定50/50平均は、全期間221,752件・coverage 50.41182%・accuracy 52.70031%・score 0.0176968、accuracy/score各5/7foldとなった。confirmationもaccuracy 52.54224%、score 0.0131640でProfileを点改善した。ただし全期間accuracy差 +0.01915pt（95% -0.01070〜+0.04918pt）、score差 +0.0001321（-0.0000798〜+0.0003442）、confirmationも両区間が0を跨いだ。confirmation coverage -0.09089ptは悪化側で確定し、統計的な親増分gateは満たさない。

## 既存role、高信頼度、局所整合

現行Profile × Transition 0.515はall coverage 47.95297%、accuracy 52.81175%、score 0.0179952で、Dwellよりaccuracy 7/7fold。Dwell−現行のall accuracy差 -0.11951ptとBrier/log loss差はbootstrapでも悪化側だったためbroad roleを更新しない。

0.55のDwellはall 24,018件・coverage 5.46011%・accuracy 56.13706%・score 0.0128718、confirmation 873件・58.07560%・0.0034268だった。Directional Follow-throughはall 24,328件・56.19040%・0.0130897、confirmation 940件・58.51064%・0.0039719で上回り、Dwellはaccuracy/score各3/7foldだった。high-confidence roleも更新しない。

全期間の固定band accuracyは0.50〜0.51から0.60以上まで低下なしで、0.515/0.55の累積accuracyは52.69224% / 56.13706%、mean confidenceは53.11595% / 56.36707%だった。方向×volatilityの固定6セルは両閾値で全てWilson下限50%超だが、local consistencyは0.515で3/6、0.55で5/6セルだった。最良セルを結果後filterへ変換しない。

保存済み最終artifactの最新M5は2026-06-01 04:55 UTC判定、up、`p(up)=0.5327260617`、volatility highだった。fair odds校正を付けていないため `odds_valid=false`、`strict_prediction_eligible=false` である。

## 判断

Extrema Dwellはbaselineに対してconfirmationの0.515 accuracy・selection scoreと全期間proper scoreを改善し、最終range端へのM1滞在には加工情報がある。Profileとの固定50/50平均も5/7foldで点改善し、補完可能性は残った。

しかし親Profileへの直接差と固定平均の改善区間は0を跨ぎ、confirmation coverageは有意に低下した。Profile × Transition、Pressure方向、Follow-through 0.55の既存roleを超えない。`intrabar_extrema_dwell` とOOS成果物は再現用に残すが、config、registry、authoritative予測、fair odds、paper/live policyは変更しない。同じ履歴でzone幅、center-of-mass復活、特徴subset、blend weight、閾値、subgroup filterを再探索しない。損失倍率は標準1.0のみとする。

## 成果物

- 実装・テスト: `src/trade_data/next_bar.py`, `tests/test_next_bar.py`
- 単体OOS: `experiments/next_bar/intrabar_extrema_dwell_m5_windows_canonical_001`
- 通常/方向維持blend: `experiments/next_bar/intrabar_extrema_dwell_m5_{direction,confidence}_blend_windows_canonical_001`
- Profile固定平均: `experiments/next_bar/profile_extrema_dwell_equal_m5_confidence_windows_canonical_001`
- candidate分析・親/既存role比較・20,000回UTC日bootstrap: `experiments/next_bar/*extrema_dwell*_windows*.json`
- reliability/subgroup: `experiments/next_bar/intrabar_extrema_dwell_{vs_profile_m5_reliability,m5_subgroups}_windows.json`
- latest artifact/prediction: `experiments/next_bar/intrabar_extrema_dwell_m5_latest_{artifact,prediction}_windows*`

## 検証

- 対象テストで厳密5本式、Profile列同一、71特徴、定常性、価格10倍scale不変、未来M1改変不影響、flat有限0、train/latestをMac/Windowsで確認した。
- 既知の無関係なEntry EV docs時刻検査1件だけを明示deselectしたWindows全テストは1,400 passed / 1 deselected / 83 subtests（53.88秒）。同検査単体は既知の `00384_2026-07-08_mql5_mt5_paid_expert_top_analysis.md` 内部時刻欠落であることを再確認した。Mac全テストは共有高負荷処理との競合で9分時点275 passedのまま中断し、計算資源を解放した。
- Windows OOSはbaselineと同じ439,881行・7fold、標準損失1.0、同一canonical platformで評価した。
- 共有中の画像生成等を停止せず、GPU非表示、単独8 thread、nice 10、ionice 7、空きmemory 16GiB・load 8 gateを維持した。
- 口座runtime、login、password、token、secret、API key、private key、Windows Codex認証状態は同期・commit対象に含めない。
