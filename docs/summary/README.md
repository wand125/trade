# Trade Research Summary

最終更新: 2026-07-02 08:25 JST

`docs/reports/` を読む前の入口。summaryでは詳細な実験ログを再掲せず、現在の判断、研究レーン、読む順番だけを管理する。

## まず読むもの

1. [Current Assessment](current_assessment.md)
   今の採用判断、主な失敗構造、次アクション。

2. [Report Map](report_map.md)
   `00001` から `00274` までのレポートを研究レーン別に圧縮した地図。

3. 詳細が必要なときだけ [../reports](../reports) の個別レポートを読む。

## 現時点の一文

標準採用できる利益最大化policyはまだない。標準判断は NoTrade-first のまま。

最新の有望軸だった `exit_regret_selector_confidenceexit_bucket_t0p4` とprior direction_regime guardは、`00267` でstateful replay上は改善したが、strict / relaxed admissionではrole support不足で NoTrade。`00269` の外部HGB preflight、`00270` の外部full-hybrid preflightでも NoTrade 未満。`00271` の損失分解ではno-edge entryではなくexit-capture failure / executable EV過大評価が中心だった。`00272` ではpost-selector executable EV補正もNoTrade未満。`00273` でselector前capture補正はpost-selector補正より改善したがNoTrade未満。`00274` でcoarse `direction_regime` tail-riskを重ねるとq99は `+3.1260` まで改善したが、3 trades/all-long/month floor未達で標準判断はNoTrade。

## 更新ルール

新しい重要レポートを追加したら、次だけ更新する。

1. `current_assessment.md` の結論と次アクション。
2. `report_map.md` の該当レーン末尾。
3. 最新レポート番号の範囲。

all-window best、fixed test、validation-selected、prior-onlyは混同しない。最新判断はファイルmtimeや `更新日時:` ではなく本文内の作成時刻 `日時:` を基準にする。
