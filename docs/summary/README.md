# Trade Research Summary

最終更新: 2026-07-02 19:40 JST

`docs/reports/` を読む前の入口。summaryでは詳細な実験ログを再掲せず、現在の判断、研究レーン、読む順番だけを管理する。

## まず読むもの

1. [Current Assessment](current_assessment.md)
   今の採用判断、主な失敗構造、次アクション。

2. [Report Map](report_map.md)
   `00001` から `00316` までのレポートを研究レーン別に圧縮した地図。

3. 詳細が必要なときだけ [../reports](../reports) の個別レポートを読む。

## 現時点の一文

標準採用できる利益最大化policyはまだない。標準判断は NoTrade-first のまま。

最新の診断bestは、q95 + raw `loss_exit30_cd15` dynamic exit cooldownを土台に、short entry-block replacement、require-model-used hold-extension、fixed60 family-aware uncertainty margin w5、entry-time position-quality overlayを重ねたbranch。`00314` でposition-quality overlay後 `+339.2910` / month min `-0.7200` まで改善したが、`00315` のtrade-set deltaで改善源はrefit2025の少数trade削除に集中し、`00316` のprior shrinkageではその改善を粗いpriorへ寄せるとraw `+107.0324` まで落ちると確認した。standard admissionはblocked、support2/shallow025でもblocked。標準policyはNoTradeのまま。

## 更新ルール

新しい重要レポートを追加したら、次だけ更新する。

1. `current_assessment.md` の結論と次アクション。
2. `report_map.md` の該当レーン末尾。
3. 最新レポート番号の範囲。

all-window best、fixed test、validation-selected、prior-onlyは混同しない。最新判断はファイルmtimeや `更新日時:` ではなく本文内の作成時刻 `日時:` を基準にする。
