# Trade Research Summary

最終更新: 2026-07-01 08:31 JST

`docs/reports/` の大量レポートを読む前の入口。ここでは詳細ログを再掲せず、現在の判断、研究レーン、読む順番だけを管理する。

## まず読むもの

1. [Current Assessment](current_assessment.md)
   現時点の結論、採用状態、次に進めるべき検証。

2. [Report Map](report_map.md)
   `00001` から `00244` までのレポートをテーマ別に圧縮した地図。

3. 詳細が必要なときだけ [../reports](../reports) の個別レポートを読む。

## 現時点の一文

標準採用できる利益最大化policyはまだない。現在の標準判断は NoTrade-first で、採用できているのは検証インフラと診断レーンである。

最新の焦点は entry EV 系の再整理。絶対EV閾値、rank gate、quantile admission、hold-cap延長、prior inversion guard、executable EV、side-balance、composite hard gateを順に試したが、`00241` 時点では strict / relaxed / sensitivity の候補選定はすべて NoTrade。`00243` で `side_prior_pressure` がbaseよりAUC改善し、`00244` でprediction rowへ接続するとvalidationは改善した。ただし fixed 2025で崩れたため、標準policyはNoTradeのまま。

## 更新ルール

新しい重要レポートを追加したら、この順で更新する。

1. `current_assessment.md` の「現在の判断」と「次にやること」を更新する。
2. `report_map.md` の該当レーンに、レポート番号と結論を1行で追加する。
3. `standard policy`, `accepted infrastructure`, `diagnostic baseline`, `rejected` のどれかを明記する。
4. all-window best、validation-selected、fresh/fixed test、prior-only を混同しない。
5. レポートの最新判断はファイルmtimeや `更新日時:` ではなく、本文内の作成時刻 `日時:` を基準にする。
