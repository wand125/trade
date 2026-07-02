# Entry EV Calibration Residual Context Diagnostics

日時: 2026-07-02 14:51 JST
更新日時: 2026-07-02 14:51 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00299でOOF calibrationはscale補正に有効だがdirect gateには弱いと分かったため、calibration residualをcontext / support / score binへ分解した。
- `scripts/experiments/entry_ev_selected_trade_calibration_diagnostics.py` を追加し、selected-trade OOF predictionsからmode別score、bias、MAE、overestimate、loss rate、large loss、train supportをCSV化できるようにした。
- 対象は00299 residual combo selected-trade calibration artifact。
- 危険contextは明確に出た。`short|ny_late` は17 trades / total `-13.0136`、pnl bias `+2.4593`、factor bias `+1.4369`、large loss 5件。`long|range_normal_vol|ny_overlap` は9 trades / total `-12.5040`、overestimate rate `0.8889`、train rows平均 `160.8`、train months平均 `11.8`。
- 重要なのは、悪いcontextが単純なsupport不足ではないこと。`long|range_normal_vol|ny_overlap` は全件model-usedでsupportも十分なのに外している。
- score binでも、PnL scoreの最低binは total `+144.3950` と強く、low-score gateが勝ちを削る理由が再確認された。raw EV最高binも total `+3.9402` しかなく、raw high EVは高品質subsetではない。
- 判断: calibration residual context diagnosticsはaccepted infrastructure。context別のpost-hoc static blacklistはreject。次はprior-only context residual pressure / uncertainty headとしてchronologicalに戻す。

## Artifacts

- New script:
  - `scripts/experiments/entry_ev_selected_trade_calibration_diagnostics.py`
- New test:
  - `tests/test_entry_ev_selected_trade_calibration_diagnostics.py`
- Main run:
  - `data/reports/backtests/20260702_055101_20260702_entry_ev_residual_combo_calibration_residual_diagnostics_s1/`

## Input

```text
data/reports/backtests/20260702_053852_20260702_entry_ev_residual_combo_selected_trade_calibration_s1/selected_trade_supervised_shrinkage_predictions.csv
```

Rows:

```text
232 selected trades x 2 supervised target modes = 464 rows
target modes: pnl, factor
```

## Overall

| mode | total | mean actual | mean score | bias | MAE | RMSE | Spearman | loss rate | large losses |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| factor | `+329.4348` | `+1.4200` | `+0.4363` | `-0.9837` | `2.9448` | `8.1339` | `0.1329` | `0.4181` | `23` |
| pnl | `+329.4348` | `+1.4200` | `+1.0681` | `-0.3519` | `3.0165` | `8.2377` | `0.1072` | `0.4181` | `23` |

Reading:

- raw EVよりscaleは良いが、large-loss contextの識別は弱い。
- `factor` は平均的に保守的、`pnl` は一部contextで過大評価が残る。
- どちらも直接gateとしては不十分。

## Worst Contexts

Direction / session:

| mode | context | trades | total | bias | MAE | loss rate | large losses | overestimate rate | train rows | train months |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| pnl | `short|ny_late` | `17` | `-13.0136` | `+2.4593` | `3.3837` | `0.5882` | `5` | `0.7059` | `91.1` | `5.8` |
| factor | `short|ny_late` | `17` | `-13.0136` | `+1.4369` | `2.4682` | `0.5882` | `5` | `0.7059` | `91.1` | `5.8` |

Direction / combined regime / session:

| mode | context | trades | total | bias | MAE | loss rate | large losses | overestimate rate | train rows | train months |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| pnl | `long|range_normal_vol|ny_overlap` | `9` | `-12.5040` | `+2.6618` | `3.0046` | `0.6667` | `3` | `0.8889` | `160.8` | `11.8` |
| factor | `long|range_normal_vol|ny_overlap` | `9` | `-12.5040` | `+2.1141` | `2.4988` | `0.6667` | `3` | `0.8889` | `160.8` | `11.8` |
| pnl | `short|range_low_vol|asia` | `5` | `-6.5482` | `+2.4666` | `3.0640` | `0.6000` | `1` | `0.8000` | `73.8` | `4.8` |
| factor | `short|range_low_vol|asia` | `5` | `-6.5482` | `+1.6198` | `3.2474` | `0.6000` | `1` | `0.6000` | `73.8` | `4.8` |
| pnl | `short|up_low_vol|ny_late` | `4` | `-5.4264` | `+1.1750` | `1.9234` | `0.5000` | `1` | `0.5000` | `108.3` | `6.3` |
| factor | `short|up_low_vol|ny_late` | `4` | `-5.4264` | `+0.9547` | `2.1543` | `0.5000` | `1` | `0.5000` | `108.3` | `6.3` |

Reading:

- `short|ny_late` はdirection/sessionの広い単位で悪い。
- `long|range_normal_vol|ny_overlap` はsupportが十分でも悪く、追加データだけではなくcontext-conditioned calibration / uncertaintyが必要。
- `short|range_low_vol|asia` はsupportがやや薄く、support-aware残差として扱う余地がある。

## Bin Diagnostics

Score bins:

| mode | bin | score range | trades | total | bias | MAE | loss rate | large losses |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| factor | q0 | `-3.8064..0.0000` | `47` | `+2.8690` | `-0.5808` | `1.4794` | `0.3617` | `2` |
| factor | q4 | `+0.9281..+3.1929` | `47` | `+146.1180` | `-1.4329` | `5.1875` | `0.3191` | `6` |
| pnl | q0 | `-2.8160..0.0000` | `47` | `+144.3950` | `-3.4970` | `4.7201` | `0.3830` | `4` |
| pnl | q4 | `+1.8658..+11.0498` | `47` | `+88.0296` | `+2.4399` | `4.5951` | `0.3617` | `7` |

Support bins:

| mode | support bin | trades | total | bias | MAE | loss rate | large losses |
|---|---|---:|---:|---:|---:|---:|---:|
| factor | train rows `121-240` | `109` | `+277.7508` | `-1.9771` | `4.3607` | `0.3761` | `12` |
| pnl | train rows `121-240` | `109` | `+277.7508` | `-0.6808` | `4.4359` | `0.3761` | `12` |
| factor | train rows `61-120` | `57` | `+18.0234` | `+0.2445` | `2.0618` | `0.5088` | `7` |
| pnl | train rows `61-120` | `57` | `+18.0234` | `+0.3621` | `2.2034` | `0.5088` | `7` |

Reading:

- PnL scoreの低score binが強いので、direct low-score gateはやはり不適。
- raw EV highest binはtotal `+3.9402` しかなく、raw high EVも高品質subsetではない。
- supportが大きいbinでもlarge lossは残る。support不足だけでは説明できない。

## Decision

Accepted:

- calibration residual context diagnostics
- mode-specific calibration residual summary
- score / support / context bin diagnostics

Rejected:

- `short|ny_late` や `long|range_normal_vol|ny_overlap` のpost-hoc static blacklist
- support不足だけでcalibration failureを説明すること
- score binの良し悪しをそのままadmission ruleにすること

Standard policy remains NoTrade.

## Next

1. context residualを同じwindow内のblacklistではなく、prior-only context residual pressureとして作る。
2. `short|ny_late` と `long|range_normal_vol|ny_overlap` は次のresidual-risk targetの監査対象にする。
3. uncertainty headを作るなら、score平均だけでなくresidual dispersion / large-loss rateを予測する。
4. calibration改善は必ずrole/month floor、side share、NoTrade-first gateへ戻して評価する。

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_selected_trade_calibration_diagnostics.py tests/test_entry_ev_selected_trade_calibration_diagnostics.py`: OK
- `uv run python -m unittest tests.test_entry_ev_selected_trade_calibration_diagnostics`: OK
- `uv run python -m unittest tests.test_entry_ev_selected_trade_calibration_diagnostics tests.test_entry_ev_selected_trade_supervised_shrinkage tests.test_docs_reports`: OK
- `git diff --check`: OK
- calibration residual context diagnostics run: OK
