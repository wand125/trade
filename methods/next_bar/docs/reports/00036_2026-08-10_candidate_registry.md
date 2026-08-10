# 00036 Fixed confidence candidate registry

日時: 2026-08-10 13:52 JST

追記: このレポートは13候補時点のsnapshotである。00038でintrabar profileを追加し、現行registryは14候補、broad championはintrabar profile 0.515へ更新された。

## 目的

増えたM15 confidence候補を同じ定義で再計算し、履歴レポートの転記値ではなく予測parquetを正本として採否を比較できる台帳を作る。coverageとaccuracyを同時に扱う目的関数、確率品質、fold安定性を自動監査し、役割別にchampion・challenger・dominated・shadowを分類する。

## 固定した評価規則

- 対象はbaseline方向を維持する固定confidence候補13件、145,140 OOS行、M15 2020〜2026途中の7fold。
- 2020〜2023だけをdevelopmentとしてchampionを選ぶ。2024〜2026途中はconfirmation監査に限定し、順位選択へ使わない。
- 各candidate configに結果確認済みの固定閾値を明示する。台帳生成時の閾値再探索は禁止する。
- 目的関数は `sqrt(coverage) * (Wilson95Lower(accuracy) - 0.50)`。
- broadは閾値0.52以下、balancedは0.525、selectiveは0.53〜0.54、precisionは0.55以上とする。
- championは役割内forward candidateのdevelopment目的関数最大。coverageとaccuracyの両方で他候補に劣るものをdominated、非劣位の残りをchallengerとする。shadowはchampion選択から除外する。
- historical gateはdevelopment/confirmationのaccuracyとscore、confirmation Brier/log loss、lane/proper scoreの年別再現性を検査する。ただし通過は新しい完全未使用期間を代替しない。

古い5設定は閾値がlane説明やevidence名にしかなかったため、weighted 0.54、Extra Trees 0.53、intrabar 0.55、logistic 0.54、regime 0.55を `fixed_confidence_threshold` として明示した。今後は暗黙閾値をエラーにする。

## 役割別champion

| role | champion | threshold | development coverage | accuracy | score | confirmation coverage | accuracy | score |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| broad | signed-body | 0.520 | 40.231% | 53.807% | 0.02087 | 30.745% | 53.594% | 0.01580 |
| balanced | signed-body quantile | 0.525 | 37.715% | 54.078% | 0.02177 | 26.455% | 54.086% | 0.01689 |
| selective | Extra Trees | 0.530 | 29.377% | 54.467% | 0.02094 | 18.148% | 54.664% | 0.01574 |
| precision | intrabar structure | 0.550 | 10.888% | 55.934% | 0.01631 | 3.104% | 56.437% | 0.00722 |

4 championはいずれも同じ閾値のbaselineに対し、developmentとconfirmationのaccuracy・selection scoreを改善し、historical gateを通過した。

## coverageとaccuracyの分離

balancedではsigned-body quantileが目的関数とcoverageの首位だが、clear-bodyはdevelopment 54.173%、confirmation 54.201%で正答率首位だった。clear-bodyはPareto challengerとして残す。

selectiveでもExtra Trees 0.53が目的関数・coverage首位、body/ATR weighted 0.54がdevelopment 55.120%、confirmation 55.465%で正答率首位である。weightedはPareto challenger、logistic 0.54はdevelopmentでcoverageとaccuracyの両方がweightedに劣るためdominatedとなった。

precisionではintrabar structure 0.55がdevelopmentで既存intrabar 0.55をcoverage・accuracyとも上回りchampionとなる。confirmation accuracyだけは既存intrabarが56.459%対56.437%で僅かに高いが、confirmationは選択に使わない監査値である。

## 品質監査

- broad champion: lane accuracy 7/7、score 6/7 fold改善。Brier/log loss/ECEは各4/7。
- balanced champion: lane accuracy 6/7、score 6/7、Brier/log loss 6/7、ECE 3/7。
- selective champion: lane accuracy 7/7、score 6/7、Brier/log loss 5/7、ECE 4/7。
- precision champion: lane accuracy 7/7、score 6/7、Brier/log loss/ECE 6/7。

ECE単独を必須条件にしていないのは、Brier/log lossと高信頼laneの目的に対して小さいbin誤差が不安定だからである。ただしfair oddsへの昇格では別途ECEと局所supportを監査する。

## 成果物と判断

- 再計算器: `src/trade_data/next_bar_registry.py`
- CLI: `methods/next_bar/scripts/build_candidate_registry.py`
- 機械可読台帳: `methods/next_bar/config/m15_candidate_registry_v1.json`
- 13候補の予測パス、145,140行のkey整列、固定閾値、全指標を毎回検証する。
- 役割別の履歴championを確定したが、authoritative confidence、fair odds、paper policyは置換しない。次の完全未使用期間ではこの4 championと2 accuracy challengerだけを固定条件で比較する。
- shadowやdominated候補のparameter・weight・閾値を同じ履歴へ合わせて再探索しない。
- 損失倍率は標準1.0のみであり、この台帳の評価に損益倍率は含めない。

## 検証

registry、next-bar本体、ensemble、overlayの関連61テストを実行し、全件成功した。
