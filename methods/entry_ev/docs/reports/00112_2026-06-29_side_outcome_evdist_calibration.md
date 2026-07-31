# Side Outcome EV Distribution Calibration

日時: 2026-06-29 07:58 JST
更新日時: 2026-06-29 07:58 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻である `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## 目的

`00111` では、side confidenceや既存calibrated EVを単純なsoft補正として使うと、validation改善がholdoutで崩れることを確認した。

今回は、entry方向そのものではなく、候補sideごとの実現EV分布をsupport-awareに校正する。

- side別の予測EV bucket
- side confidence bucket
- `combined_regime`
- `session_regime`

を使い、実現targetの平均、下方信頼値、no-edge確率、large-loss確率、wrong-side確率、EV過大評価riskを出す。OOFでは `dataset_month` を抜いてfitし、scored monthを校正統計に混ぜない。

## 実装

`trade_data.meta_model side-outcome-calibration` を追加した。

主な出力列:

- `pred_side_outcome_evdist_<side>_calibrated_target_mean`
- `pred_side_outcome_evdist_<side>_calibrated_target_lower`
- `pred_side_outcome_evdist_<side>_realized_ev_score`
- `pred_side_outcome_evdist_<side>_conservative_ev_score`
- `pred_side_outcome_evdist_<side>_no_edge_prob`
- `pred_side_outcome_evdist_<side>_large_loss_prob`
- `pred_side_outcome_evdist_<side>_side_win_prob`
- `pred_side_outcome_evdist_<side>_wrong_side_prob`
- `pred_side_outcome_evdist_<side>_ev_overestimate`
- `pred_side_outcome_evdist_<side>_wrong_side_risk`
- `pred_side_outcome_evdist_<side>_ev_overestimate_risk`
- `pred_side_outcome_evdist_<side>_support`
- `pred_side_outcome_evdist_<side>_source`

OOF生成:

- examples rows: `115252`
- prediction rows: `115252`
- OOF folds: `2024-07`, `2024-09`, `2024-11`, `2025-01`
- group columns: `combined_regime,session_regime`
- EV buckets: `10`
- confidence buckets: `5`
- min group support: `30`
- prior strength: `80`
- lower z: `1`
- no-edge threshold: `0`
- large-loss threshold: `-15`

## Validation

固定条件は `00111` の `down5,up10` baseを維持した。

- `policy=timed_ev`
- `entry_threshold=12`
- `short_entry_threshold_offset=6`
- `side_margin=5`
- `min_entry_rank=0.5`
- `max_predicted_hold_minutes=480`
- `side_ev_penalty_rules=short:combined_regime=down_low_vol:5,short:combined_regime=up_low_vol:10`
- `pred_mlp_*_exit_event_minutes`
- loss multiplier `1.20`

まず、side-outcome列を付与したparquetでraw baselineが再現できることを確認した。

| mode | validation sum | validation min | trades | max DD | direction error | EV overestimate |
|---|---:|---:|---:|---:|---:|---:|
| raw | `622.6486` | `138.0338` | `275` | `85.0166` | `0.3943` | `13.8658` |

calibrated EV系の列をそのままEV列へ差し替えると、全てrawを大きく下回った。

| direct replacement | best threshold | validation sum | validation min | trades | max DD |
|---|---:|---:|---:|---:|---:|
| calibrated mean | `12` | `176.2470` | `-116.8952` | `741` | `190.5970` |
| calibrated lower | `10` | `93.4578` | `-134.5354` | `706` | `199.6422` |
| realized score | `10` | `101.9052` | `-147.0078` | `699` | `221.0826` |
| conservative score | `10` | `89.9698` | `-143.4350` | `649` | `217.5064` |

次に、raw EVは維持したまま、side-outcome列を `min_trade_quality` gateとして使った。

| gate | min trade quality | validation sum | validation min | trades | max DD | direction error | EV overestimate |
|---|---:|---:|---:|---:|---:|---:|---:|
| wrong-side risk | `-0.45` | `663.4534` | `148.1228` | `247` | `80.3918` | `0.3712` | `13.3401` |
| conservative score | `0` | `651.9034` | `146.6748` | `270` | `85.0166` | `0.3869` | `13.6647` |
| conservative score | `10` | `678.4180` | `143.8022` | `250` | `63.6762` | `0.3711` | `13.2856` |
| raw | `-inf` | `622.6486` | `138.0338` | `275` | `85.0166` | `0.3943` | `13.8658` |

validationだけを見ると、`wrong_side_risk >= -0.45` は月次下限、direction error、EV overestimateを改善する。合計では `conservative_ev_score >= 10` も強い。

## Holdout

validation全体でfitしたside-outcome統計を、既存holdout `2024-12`, `2025-02`, `2025-03` へ適用した。比較対象はvalidationで有望だった2候補に限定した。

| mode | min trade quality | holdout sum | holdout min | trades | max DD | direction error | EV overestimate |
|---|---:|---:|---:|---:|---:|---:|---:|
| raw | `-inf` | `242.5008` | `-20.8252` | `426` | `122.9852` | `0.5249` | `19.0017` |
| conservative score | `10` | `192.3162` | `-28.4754` | `386` | `122.4052` | `0.5321` | `18.8750` |
| wrong-side risk | `-0.45` | `145.5712` | `-57.7274` | `361` | `119.6508` | `0.5075` | `19.3266` |

月別では、どちらのgateも2024-12を改善できない。

| month | raw | wrong-side risk `>= -0.45` | conservative score `>= 10` |
|---|---:|---:|---:|
| 2024-12 | `-20.8252` | `-57.7274` | `-28.4754` |
| 2025-02 | `179.2484` | `130.5942` | `172.4778` |
| 2025-03 | `84.0776` | `72.7044` | `48.3138` |

## 判断

`side-outcome-calibration` の実装は採用する。OOFで月を抜いた校正列を作れ、診断・特徴量・stacking入力として使える。

ただし、現時点では標準policyのEV差し替えやhard gateには採用しない。

- EV列への直接差し替えはvalidation時点で棄却。
- `wrong_side_risk >= -0.45` はvalidationで最も安定して見えたが、holdoutでrawより悪い。
- `conservative_ev_score >= 10` はvalidation sumが高いが、holdoutではrawより悪い。
- side-outcome統計は単純な閾値より、entry/side/exit modelの入力特徴、candidate rankingの診断、regime別の失敗説明に回す。

次は、side-outcome列を単独gateにせず、追加walk-forward foldまたはstacking modelの入力として扱う。特に2024-12型の失敗は、wrong-side確率だけでなく、direction/session exposure、exit timing、EV過大評価が同時に絡んでいるため、単一risk列の閾値化では不安定になりやすい。

## Artifacts

- OOF predictions: `data/reports/modeling/20260629_side_outcome_evdist_oof/predictions_component_fixed_weighted_side_outcome_oof.parquet`
- OOF metrics: `data/reports/modeling/20260629_side_outcome_evdist_oof/predictions_component_fixed_weighted_side_outcome_oof.metrics.json`
- OOF stats: `data/reports/modeling/20260629_side_outcome_evdist_oof/predictions_component_fixed_weighted_side_outcome_oof.side_outcome_stats.csv`
- validation direct replacement summary: `data/reports/backtests/20260629_side_outcome_evdist_validation_summary.csv`
- validation gate months: `data/reports/backtests/20260629_side_outcome_evdist_gate_validation_months.csv`
- validation gate summary: `data/reports/backtests/20260629_side_outcome_evdist_gate_validation_summary.csv`
- holdout side-outcome predictions: `data/reports/modeling/20260629_side_outcome_evdist_apply/`
- holdout months: `data/reports/backtests/20260629_side_outcome_evdist_holdout_months.csv`
- holdout summary: `data/reports/backtests/20260629_side_outcome_evdist_holdout_summary.csv`

## Verification

- `PYTHONPATH=src python3 -m unittest tests.test_meta_model`: OK
- `PYTHONPATH=src python3 -m unittest tests.test_docs_reports`: OK
- `python3 -m trade_data.meta_model side-outcome-calibration`: OK for OOF validation and holdout apply
- `python3 -m trade_data.backtest model-sweep`: OK for validation and holdout comparisons
