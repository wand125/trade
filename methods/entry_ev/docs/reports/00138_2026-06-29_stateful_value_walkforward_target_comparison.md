# Stateful Value Walk-Forward Target Comparison

日時: 2026-06-29 11:56 JST
更新日時: 2026-06-29 11:56 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻である `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## 目的

`00137` で作成したwalk-forward stress targetを、stateful value modelの教師候補として比較した。

確認したい点:

- 月抜きOOFだけでなく、未来月をfitに含めないexpanding OOFで性能がどう変わるか。
- 元の `target`、available-context floor、session-context floorのどれがEV補正に使えるか。
- policyへ直接接続してよいか、または診断/下方リスクtargetに留めるべきか。

## 実装

`trade_data.meta_model oof-stateful-value-model` にOOF分割方式を追加した。

- `--oof-scheme leave_one_month`: 従来通り、対象月以外の全月でfitする。
- `--oof-scheme expanding`: 対象月より前の月だけでfitする。
- `--min-train-months`: fitに必要な最小月数。満たさないfoldは `skipped` として `fold_plan` に残す。

expanding OOFでは、今回 `--min-train-months 2` としたため、`2024-07` と `2024-09` は学習月不足でskipし、`2024-11` 以降だけを評価対象にした。

## 実行

代表コマンド:

```bash
python3 -m trade_data.meta_model oof-stateful-value-model \
  --examples data/reports/backtests/20260629_024156_stateful_examples_available_context_walkforward_stress/walkforward_stateful_examples.csv \
  --validation-months 2024-07,2024-09,2024-11,2024-12,2025-01,2025-02,2025-03,2025-04 \
  --target-column target \
  --prediction-prefix wf_exp_base \
  --oof-scheme expanding \
  --min-train-months 2 \
  --output-dir data/reports/modeling \
  --label stateful_value_expanding_base_target_compare
```

比較対象:

- `target`
- `target_walkforward_context_stress_adjusted`
- `target_walkforward_context_holdout_mean_floor`
- available context: `candidate_side + combined_regime`
- session context: `candidate_side + combined_regime + session_regime`

## 結果

leave-one-month OOF:

| target | rows | target mean | pred mean | bias | MAE | RMSE | R2 | mean over | lower over | lower coverage |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| base target | 1544 | `+0.6154` | `+0.8876` | `+0.2722` | `8.6349` | `13.2915` | `+0.0052` | `4.4535` | `2.4541` | `0.7468` |
| available stress adjusted | 1544 | `-1.2823` | `-0.4601` | `+0.8223` | `9.5026` | `14.1126` | `-0.0188` | `5.1624` | `2.8795` | `0.7183` |
| available floor | 1544 | `-2.2679` | `-1.5795` | `+0.6885` | `7.4366` | `12.0849` | `-0.0197` | `4.0625` | `2.4500` | `0.7234` |
| session stress adjusted | 1544 | `-0.7835` | `-0.2004` | `+0.5831` | `9.4110` | `14.1090` | `-0.0192` | `4.9970` | `2.9237` | `0.7383` |
| session floor | 1544 | `-1.2457` | `-0.7982` | `+0.4474` | `7.7830` | `12.4475` | `-0.0055` | `4.1152` | `2.5088` | `0.7332` |

expanding OOF:

| target | rows | target mean | pred mean | bias | MAE | RMSE | R2 | mean over | lower over | lower coverage |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| base target | 1220 | `+0.2417` | `+1.7704` | `+1.5287` | `8.9112` | `13.9020` | `-0.0113` | `5.2199` | `2.7244` | `0.7320` |
| available floor | 1220 | `-3.4073` | `+0.7291` | `+4.1365` | `7.3780` | `12.4705` | `-0.0945` | `5.7572` | `3.1176` | `0.6287` |
| session floor | 1220 | `-2.1136` | `+1.0059` | `+3.1195` | `7.8476` | `12.8969` | `-0.0498` | `5.4836` | `2.9585` | `0.6951` |

## Artifacts

- `data/reports/modeling/20260629_024840_stateful_value_wf_base_target_compare/`
- `data/reports/modeling/20260629_024840_stateful_value_wf_available_stress_compare/`
- `data/reports/modeling/20260629_024840_stateful_value_wf_available_floor_compare/`
- `data/reports/modeling/20260629_024925_stateful_value_wf_session_stress_compare/`
- `data/reports/modeling/20260629_024926_stateful_value_wf_session_floor_compare/`
- `data/reports/modeling/20260629_025354_stateful_value_expanding_base_target_compare/`
- `data/reports/modeling/20260629_025355_stateful_value_expanding_available_floor_compare/`
- `data/reports/modeling/20260629_025355_stateful_value_expanding_session_floor_compare/`

## 判断

leave-one-monthではbase targetだけがわずかに正のR2だったが、これは対象月の未来側の月もfitへ入るため、chronologicalな採用判断としては甘い。

expanding OOFではbase targetのR2も `-0.0113` へ落ち、平均予測はtargetより `+1.5287` 高い。available/session floorはMAE/RMSEこそ改善するが、targetを保守的に下げた結果であり、rank能力はさらに悪化した。特にavailable floorはR2 `-0.0945`, bias `+4.1365` で、EV補正としてそのまま使うには過大評価が強い。

したがって、今回のwalk-forward stress/floor targetは、現時点ではpolicyの直接EV replacementやhard gateに使わない。用途は以下に限定する。

- chronological OOFでの過大評価診断
- downside / floor breach の分類target候補
- support-aware calibrationの監査列
- 次の追加データ月で、同じexpanding手順を固定して再評価するtarget候補

## 次の作業

- stateful value target比較は、原則 `--oof-scheme expanding --min-train-months 2` 以上で行う。
- floor targetは回帰EVとして直接使わず、`target <= floor` や `base target - floor target` のような下方リスク分類/校正へ変換して試す。
- 現在の8ヶ月ではsupport不足が強いため、追加月のstateful examplesを増やして、同じfold設計でR2、bias、overestimate、月別coverageが改善するかを見る。
- policy接続へ進む場合は、direct replacementではなく、raw EV primaryを維持したrisk budget/tie-break/soft calibrationとして小さく接続し、必ずholdout preflightを通す。
