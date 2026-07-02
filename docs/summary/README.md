# Trade Research Summary

最終更新: 2026-07-03 06:11 JST

`docs/reports/` を読む前の入口。summaryでは詳細な実験ログを再掲せず、現在の判断、研究レーン、読む順番だけを管理する。

## まず読むもの

1. [Current Assessment](current_assessment.md)
   今の採用判断、主な失敗構造、次アクション。

2. [Report Map](report_map.md)
   `00001` から `00328` までのレポートを研究レーン別に圧縮した地図。

3. 詳細が必要なときだけ [../reports](../reports) の個別レポートを読む。

## 現時点の一文

標準採用できる利益最大化policyはまだない。標準判断は NoTrade-first のまま。

最新の診断bestは、q95 + raw `loss_exit30_cd15` dynamic exit cooldownを土台に、short entry-block replacement、require-model-used hold-extension、fixed60 family-aware uncertainty margin w5、entry-time position-quality overlayを重ねたbranch。`00318` から `00322` でnear-miss support候補をexit target化し、`00323` でsupport repairへ接続するとcombined `+362.7000` まで伸びた。`00325` のactual-floor upper-boundはcombined `+371.6610`。`00326` ではrow x horizon化とhorizon penalty `0.25` により、actual-floorなしでもfresh2024 2024-08を720m `-29.1360` から60m `+2.9500` に切り替え、combined `+374.6110` まで伸びた。`00327` でsupport-repair-only chronological calibrationが失敗し、`00328` でbroad duration priorを導入した。broad priorは2024-08の悪い720mを事前警告できるが、direct penalty bestはcombined `+363.0870` で勝ち候補も削るため、標準policyはNoTradeのまま。

## 更新ルール

新しい重要レポートを追加したら、次だけ更新する。

1. `current_assessment.md` の結論と次アクション。
2. `report_map.md` の該当レーン末尾。
3. 最新レポート番号の範囲。

all-window best、fixed test、validation-selected、prior-onlyは混同しない。最新判断はファイルmtimeや `更新日時:` ではなく本文内の作成時刻 `日時:` を基準にする。
