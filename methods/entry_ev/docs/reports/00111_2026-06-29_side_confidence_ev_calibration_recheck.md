# Side Confidence EV Calibration Recheck

日時: 2026-06-29 07:37 JST
更新日時: 2026-06-29 07:37 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻である `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## 目的

`00110` では、2024-12型の崩れをsession/regime hard blockへ直結すると、ポジション空きによる代替entryで悪化することを確認した。

今回は hard block ではなく、既存のsoft補正を再検証する。

- `side_confidence_penalty`: side confidenceが低いsideのEVを下げる。
- `min_side_confidence`: confidenceの低いentryを開かない。
- `pred_calibrated_*_best_adjusted_pnl`: raw EVではなくcalibrated EV列を使う。

対象候補は `down5,up10` 固定。loss multiplierは `1.20`。

## Side Confidence Penalty

固定条件:

- `entry_threshold=12`
- `short_entry_threshold_offset=6`
- `side_margin=5`
- `min_entry_rank=0.5`
- `side_ev_penalty_rules=short:combined_regime=down_low_vol:5,short:combined_regime=up_low_vol:10`
- `pred_mlp_*_exit_event_minutes`

### Validation

| side confidence penalty | validation sum | validation min | trades | max DD | EV overestimate |
|---:|---:|---:|---:|---:|---:|
| `0` | `622.6486` | `138.0338` | `275` | `85.0166` | `13.8658` |
| `2` | `691.1634` | `151.6892` | `256` | `99.0990` | `13.6629` |
| `5` | `435.9082` | `87.1328` | `207` | `66.2788` | `15.3333` |
| `8` | `366.3432` | `11.6858` | `139` | `100.3932` | `16.1708` |
| `12` | `221.0460` | `10.6320` | `95` | `64.1916` | `18.3067` |
| `16` | `184.0738` | `-9.4830` | `47` | `63.0394` | `18.6029` |

validationだけなら `penalty=2` が最良に見える。合計、最低月、EV overestimate平均がbaseより良い。

### Holdout

| side confidence penalty | holdout sum | holdout min | trades | max DD | EV overestimate |
|---:|---:|---:|---:|---:|---:|
| `0` | `242.5008` | `-20.8252` | `426` | `122.9852` | `19.0017` |
| `2` | `192.9620` | `-34.8578` | `394` | `124.6100` | `19.4003` |
| `5` | `-101.8548` | `-131.3254` | `339` | `173.4418` | `21.1620` |
| `8` | `-104.6960` | `-137.7316` | `267` | `153.8002` | `22.3582` |
| `12` | `13.9212` | `-53.3918` | `189` | `86.6612` | `23.6514` |
| `16` | `68.8822` | `-17.8110` | `137` | `51.4440` | `25.4770` |

`penalty=2` はvalidationでは最良だったが、holdoutではbaseより悪い。特に2024-12は `-20.8252 -> -34.8578`、2025-03は `84.0776 -> 39.9498` に落ちる。

`penalty=16` はholdout minだけ少し改善するが、validationでは月10trades未満のfoldがあり、EV overestimateも大きい。実質的な低頻度化であり標準候補にはしない。

## Min Side Confidence

validationだけで棄却できる。

| min side confidence | validation sum | validation min | trades | min trades | eligible months |
|---:|---:|---:|---:|---:|---:|
| `0.00` | `622.6486` | `138.0338` | `275` | `65` | `4` |
| `0.55` | `314.7878` | `42.4602` | `126` | `30` | `4` |
| `0.60` | `311.0594` | `13.5768` | `69` | `12` | `4` |
| `0.65` | `103.4964` | `-39.7818` | `23` | `2` | `0` |
| `0.70` | `40.4818` | `-3.5160` | `7` | `1` | `0` |
| `0.75` | `65.4100` | `0.0000` | `1` | `0` | `0` |

global confidence gateは取引数を落としすぎる。`0.55` / `0.60` でもbaseに大きく負ける。

## Calibrated EV Columns

`pred_calibrated_long_best_adjusted_pnl` / `pred_calibrated_short_best_adjusted_pnl` へ差し替えて固定条件でvalidationした。

| month | adjusted pnl | trades | max DD | direction error | EV overestimate | worst direction/session |
|---|---:|---:|---:|---:|---:|---|
| 2024-07 | `14.6666` | `70` | `160.2196` | `0.3714` | `17.4650` | `long:asia` |
| 2024-09 | `83.5088` | `65` | `66.4966` | `0.3846` | `17.1204` | `long:ny_late` |
| 2024-11 | `-90.7698` | `76` | `146.2116` | `0.5658` | `21.7272` | `long:ny_overlap` |
| 2025-01 | `204.5940` | `67` | `29.2640` | `0.3284` | `16.8341` | `short:asia` |

validation sumは `211.9996`、minimumは `-90.7698`。raw EVの `622.6486` / `138.0338` と比べて明確に悪い。現固定閾値へそのままcalibrated EV列を差し替える方針は棄却する。

## 判断

今回の再検証では標準policyへ昇格するsoft補正はない。

- `side_confidence_penalty=2` はvalidation改善だが、holdoutでbaseより悪い。採用しない。
- `min_side_confidence` はvalidation時点で取引数とPnLを壊す。採用しない。
- `pred_calibrated_*_best_adjusted_pnl` は現閾値のまま差し替えるとvalidation 2024-11を壊す。採用しない。
- side confidenceは単独のglobal gate/penaltyではなく、entry/side targetを再学習する特徴、またはcandidate selectionの補助診断として扱う。

次は、候補後段のsoft補正ではなく、教師側で「side選択の不確実性」と「実現EVの分布」をより直接学習する方向へ戻す。

## Artifacts

- side confidence penalty validation: `data/reports/backtests/down5_up10_side_confidence_penalty_validation/`
- side confidence penalty holdout: `data/reports/backtests/down5_up10_side_confidence_penalty_holdout/`
- side confidence penalty validation summary: `data/reports/backtests/20260629_down5_up10_side_confidence_penalty_validation_summary.csv`
- side confidence penalty holdout summary: `data/reports/backtests/20260629_down5_up10_side_confidence_penalty_holdout_summary.csv`
- min side confidence validation: `data/reports/backtests/down5_up10_min_side_confidence_validation/`
- min side confidence summary: `data/reports/backtests/20260629_down5_up10_min_side_confidence_validation_summary.csv`
- calibrated EV validation: `data/reports/backtests/down5_up10_calibrated_ev_validation/`
- calibrated EV summary: `data/reports/backtests/20260629_down5_up10_calibrated_ev_validation_months.csv`

## Verification

- `python3 -m trade_data.backtest model-sweep`: OK for side confidence penalty validation/holdout
- `python3 -m trade_data.backtest model-sweep`: OK for min side confidence validation
- `python3 -m trade_data.backtest model-sweep`: OK for calibrated EV validation
