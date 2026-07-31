# Profit Barrier OOF Representative

日時: 2026-06-28 17:44 JST
更新日時: 2026-06-28 17:44 JST

## Summary

- Experiment ID: `profit_barrier_oof_representative_smoke`
- Status: implemented and diagnosed
- Main result: 代表4ヶ月OOFでは `0.4-0.6` bucket 全体の大きな過大評価は再現しなかったが、short側と `>=0.5` 高信頼領域は過大評価が残った。
- Report numbering note: this file is numbered from the internal file `日時`, not filesystem mtime or `更新日時`.

## Implementation

`trade_data.modeling oof --target-set profit_barrier` を追加できるようにした。

変更点:

- `profit_barrier` target setを追加し、`long_profit_barrier_hit` / `short_profit_barrier_hit` だけを学習対象にした。
- EV列を持たないtarget setでも `prediction_frame_evaluation_metrics` と OOF fold metrics が落ちないよう、selection metricsは必要列がある場合だけ計算する。
- `write_oof_report` も selection metrics がない OOF を許容する。

## OOF Setup

- dataset: `data/processed/datasets/xauusd_m1_p1_l1p2`
- months: `2024-07,2024-09,2024-11,2025-01`
- fold: 1 month blocked OOF
- purge: label overlap purge enabled
- embargo: 24 hours
- sample frac: `0.25`
- max iter: `20`
- target set: `profit_barrier`

Artifacts:

- OOF predictions: `experiments/20260628_084318_profit_barrier_oof_representative_smoke/predictions_oof.parquet`
- OOF metrics: `experiments/20260628_084318_profit_barrier_oof_representative_smoke/metrics.json`
- calibration report: `data/reports/modeling/20260628_084402_profit_barrier_oof_representative_smoke/`

OOF classifier metrics:

| target | accuracy | balanced accuracy | macro F1 |
|---|---:|---:|---:|
| `long_profit_barrier_hit` | `0.5220` | `0.4962` | `0.3551` |
| `short_profit_barrier_hit` | `0.7213` | `0.5013` | `0.4335` |

## Overall Calibration

| stacked rows | actual hit | predicted mean | calibration error | Brier | predicted hit rate | threshold accuracy |
|---:|---:|---:|---:|---:|---:|---:|
| `238482` | `0.3734` | `0.3295` | `-0.0439` | `0.2272` | `0.2059` | `0.6166` |

全体では、valid/test smokeと同じく予測平均は実測hit rateより低い。したがって global down-shift は危険。

## Bucket View

| bucket | rows | actual hit | predicted mean | overestimate | threshold accuracy |
|---|---:|---:|---:|---:|---:|
| `0.00-0.20` | `7753` | `0.0749` | `0.1852` | `0.1103` | `0.9251` |
| `0.20-0.40` | `181626` | `0.3585` | `0.3073` | `0.0000` | `0.6415` |
| `0.40-0.60` | `49088` | `0.4759` | `0.4341` | `0.0000` | `0.4759` |
| `0.60-0.80` | `15` | `0.0000` | `0.6001` | `0.6001` | `0.0000` |

前回の valid/test smoke では test `0.40-0.60` bucket が actual `0.1807` / predicted `0.4447` で強く壊れた。今回の代表OOFでは同bucket全体の崩れは再現せず、actual `0.4759` / predicted `0.4341` だった。

## Threshold Subset

`probability >= 0.4` のみ:

| side | rows | actual hit | predicted mean | error |
|---|---:|---:|---:|---:|
| long | `37938` | `0.5164` | `0.4282` | `-0.0882` |
| short | `11165` | `0.3376` | `0.4545` | `0.1169` |

`probability >= 0.5` のみ:

| side | rows | actual hit | predicted mean | error |
|---|---:|---:|---:|---:|
| long | `2149` | `0.3685` | `0.5556` | `0.1870` |
| short | `1638` | `0.3107` | `0.5196` | `0.2089` |

Month / side view for `probability >= 0.4`:

| month | side | rows | actual hit | predicted mean | error |
|---|---|---:|---:|---:|---:|
| `2024-07` | long | `6198` | `0.3622` | `0.4725` | `0.1102` |
| `2024-07` | short | `1535` | `0.2573` | `0.4289` | `0.1716` |
| `2024-09` | long | `8592` | `0.5334` | `0.4190` | `-0.1144` |
| `2024-09` | short | `2445` | `0.3063` | `0.4446` | `0.1383` |
| `2024-11` | long | `10870` | `0.4419` | `0.4195` | `-0.0224` |
| `2024-11` | short | `6610` | `0.3770` | `0.4642` | `0.0872` |
| `2025-01` | long | `12278` | `0.6482` | `0.4200` | `-0.2282` |
| `2025-01` | short | `575` | `0.2313` | `0.4531` | `0.2218` |

## Interpretation

- `0.4-0.6` bucket崩れは、代表OOF全体では再現しなかった。前回testの崩れはholdout/regime固有の可能性が高い。
- ただし short側は `probability >= 0.4` で一貫して過大評価しており、2025-01 shortは support `575` と薄いが error `0.2218`。
- `probability >= 0.5` は long/shortとも過大評価になり、高信頼領域をそのまま信用できない。
- classifierのbalanced accuracyはほぼ `0.5` なので、profit-barrier確率を単独の強いentry根拠にするには弱い。

## Decision

- `profit_barrier_threshold=0.4` を hard gate として単独採用しない。
- global calibration補正もしない。全体平均では過小評価だが、shortと高信頼bucketは過大評価しているため、global補正は壊れ方を悪化させうる。
- 次は side別、bucket別、support-aware のOOF calibrationを作る。候補選定では raw probability ではなく、OOF上のsmoothed actual hit rate / uncertainty / supportを併記する。

## Next Actions

1. profit-barrier確率に side別 calibrated probability を追加する。
2. calibrationは月別OOFでfitし、low support bucketはLaplace smoothingまたは信頼区間penaltyを入れる。
3. `model-candidate-selection` のtie-breakに raw probability ではなく calibrated/support-aware hit rateを入れる。
4. high-confidence bucket `>=0.5` を採用方向に使う場合は、必ずside別・月別のOOF evidenceを要求する。
