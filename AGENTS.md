# AGENTS.md — Codex 向けプロジェクト指示

このファイルは **Codex(ゴール駆動の研究・開発担当)** 向け。Claude 向けの指示は `CLAUDE.md` にある。両方を読んでよいが、**役割が違う**。

## このリポジトリは実弾口座につながっている

Titan FX 口座 **9181575**(JPY建て、実残高 約38万円)がライブで動いている。MT5・EA・ブリッジは Windows 側で稼働中。

**Codex は絶対に売買を行わない。**

- `python3 src/bridge/create_trade_command.py` を **live で実行しない**(`--live --confirm LIVE` は禁止)
- `runtime/trade_command.json` を直接書かない
- MT5・EA の設定を変更しない
- ブリッジ(`src/bridge/mt5_ai_bridge.py`)を停止・再起動しない

**発注・決済・EA設定・ブリッジ運用はすべて人間と Claude セッションの領分**。Codex の担当は**研究とプログラム開発**であって、執行ではない。dry-run であっても実機へコマンドを送る操作は行わない。

`runtime/` 配下は**読み取り専用**として扱う。ライブの口座・ポジション・相場が入っており、書き換えると監視が壊れる。

## Codex の担当領域

系統的トレードの研究・開発。3つのトラックがある。

| トラック | 場所 | 目的 | 最終更新 |
|---|---|---|---|
| `entry_ev` | `methods/entry_ev/` | エントリー期待値のML研究。selector surface / replacement 診断 | 2026-07-03 |
| `next_bar` | `methods/next_bar/` | 次足方向モデル(M1/M5/M15/M30)と校正済み確率・オッズ | 2026-08-11 |
| `next_bar_ev` | `methods/next_bar_ev/` | 方向確率を売買可能な期待値へ変換する独立層 | 2026-08-07 |

`methods/swing_eval/` は MT5 ライブ側(EA)、`methods/manual/` は裁量トレードの知見。**この2つは Codex の担当外**(EA のコードを読むのは可、変更は人間の配備手順を通す)。

## ゴール駆動の進め方

各トラックは同じ文書構造を持つ。**この構造を壊さない**。

- `docs/GOAL.md` — そのトラックの完成条件。**書き換えるのは人間の判断があるときだけ**
- `docs/status.md` — 現在の状態と「次の検証」。**作業したら必ず更新する**
- `docs/reports/` — 連番の検証レポート(`00001_YYYY-MM-DD_主題.md`)。**1検証=1レポート**
- `docs/decisions/`(entry_ev のみ) — 方法論上の決定(ADR形式)
- `config/` — 固定した policy / candidate の JSON

**作業の型**:

1. `docs/status.md` の「次の検証」から1つ取る
2. 実行し、**採用(accepted)/棄却(reject)/shadow・candidate 止まり**のどれかを明示して結論づける
3. レポートを `docs/reports/` に連番で追加する
4. `docs/status.md` の「現在の状態」と「次の検証」を更新する
5. コミットする

**結論の書き方の原則**(既存レポートに一貫している。踏襲すること):

- **標準判断は `NoTrade`**。条件を満たさない限り採用しない
- **診断基盤(infrastructure)の採用と、policy の採用を分ける**。「診断としては accepted、policy としては reject」は正当な結論であり、実際に多い
- **改善が1 target・1 fold に集中しているものを「再現した」と書かない**
- **探索後に選んだ candidate 同士の比較を昇格の根拠にしない**
- 未来情報を使わない chronological OOS で評価する。**生の OHLC 価格水準を特徴量に入れない**(ガード実装済み)

## 実行環境

- 実行はリポジトリルートを cwd とする
- テスト: `uv run --with pytest pytest`
- 共通ライブラリは `src/`、データは `data/`、実験成果物は `experiments/`
- Python は `.venv/` にある

## 現在の最優先事項(2026-08-16 時点)

`next_bar_ev/docs/status.md` の「次の検証1」= **TitanFX の実コストを 1 oz 往復価格差へ換算し、cost ceiling `0.05415/oz` 以下か測る**。

**この測定は 2026-08-16 に部分的に実施済みで、結果は否定的**:

- `runtime/events.jsonl`(EAスナップショット 9,458件、2026-08-11〜08-15)の bid/ask から XAUUSD-m の実スプレッドを集計した結果、**中央値 0.260/oz、最小 0.210、p90 0.310**
- **cost ceiling 0.05415/oz の約4.8倍**。confidence 0.54以上の gross mean `+0.09781/oz` はスプレッド中央値の **38%** しかない
- したがって **M15 次足単独 policy は、この銘柄・このブローカーでは成立しない**
- 残る作業: commission と slippage の実測(deal 履歴から)、および**スプレッドの薄い銘柄・より長い保有期間で edge が残るか**の検討

詳細と再現コードは `methods/next_bar_ev/docs/reports/` の該当レポートを参照(未作成なら、これを最初のタスクとしてレポート化してよい)。

## 記録の原則

- **事実の主張には出典を持たせる**(ファイル・`runtime/`・git のいずれか)。会話にのみ現れる数値は無効
- 取得できなかったものは **「取得できず」と書く**。推測で数字を埋めない
- 数字を出すときは**サンプル数と期間**を添える
