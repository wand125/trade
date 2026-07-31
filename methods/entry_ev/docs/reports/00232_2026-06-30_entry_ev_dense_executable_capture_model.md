# Entry EV Dense Executable Capture Model

日時: 2026-06-30 18:41 JST
更新日時: 2026-06-30 18:41 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00231の次アクションとして、selected tradeだけのprior context平均captureではなく、prediction全行のdense targetからcapture factorを学習する診断を追加した。
- `scripts/experiments/entry_ev_dense_executable_capture_model.py` は各prediction行をlong/short side-rowへ展開し、`side_fixed_720m_adjusted_pnl / side_best_adjusted_pnl` または `side_fixed_240m_adjusted_pnl / side_best_adjusted_pnl` を月順OOFで回帰する。
- 重要: target月と未来月のlabelは使わず、対象月より前のdense row labelだけで学習する。ただし今回の診断runは与えたprediction artifact内の全prior月を使うため、role純度の観点ではpolicy promotion用ではなく、dense calibration feasibility診断として扱う。
- dense capture modelはrow-level EV MAEを大きく改善した。fixed720 targetでは `2025-01` raw MAE `17.0734 -> 10.6154`, `2025-02` `19.9742 -> 13.9449`。fixed240 targetでは `2025-01` `16.0786 -> 6.0691`, `2025-02` `17.4734 -> 8.1887`。
- しかしstateful trade成績には転化しなかった。fixed720 targetのvalidation overallは q95 floor5 total `+16.4192` だが fresh role `-76.2788`、q99 floor5 total `-25.4216`。fixed240 targetも全候補NoTradeで、fresh q95/q99 floor5が `-42.3600` / `-38.9040`。
- 結論: dense executable capture model infrastructureはaccepted。現fixed720/fixed240 capture scoreは標準policyへ採用しない。row-level MAE改善だけでは一玉制約下のadmission品質を保証しない。

## Artifacts

- Script: `scripts/experiments/entry_ev_dense_executable_capture_model.py`
- Test: `tests/test_entry_ev_dense_executable_capture_model.py`
- fixed720 dense input:
  - `data/reports/backtests/20260630_093629_20260630_entry_ev_dense_capture_fixed720_inputs/`
- fixed720 stateful backtest:
  - `data/reports/backtests/20260630_093749_20260630_entry_ev_dense_capture_policy_backtest_720/`
- fixed720 selector:
  - `data/reports/backtests/20260630_093817_20260630_entry_ev_dense_capture_policy_selector_720_relaxed_trades/`
- fixed720 fresh fixed diagnostic:
  - `data/reports/backtests/20260630_093832_20260630_entry_ev_dense_capture_policy_backtest_720_fixed_2024_10_11/`
- fixed240 dense input:
  - `data/reports/backtests/20260630_093859_20260630_entry_ev_dense_capture_fixed240_inputs/`
- fixed240 stateful backtest:
  - `data/reports/backtests/20260630_094008_20260630_entry_ev_dense_capture_fixed240_policy_backtest_720/`
- fixed240 selector:
  - `data/reports/backtests/20260630_094027_20260630_entry_ev_dense_capture_fixed240_policy_selector_720_relaxed_trades/`

## Method

Dense target construction:

```text
for each prediction row and side:
  target_best_ev = side_best_adjusted_pnl
  target_executable_ev =
    fixed720 run: side_fixed_720m_adjusted_pnl
    fixed240 run: side_fixed_240m_adjusted_pnl

  target_capture_factor =
    target_executable_ev / target_best_ev
    only when target_best_ev > 0
    clipped to [0, 1]
```

Chronological model:

```text
target month M:
  train rows = dense side rows with month < M
  features = predicted EV, opposite EV, side gap, ranks,
             predicted holding, predicted fixed horizons,
             side, family, combined_regime, session_regime, decision hour
  model = HistGradientBoostingRegressor
  output = pred_dense_executable_long/short_best_adjusted_pnl
         = pred_calibrated_long/short_best_adjusted_pnl
           * predicted dense capture factor
```

Backtest:

```text
policy = timed_ev
score_kind = dense_executable
max_predicted_hold_minutes = 720
profit_multiplier = 1.00
loss_multiplier = 1.20
candidates = q95/q99, sg95, rank90, floor5/floor10,
             side_regime_session_month
selector = NoTrade-first, validation roles only
```

## Dense Calibration Results

### fixed720 target

| target month | target capture mean | pred capture mean | raw EV MAE | dense EV MAE | raw bias | dense bias |
|---|---:|---:|---:|---:|---:|---:|
| `2024-02` | `0.2447` | `0.2076` | `11.1010` | `6.6945` | `9.7845` | `2.3335` |
| `2024-03` | `0.2529` | `0.2237` | `14.9027` | `11.8779` | `10.5295` | `2.8788` |
| `2024-04` | `0.2363` | `0.2676` | `18.1099` | `15.3636` | `11.5652` | `3.6835` |
| `2025-01` | `0.2414` | `0.2185` | `17.0734` | `10.6154` | `16.2570` | `3.9863` |
| `2025-02` | `0.2191` | `0.2349` | `19.9742` | `13.9449` | `17.1835` | `4.8698` |

Prediction effect:

| family/month | base long share | dense long share | side switch | base q95 | dense q95 | long factor | short factor |
|---|---:|---:|---:|---:|---:|---:|---:|
| cal2024 `2024-02` | `0.4063` | `0.6477` | `0.4779` | `11.1627` | `4.3564` | `0.2376` | `0.1777` |
| fresh2024 `2024-03` | `0.2907` | `0.4786` | `0.4445` | `12.0795` | `4.3571` | `0.2195` | `0.2278` |
| fresh2024 `2024-04` | `0.1458` | `0.6417` | `0.5102` | `15.6104` | `4.7899` | `0.3127` | `0.2224` |
| refit2025 `2025-01` | `0.9170` | `0.9453` | `0.0929` | `23.5228` | `4.9781` | `0.2347` | `0.2022` |
| refit2025 `2025-02` | `0.9150` | `0.8970` | `0.0506` | `23.7344` | `9.3278` | `0.3054` | `0.1644` |

Stateful result:

| candidate | validation total | min role | min month | trades | selector |
|---|---:|---:|---:|---:|---|
| q95 floor5 | `+16.4192` | `-76.2788` | `-44.0268` | `59` | NoTrade |
| q99 floor5 | `-25.4216` | `-36.5510` | `-33.4920` | `30` | NoTrade |
| q95 floor10 | `+19.3836` | `-11.2600` | `-9.4600` | `24` | NoTrade |
| q99 floor10 | `+5.0020` | `-3.5664` | `-3.5664` | `11` | NoTrade |

Fresh fixed `2024-10..11` diagnostic:

| candidate | fixed total | min month | trades |
|---|---:|---:|---:|
| q99 floor5 | `+27.3080` | `0.0000` | `2` |
| q95 floor5 | `-8.2074` | `-8.2074` | `3` |
| q95/q99 floor10 | `0.0000` | `0.0000` | `0` |

The fixed diagnostic positivity is too sparse and cannot override validation failure.

### fixed240 target

| target month | target capture mean | pred capture mean | raw EV MAE | dense EV MAE | raw bias | dense bias |
|---|---:|---:|---:|---:|---:|---:|
| `2024-02` | `0.1787` | `0.1862` | `10.0487` | `4.1689` | `9.5723` | `1.9365` |
| `2024-03` | `0.1752` | `0.1760` | `11.2742` | `5.9041` | `10.1145` | `2.0114` |
| `2024-04` | `0.1717` | `0.1792` | `13.1475` | `8.8152` | `11.1139` | `2.3397` |
| `2025-01` | `0.1728` | `0.1764` | `16.0786` | `6.0691` | `15.9077` | `2.9508` |
| `2025-02` | `0.1695` | `0.1681` | `17.4734` | `8.1887` | `16.7858` | `3.1290` |

Stateful result:

| candidate | validation total | min role | min month | trades | selector |
|---|---:|---:|---:|---:|---|
| q99 floor10 | `+8.5684` | `0.0000` | `-1.8000` | `9` | NoTrade |
| q95 floor10 | `-11.2600` | `-11.2600` | `-9.4600` | `21` | NoTrade |
| q99 floor5 | `-41.3412` | `-38.9040` | `-38.9040` | `17` | NoTrade |
| q95 floor5 | `-55.8390` | `-42.3600` | `-42.3600` | `31` | NoTrade |

fixed240 is more conservative in score scale, but it does not improve stateful admission.

## Decision

Accepted:

- Dense side-row capture target construction.
- Chronological dense capture model infrastructure.
- `pred_dense_executable_long_best_adjusted_pnl` / `short` output columns.
- `dense_executable` quantile columns for existing stateful backtest.
- fixed720/fixed240 target comparison as a diagnostic.

Not accepted:

- Promoting fixed720 dense capture policy.
- Promoting fixed240 dense capture policy.
- Treating row-level MAE improvement as sufficient evidence for trade policy improvement.
- Using sparse fixed diagnostic positivity to override validation role failure.

Standard policy remains NoTrade.

## Interpretation

Dense capture learning solves a real problem: raw EV scale is too large. But the learned factor is still not aligned with the actual one-position trading decision. In fixed720, refit2025 remains long-heavy (`2025-01` dense long share `0.9453`; `2025-02` `0.8970`). In fixed240, scores shrink further but admission becomes too sparse or still selects fresh2024 tail losses.

This suggests the next target should not only predict generic fixed-horizon capture. It should include one of:

- selected-side ranking quality under the stateful policy path,
- downside/capture asymmetry by side,
- direct executable EV quantile calibration with side-balance constraints,
- target focused on losing admitted rows, not all dense rows equally.

## Next

1. Keep the dense capture model as infrastructure and diagnostic feature, but do not use it as the standard score.
2. Add side-balance / side-drift penalty to dense capture score before admission, especially for refit2025 long-heavy folds.
3. Use dense target as a secondary feature in selector/ranking, not a direct replacement score.
4. Train a downside-weighted target: high raw EV + low realized fixed/exit EV, focused on admitted quantile candidates.
5. Continue NoTrade-first selection; do not promote fixed-positive sparse rows.

## Verification

- `python3 -m py_compile scripts/experiments/entry_ev_dense_executable_capture_model.py tests/test_entry_ev_dense_executable_capture_model.py`: OK
- `python3 -m unittest tests.test_entry_ev_dense_executable_capture_model`: OK
- fixed720 dense input generation: OK
- fixed720 stateful backtest and selector: OK, selected NoTrade
- fixed720 fresh fixed diagnostic: OK
- fixed240 dense input generation: OK
- fixed240 stateful backtest and selector: OK, selected NoTrade
