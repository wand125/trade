# Profit Barrier Bucket Calibration

日時: 2026-06-28 17:56 JST
更新日時: 2026-06-28 17:56 JST

## Summary

- Experiment ID: `profit_barrier_oof_month_bucket_calibration_smoke_v2`
- Status: implemented and diagnosed
- Main result: side/bucket/support-aware calibrationはglobal biasとBrierを改善したが、月×sideの不安定性は残った。policy gateへ直結するにはまだ危険。
- Report numbering note: this file is numbered from the internal file `日時`, not filesystem mtime or `更新日時`.

## Implementation

`trade_data.modeling profit-barrier-calibrate` を追加した。

機能:

- raw profit-barrier probabilityをside別・probability bucket別に実測hit率へ写像する。
- bucket実測はLaplace smoothingする。
- `min_bucket_rows` 未満のbucketはside全体へfallbackする。
- `calibrated_prob_lower` と support/source/bucket列も保存する。
- `--oof-column dataset_month` で、各月をfitから抜いて校正を適用できる。

追加される列:

- `pred_long_profit_barrier_hit_calibrated_prob`
- `pred_short_profit_barrier_hit_calibrated_prob`
- `pred_long_profit_barrier_hit_calibrated_prob_lower`
- `pred_short_profit_barrier_hit_calibrated_prob_lower`
- `pred_*_profit_barrier_hit_calibration_support`
- `pred_*_profit_barrier_hit_calibration_source`
- `pred_*_profit_barrier_hit_calibration_bucket`

## Setup

- fit/apply predictions: `experiments/20260628_084318_profit_barrier_oof_representative_smoke/predictions_oof.parquet`
- OOF column: `dataset_month`
- months: `2024-07`, `2024-09`, `2024-11`, `2025-01`
- bucket count: `5`
- min bucket rows: `500`
- alpha: `1.0`
- lower z: `1.0`
- threshold: `0.4`

Artifacts:

- `data/reports/modeling/20260628_085552_profit_barrier_oof_month_bucket_calibration_smoke_v2/`
- calibrated predictions: `data/reports/modeling/20260628_085552_profit_barrier_oof_month_bucket_calibration_smoke_v2/predictions_profit_barrier_calibrated.parquet`
- calibration table: `data/reports/modeling/20260628_085552_profit_barrier_oof_month_bucket_calibration_smoke_v2/oof_calibration_table.csv`

## Overall

| probability | actual hit | predicted mean | calibration error | Brier | predicted hit rate | threshold accuracy |
|---|---:|---:|---:|---:|---:|---:|
| raw | `0.3734` | `0.3295` | `-0.0439` | `0.2272` | `0.2059` | `0.6166` |
| calibrated | `0.3734` | `0.3707` | `-0.0027` | `0.2250` | `0.4853` | `0.6129` |
| conservative lower | `0.3734` | `0.3684` | `-0.0050` | `0.2251` | `0.4853` | `0.6129` |

Brier improvement:

- calibrated: `+0.002198`
- conservative lower: `+0.002165`

## Threshold Subsets

| signal | side | rows | actual hit | predicted mean | raw mean | error |
|---|---|---:|---:|---:|---:|---:|
| raw `>=0.4` | long | `37938` | `0.5164` | `0.4282` | `0.4282` | `-0.0882` |
| raw `>=0.4` | short | `11165` | `0.3376` | `0.4545` | `0.4545` | `0.1169` |
| raw `>=0.5` | long | `2149` | `0.3685` | `0.5556` | `0.5556` | `0.1870` |
| raw `>=0.5` | short | `1638` | `0.3107` | `0.5196` | `0.5196` | `0.2089` |
| calibrated `>=0.4` | long | `115742` | `0.4859` | `0.4808` | `0.3539` | `-0.0051` |
| calibrated `>=0.5` | long | `43362` | `0.4106` | `0.5234` | `0.3830` | `0.1128` |
| lower `>=0.4` | long | `115742` | `0.4859` | `0.4784` | `0.3539` | `-0.0075` |
| lower `>=0.5` | long | `43362` | `0.4106` | `0.5208` | `0.3830` | `0.1102` |

## Month And Side

| month | side | rows | actual hit | calibrated mean | raw mean | error |
|---|---|---:|---:|---:|---:|---:|
| `2024-07` | long | `31587` | `0.4935` | `0.4294` | `0.3482` | `-0.0641` |
| `2024-07` | short | `31587` | `0.2568` | `0.2845` | `0.3151` | `0.0276` |
| `2024-09` | long | `28885` | `0.4519` | `0.4662` | `0.3429` | `0.0144` |
| `2024-09` | short | `28885` | `0.2651` | `0.2728` | `0.2989` | `0.0077` |
| `2024-11` | long | `28572` | `0.3842` | `0.5220` | `0.3528` | `0.1378` |
| `2024-11` | short | `28572` | `0.3708` | `0.2480` | `0.3282` | `-0.1228` |
| `2025-01` | long | `30197` | `0.5570` | `0.4597` | `0.3524` | `-0.0974` |
| `2025-01` | short | `30197` | `0.2067` | `0.2857` | `0.2976` | `0.0791` |

## Interpretation

- 月別OOFでもglobalには改善した。全体biasは `-0.0439` から `-0.0027` まで縮んだ。
- raw short `>=0.4` の過大評価は、calibration後はshortが `>=0.4` に残らない形で抑えられた。
- 一方で calibrated `>=0.5` はlongだけに偏り、actual `0.4106` / predicted `0.5234` と過大評価が残る。
- 月×sideでは 2024-11 long `+0.1378`、2024-11 short `-0.1228`、2025-01 long `-0.0974` と、regime依存のズレが大きい。
- したがって、global calibrationをpolicy thresholdへ直結しない。これは「確率校正の診断列」として使い、entry gateにするなら月別OOFでthreshold台地とbacktestを別途検証する。

## Decision

- `profit-barrier-calibrate` は採用し、次の候補診断で使う。
- `pred_*_profit_barrier_hit_calibrated_prob` をそのまま `>=0.5` gateに使う案は採用しない。
- 次は calibrated probability / lower probability を `model-policy` へ渡した固定候補比較を行う。ただし、thresholdはvalidationで事前登録し、blind月で後付けしない。

## Next Actions

1. `model-policy` / `model-sweep` で calibrated profit-barrier probability列を指定して raw列との差分を比較する。
2. thresholdは `0.35`, `0.40`, `0.45`, `0.50` を小さく比較し、取引回数・side偏り・month×side errorを見る。
3. `calibrated_prob_lower` はhard gate候補ではなく、support-aware tie-breakまたはpenaltyとして試す。
4. 月×sideのズレが大きいため、次は `session_regime` / `trend_regime` を含めたcalibrationを検討する。ただしsupport不足と過学習に注意する。
