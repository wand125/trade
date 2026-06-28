# 0008: Trade-analysis diagnostic gateをpost-hoc閾値でhard採用しない

日付: 2026-06-28 12:48 JST
状態: accepted

## 背景

2025-07 blindで候補AはNoTradeに負けた。失敗診断では、direction error、exit regret、EV overestimateが大きく、`model-sweep` と `model-candidate-selection` にtrade-analysis diagnostic列とgateを追加した。

ただし、2025-07の失敗を見た後に設定した閾値をそのまま次の候補選定に使うと、post-hoc overfittingになる。

詳細は `docs/reports/00030_2026-06-28_trade_analysis_diagnostic_gates.md` と `docs/reports/00031_2026-06-28_diagnostic_gate_validation.md`。

## 決定

trade-analysis diagnosticは今後の候補評価に必ず記録する。

一方で、2025-07 smokeで候補Aを落とせた以下の厳しい閾値は、hard gateとして採用しない。

- `max-direction-error-rate=0.50`
- `max-exit-regret-mean=15.0`
- `max-ev-overestimate-vs-realized-mean=10.0`

理由は、validation 4foldのhigh-turnover gridで候補が `0` 件になるため。

現時点では、diagnostic gateは以下の扱いにする。

- `balanced` 程度の閾値は、候補集合を壊さない安全診断として記録する。
- `focused` / `strict` は候補数が2件/1件に縮むため、追加validationで台地が見えるまで主採用基準にしない。
- 次のblind候補を固定する場合は、PnL、trade count、cost-aware成績、side/session損失、short share、smoothed missを主条件にし、diagnosticはtie-breakまたは失敗分析で使う。
- strict diagnostic thresholdを使う場合は、blindを見る前にvalidation-onlyで閾値、候補、根拠をレポートへ固定する。

## 影響

- 2025-07の失敗月に合わせた閾値をそのまま採用しないため、post-hoc overfittingを避ける。
- diagnostic列は候補比較に残るため、方向ミス、exit取り逃し、EV過大評価の悪化は継続監視できる。
- 次の主要改善は、厳しいgateで候補を削ることではなく、exit timing targetとEV calibration自体の改善へ寄せる。

## 代替案

- 2025-07 smoke-like gateをhard採用する: validation 4fold候補が0件になるため却下。
- strict gateで残る1候補を採用する: cost min pnlが低く、smoothed missが上限近く、台地が弱いため現時点では却下。
- diagnosticを完全に使わない: 2025-07で見えた失敗構造を候補選定に戻せなくなるため却下。
