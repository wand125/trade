# FX Workspace Notes

## 目的

このワークスペースは、MT5からXAU/USDの最新スナップショットを受け取り、Codexが保存済みデータを読んで相場状況や短期の流れを分析するために使う。

## ブリッジ起動

このディレクトリで起動する。

```bash
python3 bridge/mt5_ai_bridge.py
```

Codexが相場の流れを読むだけなら、EAは`/snapshot`へ保存専用POSTを行う。OpenAI/Claude APIキーやブリッジ側のAI判断は不要。Codexが`runtime/`の価格・足・口座情報を読んで判断する。
通常の相場確認では`/analyze`を取得元にしない。Codexは保存済みの`runtime/latest_snapshot.json`、`runtime/latest_account.json`、`runtime/latest_context.md`を直接読む。

## MT5からCodexまでの流れ

1. MT5 EAが`http://127.0.0.1:8765/snapshot`へスナップショットをPOSTする。
2. ブリッジはAI判断をせず、以下を書き出す。
   - `runtime/latest_snapshot.json`
   - `runtime/latest_context.md`
   - `runtime/latest_signal.json`  保存専用ステータス
   - `runtime/latest_account.json`
   - `runtime/latest_account.md`
   - `runtime/events.jsonl`
3. Codexは相場確認を頼まれたら、`runtime/latest_snapshot.json`を主取得元として読み、必要に応じて口座情報や要約を併読する。

## 保存と判断の分離

通常運用ではEA入力を以下にする。

- `InpBridgeUrl = http://127.0.0.1:8765/snapshot`
- `InpSaveOnlyMode = true`
- `InpRequestOnlyFromMatchingChart = true`
- `InpPollCodexTradeCommands = false`
- `InpEnableTrading = false`

EAはM1チャート1つにだけ載せる。M5/M15/M30は`timeframes`として同じスナップショットに含まれるため、複数チャートへEAを載せる必要はない。

`/analyze`はOpenAI/Claudeへ即時シグナル生成を依頼したい場合だけ使う。通常の相場判断と建玉確認は、`/snapshot`で保存されたファイルをCodexが読んで行う。

## 24時間履歴の取得

ユーザーから「21時半以降」「過去24時間」「履歴も見て」などの依頼があり、通常の直近スナップショットだけでは足りない場合は、次を実行する。

```bash
python3 bridge/request_history.py 24
```

EAは次回ポーリング時にM1/M5/M15/M30の24時間分を送る。ブリッジは取得できた履歴を以下へ保存する。

- `runtime/latest_history_24h.json`
- `runtime/latest_history_24h_context.md`

取得完了後は`runtime/history_request.done.json`で完了時刻を確認できる。

## Codex分析トリガー

相場状況や流れの確認では`market-flow-analysis`スキルを使う。EAが複数時間足送信に対応している場合、`runtime/latest_snapshot.json`の`timeframes`配下にM1/M5/M15/M30が保存される。
取得基準は`runtime/latest_snapshot.json`を最優先にし、建玉や損益を確認するときだけ`runtime/latest_account.json`も併読する。`runtime/latest_context.md`は人間向け要約として補助的に使う。`runtime/latest_signal.json`は保存状態の確認用であり、通常の売買判断には使わない。

想定プロンプト:

```text
XAU/USDの流れを見て
相場状況を確認して
runtime/latest_snapshot.jsonを見て短期分析して
数分足の状況を読んで
```

標準の分析項目:

- 現在のBid/Askとスプレッド
- M1の短期フロー
- M5の短期トレンド確認
- M15/M30の大きめの流れ
- 保存されている足全体でのレンジと方向感
- EMA、RSI、ATR
- サポート、レジスタンス、否定ライン
- 上抜け・下抜け時のシナリオ
- 追いかける場面か、待つ場面か

現在の取引やポジション確認では`runtime/latest_account.md`または`runtime/latest_account.json`を読む。

## Codexからの注文コマンド

注文コマンドは通常停止する。使う場合だけEA入力`InpPollCodexTradeCommands=true`にし、デフォルトでdry-runにする。まずEA側で検証だけ行い、`runtime/latest_trade_result.md`を確認する。

例:

```bash
python3 bridge/create_trade_command.py buy --symbol XAUUSD-m --volume 0.01 --sl 4100 --tp 4120
```

実発注は以下を満たす場合だけ行う。

- ユーザーが明示的に実発注を依頼している
- EA入力`InpPollCodexTradeCommands=true`
- EA入力`InpAllowCodexTrading=true`
- CLIで`--live --confirm LIVE`を付ける
- SL/TP、スプレッド、ロット、期限、対象シンボルのチェックに通る

`InpEnableTrading=false`を維持する。売買自動化を試す場合でも、最初はデモ口座で検証する。
