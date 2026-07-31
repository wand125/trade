# Docs Index

XAUUSD トレード検証基盤の共通ドキュメント置き場。手法ごとのドキュメントは `methods/<手法名>/docs/` にあり、ここには全手法で共有するレポートストリームと記録を置く。

## 構成

- `reports/`
  実験・調査レポートの共通ストリーム(全手法共用、番号付き)。
- `summary/`
  `reports/` の大量レポートを俯瞰する入口。現在の評価、テーマ別地図、採用/保留/棄却の整理。
- `decisions/`
  仕様変更や重要な設計判断の記録。
- `templates/`
  実験レポートやログ追記用のテンプレート。

手法ごとのドキュメント:

- `../methods/entry_ev/docs/`
  ML エントリー期待値予測研究。GOAL.md(目標・取引ルール)、研究計画、バックテスト仕様、研究ログ。
- `../methods/swing_eval/docs/`
  山谷評価トレード(MT5 ライブ運用)。WORK.md(運用手順)、ブリッジ仕様、システム仕様。

新しい検証手法を追加するときは `methods/<手法名>/docs/` を作り、レポートは共通の `reports/` 番号ストリームに追記する。

## 最初に読むもの(entry_ev 研究)

1. `../methods/entry_ev/docs/GOAL.md`
   研究目的、取引ルール、評価方針。

2. `summary/`
   現在の評価と全体地図。

3. `../methods/entry_ev/docs/status.md`
   現在の到達点、利用可能なデータ、次の作業。

4. `../methods/entry_ev/docs/trading_ml_generalization_principles.md`
   トレードMLで守るべき汎化・検証・リーク防止の原則。

5. `../methods/entry_ev/docs/research_log.md`
   時系列の作業記録。

6. `../methods/entry_ev/docs/research_plan.md`
   体系的な研究ロードマップ。

そのほか entry_ev の仕様と方針は `../methods/entry_ev/docs/` 配下の `pipeline.md`、`backtest_spec.md`、`data_strategy.md`、`modeling_strategy.md`、`experiment_protocol.md`、`ideas.md` を参照。

- stateful value / candidate quality系の採用判断では、月抜きOOFの結果だけでなく、対象月より前の月だけでfitするchronological OOFを確認する。`oof-stateful-value-model` では `--oof-scheme expanding --min-train-months 2` 以上を標準診断に使う。

## ライブ運用(swing_eval)

- `../methods/swing_eval/docs/WORK.md`
  日常の運用手順(ブリッジ起動、スナップショット確認)。

- `../methods/swing_eval/docs/fx-workspace.ja.md`
  ワークスペース全体の解説(日本語)。

- `../methods/swing_eval/docs/mt5-ai-bridge.md`
  ブリッジの仕様とレイアウト。

- `../methods/swing_eval/docs/mt5-installation-guide.md`
  MT5 のセットアップ手順。

- `../methods/swing_eval/docs/swing-evaluation-trading-system-spec.md`
  山谷評価トレードシステムの仕様。

## 記録ルール

- `reports/`
  実験ごとのレポートを置く。ファイル名は `00001_YYYY-MM-DD_slug.md` の通し番号形式にする。通し番号はファイルシステムの更新時刻(mtime)や本文の `更新日時` ではなく、レポート本文内の `日時: YYYY-MM-DD HH:MM JST` の昇順で決める。再採番・最新判断・既存レポート確認でも、必ずファイル内の `日時` を正とする。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。各レポートの冒頭には `日時: YYYY-MM-DD HH:MM JST` と `更新日時: YYYY-MM-DD HH:MM JST` を入れる。

## 再開手順(entry_ev 研究)

1. `../methods/entry_ev/docs/GOAL.md` で目的と取引ルールを確認する。
2. `../methods/entry_ev/docs/status.md` の「現在の状態」と「次の作業」を読む。
3. `../methods/entry_ev/docs/trading_ml_generalization_principles.md` のチェックリストを読む。
4. `../methods/entry_ev/docs/research_log.md` の最新エントリを読む。
5. 直近の実験がある場合は `reports/` の最新レポートを読む。最新判断はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、ファイル内の `日時` を基準にする。通し番号はその `日時` 順に由来する補助情報として扱う。
6. 作業前に、変更する仕様や新しい仮説を `../methods/entry_ev/docs/research_log.md` に記録する。
7. 作業後に、結果、スコア、失敗、次の一手を記録する。
