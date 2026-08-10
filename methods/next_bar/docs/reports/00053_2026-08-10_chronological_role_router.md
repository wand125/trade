# 00053 Chronological role router

## 目的

candidate registryの各roleについて、固定championを使い続ける代わりに、各評価foldより前のOOS成績だけで候補を選び直すとselection scoreを改善できるか検証した。方向は全候補で正式baselineと一致させ、候補固有の固定confidence閾値も変更しない。

## 方法

- 最初のfoldは過去OOSがないためbaseline fallbackとし、nested集計から除外する。
- 2番目以降は、それ以前の全OOS foldをpoolし、`sqrt(coverage) * (Wilson95Lower(accuracy) - 0.50)` が最大の同role候補を次foldへ固定適用する。
- current/future foldの正解は選択へ使わない。future foldを書き換えても同foldの選択が変わらない単体テストを追加した。
- 方向を変える候補、行alignment不一致、重複予測は停止する。

実装は `src/trade_data/next_bar_router.py`、CLIは `methods/next_bar/scripts/chronological_role_router.py`、成果物は `experiments/next_bar/chronological_role_router_m15_001` である。

## 結果

### Confirmation 2024–2026途中

| role | router accuracy | router coverage | router score | static accuracy | static coverage | static score |
|---|---:|---:|---:|---:|---:|---:|
| broad | 52.895% | 39.185% | 0.01399 | 52.743% | 49.327% | 0.01513 |
| balanced | 54.086% | 26.455% | 0.01689 | 54.086% | 26.455% | 0.01689 |
| selective | 54.664% | 18.148% | 0.01574 | 54.664% | 18.148% | 0.01574 |
| precision | 56.437% | 3.104% | 0.00722 | 56.437% | 3.104% | 0.00722 |

balanced/selective/precisionは確認期間中にstatic championから切り替わらなかった。broadは2024をProfile 0.515、2025と2026途中をSigned-body 0.52に切り替え、accuracyは+0.152ptだったがcoverageを-10.142pt失い、目的関数は-0.00114となった。

### 全nested期間

| role | router score | static score | 判定 |
|---|---:|---:|---|
| broad | 0.01660 | 0.01709 | static優位 |
| balanced | 0.01828 | 0.01856 | static優位 |
| selective | 0.01768 | 0.01768 | 同一 |
| precision | 0.01101 | 0.01145 | static優位 |

broadの年別scoreはProfileが2020/2022/2023/2025/2026途中、Signed-bodyが2021/2024に勝った。前年までの勝者を追うrouterは2022と2025以降で平均回帰に逆らう切替になり、固定Profileより悪化した。

Profile 0.515とSigned-body 0.52の選択集合も監査した。Signed-bodyはほぼProfileの部分集合で、confirmationの積集合は17,188件、accuracy 53.613%、score 0.01587だった。一方Profile単独の10,463件はaccuracy 51.314%だった。積集合は高精度だがSigned-body単独との差が47件しかなく、確認期間を見た後の派生ruleでもあるため新candidateにはしない。

## 判定

不採用。固定role championを維持する。候補pool自体が全履歴の研究後に確定しているため、このnested試験は選択規則の安定性監査であり、完全な候補生成時点まで再現したunbiased promotion試験ではない。今後のchampion交代は、今回のrouterで過去勝者を追うのではなく、固定並行運用したfresh期間の事前gateで行う。

