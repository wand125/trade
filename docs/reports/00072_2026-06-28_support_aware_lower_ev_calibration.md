# Support-Aware Lower EV Calibration

日時: 2026-06-28 22:47 JST
更新日時: 2026-06-28 22:47 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻や `更新日時` ではなく、本文内の作成時刻である `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

前回のmulti-holdout auditで、手作業のside EV penalty候補は固定holdout同時監査を通らなかった。次の本流として、entry/side EV calibrationそのものをsupport-awareに保守化する実験を行った。

`trade_data.meta_model` のgroup calibrationに lower EV列を追加した。単純な平均標準誤差だけではmarginが小さすぎたため、`prior_strength > 0` の場合は以下のsupport-aware std marginを使う。

```text
lower_margin = lower_z * target_std * sqrt(prior_strength / (support + prior_strength))
lower_ev = calibrated_ev - lower_margin
```

この列を `timed_ev` の `long_column` / `short_column` として直接使い、既存のMLP exit holdingと組み合わせて検証した。

## Implementation

追加:

- `GroupEVCalibrationConfig.lower_z`
- `GroupEVStats.target_std`
- `GroupEVStats.target_standard_error`
- support-aware lower margin helper
- group EV calibration output:
  - `pred_regime_calibrated_long_best_adjusted_pnl_lower`
  - `pred_regime_calibrated_short_best_adjusted_pnl_lower`
  - support / margin / source columns
- fixed-horizon target calibration outputにも同じ lower / support / margin / source columnsを追加

`model-policy` / `model-sweep` 側は任意の `long_column` / `short_column` を受け取れるため、backtest側の追加変更は不要だった。

## Validation Setup

Calibration:

- validation OOF predictions: `data/reports/modeling/20260628_hgb_mlp_exit_hybrid/predictions_hgb_entry_mlp_exit_oof.parquet`
- validation months: `2024-07`, `2024-09`, `2024-11`, `2025-01`
- group columns: `volatility_regime,session_regime`
- `min_group_size=500`
- `prior_strength=2000`
- `prediction_shrinkage=0.65`
- `lower_z=0.5`

Policy sweep:

- `policy=timed_ev`
- score columns: support-aware lower EV
- holding columns: `pred_mlp_long_exit_event_minutes`, `pred_mlp_short_exit_event_minutes`
- `entry_threshold=15`
- `short_entry_threshold_offset=4`
- `side_margin=5`
- `max_predicted_hold_minutes=480`
- `min_entry_rank=0.0,0.5`

## Calibration Diagnostics

Validation OOF selection at threshold `15`:

| score | selected rows | selected avg adjusted pnl | side accuracy | long lower bias | short lower bias |
|---|---:|---:|---:|---:|---:|
| calibrated EV | `107001` | `18.9940` | `0.6066` | - | - |
| lower EV | `73694` | `19.5499` | `0.6163` | `-2.3821` | `-3.2308` |

Lower EV reduced the selected universe and improved OOF selected-side quality. This looked directionally useful before executable backtest.

However, apply diagnostics were mixed:

| apply month | score | selected rows | selected avg adjusted pnl | side accuracy | note |
|---|---|---:|---:|---:|---|
| `2024-12` | calibrated EV | `27094` | `12.0189` | `0.4439` | weak side accuracy |
| `2024-12` | lower EV | `21533` | `12.1293` | `0.4263` | fewer rows, worse side accuracy |
| `2025-02` | calibrated EV | `25900` | `18.1130` | `0.4868` | weak side accuracy |
| `2025-02` | lower EV | `21601` | `17.5710` | `0.4598` | fewer rows, worse side accuracy |

## Backtest Results

Validation 4fold summary:

| min entry rank | fold count | eligible fold count | min adjusted pnl | sum adjusted pnl | max drawdown max | forced exit max | eligible |
|---:|---:|---:|---:|---:|---:|---:|---|
| `0.0` | `4` | `2` | `-127.7796` | `196.4672` | `222.2264` | `0.0000` | false |
| `0.5` | `4` | `2` | `-134.5254` | `214.6528` | `220.8344` | `0.0000` | false |

The lower EV score fails the validation standard. The failure month is `2024-11`, where long-side losses increased.

Fixed holdout smoke:

| month | min entry rank | adjusted pnl | trades | max drawdown | forced exits |
|---|---:|---:|---:|---:|---:|
| `2024-12` | `0.0` | `-101.7542` | `73` | `157.7610` | `3` |
| `2024-12` | `0.5` | `-133.4082` | `71` | `161.8430` | `3` |
| `2025-02` | `0.0` | `+135.2708` | `113` | `95.2512` | `0` |
| `2025-02` | `0.5` | `+106.2222` | `91` | `81.6480` | `0` |

2025-02は強いが、2024-12を救えない。既存のraw baseline 2024-12 `-54.6032` や `long:ny_late:15` risk top `-5.4938` より悪い。

## Decision

- support-aware lower EV columnsは実装として残す。
- `lower_z=0.5` のstd-margin lower EVは標準policyに採用しない。
- 平均標準誤差marginは小さすぎ、std-marginはvalidation PnLを壊す。単純なglobal lower boundではなく、side/regimeの「どの方向を削るべきか」を別途学習・診断する必要がある。
- 次は、EV全体を一律に下げるのではなく、month/regime OOFで壊れやすい `long` 側の過大評価をtarget化する。候補として、`long`/`short` 別のcalibration residual target、またはside selection confidenceのregime-conditioned calibrationを優先する。

## Artifacts

- group calibration 2024-12 apply: `data/reports/modeling/20260628_134559_best_ev_support_std_lower_z0p5_2024_12/`
- group calibration 2025-02 apply: `data/reports/modeling/20260628_134627_best_ev_support_std_lower_z0p5_2025_02/`
- validation sweeps: `data/reports/backtests/best_ev_support_std_lower_z0p5_validation_base/`
- validation summary: `data/reports/backtests/best_ev_support_std_lower_z0p5_validation_summary/20260628_134712_model_sweep_summary/`
- fixed holdout tests: `data/reports/backtests/best_ev_support_std_lower_z0p5_fixed_tests/`

## Verification

- `PYTHONPATH=src python3 -m unittest tests.test_meta_model`
