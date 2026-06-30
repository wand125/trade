# Entry EV Executable EV Selector Feature

日時: 2026-06-30 18:00 JST
更新日時: 2026-06-30 18:03 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00229の `pred_capture_calibrated_ev` を、単独thresholdではなくNoTrade-first selectorのcandidate-level featureとして評価する `scripts/experiments/entry_ev_executable_ev_selector_diagnostics.py` を追加した。
- selected tradeをrole/month/candidate単位へ再集計し、PnL gate、月次floor、role floor、side concentrationに加えて、`capture_ev_mean`, `capture_ev_low2_share`, `mae_delta_raw_minus_capture` を出す。
- 結論: executable EV featureは候補説明には有用だが、NoTrade-firstの結論は変わらない。validation q95/q99もfresh q95/720も、標準selectorはNoTrade。
- validation q95/q99ではq99候補が `capture_ev_mean > 5` を満たすが、refit role totalと月次floorが負のため採用不可。fresh q95/720は validation total `+76.2204` だが `2024-03` の min month `-9.1718` で落ちる。
- 標準policyはNoTradeのまま。次は executable EV を候補採用条件ではなく、stateful policyの実際のentry ranking / replacement choice に入れる必要がある。

## Artifacts

- Script: `scripts/experiments/entry_ev_executable_ev_selector_diagnostics.py`
- Test: `tests/test_entry_ev_executable_ev_selector_diagnostics.py`
- Validation q95/q99 base selector:
  - `data/reports/backtests/20260630_entry_ev_executable_ev_selector_diagnostics/20260630_085941_entry_ev_executable_ev_selector_validation_q95q99/`
- Validation q95/q99 feature screen:
  - `data/reports/backtests/20260630_entry_ev_executable_ev_selector_diagnostics/20260630_090005_entry_ev_executable_ev_selector_validation_q95q99_feature_screen/`
- Fresh q95_floor5 / 720m base selector:
  - `data/reports/backtests/20260630_entry_ev_executable_ev_selector_diagnostics/20260630_085941_entry_ev_executable_ev_selector_fresh_q95_720/`
- Fresh q95_floor5 / 720m feature screen:
  - `data/reports/backtests/20260630_entry_ev_executable_ev_selector_diagnostics/20260630_090005_entry_ev_executable_ev_selector_fresh_q95_720_feature_screen/`

## Selector Setup

Validation-only gates:

```text
min total PnL       >= 0
min role total PnL  >= 0
min month PnL       >= 0
min role trades     >= 1
min month trades    >= 1
max side share      <= 0.98
```

Feature screen diagnostic:

```text
capture_ev_mean >= 5
capture_ev_low2_share <= 0.10
```

The feature screen is not a standard rule. It only checks whether executable EV ranking is pointing at different candidates.

## Validation q95/q99

Base selector:

| candidate | eligible | blockers | total | min role | min month | trades | capture EV mean | low2 share | MAE improvement |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| q95 floor5 | false | `positive_roles_low;total_pnl_below_floor;role_total_pnl_below_floor;month_pnl_below_floor` | `-5.6974` | `-23.2338` | `-36.8342` | `97` | `4.9314` | `0.1031` | `7.7410` |
| q95 floor10 | false | `positive_roles_low;total_pnl_below_floor;role_total_pnl_below_floor;month_pnl_below_floor` | `-16.2290` | `-23.6438` | `-36.8342` | `96` | `4.9660` | `0.0938` | `7.7423` |
| q99 floor10 | false | `positive_roles_low;role_total_pnl_below_floor;month_pnl_below_floor` | `+16.4832` | `-27.9456` | `-37.7536` | `43` | `5.1315` | `0.0930` | `8.1113` |
| q99 floor5 | false | `positive_roles_low;role_total_pnl_below_floor;month_pnl_below_floor` | `+12.5532` | `-27.9456` | `-37.7536` | `44` | `5.2237` | `0.0909` | `7.9270` |

Feature screen:

- q99 floor5/floor10 pass the executable EV feature screen.
- They still fail `positive_roles_low`, `role_total_pnl_below_floor`, and `month_pnl_below_floor`.
- Therefore executable EV feature cannot promote a candidate under NoTrade-first rules.

## Fresh q95_floor5 / 720m

Base selector:

| candidate | eligible | blockers | total | min role | min month | trades | capture EV mean | low2 share | MAE improvement |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| q95 floor5 / 720m | false | `month_pnl_below_floor` | `+76.2204` | `+76.2204` | `-9.1718` | `36` | `2.7730` | `0.1111` | `6.3270` |

Fixed diagnostic audit:

| candidate | validation total | validation min month | validation capture EV | fixed total | fixed min month | fixed capture EV | fixed MAE improvement |
|---|---:|---:|---:|---:|---:|---:|---:|
| q95 floor5 / 720m | `+76.2204` | `-9.1718` | `2.7730` | `+325.8914` | `+1.3594` | `2.3873` | `6.4166` |

Feature screen:

- q95 floor5 / 720m fails both `capture_ev_mean >= 5` and `capture_ev_low2_share <= 0.10`.
- It already fails `month_pnl_below_floor`, so feature screen does not change the selected policy.

## Decision

Accepted:

- Executable EV selector feature diagnostic script.
- Candidate-level features:
  - `capture_ev_mean`
  - `capture_ev_low2_share`
  - `mae_delta_raw_minus_capture`
  - `capture_factor_mean`
- NoTrade-first selector remains the promotion gate.

Not accepted:

- Promoting q99 just because executable EV features are cleaner.
- Promoting q95/720 based on fixed diagnostic positivity while validation month floor is negative.
- `capture_ev_mean >= 5` or `capture_ev_low2_share <= 0.10` as standard gates.

Standard policy remains NoTrade.

## Next

1. Move from candidate-level post-trade selector diagnostics to executable entry ranking inside the stateful policy.
2. Test whether `pred_capture_calibrated_ev` can replace raw `pred_taken_ev` for entry ordering among competing candidates without adding a hard threshold.
3. Keep monthly NoTrade-first gates, because feature cleanliness does not guarantee month-floor stability.
4. Separate this from direction-side inversion. Executable EV fixes overestimate/capture; it does not by itself solve wrong-side trades.

## Verification

- `python3 -m unittest tests.test_entry_ev_executable_ev_selector_diagnostics tests.test_entry_ev_executable_ev_calibration_diagnostics tests.test_docs_reports`: OK, `9` tests
- `python3 -m py_compile scripts/experiments/entry_ev_executable_ev_selector_diagnostics.py tests/test_entry_ev_executable_ev_selector_diagnostics.py`: OK
- validation q95/q99 base and feature selector runs: OK
- fresh q95_floor5 / 720m base and feature selector runs: OK
- `git diff --check`: OK
