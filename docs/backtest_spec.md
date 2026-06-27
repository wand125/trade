# Backtest Specification

## 目的

GOAL.md の取引ルールを、コードで再現できる仕様に落とす。

## データ粒度

初期実装は M1 を基準にする。

- 予測は、ある bar が確定した後に行う。
- 約定は次の bar の open で行う。
- これにより、同じ bar の future high/low/close を使った将来リークを避ける。

M5 は学習や特徴量確認に使えるが、最初の厳密なバックテストは M1 で行う。

Tick は次段階で、Bid/Ask、スプレッド、約定価格の現実性を検証するために使う。

## 状態

各時点の状態:

- `flat`: ポジションなし
- `long`: ロングを 1 オンス保有
- `short`: ショートを 1 オンス保有

保持する情報:

- direction
- entry_timestamp
- entry_price
- max_exit_timestamp
- holding_minutes
- unrealized_pnl

## 行動

`flat` のとき:

- `enter_long`
- `enter_short`
- `stay_flat`

`long` または `short` のとき:

- `hold`
- `close`

ポジション保有中の新規エントリーは禁止。

## 強制決済

エントリーから 24 時間が経過したポジションは強制決済する。

M1 の場合:

- 最大保有 bar 数は 1440。
- timestamp が `entry_timestamp + 24h` 以上になった最初の約定可能 bar で決済する。
- データ gap によってちょうど 24 時間後の bar が存在しない場合、次に存在する bar で決済する。

## 損益計算

サイズは 1 オンス固定。

ロング:

```text
raw_pnl = exit_price - entry_price
```

ショート:

```text
raw_pnl = entry_price - exit_price
```

補正後損益:

```text
adjusted_pnl = raw_pnl * 0.9  if raw_pnl > 0
adjusted_pnl = raw_pnl * 1.3  if raw_pnl < 0
adjusted_pnl = 0              if raw_pnl = 0
```

初期実装では `adjusted_pnl` を主スコアにする。

## 初期実装

実装ファイル:

- `src/trade_data/backtest.py`

CLI:

```bash
python -m trade_data.backtest run --month 2025-01 --strategy ma_cross
python -m trade_data.backtest benchmark --month 2025-01
```

成果物:

- `trades.csv`
- `equity_curve.csv`
- `metrics.json`
- `config.json`

## 月次評価

任意の 1 か月を評価対象にできるようにする。

月次スコアに含めるもの:

- total adjusted pnl
- total raw pnl
- trade count
- win rate
- average adjusted pnl per trade
- profit factor
- max drawdown
- exposure time
- long trade count
- short trade count
- forced exit count
- average holding time
- median holding time

月またぎポジションの扱い:

- 初期仕様では、評価月内にエントリーした取引を対象にする。
- 決済が翌月に出る場合も、その取引の損益はエントリー月に帰属させる。
- この仕様は、月次最適化の目的に合わせるため。

## ベースライン

最低限、以下を比較対象にする。

- No trade
- Random entry
- Random direction
- Moving average crossover
- RSI reversal
- Breakout
- Volatility filter
- Oracle-like upper bound

深層学習モデルは、これらのベースラインを超えなければ採用しない。

## 禁止事項

- 将来の high/low/close を、同じ時点の意思決定に使わない。
- test month に合わせて特徴量や閾値を手作業で調整しない。
- ランダム分割だけでモデル評価を終えない。
- 単月だけの最高スコアを研究成果とみなさない。
