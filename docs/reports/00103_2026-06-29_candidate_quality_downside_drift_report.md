# Candidate Quality Downside Drift Report

日時: 2026-06-29 06:17 JST
更新日時: 2026-06-29 06:17 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻である `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## 目的

`00102` の反省として、candidate failure分類probabilityをentry scoreへ直接penalty接続する方針は採用しない。

次の本流である「candidate rowの連続的なrealizable PnL / lower quantile / calibrated downside」を扱う前に、既存のcandidate quality OOF exampleを月・side・regime・prediction bucketで分解し、target分布のshift、下側分位coverage、過大評価を確認する診断CLIを追加した。

## 実装

`trade_data.meta_model candidate-quality-report` を追加した。

入力:

- `validation_oof_candidate_quality_examples.csv`
- `target`
- `pred_taken_ev`
- `pred_candidate_quality_taken_adjusted_pnl`
- `pred_candidate_quality_taken_lower_adjusted_pnl`
- 任意のgroup columns: `dataset_month`, `candidate_side`, `combined_regime`, `session_regime` など

出力:

- `overall_metrics.csv`
- `group_metrics.csv`
- `bucket_metrics.csv`
- `summary.json`

主なmetric:

- `target_mean`, `target_q10`, `target_q25`
- raw / mean / lower prediction bias
- raw / mean / lower overestimate mean
- lower quantile coverage
- downside prevalence: `target <= 0`, `target <= -15`
- prediction bucket別の同metric
- month/regime groupの全体平均との差分

## 診断対象

既存の代表4ヶ月OOF candidate quality componentを診断した。

validation months:

- `2024-07`
- `2024-09`
- `2024-11`
- `2025-01`

target:

- `timed_barrier_component_adjusted_pnl`
- `fixed_horizon_component_adjusted_pnl`
- `clipped_best_adjusted_pnl`

## Overall

| target | support | target mean | mean bias | mean MAE | mean overestimate | lower overestimate | lower coverage | target<=0 | target<=-15 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| timed component | `9091` | `1.4816` | `0.7989` | `12.7850` | `6.7919` | `1.8138` | `0.6754` | `0.4282` | `0.0000` |
| fixed component | `9091` | `1.2754` | `0.2982` | `7.9169` | `4.1076` | `1.9189` | `0.7055` | `0.4114` | `0.0806` |
| clipped best | `9091` | `11.0714` | `0.0182` | `4.9377` | `2.4779` | `1.2781` | `0.7078` | `0.0152` | `0.0000` |

読み:

- fixed componentはbias/MAEのバランスが最も現実的。
- timed componentはtargetの分散が大きく、mean overestimateが大きい。lowerは保守的だがcoverageは `0.6754` と十分ではない。
- clipped bestは見かけのMAEが良いが、`target<=0` が `0.0152` しかなく、downside教師としては情報を消しすぎている。

## Month Drift

fixed componentの月別:

| month | support | target mean | target mean shift | mean bias | mean overestimate | lower coverage | target<=0 | target<=0 shift | target<=-15 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `2024-07` | `2124` | `2.9214` | `+1.6460` | `-2.1630` | `2.0589` | `0.9134` | `0.2415` | `-0.1699` | `0.0504` |
| `2024-09` | `1156` | `0.8582` | `-0.4172` | `-0.0337` | `3.7498` | `0.6808` | `0.3711` | `-0.0403` | `0.0476` |
| `2024-11` | `4075` | `0.6929` | `-0.5824` | `+1.7279` | `5.4115` | `0.6125` | `0.4785` | `+0.0671` | `0.1151` |
| `2025-01` | `1736` | `0.9065` | `-0.3689` | `+0.1747` | `3.7917` | `0.6861` | `0.4885` | `+0.0771` | `0.0588` |

読み:

- 2024-11はsupportが最も多いのに、mean overestimate `5.4115`, lower coverage `0.6125`, `target<=-15` `0.1151` と下振れが大きい。
- 2025-01も `target<=0` が `0.4885` まで増え、全体より `+0.0771` 悪い。
- 月別shiftを無視してglobal quality gateやscalar riskへ直結すると、validation内でも月の偏りを拾いやすい。

## Regime Drift

fixed componentのworst month+combined regime:

| month | combined regime | support | target mean | mean bias | mean overestimate | lower coverage | target<=0 | target<=-15 |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `2024-11` | `range_high_vol` | `23` | `-6.5387` | `6.7620` | `7.9114` | `0.0870` | `0.9130` | `0.0000` |
| `2024-09` | `down_low_vol` | `288` | `-6.6474` | `6.9189` | `8.3326` | `0.3715` | `0.7153` | `0.1771` |
| `2025-01` | `range_low_vol` | `614` | `-1.4601` | `2.7485` | `4.8562` | `0.5896` | `0.6743` | `0.0570` |
| `2024-11` | `range_low_vol` | `513` | `-3.7463` | `5.1673` | `6.7550` | `0.5634` | `0.6277` | `0.2398` |
| `2025-01` | `down_low_vol` | `211` | `0.2966` | `0.1241` | `3.8360` | `0.7583` | `0.5735` | `0.1280` |

読み:

- `range_low_vol` と `down_low_vol` は複数月でdownside prevalenceが高い。
- ただしこれはruleで直接減点すべきという意味ではない。`00101` と `00102` でrule/risk直結はholdout悪化が確認済み。
- 使うなら、月別・regime別のsupportとcoverageを持つcalibrated downside featureとして扱い、policyへ直結する前に別foldで検証する。

## Prediction Bucket

fixed componentのmean prediction bucketを全体集約した。

| bucket | support | target mean | mean pred | lower pred | mean bias | mean overestimate | lower coverage | target<=0 | target<=-15 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `q01` | `907` | `2.2977` | `-2.3398` | `-7.2844` | `-4.6375` | `2.5810` | `0.7464` | `0.2955` | `0.0926` |
| `q05` | `909` | `2.3950` | `1.3441` | `-4.1608` | `-1.0509` | `3.0023` | `0.7613` | `0.3080` | `0.0385` |
| `q07` | `909` | `-0.3701` | `2.2603` | `-3.3443` | `2.6305` | `4.6483` | `0.7250` | `0.5457` | `0.1122` |
| `q09` | `871` | `-0.3879` | `3.6373` | `-2.2246` | `4.0252` | `6.5076` | `0.5844` | `0.5063` | `0.1401` |
| `q10` | `909` | `1.2699` | `5.6681` | `-1.1705` | `4.3982` | `6.3060` | `0.6139` | `0.4257` | `0.0440` |

読み:

- fixed componentのmean predictionは単調なquality rankになっていない。
- 上位bucket `q09/q10` はmean predictionが高いにもかかわらず、mean overestimateが大きくlower coverageも悪い。
- したがって `min_trade_quality` や `quality>=k` のようなhard gateは引き続き危険。quality scoreは単独rankではなく、overestimate/downside calibration featureとして使うべき。

## 判断

今回の診断器は採用。

ただし、fixed/timed/clipped componentのどれも、このまま単独でpolicy scoreへ直結しない。

次の方針:

- fixed componentを中心に、month/regime/bucket別のcalibrated downsideを作る。
- global quality thresholdは使わない。
- `range_low_vol`, `down_low_vol`, 2024-11型の下振れは、ruleではなくsupport-aware calibrated featureとして扱う。
- prediction bucket別に「高quality予測ほど過大評価する」現象をpenalty候補にする。ただしpolicy適用前にvalidation fold内でOOF校正し、holdoutで反証する。

## Artifacts

- timed report: `data/reports/modeling/20260628_211643_candidate_quality_downside_report_timed_component/`
- fixed report: `data/reports/modeling/20260628_211643_candidate_quality_downside_report_fixed_component/`
- clipped report: `data/reports/modeling/20260628_211643_candidate_quality_downside_report_clipped_best/`

## Verification

- `python3 -m py_compile src/trade_data/meta_model.py tests/test_meta_model.py`: OK
- `python3 -m unittest tests.test_meta_model.MetaModelTests.test_candidate_quality_report_metrics_capture_month_and_bucket_drift`: OK
- `python3 -m unittest tests.test_docs_reports`: OK
- `python3 -m trade_data.meta_model candidate-quality-report`: OK for timed/fixed/clipped component examples
