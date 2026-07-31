# Selected Trade Quality Overestimate Soft Penalty

日時: 2026-06-28 23:39 JST
更新日時: 2026-06-28 23:39 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

前回は calibrated trade quality を entry EV へ全面置換して失敗した。今回は全面置換ではなく、`raw EV - calibrated quality` を過大評価幅として算出し、既存の `risk_penalty` 機構で部分的にEVから引く soft penalty を試した。

結論:

- codeとして `pred_trade_quality_*_overestimate` と `pred_trade_quality_*_overestimate_risk` を追加した。
- validation 4foldでは `risk_penalty=0.25` が top になり、min pnl `86.9174`, sum pnl `442.9766` と直前hybrid基準 min `81.5352`, sum `396.9782` を上回った。
- しかし fixed holdout 2024-12 で `-128.2556` と大きく崩れ、既存baseline `-54.6032` より悪化した。
- risk `0.10` / `0.50` の代表候補も2024-12で `-222.7318` / `-77.5040`。標準採用しない。

## Implementation

`add_trade_quality_columns` が以下を出力するようにした。

- `pred_trade_quality_long_overestimate`
- `pred_trade_quality_short_overestimate`
- `pred_trade_quality_long_overestimate_risk`
- `pred_trade_quality_short_overestimate_risk`

定義:

```text
overestimate = max(raw_ev - calibrated_trade_quality, 0)
overestimate_risk = -overestimate
```

既存の `model-policy` は `risk_penalty > 0` のとき `EV -= risk_penalty * max(-risk_column, 0)` と処理するため、risk列には負値を入れる。

## Setup

Source:

- validation predictions: `data/reports/modeling/20260628_hgb_mlp_exit_hybrid/predictions_hgb_entry_mlp_exit_oof.parquet`
- validation selected trades: `data/reports/backtests/hybrid_top_trade_quality_validation_trades/`
- 2024-12 apply: `data/reports/modeling/20260628_hgb_mlp_exit_hybrid/predictions_hgb_entry_mlp_exit_2024_12.parquet`
- 2025-02 apply: `data/reports/modeling/20260628_hgb_mlp_exit_hybrid/predictions_hgb_entry_mlp_exit_2025_02.parquet`

Calibration:

- group columns: `session_regime`
- min group size: `5`
- prior strength: `20`
- prediction shrinkage: `0.65`
- selected validation trades: `106`

Sweep:

- policy: `timed_ev`
- EV columns: `pred_long_best_adjusted_pnl`, `pred_short_best_adjusted_pnl`
- risk columns: `pred_trade_quality_long_overestimate_risk`, `pred_trade_quality_short_overestimate_risk`
- risk penalties: `0,0.1,0.25,0.5,0.75,1`
- entry thresholds: `10,12,15,18`
- short offsets: `2,4,6`
- side margins: `3,5,7`
- min entry ranks: `0,0.5`
- max predicted hold: `480`
- evaluation: profit `1.0`, loss `1.20`

## Validation

Top rows:

| entry | short offset | side margin | risk | min rank | eligible | min pnl | sum pnl | min trades | max DD | EV over realized | direction error | max smoothed miss |
|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|
| `12` | `4` | `3` | `0.25` | `0.5` | true | `86.9174` | `442.9766` | `36` | `78.1616` | `15.6220` | `0.3768` | `0.5833` |
| `12` | `6` | `5` | `0.00` | `0.5` | true | `82.7176` | `406.6546` | `24` | `60.9864` | `15.5226` | `0.3809` | `0.5333` |
| `15` | `4` | `5` | `0.00` | `0.5` | true | `81.5352` | `396.9782` | `23` | `60.0744` | `15.6838` | `0.3709` | `0.5000` |
| `12` | `6` | `5` | `0.00` | `0.0` | true | `78.0486` | `390.5404` | `24` | `73.1280` | `15.4211` | `0.3876` | `0.5484` |
| `12` | `2` | `5` | `0.00` | `0.5` | true | `77.7978` | `410.3604` | `28` | `60.9864` | `15.5466` | `0.4285` | `0.5588` |

Risk penalty別best:

| risk | best validation min pnl | sum pnl | note |
|---:|---:|---:|---|
| `0.00` | `82.7176` | `406.6546` | raw EV baseline周辺 |
| `0.10` | `73.0100` | `378.5302` | validation上は弱い |
| `0.25` | `86.9174` | `442.9766` | validation top |
| `0.50` | `20.5766` | `229.6330` | 過度に削る |
| `0.75` | `0.0000` | `54.9400` | trades不足でeligible false |
| `1.00` | `0.0000` | `51.0330` | 全面置換に近くeligible false |

validation上は `0.25` が見えるが、EV overestimate平均は `15.6220` でほぼ改善していない。損益だけが上がっており、失敗原因の直接制御にはなっていない。

## Fixed Holdout

Validation top and risk-level representatives:

| risk | entry | short offset | side margin | month | adjusted pnl | raw pnl | trades | PF | max DD | forced | EV over realized | smoothed miss |
|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `0.10` | `12` | `6` | `3` | 2024-12 | `-222.7318` | `-161.3410` | `72` | `0.3953` | `238.3896` | `2` | `22.5890` | `0.7703` |
| `0.10` | `12` | `6` | `3` | 2025-02 | `60.3844` | `118.3710` | `146` | `1.1736` | `123.6698` | `0` | `22.8052` | `0.3851` |
| `0.25` | `12` | `4` | `3` | 2024-12 | `-128.2556` | `-82.2390` | `67` | `0.5355` | `138.3458` | `1` | `22.1987` | `0.7826` |
| `0.25` | `12` | `4` | `3` | 2025-02 | `43.2518` | `99.1090` | `137` | `1.1291` | `126.0000` | `0` | `23.0575` | `0.4029` |
| `0.50` | `10` | `2` | `3` | 2024-12 | `-77.5040` | `-37.2460` | `59` | `0.6791` | `106.7784` | `0` | `22.2881` | `0.7541` |
| `0.50` | `10` | `2` | `3` | 2025-02 | `3.5048` | `56.5960` | `120` | `1.0110` | `120.8644` | `0` | `23.8394` | `0.3934` |

2024-12ではすべてNoTradeを下回る。特にvalidation topの `risk=0.25` は既存hybrid baseline `-54.6032` より悪い。`risk=0.50` は2024-12損失を少し抑えるが、2025-02をほぼ消してしまう。

## Decision

- selected-trade overestimate soft penaltyは標準policyへ採用しない。
- validationだけなら改善するが、fixed holdoutで2024-12の壊れ方を増幅する。
- `raw_ev - calibrated_quality` は実行tradeの未知月リスクを安定的に表していない。
- 次は回帰的な過大評価幅ではなく、実行trade failureを分類target化する。候補は `large_loss`, `wrong_side`, `profit_barrier_miss`, `exit_regret_high`。
- 分類targetを使う場合も、entry EVを一律に下げるのではなく、side/regime/session/time-of-day別に「どの壊れ方を避けるか」を分ける。

## Artifacts

- calibration 2024-12 apply: `data/reports/modeling/20260628_143330_selected_trade_quality_hybrid_session_p20_overestimate_risk_2024_12/`
- calibration 2025-02 apply: `data/reports/modeling/20260628_143330_selected_trade_quality_hybrid_session_p20_overestimate_risk_2025_02/`
- validation sweeps: `data/reports/backtests/selected_trade_quality_overestimate_soft_penalty_validation/`
- validation summary: `data/reports/backtests/selected_trade_quality_overestimate_soft_penalty_summary/20260628_143730_model_sweep_summary/`
- fixed tests: `data/reports/backtests/selected_trade_quality_overestimate_soft_penalty_fixed_tests/`

## Verification

- `PYTHONPATH=src python3 -m unittest tests.test_meta_model`
- `PYTHONPATH=src python3 -m unittest tests.test_docs_reports`
- `git diff --check`
