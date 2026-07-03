# Entry EV Support-Sufficient Horizon Abstention

日時: 2026-07-03 15:51 JST
更新日時: 2026-07-03 15:51 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00364でloss-riskをentry blockに使うとwinner damageが大きいと分かったため、同じsignalをfixed-horizon choiceのabstentionへ回した。
- `entry_ev_support_sufficient_horizon_abstention_diagnostics.py` を追加し、current exitとpredicted fixed-horizon argmaxの実現PnL差を教師/評価として、観測特徴と時系列priorで「predicted horizonを信じない」ruleを診断した。
- 全240 selected tradesでpredicted fixed-horizon argmaxを全採用すると、current exit比のextension deltaは `-221.4806`。
- 対象 `refit2025 2025-03` では、current month PnL `-0.4730` に対し、predicted fixed-horizon全採用は delta `-50.4340`、month PnL `-50.9070` まで崩れる。
- `lossfirst_ge0p40_or_pred_best_ge5_or_ev_lowlf` は対象月のharmful horizon 7/7をflagし、unflagged 2本のhelpだけを残す。target extension deltaは `-50.4340 -> +26.1200`。
- 同ruleは全240 tradesでも flagged extension delta `-428.8362` をabstainし、extension deltaを `-221.4806 -> +207.3556` へ反転させる。
- 判断: horizon abstention diagnosticsはaccepted infrastructure。`lossfirst_ge0p40_or_pred_best_ge5_or_ev_lowlf` はstateful replay candidate。ただしまだ標準policyではなく、実際のexit-extension hook / one-position constraintで再検証する。

## Artifacts

Added script:

- `scripts/experiments/entry_ev_support_sufficient_horizon_abstention_diagnostics.py`

Added tests:

- `tests/test_entry_ev_support_sufficient_horizon_abstention_diagnostics.py`

Run:

- `data/reports/backtests/20260703_065121_20260703_entry_ev_00365_support_sufficient_horizon_abstention/`

Outputs:

- `support_sufficient_horizon_abstention_target_trades.csv`
- `support_sufficient_horizon_abstention_month_summary.csv`
- `support_sufficient_horizon_abstention_prior_context.csv`
- `support_sufficient_horizon_abstention_prior_context_all_trades.csv`
- `support_sufficient_horizon_abstention_rule_hits.csv`
- `support_sufficient_horizon_abstention_rule_summary.csv`
- `support_sufficient_horizon_abstention_all_trade_features.csv`
- `support_sufficient_horizon_abstention_meta.json`

## Method

Target:

```text
refit2025_validation:2025-03:short
```

Outcome label:

```text
pred_extension_delta =
  actual_at_pred_fixed_best_horizon - current_adjusted_pnl
```

Interpretation:

- `pred_extension_delta < 0`: predicted fixed-horizon argmax is harmful; abstain should keep current exit.
- `pred_extension_delta > 0`: predicted fixed-horizon argmax helps; abstain would leave upside unused.

Important:

- Actual fixed-horizon PnL is used only for teacher/evaluation.
- Rule features are current selected-trade predictions and chronological prior using only earlier trades.
- This is not a replay yet. It estimates whether a future extension/exit-selector hook should abstain.

## Month Result

| metric | value |
|---|---:|
| current month PnL | `-0.4730` |
| predicted follow extension delta all | `-50.4340` |
| month PnL if follow predicted horizon all | `-50.9070` |
| month PnL if abstain all | `-0.4730` |
| trades | `9` |
| harmful predicted horizons | `7` |
| helpful predicted horizons | `2` |

## Rule Findings

Top abstention rules:

| rule | all flagged | all abstain delta | all extension delta after abstain | target flagged harm | target extension delta after abstain | reading |
|---|---:|---:|---:|---:|---:|---|
| `lossfirst_ge0p40_or_pred_best_ge5_or_ev_lowlf` | `190` | `+428.8362` | `+207.3556` | `7/7` | `+26.1200` | strongest target/all diagnostic, but broad |
| `lossfirst_ge0p40_or_pred_best_ge5_or_sidegap_lowlf` | `171` | `+427.6360` | `+206.1554` | `7/7` | `+26.1200` | similar, slightly narrower |
| `lossfirst_ge0p40_or_pred_best_ge5` | `134` | `+311.6366` | `+90.1560` | `6/7` | `+13.3724` | simpler candidate |
| `pred_best_ge5_or_h720_lossfirst_ge0p40` | `94` | `+273.2356` | `+51.7550` | `5/7` | `+4.9880` | narrower, misses two target harms |
| `loss_first_ge0p40` | `84` | `+231.6992` | `+10.2186` | `5/7` | `+4.4684` | target long/720 harmに強い |
| `pred_fixed_best_ge5` | `66` | `+323.4282` | `+101.9476` | `2/7` | `-24.6100` | allでは強いがtargetでは不足 |

Read:

- 00364のloss-risk signalはentry blockでは粗いが、horizon abstentionでは役割が明確になる。
- 特に `loss_first >= 0.40` はtarget long lossesとwinner `2025-03-31 short` のbad 720mを止める。
- `pred_fixed_best >= 5` や `EV>=5 & loss_first<0.30` はtarget short lossesのoverconfident fixed-horizon failureを止める。
- `pred_horizon_720` 単体は target でhelp rowも1件止め、全体でも extension delta after abstention `-107.4692` なので弱い。

## Target Trade Findings

Target predicted horizon failures:

| trade | current pnl | pred horizon | actual at pred horizon | delta | main abstention read |
|---|---:|---:|---:|---:|---|
| `2025-03-06 14:28 long` | `+0.4700` | `720m` | `-2.3160` | `-2.7860` | loss_first high + 720m |
| `2025-03-06 15:16 long` | `+0.0400` | `720m` | `-13.7040` | `-13.7440` | loss_first high + 720m |
| `2025-03-20 00:38 long` | `-0.6360` | `720m` | `-13.7040` | `-13.0680` | loss_first high + 720m |
| `2025-03-20 09:53 long` | `-0.1716` | `240m` | `-8.5560` | `-8.3844` | loss_first high |
| `2025-03-21 14:00 short` | `-2.3400` | `240m` | `-11.2440` | `-8.9040` | pred best >= 5 / low loss-first overconfidence |
| `2025-03-21 14:29 short` | `-0.3324` | `240m` | `-13.0800` | `-12.7476` | low loss-first overconfidence |
| `2025-03-31 03:40 short` | `+1.3800` | `720m` | `-15.5400` | `-16.9200` | loss_first high + pred best >= 5 |

Helpful unflagged rows under the broad candidate:

- `2025-03-07 15:01 short`: current `+0.5200`, pred 240m actual `+22.2500`, delta `+21.7300`
- `2025-03-27 11:28 long`: current `+0.5970`, pred 720m actual `+4.9870`, delta `+4.3900`

This is why target extension delta after abstention becomes `+26.1200`.

## Decision

- 00365 horizon abstention diagnostics are accepted infrastructure.
- `lossfirst_ge0p40_or_pred_best_ge5_or_ev_lowlf` is promoted to stateful replay candidate for predicted fixed-horizon extension.
- Do not use predicted fixed-horizon argmax without abstention.
- Do not interpret this as standard policy yet:
  - It is selected-trade counterfactual, not a full stateful replay.
  - Extension can skip later trades under one-position constraint.
  - The broad rule flags 190/240 trades, so execution impact must be measured directly.
- Standard policy remains NoTrade.

## Next

1. Add the abstention rule to the hold-extension / predicted fixed-horizon replay path.
2. Compare no-extension, predicted-horizon extension without abstention, and predicted-horizon extension with abstention.
3. Report skipped-trade impact under one-position constraint.
4. Keep actual fixed-horizon PnL as teacher/evaluation only.

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_support_sufficient_horizon_abstention_diagnostics.py tests/test_entry_ev_support_sufficient_horizon_abstention_diagnostics.py`: OK
- `uv run python -m unittest tests.test_entry_ev_support_sufficient_horizon_abstention_diagnostics`: OK
- 00365 support-sufficient horizon abstention diagnostic run: OK
