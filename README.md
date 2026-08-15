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
├── swing_eval/       山谷評価トレード(MT5 ライブ運用)
│   ├── analysis/              バックテスト・シグナル分析・監視スクリプト
│   ├── mt5/                   EA・インジケーター・ストラテジーテスター設定
│   ├── skills/                相場分析用スキル定義
│   ├── docs/                  WORK.md(運用手順)、ブリッジ仕様、システム仕様
│   └── tests/
├── next_bar/        M1/M5/M15/M30 の次足方向と校正済み信頼度の研究
│   └── docs/                  目的、評価仕様、実行手順
├── next_bar_ev/     次足方向オッズを値幅・tail risk・売買候補へ変換する独立層
│   └── docs/                  EV/overlayの評価仕様と採用判断
└── manual/           人(自分)による裁量トレード
    └── docs/                  原則・プレイブック・失敗カタログ・トレード記録(journal/)

data/                 共通データ(生成物は git 管理外)
runtime/              ライブ状態のスナップショット(git 管理外)
experiments/          実験の実行記録(git 管理外)
tests/                共通ライブラリ(trade_data / bridge)のテスト
```

## 作業コピーの運用(2026-08-16 確立)

**このリポジトリは実験からライブトレードまでを1本で扱うモノレポ**。ただし**同一マシン上に2つの作業コピー**を置き、役割で分けている。**リポジトリを分けるのではなく、作業コピーを分ける**。

| 作業コピー | 役割 | 主な担当 | 触るディレクトリ |
|---|---|---|---|
| **`/mnt/c/Users/user1/trade`**(Windows FS) | **ライブ運用系** | Claude(相談・運用セッション) | `methods/manual/`、`methods/swing_eval/mt5/`、`src/bridge/`、`campaign.md`、`issues.md` |
| **`/srv/trade`**(WSLネイティブFS) | **研究開発系** | Codex | `methods/next_bar*/`、`methods/entry_ev/`、`src/trade_data/`、`tests/test_next_bar*.py` |

**なぜ2つ必要か**:

- **ライブ側は Windows FS でなければならない**。MT5・EA・ブリッジが Windows で動き、`runtime/` を直接読み書きするため
- **研究側は WSL ネイティブFSでなければ遅い**。`experiments/` は13GB規模で、`/mnt/c` 越しのI/Oでは実用にならない
- **git管理外のものが両者で全く違う**。`runtime/`(ライブ状態)は `/mnt/c` にしか無く、`experiments/` と `data/`(学習成果物)は `/srv` にしか無い。**これらは .gitignore なので同期されないし、させる必要もない**

**共有されるのは git 管理下のコードとドキュメントだけ**。実測(直近30コミット)でも触るパスは重なっていない — `/mnt/c` は `methods/manual/docs` 中心、`/srv` は `methods/next_bar/docs` と `src/trade_data/` 中心。

### 同期の型

```bash
# ライブ側で書いたドキュメント・設定を幹へ
git push origin main

# 研究側へ取り込む(下記の注意を読むこと)
cd /srv/trade && git fetch origin main
git merge FETCH_HEAD                      # 幹に追従する場合
git checkout FETCH_HEAD -- <path>         # 特定ファイルだけ取る場合(推奨)

# 研究成果を幹へ戻すときは /srv から push し、ライブ側で pull
```

**注意: `/srv/trade` は single-branch クローン**(2026-08-16 実測)。fetch refspec が
`+refs/heads/agent/m30-directional-clarity:refs/remotes/origin/agent/m30-directional-clarity`
に限定されているため、**素の `git fetch origin` では `origin/main` が取れない**(`fatal: invalid reference: origin/main` になる)。
**ブランチ名を明示して `git fetch origin main` とし、`FETCH_HEAD` を使う**。
恒久的に直すなら `git remote set-branches --add origin main` を打つ。

**取り込みは「必要なファイルだけ」を既定とする**。研究側の作業ブランチへ幹をフルマージすると、
裁量トレードのドキュメントが研究の履歴に混ざり、Codex がそのブランチを push したときに差分が読めなくなる。

**作業開始時に `git fetch origin main` を打つ**。両側が同じ幹を見ていることを確認してから作業する。

### モノレポゆえの注意

- **発注コードは研究側の作業コピーにも存在する**(`src/bridge/create_trade_command.py`)。`AGENTS.md` で Codex に売買を明文で禁止しているのはこのため
- ただし `/srv/trade/runtime/` にはライブのファイル(`latest_account.json` / `trade_command.json`)が無く、MT5テスターの成果物しか無い。**構造上、研究側から誤って実弾に触れる経路は塞がっている**
- **衝突しうるのは `src/` と `tests/` のみ**。`src/bridge/`(ライブ側)と `src/trade_data/`(研究側)でサブディレクトリが分かれているが、共通ライブラリを触るときは相手側の未pushを確認する

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
- 次足予測(next_bar): [methods/next_bar/docs/README.md](methods/next_bar/docs/README.md)、[methods/next_bar/docs/GOAL.md](methods/next_bar/docs/GOAL.md)
- 次足EV(next_bar_ev): [methods/next_bar_ev/docs/README.md](methods/next_bar_ev/docs/README.md)、[methods/next_bar_ev/docs/GOAL.md](methods/next_bar_ev/docs/GOAL.md)
- ライブ運用(swing_eval): [methods/swing_eval/docs/WORK.md](methods/swing_eval/docs/WORK.md)、[methods/swing_eval/docs/mt5-ai-bridge.md](methods/swing_eval/docs/mt5-ai-bridge.md)
- 裁量トレード(manual): [methods/manual/docs/README.md](methods/manual/docs/README.md)
