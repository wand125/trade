# Candidate Quality Prefixed Component Gates

日時: 2026-06-29 02:57 JST
更新日時: 2026-06-29 03:01 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻である `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## 目的

前回のcomponent target検証では、componentを `raw EV - predicted quality` の単一risk penaltyへ潰すとbaselineに負けた。

今回はcomponent予測を同じprediction parquetへ共存させるため、candidate quality出力にprefixを追加し、timed / fixed / clipped componentを別々の `min_trade_quality` gateとして検証した。

## 実装

`oof-candidate-quality-model` に `--prediction-prefix` を追加した。

prefixなしでは従来列を維持する。

- `pred_candidate_quality_long_adjusted_pnl`
- `pred_candidate_quality_short_adjusted_pnl`
- `pred_candidate_quality_long_lower_adjusted_pnl`
- `pred_candidate_quality_short_lower_adjusted_pnl`
- `pred_candidate_quality_long_overestimate_risk`
- `pred_candidate_quality_short_overestimate_risk`

prefixありでは、同じprediction parquetにcomponent別列を共存できる。

- `pred_candidate_quality_timed_component_long_adjusted_pnl`
- `pred_candidate_quality_fixed_component_long_adjusted_pnl`
- `pred_candidate_quality_clipped_best_long_adjusted_pnl`
- short / lower / risk列も同じ規則で出力する。

prefixは英数字とunderscoreだけ許可する。学習例とOOF metricsは従来列名を使うため、既存の評価互換は維持する。

## 条件

- base predictions: `data/reports/modeling/20260629_hgb_mlp_exit_hybrid_forced_targets/predictions_hgb_entry_mlp_exit_oof_forced.parquet`
- final combined OOF predictions: `data/reports/modeling/20260628_175327_candidate_quality_prefixed_clipped_best_oof/predictions_validation_oof_candidate_quality_model.parquet`
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
- candidate summary filter: `min-folds=4`, `min-trades-per-fold=10`, `max-forced-exit-rate=0.10`

## OOF列確認

final combined OOF parquetは `115252` rows、candidate quality component列は `24` 本で、対象列の欠損は0だった。

代表平均:

| column family | long mean | short mean |
|---|---:|---:|
| timed component mean | `2.1530` | `1.8340` |
| fixed component mean | `1.8941` | `1.3998` |
| clipped best mean | `11.4059` | `11.3788` |

## Validation

baselineは `entry=12`, `min_entry_rank=0.5`, `min_trade_quality=-inf`。

| gate family | best positive gate | min pnl | sum pnl | min trades | forced exit max | EV overestimate mean |
|---|---|---:|---:|---:|---:|---:|
| baseline | no gate | `82.7176` | `406.6546` | `24` | `0.0370` | `15.5226` |
| timed component | entry `10`, rank `0.5`, quality `0` | `39.5520` | `287.2454` | `24` | `0.0357` | `16.5066` |
| fixed component | entry `12`, rank `0.5`, quality `0` | `71.1944` | `367.3486` | `21` | `0.0000` | `15.9284` |
| clipped best | entry `12`, rank `0.5`, quality `0/2/5` | `82.7176` | `406.6546` | `24` | `0.0370` | `15.5226` |
| clipped best | entry `12`, rank `0.5`, quality `8` | `82.7176` | `402.3006` | `24` | `0.0370` | `15.5758` |
| clipped best | entry `12`, rank `0.5`, quality `10` | `78.9308` | `334.8868` | `22` | `0.0370` | `16.3418` |

## 判断

`--prediction-prefix` は採用する。component列を同じparquetへ共存させる基盤として必要で、既存列の互換も崩さない。

一方、component meanを単独の `min_trade_quality` gateとして標準採用しない。

理由:

- timed component gateはfold最低PnLと合計PnLを大きく落とし、EV過大評価も悪化する。
- fixed component gateはbest positiveでfold最低PnL `71.1944` まで近づくが、baseline `82.7176` 未満。forced exitを0にする効果はあるが、PnL改善に変換できていない。
- clipped best gateは `0/2/5` では実質何も落とさず、`8/10` 以上では合計PnLとEV過大評価が悪化する。

次は単一component gateではなく、component列を診断特徴として扱う。特にfixed componentはforced exit回避のsignalとしては弱く残るため、採用するとしてもPnL主目的のhard gateではなく、候補同点時のtie-breakやmulti-feature stackingの説明変数に留める。

## Artifacts

- timed prefixed OOF: `data/reports/modeling/20260628_175235_candidate_quality_prefixed_timed_component_oof/`
- fixed prefixed OOF: `data/reports/modeling/20260628_175302_candidate_quality_prefixed_fixed_component_oof/`
- final combined prefixed OOF: `data/reports/modeling/20260628_175327_candidate_quality_prefixed_clipped_best_oof/`
- timed gate validation: `data/reports/backtests/candidate_quality_timed_component_quality_gate_validation/`
- fixed gate validation: `data/reports/backtests/candidate_quality_fixed_component_quality_gate_validation/`
- clipped gate validation: `data/reports/backtests/candidate_quality_clipped_best_quality_gate_validation/`
- timed gate summary: `data/reports/backtests/candidate_quality_timed_component_quality_gate_summary/20260628_175700_model_sweep_summary/`
- fixed gate summary: `data/reports/backtests/candidate_quality_fixed_component_quality_gate_summary/20260628_175700_model_sweep_summary/`
- clipped gate summary: `data/reports/backtests/candidate_quality_clipped_best_quality_gate_summary/20260628_175700_model_sweep_summary/`

## Verification

- `PYTHONPATH=src python3 -m unittest tests.test_meta_model`: OK, 29 tests
- `PYTHONPATH=src python3 -m unittest discover -s tests`: OK, 137 tests
- `git diff --check`: OK
