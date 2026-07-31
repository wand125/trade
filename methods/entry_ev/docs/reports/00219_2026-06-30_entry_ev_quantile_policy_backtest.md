# Entry EV Quantile Policy Backtest

日時: 2026-06-30 15:36 JST
更新日時: 2026-06-30 15:36 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00218のstateless quantile admissionを、実際の `timed_ev` backtestへ接続した。
- `ModelPolicyConfig` / `model-policy` に `min_entry_score_quantile`, `min_side_gap_quantile`, `min_entry_rank_quantile` と対応列名を追加した。
- `entry_ev_scale_quantile_diagnostics.py --write-enriched-predictions` でquantile列付きprediction parquetを出せるようにした。
- `entry_ev_quantile_policy_backtest.py` を追加し、family/month/role別にquantile policyを同条件で再実行できるようにした。
- 評価条件は profit multiplier `1.0`, loss multiplier `1.20`, MLP exit holding, `min_valid_hold=30`, `max_predicted_hold=260`。
- `side_regime_session_month` quantile gateはcal2024のno-entry問題を解消した。`q99/side_gap_q95/rank_q90` は cal2024で `+6.2048`, worst `+1.8830`, `14` trades。
- ただしstateful PnLではまだ安定しない。同じ `q99/side_gap_q95/rank_q90` は fresh2024 validation total `+34.2940` だが worst `-12.4240`、refit2025 validation total `-27.9456`, worst `-37.7536`。
- `q95/side_gap_q95/rank_q90` はfresh fixed diagnosticでは強いが、refit2025 validationで `-23.2338`。
- `rank_q0` はrefit2025では `+86.4510` だが、cal2024 `-23.3044`、fresh2024 validation `-70.7894` と壊れる。rank quantileは外せない。
- 絶対閾値baseline `entry10/short9/side5/rank0` は集計上positiveだが、cal2024は0 trades、refit2025はlong share `0.9763`。scale driftを解いた証拠ではなく、標準採用しない。
- 判断: quantile admissionはaccepted infrastructure。ただし標準policyは引き続きNoTrade。

## Artifacts

- Backtest hook: `src/trade_data/backtest.py`
- Enriched prediction writer: `scripts/experiments/entry_ev_scale_quantile_diagnostics.py`
- Quantile policy backtest: `scripts/experiments/entry_ev_quantile_policy_backtest.py`
- Tests:
  - `tests/test_backtest.py`
  - `tests/test_entry_ev_scale_quantile_diagnostics.py`
  - `tests/test_entry_ev_quantile_policy_backtest.py`
- Quantile input run:
  - `data/reports/backtests/20260630_entry_ev_quantile_policy_inputs/20260630_062437_entry_ev_quantile_policy_inputs/`
- Policy backtest run:
  - `data/reports/backtests/20260630_entry_ev_quantile_policy_backtest/20260630_063440_entry_ev_quantile_policy_backtest/`
- Main outputs:
  - `monthly_policy_metrics.csv`
  - `family_policy_summary.csv`
  - `role_policy_summary.csv`
  - `overall_policy_summary.csv`
  - `policy_candidates.csv`
  - `config.json`

## Method

Input families:

| family | role | months |
|---|---|---|
| `cal2024` | calibration-validation | `2024-01..02` |
| `fresh2024` | validation | `2024-03..04` |
| `fresh2024` | fixed diagnostic | `2024-05..12` |
| `refit2025` | validation | `2025-01..02` |

Policy candidates:

| candidate | admission rule |
|---|---|
| `abs_entry10_short9_side5_rank0` | calibrated EV absolute threshold baseline |
| `q99_sg95_rank90_side_regime_session_month` | selected score q99, side gap q95, selected rank q90 |
| `q95_sg95_rank90_side_regime_session_month` | selected score q95, side gap q95, selected rank q90 |
| `q99_sg90_rank90_side_regime_session_month` | selected score q99, side gap q90, selected rank q90 |
| `q99_sg95_rank0_side_regime_session_month` | selected score q99, side gap q95, rank gate off |
| `q99_sg95_rank90_side_month` | side-month local q99/q95/q90 |
| `q99_sg95_rank90_month` | month local q99/q95/q90 |

This is still a diagnostic comparison, not a selector. `fresh2024_fixed_diagnostic` is shown only to inspect extrapolation after validation; it is not used to choose thresholds.

## Role Results

Selected rows from `role_policy_summary.csv`:

| role | candidate | total pnl | worst month | trades | max DD | max side share |
|---|---|---:|---:|---:|---:|---:|
| `cal2024_calibration_validation` | `q99_sg95_rank90_side_regime_session_month` | `+6.2048` | `+1.8830` | `14` | `13.9412` | `0.6429` |
| `fresh2024_validation` | `q99_sg95_rank90_side_regime_session_month` | `+34.2940` | `-12.4240` | `12` | `17.9640` | `0.6667` |
| `refit2025_validation` | `q99_sg95_rank90_side_regime_session_month` | `-27.9456` | `-37.7536` | `18` | `51.3246` | `0.5556` |
| `cal2024_calibration_validation` | `q95_sg95_rank90_side_regime_session_month` | `+15.5444` | `+0.2074` | `30` | `27.1290` | `0.5667` |
| `fresh2024_validation` | `q95_sg95_rank90_side_regime_session_month` | `+1.9920` | `-3.6326` | `38` | `44.4834` | `0.6053` |
| `refit2025_validation` | `q95_sg95_rank90_side_regime_session_month` | `-23.2338` | `-36.8342` | `29` | `54.4442` | `0.5862` |
| `cal2024_calibration_validation` | `q99_sg95_rank0_side_regime_session_month` | `+5.5412` | `-23.3044` | `53` | `51.0978` | `0.6415` |
| `fresh2024_validation` | `q99_sg95_rank0_side_regime_session_month` | `-70.7894` | `-72.0966` | `60` | `76.7116` | `0.5333` |
| `refit2025_validation` | `q99_sg95_rank0_side_regime_session_month` | `+86.4510` | `+32.1566` | `50` | `46.7314` | `0.6400` |
| `cal2024_calibration_validation` | `abs_entry10_short9_side5_rank0` | `0.0000` | `0.0000` | `0` | `0.0000` | `0.0000` |
| `fresh2024_validation` | `abs_entry10_short9_side5_rank0` | `+16.1220` | `+1.0490` | `4` | `0.0000` | `0.7500` |
| `refit2025_validation` | `abs_entry10_short9_side5_rank0` | `+238.5846` | `+72.9576` | `169` | `77.9136` | `0.9763` |

Interpretation:

- `side_regime_session_month` quantile is the best local scale so far because it restores cal2024 entries while keeping side share around `0.56..0.67`.
- That does not yet imply edge. refit2025 validation rejects the rank90 quantile candidates.
- Turning off rank quantile increases trades but creates large fresh2024 validation loss.
- Absolute baseline looks strong only because refit2025 is dominated by long entries. It still has zero cal2024 trades and known fixed-test fragility from 00212/00213.

## Decision

Accepted:

- Quantile columns as model-policy gate inputs.
- Enriched prediction output for repeated backtests.
- Role-aware quantile policy backtest script.
- `side_regime_session_month` as the primary diagnostic scope for the next admission experiments.

Not accepted as standard policy:

- Any quantile gate tested here.
- Dropping rank quantile.
- Re-promoting absolute EV threshold baseline because it is positive on the current role summary.
- Using `fresh2024_fixed_diagnostic` to select thresholds.

Current standard remains NoTrade.

## Next

1. Add more chronological validation windows before selecting a quantile threshold. Two-month windows are still too regime-dependent.
2. Use a selector gate that requires role-level worst month `>= 0`, active trades in every validation role, side share below a pre-registered cap, and fixed diagnostic only after selection.
3. Compare quantile admission under cost stress after a validation-positive candidate exists.
4. Try hybrid admission only after pre-registering it: local quantile gate plus a small absolute positive EV floor, not a high fixed EV threshold.

## Verification

- `python3 -m unittest tests.test_backtest tests.test_entry_ev_scale_quantile_diagnostics tests.test_entry_ev_quantile_policy_backtest`: OK, `111` tests
- `python3 -m unittest tests.test_entry_ev_quantile_policy_backtest`: OK, `6` tests
- `python3 -m py_compile src/trade_data/backtest.py scripts/experiments/entry_ev_scale_quantile_diagnostics.py scripts/experiments/entry_ev_quantile_policy_backtest.py tests/test_backtest.py tests/test_entry_ev_scale_quantile_diagnostics.py tests/test_entry_ev_quantile_policy_backtest.py`: OK
- Quantile input run with `--write-enriched-predictions`: OK
- Quantile policy backtest run: OK, output in `data/reports/backtests/20260630_entry_ev_quantile_policy_backtest/20260630_063440_entry_ev_quantile_policy_backtest/`
