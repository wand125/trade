# Train OOF Calibration With Loss 1.20

日時: 2026-06-28 08:09 JST

## 目的

前回の side/regime EV calibration は validation 4ヶ月だけで補正統計をfitしたため、OOF validationでは強く見えたが fixed test へ汎化しなかった。

今回は train期間のOOF predictionsを作り、各validation foldのcalibration fitに `train OOF + 他validation月` を使う。あわせて、評価倍率を現行標準の profit 1.0 / loss 1.20 に統一する。

## 実装

`trade_data.meta_model oof-group-calibration` に以下を追加した。

- `--base-fit-predictions`
- `--base-fit-months`

各validation holdoutでは、fit側を以下にする。

```text
base train OOF predictions + validation predictions excluding holdout month
```

final test用calibratorは以下でfitする。

```text
base train OOF predictions + all validation predictions
```

また、`trade_data.dataset` と `trade_data.backtest` のデフォルト倍率を profit 1.0 / loss 1.20 に変更した。

## Train OOF

Artifact:

- `experiments/20260627_223559_policy_train_oof_4m_p1_l1p2_regime_purge_e24/`

設定:

- dataset: `data/processed/datasets/xauusd_m1_p1_l1p2`
- train months: `2023-01..2024-06, 2024-08, 2024-10`
- fold-month-count: 4
- target set: `policy`
- max iter: 80
- purge label overlap: true
- embargo hours: 24

OOF結果:

- rows: 546,537
- folds: 5
- selected_trade_count at threshold 15: 79,612
- selected_avg_adjusted_pnl: 17.0821
- selected_side_accuracy: 0.5240

EV系R2は小さい一方、wait_regret系には比較的信号が残った。これは「方向を直接当てる」より「悪いentryを避ける」補助targetにまだ余地があることを示す。

## Calibration Artifacts

Residual offset:

- `experiments/20260627_223950_regime_ev_calib_train_oof4m_vol_session_offset/`

Shrink 0.65:

- `experiments/20260627_224357_regime_ev_calib_train_oof4m_vol_session_shrink065/`

両方とも base fit rows は 546,537、final fit rows は 659,031。

## Loss 1.20 Validation Sweep

共通条件:

- evaluation: profit 1.0 / loss 1.20
- validation months: 2024-07, 2024-09, 2024-11, 2025-01
- policy: `timed_ev`
- fixed test months: 2024-12, 2025-02
- eligibility: 4 folds, 10 trades/fold以上, forced exit 0, max drawdown 150以下, 各fold PnL 0以上

Shrink 0.65 top by min-pnl:

- summary: `data/reports/backtests/20260627_224840_model_sweep_summary/`

| policy | entry | side margin | risk | max wait | min rank | mean pnl | min pnl | min trades | max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| timed_ev | 15 | 2 | 0.05 | 2 | 0 | 49.9715 | 41.1354 | 10 | 35.1396 |

Fixed test:

| candidate | month | adjusted pnl | raw pnl | trades | max DD | long pnl | short pnl |
|---|---|---:|---:|---:|---:|---:|---:|
| shrink065 top-min | 2024-12 | 18.8306 | 25.3280 | 12 | 21.1826 | -12.5294 | 31.3600 |
| shrink065 top-min | 2025-02 | -44.5990 | -31.0630 | 12 | 50.3220 | -5.5990 | -39.0000 |

Shrink 0.65 riskなし参考:

| candidate | month | adjusted pnl | raw pnl | trades | max DD |
|---|---|---:|---:|---:|---:|
| shrink065 risk0 | 2024-12 | -7.9812 | 1.3390 | 15 | 32.1174 |
| shrink065 risk0 | 2025-02 | -36.9516 | -20.7390 | 15 | 47.7840 |

Residual offset top by min-pnl:

- summary: `data/reports/backtests/20260627_225028_model_sweep_summary/`

| policy | entry | side margin | risk | max wait | min rank | mean pnl | min pnl | min trades | max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| timed_ev | 15 | 2 | 0.05 | 2 | 0.5 | 72.3580 | 46.8804 | 15 | 47.0160 |

Fixed test:

| candidate | month | adjusted pnl | raw pnl | trades | max DD |
|---|---|---:|---:|---:|---:|
| offset top-min | 2024-12 | -63.2266 | -44.3980 | 18 | 87.3276 |
| offset top-min | 2025-02 | -44.3740 | -27.6300 | 12 | 61.0320 |

## 判断

loss 1.20へ統一すると数値は改善したが、未知test月でNoTradeを明確に超える状態にはまだ到達していない。

- train OOFをfitに足すことで、前回の過大entryは抑えられた。
- shrink 0.65 は 2024-12 をプラスに戻したが、2025-02 はまだ負ける。
- offset はvalidation平均が高いが、2024-12で崩れやすい。
- 2025-02の損失は少数のshort側失敗に支配されやすい。

現時点の採用候補は `shrink065 top-min` だが、これは「暫定の比較基準」であり、まだ本採用ではない。

## 次

1. 2025-02のshort失敗tradeを分解し、regime/session/entry timingごとの崩れを確認する。
2. exit timing targetを追加し、入った後の手放し方を改善する。
3. train OOFをmonthly foldに細かくするか、walk-forward OOFを作り、calibrationがblocked fold幅に依存していないか確認する。
4. calibration採用基準にtestを使わず、validation OOF上のside別損益・regime別損益・entry数上限を追加する。
