# Trade Research Summary

最終更新: 2026-07-02 02:35 JST

`docs/reports/` の大量レポートを読む前の入口。ここでは詳細ログを再掲せず、現在の判断、研究レーン、読む順番だけを管理する。

## まず読むもの

1. [Current Assessment](current_assessment.md)
   現時点の結論、採用状態、次に進めるべき検証。

2. [Report Map](report_map.md)
   `00001` から `00262` までのレポートをテーマ別に圧縮した地図。

3. 詳細が必要なときだけ [../reports](../reports) の個別レポートを読む。

## 現時点の一文

標準採用できる利益最大化policyはまだない。現在の標準判断は NoTrade-first で、採用できているのは検証インフラと診断レーンである。

最新の焦点は entry EV 系の再整理。絶対EV閾値、rank gate、quantile admission、hold-cap延長、prior inversion guard、executable EV、side-balance、composite hard gateを順に試したが、標準候補はまだない。`00258` ではexit-regret riskをprediction rowへ戻し、`confidence_exit t0.4` hard selector q99/floor5がbroad/fixed2025で改善した。`00259` ではdeltaを分解し、s1 exposure baselineより良いが勝ちtrade削除とreplacement悪化が残ると確認した。`00260` ではreplacementを `replacement_stateful_net` targetで診断し、`conf_gap_extreme` をstateful replay candidateにした。`00261` では実際にreplacement guard replayを行い、q95/floor5もpositive化した。`00262` ではadmission gateへ通し、fresh2024の0-trade role support不足により標準policyはNoTradeのままと確認した。

## 更新ルール

新しい重要レポートを追加したら、この順で更新する。

1. `current_assessment.md` の「現在の判断」と「次にやること」を更新する。
2. `report_map.md` の該当レーンに、レポート番号と結論を1行で追加する。
3. `standard policy`, `accepted infrastructure`, `diagnostic baseline`, `rejected` のどれかを明記する。
4. all-window best、validation-selected、fresh/fixed test、prior-only を混同しない。
5. レポートの最新判断はファイルmtimeや `更新日時:` ではなく、本文内の作成時刻 `日時:` を基準にする。
