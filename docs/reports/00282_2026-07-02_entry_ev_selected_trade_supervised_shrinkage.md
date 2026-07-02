# Entry EV Selected Trade Supervised Shrinkage

日時: 2026-07-02 10:51 JST
更新日時: 2026-07-02 10:51 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00281の次アクションとして、prior capture factorを直接掛けるのではなく、selected raw cd15 trades上でsupervised realized-PnL shrinkageを試した。
- `scripts/experiments/entry_ev_selected_trade_supervised_shrinkage.py` を追加した。対象月より前のselected tradesだけで、`adjusted_pnl` 直接回帰と `adjusted_pnl / pred_taken_ev` factor回帰を学習する。
- 特徴量は予測時点で使える prediction / prior-risk 系に限定した。`adjusted_pnl`, oracle, exit regretなどの実現値はtarget/evaluationにのみ使い、featureには入れない。
- supervised headは scale correctionとしては有効。raw EV MAE `10.3692`、prior capture calibrated EV MAE `3.6264` に対し、supervised factor EV MAE `2.2447`、supervised PnL EV MAE `2.3511` まで改善した。
- ただしrank/gateとしては未達。低score除外はほぼ全てプラスPnL集合を削り、raw benchmark `+118.6900` を改善しない。
- 判断: selected-trade supervised shrinkage infrastructureはaccepted。直接threshold gateはreject。次はこのheadを「特徴量」としてcandidate row / dense side-row側へ戻し、stateful replayで評価する。

## Artifacts

- Script:
  - `scripts/experiments/entry_ev_selected_trade_supervised_shrinkage.py`
- Test:
  - `tests/test_entry_ev_selected_trade_supervised_shrinkage.py`
- Main run:
  - `data/reports/backtests/20260702_015124_20260702_entry_ev_selected_trade_supervised_shrinkage_raw_cd15_s2/`
- Earlier smoke:
  - `data/reports/backtests/20260702_015019_20260702_entry_ev_selected_trade_supervised_shrinkage_raw_cd15_s1/`

## Method

Input:

```text
data/reports/backtests/20260702_011904_20260702_entry_ev_raw_cd15_executable_ev_calibration_on_capture_targets_s1/enriched_executable_ev_calibration.csv
```

Target:

```text
pnl mode:
  y = adjusted_pnl

factor mode:
  y = adjusted_pnl / pred_taken_ev
  clipped to [-1, 1]
  score = pred_taken_ev * predicted_factor
```

Chronological fold:

```text
target month M:
  train = selected trades with month < M
  test = selected trades with month == M
  no future month, no target month labels
```

Model:

```text
HistGradientBoostingRegressor
max_iter=60
learning_rate=0.05
max_leaf_nodes=7
min_samples_leaf=20
l2_regularization=0.10
min_train_months=2
min_train_rows=30
```

Features include:

- `pred_taken_ev`, `pred_opposite_ev`, side confidence, entry rank
- selected MLP exit minutes, loss-first probability, time-exit probability
- predicted fixed-horizon PnL proxies
- direction inversion / replacement / EV overestimate prediction features
- prior exit-capture risk and prior executable capture stats
- family, role, direction, combined regime, session regime, prior risk bucket

Excluded from features:

- realized `adjusted_pnl`
- same-side oracle PnL
- exit regret
- actual capture ratio and failure labels

## Score Calibration

Overall score quality:

| score | mean score | bias | MAE | RMSE | Spearman |
|---|---:|---:|---:|---:|---:|
| raw EV | `10.0967` | `+9.6505` | `10.3692` | `12.2233` | `0.0315` |
| prior capture calibrated EV | `1.1578` | `+0.7116` | `3.6264` | `6.6097` | `-0.0452` |
| supervised PnL EV | `0.2268` | `-0.2194` | `2.3511` | `5.5028` | `0.0935` |
| supervised factor EV | `0.1646` | `-0.2816` | `2.2447` | `5.2871` | `0.1063` |

Reading:

- supervised factor is the best scale correction by MAE/RMSE.
- Spearman remains weak, so ranking quality is not yet sufficient.
- The head learns “how much to shrink” better than “which trades to remove”.

## Threshold Diagnostics

Low-score removal on selected trades:

| score | threshold | flagged trades | flagged pnl | kept pnl | loss precision | loss recall |
|---|---:|---:|---:|---:|---:|---:|
| supervised factor EV | `-2.0` | `1` | `-0.2760` | `+118.9660` | `1.0000` | `0.0082` |
| supervised factor EV | `-1.0` | `17` | `+0.5532` | `+118.1368` | `0.5882` | `0.0820` |
| supervised factor EV | `0.0` | `85` | `+46.2508` | `+72.4392` | `0.4706` | `0.3279` |
| supervised PnL EV | `0.0` | `65` | `+55.2362` | `+63.4538` | `0.5077` | `0.2705` |
| supervised PnL EV | `0.25` | `146` | `+66.3446` | `+52.3454` | `0.4863` | `0.5820` |
| prior capture calibrated EV | `0.0` | `155` | `+43.0344` | `+75.6556` | `0.4581` | `0.5820` |
| prior capture calibrated EV | `2.0` | `229` | `+103.3826` | `+15.3074` | `0.4629` | `0.8689` |

Reading:

- `supervised factor EV < -2.0` は一応 `+0.2760` 改善するが、1 tradeだけで効果が小さすぎる。
- 実用的なcoverageにすると、flagged集合のPnLは大きくプラスになり、勝ちtradeを削る。
- selected-trade post-hocの段階でもgateが弱いので、stateful policyへ直接接続しない。

## Fold Behavior

Key fold observations:

- 2024-01 / 2024-03はprior不足でfallback `0.0`。これは意図通り。
- 2025-11は実現平均 `+4.2981` に対し、supervised PnL EV平均 `-0.6013`、factor EV平均 `-0.1929` と、大勝月を過小評価した。
- 2025-02は実現平均 `-0.5464` に対し、supervised PnL EV平均 `+1.7436`、factor EV平均 `+0.8129` と、負け月を過大評価した。

Reading:

- Scaleは合うが、月/regime単位の方向はまだ不安定。
- 266 selected tradesでは、large positive outlierとsmall lossが混ざり、regimeごとのrank signalを安定して学びにくい。

## Decision

Accepted:

- selected-trade supervised shrinkage diagnostic script
- chronological fold implementation for `pnl` and `factor` targets
- supervised shrinkage as scale-correction evidence

Rejected:

- low supervised EV threshold as direct admission gate
- selected-trade-only shrinkage as policy score replacement
- claiming policy improvement from MAE improvement alone

Standard policy remains NoTrade.

Raw `loss_exit30_cd15` remains the fixed diagnostic benchmark.

## Next

1. Move this head from selected-trade post-hoc into candidate-row or dense side-row feature generation.
2. Keep supervised shrinkage as a feature, not as a standalone score.
3. Combine it with side-support, candidate episode support, and one-position replacement diagnostics before any stateful replay.
4. Consider downside-weighted or quantile loss where large losses get more weight, because ordinary MAE/RMSE improvement did not produce useful removal decisions.

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_selected_trade_supervised_shrinkage.py tests/test_entry_ev_selected_trade_supervised_shrinkage.py`: OK
- `uv run python -m unittest tests.test_entry_ev_selected_trade_supervised_shrinkage`: OK
- selected-trade supervised shrinkage run: OK
