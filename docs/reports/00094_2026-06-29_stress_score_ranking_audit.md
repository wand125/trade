# Stress Score Ranking Audit

日時: 2026-06-29 04:26 JST
更新日時: 2026-06-29 04:26 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻である `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## 目的

`00093` の反省を受け、候補rankingをcost min pnl一点から少し外し、validation fold内だけでstress-aware rankingを定義する。

ただし、既存holdout 2024-12 / 2025-02 / 2025-03 はすでに見ているため、今回のholdout監査は採用根拠ではなく外挿診断として扱う。未使用月検証は、同一形式の `component_fixed_weighted` predictionを2025-04以降へ生成してから行う。

## 実装

`model-candidate-selection --candidate-rank-mode stress_score` を追加した。

score:

```text
stress_risk_score
  = near_top_risk_score
  - stress_cost_pnl_sum_reward_weight * total_adjusted_pnl_sum_cost
  - stress_base_pnl_sum_reward_weight * total_adjusted_pnl_sum_base
```

`near_top_risk_score` は既存どおり、group loss、drawdown、EV overestimate、exit regret、actual miss、side shareの合成risk。`stress_score` はその上で、validation cost/base scenario合計PnLを小さくrewardする。

また、`model-holdout-audit` を `model-sweep` の `metrics.csv` gridにも対応させた。これにより、固定policy runだけでなく、複数候補のholdout sweepをvalidation summaryへmergeできる。

## Validation Selection

条件:

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

Top候補は `down5,up10`。`00093` のstrict min-pnl top `down5,up10,range5` からは変わったが、既存near-top risk topと同じ。

| rule set | eligible | near top | stress score | risk score | cost min pnl | cost sum pnl | base min pnl | max DD | group loss |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `down5,up10` | yes | yes | `351.3986` | `372.6128` | `96.8776` | `1060.7086` | `138.0338` | `88.9514` | `109.2144` |
| `down5,up15` | yes | yes | `394.0283` | `413.7727` | `94.2442` | `987.2160` | `131.3082` | `101.5464` | `134.8324` |
| `down10,up10,range10` | yes | yes | `396.7231` | `418.8349` | `81.7042` | `1105.5924` | `116.8422` | `121.0958` | `115.7584` |
| `down5,up10,range10` | yes | yes | `410.5976` | `431.8665` | `80.3808` | `1063.4408` | `110.1976` | `116.6198` | `133.4440` |
| `down5,up15,range10` | yes | yes | `417.0862` | `438.6682` | `83.7792` | `1079.1004` | `118.7610` | `120.1644` | `132.9418` |
| `down5,up10,range5` | yes | yes | `476.8519` | `500.5073` | `107.1572` | `1182.7684` | `138.3706` | `86.9156` | `233.2880` |

## Existing Holdout Audit

既存holdout stressの診断では、全候補に負けcaseが残る。`min_adjusted_pnl_per_case=0`、9cases全通過の候補は0。

| rule set | validation eligible | holdout cases | pass cases | holdout min pnl | holdout sum pnl | holdout max DD | positive rate |
|---|---:|---:|---:|---:|---:|---:|---:|
| `down5,up10,range5` | yes | `9` | `5` | `-32.4176` | `147.1338` | `181.6922` | `0.5556` |
| `down10,up10,range10` | yes | `9` | `6` | `-41.0256` | `569.9690` | `127.9822` | `0.6667` |
| `down5,up15,range10` | yes | `9` | `5` | `-53.7684` | `170.0336` | `144.4880` | `0.6667` |
| `down5,up10,range10` | yes | `9` | `6` | `-53.8458` | `360.8382` | `130.2018` | `0.6667` |
| `down5,up10` | yes | `9` | `6` | `-57.7402` | `473.2982` | `132.5332` | `0.6667` |

今回のvalidation top `down5,up10` は、holdoutではmin pnl `-57.7402`。`00093` のstrict top `down5,up10,range5` よりholdout sumは良いが、min pnlは悪い。holdout上の相対バランスは引き続き `down10,up10,range10` が良いが、validation stress scoreでは3位に留まる。

## 判断

stress score rankingは実装価値があるが、この設定だけでは標準採用候補を作れない。

重要な点:

- validation内で `cost sum pnl` をrewardしても、既存holdoutのmin-loss問題は解消しない。
- `down5,up10,range5` はvalidation cost min最強だがgroup lossが大きい。
- `down10,up10,range10` はholdout合計とdrawdownのバランスが良いが、validation stress scoreではまだtopではない。
- 既存holdoutを見てweightを調整するとpost-hocになるため、ここでweightを最適化しない。

次は、2025-04以降へ同一形式の `xauusd_m1_p1_l1p2_policy_combined` dataset、HGB entry/side + MLP exit prediction、forced target、component fixed weighted applyを生成し、今回の `stress_score` topと近傍候補を未使用holdoutで確認する。

## Artifacts

- stress score selection: `data/reports/backtests/component_fixed_weighted_short_lowvol_combo_stress_score_selection/20260628_192419_model_candidate_selection/`
- stress score holdout audit: `data/reports/backtests/component_fixed_weighted_short_lowvol_combo_stress_score_holdout_audit/20260628_192600_model_holdout_audit/`

## Verification

- `PYTHONPATH=src python3 -m unittest tests.test_backtest`: OK, 60 tests
- `PYTHONPATH=src python3 -m trade_data.backtest model-candidate-selection --help`: OK, `stress_score` options shown
- `PYTHONPATH=src python3 -m trade_data.backtest model-candidate-selection`: OK for stress score selection
- `PYTHONPATH=src python3 -m trade_data.backtest model-holdout-audit`: OK for model-sweep holdout grid
- `PYTHONPATH=src python3 -m unittest discover tests`: OK, 141 tests
- `git diff --check`: OK
