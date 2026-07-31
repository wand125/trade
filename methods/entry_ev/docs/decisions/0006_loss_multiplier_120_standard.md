# 0006: 評価倍率を 1.0 / 1.20 に統一する

日付: 2026-06-28 JST
状態: accepted

## 背景

一時的に validation/test 評価を profit 1.0 / loss 1.25 に緩和していたが、その後、教師生成と実行backtestのズレを減らすため、profit 1.0 / loss 1.20 のdatasetを作成して診断を進めた。

直近の研究では `data/processed/datasets/xauusd_m1_p1_l1p2/` を主datasetとして使っており、学習targetはすでに loss 1.20 前提になっている。一方で一部のbacktestコマンドが loss 1.25 のまま残っていたため、評価条件が混在していた。

## 決定

現行の標準評価条件を以下に統一する。

- profit multiplier: 1.0
- loss multiplier: 1.20

学習target、validation policy selection、fixed test evaluation は原則として同じ 1.0 / 1.20 に揃える。

## 影響

- `trade_data.dataset` と `trade_data.backtest` のデフォルトを profit 1.0 / loss 1.20 に変更する。
- README、GOAL、仕様文書の標準例を 1.0 / 1.20 に更新する。
- 過去レポートの 0.9 / 1.3 や 1.0 / 1.25 の結果は履歴として残す。
- 今後の実験レポートでは、倍率を明記し、過去結果と比較する場合は同倍率で再評価する。

## 代替案

- 1.0 / 1.25 を継続する案: NoTrade寄りの評価を緩める意義はあったが、学習targetとのズレが残る。
- 0.9 / 1.3 へ戻す案: 厳しい条件の研究として有用だが、現段階ではentry数が薄くなりすぎ、モデル改善の診断が進みにくい。
