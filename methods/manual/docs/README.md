# methods/manual/docs — 何を見るか

## 現役(判断に使う)

| ファイル | 中身 | 誰が書くか |
|---|---|---|
| **`campaign.md`** | **生きている作戦**。シーシス・サイズ・無効化条件・トレーリング基準 | 本人 + Claude(経過記録) |
| **`ops_runbook.md`** | 運用セッションの手順。委任済み執行と対応表 | Claude |
| `claude/conclusions.md` | **合意済みリスクパラメータと確定事実**。相談前に必ず読む | Claude |
| `claude/proposals.md` | 未処理の提案(Issue扱い、P番号) | Claude |
| `claude/mistakes.md` | **Claude自身の反復失敗**(C番号)と、それを止める手順 | Claude |
| `market_hours.md` | 開場・閉場の実測値 | Claude |
| `principles.md` / `playbook.md` / `mistakes.md` / `journal/` | **本人の考察専用。Claudeは書かない** | 本人 |

## アーカイブ(**現在の判断には使わない**)

| ファイル | 中身 |
|---|---|
| `archive/campaign_closed.md` | 終了・失効した作戦(01〜07) |
| `archive/ops_runbook_retired.md` | 失効した委任・対応表の行 |

## アーカイブへ移すルール

**終わったものはその場で移す。溜めない。**

- **作戦**: 決済完了 / 失効 / 撤回 のいずれかになったら `archive/campaign_closed.md` へ。結果(損益)と理由を1行残す
- **運用手順**: 対象の決済・委任の解除・参照作戦の終了で `archive/ops_runbook_retired.md` へ
- **取り消し線で残さない**。無効な行が現役ファイルに居座ると、古い水準やチケット番号を現在の判断に持ち込む事故になる
- 日付つきの一時的な節(「本日の指標」等)も、その日を過ぎたら移す

## 相談セッションが読む順序

1. `claude/conclusions.md` — 合意済みパラメータ
2. `campaign.md` — 現在の作戦
3. `runtime/latest_account.md` / `latest_context_<銘柄>.md` — ライブの口座と相場(**古ければ鮮度を指摘する**)
4. 高重要指標の日時(週初または作戦開始時に確認)
