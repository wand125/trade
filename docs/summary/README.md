# Trade Research Summary

最終更新: 2026-06-30 11:23 JST

このディレクトリは、`docs/reports/` の大量の実験レポートを俯瞰するための入口。

個別レポートは事実・実験条件・数値を残す場所で、この summary は「どの系列が何を示したか」「今どの判断状態か」を短時間で把握するために使う。

## 読む順番

1. [Current Assessment](current_assessment.md)
   現時点の研究評価、採用/保留/棄却の整理、次に検証すべき論点。

2. [Report Map](report_map.md)
   `00001` から `00201` までのレポート系列をテーマ別に圧縮した地図。

3. 詳細確認が必要なときだけ `../reports/` の個別レポートを読む。

## 現時点の要約

標準採用できる利益最大化policyはまだない。

研究基盤はかなり整っている。一方、実行policyの主な失敗は、2025-09..12 のような未知期間で short side に過剰に寄る side drift と、guard後の replacement trade が別の損失を作る点にある。

直近で有望なのは以下の「risk-control / diagnostic axis」だが、いずれも標準policyではない。

- `short` entry budget: repeated active short を制限する軸。`budget0` 追加で prior-only が大きく改善し、fixed `gap5 -> gap0` triggerもmin4..6では改善する。ただしmin8はNoTrade未満。00196..00201で、late common short、`gap5` replacement short、prior signal coverage、entry-level signal、dynamic hook、replacement risk targetを分解済み。次はprior deterioration trigger後だけのreplacement low-EV hookを検証する。
- online side-month drawdown guard: realized lossだけで発火する防御軸。`worst` objectiveならtailは削れるが利益policyではない。
- side drift guard + admission margin: bad short contextを検出し、弱いreplacementを抑える診断baseline。損失は大きく縮むがまだ負。
- `250..260m` holding max cap: holding側の安定化候補。ただし fresh failure はholdingではなくside driftが主因。

## Summary更新ルール

新しい重要レポートを追加したら、この順で更新する。

1. `current_assessment.md` の「現在の判断」を更新する。
2. `report_map.md` の該当テーマに、レポート番号と結論を1行で追加する。
3. 標準採用、診断baseline、棄却、保留のいずれかを明記する。
4. all-window best と prior-only / fresh-window の結果を混同しない。
5. `docs/reports/` の最新判断は、ファイルmtimeや `更新日時:` ではなく本文内の作成時刻 `日時:` を基準にする。
