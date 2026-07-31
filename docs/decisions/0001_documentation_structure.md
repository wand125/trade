# 0001: 研究ドキュメント構造を固定する

日付: 2026-06-28 JST
状態: accepted

## 背景

XAUUSD の短期トレード予測研究は、データ取得、バックテスト、特徴量、深層学習、評価、外部データ調査が絡む。作業が長期化すると、何を試したか、どの仕様で比較したか、次に何をすべきかが分からなくなる。

## 決定

以下の文書構造を採用する。

- `GOAL.md`: 研究目的と取引ルール。
- `methods/entry_ev/docs/status.md`: 現在の状態と次の作業。
- `methods/entry_ev/docs/research_log.md`: 時系列の作業記録。
- `methods/entry_ev/docs/research_plan.md`: 体系的な研究ロードマップ。
- `methods/entry_ev/docs/backtest_spec.md`: バックテスト仕様。
- `methods/entry_ev/docs/data_strategy.md`: データと前処理方針。
- `methods/entry_ev/docs/modeling_strategy.md`: モデル方針。
- `methods/entry_ev/docs/experiment_protocol.md`: 実験管理ルール。
- `methods/entry_ev/docs/ideas.md`: 未検証アイデア。
- `docs/reports/`: 実験レポート。
- `docs/decisions/`: 重要判断。

## 影響

作業開始時は `GOAL.md`、`methods/entry_ev/docs/status.md`、`methods/entry_ev/docs/research_log.md` を読む。作業後は `methods/entry_ev/docs/research_log.md` と必要な体系文書を更新する。

## 代替案

単一の長いノートにまとめる案もあったが、仕様、ログ、実験結果、アイデアが混ざりやすいため採用しない。

