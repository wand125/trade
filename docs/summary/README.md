# Trade Research Summary

最終更新: 2026-07-03 10:49 JST

`docs/reports/` を読む前の入口。summaryでは詳細な実験ログを再掲せず、現在の判断、研究レーン、読む順番だけを管理する。

## まず読むもの

1. [Current Assessment](current_assessment.md)
   今の採用判断、主な失敗構造、次アクション。

2. [Report Map](report_map.md)
   `00001` から `00346` までのレポートを研究レーン別に圧縮した地図。

3. 詳細が必要なときだけ [../reports](../reports) の個別レポートを読む。

## 現時点の一文

標準採用できる利益最大化policyはまだない。標準判断は NoTrade-first のまま。

最新の診断bestは、q95 + raw `loss_exit30_cd15` dynamic exit cooldownを土台に、short entry-block replacement、require-model-used hold-extension、fixed60 family-aware uncertainty margin w5、entry-time position-quality overlayを重ねたbranch。`00318` から `00322` でnear-miss support候補をexit target化し、`00323` でsupport repairへ接続するとcombined `+362.7000` まで伸びた。`00326` ではrow x horizon化とhorizon penalty `0.25` によりcombined `+374.6110` まで伸びたが、`00327` でsupport-repair-only calibrationは失敗。`00329` でbroad priorをhorizon-choice rankerのfeatureへ入れ、低複雑度版はcombined `+403.2680` まで伸びた。`00335` でsupport repairのactual PnL tie-breaker leakを修正し、同条件のleak-free replayはbest scenario combined `+400.1440`、EV -2 combined `+371.0080` へ下方修正された。`00339` でthin-month候補面を見直すと、`fresh2024 2024-03` はoracle positiveがあるがmodel-used 0、`fresh2024 2024-11` / `refit2025 2025-03` は候補生成不足。`00340` から `00344` でfresh03のhorizon confidence / tail/reliability calibrationを確認し、tail support gateやreliability-gated scoreのdirect multiplierはplain `pnl +400.1440` を超えない。`00345` でreliability-driven switchのabstentionを診断すると、`ranker_pred_pnl < 0` vetoがavailable candidatesでreliability-gated悪化を回復したが、`00346` でstateful replayへ戻すとbestはplain `pnl` と同じ5 trades / combined `+400.1440` のまま、selector pass 0件だった。標準policyはNoTradeのまま。

## 更新ルール

新しい重要レポートを追加したら、次だけ更新する。

1. `current_assessment.md` の結論と次アクション。
2. `report_map.md` の該当レーン末尾。
3. 最新レポート番号の範囲。

all-window best、fixed test、validation-selected、prior-onlyは混同しない。最新判断はファイルmtimeや `更新日時:` ではなく本文内の作成時刻 `日時:` を基準にする。
