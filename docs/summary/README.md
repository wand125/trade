# Trade Research Summary

最終更新: 2026-07-03 08:03 JST

`docs/reports/` を読む前の入口。summaryでは詳細な実験ログを再掲せず、現在の判断、研究レーン、読む順番だけを管理する。

## まず読むもの

1. [Current Assessment](current_assessment.md)
   今の採用判断、主な失敗構造、次アクション。

2. [Report Map](report_map.md)
   `00001` から `00334` までのレポートを研究レーン別に圧縮した地図。

3. 詳細が必要なときだけ [../reports](../reports) の個別レポートを読む。

## 現時点の一文

標準採用できる利益最大化policyはまだない。標準判断は NoTrade-first のまま。

最新の診断bestは、q95 + raw `loss_exit30_cd15` dynamic exit cooldownを土台に、short entry-block replacement、require-model-used hold-extension、fixed60 family-aware uncertainty margin w5、entry-time position-quality overlayを重ねたbranch。`00318` から `00322` でnear-miss support候補をexit target化し、`00323` でsupport repairへ接続するとcombined `+362.7000` まで伸びた。`00326` ではrow x horizon化とhorizon penalty `0.25` によりcombined `+374.6110` まで伸びたが、`00327` でsupport-repair-only calibrationは失敗。`00329` でbroad priorをhorizon-choice rankerのfeatureへ入れ、低複雑度版はcombined `+403.2680` まで伸びた。`00330` lower-bound、`00331` harmful direct penalty、`00332` support-aware harmful penaltyはいずれもbaselineを超えない。`00334` でstateful selection直前の広い候補面をlistwise診断したが、baseline bestのactual oracle差は `+2.6360` のみ。EV -2ではoracle差 `+22.3190` まで増えるが、fresh2024 2024-08の悪い1候補はrerankingでは救えない。次はlistwise examplesを教師化し、fresh/thin monthの候補生成またはabstention層を作る。標準policyはNoTradeのまま。

## 更新ルール

新しい重要レポートを追加したら、次だけ更新する。

1. `current_assessment.md` の結論と次アクション。
2. `report_map.md` の該当レーン末尾。
3. 最新レポート番号の範囲。

all-window best、fixed test、validation-selected、prior-onlyは混同しない。最新判断はファイルmtimeや `更新日時:` ではなく本文内の作成時刻 `日時:` を基準にする。
