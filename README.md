# trade

XAUUSD の短期トレードを対象にした統合ワークスペース。オフラインの予測研究基盤と、MT5 と連携するライブ運用環境を 1 つのリポジトリで管理する。

## 2 つの柱

### 研究基盤(オフライン)

XAUUSD の短期チャートデータを使ったトレード予測の研究・バックテスト。目標と取引ルールは [GOAL.md](GOAL.md)、パイプラインの詳細は [docs/research/pipeline.md](docs/research/pipeline.md) を参照。

- `src/trade_data/` — データパイプラインとモデリングのパッケージ(`trade-histdata` などの CLI を提供)
- `scripts/experiments/` — 実験用スクリプト
- `experiments/` — 実験の実行記録(git 管理外)
- `docs/` — 研究計画・実験プロトコル・調査レポート

### ライブ運用(MT5 連携)

MT5 EA からスナップショットを受け取り、保存済みデータを読んで相場分析・dry-run・Forward 検証を行う環境。運用手順は [WORK.md](WORK.md)、ブリッジの仕様は [docs/live/mt5-ai-bridge.md](docs/live/mt5-ai-bridge.md)、ワークスペース全体の解説は [docs/live/fx-workspace.ja.md](docs/live/fx-workspace.ja.md) を参照。

- `bridge/` — MT5 と通信するローカル HTTP ブリッジ(標準ライブラリのみ)
- `analysis/` — バックテスト・シグナル分析・監視スクリプト群
- `mt5/` — EA・インジケーター・ストラテジーテスター設定
- `runtime/` — ライブ状態のスナップショット置き場(git 管理外)
- `skills/` — 相場分析用スキル定義

## 共通

- `data/` — 研究データと MQL5 製品調査データ(生成物は git 管理外)
- `tests/` — 両方のテストスイート(`pytest` をリポジトリルートで実行)
- ブリッジや分析スクリプトはこのリポジトリルートをカレントディレクトリとして実行する(`runtime/` を相対参照するため)

## セットアップ

```bash
uv sync                      # 研究側の依存関係(ライブ運用側は標準ライブラリのみ)
uv run pytest tests/         # テスト実行
python3 bridge/mt5_ai_bridge.py   # ブリッジ起動(ルートで実行)
```
