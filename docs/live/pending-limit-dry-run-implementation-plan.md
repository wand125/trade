# Pending Limit Dry-Run Implementation Plan

## 背景

現在のCodex-to-MT5注文連携は、`buy`、`sell`、`close`、`close_all` のみを扱う。
`buy` と `sell` は現在値での成行検証であり、指値価格を持つ pending order ではない。

そのため、現時点で安全に扱えるのは次の2種類に分かれる。

- 非実行の「指値候補」台帳: 価格、条件、TP/SL、無効化条件を記録するだけで、EAは発注しない。
- MT5 pending order の dry-run: `buy_limit` / `sell_limit` をEAまで通し、発注せずにバリデーション結果だけ返す。

実装は、誤発注リスクを避けるために候補台帳から始め、次にEA dry-runを追加する。

## 取得前提

READMEの運用方針に合わせ、通常の相場取得は `/analyze` ではなく `/snapshot` ベースにする。

- EAは `http://127.0.0.1:8765/snapshot` へ保存専用POSTを行う。
- Codexは `runtime/latest_snapshot.json` を主取得元として読み、M1/M5/M15/M30の足とインジケーターを直接評価する。
- 建玉、損益、約定履歴が必要なときだけ `runtime/latest_account.json` と `runtime/latest_deal_history.json` を併読する。
- `runtime/latest_context.md` は人間向け要約として補助的に使う。
- `runtime/latest_signal.json` と `/analyze` は保存状態確認または明示的なprovider-backed signalテスト用であり、通常の売買判断や候補評価には使わない。

## 現状の制約

- `bridge/create_trade_command.py` は `buy/sell/close/close_all` のみを受け付ける。
- `bridge/mt5_ai_bridge.py` の `TRADE_COMMAND_ACTIONS` も同じ4種類のみを許可する。
- `mt5/Experts/AI_Bridge_Advisor.mq5` は `buy/sell` を `Trade.Buy` / `Trade.Sell` の成行として処理する。
- 注文コマンドに `entry_price`、`order_type`、`trigger_condition` がない。
- `dry_run=true` は発注しないが、現状の検証価格は現在のBid/Askであり、指値価格ではない。

## 目標

1. 実注文を出さない指値候補を保存できるようにする。
2. 候補ごとに、参入価格、方向、TP、SL、無効化条件、期限、根拠を記録する。
3. 最新スナップショットに対して、候補が「未到達」「接近」「到達」「無効化」のどれかを判定できるようにする。
4. その後、EA側で `buy_limit` / `sell_limit` の dry-runバリデーションに対応する。
5. live pending order は明示的な追加実装まで無効にする。

## 運用時間軸

スキャル目的ではなく、M15/M30の流れを主軸にした短めの中期候補を扱う。
M1はエントリー直前の反発・失敗確認にだけ使い、数十秒から数分の値動きだけでは候補を作らない。
2026-07-03時点ではスキャル運用を一旦停止し、M15/M30の押し目・戻りを待つ運用を優先する。

- 監視主軸: M15 / M30
- 補助確認: M5
- トリガー確認: M1
- 候補期限: 原則30分から6時間
- 候補の更新理由: M15/M30の高値更新、安値割れ、EMA帯回復、主要サポート/レジスタンス到達
- 候補を作らない条件: M1だけの急騰急落、スプレッド拡大、直近高値/安値の中央で方向がない状態

## フェーズ1: 非実行の指値候補台帳

### 追加ファイル

- `bridge/create_limit_candidate.py`
- `runtime/limit_candidates.json`
- `runtime/latest_limit_candidates.md`

### 候補データ構造

```json
{
  "id": "uuid",
  "status": "watching",
  "created_at": 1783035000,
  "expires_at": 1783036800,
  "symbol": "XAUUSD-m",
  "side": "buy_limit",
  "entry_price": 4127.8,
  "take_profit": [4129.2, 4130.0, 4132.0],
  "stop_loss": 4126.4,
  "time_horizon": "M15-M30",
  "invalidation": "M1 close below 4126.4 or M5 fails below 4127.0",
  "confirmation": "M1下ヒゲ反発、Bidが4128.2回復、スプレッド80pt未満",
  "reason": "M5上昇中の押し目候補",
  "dry_run": true
}
```

### CLI仕様

```bash
python3 bridge/create_limit_candidate.py buy_limit \
  --symbol XAUUSD-m \
  --entry-price 4127.8 \
  --tp 4129.2 --tp 4130.0 --tp 4132.0 \
  --sl 4126.4 \
  --expires-in-seconds 1800 \
  --confirmation "M1反発確認" \
  --invalidation "M1 close below 4126.4" \
  --reason "押し目買い候補"
```

### 判定ロジック

- `buy_limit`
  - 接近: `ask <= entry_price + proximity`
  - 到達: `ask <= entry_price`
  - 無効化: 現在価格またはM1終値が `stop_loss` を下抜け
- `sell_limit`
  - 接近: `bid >= entry_price - proximity`
  - 到達: `bid >= entry_price`
  - 無効化: 現在価格またはM1終値が `stop_loss` を上抜け
- 期限切れ: `expires_at < now`
- 時間軸不一致: `time_horizon` が `M15-M30` の候補は、M1到達だけでは「到達」にせず、M5以上の反発または失敗確認を要求する。

### 出力

`runtime/latest_limit_candidates.md` に次を出す。

- 候補ID
- 方向
- 参入価格
- 現在Bid/Askとの差
- TP/SL
- 現在ステータス
- 到達時に見る確認条件
- 無効化条件
- 時間軸
- 期限までの残り時間

## フェーズ2: bridge注文コマンドのpending dry-run対応

### `create_trade_command.py`

追加するaction:

- `buy_limit`
- `sell_limit`

追加する引数:

- `--entry-price`
- `--order-expiration-seconds`

バリデーション:

- `buy_limit` は `entry_price < current ask` を基本条件にする。
- `sell_limit` は `entry_price > current bid` を基本条件にする。
- `sl` と `tp` は方向に対して正しい位置であること。
- `--live --confirm LIVE` がない限り `dry_run=true` のままにする。

### `mt5_ai_bridge.py`

- `TRADE_COMMAND_ACTIONS` に `buy_limit` と `sell_limit` を追加する。
- `load_trade_command()` で `entry_price` を保持する。
- `format_trade_result()` に `entry_price` と pending type を表示する。
- `latest_trade_result.json` に pending dry-run結果を保存する。

## フェーズ3: EA pending dry-run対応

### `AI_Bridge_Advisor.mq5`

追加する処理:

- `CheckTradeCommand()` で `entry_price` を読む。
- `action == "buy_limit" || action == "sell_limit"` を分岐する。
- `ExecuteCodexPendingCommand()` を追加する。

dry-run時:

- symbol許可
- 期限
- spread
- volume
- max positions
- SL/TP必須
- 指値価格とBid/Askの位置関係
- brokerの最小ストップ距離
- tick size丸め

上記だけ検証し、`Trade.BuyLimit` / `Trade.SellLimit` は呼ばない。

live時:

- 初期実装では拒否する。
- 将来有効化する場合は、`InpAllowCodexTrading=true` に加えて `InpAllowCodexPendingTrading=true` を別途要求する。

## フェーズ4: テスト

### Python側

`tests/test_bridge.py` に追加する。

- `buy_limit` / `sell_limit` が許可される。
- `entry_price` がないpending commandは拒否される。
- 期限切れpending commandは返却されない。
- candidate台帳の作成と期限切れ判定。
- `latest_limit_candidates.md` の生成。

### EA側

MT5 Strategy Testerまたはデモ環境で確認する。

- dry-run `buy_limit` は発注されず、`dry_run_passed` が返る。
- 不正なSL/TPは `rejected` になる。
- 不正な指値位置は `rejected` になる。
- live pendingは初期状態で拒否される。

## 安全条件

- フェーズ1の候補台帳はEAが読まないため、発注不能にする。
- フェーズ2以降もデフォルトは必ず `dry_run=true`。
- live化には `--live --confirm LIVE` とEA側inputの両方を要求する。
- pending order live化は成行liveとは別inputで保護する。
- コマンド期限は短くし、古い候補や古い注文を使わない。

## 実装順

1. `create_limit_candidate.py` を追加し、非実行の候補台帳を作る。
2. 候補台帳を最新スナップショットで評価し、Markdownに出力する。
3. テストを追加する。
4. `create_trade_command.py` に `buy_limit/sell_limit` と `entry_price` を追加する。
5. bridgeの許可actionと表示を更新する。
6. EAにpending dry-run検証を追加する。
7. MT5デモでdry-run結果を確認する。
8. live pendingは別途確認後に設計する。

## 非目標

- 初期実装ではMT5に実際のpending orderを置かない。
- 指値候補を自動で実注文へ昇格しない。
- AI mock signalを売買根拠として使わない。
- `/analyze` のprovider-backed signalを通常取得元にしない。
- 既存の成行dry-runの挙動を変えない。
