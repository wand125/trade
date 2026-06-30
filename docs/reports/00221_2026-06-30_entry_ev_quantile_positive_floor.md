# Entry EV Quantile Positive Floor

日時: 2026-06-30 15:57 JST
更新日時: 2026-06-30 15:57 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00220の次アクションとして、quantile admissionに小さな絶対EV floorを事前登録候補として追加した。
- `entry_ev_quantile_policy_backtest.py` のcandidate parserを拡張し、`q95_sg95_rank90_floor10_side_regime_session_month` のような名前で `entry_threshold=10` を指定できるようにした。
- 候補は `score q90/q95/q99`, `side_gap q90/q95`, `rank q90`, floor `5/10` の8本。
- 結果: strict3もclean2もNoTrade。全候補が `positive_roles_low`, `role_total_pnl_below_floor`, `month_pnl_below_floor` で落ちた。
- floor10は一部のfresh2024 validationを改善したが、refit2025 validationの負けを解けない。
- q90系は候補数を増やすが、fresh2024 validationで大きく壊れる。
- 判断: positive EV floor候補は実装としてaccepted。ただし現candidate familyは標準採用しない。

## Artifacts

- Script updated: `scripts/experiments/entry_ev_quantile_policy_backtest.py`
- Tests updated: `tests/test_entry_ev_quantile_policy_backtest.py`
- Floor policy backtest:
  - `data/reports/backtests/20260630_entry_ev_quantile_floor_policy_backtest/20260630_065523_entry_ev_quantile_floor_policy_backtest/`
- strict3 selection:
  - `data/reports/backtests/20260630_entry_ev_quantile_floor_policy_selection/20260630_065645_entry_ev_quantile_floor_policy_selection_strict3/`
- clean2 selection:
  - `data/reports/backtests/20260630_entry_ev_quantile_floor_policy_selection/20260630_065645_entry_ev_quantile_floor_policy_selection_clean2/`

## Candidate Syntax

Candidate name:

```text
q{score}_sg{side_gap}_rank{rank}_floor{ev_floor}_{scope}
```

Examples:

```text
q95_sg95_rank90_floor5_side_regime_session_month
q95_sg95_rank90_floor10_side_regime_session_month
q95_sg95_rank90_floor2p5_side_regime_session_month
```

`floor2p5` means `entry_threshold=2.5`. The floor is applied to selected calibrated EV after quantile gates.

## Results

Selected role rows:

| role | candidate | total pnl | worst month | trades | max DD | side share |
|---|---|---:|---:|---:|---:|---:|
| `cal2024_calibration_validation` | `q95_sg95_rank90_floor5_side_regime_session_month` | `+15.5444` | `+0.2074` | `30` | `27.1290` | `0.5667` |
| `fresh2024_validation` | `q95_sg95_rank90_floor5_side_regime_session_month` | `+1.9920` | `-3.6326` | `38` | `44.4834` | `0.6053` |
| `refit2025_validation` | `q95_sg95_rank90_floor5_side_regime_session_month` | `-23.2338` | `-36.8342` | `29` | `54.4442` | `0.5862` |
| `cal2024_calibration_validation` | `q95_sg95_rank90_floor10_side_regime_session_month` | `+3.4364` | `-11.3846` | `30` | `37.6670` | `0.5667` |
| `fresh2024_validation` | `q95_sg95_rank90_floor10_side_regime_session_month` | `+3.9784` | `-1.6462` | `38` | `44.4834` | `0.6053` |
| `refit2025_validation` | `q95_sg95_rank90_floor10_side_regime_session_month` | `-23.6438` | `-36.8342` | `28` | `54.4442` | `0.6071` |
| `cal2024_calibration_validation` | `q99_sg95_rank90_floor10_side_regime_session_month` | `+10.1348` | `+1.8830` | `13` | `7.1012` | `0.6923` |
| `fresh2024_validation` | `q99_sg95_rank90_floor10_side_regime_session_month` | `+34.2940` | `-12.4240` | `12` | `17.9640` | `0.6667` |
| `refit2025_validation` | `q99_sg95_rank90_floor10_side_regime_session_month` | `-27.9456` | `-37.7536` | `18` | `51.3246` | `0.5556` |
| `cal2024_calibration_validation` | `q90_sg90_rank90_floor5_side_regime_session_month` | `+16.5308` | `+3.0456` | `49` | `29.3286` | `0.5714` |
| `fresh2024_validation` | `q90_sg90_rank90_floor5_side_regime_session_month` | `-50.8200` | `-37.3312` | `58` | `107.8732` | `0.5690` |
| `refit2025_validation` | `q90_sg90_rank90_floor5_side_regime_session_month` | `+9.3596` | `-7.1966` | `37` | `30.4000` | `0.6757` |

Selector result:

| selector | selected | dominant blockers |
|---|---|---|
| strict3 | NoTrade | `positive_roles_low`, `role_total_pnl_below_floor`, `month_pnl_below_floor` all `8/8` |
| clean2 | NoTrade | `positive_roles_low`, `role_total_pnl_below_floor`, `month_pnl_below_floor` all `8/8` |

## Interpretation

- `floor10` can remove a few bad entries in fresh2024 validation, but it also worsens cal2024 and does not fix refit2025.
- `q90` score quantile lowers the score gate too much. It increases trades and makes fresh2024 validation tail risk worse.
- `q99 floor10` is almost identical to `q99 floor5` in clean validation because q99 selected EV already exceeds the floor; it cannot solve refit2025.
- The failure is not simply "EV must be positive." The problem is still role/regime instability.

## Decision

Accepted:

- Dynamic candidate parser for positive EV floors.
- Floor candidate syntax and tests.
- Floor family as a future pre-registered diagnostic axis.

Not accepted:

- Any floor candidate from this run.
- q90 score quantile as a standard relaxation.
- floor10 as a rescue for q95, because it trades one validation role improvement for another role loss.

Current standard remains NoTrade.

## Next

1. Add more chronological validation roles; do not tune more floor values on the same roles.
2. If floor candidates are revisited, use a coarse pre-registered set such as `0/5/10`, not a post-hoc fine search.
3. Investigate why refit2025 rejects rank90 quantile gates while cal/fresh sometimes accept them. The next diagnostic should compare selected trade context and EV calibration by role.

## Verification

- `python3 -m unittest tests.test_entry_ev_quantile_policy_backtest`: OK, `8` tests
- `python3 -m py_compile scripts/experiments/entry_ev_quantile_policy_backtest.py tests/test_entry_ev_quantile_policy_backtest.py`: OK
- floor policy backtest run: OK
- floor strict3 selector run: OK, selected NoTrade
- floor clean2 selector run: OK, selected NoTrade
