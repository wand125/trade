# Short Entry Budget Guard

日時: 2026-06-30 08:43 JST
更新日時: 2026-06-30 08:43 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- `run_backtest` に `entry_budget_context` / `context_entry_budget` を追加した。
- `scripts/experiments/side_context_interaction_guard_apply.py` に `--entry-budgets` を追加し、active contextだけに月次entry count budgetをかけられるようにした。
- `signal_short_raw_gap` のactive short contextに対し、drawdownではなく「同一月・同一regimeのshort入場回数」を制限するdynamic backtestを実行した。
- 全12ヶ月を見ると `short_gap=5, context_entry_budget=1` が total `+369.3640`、worst `-202.8332`、short PnL `+25.1080` まで改善した。
- prior-only selectionでは min4/worst が total `-15.9692`、worst `-132.1382` まで改善したが、まだNoTradeを上回らない。min8/worst は total `-240.2230`。
- 標準採用はしないが、short exposure budgetはこれまでの手法より有望な制御軸として残す。

## Artifacts

- Budget-only sweep: `data/reports/backtests/20260629_233936_short_raw_gap_entry_budget_p10_margin10/`
- Budget-only prior selection min4: `data/reports/backtests/short_raw_gap_entry_budget_selection_min4/`
- Budget-only prior selection min8: `data/reports/backtests/short_raw_gap_entry_budget_selection_min8/`
- Budget + drawdown sweep: `data/reports/backtests/20260629_234124_short_raw_gap_entry_budget_drawdown_p10_margin10/`
- Budget + drawdown prior selection min4: `data/reports/backtests/short_raw_gap_entry_budget_drawdown_selection_min4/`
- Budget + drawdown prior selection min8: `data/reports/backtests/short_raw_gap_entry_budget_drawdown_selection_min8/`

Input source:

- `data/reports/backtests/20260629_140836_side_drift_guard_admission_margin_isolated_2025_01_12_coststress_260/coststress_side_guard_p10_replm10`

## Method

The budget key is based on:

```text
entry decision month
direction
entry_budget_context
```

In this experiment, `entry_budget_context` is the same guarded/inactive context produced by `side_context_interaction_guard_apply.py`:

```text
guarded|dataset_month=<month>|combined_regime=<regime>
inactive|row=<row>|ts=<timestamp>
```

Therefore the finite budget only constrains repeated active short entries in the same month/regime. Inactive rows are unique and are effectively unconstrained.

This is a true dynamic backtest hook:

- one-position constraint remains active,
- replacement trades are simulated,
- execution delay, spread, slippage, and max holding are still applied,
- the budget count increments only when an entry actually opens.

## All-Window Budget Sweep

Baseline source run:

- total adjusted PnL `-90.1378`
- worst month `-289.0056`
- max monthly drawdown `289.0056`
- short PnL `-434.3938`
- long PnL `344.2560`
- trades `949`

Top budget-only candidates:

| short gap | budget | trades | total PnL | worst month | max DD | short PnL | long PnL | active trades | active PnL |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `5` | `1` | `783` | `369.3640` | `-202.8332` | `202.8332` | `25.1080` | `344.2560` | `82` | `-79.2034` |
| `5` | `2` | `819` | `332.9380` | `-183.2732` | `195.7228` | `-11.3180` | `344.2560` | `155` | `-147.3666` |
| `5` | `3` | `843` | `318.2672` | `-195.7808` | `204.1828` | `-25.9888` | `344.2560` | `212` | `-321.9532` |
| `0` | `1` | `628` | `281.8854` | `-118.5098` | `128.6044` | `-62.3706` | `344.2560` | `85` | `-90.5052` |
| `5` | `5` | `895` | `100.8758` | `-263.1580` | `263.1580` | `-243.3802` | `344.2560` | `304` | `-494.8930` |
| `0` | `2` | `691` | `97.1244` | `-138.2384` | `142.2384` | `-247.1316` | `344.2560` | `161` | `-225.2828` |

Monthly results for all-window best `short_gap=5, budget=1`:

| month | trades | total PnL | short PnL | long PnL | max DD | active trades | active PnL |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2025-01 | `92` | `106.6932` | `36.1512` | `70.5420` | `51.6650` | `6` | `9.5082` |
| 2025-02 | `89` | `82.6516` | `52.1268` | `30.5248` | `52.5472` | `6` | `-4.1016` |
| 2025-03 | `102` | `93.5256` | `19.9948` | `73.5308` | `82.7082` | `6` | `-15.3860` |
| 2025-04 | `48` | `291.7814` | `199.6124` | `92.1690` | `56.1230` | `8` | `117.4270` |
| 2025-05 | `64` | `42.9982` | `89.0052` | `-46.0070` | `71.3360` | `8` | `18.6960` |
| 2025-06 | `60` | `156.4992` | `28.1062` | `128.3930` | `47.0592` | `7` | `23.5020` |
| 2025-07 | `114` | `86.0630` | `82.5182` | `3.5448` | `129.7364` | `6` | `-6.7064` |
| 2025-08 | `90` | `-63.8486` | `-41.8002` | `-22.0484` | `133.5398` | `6` | `-21.1900` |
| 2025-09 | `68` | `-202.8332` | `-189.8612` | `-12.9720` | `202.8332` | `7` | `-66.7648` |
| 2025-10 | `20` | `-33.8606` | `-43.8806` | `10.0200` | `89.7922` | `7` | `-40.2010` |
| 2025-11 | `15` | `-118.6978` | `-141.2368` | `22.5390` | `122.6978` | `7` | `-86.6888` |
| 2025-12 | `21` | `-71.6080` | `-65.6280` | `-5.9800` | `71.6080` | `8` | `-7.2980` |

Interpretation:

- Budgeting repeated active short entries is much more effective than only adding raw score gap.
- It turns total short PnL from `-434.3938` to `+25.1080`.
- It does not remove the 2025-09/11 losses, but it materially caps them.
- `gap=0, budget=1` has lower total but much better worst month / max DD, so this axis is a risk-vs-return surface rather than a single sharp optimum.

## Budget + Drawdown Check

Adding context drawdown hard guard did not materially improve the strict budget cases:

- `gap=5, budget=1` is identical for threshold `20/40/60/inf`: total `369.3640`.
- `gap=0, budget=1` is also identical for threshold `20/40/60/inf`: total `281.8854`.
- Some looser cases improve slightly with threshold `20`, e.g. `gap=0, budget=2, threshold=20` total `137.7604` versus budget-only `97.1244`, but this did not improve prior-only selection.

## Prior-Only Selection

Budget-only candidate columns:

```text
short_gap_threshold,
context_entry_budget
```

### min_train_months=4

| selection | target months | trades | total PnL | worst month | max DD | short PnL | selected pattern |
|---|---:|---:|---:|---:|---:|---:|---|
| worst | `8` | `439` | `-15.9692` | `-132.1382` | `142.2328` | `-93.4586` | `gap0/budget1`, `gap0/budget2`, `gap5/budget1`, `gap5/budget3` |
| risk_adjusted_ww4 and risk_budget family | `8` | `454` | `-79.6118` | `-195.7808` | `204.1828` | `-157.1012` | `gap0/budget1`, `gap5/budget1`, `gap5/budget3` |
| total | `8` | `490` | `-285.1334` | `-195.7808` | `204.1828` | `-362.6228` | `gap5/budget1`, `gap5/budget3` |

### min_train_months=8

| selection | target months | trades | total PnL | worst month | max DD | short PnL | selected pattern |
|---|---:|---:|---:|---:|---:|---:|---|
| worst | `4` | `95` | `-240.2230` | `-132.1382` | `142.2328` | `-253.8300` | `gap0/budget1`, `gap0/budget2` |
| risk_adjusted_ww4 and risk_budget family | `4` | `110` | `-303.8656` | `-195.7808` | `204.1828` | `-317.4726` | `gap0/budget1`, `gap5/budget3` |
| total | `4` | `146` | `-509.3872` | `-195.7808` | `204.1828` | `-522.9942` | `gap5/budget3` |

Budget + drawdown prior selection produced the same top conclusions:

- min4/worst total `-15.9692`
- min8/worst total `-240.2230`
- drawdown threshold selection mainly chose `20` or `60`, but did not change the target aggregate outcome.

## Decision

- Keep `context_entry_budget` as a core experimental hook.
- Do not promote a standard policy yet because prior-only selection still does not beat NoTrade.
- This is a meaningful improvement over `00187`: the same short-bias family moved from min4/worst `-274.9360` to `-15.9692`.
- The next research step should make the budget rule target-month-independent more directly:
  - select budget from prior short-side deterioration, not total/worst aggregate alone,
  - add prior short active PnL and recent short losing-month count as selection features,
  - test a fixed defensive mandate such as `gap0/budget1` or `gap0/budget2` on additional unseen months/data.

## Verification

- `python3 -m py_compile src/trade_data/backtest.py scripts/experiments/side_context_interaction_guard_apply.py tests/test_backtest.py tests/test_side_context_interaction_guard_apply.py`: OK
- `python3 -m unittest tests.test_backtest tests.test_context_drawdown_guard_selection tests.test_online_context_state_diagnostics tests.test_online_context_feature_model tests.test_side_context_interaction_guard_apply tests.test_docs_reports`: OK, 111 tests
- `git diff --check`: OK
