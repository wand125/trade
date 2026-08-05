# 運用セッション手順書(ops runbook)

軽量モデルの別セッションが、トレードの定期監視・報告・委任済み執行を担うための手順書。**相談・議論・分析はこのセッションの仕事ではない** — 求められたら「相談セッションで」と案内する。

最終更新: 2026-08-05 20:45 JST(相談セッションが引き継ぎ時点の状態で記載)

## 役割の境界

- **やること**: 監視Monitorの維持、15分ダイジェスト報告、水準・指標アラート対応、**下記の委任済みルールの執行のみ**、約定・執行の campaign.md 経過記録への追記とコミット
- **やらないこと**: 新規エントリー、委任外の判断、サイズ・作戦の変更、分析・議論(→相談セッションへ)、ルールにない事態への対処(→本人へ報告して指示待ち)
- 迷ったら: **何もせず報告**。サーバー側SL/TPが最後の防衛線として常駐している

## 引き継ぎ実施記録

- 2026-08-05 20:56 JST: 運用セッション稼働開始。ブリッジhealth OK、Monitor起動(brsts8b4e)。本人確認: 相談セッション側Monitor停止済み(二重執行防止確認完了)

## 現在の状態(引き継ぎ時点)

- 口座: Titan FX 9181575。残高401,405円(仮想A: USDJPY 20万 / 仮想B: XAUUSD 20万)
- **保有ポジション(作戦01)**: USDJPY-m ショート計40ロット @157.81(2026-08-05 17:33約定)
  - ticket **89704811**: 20ロット SL **157.81(建値)** TP 157.20
  - ticket **89704860**: 20ロット SL **157.81(建値)** TP 155.80
  - 建値ストップ移動済み(20:21実施)— **実質リスクゼロ**
- 詳細: `methods/manual/docs/campaign.md` 作戦01 / リスクパラメータ等: リポジトリ直下 `CLAUDE.md`

## 起動手順

1. ブリッジ稼働確認: `curl -s -m 3 http://127.0.0.1:8765/health`(落ちていれば `nohup python3 src/bridge/mt5_ai_bridge.py > runtime/bridge_stdout.log 2>&1 &`)
2. 監視Monitorを起動(persistent):

```
python3 -u methods/manual/scripts/runtime_watch.py --interval 12 --digest-minutes 15 --stale-seconds 240 --level-cooldown 900 --levels "USDJPY-m:157.15,USDJPY-m:158.10,XAUUSD-m:4131,XAUUSD-m:4100" --events "2026-08-05T23:00|米ISM非製造業PMI;2026-08-07T21:30|米雇用統計(NFP+失業率)" 2>&1
```

(157.51は建値移動済みのため水準から除外済み。作戦が変わったら相談セッションの指示で水準を更新)

3. 起動したら本人に「運用セッション稼働開始」を報告。**相談セッション側のMonitor停止を本人経由で確認**(二重執行防止 — 両セッションが同時にルール執行すると決済・修正が二重になる)

## イベント別対応表

| イベント | 対応 |
|---|---|
| DIGEST(15分) | 1〜2行で報告(USDJPY・金・含み損益)。変化なしなら「変化なし」と一言 |
| POSITIONS 2→1 | **TP1約定(157.20、+約1.2万円)の可能性大**。runtime/latest_account.md で確認 → 残玉(89704860)のSLを157.50へ: `python3 src/bridge/create_trade_command.py modify --symbol USDJPY-m --ticket 89704860 --sl 157.50 --expires-in-seconds 120 --reason "campaign01 rule4b trail after TP1" --live --confirm LIVE` → 結果確認・campaign経過記録に追記・報告 |
| POSITIONS 1→0 / 2→0 | 決済完了(TP2 or 建値ストップ)。deal内容を確認し報告+campaign記録。**新規注文は置かない** |
| LEVEL_UP 158.10 | 警戒モード: USDJPYのM15終値を追跡(snapshotのM15 bars)。**終値が158.10超で2本連続確定したら両玉を成行決済**: `create_trade_command.py close --symbol USDJPY-m --ticket <番号> --expires-in-seconds 120 --reason "campaign01 primary defense confirmed band break" --live --confirm LIVE` を各ticketに実行 → 報告。スパイクの一時突き抜け(M15終値が戻る)なら決済せず報告のみ |
| LEVEL_DOWN 157.15 | 円高再開の確認。報告のみ(ポジションはTPに向かって順行中のため行動不要) |
| EVENT_WARN(指標60分前/10分前) | 本人に通知。ISM(8/5 23:00)は跨ぐ方針決定済み。**NFP(8/7 21:30)の扱いは未決 — 木曜までに相談セッションで決まる予定。金曜21:00までに指示がなければ本人へ確認** |
| SYMBOL_STALE / DATA_STALE | 報告。5分以上続けばEAログ確認(`MT5ログ: ~/Library/Application Support/net.metaquotes.wine.metatrader5/drive_c/Program Files/MetaTrader 5/MQL5/Logs/`)。チャート時間足がM1以外になっていたら本人にM1復帰を依頼 |
| BALANCE 変化 | 決済損益 or 入出金。内容確認して報告 |

## チャート運用の注意(本人へ随時案内してよい)

- EA付きチャート(XAUUSD-m M1 / USDJPY-m M1)は**データ供給専用・M1固定**。時間足を変えるとEAがpassive化し監視が盲目になる(8/5に2回発生)。時間足を見たいときはEAなしの別チャートを開いてもらう

## 夜間ウォッチ

本人が就寝宣言+当夜ルールを伝えた場合のみ: campaign.md 就寝時ルール欄に記入してから、防御行動(決済・削減)に限り確認なしで実行可。新規・増ロットは不可。詳細はリポジトリ CLAUDE.md「夜間ウォッチ」節。

## 報告様式

- ダイジェスト: `**定期報告(HH:MM:SS)**: USDJPY xxx.xx(建値±Xpips)/ 金 x,xxx / 特記事項`
- 執行報告: 何を・なぜ(どのルール)・結果(チケット・価格)・次の状態
- 時刻はウォッチャー出力のタイムスタンプをそのまま使う(推定時刻を書かない)

## 禁止事項(リポジトリCLAUDE.mdの心構えより)

- 事実の顔をした創作・メタ的な演出の出力(心構え11・12)
- 出典のない数値・時刻の記載
- 委任外のlive発注(発注経路の権限があっても、ルールにない操作はしない)
