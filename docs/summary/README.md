# Trade Research Summary

最終更新: 2026-07-03 09:16 JST

`docs/reports/` を読む前の入口。summaryでは詳細な実験ログを再掲せず、現在の判断、研究レーン、読む順番だけを管理する。

## まず読むもの

1. [Current Assessment](current_assessment.md)
   今の採用判断、主な失敗構造、次アクション。

2. [Report Map](report_map.md)
   `00001` から `00340` までのレポートを研究レーン別に圧縮した地図。

3. 詳細が必要なときだけ [../reports](../reports) の個別レポートを読む。

## 現時点の一文

標準採用できる利益最大化policyはまだない。標準判断は NoTrade-first のまま。

最新の診断bestは、q95 + raw `loss_exit30_cd15` dynamic exit cooldownを土台に、short entry-block replacement、require-model-used hold-extension、fixed60 family-aware uncertainty margin w5、entry-time position-quality overlayを重ねたbranch。`00318` から `00322` でnear-miss support候補をexit target化し、`00323` でsupport repairへ接続するとcombined `+362.7000` まで伸びた。`00326` ではrow x horizon化とhorizon penalty `0.25` によりcombined `+374.6110` まで伸びたが、`00327` でsupport-repair-only calibrationは失敗。`00329` でbroad priorをhorizon-choice rankerのfeatureへ入れ、低複雑度版はcombined `+403.2680` まで伸びた。`00335` でsupport repairのactual PnL tie-breaker leakを修正し、同条件のleak-free replayはbest scenario combined `+400.1440`、EV -2 combined `+371.0080` へ下方修正された。`00336` でlistwise teacher化を診断したが、baseline bestのoracle改善は `+5.7600` だけ、EV -2の `fresh2024 2024-08 long -29.1360` はsingleton negativeでrerankingでは救えない。`00337` / `00338` でsingleton abstentionを広げ、available-onlyでは条件付きruleが同じ負けsingletonだけをpositive damage 0でflagしたが、unique負例は1件だけなので標準化しない。`00339` でthin-month候補面を見直すと、`fresh2024 2024-03` はoracle positiveがあるがmodel-used 0、`fresh2024 2024-11` / `refit2025 2025-03` は候補生成不足。`00340` でtarget-local confidenceを診断し、fresh03は60m/720mが大きく負け、240mだけが `+49.0950` と正で、exit timing / horizon confidence / EV calibrationが主弱点と確認した。単純threshold緩和、fallback採用、240m固定ruleはreject。標準policyはNoTradeのまま。

## 更新ルール

新しい重要レポートを追加したら、次だけ更新する。

1. `current_assessment.md` の結論と次アクション。
2. `report_map.md` の該当レーン末尾。
3. 最新レポート番号の範囲。

all-window best、fixed test、validation-selected、prior-onlyは混同しない。最新判断はファイルmtimeや `更新日時:` ではなく本文内の作成時刻 `日時:` を基準にする。
