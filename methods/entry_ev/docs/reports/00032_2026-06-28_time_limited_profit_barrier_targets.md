# Time-Limited Profit Barrier Targets

日時: 2026-06-28 12:58 JST
更新日時: 2026-06-28 12:58 JST

## Summary

- Experiment ID: `time_limited_profit_barrier_targets`
- Status: implemented and smoke-tested
- Main result: `long_profit_barrier_hit_60m/240m/720m` と `short_profit_barrier_hit_60m/240m/720m` をdataset targetに追加した。既存の `--long-profit-barrier-column` / `--short-profit-barrier-column` に確率列を差し替えられる。
- Report numbering note: this file is numbered by the internal `日時`, not by file update time or `更新日時`.

## Motivation

既存の `long_profit_barrier_hit` / `short_profit_barrier_hit` は、24h以内のどこかで利益バリアを先に取れるかを見る。2025-07 blind failureでは、entry後のedgeが薄く、exit regretとEV過大評価が残った。

そこで、単に「24h以内に取れる」ではなく、近い時間帯で利益バリアを取れる可能性を別targetとして学習する。これは exit timing target / hazard target の第一段階であり、fixed horizon EVだけに依存しない選別軸にする。

## Implementation

追加したtarget:

- `long_profit_barrier_hit_60m`
- `short_profit_barrier_hit_60m`
- `long_profit_barrier_hit_240m`
- `short_profit_barrier_hit_240m`
- `long_profit_barrier_hit_720m`
- `short_profit_barrier_hit_720m`

仕様:

- entryは従来通り次足open。
- 各sideについて、指定分数以内にprofit barrierへloss barrierより先に到達すれば `1`。
- 指定分数が最大保有horizonを超える場合は、利用可能な最大horizonでcapする。
- `target-set policy` と `target-set full` のclassification targetへ追加。
- 学習後は `pred_long_profit_barrier_hit_240m_prob` のような確率列が保存される。

## Smoke Data

本番datasetはまだ上書きしていない。検証用に `/tmp` へ 2025-01 から 2025-03 を生成した。

2025-01 target distribution:

| target | positive rate | positives |
|---|---:|---:|
| `long_profit_barrier_hit_60m` | `0.0023` | 70 |
| `short_profit_barrier_hit_60m` | `0.0063` | 190 |
| `long_profit_barrier_hit_240m` | `0.0665` | 2009 |
| `short_profit_barrier_hit_240m` | `0.0420` | 1267 |
| `long_profit_barrier_hit_720m` | `0.3255` | 9828 |
| `short_profit_barrier_hit_720m` | `0.1196` | 3613 |

全列のnull countは `0`。

Interpretation:

- 60m targetはかなり希少で、通常のHGB binary classifierでは全ゼロ予測に寄りやすい。
- 240m / 720m targetは正例が十分あり、最初のpolicy sweepで使う候補として現実的。
- 24h targetより短いhorizonを使うことで、「遅いoracle exitだけに依存するentry」を落とせる可能性がある。

## Smoke Training

軽量学習:

- train: `2025-01`
- valid: `2025-02`
- test: `2025-03`
- dataset dir: `/tmp`
- target set: `policy`
- max iter: `2`
- sample frac: `0.05`
- artifact: `experiments/20260628_035801_exit_target_smoke/`

確認したこと:

- policy target setに新targetが含まれる。
- `pred_long_profit_barrier_hit_60m_prob`, `pred_long_profit_barrier_hit_240m_prob`, `pred_long_profit_barrier_hit_720m_prob` などが `predictions_valid.parquet` に保存される。
- train/valid/test分割重複は従来通り拒否される。

Smokeの分類結果は、max_iter=2かつsample 5%なので性能評価には使わない。60m/240m/720mの列生成、学習、確率保存が通ることだけを確認した。

## Verification

- `python3 -m unittest tests.test_dataset tests.test_modeling`: 25 tests OK
- `python3 -m unittest discover tests`: 71 tests OK
- `python3 -m py_compile src/trade_data/dataset.py src/trade_data/modeling.py`: OK
- `git diff --check`: OK

## Next Actions

1. 主dataset `data/processed/datasets/xauusd_m1_p1_l1p2/` を新target込みで再生成する。
2. `target-set policy` のHGBを再学習し、`pred_*_profit_barrier_hit_240m_prob` / `720m_prob` をprofit barrier columnに使ったvalidation sweepを比較する。
3. 60m targetは希少なので、最初はhard gateにせず診断扱いにする。使う場合はclass weightingやpositive supportを別途検討する。
4. cost-aware validationを主目的にし、NoTradeを超える候補だけを次のblindへ進める。
