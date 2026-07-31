# Docs Index

XAUUSD トレード検証基盤のドキュメント置き場。手法ごとのドキュメントはサブディレクトリに分け、実験レポートは全手法共通の `reports/` に番号付きで蓄積する。

## 構成

- `research/`
  オフライン予測研究(データパイプライン・モデリング・バックテスト)のドキュメント。
- `live/`
  MT5 連携のライブ運用(ブリッジ・EA・山谷評価トレード)のドキュメント。
- `reports/`
  実験・調査レポートの共通ストリーム。
- `summary/`
  `reports/` の大量レポートを俯瞰する入口。現在の評価、テーマ別地図、採用/保留/棄却の整理。
- `decisions/`
  仕様変更や重要な設計判断の記録。
- `templates/`
  実験レポートやログ追記用のテンプレート。

今後新しい検証手法を追加するときは `docs/<手法名>/` を作り、レポートは共通の `reports/` 番号ストリームに追記する。

## 最初に読むもの(研究基盤)

1. `../GOAL.md`
   研究目的、取引ルール、評価方針。

2. `summary/`
   現在の評価と全体地図。

3. `research/status.md`
   現在の到達点、利用可能なデータ、次の作業。

4. `research/trading_ml_generalization_principles.md`
   トレードMLで守るべき汎化・検証・リーク防止の原則。

5. `research/research_log.md`
   時系列の作業記録。

6. `research/research_plan.md`
   体系的な研究ロードマップ。

## 仕様と方針(研究基盤)

- `research/pipeline.md`
  データパイプラインと CLI の全体解説。

- `research/backtest_spec.md`
  取引ルール、損益計算、強制決済、評価指標の仕様。

- `research/data_strategy.md`
  データ、欠損、ノイズ、前処理、分割方針。

- `research/modeling_strategy.md`
  ベースライン、深層学習、強化学習、ハイパーパラメータ探索の方針。

- `research/experiment_protocol.md`
  実験管理、ログ、チェックポイント、レポート、再現性のルール。

- `research/trading_ml_generalization_principles.md`
  過去成績への過適合を避け、未知regimeへ壊れにくくするための原則とチェックリスト。

- stateful value / candidate quality系の採用判断では、月抜きOOFの結果だけでなく、対象月より前の月だけでfitするchronological OOFを確認する。`oof-stateful-value-model` では `--oof-scheme expanding --min-train-months 2` 以上を標準診断に使う。

- `research/ideas.md`
  未検証アイデア、特徴量案、モデル案、リスク。

## ライブ運用(MT5)

- `../WORK.md`
  日常の運用手順(ブリッジ起動、スナップショット確認)。

- `live/fx-workspace.ja.md`
  ワークスペース全体の解説(日本語)。

- `live/mt5-ai-bridge.md`
  ブリッジの仕様とレイアウト。

- `live/mt5-installation-guide.md`
  MT5 のセットアップ手順。

- `live/swing-evaluation-trading-system-spec.md`
  山谷評価トレードシステムの仕様。

## 記録ルール

- `reports/`
  実験ごとのレポートを置く。ファイル名は `00001_YYYY-MM-DD_slug.md` の通し番号形式にする。通し番号はファイルシステムの更新時刻(mtime)や本文の `更新日時` ではなく、レポート本文内の `日時: YYYY-MM-DD HH:MM JST` の昇順で決める。再採番・最新判断・既存レポート確認でも、必ずファイル内の `日時` を正とする。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。各レポートの冒頭には `日時: YYYY-MM-DD HH:MM JST` と `更新日時: YYYY-MM-DD HH:MM JST` を入れる。

## 再開手順(研究基盤)

1. `GOAL.md` で目的と取引ルールを確認する。
2. `docs/research/status.md` の「現在の状態」と「次の作業」を読む。
3. `docs/research/trading_ml_generalization_principles.md` のチェックリストを読む。
4. `docs/research/research_log.md` の最新エントリを読む。
5. 直近の実験がある場合は `docs/reports/` の最新レポートを読む。最新判断はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、ファイル内の `日時` を基準にする。通し番号はその `日時` 順に由来する補助情報として扱う。
6. 作業前に、変更する仕様や新しい仮説を `docs/research/research_log.md` に記録する。
7. 作業後に、結果、スコア、失敗、次の一手を記録する。
