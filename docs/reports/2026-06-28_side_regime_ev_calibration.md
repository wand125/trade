# Side/Regime EV Calibration

日付: 2026-06-28 JST

## 目的

hard regime gate は損失回避のablationとしては有用だったが、採用policyとしては月間regime差に弱かった。次に、特定regimeを完全に消すのではなく、side/regime別に予測EVを補正し、予測EVの過大評価を抑える。

## 実装

`trade_data.meta_model` に side/regime EV calibration を追加した。

CLI:

```bash
python3 -m trade_data.meta_model oof-group-calibration \
  --validation-predictions experiments/20260627_215123_policy_iter80_p1_l1p2_regime_purge_e24_v2/predictions_valid.parquet \
  --test-predictions experiments/20260627_215123_policy_iter80_p1_l1p2_regime_purge_e24_v2/predictions_test.parquet \
  --validation-months 2024-07,2024-09,2024-11,2025-01 \
  --test-months 2024-12,2025-02 \
  --group-columns volatility_regime,session_regime
```

出力列:

- `pred_regime_calibrated_long_best_adjusted_pnl`
- `pred_regime_calibrated_short_best_adjusted_pnl`

設計:

- sideごとに補正する。
- groupは `volatility_regime,session_regime` を初期値にした。
- validation OOFでは、各validation月をholdoutし、残りのvalidation月でcalibratorをfitする。
- testにはvalidation全体でfitしたcalibratorを固定適用する。
- testを使ったfit/選択はしない。

補正式:

```text
calibrated_ev = target_mean_group + prediction_shrinkage * (pred_ev - pred_mean_group)
```

group統計はside全体統計へempirical Bayes的にshrinkする。

```text
weight = group_count / (group_count + prior_strength)
```

## 検証

```bash
python3 -m unittest tests.test_meta_model
python3 -m trade_data.meta_model oof-group-calibration --help
git diff --check
```

結果:

- `tests.test_meta_model`: 11 tests OK。
- CLI help OK。
- diff check OK。

## Experiment 1: Shrink to Group Mean

設定:

- group columns: `volatility_regime,session_regime`
- min group size: 500
- prior strength: 2000
- prediction shrinkage: 0.65

Artifact:

- `experiments/20260627_221255_regime_ev_calib_vol_session/`
- summary: `data/reports/backtests/20260627_221441_model_sweep_summary/`

OOF validation top eligible:

| policy | entry | side margin | risk | wait | rank | mean pnl | min pnl | min trades | max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| timed_ev | 18 | 2 | 0.05 | 4 | 0.5 | 63.4787 | 13.9340 | 28 | 82.0904 |

Fixed test:

| month | adjusted pnl | raw pnl | trades | max DD |
|---|---:|---:|---:|---:|
| 2024-12 | -260.2992 | -195.3700 | 48 | 278.2292 |
| 2025-02 | -6.6830 | 39.6730 | 50 | 121.0910 |

## Experiment 2: Residual Offset

設定:

- group columns: `volatility_regime,session_regime`
- min group size: 500
- prior strength: 2000
- prediction shrinkage: 1.0

これはgroup平均へ強く圧縮せず、group別の平均残差だけを補正する。

Artifact:

- `experiments/20260627_221536_regime_ev_calib_vol_session_offset/`
- summary: `data/reports/backtests/20260627_221737_model_sweep_summary/`

OOF validation top eligible:

| policy | entry | side margin | risk | wait | rank | mean pnl | min pnl | min trades | max DD |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| timed_ev | 18 | 0 | 0 | 4 | 0 | 102.5949 | 73.6080 | 54 | 77.3132 |

Fixed test:

| candidate | month | adjusted pnl | raw pnl | trades | max DD |
|---|---|---:|---:|---:|---:|
| top OOF | 2024-12 | -185.8364 | -115.5420 | 141 | 229.0912 |
| top OOF | 2025-02 | -65.1476 | 7.3730 | 165 | 129.4326 |
| conservative OOF | 2024-12 | -149.2616 | -105.5120 | 33 | 188.8472 |
| conservative OOF | 2025-02 | -10.7646 | 31.2660 | 34 | 156.8810 |

conservative OOF:

```text
entry=20
side_margin=5
risk=0
max_wait_regret=4
min_entry_rank=0.5
```

## 判断

side/regime EV calibration は実装としては有用だが、今回の採用候補としては失敗。

- OOF validationでは大きく改善する。
- しかし fixed test では raw EVの前回候補 2024-12 `-35.7010`, 2025-02 `-47.6716` より悪化した。
- calibrated EVはtestでentry数を増やしすぎる。
- OOF validationで見えたregime補正が、2024-12/2025-02の未知regimeへ汎化していない。
- test selection accuracyも悪く、calibrationが方向判断を改善していない。

したがって、現時点では `pred_regime_calibrated_*` を採用policyには使わない。

## 次

1. validation 4ヶ月だけでcalibrationを学ぶのは弱い。train期間にもOOF predictionsを作り、calibration fit用の月数を増やす。
2. calibrationの採用基準に「OOF validationで良い」だけでなく、entry数の上限、fold間trade分布、regime別direction accuracyを入れる。
3. hard/soft gateやcalibrationの前に、exit timing targetの改善を優先する。今回もentry後の保持・決済が損失を拡大している。
