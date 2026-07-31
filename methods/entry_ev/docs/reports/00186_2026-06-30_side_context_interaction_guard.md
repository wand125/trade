# Side Context Interaction Guard

日時: 2026-06-30 08:21 JST
更新日時: 2026-06-30 08:21 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- `scripts/experiments/side_context_interaction_guard_apply.py` を追加した。
- 目的は `00185` の反省を受け、post-trade filterではなくdynamic backtestで低容量interactionを試すこと。
- 既存の side drift guard run (`p10 + replacement margin10`) を入力にし、`side_ev_penalty_rules` に該当する予測文脈だけ online context drawdown guard の対象にする。
- 非該当rowは一意な `inactive|...` contextに逃がし、通常trade同士のdrawdown連鎖を起こさない。
- 結論: `dataset_month + combined_regime` の `any_rule / threshold20` は totalを `-90.1378 -> -46.8210` へ改善したが、worst monthは `-289.0056 -> -292.2070` と悪化し、NoTradeにも届かない。標準採用しない。

## Artifacts

- Script: `scripts/experiments/side_context_interaction_guard_apply.py`
- Test: `tests/test_side_context_interaction_guard_apply.py`
- Month-only sweep: `data/reports/backtests/20260629_231817_side_context_interaction_guard_p10_margin10_v2/`
- Month + combined regime hard-block sweep: `data/reports/backtests/20260629_231922_side_context_interaction_guard_p10_margin10_month_regime/`
- Month + combined regime margin20 sweep: `data/reports/backtests/20260629_232024_side_context_interaction_guard_p10_margin10_month_regime_margin20/`

Input source:

- `data/reports/backtests/20260629_140836_side_drift_guard_admission_margin_isolated_2025_01_12_coststress_260/coststress_side_guard_p10_replm10`

## Method

Dynamic procedure:

1. Load each monthly source run and its `side_ev_penalty_rules`.
2. Rebuild the original model signal from the run's prediction parquet.
3. Mark rows matching side-drift guarded prediction context:
   - `any_rule`: row matches any side EV penalty rule condition.
   - `selected_side_rule`: row matches a side EV penalty rule and current selected signal has the same side.
4. For active rows, set context to `guarded|<context columns>`.
5. For inactive rows, set context to a unique `inactive|row=...|ts=...` value so repeated inactive trades cannot trigger the guard.
6. Run `run_backtest` with the usual one-position constraint, execution delay, spread/slippage, and context drawdown guard.

This is a true dynamic backtest path, unlike `00185`'s post-trade deletion diagnostic.

## Results

Baseline source run:

- total adjusted PnL `-90.1378`
- worst month `-289.0056`
- max monthly drawdown `289.0056`
- short PnL `-434.3938`
- long PnL `344.2560`
- trades `949`

### Month-only context

`context_columns=dataset_month`

| match mode | threshold | margin | trades | total PnL | worst month | max DD | active trades | active PnL | inactive PnL |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| selected_side_rule | `20` | `20` | `949` | `-90.1378` | `-289.0056` | `289.0056` | `4` | `-33.9092` | `-56.2286` |
| selected_side_rule | `20` | `inf` | `949` | `-90.1378` | `-289.0056` | `289.0056` | `4` | `-33.9092` | `-56.2286` |
| selected_side_rule | `40/60` | `20/inf` | `949` | `-90.1378` | `-289.0056` | `289.0056` | `4` | `-33.9092` | `-56.2286` |
| any_rule | `60` | `20/inf` | `949` | `-93.2048` | `-289.0056` | `289.0056` | `362` | `104.7236` | `-197.9284` |
| any_rule | `40` | `20/inf` | `946` | `-120.7624` | `-319.5820` | `319.5820` | `298` | `101.4458` | `-222.2082` |
| any_rule | `20` | `20/inf` | `943` | `-136.3612` | `-325.5976` | `325.5976` | `149` | `-20.1380` | `-116.2232` |

`selected_side_rule` is too narrow: only 4 executed trades are active, so nothing changes.

`any_rule` is too broad at month-only granularity: it changes path and worsens total/worst, even though some active-trade subsets remain positive.

### Month + combined regime context

`context_columns=dataset_month,combined_regime`

| match mode | threshold | margin | trades | total PnL | worst month | max DD | active trades | active PnL | inactive PnL |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| any_rule | `20` | `inf` | `945` | `-46.8210` | `-292.2070` | `292.2070` | `247` | `119.0370` | `-165.8580` |
| any_rule | `40` | `inf` | `949` | `-76.4336` | `-292.2070` | `292.2070` | `362` | `194.5640` | `-270.9976` |
| any_rule | `60` | `inf` | `949` | `-87.0950` | `-289.0056` | `289.0056` | `386` | `230.6940` | `-317.7890` |
| selected_side_rule | `20/40/60` | `inf` | `949` | `-90.1378` | `-289.0056` | `289.0056` | `4` | `-33.9092` | `-56.2286` |

Margin20 gave identical results:

| match mode | threshold | margin | trades | total PnL | worst month | max DD |
|---|---:|---:|---:|---:|---:|---:|
| any_rule | `20` | `20` | `945` | `-46.8210` | `-292.2070` | `292.2070` |
| any_rule | `40` | `20` | `949` | `-76.4336` | `-292.2070` | `292.2070` |
| any_rule | `60` | `20` | `949` | `-87.0950` | `-289.0056` | `289.0056` |

## Interpretation

- The interaction is directionally more sane than raw online context features: `dataset_month + combined_regime` improves total PnL by `+43.3168`.
- However, it does not improve the true risk objective:
  - worst month is slightly worse,
  - max drawdown is slightly worse,
  - short PnL remains `-434.3938`, unchanged.
- The apparent total improvement comes mainly from long-path changes, not from fixing the core late-year short drift.
- `selected_side_rule` has too little support; it captures only 4 executed trades.
- `any_rule` has enough support but still creates replacement/path effects that can worsen tail risk.

## Decision

- Keep the script as a dynamic interaction diagnostic.
- Do not promote this guard to standard policy.
- Do not use `selected_side_rule` as currently defined; support is too small.
- If continuing this branch, the next candidate should be a side-specific short drift interaction that directly targets the short side, not a general context drawdown guard:
  - side must be short,
  - prior context/side-month loss active,
  - prediction-side short bias high,
  - require strong entry margin or stay flat,
  - evaluate with true dynamic backtest only.

## Verification

- `python3 -m py_compile scripts/experiments/side_context_interaction_guard_apply.py tests/test_side_context_interaction_guard_apply.py`: OK
- `python3 -m unittest tests.test_backtest tests.test_context_drawdown_guard_selection tests.test_online_context_state_diagnostics tests.test_online_context_feature_model tests.test_side_context_interaction_guard_apply tests.test_docs_reports`: OK, 108 tests
