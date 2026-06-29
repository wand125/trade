# Context Drawdown Guard Threshold Selection

日時: 2026-06-29 23:50 JST
更新日時: 2026-06-29 23:54 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- `scripts/experiments/context_drawdown_guard_selection.py` を追加し、online side-month drawdown guard のしきい値を対象月より前の月だけで選ぶ診断を作った。
- 入力は `context_drawdown_guard_apply.py` の `summary_by_run.csv`。各 target month に対し、prior months だけで `total`, `worst`, `risk_adjusted`, `risk_budget` 目的のしきい値を選び、target month の実績を集計する。
- 目的は `00180` の `threshold=40/60` が全12ヶ月を見た後知恵かどうかを分離すること。
- 結果として、total PnL基準は依然として `inf` や `60` を選びやすく、2025-09 の大崩れを防げない。worst-month基準はかなり防御的で、損失尾部を抑えるが取引数と利益機会を大きく削る。
- 現時点では標準policyへ昇格しない。採用するなら、利益最大化ではなく「月次tail riskを抑える事前登録済みrisk mandate」として扱う必要がある。

## Implementation

- reusable script: `scripts/experiments/context_drawdown_guard_selection.py`
- tests: `tests/test_context_drawdown_guard_selection.py`
- summary outputs:
  - `walkforward_selection.csv`
  - `walkforward_summary.csv`
  - `input_summary_by_run.csv`
  - `config.json`

Selection rules:

- `total`: prior total PnL最大。
- `worst`: prior worst-month PnL最大。
- `risk_adjusted`: `total + worst_weight * worst_month - drawdown_weight * max_drawdown`。
- `risk_budget`: 上記scoreに加え、prior worst-month / drawdown制約を満たす候補だけを優先する。候補0件なら fallback として全候補から選び、`selected_eligible=false` を残す。

## Artifacts

- Source apply run: `data/reports/backtests/20260629_143836_side_drift_guard_admission_margin10_online_side_month_drawdown/`
- Prior-only min 8 months: `data/reports/backtests/context_drawdown_guard_side_month_selection_min8/`
- Prior-only min 4 months: `data/reports/backtests/context_drawdown_guard_side_month_selection_min4/`
- Tight tail diagnostic: `data/reports/backtests/context_drawdown_guard_side_month_selection_tight_tail/`

All runs use profit `1.0`, loss `1.20`, coststress spread/slippage/delay, and the `p10 + margin10` monthly configs from `00178` / `00180`.

## Results

`min_train_months=8` means 2025-01..08 are needed before selecting, so target months are 2025-09..12.

| selection | target months | trades | total PnL | worst month | max monthly DD | selected thresholds |
|---|---:|---:|---:|---:|---:|---|
| `worst` | `4` | `54` | `-206.0758` | `-116.4516` | `116.4516` | `20` |
| `total` | `4` | `148` | `-480.8728` | `-289.0056` | `289.0056` | `60,inf` |
| `risk_adjusted_ww4_dw0p5` | `4` | `142` | `-450.7808` | `-289.0056` | `289.0056` | `40,inf` |

Interpretation:

- `worst` objective is the only simple prior-only rule that consistently avoids the `inf` crash path in 2025-09..12.
- It does not make the period profitable. It converts `future total -626.1752 / worst -289.0056` for fixed `inf` into `-206.0758 / -116.4516`.
- This is a risk-control improvement, not a PnL maximizer.

`min_train_months=4` starts selection at 2025-05, so target months are 2025-05..12.

| selection | target months | trades | total PnL | worst month | max monthly DD | selected thresholds |
|---|---:|---:|---:|---:|---:|---|
| `worst` | `8` | `448` | `63.3054` | `-116.4516` | `129.1668` | `20,inf` |
| `total` | `8` | `542` | `-211.4916` | `-289.0056` | `289.0056` | `60,inf` |
| `risk_adjusted_ww4_dw0p5` | `8` | `536` | `-181.3996` | `-289.0056` | `289.0056` | `40,inf` |

Interpretation:

- `worst` objective is strongest here because 2025-05..08では `inf` を選び、2025-09以降は prior tail risk を見て `20` へ寄る。
- ただし2025-08の悪化は完全には防げない。2025-09のような大崩れを prior-only で拾うには、2025-01..08側のtail evidenceを「利益より優先する」と事前に決める必要がある。

## Tight Tail Diagnostic

`risk_budget` に `min_validation_worst_month_pnl=-100/-80` を入れて、より厳しいtail制約を試した。

| selection | target months | trades | total PnL | worst month | max monthly DD | selected thresholds |
|---|---:|---:|---:|---:|---:|---|
| `risk_budget_ww4_dw0p5_minwm80` | `4` | `78` | `-278.2268` | `-116.4516` | `116.4516` | `20,40` |
| `risk_budget_ww1_minwm80` | `4` | `84` | `-308.3188` | `-116.4516` | `116.4516` | `20,60` |
| `risk_budget_ww1_minwm100` | `4` | `148` | `-480.8728` | `-289.0056` | `289.0056` | `60,inf` |

`minwm80` は2025-09の `inf` を事前に落とせるが、2025-10以降は制約を満たす候補がなく `selected_eligible=false` の fallback が混ざる。これは採用候補というより、tail制約を厳しくしたときの挙動確認として読む。

## Decision

- Fixed all-window `threshold=40/60` は後知恵なので標準採用しない。
- Prior-only `worst` objective は defensible な risk-control candidate だが、利益最大化の主policyではない。
- 次に採用候補へ進めるなら、先に mandate を固定する:
  - `side-month context`
  - `min_train_months=4` または `8`
  - `objective=worst`
  - `threshold candidates=20,40,60,80,120,inf`
- その後、未使用月または追加データで再探索なしに評価する。
- 代替案として、hard blockだけでなく「drawdown breach後の追加admission margin / cooldown / stay flat」を比較する。

## Verification

- `python3 -m py_compile scripts/experiments/context_drawdown_guard_selection.py`: OK
- `python3 -m unittest tests.test_context_drawdown_guard_selection`: OK
- `python3 -m py_compile src/trade_data/backtest.py scripts/experiments/context_drawdown_guard_apply.py scripts/experiments/residual_trade_failure_diagnostics.py scripts/experiments/context_drawdown_guard_selection.py`: OK
- `python3 -m unittest tests.test_backtest tests.test_residual_trade_failure_diagnostics tests.test_context_drawdown_guard_selection tests.test_docs_reports`: OK, 97 tests
