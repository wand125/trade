# Trade Failure Classifier Risk

日時: 2026-06-28 23:55 JST
更新日時: 2026-06-28 23:55 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

前回の selected-trade overestimate soft penalty は validation 上だけ改善し、fixed 2024-12 で崩れた。今回は、実行trade単位で失敗の種類を分類target化し、side別failure probabilityをrisk列としてEVから引く基盤を追加した。

結論:

- `oof-trade-failure-model` を追加し、`large_loss`, `wrong_side`, `profit_barrier_miss`, `exit_regret_high`, `any_failure` をOOF分類できるようにした。
- OOF上で使える信号は `large_loss` だけ薄く、AUC `0.5736`。他targetはAUC `0.5` 未満または弱い。
- `large_loss` risk full sweepでは validation 4fold top が min pnl `92.8530`, sum `402.2514` で、同じ骨格の risk `0` min `82.7176`, sum `406.6546` よりfold最低損益を改善した。
- fixed 2024-12は `-54.6032` baselineから `-37.2928` へ改善したが、まだNoTradeを下回る。
- fixed 2025-02は `+81.8334` baselineから `+76.9254` へ少し悪化した。

現時点で標準採用はしない。ただし、過去の回帰penalty群よりは方向性が良く、次は `large_loss` targetの特徴量・threshold・side/regime別校正を改善する。

## Implementation

追加したCLI:

```text
python3 -m trade_data.meta_model oof-trade-failure-model
```

出力列:

```text
pred_trade_failure_<target>_long_prob
pred_trade_failure_<target>_short_prob
pred_trade_failure_<target>_long_risk = -prob
pred_trade_failure_<target>_short_risk = -prob
```

target定義:

| target | definition |
|---|---|
| `large_loss` | `adjusted_pnl <= -large_loss_threshold` |
| `wrong_side` | `direction_error` |
| `profit_barrier_miss` | `actual_taken_profit_barrier_hit < 0.5` |
| `exit_regret_high` | `exit_regret >= exit_regret_threshold` |
| `any_failure` | 上記4targetのOR |

今回の閾値:

- `large_loss_threshold=10`
- `exit_regret_threshold=10`

## OOF Diagnostics

Validation selected trades: `106`

| target | prevalence | predicted mean | bias | brier | AUC |
|---|---:|---:|---:|---:|---:|
| `large_loss` | `0.1509` | `0.1393` | `-0.0116` | `0.1277` | `0.5736` |
| `wrong_side` | `0.3774` | `0.3815` | `0.0041` | `0.2400` | `0.4845` |
| `profit_barrier_miss` | `0.4623` | `0.4576` | `-0.0046` | `0.2548` | `0.4595` |
| `exit_regret_high` | `0.6321` | `0.6339` | `0.0018` | `0.2404` | `0.4566` |
| `any_failure` | `0.8396` | `0.8294` | `-0.0102` | `0.1386` | `0.5284` |

分類確率の平均校正は悪くないが、ranking力は弱い。`large_loss` 以外はそのままriskにしても採用余地は低い。

## Validation Sweep

`large_loss` riskはfull gridで評価した。

| entry | short offset | side margin | risk | min rank | min pnl | sum pnl | min trades | max DD | forced max | EV over realized mean | direction error mean | smoothed miss max |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `12` | `6` | `5` | `10` | `0.5` | `92.8530` | `402.2514` | `24` | `59.5894` | `0.0385` | `15.6247` | `0.3746` | `0.5172` |
| `12` | `6` | `5` | `0` | `0.5` | `82.7176` | `406.6546` | `24` | `60.9864` | `0.0370` | - | - | - |

同じpolicy骨格で、他targetはsmoke sweepのみ実施した。`wrong_side`, `profit_barrier_miss`, `exit_regret_high`, `any_failure` はすべて最良が `risk=0` で、riskを入れるほど悪化した。

## Fixed Holdout

Validation top `large_loss risk=10` を固定適用。

| month | adjusted pnl | raw pnl | trades | PF | max DD | forced | long pnl | short pnl | direction error | EV over realized | smoothed miss |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `2024-12` | `-37.2928` | `1.0500` | `52` | `0.8379` | `99.3530` | `3` | `-9.3964` | `-27.8964` | `0.5962` | `22.3784` | `0.7037` |
| `2025-02` | `76.9254` | `120.6080` | `117` | `1.2935` | `128.2894` | `0` | `41.9000` | `35.0254` | `0.4359` | `23.3858` | `0.3782` |

2024-12は既存hybrid baseline `-54.6032` より改善し、overestimate soft penalty top `-128.2556` より明確に良い。ただしNoTrade `0` にはまだ届かない。2025-02は既存baseline `+81.8334` より少し弱い。

## Decision

- trade failure classifier基盤は残す。
- `large_loss` riskは標準採用保留。明確な改善方向だが、2024-12がまだNoTrade未満で、2025-02を少し削る。
- `wrong_side`, `profit_barrier_miss`, `exit_regret_high`, `any_failure` の単独riskは現時点では採用しない。
- 次は `large_loss` に絞り、以下を試す:
  - threshold `5/10/15` の比較
  - side/regime/session別の校正
  - `large_loss` probabilityを一律EV penaltyではなく、side marginやentry threshold offsetへ反映
  - selected-trade 106件だけでなく、candidate-entry集合へtargetを広げてデータ量を増やす

## Artifacts

- failure model 2024-12 apply: `data/reports/modeling/20260628_144901_trade_failure_hybrid_v1_2024_12/`
- failure model 2025-02 apply: `data/reports/modeling/20260628_144901_trade_failure_hybrid_v1_2025_02/`
- large_loss validation sweeps: `data/reports/backtests/trade_failure_large_loss_risk_validation/`
- large_loss summary: `data/reports/backtests/trade_failure_large_loss_risk_summary/20260628_145258_model_sweep_summary/`
- large_loss fixed tests: `data/reports/backtests/trade_failure_large_loss_risk_fixed_tests/`
- other target smoke sweeps: `data/reports/backtests/trade_failure_*_risk_smoke_validation/`

## Verification

- `PYTHONPATH=src python3 -m unittest tests.test_meta_model`
- `PYTHONPATH=src python3 -m unittest tests.test_docs_reports`
- `PYTHONPATH=src python3 -m trade_data.meta_model --help`
- `PYTHONPATH=src python3 -m trade_data.meta_model oof-trade-failure-model --help`
- `git diff --check`
