# Entry EV Near-Miss Exit Head

日時: 2026-07-02 20:38 JST
更新日時: 2026-07-02 20:38 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00319の次アクションとして、near-miss fixed-best targetをchronological exit-viability / horizon headへ接続した。
- `scripts/experiments/entry_ev_near_miss_exit_head.py` を追加し、評価月より前のnear-miss rowsだけで `target_fixed_executable` と `side_fixed_60/240/720m_adjusted_pnl` を予測した。
- default headはgreedy selectedで viability AUC `0.5556`、head選択horizonの実現平均 `-13.7712`。best thresholdでも `-17.8948`。
- available-only trainingはgreedy selectedのbest thresholdが `+3.1230` になるが、flagged 1件、`model_used=0` のfallback由来なのでpolicy evidenceではない。
- available candidates側は全設定で大きく負。bestでも `-232.0894`。
- 判断: chronological near-miss exit head infrastructureはaccepted。current head policyはreject。次はPnL regressionのargmaxではなく、horizon-specific binary viability / abstention設計へ切り替える。

## Artifacts

- New script:
  - `scripts/experiments/entry_ev_near_miss_exit_head.py`
- New tests:
  - `tests/test_entry_ev_near_miss_exit_head.py`
- Runs:
  - default: `data/reports/backtests/20260702_113736_20260702_entry_ev_00320_near_miss_exit_head_00319_s1/`
  - min train 1 month / 10 rows: `data/reports/backtests/20260702_113833_20260702_entry_ev_00320_near_miss_exit_head_00319_s2_m1r10/`
  - min train 3 months / 30 rows: `data/reports/backtests/20260702_113831_20260702_entry_ev_00320_near_miss_exit_head_00319_s3_m3r30/`
  - available-only training: `data/reports/backtests/20260702_113832_20260702_entry_ev_00320_near_miss_exit_head_00319_s4_available_train/`

## Method

Input:

```text
near_miss_exit_target_rows.csv from 00319
horizons = 60, 240, 720 minutes
chronological split = train rows with month < target month
default min train = 2 months / 20 rows
model = HistGradientBoosting classifier/regressors
```

Targets:

- `target_fixed_executable`
- `target_fixed_best_adjusted_pnl`
- `side_fixed_60m_adjusted_pnl`
- `side_fixed_240m_adjusted_pnl`
- `side_fixed_720m_adjusted_pnl`

Default decision-time features include side score, quantiles, entry rank, predicted fixed-horizon PnL, predicted exit-event fields, side/session/regime, family/role, and near-miss bucket.

Excluded from features:

- actual fixed-horizon PnL
- oracle best PnL
- target fixed-best labels
- prediction error columns
- `row_scope` / `selection_bucket`

## Main Results

Run comparison:

| run | scope | viability AUC | head actual rows | head actual mean | best threshold actual PnL | flagged | flagged model-used | best threshold |
|---|---|---:|---:|---:|---:|---:|---:|---|
| default | greedy selected | `0.5556` | `5` | `-13.7712` | `-17.8948` | `2` | `2` | prob `0.7`, EV `-5` |
| default | available candidates | `0.4728` | `56` | `-12.6593` | `-296.9364` | `11` | `11` | prob `0.7`, EV `2` |
| min 1m/10r | greedy selected | `0.5556` | `5` | `-13.7712` | `-17.8948` | `2` | `2` | prob `0.7`, EV `-5` |
| min 3m/30r | greedy selected | `0.5556` | `5` | `-13.7712` | `-17.8948` | `2` | `1` | prob `0.7`, EV `-5` |
| available train | greedy selected | `0.5833` | `5` | `-13.7712` | `+3.1230` | `1` | `0` | prob `0.5`, EV `2` |
| available train | available candidates | `0.5245` | `57` | `-12.1479` | `-232.0894` | `8` | `8` | prob `0.7`, EV `5` |

The only positive greedy-selected threshold comes from the available-only training run, but it flags the 2024-08 long row with no trained model. It is fallback behavior, not a learned edge.

## Failure Pattern

Available-only training greedy-selected rows show the key failure:

| row | target fixed-best | target horizon | predicted horizon | actual at predicted horizon | model used |
|---|---:|---:|---:|---:|---|
| fresh2024 2024-08 long | `+3.1230` | `240` | `240` | `+3.1230` | `False` |
| fresh2024 2024-11 long | `+2.4500` | `240` | `240` | `+2.4500` | `True` |
| refit2025 2025-07 short | `-2.4240` | `60` | `240` | `-20.3448` | `True` |
| refit2025 2025-08 short strict | `+19.9360` | `720` | `0` | none | `True` |
| refit2025 2025-08 short relaxed | `+11.3000` | `720` | `0` | none | `True` |
| refit2025 2025-08 short one-fail | `+15.0830` | `720` | `0` | none | `True` |
| hybrid2025 2025-10 long | `+13.5100` | `720` | `0` | none | `True` |
| hybrid2025 2025-11 short | `+0.8200` | `60` | `720` | `-39.9600` | `True` |

The head suppresses several positive 720m opportunities while still selecting the bad hybrid 2025-11 short 720m path. This is the same failure shape as 00319: the model struggles with horizon choice, especially distinguishing viable 720m extension from tail-loss 720m.

## Decision

Accepted:

- chronological near-miss exit head infrastructure
- prior-month-only training split for near-miss candidate rows
- threshold and model-used diagnostics for exit-head decisions

Rejected:

- current PnL-regression argmax horizon selector
- using available-only fallback positive row as policy evidence
- side-balanced support overlay with the current exit head

Standard policy remains NoTrade.

## Next

1. Replace PnL-regression argmax with horizon-specific binary viability heads:
   - `fixed60_executable`
   - `fixed240_executable`
   - `fixed720_executable`
2. Add abstention-first decision logic: choose a horizon only when its calibrated probability and expected PnL both pass, otherwise skip the near-miss support candidate.
3. Add an explicit 720m tail-loss classifier before allowing long-horizon exits.
4. Keep 00317 repair target as a gate; support count improvement is not progress if the exit head selects negative fixed paths.

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_near_miss_exit_head.py tests/test_entry_ev_near_miss_exit_head.py`: OK
- `uv run python -m unittest tests.test_entry_ev_near_miss_exit_head`: OK
- `uv run python -m unittest tests.test_entry_ev_near_miss_exit_head tests.test_entry_ev_near_miss_exit_target_diagnostics tests.test_docs_reports`: OK
- `git diff --check`: OK
- 00320 near-miss exit head runs: OK
