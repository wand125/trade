# Online Context Drawdown Guard

日時: 2026-06-29 23:41 JST
更新日時: 2026-06-29 23:41 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 決済済み実績だけを使う online drawdown guard を `run_backtest` / `model-policy` / `model-sweep` に追加した。
- 仕組み: `direction + context + entry month` ごとの実現adjusted PnLが `-threshold` 以下になったら、その月内の同side/context entryを以後ブロックする。
- これは未来情報を使わない。損失はtradeが決済されてからだけ反映される。
- `p10 + margin10` baselineに適用すると、細かい `combined_regime + session_regime` contextでは小改善止まり。
- 粗い `direction + dataset_month`、つまりside別月内drawdown guardでは total PnL がプラス化したが、同じ12ヶ月を見て閾値を選んでいるため標準採用しない。

## Implementation

- `ModelPolicyConfig.context_drawdown_guard_loss_threshold`
- `ModelPolicyConfig.context_drawdown_guard_context_columns`
- `ModelPolicyConfig.context_drawdown_guard_reset_monthly`
- `run_backtest(..., entry_context=..., context_drawdown_guard_loss_threshold=...)`
- reusable apply script: `scripts/experiments/context_drawdown_guard_apply.py`

## Artifacts

- combined + session context: `data/reports/backtests/20260629_143512_side_drift_guard_admission_margin10_online_context_drawdown_warm7/`
- combined-only context: `data/reports/backtests/20260629_143703_side_drift_guard_admission_margin10_online_context_drawdown_combined/`
- side-month context: `data/reports/backtests/20260629_143836_side_drift_guard_admission_margin10_online_side_month_drawdown/`

All runs used the original `p10 + margin10` monthly configs with `warmup_days=7`, `post_days=4`, profit `1.0`, loss `1.20`, coststress spread/slippage/delay.

## Results

Baseline `inf` matches `00178`: total PnL `-90.1378`, trades `949`, worst month `-289.0056`, max monthly DD `289.0056`.

`combined_regime + session_regime`:

| threshold | trades | total PnL | worst month | max monthly DD |
|---:|---:|---:|---:|---:|
| `20` | `931` | `-80.3404` | `-287.5092` | `287.5092` |
| `40` | `948` | `-82.9380` | `-269.1576` | `269.1576` |
| `inf` | `949` | `-90.1378` | `-289.0056` | `289.0056` |

`combined_regime` only:

| threshold | trades | total PnL | worst month | max monthly DD |
|---:|---:|---:|---:|---:|
| `20` | `889` | `-56.3298` | `-249.3830` | `249.3830` |
| `120` | `947` | `-76.3830` | `-275.0408` | `275.0408` |
| `inf` | `949` | `-90.1378` | `-289.0056` | `289.0056` |

Side-month guard using `dataset_month` as context:

| threshold | trades | total PnL | worst month | max monthly DD | short PnL | long PnL |
|---:|---:|---:|---:|---:|---:|---:|
| `60` | `841` | `135.6350` | `-153.6646` | `153.6646` | `-153.8928` | `289.5278` |
| `40` | `692` | `100.5640` | `-138.4960` | `138.4960` | `-71.6948` | `172.2588` |
| `80` | `863` | `-18.6608` | `-169.6200` | `170.0650` | `-292.2332` | `273.5724` |
| `inf` | `949` | `-90.1378` | `-289.0056` | `289.0056` | `-434.3938` | `344.2560` |
| `20` | `286` | `-217.1144` | `-116.4516` | `116.4516` | `-336.7538` | `119.6394` |

## Validation Check

If `2025-01..08` is treated as validation and `2025-09..12` as pseudo-future:

| threshold | validation total | validation worst | future total | future worst |
|---:|---:|---:|---:|---:|
| `inf` | `536.0374` | `-98.9364` | `-626.1752` | `-289.0056` |
| `60` | `436.1932` | `-153.6646` | `-300.5582` | `-108.6910` |
| `40` | `400.8352` | `-106.0940` | `-300.2712` | `-138.4960` |
| `20` | `-11.0386` | `-58.9360` | `-206.0758` | `-116.4516` |

Total PnLでvalidation選択すると `inf` が選ばれ、futureの大崩れを防げない。つまり `threshold=40/60` は全12ヶ月を見た後知恵であり、このまま標準採用してはいけない。

## Decision

- online guard infrastructure is useful and stays.
- `combined + session` context is too fine and activates late.
- side-month guard is promising as a risk control, but fixed threshold selection is unsolved.
- Do not standardize any drawdown threshold yet.
- Next work:
  - threshold selection objective must include tail risk / worst month, not only validation total PnL;
  - test a pre-registered defensive policy, e.g. `dataset_month threshold 60`, on later unseen months or a rolling walk-forward split;
  - consider a risk budget mode: maximize PnL subject to monthly side drawdown cap, rather than selecting by total PnL alone.

## Verification

- `python3 -m py_compile src/trade_data/backtest.py scripts/experiments/context_drawdown_guard_apply.py scripts/experiments/residual_trade_failure_diagnostics.py`: OK
- `python3 -m unittest tests.test_backtest tests.test_residual_trade_failure_diagnostics tests.test_docs_reports`: OK, 92 tests
