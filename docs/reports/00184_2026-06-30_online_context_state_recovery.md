# Online Context State Recovery

日時: 2026-06-30 07:47 JST
更新日時: 2026-06-30 07:47 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- `scripts/experiments/online_context_state_diagnostics.py` を追加した。
- executed tradeごとに、entry時点で既に決済済みだった同一side/contextの累積PnL、trade数、breach有無、breachからの経過分、entry marginを付与する。
- 診断結果は「一度でもbreachしたか」より「現在も累積context PnLが閾値以下か」の方が悪化tradeをよく示した。
- その仮説をpolicyへ戻すため、`context_drawdown_guard_recover_after_pnl_recovery` を追加した。
- 結論: recovery modeは isolated `20/20` では改善するが、prior-only selectionでは `00182` の hard block / high margin 案を超えない。標準採用しない。

## Artifacts

- Online state diagnostics: `data/reports/backtests/20260629_223949_online_context_state_side_month_p10_margin10/`
- Recovery sweep: `data/reports/backtests/20260629_224339_context_drawdown_guard_side_month_recovery_sweep/`
- Prior-only selection min4: `data/reports/backtests/context_drawdown_guard_side_month_recovery_selection_min4/`
- Prior-only selection min8: `data/reports/backtests/context_drawdown_guard_side_month_recovery_selection_min8/`

Inputは `p10 + margin10` 月次run。`context_columns=dataset_month`, profit `1.0`, loss `1.20`, coststress spread/slippage/delay。

## Online State Diagnostic

`p10 + margin10` の全949 tradesを、entry時点のprior stateで診断した。

| threshold | mode | trades | total PnL | avg PnL | win rate | large loss rate | short PnL | long PnL |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| `20` | ever breached | `663` | `126.9766` | `0.1915` | `0.5249` | `0.0618` | `-97.6400` | `224.6166` |
| `20` | active loss breach | `241` | `-63.6502` | `-0.2641` | `0.4938` | `0.0871` | `-212.3328` | `148.6826` |
| `40` | ever breached | `257` | `-190.7018` | `-0.7420` | `0.5058` | `0.0934` | `-362.6990` | `171.9972` |
| `40` | active loss breach | `132` | `-230.9472` | `-1.7496` | `0.4545` | `0.1364` | `-350.9520` | `120.0048` |
| `60` | ever breached | `108` | `-225.7728` | `-2.0905` | `0.4352` | `0.1389` | `-280.5010` | `54.7282` |
| `60` | active loss breach | `86` | `-277.8980` | `-3.2314` | `0.3837` | `0.1628` | `-307.6910` | `29.7930` |

Interpretation:

- threshold `20` の `ever breached` はむしろプラス。永久blockは良い回復後tradeも消す。
- `active loss breach` は全thresholdで悪く、現在のprior context PnLは有効な状態量。
- ただし、active lossをblockすると、そのcontextは自力で回復できない。有限entry marginで強い再入場だけ許可し、そのtradeで累積PnLが回復したら通常状態へ戻す、というhookが必要。

## Recovery Mode

追加した設定:

- `context_drawdown_guard_recover_after_pnl_recovery=false`: 既存通り。breach後はhard blockまたは追加margin状態が月内継続。
- `true`: breach後でも有限marginやcooldownで許可されたtradeにより、累積context PnLが `-threshold` より上へ戻ったらbreach状態を解除する。

All-window shape check:

| threshold | margin | recovery | trades | total PnL | worst month | max DD | short PnL | long PnL |
|---:|---:|---|---:|---:|---:|---:|---:|---:|
| `60` | `20` | `false` | `842` | `142.9750` | `-153.6646` | `153.6646` | `-146.5528` | `289.5278` |
| `60` | `20` | `true` | `843` | `134.0626` | `-153.6646` | `153.6646` | `-155.4652` | `289.5278` |
| `40` | `20` | `false` | `693` | `107.9040` | `-138.4960` | `138.4960` | `-64.3548` | `172.2588` |
| `40` | `20` | `true` | `693` | `107.9040` | `-138.4960` | `138.4960` | `-64.3548` | `172.2588` |
| `20` | `20` | `true` | `327` | `-123.7850` | `-116.4516` | `116.4516` | `-243.4244` | `119.6394` |
| `20` | `20` | `false` | `292` | `-208.7024` | `-116.4516` | `116.4516` | `-328.3418` | `119.6394` |

Recovery helps the very defensive `20/20` path, mainly by improving short PnL, but it does not reach the all-window `40/60` family.

## Prior-Only Selection

`threshold + margin + recovery` を候補として、target monthより前だけで選択した。

| min train months | selection | target months | trades | total PnL | worst month | max DD | selected pattern |
|---:|---|---:|---:|---:|---:|---:|---|
| `4` | `worst` | `8` | `417` | `15.2092` | `-153.6646` | `153.6646` | `20/20/recover`, `60/20/no-recover` |
| `4` | `total` | `8` | `478` | `-78.5652` | `-153.6646` | `153.6646` | `60/20/no-recover` |
| `8` | `worst` | `4` | `56` | `-199.4438` | `-116.4516` | `116.4516` | `20/20/recover` |
| `8` | `total` | `4` | `117` | `-293.2182` | `-108.6910` | `145.5010` | `60/20/no-recover` |

For comparison, `00182` cooldownなし margin-aware prior-only `worst` was:

- min4: total `69.9374`, worst `-116.4516`, trades `450`
- min8: total `-199.4438`, worst `-116.4516`, trades `56`

Thus recovery does not improve the defensible prior-only family. It worsens min4 and ties min8 only because the same defensive path dominates.

## Decision

- Keep `online_context_state_diagnostics.py`; the prior-state enrichment is useful for future meta features and failure analysis.
- Keep `context_drawdown_guard_recover_after_pnl_recovery` as an experimental hook.
- Do not promote recovery mode to standard policy or risk mandate.
- Current best defensible guard remains `00182` prior-only `worst` objective with hard block / high re-entry margin.
- Next direction: use online context state as model/selection features rather than another hand-written guard. Candidate features:
  - prior side-month/context PnL,
  - prior context active loss breach,
  - prior context trade count,
  - minutes since breach,
  - interaction with side drift and entry margin.

## Verification

- `python3 -m py_compile src/trade_data/backtest.py scripts/experiments/context_drawdown_guard_apply.py scripts/experiments/online_context_state_diagnostics.py`: OK
- `python3 -m unittest tests.test_backtest tests.test_context_drawdown_guard_selection tests.test_online_context_state_diagnostics tests.test_docs_reports`: OK, 106 tests
