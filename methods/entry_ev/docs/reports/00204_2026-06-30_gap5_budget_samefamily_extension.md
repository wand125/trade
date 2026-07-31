# Gap5 Budget Same-Family Extension

日時: 2026-06-30 12:02 JST
更新日時: 2026-06-30 12:02 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00203の次アクションとして、`gap5/budget0` 自体を追加same-family windowへ再探索なしで固定適用した。
- 入力は同一risk列を持つ `2024-11..2025-04` OOF と `2025-05..08` applyを結合した10ヶ月窓。
- 10ヶ月合計では `gap5/budget0` が source p10/replm10 を上回ったが、追加対象の `2025-05..08` だけでは source と baseline の両方に負けた。
- 結論: `gap5/budget0` は強い時期があるが、追加same-family applyで安定しない。標準採用候補からは外し、diagnostic baseline / intervention locatorとして扱う。

## Artifacts

- Holding max baseline: `data/reports/backtests/20260630_025915_20260630_120600_holding_max260_samefamily_2024_11_2025_08/`
- Side drift p10/replm10 source: `data/reports/backtests/20260630_030015_20260630_120800_side_drift_p10_replm10_samefamily_2024_11_2025_08/`
- Short raw-gap budget fixed apply: `data/reports/backtests/20260630_030122_20260630_120900_short_raw_gap_budget_samefamily_2024_11_2025_08/`

Inputs:

- OOF prediction frame: `data/reports/modeling/20260629_132211_stateful_risk_mean_match_session_floor_lowered_apply_2025_09_12/predictions_validation_oof_stateful_risk_model.parquet`
- Apply prediction frames:
  - `data/reports/modeling/20260629_033349_stateful_risk_mean_match_session_floor_lowered_apply_2025_05/predictions_apply_stateful_risk_model.parquet`
  - `data/reports/modeling/20260629_083956_stateful_risk_mean_match_session_floor_lowered_apply_2025_06/predictions_apply_stateful_risk_model.parquet`
  - `data/reports/modeling/20260629_090355_stateful_risk_mean_match_session_floor_lowered_apply_2025_07/predictions_apply_stateful_risk_model.parquet`
  - `data/reports/modeling/20260629_091545_stateful_risk_mean_match_session_floor_lowered_apply_2025_08/predictions_apply_stateful_risk_model.parquet`
- Base config: `data/reports/backtests/20260629_exit_shortening_failure_policy/stateful_p5/20260629_121701_model_timed_ev_2025-01/config.json`
- Data: `data/processed/histdata/xauusd/xauusd_m1.parquet`

## Method

Fixed conditions:

```text
base policy: coststress maxhold 260
source policy: side drift p10 + side EV penalty replacement margin10
short budget hook: signal_short_raw_gap
short_gap_threshold: 0 or 5
context_entry_budget: 0
context columns: dataset_month, combined_regime
profit multiplier: 1.0
loss multiplier: 1.20
```

No threshold, trigger, or context parameter was reselected after seeing `2025-05..08`.

## Aggregate Results

### All 10 months

| variant | months | trades | total PnL | worst month | max DD | short PnL | long PnL |
|---|---:|---:|---:|---:|---:|---:|---:|
| `coststress_maxhold_260` baseline | `10` | `1137` | `+433.3572` | `-26.2112` | `220.9196` | `+141.4032` | `+291.9540` |
| `p10 + replm10` source | `10` | `945` | `+219.9460` | `-102.2830` | `126.8836` | `+13.0454` | `+206.9006` |
| `gap0/budget0` | `10` | `627` | `+273.3682` | `-80.9772` | `117.0906` | `+66.4676` | `+206.9006` |
| `gap5/budget0` | `10` | `777` | `+384.6968` | `-90.5606` | `125.3028` | `+177.7962` | `+206.9006` |

### Additional apply months only: 2025-05..08

| variant | months | trades | total PnL | worst month | max DD | short PnL | long PnL |
|---|---:|---:|---:|---:|---:|---:|---:|
| `coststress_maxhold_260` baseline | `4` | `496` | `+176.8236` | `-24.6998` | `145.7572` | `+63.5560` | `+113.2676` |
| `p10 + replm10` source | `4` | `396` | `+66.7730` | `-102.2830` | `116.4318` | `+37.4170` | `+29.3560` |
| `gap0/budget0` | `4` | `236` | `+57.1198` | `-80.9772` | `117.0906` | `+27.7638` | `+29.3560` |
| `gap5/budget0` | `4` | `293` | `+13.9434` | `-90.5606` | `115.2974` | `-15.4126` | `+29.3560` |

## Monthly Results

| month | baseline | source | gap0/budget0 | gap5/budget0 | gap5-source | gap5-baseline |
|---|---:|---:|---:|---:|---:|---:|
| 2024-11 | `+2.2056` | `-36.9134` | `-50.5156` | `-39.0766` | `-2.1632` | `-41.2822` |
| 2024-12 | `-26.2112` | `-8.8758` | `-24.4834` | `-25.0670` | `-16.1912` | `+1.1442` |
| 2025-01 | `+103.3314` | `+100.0456` | `+64.4292` | `+65.1106` | `-34.9350` | `-38.2208` |
| 2025-02 | `+105.3466` | `+61.5098` | `+64.3340` | `+101.9738` | `+40.4640` | `-3.3728` |
| 2025-03 | `+29.0362` | `-8.8436` | `+22.0142` | `+66.1926` | `+75.0362` | `+37.1564` |
| 2025-04 | `+42.8250` | `+46.2504` | `+140.4700` | `+201.6200` | `+155.3696` | `+158.7950` |
| 2025-05 | `-24.6998` | `-51.7900` | `-28.4484` | `-25.8432` | `+25.9468` | `-1.1434` |
| 2025-06 | `+153.9368` | `+190.3778` | `+144.8634` | `+104.1648` | `-86.2130` | `-49.7720` |
| 2025-07 | `+10.1308` | `+30.4682` | `+21.6820` | `+26.1824` | `-4.2858` | `+16.0516` |
| 2025-08 | `+37.4558` | `-102.2830` | `-80.9772` | `-90.5606` | `+11.7224` | `-128.0164` |

## Interpretation

- `gap5/budget0` の10ヶ月total改善は、主に `2025-03` と `2025-04` の勝ちに依存している。
- 追加applyの `2025-05..08` では、`gap5/budget0` はsourceより `-52.8296`、baselineより `-162.8802` 悪い。
- `gap0/budget0` は追加applyで `gap5/budget0` よりは良いが、sourceより `-9.6532`、baselineより `-119.7038` 悪い。
- したがって、この系列のshort-specific budget hookをさらに積むと、2025内の一部成功期間に過適合する危険が高い。

## Decision

- `gap5/budget0` は標準採用候補から外し、diagnostic baseline / intervention locatorとして残す。
- `triggered profit-miss` も、00203の失敗に続き標準候補に戻さない。
- 次はhookを増やすより、純2024または別regimeの同一risk列を生成し、現在のshort-side drift対策が期間依存かどうかを広く検証する。
- baseline `coststress_maxhold_260` がこの10ヶ月でも追加applyでも最も安定しているため、side drift guard自体の採用前提も再確認する。

## Next

1. 2024-07/09/11/12 などの同一risk列を生成し、純2024内で `gap0/budget0`, `gap5/budget0`, p10/replm10, baselineを再探索なし比較する。
2. 2025系列でこれ以上hookを重ねず、source policy自体のside prediction calibrationとregime別崩れを再評価する。
3. `pred_short_profit_barrier_hit` の0/1列は、calibrated probability化するまでreplacement hookの主要条件に使わない。

## Verification

- Holding max baseline artifact generated: OK
- Side drift p10/replm10 artifact generated: OK
- Short raw-gap budget fixed-apply artifact generated: OK
- `python3 -m unittest tests.test_docs_reports`: OK, 3 tests before writing this report
