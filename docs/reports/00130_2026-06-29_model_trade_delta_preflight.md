# Model Trade Delta Preflight

日時: 2026-06-29 10:48 JST
更新日時: 2026-06-29 10:48 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻である `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## 目的

`00128` / `00129` で、validation top候補はvalidationでは強いがapplyでは大きく崩れることを確認した。手作業のdelta確認だけでは、同じ過適合候補を再び採用しやすい。

今回は `model-trade-delta` の出力をvalidation/holdoutに分けて横断集計し、候補採用前に機械的に落とすpreflight診断を追加する。

## 実装

`src/trade_data/backtest.py` に `model-trade-delta-preflight` を追加した。

入力:

- `--validation-deltas`
- `--holdout-deltas`

出力:

- `case_metrics.csv`
- `failed_cases.csv`
- `summary.json`
- `config.json`

各caseで以下を集計する。

- 合計 `pnl_delta_sum`
- 月別最悪 `pnl_delta_min_month`
- 月別最悪 `stateful_target_mean_min_month`
- `common` / `only_base` / `only_candidate` のPnL delta
- `blocking_cost_sum`, `replacement_regret_mean`

デフォルト判定:

- validation: 合計PnL deltaが非負
- holdout: 合計PnL delta、月別最悪PnL delta、月別最悪stateful targetがすべて非負
- holdout caseが1件以上存在し、全件pass

stateful examplesがないcaseは、finiteなstateful閾値ではfailする。これは、候補採用前のstateful確認漏れを通さないため。

## 実データ確認

対象は `00128` の標準候補 vs validation top候補。

```bash
python3 -m trade_data.backtest model-trade-delta-preflight \
  --validation-deltas data/reports/backtests/20260629_014012_guard_fixed_parent_validation_base_delta,data/reports/backtests/20260629_014012_guard_fixed_parent_validation_highcost_delta \
  --holdout-deltas data/reports/backtests/20260629_014012_guard_fixed_parent_apply_base_delta,data/reports/backtests/20260629_014012_guard_fixed_parent_apply_highcost_delta \
  --label guard_fixed_entry_side_preflight
```

結果:

| split | case | pass | pnl delta sum | min month pnl delta | min month stateful target | negative pnl months | negative stateful months |
|---|---|---:|---:|---:|---:|---:|---:|
| validation | base | true | `+62.8970` | `-34.0268` | `+1.7054` | 1 | 0 |
| validation | high cost | true | `+86.4218` | `-9.2824` | `+1.4540` | 1 | 0 |
| holdout/apply | base | false | `-289.3090` | `-192.5654` | `-2.1726` | 3 | 3 |
| holdout/apply | high cost | false | `-290.4310` | `-189.2264` | `-2.4973` | 3 | 3 |

summary:

- validation case pass: `2 / 2`
- holdout case pass: `0 / 2`
- preflight pass: `False`

この診断は、validation top候補を採用前に棄却できる。

## 判断

`model-trade-delta-preflight` を候補採用前の反証ゲートとして使う。

扱い:

- validation summaryだけで候補を昇格しない。
- `model-trade-delta` でvalidation/applyのdeltaを作り、preflightでholdout passを確認する。
- preflight failの候補は、validation topでも標準採用しない。
- これはpolicy変更ではなく、過適合候補を殺す検証フローの追加。

次に進む方向は、追加grid探索ではなく、OOF calibration、stateful blocking / replacement regret target、より広いwalk-forwardでの再評価。

## Artifacts

- preflight: `data/reports/backtests/20260629_014830_guard_fixed_entry_side_preflight/`
- validation base delta: `data/reports/backtests/20260629_014012_guard_fixed_parent_validation_base_delta/`
- validation high cost delta: `data/reports/backtests/20260629_014012_guard_fixed_parent_validation_highcost_delta/`
- apply base delta: `data/reports/backtests/20260629_014012_guard_fixed_parent_apply_base_delta/`
- apply high cost delta: `data/reports/backtests/20260629_014012_guard_fixed_parent_apply_highcost_delta/`

## Verification

- targeted preflight unit test: OK
- real preflight run: OK
- `python3 -m unittest tests.test_backtest tests.test_docs_reports`: OK, 76 tests
- `git diff --check`: OK
