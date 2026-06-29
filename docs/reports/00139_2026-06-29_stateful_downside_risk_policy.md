# Stateful Downside Risk Policy

日時: 2026-06-29 12:11 JST
更新日時: 2026-06-29 12:11 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻である `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## 目的

`00138` ではwalk-forward floor targetを回帰EVとして直接使うのは弱いと判断した。

今回は、同じ情報を下方リスク分類targetへ変換し、chronological OOFで学習できるか、またrisk penaltyとしてpolicyに小さく接続した場合に防御として働くかを確認する。

## 実装

`oof-stateful-risk-model` に以下を追加した。

- `--oof-scheme leave_one_month|expanding`
- `--min-train-months`
- `walkforward_stress_flag`
- `walkforward_stress_adjusted_nonpositive`
- `walkforward_floor_nonpositive`
- `walkforward_floor_lowered`

target定義:

| target | definition |
|---|---|
| `walkforward_stress_flag` | `walkforward_context_stress_flag` |
| `walkforward_stress_adjusted_nonpositive` | `target_walkforward_context_stress_adjusted <= 0` |
| `walkforward_floor_nonpositive` | `target_walkforward_context_holdout_mean_floor <= 0` |
| `walkforward_floor_lowered` | `target_walkforward_context_holdout_mean_floor < target` |

## OOF分類結果

expanding OOFは `--min-train-months 2`。`2024-07`, `2024-09` はskipし、`2024-11` 以降1220例で評価した。

| context | target | prevalence | predicted mean | bias | brier | AUC |
|---|---|---:|---:|---:|---:|---:|
| available | `walkforward_stress_flag` | `0.3254` | `0.0651` | `-0.2603` | `0.2869` | `0.6512` |
| available | `walkforward_stress_adjusted_nonpositive` | `0.5811` | `0.4524` | `-0.1288` | `0.2654` | `0.4983` |
| available | `walkforward_floor_nonpositive` | `0.6516` | `0.4766` | `-0.1751` | `0.2609` | `0.5296` |
| available | `walkforward_floor_lowered` | `0.4115` | `0.1516` | `-0.2599` | `0.3045` | `0.6077` |
| session | `walkforward_stress_flag` | `0.1705` | `0.0547` | `-0.1158` | `0.1534` | `0.6170` |
| session | `walkforward_stress_adjusted_nonpositive` | `0.5426` | `0.4537` | `-0.0889` | `0.2663` | `0.4721` |
| session | `walkforward_floor_nonpositive` | `0.5893` | `0.4785` | `-0.1109` | `0.2613` | `0.4993` |
| session | `walkforward_floor_lowered` | `0.2754` | `0.1051` | `-0.1703` | `0.2181` | `0.6473` |

`stress_flag` と `floor_lowered` はAUC `0.61-0.65` で、stateful value回帰よりはrank signalがある。ただし初期fit月に陽性例が少ないため、predicted meanがprevalenceを大きく下回り、calibrationは弱い。

## Policy接続

8ヶ月のforced predictionを結合し、expanding OOF risk列を付与した。

policy条件:

- policy: `timed_ev`
- entry threshold: `12`
- short offset: `6`
- side margin: `5`
- side EV penalty: `short:combined_regime=down_low_vol:5`, `short:combined_regime=up_low_vol:10`
- holding: `pred_mlp_long_exit_event_minutes`, `pred_mlp_short_exit_event_minutes`
- max holding prediction: `480`
- min entry rank: `0.5`
- MLP holding guard: auto, `min_valid_predicted_hold_minutes=30`
- months: `2024-11`, `2024-12`, `2025-01`, `2025-02`, `2025-03`, `2025-04`

base cost:

| risk signal | penalty | total PnL | min month | trades | max DD | forced |
|---|---:|---:|---:|---:|---:|---:|
| none / baseline | `0` | `543.9972` | `-18.7168` | 517 | `249.9600` | 4 |
| available stress flag | `10` | `538.6306` | `-10.5308` | 495 | `239.2430` | 4 |
| available stress flag | `20` | `424.7458` | `-62.3790` | 463 | `203.4380` | 4 |
| available stress flag | `40` | `263.0912` | `-41.3538` | 395 | `173.5746` | 3 |
| session floor lowered | `10` | `422.1416` | `+8.0320` | 459 | `250.8660` | 4 |
| session floor lowered | `20` | `357.1258` | `-49.7598` | 387 | `265.4276` | 4 |
| session floor lowered | `40` | `15.1552` | `-200.0996` | 294 | `357.2984` | 3 |

high cost (`spread=0.2`, `slippage=0.1`, `delay=1`):

| risk signal | penalty | total PnL | min month | trades | max DD | forced |
|---|---:|---:|---:|---:|---:|---:|
| none / baseline | `0` | `391.2374` | `-34.3748` | 521 | `259.0392` | 4 |
| available stress flag | `10` | `390.2226` | `-34.3748` | 499 | `248.2764` | 4 |
| available stress flag | `20` | `287.3502` | `-96.4634` | 467 | `196.5474` | 4 |
| session floor lowered | `10` | `311.0372` | `-20.8080` | 463 | `251.3494` | 4 |
| session floor lowered | `20` | `227.3016` | `-49.8372` | 391 | `258.2284` | 4 |

`session_floor_lowered risk=10` はbaseで最悪月を `-18.7168 -> +8.0320`、high costで `-34.3748 -> -20.8080` へ改善した。一方で、base合計は `543.9972 -> 422.1416`、high cost合計は `391.2374 -> 311.0372` へ落ちる。

## 判断

`session_floor_lowered` は、今までのstateful risk targetよりは「防御signal」として筋がある。特に、2024-12 / 2025-04 の下振れを削る方向に働いた。

ただし標準採用はしない。

理由:

- calibrationが弱く、predicted meanがprevalenceを大きく下回る。
- `risk=10` は最悪月を改善するが、2025-02 / 2025-03 の利益を大きく削る。
- high costでも最悪月改善は残るが、合計PnLの劣化が大きい。
- `risk=20/40` は月別に崩れ、penalty台地が広くない。

したがって、現時点では標準policyではなく、risk budget / drawdown-aware ranking / candidate selectionの補助特徴として扱う。

## Artifacts

- OOF metrics:
  - `data/reports/modeling/20260629_030513_stateful_risk_expanding_available_downside_compare/`
  - `data/reports/modeling/20260629_030514_stateful_risk_expanding_session_downside_compare/`
- OOF prediction:
  - `data/reports/modeling/20260629_030805_stateful_risk_expanding_available_downside_predictions/`
  - `data/reports/modeling/20260629_030805_stateful_risk_expanding_session_downside_predictions/`
- policy summaries:
  - `data/reports/backtests/20260629_stateful_downside_risk_policy_base/stateful_downside_risk_policy_base_aggregate.csv`
  - `data/reports/backtests/20260629_stateful_downside_risk_policy_highcost/stateful_downside_risk_policy_highcost_aggregate.csv`

## 次の作業

- `session_floor_lowered` を直接penaltyに固定せず、candidate selectionの「最悪月改善を買うが合計PnLを削りすぎない」ranking特徴にする。
- probability calibrationを改善する。初期fit月の陽性不足が強いため、月別prior補正、isotonic/Platt、またはprevalence floorを検討する。
- 追加月で同じexpanding OOFを固定して、AUC `0.64` 前後と最悪月改善が再現するか確認する。
- policy直結する場合は、risk penaltyを単独採用せず、drawdown制約やhigh costを含むselectionで使う。
