# 00005 TitanFX 実スプレッドの実測と cost ceiling 判定

作成: 2026-08-16 / 対象: `next_bar_ev` docs/status.md「次の検証1」

## 目的

`m15_paper_policy_v1` の採用可否は round-trip cost に支配されている。00004 までで判明していた条件は次の通り。

- confidence 0.54以上: 17,354件、accuracy 54.30%、**gross mean `+0.09781/oz`**、6/6 OOS fold positive
- **round-trip cost 0.05 後**: net mean `+0.04781`、6/6 fold positive
- **all-fold cost ceiling `0.05415/oz`**、headroom は `0.00415` しかない
- round-trip cost 0.10 後: net mean `-0.00219`、positive fold 4/6

したがって「TitanFX の実コストが `0.05415/oz` 以下か」が唯一の分岐点だった。

## 方法

`runtime/events.jsonl` を使う。これは MT5 の EA が送ったスナップショットの生ログで、1行が1観測、`bid` と `ask` を持つ。**スプレッドは `ask - bid` として直接計算できる**(EA の `spread_points` を経由しないので単位換算の誤りが入らない)。

再現コード:

```python
import json, datetime, collections
rows = collections.defaultdict(list)
for line in open('runtime/events.jsonl', encoding='utf-8', errors='replace'):
    d = json.loads(line)
    b, a, s, t = d.get('bid'), d.get('ask'), d.get('symbol'), d.get('received_at')
    if None in (b, a, s, t):
        continue
    rows[s].append((t, a - b))
```

セッション区分は `received_at`(epoch秒)を JST の時刻に変換して行った。

## 結果

**XAUUSD-m, n=9,458, 2026-08-11 17:44 〜 2026-08-15 05:55 JST**

| 統計量 | スプレッド(USD/oz) |
|---|---|
| 最小 | **0.210** |
| p25 | 0.220 |
| **中央値** | **0.260** |
| p75 | 0.290 |
| p90 | 0.310 |
| 最大 | 4.060(週次クローズ前後を含む) |

セッション別(中央値 / p75 / p90):

| セッション | n | 中央値 | p75 | p90 |
|---|---|---|---|---|
| 東京 09-15 JST | 2,021 | 0.280 | 0.310 | 0.330 |
| 欧州 16-21 JST | 2,174 | 0.240 | 0.280 | 0.310 |
| NY 21-02 JST | 2,320 | 0.240 | 0.280 | 0.310 |

参考: USDJPY-m, n=9,268 は中央値 **0.013**(= 1.3 pips)、p90 0.014 で安定していた。

## 判定

**cost ceiling `0.05415/oz` に対し、観測された最小スプレッドですら `0.210/oz` で約3.9倍、中央値 `0.260/oz` では約4.8倍。**

- gross mean `+0.09781/oz` は**スプレッド中央値の 38%** しかない
- 00004 の感度分析では cost 0.10 で既に net mean `-0.00219`(positive fold 4/6)だった。**実コストはその 2.6 倍**
- commission と slippage は未計上であり、**加えれば差はさらに開く**(スプレッドだけで既に判定は覆らない)

**結論: `m15_paper_policy_v1` は XAUUSD-m / TitanFX では成立しない。`live_action=no_trade` を維持し、cost 前提の再検討なしに live へ上げない。**

この判定は方向モデルの否定ではない。**方向 edge(accuracy 54.30%, 6/6 fold positive)は残っている**。否定されたのは「その edge を M15 の次足1本で回収する」という**回収経路**である。

## 限界(明示)

- 標本期間は **4.5日(8/11〜8/15)のみ**。季節性・イベント日の影響を評価していない
- EA のスナップショット周期(30秒既定)でのサンプルであり、**ティックデータではない**。約定判定に使える粒度ではない
- **commission と slippage は未測定**。deal 履歴(`runtime/latest_deal_history.json`)から別途算出できる
- 最大 4.060 は週次クローズ前後を含むため、通常時の上振れ幅としては読めない

## 次に取るべき道

判定が「回収経路の否定」である以上、次は**コストに対して edge を大きくする方向**になる。候補:

1. **保有期間を延ばす**。次足1本ではなく N 本先まで持てば、コストは一定のまま gross が伸びうる。00003 の entry delay 検証と接続する
2. **スプレッドの薄い銘柄で測る**。USDJPY-m は中央値 0.013(価格比 **0.0082%**)、XAUUSD-m は 0.260(価格比 **0.0059%**)。**価格比ではむしろ金の方が薄い**ため、単純な銘柄変更では解けない可能性が高い。方向モデルの gross edge を価格比で表現し直して比較する必要がある
3. **confidence 閾値を上げて gross mean を稼ぐ**。ただし coverage が落ちるため selection score での評価が要る

**1 が本命**。2 は「金のスプレッドが厚いから駄目」という直感が価格比では成立しないことを示しており、銘柄選択では解決しない。
