# Trade Research Summary

最終更新: 2026-07-02 13:38 JST

`docs/reports/` を読む前の入口。summaryでは詳細な実験ログを再掲せず、現在の判断、研究レーン、読む順番だけを管理する。

## まず読むもの

1. [Current Assessment](current_assessment.md)
   今の採用判断、主な失敗構造、次アクション。

2. [Report Map](report_map.md)
   `00001` から `00293` までのレポートを研究レーン別に圧縮した地図。

3. 詳細が必要なときだけ [../reports](../reports) の個別レポートを読む。

## 現時点の一文

標準採用できる利益最大化policyはまだない。標準判断は NoTrade-first のまま。

最新の有望軸だった `exit_regret_selector_confidenceexit_bucket_t0p4` とprior direction_regime guardは、`00267` でstateful replay上は改善したが、strict / relaxed admissionではrole support不足で NoTrade。`00274` のcoarse `direction_regime` tail-riskは外部HGB再現が弱くdiagnosticへ降格。`00276` / `00277` でlow loss-first dynamic exitを試し、`00278` でdynamic exit後cooldownを追加した。q95 + raw `loss_exit30_cd15` は外部+内部統合で total `+118.6900`, positive roles `6/6`, month min `-6.8324` まで改善した。`00279` のglobal expanding quantile化はtotalを伸ばす場合もあるがtail/role floorを壊すため、固定診断候補はraw `loss_exit30_cd15` のまま。`00280` で残存損失はentry無価値ではなく同方向oracle利益を実行exitで取り逃がす型が中心と確認した。`00281` ではprior exit-capture riskのhard blockとdirect score shrinkをreject。`00282` ではselected-trade supervised shrinkageがMAEを改善する一方、低score gateは勝ちtradeを削ると確認した。`00283` でshrinkage headをprediction row側へ戻したが、direct score replacementはmonth floorを壊した。`00284` ではdownside meta hard blockが悪化またはno-op。`00285` ではsoft risk marginもbaselineを大きく下回った。`00286` でcandidate-level stateful floor selectorを追加し、現候補群はfloor-onlyでもNoTradeと確認した。`00287` でpost-exit pathを分解し、`prev_loss` 後tradeは全体 `+122.9292` と強く、単純なpost-loss cooldown拡張は勝ちを削ると確認した。`00288` では isolated large-loss capture failure 23件 / `-125.5752` を特定したが、一律fixed-horizon置換はmonth floorを壊すためrejectした。`00289` ではhold-extension choiceをchronological supervised target化し、`isolated_loss` training + `isolated_large_loss` threshold 5がno-replay total `+246.7530`, month min `-6.8324` を示した。`00290` でこの候補をstateful replayへ接続し、total `+250.7350` まで改善したが、month min `-6.8324` は未改善でselectorはNoTrade。`00291` でside-aware fixed 720m replayを追加し、`isolated_large_loss_long` threshold `-5` は total `+318.8540`, month min `-4.1460` まで改善した。`00292` でhybrid 2025-12 short lossをentry block overlayで消すと total `+323.5700`, month min `-2.4566` まで改善した。`00293` でLondon short mid-loss blockとhold-extension false-positive blockを合成し、total `+329.4348`, role min `+0.5354`, month min `-0.7200` まで改善したが、24件blockのno-replacement overlayでselectorもNoTrade。次はremaining sparse negative monthsを単発blacklist化せず、full stateful policyへ昇格できる形か確認する。

## 更新ルール

新しい重要レポートを追加したら、次だけ更新する。

1. `current_assessment.md` の結論と次アクション。
2. `report_map.md` の該当レーン末尾。
3. 最新レポート番号の範囲。

all-window best、fixed test、validation-selected、prior-onlyは混同しない。最新判断はファイルmtimeや `更新日時:` ではなく本文内の作成時刻 `日時:` を基準にする。
