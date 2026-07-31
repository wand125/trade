# trade

XAUUSD の短期トレードを対象にした検証統合基盤。共通ライブラリとデータを共有しつつ、検証手法ごとに独立したスクリプト・ドキュメント・テストを持つ。

## 構成

```
src/                  共通ライブラリ(pythonpath)
├── trade_data/       データパイプライン・モデリング・バックテストエンジン
└── bridge/           MT5 と通信するローカル HTTP ブリッジ(標準ライブラリのみ)

methods/              検証手法(手法ごとに scripts / docs / tests を持つ)
├── entry_ev/         ML によるエントリー期待値予測の研究(オフライン)
│   ├── scripts/experiments/   実験スクリプト
│   ├── docs/                  GOAL.md、研究計画、仕様、研究ログ
│   │   ├── reports/           番号付き実験レポート(00001〜)
│   │   └── summary/ decisions/ templates/
│   └── tests/
└── swing_eval/       山谷評価トレード(MT5 ライブ運用)
    ├── analysis/              バックテスト・シグナル分析・監視スクリプト
    ├── mt5/                   EA・インジケーター・ストラテジーテスター設定
    ├── skills/                相場分析用スキル定義
    ├── docs/                  WORK.md(運用手順)、ブリッジ仕様、システム仕様
    └── tests/

data/                 共通データ(生成物は git 管理外)
runtime/              ライブ状態のスナップショット(git 管理外)
experiments/          実験の実行記録(git 管理外)
tests/                共通ライブラリ(trade_data / bridge)のテスト
```

## 実行規約

- すべてのスクリプトは**リポジトリルートをカレントディレクトリ**として実行する(`runtime/` や `data/` を相対参照するため)。
- 新しい検証手法を追加するときは `methods/<手法名>/` に scripts / docs / tests を作り、共通ロジックは `src/` へ置く。実験レポートは手法ごとに `methods/<手法名>/docs/reports/` に番号付きで蓄積する(記録ルールは各手法の docs/README.md に定める)。

## セットアップ

```bash
uv sync                                        # 共通ライブラリの依存関係
uv run --with pytest pytest                    # 全テスト実行(testpaths 設定済み)
python3 src/bridge/mt5_ai_bridge.py            # ブリッジ起動(ルートで実行)
```

## 入口

- 研究(entry_ev): [methods/entry_ev/docs/README.md](methods/entry_ev/docs/README.md)、[methods/entry_ev/docs/GOAL.md](methods/entry_ev/docs/GOAL.md)
- ライブ運用(swing_eval): [methods/swing_eval/docs/WORK.md](methods/swing_eval/docs/WORK.md)、[methods/swing_eval/docs/mt5-ai-bridge.md](methods/swing_eval/docs/mt5-ai-bridge.md)
