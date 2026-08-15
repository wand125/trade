# 00005 TitanFX live cost audit

日時: 2026-08-16 03:04 JST

## 目的

M15次足paper candidateの実測all-in round-trip costが、historical all-fold cost ceiling `0.05415/oz` 以下か確認する。売買やruntime変更は行わず、既存のライブsnapshot記録だけを根拠にする。

## 取得できたspread

`AGENTS.md` に記録された部分測定では、`runtime/events.jsonl` のEA snapshot 9,458件（2026-08-11〜2026-08-15）のXAUUSD-m bid/ask差は次の通りだった。

| metric | spread / oz |
|---|---:|
| minimum | 0.210 |
| median | 0.260 |
| p90 | 0.310 |
| historical all-fold cost ceiling | 0.05415 |

round tripでspreadを1回負担する前提では、中央値だけでceilingの約4.80倍である。M15 confidence 0.54以上のgross mean `+0.09781/oz` は中央値spreadの約37.6%に留まり、spread控除後の単純平均は `-0.16219/oz` となる。minimum spread `0.210/oz` でもceilingの約3.88倍であり、commissionやslippageを0と仮定してもadmission条件を満たさない。

## 未取得項目と再現性

commissionとslippageを計算できるdeal履歴は `/srv/trade/runtime` から取得できなかった。2026-08-16の確認時点では、同ディレクトリに元集計の `events.jsonl` も存在しないため、この作業コピーだけから9,458件の分位を再計算できない。数値はリポジトリ管理下の `AGENTS.md` に固定された実測記録を出典とし、取得できないcommission/slippageを推測で補完しない。

## 判断

M15次足単独policyはTitanFX XAUUSD-mで **reject / NoTrade** とする。spread単独でcost ceilingを超えるため、未取得のcommission/slippageを加えれば結論が改善する余地はない。`m15_paper_policy_v1.json` は研究再現用の固定candidateとして残すが、`live_action=no_trade` を維持し、authoritative予測、fair odds、paper/live execution policyへ昇格しない。loss multiplierは標準1.0のみで判断した。

commission/slippageのdeal履歴取得は、XAUUSD-m不採用を覆すためではなく、別銘柄または長い保有期間のall-in cost評価に再利用する診断として残す。次はspreadの薄い銘柄、または同じspreadをより長い値幅で吸収できる保有期間について、固定予測条件のgross edgeとcost ceilingを比較する。

## 出典

- live spread測定値とsample期間: `AGENTS.md`「現在の最優先事項」
- M15 gross meanとcost ceiling: `methods/next_bar_ev/docs/reports/00004_2026-08-07_standard_pnl_reassessment.md`
- 固定candidate: `methods/next_bar_ev/config/m15_paper_policy_v1.json`
