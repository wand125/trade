# PnL Stability Candidate Ranking

日時: 2026-06-29 07:03 JST
更新日時: 2026-06-29 07:03 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻である `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## 目的

`00106` までの反省では、entry timing / quality / failure probabilityを単独のhard gateやrisk penaltyにするとvalidationの一部月を削りすぎる問題が続いた。

今回は新しい売買ルールを増やさず、候補選定rankingに「fold間でPnLが荒い候補を下げる」診断を追加する。狙いは最高PnL一点ではなく、未知月で壊れにくい候補をnear-top内で選びやすくすること。

## 実装

`model-sweep-summary` に `total_adjusted_pnl_std` を追加した。これは同一候補について、validation foldごとの `total_adjusted_pnl` の標準偏差を集計する。

`model-candidate-selection` には `--near-top-pnl-stability-weight` を追加した。defaultは `0.0` で既存挙動を維持する。

score追加:

```text
near_top_risk_score += near_top_pnl_stability_weight * pnl_stability_risk_all
pnl_stability_risk_all = max(total_adjusted_pnl_std_base, total_adjusted_pnl_std_cost)
```

このpenaltyは `near_top_risk` と `stress_score` の両方で効く。eligible判定やnear-top判定そのものは変えない。

## Validation

`00094` と同じbase 4fold + moderate/high cost 8foldのstress selection条件で比較した。

固定条件:

- profit/loss: `1.0 / 1.20`
- base validation: 2024-07 / 2024-09 / 2024-11 / 2025-01
- cost validation: moderate + high cost, 8fold
- `min_base_folds=4`
- `min_cost_folds=8`
- `min_trades_per_fold=50`
- `max_drawdown=125`
- `min_base_adjusted_pnl_per_fold=80`
- `min_cost_adjusted_pnl_per_fold=50`
- `max_short_trade_share=0.65`
- `max_side_trade_share=0.90`
- `candidate_rank_mode=stress_score`
- `near_top_cost_pnl_tolerance=30`
- `stress_cost_pnl_sum_reward_weight=0.02`

### Weight Sensitivity

| stability weight | selected rule set | stress score | cost min pnl | cost sum pnl | base min pnl | pnl stability |
|---:|---|---:|---:|---:|---:|---:|
| `0.0` | `down5,up10` | `351.3986` | `96.8776` | `1060.7086` | `138.0338` | `28.4510` |
| `0.5` | `down5,up10` | `365.6241` | `96.8776` | `1060.7086` | `138.0338` | `28.4510` |
| `1.0` | `down5,up10` | `379.8496` | `96.8776` | `1060.7086` | `138.0338` | `28.4510` |

top候補は変わらない。これは `down5,up10` がnear-top内で既に低めのfold間PnL標準偏差を持っているため。

near-top候補の比較:

| rule set | stress score w0 | stress score w1 | cost min pnl | cost sum pnl | base min pnl | pnl stability | group loss |
|---|---:|---:|---:|---:|---:|---:|---:|
| `down5,up10` | `351.3986` | `379.8496` | `96.8776` | `1060.7086` | `138.0338` | `28.4510` | `109.2144` |
| `down5,up15` | `394.0283` | `423.3450` | `94.2442` | `987.2160` | `131.3082` | `29.3166` | `134.8324` |
| `down10,up10,range10` | `396.7231` | `442.0283` | `81.7042` | `1105.5924` | `116.8422` | `45.3052` | `115.7584` |
| `down5,up10,range10` | `410.5976` | `460.7669` | `80.3808` | `1063.4408` | `110.1976` | `50.1692` | `133.4440` |
| `down5,up15,range10` | `417.0862` | `459.3200` | `83.7792` | `1079.1004` | `118.7610` | `42.2338` | `132.9418` |
| `down5,up10,range5` | `476.8519` | `515.7416` | `107.1572` | `1182.7684` | `138.3706` | `38.8897` | `233.2880` |

## 判断

PnL安定性rankingの実装は採用する。最高PnL候補を直接変える機能ではなく、near-top候補間の不安定性を可視化して下げる診断・tie-breakとして使う。

ただし、この結果だけで新しい標準候補は作らない。

理由:

- weight `0/0.5/1.0` でtopが変わらず、既存stress topの再確認に留まった。
- `down10,up10,range10` のような既存holdoutで相対的に良かった候補は、validation上のPnL標準偏差が大きく、今回の事前rankingではむしろ下がる。
- 既存holdout結果に合わせてstability weightを調整するとpost-hocになる。

次は、このrankingを使うなら事前登録したweightのまま、未使用月または追加walk-forward foldで確認する。現時点では「候補選定の説明変数を増やした」段階であり、「標準policy改善」とは扱わない。

## Artifacts

- stability weight 0: `data/reports/backtests/pnl_stability_candidate_ranking_w0/20260628_220328_model_candidate_selection/metrics.csv`
- stability weight 0.5: `data/reports/backtests/pnl_stability_candidate_ranking_w0p5/20260628_220328_model_candidate_selection/metrics.csv`
- stability weight 1.0: `data/reports/backtests/pnl_stability_candidate_ranking_w1/20260628_220328_model_candidate_selection/metrics.csv`

## Verification

- `python3 -W ignore -m unittest tests.test_backtest.BacktestTests.test_candidate_selection_can_rank_near_top_by_pnl_stability`: OK
- `python3 -m trade_data.backtest model-candidate-selection --help`: OK, `--near-top-pnl-stability-weight` shown
- `python3 -m trade_data.backtest model-candidate-selection`: OK for weight `0`, `0.5`, `1.0`
- `python3 -W ignore -m unittest tests.test_backtest tests.test_docs_reports`: OK, 66 tests
- `python3 -W ignore -m unittest discover tests`: OK, 152 tests
- `git diff --check`: OK
