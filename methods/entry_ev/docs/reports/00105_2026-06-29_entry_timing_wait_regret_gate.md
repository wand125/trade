# Entry Timing Wait Regret Gate

日時: 2026-06-29 06:44 JST
更新日時: 2026-06-29 06:44 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻である `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## 目的

`00104` ではcandidate quality downside calibrationをrisk penaltyとして標準採用しなかった。次はrule追加ではなく、既存のentry timing教師である `pred_*_wait_regret` と `pred_*_entry_local_rank` を使い、「今入るより待ったほうがよい局面」を落とせるかを検証する。

固定条件:

- predictions: `data/reports/modeling/20260629_candidate_quality_downside_calibration/predictions_fixed_component_oof_downside_holding.parquet`
- policy: `timed_ev`
- entry threshold `12`
- long offset `0`, short offset `6`
- side margin `5`
- max predicted hold `480`
- short low-vol penalty: `down_low_vol:5`, `up_low_vol:10`, `range_low_vol:5`
- profit/loss: `1.0/1.20`

検証grid:

- `max_wait_regret`: `inf`, `8`, `4`, `2`
- `min_entry_rank`: `0.5`, `0.7`

## Prediction Scale Check

`min_entry_rank=0.7` は全月で0 tradeになった。予測列の最大値はlong `0.6818`, short `0.6905` で、探索範囲として無効。

今後この系列では、`entry_rank` を使うなら `0.50..0.65` 程度に探索範囲を制限する。`0.7` 以上は現在のHGB予測スケールでは実質NoTrade gateになる。

`wait_regret` はlong/shortとも大半が `1..5` に分布し、`max_wait_regret=4` は軽い防御gate、`2` は強い低頻度gateとして機能する。

## Validation

対象月: `2024-07`, `2024-09`, `2024-11`, `2025-01`。

### Base

| max_wait_regret | min_entry_rank | sum pnl | min month pnl | trades | min trades | max DD | month pnls |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| inf | 0.5 | 673.9120 | 145.5682 | 274 | 66 | 92.0350 | 2024-07:146.9022/70, 2024-09:160.5454/68, 2024-11:145.5682/70, 2025-01:220.8962/66 |
| 8 | 0.5 | 673.9120 | 145.5682 | 274 | 66 | 92.0350 | same as inf |
| 4 | 0.5 | 654.3170 | 142.5510 | 263 | 64 | 74.9336 | 2024-07:172.9754/67, 2024-09:142.5510/65, 2024-11:151.8354/67, 2025-01:186.9552/64 |
| 2 | 0.5 | 201.1762 | -9.1754 | 148 | 30 | 59.2172 | 2024-07:51.8760/42, 2024-09:56.6266/39, 2024-11:-9.1754/30, 2025-01:101.8490/37 |

`max_wait_regret=4` はdrawdownを `92.0350 -> 74.9336` に下げるが、sumとmin monthを落とす。`2` は取引数を削りすぎ、2024-11でマイナスになる。

### High Cost

高コスト条件は `spread=0.2`, `slippage=0.1`, `execution_delay_bars=1`。

| max_wait_regret | min_entry_rank | sum pnl | min month pnl | trades | min trades | max DD | month pnls |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| inf | 0.5 | 562.8784 | 120.5842 | 274 | 66 | 97.1906 | 2024-07:120.5842/70, 2024-09:121.1420/68, 2024-11:129.7600/70, 2025-01:191.3922/66 |
| 8 | 0.5 | 562.8784 | 120.5842 | 274 | 66 | 97.1906 | same as inf |
| 4 | 0.5 | 560.1462 | 116.5374 | 263 | 64 | 79.4966 | 2024-07:155.8200/67, 2024-09:116.5374/65, 2024-11:132.5756/67, 2025-01:155.2132/64 |
| 2 | 0.5 | 140.9996 | -17.4532 | 148 | 30 | 62.1250 | 2024-07:37.7638/42, 2024-09:32.7168/39, 2024-11:-17.4532/30, 2025-01:87.9722/37 |

高コストでも同じ構図。`4` はDDだけ改善するが、sum/min monthはbaseline未満。`2` は棄却。

## Holdout Check

holdout: `2024-12`, `2025-02`, `2025-03`, `2025-04`。これはvalidationで有望候補を選ぶためではなく、棄却判断の妥当性確認として実施した。

| max_wait_regret | min_entry_rank | sum pnl | min month pnl | trades | min trades | max DD | month pnls |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| inf | 0.5 | -116.0564 | -223.7292 | 314 | 72 | 474.6194 | 2024-12:7.2314/73, 2025-02:101.3432/72, 2025-03:-0.9018/83, 2025-04:-223.7292/86 |
| 4 | 0.5 | -59.4190 | -83.7526 | 280 | 66 | 299.7690 | 2024-12:-5.1816/71, 2025-02:82.0432/67, 2025-03:-52.5280/76, 2025-04:-83.7526/66 |
| 2 | 0.5 | 180.4620 | -48.1480 | 90 | 5 | 69.0510 | 2024-12:-48.1480/36, 2025-02:84.1642/20, 2025-03:89.6388/29, 2025-04:54.8070/5 |

holdoutだけ見ると `max_wait_regret=2` が良く見える。しかしvalidationでは2024-11が `-9.1754`、high costでは `-17.4532` であり、trade数も30-42まで落ちている。これは2025-04の後付け改善として扱い、標準候補にはしない。

`max_wait_regret=4` はholdoutでDDを縮めるが、2025-03を `-0.9018 -> -52.5280` に悪化させる。validationでも優位ではないため採用しない。

## 判断

標準policyに `max_wait_regret` gateを追加しない。

理由:

- validation base/high costの両方で、baselineがsum pnlとmin month pnlで最上位。
- `max_wait_regret=4` はDD改善だけで、合計と最低月を削る。
- `max_wait_regret=2` はvalidation 2024-11でマイナス化し、取引数も削りすぎる。
- holdoutで `2` が良く見えるのは、2025-04をほぼNoTrade化した後付け効果に近い。
- `min_entry_rank=0.7` は現行予測スケールでは全月0 tradeになり、探索値として不適切。

ただし `wait_regret` 自体は2025-04の損失回避に強く反応している。次はhard gateではなく、entry timing targetの再学習・再校正を検討する。具体的には `wait_regret` をそのまま閾値化するのではなく、side/regime別に「待つべき確率」または「今入る価値のlower bound」として校正する。

## Artifacts

- base validation: `data/reports/backtests/entry_timing_wait_regret_validation/`
- high cost validation: `data/reports/backtests/entry_timing_wait_regret_validation_highcost/`
- holdout: `data/reports/backtests/entry_timing_wait_regret_holdout/`
- summaries:
  - `data/reports/backtests/entry_timing_wait_regret_base_summary.csv`
  - `data/reports/backtests/entry_timing_wait_regret_highcost_summary.csv`
  - `data/reports/backtests/entry_timing_wait_regret_base_highcost_comparison_summary.csv`
  - `data/reports/backtests/entry_timing_wait_regret_holdout_summary.csv`
