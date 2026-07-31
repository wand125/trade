# Online Context Feature Model

日時: 2026-06-30 08:08 JST
更新日時: 2026-06-30 08:08 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- `scripts/experiments/online_context_feature_model.py` を追加した。
- `enriched_context_state_trades.csv` を使い、base特徴のみ vs base + online context state特徴の chronological OOF classifier を比較した。
- targetは `nonpositive` と `large_loss(adjusted_pnl <= -15)`。
- target月は学習に使わず、risk filterの閾値も過去月のtrain score quantileから決める。
- 結論: online context stateは後半の損失塊をpost-filterで削る診断力はあるが、単純に特徴量として足すとOOF AUCは悪化した。標準featureには昇格しない。

重要な制約:

- risk filterは実行済みtradeを後から削る診断であり、一玉制約下のreplacement tradeを再現しない。
- よってpolicy採用判断ではなく、「この特徴が損失tradeを説明するか」の前処理診断として読む。

## Artifacts

- Script: `scripts/experiments/online_context_feature_model.py`
- Test: `tests/test_online_context_feature_model.py`
- min4 run: `data/reports/modeling/20260629_230759_online_context_feature_model_p10_margin10_min4/`
- min8 run: `data/reports/modeling/20260629_230819_online_context_feature_model_p10_margin10_min8/`

Input:

- `data/reports/backtests/20260629_223949_online_context_state_side_month_p10_margin10/enriched_context_state_trades.csv`

## Feature Sets

`base`:

- side, entry margin, selected/opposite predicted score, score gap,
- side probability,
- decision hour,
- direction / combined regime / session regime.

`context`:

- all `base` features,
- `prior_context_pnl`, `prior_context_trade_count`, `prior_context_win_rate`,
- `prior_side_month_pnl`, `prior_side_month_trade_count`,
- `minutes_since_context_last_exit`,
- active/ever breach flags for `20/40/60`,
- minutes since breach,
- context PnL / trade count / entry margin buckets.

## OOF Metrics

### min_train_months=4

Scored months: 2025-05..2025-12, 569 trades, baseline PnL `-356.7940`.

| feature set | target | trades | prevalence | predicted mean | brier | AUC |
|---|---|---:|---:|---:|---:|---:|
| base | nonpositive | `569` | `0.5062` | `0.4521` | `0.2629` | `0.5622` |
| base | large_loss | `569` | `0.0703` | `0.0569` | `0.0674` | `0.5810` |
| context | nonpositive | `569` | `0.5062` | `0.4436` | `0.2707` | `0.5517` |
| context | large_loss | `569` | `0.0703` | `0.0459` | `0.0667` | `0.5606` |

Post-filter diagnostic top:

| feature set | target | train quantile | kept trades | baseline PnL | kept PnL | delta |
|---|---|---:|---:|---:|---:|---:|
| base | nonpositive | `0.70` | `440/569` | `-356.7940` | `-8.9092` | `+347.8848` |
| context | large_loss | `0.70` | `348/569` | `-356.7940` | `-36.8202` | `+319.9738` |
| context | large_loss | `0.90` | `492/569` | `-356.7940` | `-124.2894` | `+232.5046` |

The best context filter is not better than base. It also filters many trades and still leaves a negative total.

### min_train_months=8

Scored months: 2025-09..2025-12, 175 trades, baseline PnL `-626.1752`.

| feature set | target | trades | prevalence | predicted mean | brier | AUC |
|---|---|---:|---:|---:|---:|---:|
| base | nonpositive | `175` | `0.6171` | `0.4765` | `0.2489` | `0.6207` |
| base | large_loss | `175` | `0.1371` | `0.0749` | `0.1222` | `0.5523` |
| context | nonpositive | `175` | `0.6171` | `0.4958` | `0.2631` | `0.5471` |
| context | large_loss | `175` | `0.1371` | `0.0611` | `0.1248` | `0.5364` |

Post-filter diagnostic top:

| feature set | target | train quantile | kept trades | baseline PnL | kept PnL | delta |
|---|---|---:|---:|---:|---:|---:|
| context | large_loss | `0.70` | `98/175` | `-626.1752` | `-271.9178` | `+354.2574` |
| base | large_loss | `0.70` | `94/175` | `-626.1752` | `-316.3742` | `+309.8010` |
| context | large_loss | `0.80` | `116/175` | `-626.1752` | `-345.8832` | `+280.2920` |

Month breakdown for `context / large_loss / q70`:

| month | baseline trades | kept trades | baseline PnL | kept PnL | delta |
|---|---:|---:|---:|---:|---:|
| 2025-09 | `81` | `50` | `-289.0056` | `-191.2808` | `+97.7248` |
| 2025-10 | `29` | `13` | `-46.6894` | `-3.9818` | `+42.7076` |
| 2025-11 | `23` | `17` | `-111.6232` | `-57.4712` | `+54.1520` |
| 2025-12 | `42` | `18` | `-178.8570` | `-19.1840` | `+159.6730` |

This is useful evidence that online context state helps describe the late-year breakdown, but it remains a post-trade deletion diagnostic and still does not recover NoTrade.

## Decision

- Keep the script as a feature diagnostic and OOF sanity check.
- Do not add raw online context state into the standard selected-trade failure / quality feature set yet.
- Do not promote the post-filter result to a policy rule; it ignores replacement trades.
- Next direction:
  - combine online context state with side-drift / prediction-side-bias features,
  - evaluate only in a true dynamic backtest path,
  - prefer lower-capacity or monotonic feature groups because raw context features overfit the small selected-trade sample.

## Verification

- `python3 -m py_compile scripts/experiments/online_context_feature_model.py tests/test_online_context_feature_model.py`: OK
- `python3 -m unittest tests.test_backtest tests.test_context_drawdown_guard_selection tests.test_online_context_state_diagnostics tests.test_online_context_feature_model tests.test_docs_reports`: OK, 107 tests
