# Train-Period OOF Prediction Infrastructure

日時: 2026-06-28 07:54 JST
更新日時: 2026-06-28 08:02 JST

## 目的

side/regime EV calibration は validation 4ヶ月だけではtestへ汎化しなかった。calibration / meta model のfit月数を増やすため、train期間にも out-of-fold predictions を作れるようにする。

目的は、train期間の各月について「その月を学習に使っていないモデル」の予測を得ること。

これにより、以下に使えるデータが増える。

- side/regime別EV calibration。
- meta EV model。
- regime別direction accuracy診断。
- threshold / NoTrade化のOOF評価。

## 実装

`trade_data.modeling` に `oof` サブコマンドを追加した。

```bash
python3 -m trade_data.modeling oof \
  --dataset-dir data/processed/datasets/xauusd_m1_p1_l1p2 \
  --months 2023-01,2023-02,2023-03 \
  --target-set policy \
  --fold-month-count 1
```

出力:

- `predictions_oof.parquet`
- `metrics.json`
- `feature_columns.json`
- `report.md`

仕様:

- `--months` または `--start-month` / `--end-month` でOOF対象月を指定する。
- `--fold-month-count` でholdout月数を指定する。
- 各foldではholdout月をfitから外す。
- `--purge-label-overlap true` の場合、holdoutのlabel horizonに重なるfit行を削除する。
- `--embargo-hours` でholdout window周辺にbufferを追加する。
- 既存のHGB target-set、sample weighting、正則化パラメータをそのまま使う。

注意:

- これはblocked OOFであり、strict walk-forwardではない。
- calibration用の汎化診断には有用だが、最終本番想定ではwalk-forward OOFも別途検討する。

## Smoke Test

実データで軽量smoke runを実行した。

Command:

```bash
python3 -m trade_data.modeling oof \
  --dataset-dir data/processed/datasets/xauusd_m1_p1_l1p2 \
  --months 2025-01,2025-02 \
  --fold-month-count 1 \
  --horizon-hours 24 \
  --min-adjusted-edge 15 \
  --target-set policy \
  --max-iter 1 \
  --sample-frac 0.02 \
  --max-depth 2 \
  --max-leaf-nodes 3 \
  --min-samples-leaf 20 \
  --learning-rate 0.03 \
  --entry-threshold 15 \
  --purge-label-overlap true \
  --embargo-hours 24 \
  --label oof_smoke_policy
```

Artifact:

- `experiments/20260627_222746_oof_smoke_policy/`

結果:

- 2fold OOF が最後まで完了。
- `predictions_oof.parquet`、`metrics.json`、`report.md` を生成。
- smoke runは機能確認用であり、スコアは研究判断に使わない。

## 検証

```bash
python3 -m unittest tests.test_modeling
python3 -m trade_data.modeling oof --help
python3 -m unittest discover tests
git diff --check
```

結果:

- `tests.test_modeling`: 17 tests OK。
- all tests: 47 tests OK。
- CLI help OK。
- diff check OK。

## 次の実験

HGB 80iter regime/purge v2 と同じtrain期間でOOF predictionsを作る。

Train months:

```text
2023-01..2024-06, 2024-08, 2024-10
```

候補コマンド:

```bash
python3 -m trade_data.modeling oof \
  --dataset-dir data/processed/datasets/xauusd_m1_p1_l1p2 \
  --months 2023-01,2023-02,2023-03,2023-04,2023-05,2023-06,2023-07,2023-08,2023-09,2023-10,2023-11,2023-12,2024-01,2024-02,2024-03,2024-04,2024-05,2024-06,2024-08,2024-10 \
  --fold-month-count 1 \
  --horizon-hours 24 \
  --min-adjusted-edge 15 \
  --target-set policy \
  --max-iter 80 \
  --learning-rate 0.03 \
  --max-depth 4 \
  --max-leaf-nodes 15 \
  --min-samples-leaf 100 \
  --l2-regularization 0.2 \
  --max-features 0.8 \
  --sample-weighting month_label \
  --target-clip-quantile 0.99 \
  --entry-threshold 15 \
  --purge-label-overlap true \
  --embargo-hours 24 \
  --label policy_train_oof_p1_l1p2_regime_purge_e24
```

このOOFを作った後、`predictions_oof.parquet` と validation OOF predictions を結合し、side/regime calibration と meta model を再評価する。

## Follow-up

4ヶ月holdout単位のtrain OOFを実行し、side/regime calibrationへ接続した。

- OOF artifact: `experiments/20260627_223559_policy_train_oof_4m_p1_l1p2_regime_purge_e24/`
- calibration report: `docs/reports/00017_2026-06-28_train_oof_calibration_loss120.md`

月単位OOFはまだ未実施。今回の4ヶ月blocked OOFはcalibration fit母集団を増やす初期実験として扱う。
