# Candidate Quality Component Composite

日時: 2026-06-29 03:10 JST
更新日時: 2026-06-29 03:14 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻である `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## 目的

前回は timed / fixed / clipped component を単独の `min_trade_quality` gateとして試したが、baselineを超えなかった。

今回はcomponentを1つに潰すのではなく、複数componentを合成したquality列を作り、既存 `model-sweep` のquality gateへ渡した。

狙い:

- `mean`: component ensembleとして平均化する。
- `min`: 複数componentの合意が弱い候補を落とす。
- `weighted_mean`: fixed horizon componentを重めにし、forced exit回避signalを少し反映する。

## 実装

`trade_data.meta_model combine-candidate-quality-components` を追加した。

入力:

- `--predictions`: prefixed candidate quality列を含むprediction parquet
- `--component-prefixes`: 例 `timed_component,fixed_component,clipped_best`
- `--output-prefix`: 例 `component_fixed_weighted`
- `--mode`: `mean`, `min`, `max`, `weighted_mean`
- `--weights`: `weighted_mean` 用

出力:

- `pred_candidate_quality_<output_prefix>_<side>_adjusted_pnl`
- `pred_candidate_quality_<output_prefix>_<side>_lower_adjusted_pnl`
- `pred_candidate_quality_<output_prefix>_<side>_overestimate_risk`
- `pred_candidate_quality_<output_prefix>_<side>_lower_overestimate_risk`

合成後も既存 `model-sweep --long-trade-quality-column` / `--short-trade-quality-column` にそのまま渡せる。

## 条件

- input predictions: `data/reports/modeling/20260628_175327_candidate_quality_prefixed_clipped_best_oof/predictions_validation_oof_candidate_quality_model.parquet`
- components: `timed_component`, `fixed_component`, `clipped_best`
- output variants:
  - `component_mean`: `mean`
  - `component_min`: `min`
  - `component_fixed_weighted`: `weighted_mean`, weights `0.25,0.5,0.25`
- validation months: `2024-07,2024-09,2024-11,2025-01`
- policy validation: profit multiplier `1.0`, loss multiplier `1.20`
- policy: `timed_ev`
- entry threshold grid: `10,12,15`
- short offset: `6`
- side margin: `5`
- risk penalty: `0`
- min entry rank grid: `0,0.5`
- min trade quality grid: `-inf,0,2,5,8,10,12`
- holding columns: `pred_mlp_long_exit_event_minutes`, `pred_mlp_short_exit_event_minutes`
- max predicted hold minutes: `480`
- summary filter: `min-folds=4`, `min-trades-per-fold=10`, `max-forced-exit-rate=0.10`

## Composite列確認

全variantで `115252` rows、出力8列の欠損は0。

| variant | long mean | short mean | long risk mean | short risk mean |
|---|---:|---:|---:|---:|
| component_mean | `5.1510` | `4.8709` | `-8.7058` | `-9.2617` |
| component_min | `1.3182` | `0.8809` | `-12.5352` | `-13.2406` |
| component_fixed_weighted | `4.3368` | `4.0031` | `-9.5169` | `-10.1202` |

## Validation

baselineは `entry=12`, `min_entry_rank=0.5`, `min_trade_quality=-inf`。

| variant | best finite gate | min pnl | sum pnl | min trades | forced exit max | EV overestimate mean | direction error mean |
|---|---|---:|---:|---:|---:|---:|---:|
| baseline | no gate | `82.7176` | `406.6546` | `24` | `0.0370` | `15.5226` | `0.3809` |
| component_mean | quality `0` | `82.7176` | `406.1976` | `24` | `0.0370` | `15.5271` | `0.3809` |
| component_min | quality `0` | `34.5604` | `315.1544` | `18` | `0.0000` | `16.4648` | `0.4091` |
| component_fixed_weighted | quality `0` | `82.7176` | `410.7146` | `24` | `0.0370` | `15.4567` | `0.3809` |

## 判断

`component_fixed_weighted` の `quality>=0` はbaselineと同じfold最低PnLを維持し、合計PnLを `+4.0600`、EV overestimate meanを `-0.0659` 改善した。これはcomponent列を単独gateではなく、軽いensemble/tie-breakとして使う方向には合っている。

ただし、改善幅は小さい。forced exit maxは `0.0370` のまま、direction errorも変わらない。さらにprefixed apply parquetは今回作っておらず、2024-12 / 2025-02 fixed holdoutへは未適用。

そのため標準policyとしてはまだ採用しない。現時点の扱いは以下。

- `combine-candidate-quality-components` は採用する。component列を評価へ接続する基盤として有用。
- `component_min` は絞りすぎてtrade数とPnLを壊すため採用しない。
- `component_mean` はbaselineとほぼ同じで、採用理由が弱い。
- `component_fixed_weighted quality>=0` はtie-break候補として残す。次はprefixed applyを生成して、2024-12 / 2025-02だけでなく、見すぎていない追加holdoutにも固定適用する。

## Artifacts

- composite predictions: `data/reports/modeling/20260629_candidate_quality_component_composites/`
- mean validation: `data/reports/backtests/candidate_quality_component_mean_stack_validation/`
- min validation: `data/reports/backtests/candidate_quality_component_min_stack_validation/`
- fixed weighted validation: `data/reports/backtests/candidate_quality_component_fixed_weighted_stack_validation/`
- mean summary: `data/reports/backtests/candidate_quality_component_mean_stack_summary/20260628_180940_model_sweep_summary/`
- min summary: `data/reports/backtests/candidate_quality_component_min_stack_summary/20260628_180940_model_sweep_summary/`
- fixed weighted summary: `data/reports/backtests/candidate_quality_component_fixed_weighted_stack_summary/20260628_180940_model_sweep_summary/`

## Verification

- `PYTHONPATH=src python3 -m unittest tests.test_meta_model`: OK, 30 tests
- `PYTHONPATH=src python3 -m unittest tests.test_meta_model tests.test_docs_reports`: OK, 31 tests
- `PYTHONPATH=src python3 -m unittest discover -s tests`: OK, 138 tests
- `git diff --check`: OK
