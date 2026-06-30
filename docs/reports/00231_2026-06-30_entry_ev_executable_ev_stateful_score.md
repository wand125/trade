# Entry EV Executable EV Stateful Score

日時: 2026-06-30 18:19 JST
更新日時: 2026-06-30 18:21 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00230の次アクションとして、post-trade selector featureではなく、実際の `timed_ev` stateful policyのentry scoreをexecutable EVへ差し替える診断を追加した。
- `scripts/experiments/entry_ev_executable_ev_policy_inputs.py` は、対象月より前のselected tradeだけから `direction + combined_regime + session_regime` 別capture factorを作り、prediction parquet全行に `pred_executable_calibrated_long_best_adjusted_pnl` / `short` と `pred_executable_*_pct_*` quantile列を追加する。
- 結論: stateful score replacementは有効な改善軸。refit2025のlong過剰選択は大きく縮み、`720m q99 floor5` はvalidation total `+43.0418`, min role `+2.4158` まで改善した。
- ただしNoTrade-first gateはまだ通らない。最良候補の `720m q99 floor5` は validation min month `-1.8000` と `month_trades_low` で落ち、fresh fixed diagnosticにも `2024-10 -10.3560` が残る。
- floorなしは大きく悪化し、floor `2/3/4` も安定台地を作れなかった。標準policyはNoTradeのまま。

## Artifacts

- Script: `scripts/experiments/entry_ev_executable_ev_policy_inputs.py`
- Test: `tests/test_entry_ev_executable_ev_policy_inputs.py`
- Executable EV prediction inputs:
  - `data/reports/backtests/20260630_091330_20260630_entry_ev_executable_ev_policy_inputs/`
- Stateful backtest, `720m`, floor `5/10`:
  - `data/reports/backtests/20260630_091445_20260630_entry_ev_executable_ev_policy_backtest_720/`
- Selector, `720m`, floor `5/10`, relaxed trade support:
  - `data/reports/backtests/20260630_091525_20260630_entry_ev_executable_ev_policy_selector_720_relaxed_trades/`
- Stateful backtest, `260m`, floor `5/10`:
  - `data/reports/backtests/20260630_091543_20260630_entry_ev_executable_ev_policy_backtest_260/`
- Selector, `260m`, floor `5/10`, relaxed trade support:
  - `data/reports/backtests/20260630_091615_20260630_entry_ev_executable_ev_policy_selector_260_relaxed_trades/`
- Stateful backtest, `720m`, floorなし:
  - `data/reports/backtests/20260630_091635_20260630_entry_ev_executable_ev_policy_backtest_720_nofloor/`
- Selector, `720m`, floorなし:
  - `data/reports/backtests/20260630_091728_20260630_entry_ev_executable_ev_policy_selector_720_nofloor_relaxed_trades/`
- Stateful backtest, `720m`, floor `2/3/4/5` sweep:
  - `data/reports/backtests/20260630_091745_20260630_entry_ev_executable_ev_policy_backtest_720_floor_sweep/`
- Selector, `720m`, floor sweep:
  - `data/reports/backtests/20260630_091856_20260630_entry_ev_executable_ev_policy_selector_720_floor_sweep_relaxed_trades/`

## Method

Prediction input generation:

```text
prior trades:
  roles = cal2024_calibration_validation,
          fresh2024_validation,
          refit2025_validation
  candidates = q95/q99 sg95 rank90 floor5/floor10
  dedupe = month + entry_decision_timestamp + direction
           + combined_regime + session_regime

capture_ratio = adjusted_pnl / actual_taken_best_adjusted_pnl
capture_ratio is computed only when actual_taken_best_adjusted_pnl > 0
capture_ratio is clipped to [0, 1]

executable_capture_factor =
  (1 - support_weight) * global_capture_factor
  + support_weight * context_capture_factor

support_weight = clip(prior_context_capture_count / 4, 0, 1)

pred_executable_calibrated_side_EV =
  pred_calibrated_side_best_adjusted_pnl * executable_capture_factor
```

This is prior-only by target month. Same-month and future realized PnL are not used for the target month factor.

Policy evaluation:

```text
policy = timed_ev
long_column  = pred_executable_calibrated_long_best_adjusted_pnl
short_column = pred_executable_calibrated_short_best_adjusted_pnl
score_kind   = executable
loss_multiplier = 1.20
profit_multiplier = 1.00
```

## Prediction Effect

Selected side / score scale after executable EV replacement:

| family/month | base long share | executable long share | side switch share | base q95 | executable q95 | long factor | short factor |
|---|---:|---:|---:|---:|---:|---:|---:|
| cal2024 `2024-01` | `0.3443` | `0.3443` | `0.0000` | `11.2200` | `11.2200` | `1.0000` | `1.0000` |
| cal2024 `2024-02` | `0.4063` | `0.4011` | `0.3325` | `11.1627` | `3.5643` | `0.1806` | `0.2041` |
| fresh2024 `2024-03` | `0.2907` | `0.3500` | `0.2269` | `12.0795` | `5.3849` | `0.2081` | `0.2365` |
| fresh2024 `2024-04` | `0.1458` | `0.2873` | `0.2235` | `15.6104` | `5.4560` | `0.1693` | `0.1981` |
| refit2025 `2025-01` | `0.9170` | `0.4367` | `0.5390` | `23.5228` | `7.6310` | `0.1476` | `0.1870` |
| refit2025 `2025-02` | `0.9150` | `0.4705` | `0.4996` | `23.7344` | `7.5813` | `0.1516` | `0.2051` |

Interpretation:

- executable EV replacement directly changes side choice, not only admission.
- refit2025のlong share `~0.91` が `~0.44..0.47` へ下がり、00217で見たlong EV scale driftはかなり緩む。
- fresh2024ではlong shareが上がるが、これはshort側だけを消す単純guardではなく、side別capture factorによるscore replacementの結果。

## Stateful Results

### `720m`, floor `5/10`

Relaxed selector gates (`min_role_trades=1`, `min_month_trades=1`, `max_side_share=0.95`) still select NoTrade.

| candidate | eligible | blockers | validation total | min role | min month | validation trades | fixed total | fixed min month |
|---|---|---|---:|---:|---:|---:|---:|---:|
| q99 floor5 | false | `month_pnl_below_floor;month_trades_low` | `+43.0418` | `+2.4158` | `-1.8000` | `19` | `+77.7010` | `-10.3560` |
| q99 floor10 | false | `positive_roles_low;active_roles_low;month_pnl_below_floor;role_trades_low;month_trades_low` | `+26.2884` | `0.0000` | `-1.8000` | `10` | `+46.8000` | `0.0000` |
| q95 floor5 | false | `positive_roles_low;role_total_pnl_below_floor;month_pnl_below_floor` | `+81.7238` | `-1.6986` | `-2.3640` | `40` | `+112.0732` | `-13.6956` |
| q95 floor10 | false | `positive_roles_low;active_roles_low;role_total_pnl_below_floor;month_pnl_below_floor;role_trades_low;month_trades_low` | `+6.4600` | `-11.2600` | `-9.4600` | `22` | `+46.8000` | `0.0000` |

The closest row is q99 floor5:

| role/month | PnL | trades | long | short |
|---|---:|---:|---:|---:|
| cal2024 `2024-01` | `+4.2158` | `9` | `6` | `3` |
| cal2024 `2024-02` | `-1.8000` | `1` | `0` | `1` |
| fresh2024 `2024-03` | `0.0000` | `0` | `0` | `0` |
| fresh2024 `2024-04` | `+4.4270` | `1` | `0` | `1` |
| refit2025 `2025-01` | `+29.3900` | `3` | `1` | `2` |
| refit2025 `2025-02` | `+6.8090` | `5` | `3` | `2` |
| fixed `2024-10` | `-10.3560` | `1` | `0` | `1` |
| fixed `2024-11` | `+71.5670` | `4` | `0` | `4` |

This is much closer than previous q95/q99 validation rows, but still too sparse and fails month floor.

### `260m`, floor `5/10`

`260m` is worse than `720m` under executable score replacement.

| candidate | eligible | blockers | validation total | min role | min month | validation trades | fixed total | fixed min month |
|---|---|---|---:|---:|---:|---:|---:|---:|
| q99 floor5 | false | `month_pnl_below_floor;month_trades_low` | `+33.4638` | `+2.7978` | `-1.5240` | `20` | `+25.9180` | `-11.4720` |
| q95 floor5 | false | `positive_roles_low;total_pnl_below_floor;role_total_pnl_below_floor;month_pnl_below_floor` | `-14.5208` | `-17.1110` | `-12.5400` | `41` | `+60.1580` | `-18.8280` |

This confirms 720m remains the better diagnostic cap for these entry-EV candidates.

### No Floor

Removing the floor is not viable:

| candidate | eligible | blockers | validation total | min role | min month | validation trades | fixed total | fixed min month |
|---|---|---|---:|---:|---:|---:|---:|---:|
| q95 no floor | false | `positive_roles_low;total_pnl_below_floor;role_total_pnl_below_floor;month_pnl_below_floor` | `-36.5868` | `-26.1964` | `-48.3044` | `121` | `+150.7354` | `-11.7422` |
| q99 no floor | false | `positive_roles_low;total_pnl_below_floor;role_total_pnl_below_floor;month_pnl_below_floor` | `-51.2934` | `-31.1176` | `-48.1876` | `55` | `-9.3750` | `-30.1466` |

Small positive executable EV entries still admit tail losses. Executable score replacement does not remove the need for a floor.

### Floor Sweep

`720m` floor `2/3/4/5`:

| candidate | eligible | blockers | validation total | min role | min month | validation trades | fixed total | fixed min month |
|---|---|---|---:|---:|---:|---:|---:|---:|
| q99 floor5 | false | `month_pnl_below_floor;month_trades_low` | `+43.0418` | `+2.4158` | `-1.8000` | `19` | `+77.7010` | `-10.3560` |
| q95 floor5 | false | `positive_roles_low;role_total_pnl_below_floor;month_pnl_below_floor` | `+81.7238` | `-1.6986` | `-2.3640` | `40` | `+112.0732` | `-13.6956` |
| q95 floor3 | false | `positive_roles_low;role_total_pnl_below_floor;month_pnl_below_floor` | `+35.7958` | `-13.4946` | `-13.5960` | `66` | `+92.5748` | `-32.4240` |
| q99 floor4 | false | `positive_roles_low;total_pnl_below_floor;role_total_pnl_below_floor;month_pnl_below_floor` | `-27.2162` | `-29.7130` | `-34.1400` | `22` | `+53.7174` | `-10.9920` |
| q99 floor3 | false | `positive_roles_low;total_pnl_below_floor;role_total_pnl_below_floor;month_pnl_below_floor` | `-36.2788` | `-46.0350` | `-45.6790` | `32` | `+32.9784` | `-23.5200` |

There is no stable floor plateau. `floor5` is closest but too sparse; `floor2..4` quickly reintroduce tail losses.

## Decision

Accepted:

- `entry_ev_executable_ev_policy_inputs.py` as infrastructure.
- Prior-only side/context capture factor for prediction-level executable EV columns.
- `pred_executable_calibrated_long_best_adjusted_pnl` / `short` as a diagnostic score family.
- `executable` quantile columns for stateful backtest inputs.
- `720m` remains the main diagnostic cap for q95/q99 entry-EV candidates.

Not accepted:

- Any tested executable-EV stateful policy as standard.
- Floorless executable EV admission.
- Floor `2/3/4/5` tuning as a stable adoption path.
- Using fixed diagnostic positivity to override validation month-floor failure.

Standard policy remains NoTrade.

## Next

1. Do not keep細密floor探索を本流にしない。`q99 floor5` が近いが、月次1 tradeの損失と0-trade月で落ちており、汎化根拠が薄い。
2. Add more chronological validation evidence before promotion. Current cal/fresh/refit roles still leave only a few active q99 trades.
3. Train/use executable EV as a dense target or model feature, not only prior context mean capture. Current factor is coarse and makes early months default to `1.0`.
4. Separate the remaining failures into:
   - sparse q99 support problem,
   - cal2024 `2024-02` one-trade loss,
   - fresh fixed `2024-10` one-trade loss,
   - direction-side inversion vs exit capture.
5. Keep q99 floor5 / 720m as a diagnostic near-miss row, not a candidate for deployment.

## Verification

- `python3 -m unittest tests.test_entry_ev_executable_ev_policy_inputs tests.test_entry_ev_executable_ev_calibration_diagnostics tests.test_entry_ev_scale_quantile_diagnostics tests.test_entry_ev_quantile_policy_backtest tests.test_entry_ev_quantile_policy_selection tests.test_docs_reports`: OK, `26` tests
- `python3 -m py_compile scripts/experiments/entry_ev_executable_ev_policy_inputs.py tests/test_entry_ev_executable_ev_policy_inputs.py`: OK
- executable EV policy input generation: OK
- stateful executable EV backtests (`720m`, `260m`, no-floor, floor sweep): OK
- NoTrade-first selector runs: OK
