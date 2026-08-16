# 00011 Deal cost evidence audit

日時: 2026-08-16 10:00 JST

## 目的

report 00005以降に未取得だったcommission/slippageを、売買やBridge操作をせず既存artifactだけから実測できるか再監査する。値を推測せず、利用可能なMT5 schemaに合わせたoffline集計経路を固定する。

## 取得状況

`/srv/trade` の追跡・ignore済みファイルを横断したが、実約定を含む `runtime/latest_deal_history.json`、`runtime/latest_deal_history.csv`、`runtime/mt5_forward/swing_evaluation_trades.csv` は取得できなかった。現在の`runtime/`にある8ファイルはMT5 tester/archive statusだけで、deal/order exportは0件だった。

既存実装から確認できたschemaは次のとおり。

- Bridge deal履歴: `time, symbol, type, entry, volume, price, profit, commission, swap, magic`
- Forward CSV: `event, symbol, action, entry, deal_price, spread_points, latency_seconds, hold_seconds`等
- commissionはMT5口座通貨で記録されるため、symbolのcontract sizeと約定時点のaccount-to-quote換算率が別途必要
- entry slippageは計画`entry`と`deal_price`から方向付きで算出できるが、exitのrequested priceは現schemaにない

Bridgeへ履歴要求を出す既存scriptは`runtime/deal_history_request.json`へ書き、稼働EAとの連携を発生させる。この検証では`runtime/` read-only制約に従い実行していない。

## 追加した診断

`deal_cost_audit.py`を追加した。入力は既存Bridge JSONとForward CSVのみで、発注機能を持たない。

- commission price = `abs(commission) * account-to-quote rate / (lots * contract size)`
- entry/out両legが観測されたsymbolだけround-trip commission meanを出す
- 各deal行の時点別換算率を固定configより優先できる
- buy slippage = `deal_price - requested entry`
- sell slippage = `requested entry - deal_price`
- 不正値、未設定symbol、欠落legを件数化する
- exit requested price、spread join、fresh prediction edgeがない限り`all_in_cost_authorized=false`を固定する

テスト用の合成値では、JPY commission `-35`、換算率`0.01 quote/JPY`、0.1 lot、contract size 100に対して片leg `0.035`、往復`0.070` price unitsとなることを確認した。この値は計算式のtest fixtureであり、実口座コストではない。

## 判断

commission/slippageの実測値は **取得できず**。したがってall-in costは未確定で、FX shortlistを含む売買policyを認可しない。XAUUSD-m M15/M30はspread単独ですでにrejectであり、この不足によって既存判断は変わらない。

offline診断基盤は **accepted**。実deal exportとForward CSVが人間の運用手順で安全に配置された場合だけ再実行する。Bridge履歴要求、EA変更、売買、runtime書き込みはCodex側から行わない。

## 再現コマンド

```bash
uv run python methods/next_bar_ev/scripts/deal_cost_audit.py \
  --deal-history path/to/latest_deal_history.json \
  --forward-csv path/to/swing_evaluation_trades.csv \
  --config path/to/symbol_contract_and_conversion.json \
  --output experiments/next_bar_ev/deal_cost_audit.json
```

configは`symbols -> symbol -> contract_size_per_lot/account_currency_to_quote_rate`を持つ。換算率をdeal行へ`account_currency_to_quote_rate`として持たせれば、時点別値を優先する。

## 検証

- `tests/test_deal_cost_audit.py`: 4 passed
- `tests/test_spread_audit.py`: 4 passed
- 実口座・credentialを含む成果物: 追加なし
- `runtime/`変更: なし
