# Entry EV Side Prior Pressure Policy Inputs

日時: 2026-07-01 08:31 JST
更新日時: 2026-07-01 08:31 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00243で有望だった `side_prior_pressure` EV-overestimate riskをprediction rowへ接続する `scripts/experiments/entry_ev_side_prior_pressure_policy_inputs.py` を追加した。
- predictionをlong/short side rowへ展開し、prior selected tradesから `support_bucket`, `pressure_bucket`, `prior_support_bucket`, `feature_pressure_bucket` を推定し、EV-overestimate riskでscoreを割り引いた。
- penalty strength `0.5` はvalidationを大きく改善した。q95/floor5 は total `+68.0000`、q99/floor5 は total `+35.0014`。
- しかし標準selectorはNoTrade。q99/floor5は緩和selectorなら残るが、fixed 2025-03..12で `-177.3790` と崩れた。
- 判断: stateful接続インフラはaccepted。`side_prior_pressure_s0p5` は診断near-missだが標準policyにはしない。

## Artifacts

- Script: `scripts/experiments/entry_ev_side_prior_pressure_policy_inputs.py`
- Test: `tests/test_entry_ev_side_prior_pressure_policy_inputs.py`
- Input generation:
  - `data/reports/backtests/20260630_232706_20260701_entry_ev_side_prior_pressure_policy_inputs_s1/`
- Validation backtest:
  - `data/reports/backtests/20260630_232909_20260701_entry_ev_side_prior_pressure_s0p5_validation_backtest_s1/`
  - `data/reports/backtests/20260630_232940_20260701_entry_ev_side_prior_pressure_s1_validation_backtest_s1/`
- Selector:
  - `data/reports/backtests/20260630_233018_20260701_entry_ev_side_prior_pressure_s0p5_selector_strict_s1/`
  - `data/reports/backtests/20260630_233031_20260701_entry_ev_side_prior_pressure_s0p5_selector_relaxed_s1/`
- Fixed diagnostics:
  - `data/reports/backtests/20260630_233054_20260701_entry_ev_side_prior_pressure_s0p5_fixed2024_05_12_s1/`
  - `data/reports/backtests/20260630_233115_20260701_entry_ev_side_prior_pressure_s0p5_fixed2025_03_12_s1/`

Note: an earlier mixed-month run without `--months` was superseded and is not used for the decision.

## Method

Base prediction file:

```text
data/reports/backtests/20260630_095101_20260630_entry_ev_side_balance_dense720_inputs_s1/
```

Risk model:

```text
target = executable_ev_overestimate_target
group = direction + support_bucket + pressure_bucket + prior_support_bucket + feature_pressure_bucket
prior_strength = 5
min_group_support = 3
```

Score adjustment:

```text
score_scale = clip(1 - penalty_strength * predicted_ev_overestimate_risk, min_score_scale, 1)
adjusted_score = side_balanced_dense_executable_score * score_scale
```

Tested strengths:

```text
side_prior_pressure_s0p5
side_prior_pressure_s1
```

Backtest uses validation roles only for selector:

```text
cal2024: 2024-01..02
fresh2024: 2024-03..04
refit2025: 2025-01..02
max_predicted_hold_minutes = 720
profit_multiplier = 1.0
loss_multiplier = 1.2
```

## Input Risk Distribution

| family | side | rows | risk mean | p90 | bucket share | global share | no-prior share |
|---|---|---:|---:|---:|---:|---:|---:|
| cal2024 | long | `56,077` | `0.7037` | `0.7307` | `0.1945` | `0.2701` | `0.5355` |
| cal2024 | short | `56,077` | `0.6303` | `0.6842` | `0.3007` | `0.1638` | `0.5355` |
| fresh2024 | long | `296,756` | `0.5380` | `0.7084` | `0.4702` | `0.5298` | `0.0000` |
| fresh2024 | short | `296,756` | `0.5107` | `0.5422` | `0.5158` | `0.4842` | `0.0000` |
| refit2025 | long | `351,190` | `0.4498` | `0.6506` | `0.5202` | `0.4798` | `0.0000` |
| refit2025 | short | `351,190` | `0.4693` | `0.4870` | `0.5279` | `0.4721` | `0.0000` |

cal2024 has high no-prior share, so early calibration months remain fragile.

## Validation Results

Penalty `0.5`:

| candidate | total | min role | min month | trades | max DD | max side share |
|---|---:|---:|---:|---:|---:|---:|
| q95/floor5 | `+68.0000` | `-1.6986` | `-1.8000` | `30` | `26.9590` | `0.6667` |
| q99/floor5 | `+35.0014` | `+2.4158` | `-1.8000` | `17` | `14.0472` | `0.6471` |
| q99/floor10 | `+8.5684` | `0.0000` | `-1.8000` | `9` | `4.9846` | `0.6667` |
| q95/floor10 | `-11.2600` | `-11.2600` | `-9.4600` | `21` | `37.6890` | `0.6190` |

Penalty `1.0`:

| candidate | total | min role | min month | trades | note |
|---|---:|---:|---:|---:|---|
| q95/floor5 | `+27.1774` | `-1.6986` | `-1.8000` | `24` | weaker than s0.5 |
| q99/floor5 | `-1.1506` | `-3.5664` | `-3.5664` | `12` | over-penalized |
| q99/floor10 | `+8.5684` | `0.0000` | `-1.8000` | `9` | sparse |

Reading:

- s0.5 improves validation substantially versus prior side-balance direct score.
- s1.0 suppresses too much and loses support.
- The remaining `-1.8000` month is enough to keep NoTrade-first standard selector from adopting.

## Selector

Strict selector:

| candidate | selected | main blockers |
|---|---|---|
| q99/floor5 | no | `month_pnl_below_floor; role_trades_low; month_trades_low` |
| q95/floor5 | no | `positive_roles_low; role_total_pnl_below_floor; month_pnl_below_floor; role_trades_low; month_trades_low` |

Relaxed selector with `min_month_pnl=-2`, `min_role_trades=1`, `min_month_trades=0`, `max_side_share=1.0`:

```text
selected = q99_sg95_rank90_floor5_side_regime_session_month
validation total = +35.0014
validation min role = +2.4158
validation min month = -1.8000
trades = 17
```

This is a diagnostic near-miss, not a standard policy.

## Fixed Diagnostics

Fresh 2024-05..12:

| candidate | total | min month | trades |
|---|---:|---:|---:|
| q99/floor5 | `0.0000` | `0.0000` | `0` |
| q95/floor5 | `+8.6980` | `-0.6120` | `2` |

Refit 2025-03..12:

| candidate | total | min month | trades | max DD |
|---|---:|---:|---:|---:|
| q99/floor5 | `-177.3790` | `-162.1992` | `53` | `162.1992` |
| q95/floor5 | `-160.8606` | `-233.2854` | `80` | `233.2854` |

The relaxed q99/floor5 near-miss does not generalize to the refit fixed period.

## Decision

Accepted:

- Prediction-row `side_prior_pressure` risk generation.
- Risk-adjusted score columns and quantile columns.
- Stateful replay for `side_prior_pressure_s0p5` and `side_prior_pressure_s1`.

Not accepted:

- `side_prior_pressure_s0p5` as standard policy.
- Relaxing month floor just to adopt q99/floor5.
- Strength tuning around `0.5` until more chronological evidence is added.

Standard policy remains NoTrade.

## Next

1. Treat s0.5 as a diagnostic baseline, not a policy.
2. Inspect fixed 2025-03..12 losses to see whether the collapse is side-specific, context-specific, or replacement-path specific.
3. Add more chronological component-target windows before further tuning this penalty.
4. Keep q99/floor5 near-miss in the report map, but do not use it for standard selection.

## Verification

- `python3 -m py_compile scripts/experiments/entry_ev_side_prior_pressure_policy_inputs.py tests/test_entry_ev_side_prior_pressure_policy_inputs.py`: OK
- `python3 -m unittest tests.test_entry_ev_side_prior_pressure_policy_inputs`: OK
- Input generation: OK
- Validation backtests: OK
- Strict/relaxed selectors: OK
- Fixed diagnostics: OK
