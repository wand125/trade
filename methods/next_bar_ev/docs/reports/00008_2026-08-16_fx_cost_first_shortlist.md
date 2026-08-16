# 00008 FX cost-first research shortlist

日時: 2026-08-16 09:32 JST

## 目的

XAUUSD-mではM15 baseline、固定保有延長、precision 0.55の全てが実spreadで不採用となった。別銘柄でモデルを作ってから同じ問題を発見することを避けるため、Titan FX公式spreadを測定優先順位だけに使い、実測bid/askを予測開発前に監査するcost-first手順を固定した。

## 公式情報による測定shortlist

Titan FX公式Forexページ（2026-08-16確認）は、Micro accountの平均spreadを次のように掲載している。

| priority | symbol | official Micro average spread |
|---:|---|---:|
| 1 | EURUSD-m | 1.40 pips |
| 2 | USDJPY-m | 1.53 pips |
| 3 | AUDUSD-m | 1.72 pips |
| 4 | EURGBP-m | 1.73 pips |
| 5 | GBPUSD-m | 1.77 pips |

これは予測可能性、bar値幅、slippage、利益率の順位ではない。公式値は時間帯別分布でもlive口座の実測でもないため、market-data取得の優先順位にだけ使う。実口座のaccount typeはこの研究作業コピーから確認せず、symbol suffixだけで推定しない。

Titan FX公式accountページでは、Standardはcommissionなし、Bladeはraw spreadに加えてUSD 3.5/100kの片道commissionとされる。したがって別account typeを評価する場合も、狭いspreadだけを比較せずround-trip commissionを価格単位へ換算する必要がある。

## 実測gate

`spread_audit.py` はbridge event JSONLの `ask - bid` を銘柄別価格差として集計する。無条件policyの事前gateを以下へ固定した。

- 最低5,000 valid snapshot
- 最低5 UTC日
- minimum / median / p90 / maximumと観測時間数を出力
- historical all-fold cost ceilingがある場合、p90 spreadがceiling以下であること
- commission、slippage、fresh prediction edgeが揃うまで `all_in_cost_authorized=false`
- malformed JSON、時刻不明、symbol欠損、非有限/非正bid、ask < bidはinvalidとして除外・件数記録

p90 gateはspreadの広い時間帯を除くruleがまだ存在しない無条件policy向けである。時間帯filterを結果後に作らず、必要なら別の事前固定policyとしてfresh dataで検証する。

## 判断

EURUSD-m、USDJPY-m、AUDUSD-m、EURGBP-m、GBPUSD-mを **market-data measurement shortlist** として採用する。モデル学習、prediction candidate、paper/live policy、銘柄採用は認可しない。最初にbid/askを同一方式で5日・5,000件以上集め、spread p90、commission、slippageとbar値幅を確認する。

現時点では `/srv/trade` に他銘柄の研究OHLC・spread JSONLがなく、実測screenは取得できず。推測値でcost ceilingや期待利益を埋めない。XAUUSD-mのNoTrade、authoritative予測、fair odds、既存policyは変更しない。

## 成果物

- shortlist: `methods/next_bar_ev/config/fx_cost_first_research_shortlist_v1.json`
- 診断: `src/trade_data/spread_audit.py`
- CLI: `methods/next_bar_ev/scripts/spread_audit.py`
- test: `tests/test_spread_audit.py`
- 公式spread: `https://www.titanfx.com/trading-instruments/forex`
- account/commission: `https://titanfx.com/trading-accounts`
