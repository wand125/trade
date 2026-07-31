# Entry EV Quantile Trade Context Diagnostics

日時: 2026-06-30 16:12 JST
更新日時: 2026-06-30 16:12 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00221の次アクションとして、positive EV floor候補の実tradeを保存し、role/candidate/context別に prediction / oracle label / realized PnL を再結合した。
- `scripts/experiments/entry_ev_quantile_trade_diagnostics.py` を追加した。`monthly_policy_metrics.csv`、保存済みtrade CSV、family prediction parquetを読み、`role_candidate_trade_summary.csv`, `role_context_trade_summary.csv`, `candidate_role_spread.csv` を出力する。
- validation roleだけを見ると、q95/q99系は `refit2025_validation` が主な負けrole、q90系は `fresh2024_validation` が主な負けrole。
- q95/q99系のrefit負けは、no-edge率は低いがdirection errorとexit regretが大きい。単純なpositive EV floorでは解けない。
- fresh q95は平均ではoracle EVを過大評価していないが、realized PnLとの差が大きい。entry候補には利益余地があるが、決済・方向文脈・一玉制約で取り逃している。
- q90 relaxationはfreshで悪いshort contextを増やすため標準採用しない。
- 判断: quantile/floor候補は標準採用しない。次はentry admissionの閾値探索ではなく、role/context別のside inversionとexit captureを分けて診断する。

## Artifacts

- Script: `scripts/experiments/entry_ev_quantile_trade_diagnostics.py`
- Tests: `tests/test_entry_ev_quantile_trade_diagnostics.py`
- Trade-writing floor backtest:
  - `data/reports/backtests/20260630_entry_ev_quantile_floor_policy_backtest_with_trades/20260630_070948_entry_ev_quantile_floor_policy_backtest_with_trades/`
- Trade context diagnostics:
  - `data/reports/backtests/20260630_entry_ev_quantile_trade_diagnostics/20260630_071126_entry_ev_quantile_trade_diagnostics/`

## Role Candidate Result

Validation roles only:

| candidate | positive roles | worst role | total pnl sum | worst role pnl | worst role trades | worst role no-edge | worst role EV over oracle |
|---|---:|---|---:|---:|---:|---:|---:|
| `q95_sg95_rank90_floor5_side_regime_session_month` | `2/3` | `refit2025_validation` | `-5.6974` | `-23.2338` | `29` | `0.0345` | `+1.1387` |
| `q95_sg95_rank90_floor10_side_regime_session_month` | `2/3` | `refit2025_validation` | `-16.2290` | `-23.6438` | `28` | `0.0357` | `+0.9054` |
| `q99_sg95_rank90_floor10_side_regime_session_month` | `2/3` | `refit2025_validation` | `+16.4832` | `-27.9456` | `18` | `0.0556` | `+0.4200` |
| `q90_sg95_rank90_floor10_side_regime_session_month` | `1/3` | `fresh2024_validation` | `-51.7738` | `-40.4968` | `45` | `0.0000` | `-8.7088` |
| `q90_sg90_rank90_floor5_side_regime_session_month` | `2/3` | `fresh2024_validation` | `-24.9296` | `-50.8200` | `58` | `0.0000` | `-9.1311` |

Selected detail:

| role | candidate | trades | total pnl | loss pnl | direction error | actual hit | pred EV | actual best | EV over oracle | EV over realized | exit regret |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `fresh2024_validation` | `q95_sg95_rank90_floor10` | `38` | `+3.9784` | `-109.9176` | `0.4474` | `0.5789` | `13.3499` | `21.9423` | `-8.5923` | `+13.2452` | `829.8276` |
| `refit2025_validation` | `q95_sg95_rank90_floor10` | `28` | `-23.6438` | `-107.4828` | `0.4643` | `0.4643` | `20.5037` | `19.5983` | `+0.9054` | `+21.3481` | `572.3960` |
| `fresh2024_validation` | `q90_sg90_rank90_floor5` | `58` | `-50.8200` | `-189.6420` | `0.3966` | `0.5517` | `12.7813` | `21.9124` | `-9.1311` | `+13.6576` | `1321.7410` |
| `refit2025_validation` | `q99_sg95_rank90_floor10` | `18` | `-27.9456` | `-78.0636` | `0.5000` | `0.5000` | `20.4683` | `20.0482` | `+0.4200` | `+22.0208` | `388.8138` |

## Worst Contexts

Aggregated across candidates:

| role | direction | context | trades | total pnl | direction error | EV over oracle |
|---|---|---|---:|---:|---:|---:|
| `refit2025_validation` | short | `range_normal_vol / ny_overlap` | `16` | `-256.8672` | `1.0000` | `+12.1158` |
| `fresh2024_validation` | short | `up_normal_vol / ny_late` | `6` | `-214.2720` | `1.0000` | `+11.7611` |
| `fresh2024_validation` | short | `down_high_vol / rollover` | `4` | `-171.6144` | `1.0000` | `+5.4167` |
| `refit2025_validation` | long | `up_low_vol / ny_overlap` | `8` | `-131.6160` | `1.0000` | `+17.9684` |
| `fresh2024_validation` | short | `up_normal_vol / london` | `14` | `-118.5248` | `0.6250` | `-13.5105` |
| `cal2024_calibration_validation` | short | `down_low_vol / london` | `10` | `-113.2320` | `1.0000` | `-1.1141` |

Interpretation:

- Worst contexts are mostly direction-error contexts, not no-edge contexts.
- `refit2025 short / range_normal_vol / ny_overlap` is particularly bad: direction error `1.0` and EV over oracle `+12.1158`.
- `fresh2024 short / up_normal_vol / ny_late` and `down_high_vol / rollover` are also direction-error contexts.
- Some losing contexts have negative EV-over-oracle mean, meaning entry oracle potential existed but realized exit failed to capture it. Therefore an entry floor alone is not the right control.

## Decision

Accepted:

- `entry_ev_quantile_trade_diagnostics.py` as accepted diagnostic infrastructure.
- Trade-writing quantile/floor backtest artifact for future selected-trade audits.
- Role/context decomposition before adding more floor values.

Not accepted:

- More fine-grained floor tuning on the same three validation roles.
- q90 relaxation as a rescue.
- A new standard policy from q95/q99 floor candidates.

Current standard remains NoTrade.

## Next

1. Add a context-side inversion preflight: for each candidate, reject role contexts where prior/validation direction error is concentrated, instead of applying a global score floor.
2. Separate `entry has oracle potential` from `exit captures PnL`: diagnose MLP exit timing for q95/q99 selected trades by role/context.
3. Do not promote any context gate until it is selected by validation roles only and checked on a reserved fixed diagnostic window.

## Verification

- `python3 -m unittest tests.test_entry_ev_quantile_trade_diagnostics`: OK, `2` tests
- `python3 -m py_compile scripts/experiments/entry_ev_quantile_trade_diagnostics.py tests/test_entry_ev_quantile_trade_diagnostics.py`: OK
- trade-writing floor backtest run: OK
- trade context diagnostics run: OK
