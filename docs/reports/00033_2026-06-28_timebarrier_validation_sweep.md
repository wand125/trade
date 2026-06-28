# Timebarrier Validation Sweep

日時: 2026-06-28 13:53 JST
更新日時: 2026-06-28 13:57 JST

## Summary

- Experiment ID: `timebarrier_validation_sweep`
- Status: validation completed, not promoted to blind test
- Main result: 240m / 720m の time-limited profit barrier probability は候補を作れるが、現時点では 24h profit barrier probability threshold `0.2` の候補より cost-aware validation が弱い。
- Report numbering note: this file is numbered by the internal `日時`, not by file update time or `更新日時`.

## Motivation

前回追加した `long/short_profit_barrier_hit_60m/240m/720m` を、実際の policy sweep に差し替えて検証する。

狙いは、24h以内にいつか取れる profit barrier ではなく、より早い時間帯で profit barrier を取れる確率を使い、entry後に薄いedgeを持ち続ける候補を落とすこと。

## Implementation Note

`target-set policy` には `fixed_horizon_ev` policy に必要な `long_fixed_60m_adjusted_pnl` などの固定horizon回帰targetが入っていなかった。今回、policy target setへ `EXIT_FIXED_HORIZON_TARGETS` を追加した。

変更:

- `src/trade_data/modeling.py`
- `tests/test_modeling.py`

これにより `--target-set policy` で再学習したモデルから、`fixed_horizon_ev` と time-limited barrier probability を同時に使える。

## Data And Model

主datasetを新target込みで再生成した。

- Dataset dir: `data/processed/datasets/xauusd_m1_p1_l1p2/`
- Months: `2023-01` から `2025-07`
- Profit multiplier: `1.0`
- Loss multiplier: `1.2`
- Min adjusted edge: `15`
- Build summary: `data/processed/datasets/xauusd_m1_p1_l1p2/build_range_2023-01_2025-07_edge15.summary.json`

学習モデル:

- Artifact: `experiments/20260628_040828_policy_timebarrier_p1_l1p2/`
- Train months: `2023-01` から `2023-12`, `2024-01` から `2024-06`, `2024-08`, `2024-10`
- Valid months: `2024-07`, `2024-09`, `2024-11`, `2025-01`
- Test month in artifact: `2025-06`。今回はvalidation sweep比較だけに使い、blind採用判断には使わない。
- Purge / embargo: enabled, embargo `24h`
- HGB: `max_iter=80`, `learning_rate=0.05`, `max_leaf_nodes=15`, `max_depth=4`, `min_samples_leaf=100`, `l2=0.2`, `max_features=0.8`, early stopping enabled

行数:

| split | rows |
|---|---:|
| train | 535,493 |
| valid | 119,241 |
| test | 28,889 |

主な prediction columns:

- `pred_long_fixed_60m_adjusted_pnl`
- `pred_short_fixed_720m_adjusted_pnl`
- `pred_long_profit_barrier_hit_prob`
- `pred_long_profit_barrier_hit_240m_prob`
- `pred_short_profit_barrier_hit_720m_prob`

## Classifier Diagnostics

time-limited barrier classifier の balanced accuracy は validation ではほぼ `0.5` 付近だった。

| target | train bal acc | valid bal acc | test bal acc |
|---|---:|---:|---:|
| `long_profit_barrier_hit` | `0.5098` | `0.5003` | `0.4999` |
| `short_profit_barrier_hit` | `0.5256` | `0.5130` | `0.5290` |
| `long_profit_barrier_hit_60m` | `0.5174` | `0.5000` | `0.5005` |
| `short_profit_barrier_hit_60m` | `0.5398` | `0.5137` | `0.5018` |
| `long_profit_barrier_hit_240m` | `0.5100` | `0.5001` | `0.5000` |
| `short_profit_barrier_hit_240m` | `0.5269` | `0.5074` | `0.5022` |
| `long_profit_barrier_hit_720m` | `0.5015` | `0.4992` | `0.5018` |
| `short_profit_barrier_hit_720m` | `0.5318` | `0.5002` | `0.5242` |

解釈:

- 短時間barrier probabilityは、現HGBでは強い識別力を持っていない。
- 特に 60m は希少targetなので、現時点ではhard gateに使わない。
- 240m / 720m は candidate selection の補助軸としては使えるが、モデル性能の改善根拠としては弱い。

## Sweep Setup

共通条件:

- Policy: `fixed_horizon_ev`
- Entry threshold: `0`
- Long offset: `0`
- Short offsets: `0`, `4`, `8`
- Side margins: `0`, `1`
- Max wait regret: `4`, `inf`
- Min entry rank: `0`, `0.5`
- Extra side margin: `session_regime=asia:5`, `session_regime=rollover:5`
- Side block variants: none, `short:session_regime=asia`
- Cost-aware case: spread `0.1`, slippage `0.05`, delay `0`
- Candidate gates: min folds `4`, min trades per fold `10`, max forced exit `0.05`, base/cost min pnl `0`, max direction/session loss `60`, max short share `0.65`, max smoothed actual barrier miss `0.55`

比較したprofit barrier probability:

| variant | columns | thresholds |
|---|---|---|
| `barrier24` | `pred_long/short_profit_barrier_hit_prob` | `0.0`, `0.2` |
| `barrier240` | `pred_long/short_profit_barrier_hit_240m_prob` | `0.0`, `0.2` |
| `barrier720` | `pred_long/short_profit_barrier_hit_720m_prob` | `0.0`, `0.2` |
| `barrier240_fine` | 240m probability | `0.0`, `0.02`, `0.05`, `0.08`, `0.1`, `0.2` |
| `barrier720_fine` | 720m probability | `0.0`, `0.1`, `0.2`, `0.3`, `0.4` |

## Candidate Selection Results

Broad sweep summary:

| variant | eligible | top threshold | cost min pnl | min trades | forced exit max | worst dir/session | smoothed miss max | smoothed calibration over |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `barrier24` | 12 | `0.2` | `27.2158` | 47 | `0.0000` | `-39.1342` | `0.454545` | `0.396124` |
| `barrier240` | 5 | `0.0` | `20.6606` | 56 | `0.035714` | `-51.5902` | `0.500000` | `0.062716` |
| `barrier720` | 5 | `0.0` | `20.6606` | 56 | `0.035714` | `-51.5902` | `0.500000` | `0.087134` |

Fine sweep summary:

| variant | rows | eligible | top threshold | cost min pnl | min trades | forced exit max | worst dir/session | smoothed miss max | smoothed calibration over |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `barrier240_fine` | 288 | 8 | `0.0` | `20.6606` | 56 | `0.035714` | `-51.5902` | `0.500000` | `0.062716` |
| `barrier720_fine` | 240 | 8 | `0.0` | `20.6606` | 56 | `0.035714` | `-51.5902` | `0.500000` | `0.087134` |

Fine thresholdのeligible分布:

| variant | eligible thresholds |
|---|---|
| `barrier240_fine` | `0.0`: 5件, `0.02`: 3件 |
| `barrier720_fine` | `0.0`: 5件, `0.1`: 3件 |

閾値を上げた候補も少数残るが、cost min pnl は 24h probability threshold `0.2` の候補に届かなかった。

## Artifacts

- Model: `experiments/20260628_040828_policy_timebarrier_p1_l1p2/`
- Broad candidate summary: `data/reports/backtests/20260628_timebarrier_candidate_selection_summary.csv`
- Fine candidate summary: `data/reports/backtests/20260628_timebarrier_fine_candidate_selection_summary.csv`
- 240m fine candidate selection: `data/reports/backtests/20260628_045220_barrier240_fine_candidate_selection/`
- 720m fine candidate selection: `data/reports/backtests/20260628_045221_barrier720_fine_candidate_selection/`

## Conclusion

今回のtime-limited barrier targetは、設計としては妥当だが、現HGBの識別力ではまだ採用候補を改善していない。

判断:

- 24h profit barrier probability threshold `0.2` の broad候補を当面の上位候補として残す。
- 240m / 720m probability は診断・tie-breakには残すが、hard gateの主軸にはしない。
- 60m probability は希少targetなので、class weightingやhazard設計なしには使わない。
- classifierのbalanced accuracyがほぼ `0.5` なので、次はbinary classifierの確率をそのまま信じるより、exit timing / hazard を回帰またはsurvival形式で学習する方が筋が良い。

## Verification

- `python3 -m unittest discover tests`: 71 tests OK
- `git diff --check`: OK
- `docs/reports` numbering check: 33 files OK, ordered by internal `日時`

## Next Actions

1. 今回の結果を踏まえ、次のblindへ進む前に 24h barrier threshold `0.2` 候補を再固定するか、もう一段だけ validation-only で exit timing target を改善するかを決める。
2. time-limited barrier は採用保留にし、exit regret / EV overestimate を直接下げる target を優先する。
3. 60m/240m/720m targetを使うなら、class imbalanceに対応した学習か、`hit probability by horizon` の単調性を持つhazard modelに変える。
4. 次回以降も、レポート採番はファイル内の `日時` を基準にし、`更新日時` やファイル更新時刻は採番に使わない。
