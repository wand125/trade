# Validation Stateful Candidate Examples

日時: 2026-06-29 08:49 JST
更新日時: 2026-06-29 08:49 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻である `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## 目的

`00116` で作った `stateful_candidate_examples.csv` を、代表validation 4ヶ月でも作る。

smokeの2024-12/2025-03だけでは教師として少なすぎるため、validation OOF predictionから同じ形式の候補例を作り、次の `stateful_entry_value` model の教師候補にする。

## 条件

固定条件:

- predictions: `data/reports/modeling/20260628_230654_20260629_side_outcome_stack_fixed_component/predictions_validation_oof_candidate_quality_model.parquet`
- months: `2024-07`, `2024-09`, `2024-11`, `2025-01`
- policy: `timed_ev`
- entry threshold: `12`
- short entry threshold offset: `6`
- side margin: `5`
- min entry rank: `0.5`
- max predicted hold minutes: `480`
- loss multiplier: `1.2`
- side EV penalty: `short:combined_regime=down_low_vol:5`, `short:combined_regime=up_low_vol:10`
- raw policy: no quality gate
- candidate policy: `min_trade_quality=0`

candidate quality columns:

- `pred_candidate_quality_side_outcome_stack_fixed_long_adjusted_pnl`
- `pred_candidate_quality_side_outcome_stack_fixed_short_adjusted_pnl`

## Artifacts

- raw policy runs: `data/reports/backtests/stateful_examples_validation_raw/`
- stack0 policy runs: `data/reports/backtests/stateful_examples_validation_stack0/`
- trade delta: `data/reports/backtests/20260628_234917_stateful_candidate_examples_validation/`
- calibration report: `data/reports/modeling/20260628_234926_stateful_candidate_examples_validation_report/`

## Policy Delta

| month | raw pnl | stack0 pnl | delta | raw trades | stack0 trades |
|---|---:|---:|---:|---:|---:|
| 2024-07 | `198.1782` | `180.1820` | `-17.9962` | `65` | `61` |
| 2024-09 | `138.0338` | `178.1816` | `40.1478` | `70` | `59` |
| 2024-11 | `142.8264` | `148.8660` | `6.0396` | `73` | `72` |
| 2025-01 | `143.6102` | `165.8558` | `22.2456` | `67` | `62` |

4ヶ月合計ではstack0がrawを上回る。ただし、これは `min_trade_quality=0` hard gateを採用する根拠ではなく、stateful teacherを作るための候補政策として使う。

## Stateful Target Distribution

`stateful_candidate_examples.csv` は254行。

| month | candidate count | target mean | stateful positive-cost mean | blocking cost sum | positive blocking cost sum |
|---|---:|---:|---:|---:|---:|
| 2024-07 | `61` | `1.7275` | `0.9045` | `125.0090` | `125.0090` |
| 2024-09 | `59` | `3.3118` | `2.2145` | `47.5270` | `47.5270` |
| 2024-11 | `72` | `2.7154` | `2.0676` | `0.0000` | `0.0000` |
| 2025-01 | `62` | `1.8779` | `1.3976` | `79.2040` | `79.2040` |

validationでは平均targetは正。smoke holdoutの2025-03ほど壊れていないが、blocking costは2024-07と2025-01で大きい。

## Raw EV Calibration

`candidate-quality-report` を `target=stateful_entry_value`, raw/mean/lower predictionを全て `pred_taken_ev` として実行した。

overall:

| metric | value |
|---|---:|
| support | `254` |
| target mean | `2.4123` |
| target std | `11.9569` |
| target median | `1.3995` |
| raw predicted mean | `16.4274` |
| raw bias | `14.0151` |
| raw overestimate mean | `15.0311` |
| mean MAE | `16.0471` |
| target rate <= 0 | `0.3976` |
| raw pred rate <= 0 | `0.0000` |

validationでも raw EV はstateful targetに対して平均 `14.0151` 過大評価。候補targetの平均は正でも、約4割は `target <= 0` であり、EVが低い候補を明示的に見送る校正が必要。

## Regime Notes

特に注意する候補:

- 2024-07 `only_candidate long`: support `26`, target mean `-0.3622`, raw bias `14.1305`, target rate `<=0` は `0.5385`
- 2024-11 `only_candidate long`: support `1`, target `-29.2800`, raw bias `43.9894`
- 2024-11 `only_candidate short`: support `3`, target mean `-7.4572`, raw bias `36.0286`
- 2025-01 `only_candidate long`: support `31`, target mean `1.6802`, raw bias `12.9058`

`only_candidate` 全体が常に悪いわけではない。2024-09と2025-01では `only_candidate` の平均targetも正。したがって hard block ではなく、候補ごとのstateful valueを推定してranking / EV補正に使うべき。

## 判断

代表validation 4ヶ月の `stateful_candidate_examples.csv` を、次の教師候補として採用する。

次の実験:

1. `stateful_candidate_examples.csv` を月抜きOOFで学習するCLIを作る。
2. targetはまず `stateful_entry_value` とし、補助targetとして `stateful_positive_cost_value`, `blocking_cost`, `positive_blocking_cost` を併用する。
3. raw `pred_taken_ev` とのgap、side/regime、decision hour、side confidence、side-outcome/component quality列を特徴量に使う。
4. 出力を hard gate ではなく `stateful_value_adjusted_ev = raw_ev + calibrated_stateful_delta` または ranking tie-break として検証する。
5. 検証はvalidation OOF内の月抜き、既存holdout 2024-12/2025-02/2025-03、後続未使用月の順に行う。

過学習対策:

- 学習・評価の採番と最新判断は、必ずレポートファイル内の作成時刻 `日時` を使う。
- `updated time` やファイルシステムのmtimeは使わない。
- 候補数が254行と少ないため、深いモデルの前にHGB / regularized linear / small MLPを比較し、support不足のgroupではshrinkageを入れる。
- target平均だけで採用せず、月別min、`target<=0` 率、raw EV過大評価、holdout崩れを同時に見る。
