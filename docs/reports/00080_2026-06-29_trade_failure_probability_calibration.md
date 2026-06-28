# Trade Failure Probability Calibration

日時: 2026-06-29 00:45 JST
更新日時: 2026-06-29 00:45 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。

## Summary

`large_loss_threshold=10` のfailure probabilityを、side/regime別の実測失敗率でOOF校正する基盤を追加した。

結論:

- `oof-trade-failure-calibration` CLIを追加し、既存の `oof-trade-failure-model` artifactから校正済みprob/risk列を作れるようにした。
- OOF分類指標では `combined_regime` と `volatility_regime+session_regime` がraw AUCを少し上回った。
- しかし実行policyでは、`combined_regime` full gridの上位がrisk `0` に戻り、raw t10 risk topを超えなかった。
- `volatility_regime+session_regime` の軽量smokeでも、calibrated/upper riskはfold最低PnLを改善しなかった。
- fixed holdout診断では `vol_session calibrated risk=30` が2024-12 `-159.2242` と大きく崩れた。

したがって、今回のside/regime probability calibration riskは標準採用しない。実装は診断基盤として残し、次は selected trades 106件だけでなく candidate-entry集合へfailure targetを広げる。

## Implementation

追加した主な列:

- `pred_trade_failure_<target>_<side>_calibrated_prob`
- `pred_trade_failure_<target>_<side>_calibrated_risk`
- `pred_trade_failure_<target>_<side>_upper_prob`
- `pred_trade_failure_<target>_<side>_upper_risk`
- `pred_trade_failure_<target>_taken_calibrated_prob`

CLI:

```bash
python3 -m trade_data.meta_model oof-trade-failure-calibration
```

校正はvalidation月ごとに当該月を抜いてfitする。これにより、validation OOF predictionsにも未来月のfailure実績を混ぜない。

## OOF Calibration Metrics

Target: `large_loss`, threshold `10`

| calibration group | raw AUC | calibrated AUC | raw brier | calibrated brier | calibrated bias |
|---|---:|---:|---:|---:|---:|
| side only | 0.5736 | 0.4444 | 0.1277 | 0.1341 | 0.0047 |
| session | 0.5736 | 0.4618 | 0.1277 | 0.1353 | 0.0047 |
| combined | 0.5736 | 0.5799 | 0.1277 | 0.1322 | 0.0080 |
| vol+session | 0.5736 | 0.5837 | 0.1277 | 0.1292 | 0.0026 |

分類指標だけなら `vol+session` が最も良い。ただしBrierはrawより悪化しており、実行policyでの確認が必要。

## Validation Policy

Raw t10 full grid top:

| risk source | entry | short offset | side margin | risk | min rank | min pnl | sum pnl | min trades | max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| raw t10 | 12 | 6 | 5 | 10 | 0.5 | 92.8530 | 402.2514 | 24 | 59.5894 |

`combined_regime` calibrated full grid top:

| risk source | entry | short offset | side margin | risk | min rank | min pnl | sum pnl | min trades | max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| combined calibrated | 12 | 6 | 5 | 0 | 0.5 | 82.7176 | 406.6546 | 24 | 60.9864 |
| combined calibrated | 15 | 4 | 5 | 0 | 0.5 | 81.5352 | 396.9782 | 23 | 60.0744 |
| combined calibrated | 10 | 2 | 5 | 15 | 0.5 | 75.9550 | 413.4622 | 33 | 72.7702 |

上位がrisk `0` に戻ったため、校正risk自体はvalidationで選ばれていない。

`volatility_regime+session_regime` はraw top骨格だけでsmokeした。

| risk source | risk | min pnl | sum pnl | min trades | max DD | direction error | EV over mean |
|---|---:|---:|---:|---:|---:|---:|---:|
| vol+session calibrated | 0 | 82.7176 | 406.6546 | 24 | 60.9864 | 0.3809 | 15.5226 |
| vol+session calibrated | 30 | 62.7122 | 523.2990 | 33 | 96.6156 | 0.3389 | 14.7756 |
| vol+session upper | 30 | 56.3212 | 407.3920 | 26 | 111.6032 | 0.3546 | 14.5928 |

`risk=30` はsum pnlと一部diagnosticを改善するが、fold最低PnLとmax drawdownが悪化する。採用基準の中心である「最悪月を守る」には合わない。

## Fixed Holdout Smoke

`vol+session calibrated risk=30` を診断としてfixed holdoutへ適用した。

| month | adjusted pnl | raw pnl | trades | profit factor | max DD | forced | direction error | EV over mean | miss smoothed |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2024-12 | -159.2242 | -106.3830 | 88 | 0.4978 | 167.1972 | 2 | 0.5000 | 20.5781 | 0.6000 |
| 2025-02 | -0.4302 | 55.8010 | 126 | 0.9987 | 55.9926 | 0 | 0.5000 | 23.5382 | 0.6016 |

2024-12を大きく壊すため棄却する。

## Decision

- `oof-trade-failure-calibration` は残す。
- 今回の `large_loss` side/regime calibrated riskは標準採用しない。
- OOF分類AUCの改善だけでは採用しない。実行policyのfold最低PnLとfixed holdoutを優先する。
- 次はprobability校正ではなく、candidate-entry集合へfailure targetを広げて学習量を増やす。実行trade 106件だけではgroup校正が不安定。

## Artifacts

- calibration models: `data/reports/modeling/20260628_153210_trade_failure_large_loss_calibration_side_only_2024_12/`, `data/reports/modeling/20260628_153221_trade_failure_large_loss_calibration_session_2024_12/`, `data/reports/modeling/20260628_153237_trade_failure_large_loss_calibration_combined_2024_12/`, `data/reports/modeling/20260628_153253_trade_failure_large_loss_calibration_vol_session_2024_12/`
- combined validation full grid: `data/reports/backtests/trade_failure_large_loss_calibration_validation/combined_calibrated/`
- combined summary: `data/reports/backtests/trade_failure_large_loss_calibration_summary/combined_calibrated/20260628_154339_model_sweep_summary/`
- vol+session smoke: `data/reports/backtests/trade_failure_large_loss_calibration_smoke/`
- vol+session smoke summary: `data/reports/backtests/trade_failure_large_loss_calibration_smoke_summary/`
- fixed smoke: `data/reports/backtests/trade_failure_large_loss_calibration_fixed_smoke/vol_session_calibrated_risk30/`
