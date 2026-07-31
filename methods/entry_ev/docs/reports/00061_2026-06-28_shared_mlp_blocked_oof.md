# Shared MLP Blocked OOF

日時: 2026-06-28 20:06 JST
更新日時: 2026-06-28 20:06 JST

## 目的

前回追加した `train-shared-mlp` は単発splitの接続確認だった。次に、validation内でfit月とholdout月を分けられるblocked OOFをshared MLPにも追加し、HGBの `oof` と同じ検証設計へ近づける。

Report numbering note: this file is numbered from the internal file `日時`, not filesystem mtime or `更新日時`. Latest-report checks and renumbering must use the internal `日時`.

## 実装

`trade_data.modeling` に `oof-shared-mlp` を追加した。

- `--months` / `--start-month` / `--end-month` で対象月を指定する。
- `--fold-month-count` ごとにholdout月を作る。
- 各foldでholdout以外をfitに使う。
- `--purge-label-overlap` と `--embargo-hours` でholdout label windowとの重なりを除外する。
- `sample-frac` は各foldのfit側にだけ適用する。
- 出力は `predictions_oof.parquet`, `metrics.json`, `report.md`, `feature_columns.json`。

このprototypeはmulti-output regressionのみで、classification targetは未学習としてmetricsへ記録する。

## Smoke

コマンド:

```bash
python3 -m trade_data.modeling oof-shared-mlp \
  --dataset-dir data/processed/datasets/xauusd_m1_p1_l1p2_policy_combined \
  --months 2024-07,2024-09 \
  --fold-month-count 1 \
  --target-set policy \
  --sample-frac 0.02 \
  --max-iter 2 \
  --hidden-layers 8 \
  --alpha 0.01 \
  --learning-rate-init 0.001 \
  --entry-threshold 10 \
  --purge-label-overlap true \
  --embargo-hours 24 \
  --label shared_mlp_oof_smoke
```

結果:

| item | value |
|---|---:|
| input rows | `60472` |
| OOF rows | `60472` |
| fold months | `2024-07`; `2024-09` |
| regression targets | `19` |
| fold 0 fit rows after purge/sample | `578` |
| fold 0 holdout rows | `31587` |
| fold 1 fit rows after purge/sample | `632` |
| fold 1 holdout rows | `28885` |
| fold n_iter | `2/2`, `2/2` |

`max_iter=2` で未収束なので、これは性能実験ではなくOOF配線のsmokeである。

OOF oracle-exit selection:

| threshold | selected trades | oracle-exit pnl | avg pnl | side accuracy |
|---:|---:|---:|---:|---:|
| `10.0` | `47557` | `846517.1014` | `17.8001` | `0.5784` |

## Executable Backtest Smoke

OOF予測を各holdout月の `timed_ev` へ接続した。

| holdout month | adjusted pnl | raw pnl | trades | profit factor | max drawdown | forced exits | long / short / flat signals |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2024-07 | `47.3170` | `139.6450` | `562` | `1.0854` | `133.9820` | `4` | `28437 / 388 / 13802` |
| 2024-09 | `32.6390` | `146.2630` | `985` | `1.0479` | `72.6068` | `3` | `21571 / 2917 / 16757` |

両月ともコスト込みでプラスだが、取引数が極端に多い。特に2024-07はshort signalが388しかなく、side balanceは弱い。sample 2%、max_iter 2のため、この結果を採用判断には使わない。

## 判断

blocked OOF shared MLPの配線は完了した。これで次は代表4foldに同じCLIを使える。

ただし、本実験では以下を必須にする。

- `sample-frac` を十分大きくする。
- `max_iter` とvalidation scoreを確認し、未収束のまま採用しない。
- executable backtestで取引数、side share、drawdown、forced exit、NoTrade比較を見る。
- OOF oracle-exit pnlは上限診断に留め、policy採用は実行可能backtestで判断する。

## Artifacts

- OOF smoke model: `experiments/20260628_110628_shared_mlp_oof_smoke/`
- executable smoke 2024-07: `data/reports/backtests/shared_mlp_oof_smoke/20260628_110643_model_timed_ev_2024-07/`
- executable smoke 2024-09: `data/reports/backtests/shared_mlp_oof_smoke/20260628_110643_model_timed_ev_2024-09/`
