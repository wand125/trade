# Entry EV Residual Combo Selected Trade Calibration

日時: 2026-07-02 14:40 JST
更新日時: 2026-07-02 14:40 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00298でdirect confidence hard gateをrejectしたため、00293 residual combo branchのselected tradesだけを対象に、chronological OOFのexpected PnL calibrationを再診断した。
- `scripts/experiments/entry_ev_selected_trade_supervised_shrinkage.py` に `--selector-variants` と `--exclude-entry-blocked` を追加し、entry-block overlay後の採用branchだけを正確に抽出できるようにした。
- 対象月より前の月だけで学習するため、target monthや未来月の実現PnLはfeatureに入らない。
- raw EVは実績平均 `+1.4200` に対してscore平均 `+10.1991` で過大評価が大きい。OOF補正後は factor EV平均 `+0.4363`、PnL EV平均 `+1.0681` まで縮み、MAEも raw `10.7256` から factor `2.9448`、PnL `3.0165` へ改善した。
- ただしrank/gate品質は弱い。Spearmanは factor `0.1329`、PnL `0.1072` に留まり、low-score removalはほぼ標準policyにできない。
- 唯一プラスの低score除去は `pred_supervised_factor_ev < 0` で、31 tradesをflagして `+7.8728` 改善するだけ。loss precision `0.3548`、loss recall `0.1134` と弱い。
- 判断: chronological selected-trade calibration diagnosticsはaccepted infrastructure。直接OOF score hard gateはreject。標準policyはNoTrade。

## Artifacts

- Updated script:
  - `scripts/experiments/entry_ev_selected_trade_supervised_shrinkage.py`
- Updated test:
  - `tests/test_entry_ev_selected_trade_supervised_shrinkage.py`
- Main run:
  - `data/reports/backtests/20260702_053852_20260702_entry_ev_residual_combo_selected_trade_calibration_s1/`

## Target Branch

```text
input trades:
  data/reports/backtests/20260702_043727_20260702_entry_ev_stateful_entry_block_overlay_residual_combo_s1/entry_block_overlay_trades.csv

selector_variant:
  loss_exit30_cd15__holdext_isolated_large_loss_long_t-5_h720__entryblock_short_rollover_or_london_midloss_or_holdext_range_ny

candidate:
  q95_sg95_rank90_floor5_side_regime_session_month

filter:
  --exclude-entry-blocked
```

Selected branch baseline: total `+329.4348`, trades `232`, actual mean `+1.4200`.

## Method

Target:

```text
pnl mode:
  y = adjusted_pnl

factor mode:
  y = adjusted_pnl / pred_taken_ev
  score = pred_taken_ev * predicted_factor
```

Chronological fold:

```text
target month M:
  train = selected unblocked trades with month < M
  test = selected unblocked trades with month == M
```

This keeps the calibration diagnostic aligned with the walk-forward rule. The run had 18 folds, 16 model-used folds, and 232 target rows for each target mode.

## Score Calibration

| mode | score | mean score | bias | MAE | RMSE | Spearman |
|---|---|---:|---:|---:|---:|---:|
| factor | `pred_supervised_factor_ev` | `+0.4363` | `-0.9837` | `2.9448` | `8.1339` | `0.1329` |
| factor | raw EV | `+10.1991` | `+8.7791` | `10.7256` | `13.4134` | `-0.0985` |
| pnl | `pred_supervised_pnl_ev` | `+1.0681` | `-0.3519` | `3.0165` | `8.2377` | `0.1072` |
| pnl | raw EV | `+10.1991` | `+8.7791` | `10.7256` | `13.4134` | `-0.0985` |

Reading:

- scale correctionは有効。raw EVの過大評価は大きく縮む。
- Spearmanはまだ弱い。これは「期待値の絶対値を縮める」ことと「悪いtradeを選別する」ことが別問題であることを示す。
- residual combo branch上でも、scoreをそのままgateにするには不十分。

## Threshold Diagnostics

Low-score removal:

| mode | score | threshold | flagged trades | flagged PnL | kept PnL | delta if removed | loss precision | loss recall |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| factor | `pred_supervised_factor_ev` | `0.0` | `31` | `-7.8728` | `+337.3076` | `+7.8728` | `0.3548` | `0.1134` |
| factor | `pred_supervised_factor_ev` | `-2.0` | `5` | `-0.1850` | `+329.6198` | `+0.1850` | `0.4000` | `0.0206` |
| pnl | `pred_supervised_pnl_ev` | `-2.0` | `2` | `+54.1000` | `+275.3348` | `-54.1000` | weak | weak |
| pnl | `pred_supervised_pnl_ev` | `0.0` | `38` | `+133.3716` | `+196.0632` | `-133.3716` | weak | weak |
| factor | `pred_supervised_factor_ev` | `1.0` | `188` | `+179.5368` | `+149.8980` | `-179.5368` | weak | broad |
| pnl | `pred_supervised_pnl_ev` | `1.0` | `165` | `+219.3162` | `+110.1186` | `-219.3162` | weak | broad |

Reading:

- factor `< 0` は小幅プラスだが、loss precision / recallが弱く、標準gateとしては不十分。
- PnL scoreの低score領域は大きな勝ちtradeを含むため、hard gateにすると悪化する。
- 実用coverageまで広げると、削る集合のPnLがプラスになり、NoTradeに近づけるだけのgateになる。

## Score Bins

| mode | observation |
|---|---|
| factor | lowest binは47 tradesで `+2.8690`、highest binは47 tradesで `+146.1180`。方向性は少しあるがloss rateは単調ではない。 |
| pnl | lowest binが47 tradesで `+144.3950` と強く、low-score gateは明確に勝ちを削る。 |

## Decision

Accepted:

- selected-trade supervised shrinkage scriptのselector-variant filter
- `entry_blocked` exclusion filter
- residual combo branch上のchronological OOF calibration diagnostics
- OOF scale correction as calibration evidence

Rejected:

- direct `pred_supervised_pnl_ev` hard gate
- direct `pred_supervised_factor_ev` hard gate as standard policy
- MAE improvementだけでpolicy improvementとみなすこと

Standard policy remains NoTrade.

## Next

1. Calibration scoreはgateではなく、uncertainty / regime diagnostics / admission explanationへ使う。
2. residual combo branchを標準化するには、未使用chronologyまたはmodel-levelに事前固定された改善理由が必要。
3. low-score hard gateではなく、score uncertainty、support-aware diagnostics、role/month floorを同時に扱うselectorへ進む。
4. NoTrade-first standard gateは維持する。

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_selected_trade_supervised_shrinkage.py tests/test_entry_ev_selected_trade_supervised_shrinkage.py`: OK
- `uv run python -m unittest tests.test_entry_ev_selected_trade_supervised_shrinkage`: OK
- `uv run python -m unittest tests.test_entry_ev_selected_trade_supervised_shrinkage tests.test_entry_ev_confidence_gate_overlay tests.test_entry_ev_month_warmup_overlay tests.test_docs_reports`: OK
- `git diff --check`: OK
- residual combo selected-trade calibration run: OK
