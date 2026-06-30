# Focus Entry Dynamic Hook

日時: 2026-06-30 11:06 JST
更新日時: 2026-06-30 11:10 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00199の `range_low_vol/ny_overlap` focused entry signalを、実際のdynamic hookとして `side_context_interaction_guard_apply.py` に追加した。
- 新しい `match_mode`:
  - `focus_short_entry_signal`
  - `signal_short_raw_gap_or_focus_short_entry`
- 00199のOR条件をそのまま `gap5/budget0` に重ねると、12ヶ月 totalは `+508.9838 -> +507.4968` へ小幅悪化し、worstも `-215.1172 -> -220.3612` へ悪化した。
- side-gap onlyも悪化した。rank-onlyは小幅改善し、`pred_short_entry_local_rank >= 0.53` が total `+511.5964`, worst `-215.1172` で、baseline比 `+2.6126`。
- ただし改善幅は小さく、replacement込みでは強いedgeにならない。標準採用せず、hookはdiagnostic infrastructureとして残す。

## Artifacts

- Main dynamic sweep: `data/reports/backtests/20260630_020200_20260630_110500_short_focus_entry_dynamic_hook/`
- Side-only sweep: `data/reports/backtests/20260630_020408_20260630_111000_short_focus_entry_dynamic_side_only/`
- Rank-only 0.52 sweep: `data/reports/backtests/20260630_020408_20260630_111000_short_focus_entry_dynamic_rank_only/`
- Rank-only 0.53 sweep: `data/reports/backtests/20260630_020512_20260630_111500_short_focus_entry_dynamic_rank053/`
- Rank-only 0.54 sweep: `data/reports/backtests/20260630_020512_20260630_111500_short_focus_entry_dynamic_rank054/`
- Rank-only 0.55 sweep: `data/reports/backtests/20260630_020440_20260630_111300_short_focus_entry_dynamic_rank055/`
- Strict OR sweep: `data/reports/backtests/20260630_020440_20260630_111300_short_focus_entry_dynamic_strict_or/`
- OR delta: `data/reports/backtests/20260630_020334_20260630_110700_short_focus_entry_union_vs_gap5_delta/`
- Rank 0.53 delta: `data/reports/backtests/20260630_020553_20260630_111700_short_focus_rank053_vs_gap5_delta/`

## Method

The dynamic hook blocks active rows through the existing `context_entry_budget=0` mechanism. This means the result includes the one-position constraint and the next replacement trade.

Base condition:

```text
signal_short_raw_gap:
  final signal is short
  AND pred_short_best_adjusted_pnl - pred_long_best_adjusted_pnl >= 5
```

Focus condition:

```text
final signal is short
AND combined_regime = range_low_vol
AND session_regime = ny_overlap
AND (
  pred_best_side_prob_-1 - pred_best_side_prob_1 <= focus_side_gap_threshold
  OR pred_short_entry_local_rank >= focus_entry_rank_threshold
)
```

The combined mode is:

```text
signal_short_raw_gap OR focus_short_entry_signal
```

All runs used:

```text
context_entry_budget = 0
context_drawdown_guard_loss_threshold = inf
context_drawdown_guard_min_entry_margin = inf
active_min_entry_margin = -inf
context_columns = dataset_month,combined_regime
loss_multiplier = 1.20
max_holding = 260m
```

## Results

12-month comparison:

| variant | focus side gap | focus rank | total PnL | delta vs gap5 | worst month | max DD | trades | short PnL |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| rank only | `-inf` | `0.52` | `+512.4444` | `+3.4606` | `-215.6452` | `215.6452` | `738` | `+168.1884` |
| rank only | `-inf` | `0.53` | `+511.5964` | `+2.6126` | `-215.1172` | `215.1172` | `738` | `+167.3404` |
| rank only | `-inf` | `0.54` | `+511.0028` | `+2.0190` | `-215.1172` | `215.1172` | `738` | `+166.7468` |
| strict OR | `-0.05` | `0.55` | `+510.2198` | `+1.2360` | `-215.3692` | `215.3692` | `738` | `+165.9638` |
| baseline gap5/budget0 | `0.00` | `0.52` | `+508.9838` | `0.0000` | `-215.1172` | `215.1172` | `738` | `+164.7278` |
| rank only | `-inf` | `0.55` | `+508.9598` | `-0.0240` | `-215.1172` | `215.1172` | `738` | `+164.7038` |
| OR from 00199 | `0.00` | `0.52` | `+507.4968` | `-1.4870` | `-220.3612` | `220.3612` | `737` | `+163.2408` |
| side gap only | `0.00` | `inf` | `+504.5282` | `-4.4556` | `-218.8492` | `219.7288` | `737` | `+160.2722` |
| focus only OR condition | `0.00` | `0.52` | `-79.4058` | `-588.3896` | `-282.9936` | `282.9936` | `949` | `-423.6618` |

Month deltas for the original OR condition:

| month | delta vs gap5 |
|---|---:|
| 2025-03 | `-1.5390` |
| 2025-05 | `+0.5964` |
| 2025-07 | `+0.1600` |
| 2025-09 | `-5.2440` |
| 2025-10 | `+4.7796` |
| 2025-12 | `-0.2400` |

For the original OR condition, 2025-10 improves because it removes `-18.4716` and admits `-13.6920`. But 2025-09 worsens because it removes `-41.1960` and admits `-46.4400`.

Month deltas for rank-only `0.53`:

| month | delta vs gap5 |
|---|---:|
| 2025-07 | `-2.1430` |
| 2025-10 | `+4.7796` |
| 2025-12 | `-0.0240` |

Rank `0.53` avoids the 2025-09 degradation and keeps worst/DD unchanged, but total improvement is only `+2.6126`.

## Interpretation

- 00199のreplacement-row preflightは、実行済みtradeを消した場合の上限診断としては有効だった。
- しかしdynamic hookでは、消した後に別のreplacement tradeが入る。ここで 2025-09 のように、削除tradeより悪いreplacementが発生する。
- side confidence gapは、dynamic policyとしては悪化した。現時点ではfocus contextのside-gap conditionを採用しない。
- entry rankは弱い改善があるが、改善幅は小さく、単独で採用するほどではない。
- 次に必要なのは、entry rowの削除条件を増やすことではなく、replacement後の候補品質を事前に見積もること。具体的には `only_candidate` replacementの損益を目的変数にして、同contextのreplacement riskを評価する。

## Decision

- `focus_short_entry_signal` / `signal_short_raw_gap_or_focus_short_entry` hookは accepted diagnostic infrastructure。
- OR condition from 00199 is rejected as standard policy.
- side-gap-only condition is rejected.
- rank-only `0.53` is a weak candidate, not standard policy.
- 次はreplacement-aware objectiveへ進む。`model-trade-delta` の `only_candidate` shortを、replacement risk targetとして扱う。

## Verification

- `python3 -m py_compile scripts/experiments/side_context_interaction_guard_apply.py tests/test_side_context_interaction_guard_apply.py`: OK
- `python3 -m unittest tests.test_side_context_interaction_guard_apply tests.test_backtest tests.test_short_budget_entry_signal_audit tests.test_short_budget_replacement_signal_audit tests.test_short_budget_replacement_trade_audit tests.test_short_budget_fixed_rule_audit tests.test_short_budget_drift_trigger_selection tests.test_short_budget_guard_selection tests.test_docs_reports`: OK, 127 tests
- `git diff --check`: OK
- Dynamic hook sweeps generated: OK
- Delta artifacts generated: OK
