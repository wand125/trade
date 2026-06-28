# Large Loss Threshold Comparison

日時: 2026-06-29 00:22 JST
更新日時: 2026-06-29 00:22 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。

## Summary

`large_loss` trade failure classifierのtarget閾値を `5/10/15` で比較した。

結論:

- OOF分類性能は `threshold=10` が最も良い。`threshold=15` も近いが、`threshold=5` はAUC `0.4042` で逆方向に近い。
- validation 4foldの最悪月PnLも `threshold=10` が最大。
- fixed holdoutでは `threshold=5` が2024-12をプラス化したが、2025-02をマイナスにした。`threshold=10` は2ヶ月合計では最良だが、2024-12はまだNoTrade未満。
- `large_loss` thresholdだけの調整では標準採用に足りない。次は `threshold=10` を基準に、side/regime別校正またはcandidate-entry集合拡張で使う。

## Setup

- Base predictions: HGB entry/side + MLP exit timing hybrid
- Validation months: `2024-07`, `2024-09`, `2024-11`, `2025-01`
- Fixed holdout months: `2024-12`, `2025-02`
- Trade failure target: `large_loss`
- Evaluation multiplier: profit `1.0`, loss `1.20`
- Policy: `timed_ev`
- EV columns: `pred_long_best_adjusted_pnl`, `pred_short_best_adjusted_pnl`
- Risk columns: `pred_trade_failure_large_loss_long_risk`, `pred_trade_failure_large_loss_short_risk`
- Holding columns: `pred_mlp_long_exit_event_minutes`, `pred_mlp_short_exit_event_minutes`
- Max predicted hold: `480` minutes

## OOF Classifier

| large_loss threshold | prevalence | predicted mean | bias | brier | AUC |
|---:|---:|---:|---:|---:|---:|
| 5 | 0.2075 | 0.2052 | -0.0024 | 0.1688 | 0.4042 |
| 10 | 0.1509 | 0.1393 | -0.0116 | 0.1277 | 0.5736 |
| 15 | 0.1132 | 0.1068 | -0.0065 | 0.1008 | 0.5665 |

`threshold=5` は頻度が高すぎ、OOF AUCが0.5を下回る。`threshold=10/15` は薄いが分類信号が残る。Brierだけ見ると低prevalenceの `15` がよく見えるため、AUCと実行policy評価を併用する。

## Validation Top

各thresholdで、eligible候補を `total_adjusted_pnl_min`, `total_adjusted_pnl_sum` の順で選んだ。

| threshold | entry | short offset | side margin | risk penalty | min rank | min pnl | sum pnl | min trades | max DD | forced max | dir error mean | EV over mean | miss smoothed max |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 5 | 10 | 6 | 5 | 10 | 0.0 | 88.8168 | 386.5722 | 24 | 55.5120 | 0.0357 | 0.4037 | 15.4936 | 0.5588 |
| 10 | 12 | 6 | 5 | 10 | 0.5 | 92.8530 | 402.2514 | 24 | 59.5894 | 0.0385 | 0.3746 | 15.6247 | 0.5172 |
| 15 | 12 | 4 | 5 | 30 | 0.5 | 87.4970 | 399.4064 | 24 | 66.6984 | 0.0000 | 0.3844 | 15.8725 | 0.5000 |

validation上は `threshold=10` が最も安定している。`threshold=15` はrisk penalty `30` が必要で、max drawdownが悪い。`threshold=5` はOOF AUCが弱い割にvalidation PnLが出ており、過適合疑いが強い。

## Fixed Holdout

| threshold | month | adjusted pnl | raw pnl | trades | win rate | profit factor | max DD | forced | dir error | EV over | miss smoothed |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 5 | 2024-12 | 22.3498 | 56.8020 | 53 | 0.5660 | 1.1081 | 103.5650 | 3 | 0.6038 | 20.3347 | 0.7818 |
| 5 | 2025-02 | -19.6600 | 37.8170 | 135 | 0.5185 | 0.9430 | 138.8130 | 0 | 0.2741 | 22.7013 | 0.3066 |
| 10 | 2024-12 | -37.2928 | 1.0500 | 52 | 0.5000 | 0.8379 | 99.3530 | 3 | 0.5962 | 22.3784 | 0.7037 |
| 10 | 2025-02 | 76.9254 | 120.6080 | 117 | 0.5128 | 1.2935 | 128.2894 | 0 | 0.4359 | 23.3858 | 0.3782 |
| 15 | 2024-12 | -55.4970 | -22.5220 | 42 | 0.3810 | 0.7195 | 82.9620 | 0 | 0.6429 | 23.5711 | 0.7727 |
| 15 | 2025-02 | 21.5216 | 66.9250 | 100 | 0.5000 | 1.0790 | 109.3348 | 0 | 0.4100 | 23.3474 | 0.4216 |

月別に見ると、どのthresholdも片方の月で崩れる。`threshold=5` は2024-12を救うが2025-02でNoTrade未満、`threshold=15` は2024-12をさらに悪化させる。`threshold=10` は2ヶ月合計では最良だが、2024-12の負けを消せていない。

## Decision

標準policyへ昇格しない。

ただし `threshold=10` の `large_loss` riskは、validationと2ヶ月合計で最も筋がよいので、次の研究の基準信号にする。`threshold=5` はOOF AUCが悪く、fixed holdoutの改善も片月依存なので採用しない。`threshold=15` はsignalがやや薄く、2024-12で悪化するため優先度を下げる。

## Next Actions

- `threshold=10` の `large_loss` probabilityをside/regime別に校正し、全体一律risk penaltyではなく壊れやすい条件だけ減点する。
- 現在の106 selected tradesだけでなく、candidate-entry条件を通った未採用行にもfailure targetを広げ、学習量不足を緩和する。
- fixed holdoutは2024-12/2025-02の両方でNoTrade以上を最低条件にする。片月だけ救う調整は採用しない。

## Artifacts

- t5 model apply: `data/reports/modeling/20260628_150052_trade_failure_large_loss_t5_2024_12/`, `data/reports/modeling/20260628_150052_trade_failure_large_loss_t5_2025_02/`
- t10 model apply: `data/reports/modeling/20260628_144901_trade_failure_hybrid_v1_2024_12/`, `data/reports/modeling/20260628_144901_trade_failure_hybrid_v1_2025_02/`
- t15 model apply: `data/reports/modeling/20260628_150053_trade_failure_large_loss_t15_2024_12/`, `data/reports/modeling/20260628_150053_trade_failure_large_loss_t15_2025_02/`
- t5 validation summary: `data/reports/backtests/trade_failure_large_loss_t5_risk_summary/20260628_151951_model_sweep_summary/`
- t10 validation summary: `data/reports/backtests/trade_failure_large_loss_risk_summary/20260628_145258_model_sweep_summary/`
- t15 validation summary: `data/reports/backtests/trade_failure_large_loss_t15_risk_summary/20260628_151951_model_sweep_summary/`
- t5 fixed tests: `data/reports/backtests/trade_failure_large_loss_t5_risk_fixed_tests/`
- t10 fixed tests: `data/reports/backtests/trade_failure_large_loss_risk_fixed_tests/`
- t15 fixed tests: `data/reports/backtests/trade_failure_large_loss_t15_risk_fixed_tests/`
