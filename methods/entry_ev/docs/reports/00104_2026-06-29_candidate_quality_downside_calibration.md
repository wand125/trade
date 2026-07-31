# Candidate Quality Downside Calibration

日時: 2026-06-29 06:36 JST
更新日時: 2026-06-29 06:36 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻である `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## 目的

`00103` で確認した fixed component のdownside driftを、単なるlong/short/stay flatラベルに潰さず、連続targetの下振れ・過大評価・supportを保持した診断特徴量としてpolicyへ接続する。

狙いは次の2点。

- candidate quality scoreのbucketとregimeごとに、実現target mean/lower/downside probability/overestimateをOOFから校正する。
- risk penaltyとして使えるかをvalidationとholdoutの両方で確認し、未来月で壊れるなら標準採用しない。

損益設定は現在の評価条件に合わせ、profit multiplier `1.0`, loss multiplier `1.20` に統一した。

## 実装

`trade_data.meta_model candidate-quality-downside-calibration` を追加した。

主な出力列:

- `pred_candidate_quality_<prefix>_<side>_calibrated_target_mean`
- `pred_candidate_quality_<prefix>_<side>_calibrated_target_lower`
- `pred_candidate_quality_<prefix>_<side>_downside_prob`
- `pred_candidate_quality_<prefix>_<side>_large_downside_prob`
- `pred_candidate_quality_<prefix>_<side>_overestimate`
- `pred_candidate_quality_<prefix>_<side>_overestimate_risk`
- `pred_candidate_quality_<prefix>_<side>_downside_risk`
- `pred_candidate_quality_<prefix>_<side>_large_downside_risk`
- `pred_candidate_quality_<prefix>_<side>_support`
- `pred_candidate_quality_<prefix>_<side>_source`
- `pred_candidate_quality_<prefix>_<side>_quality_bucket`

校正keyは `candidate_side + combined_regime + quality_bucket`。support不足時はside fallback、さらに不足する場合はglobal fallbackに落とす。validation OOFでは `--oof-column dataset_month` を指定し、scored monthをfit examplesから外す。

## Calibration Diagnostics

固定component OOF examplesは `9091` 件。full-fit global statsは次の通り。

| scope | support | target_mean | downside_prob | large_downside_prob | mean_overestimate | lower_coverage |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| global | 9091 | 1.2754 | 0.4114 | 0.0806 | 4.1076 | 0.7055 |
| long | 2530 | 2.5361 | 0.2996 | 0.0549 | 2.6862 | 0.8415 |
| short | 6561 | 0.7892 | 0.4545 | 0.0905 | 4.6557 | 0.6531 |

`long|down_low_vol|q09` は target_mean `-2.0472`, downside_prob `0.4927`, large_downside_prob `0.2781`, mean_overestimate `6.8049` で、high predicted quality bucketでも下振れが強い。これはquality scoreを単調なentry gateとして扱う危険を再確認する結果。

## Validation

代表validation 4ヶ月: `2024-07`, `2024-09`, `2024-11`, `2025-01`。

固定条件:

- policy: `timed_ev`
- entry threshold `12`
- long offset `0`, short offset `6`
- side margin `5`
- min entry rank `0.5`
- max predicted hold `480`
- short low-vol penalty: `down_low_vol:5`, `up_low_vol:10`, `range_low_vol:5`
- profit/loss: `1.0/1.20`

### Overestimate Risk

| risk penalty | sum pnl | min month pnl | trades | max DD | month pnls |
| ---: | ---: | ---: | ---: | ---: | --- |
| 0.00 | 673.9120 | 145.5682 | 274 | 92.0350 | 2024-07:146.9022, 2024-09:160.5454, 2024-11:145.5682, 2025-01:220.8962 |
| 0.25 | 690.8404 | 128.2770 | 266 | 86.6108 | 2024-07:184.5694, 2024-09:128.2770, 2024-11:154.9764, 2025-01:223.0176 |
| 0.50 | 655.8462 | 141.3836 | 253 | 134.3486 | 2024-07:141.3836, 2024-09:142.6028, 2024-11:163.0466, 2025-01:208.8132 |
| 1.00 | 617.8008 | 95.0238 | 221 | 118.4602 | 2024-07:178.0318, 2024-09:145.9136, 2024-11:95.0238, 2025-01:198.8316 |

`0.25` は合計PnLで最上位だが、最低月PnLはbaselineより悪い。単純採用には弱い。

### High Cost Stress

高コスト条件は `spread=0.2`, `slippage=0.1`, `execution_delay_bars=1`。

| risk penalty | sum pnl | min month pnl | max DD | month pnls |
| ---: | ---: | ---: | ---: | --- |
| 0.00 | 562.8784 | 120.5842 | 97.1906 | 2024-07:120.5842, 2024-09:121.1420, 2024-11:129.7600, 2025-01:191.3922 |
| 0.25 | 587.6084 | 88.7012 | 92.4722 | 2024-07:162.3486, 2024-09:88.7012, 2024-11:138.0462, 2025-01:198.5124 |

合計は改善するが、2024-09の最低月が大きく悪化。コスト耐性も標準採用には不足。

### Downside Probability Risk

| risk penalty | sum pnl | min month pnl | trades | max DD | month pnls |
| ---: | ---: | ---: | ---: | ---: | --- |
| 0.0 | 673.9120 | 145.5682 | 274 | 92.0350 | 2024-07:146.9022, 2024-09:160.5454, 2024-11:145.5682, 2025-01:220.8962 |
| 2.0 | 684.8380 | 128.7000 | 268 | 87.7004 | 2024-07:176.2278, 2024-09:128.7000, 2024-11:154.4294, 2025-01:225.4808 |
| 5.0 | 653.1936 | 97.2322 | 243 | 105.4678 | 2024-07:163.6368, 2024-09:185.5172, 2024-11:97.2322, 2025-01:206.8074 |
| 10.0 | 441.2832 | 73.5110 | 188 | 113.5064 | 2024-07:124.7242, 2024-09:73.5110, 2024-11:88.5718, 2025-01:154.4762 |

`2.0` は合計でbaselineを上回るが、worst regime lossが悪化する。強いpenaltyは取引数を削りすぎる。

## Holdout

holdout: `2024-12`, `2025-02`, `2025-03`, `2025-04`。OOF全体でfitしたcalibratorを各holdout predictionに適用し、同じ固定条件で評価した。

### Overestimate Risk Holdout

| risk penalty | sum pnl | min month pnl | trades | max DD | month pnls |
| ---: | ---: | ---: | ---: | ---: | --- |
| 0.00 | -116.0564 | -223.7292 | 314 | 474.6194 | 2024-12:7.2314, 2025-02:101.3432, 2025-03:-0.9018, 2025-04:-223.7292 |
| 0.25 | -88.1660 | -229.0214 | 314 | 406.1932 | 2024-12:22.9342, 2025-02:158.7132, 2025-03:-40.7920, 2025-04:-229.0214 |

合計とDDは改善するが、2025-03と2025-04が悪化する。未来月での安定採用には足りない。

### Downside Probability Holdout

| risk penalty | sum pnl | min month pnl | trades | max DD | month pnls |
| ---: | ---: | ---: | ---: | ---: | --- |
| 0.0 | -116.0564 | -223.7292 | 314 | 474.6194 | 2024-12:7.2314, 2025-02:101.3432, 2025-03:-0.9018, 2025-04:-223.7292 |
| 2.0 | -160.0460 | -326.0556 | 309 | 501.1292 | 2024-12:27.1460, 2025-02:143.4598, 2025-03:-4.5962, 2025-04:-326.0556 |

downside probability riskはholdoutで明確に悪化。採用しない。

## 判断

実装と診断列は採用する。標準policyのrisk penaltyとしては採用しない。

理由:

- validationではoverestimate risk `0.25` が合計PnLを改善したが、最低月PnLはbaselineを下回った。
- high cost stressでは合計改善の代わりに2024-09が崩れた。
- holdoutではoverestimate risk `0.25` が合計とDDを改善したものの、2025-03/2025-04を悪化させた。
- downside probability riskはholdoutで大幅悪化した。

現在の弱点は、校正されたdownside signalそのものより、2025-04のshort exposureが `range_normal_vol` / `rollover` で壊れる構造。ここをholdout後付けでrule化すると過学習になるため、次はvalidation内で事前登録した regime/session exposure risk と、entry timing targetの再設計で扱う。

## Artifacts

- OOF downside calibration: `data/reports/modeling/20260629_candidate_quality_downside_calibration/predictions_fixed_component_oof_downside.parquet`
- OOF holding: `data/reports/modeling/20260629_candidate_quality_downside_calibration/predictions_fixed_component_oof_downside_holding.parquet`
- calibration stats: `data/reports/modeling/20260629_candidate_quality_downside_calibration/predictions_fixed_component_oof_downside.calibration_stats.csv`
- base validation overestimate: `data/reports/backtests/candidate_quality_downside_overestimate_risk_validation/`
- high cost validation overestimate: `data/reports/backtests/candidate_quality_downside_overestimate_risk_validation_highcost/`
- validation downside probability: `data/reports/backtests/candidate_quality_downside_probability_risk_validation/`
- holdout overestimate: `data/reports/backtests/candidate_quality_downside_overestimate_risk_holdout/`
- holdout downside probability: `data/reports/backtests/candidate_quality_downside_probability_risk_holdout/`
- comparison summaries:
  - `data/reports/backtests/candidate_quality_downside_risk_source_comparison_summary.csv`
  - `data/reports/backtests/candidate_quality_downside_holdout_risk_comparison_summary.csv`

## Validation Commands

- `python3 -m py_compile src/trade_data/meta_model.py tests/test_meta_model.py`: OK
- `python3 -m unittest tests.test_meta_model.MetaModelTests.test_candidate_quality_downside_calibration_adds_side_risk_columns`: OK
- `python3 -m unittest tests.test_meta_model.MetaModelTests.test_candidate_quality_report_metrics_capture_month_and_bucket_drift`: OK
- `python3 -m unittest tests.test_docs_reports`: OK
- `python3 -m unittest discover tests`: OK, 150 tests
- `git diff --check`: OK
