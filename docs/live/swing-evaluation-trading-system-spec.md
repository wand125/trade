# 山谷評価関数ベース自動トレード仕様

## 目的

XAUUSD-mの短期売買について、相場の山/谷を検出し、1:5程度のリスクリワードで参入できるポイントを探索する。最初の目的は自動発注ではなく、過去足から候補を抽出し、評価関数のスコアが高いほど期待値が高くなるかを検証することである。

最終的には、検証でプラス期待値が確認された条件だけをシグナル化し、さらに十分な安全条件を満たす場合のみMT5 EAから自動売買へ進める。

## 基本方針

1. データ取得と売買判断を分離する。
2. まず説明可能なルールベース評価関数を作る。
3. 評価関数は勝率ではなく期待Rを推定する。
4. スコア帯ごとの実績を集計し、一定スコア以上で平均Rがプラスになるか確認する。
5. 自動発注は最後の段階に置く。

## 対象データ

主な入力はMT5 AI Bridgeが保存するruntimeファイルとする。

- `runtime/latest_snapshot.json`: 最新スナップショット
- `runtime/latest_history_24h.json`: 24時間足データ
- `runtime/latest_history_168h.json`: 1週間足データ
- `runtime/latest_account.json`: 建玉、口座、直近約定
- `runtime/latest_deal_history.json`: 決済履歴
- `runtime/economic_calendar.json` または `.csv`: 任意の経済指標カレンダー。時刻はMT5サーバー時刻に揃える

時間足はM1/M5/M15/M30を使う。

- M30/M15: 上位足の環境認識
- M5: 短期トレンドと戻り/押しの確認
- M1: エントリータイミング

## 戦略仮説

上位足の方向に沿い、短期足の山/谷で反発失敗またはリテスト成功を確認して入る。

買い:

- M15/M30が上昇優勢
- M5で押し目形成
- M1で谷を作った後、反発確認
- SLは直近谷の外側
- TPは5R付近。ただし途中の抵抗が近い場合は見送り

売り:

- M15/M30が下落優勢
- M5で戻り形成
- M1で山を作った後、反落確認
- SLは直近山の外側
- TPは5R付近。ただし途中の支持が近い場合は見送り

## 山/谷の定義

リペイントしない形を前提にする。未来側の足を使って確定する場合は、リアル運用でも同じ本数だけ遅れて確定させる。

候補定義:

- swing_high: 中央足の高値が左右N本の高値より高い
- swing_low: 中央足の安値が左右N本の安値より低い
- 前回山/谷からの距離が一定以上
- 距離条件はATR基準で判定する

初期値:

- M1 swing window: 左右3本
- M5 swing window: 左右2本
- 最小山谷距離: `0.5 * ATR14`
- 強い山谷距離: `1.0 * ATR14`

## エントリーパターン

### 1. 戻り売り/押し目買い

トレンド方向に対して短期足が逆行し、山/谷で失敗したところを狙う。

売り条件例:

- M15/M30が下向き
- M1/M5が一時的に戻す
- 直近山で高値更新失敗
- その後、M1の直近安値割れまたはEMA再下抜け

買い条件例:

- M15/M30が上向き
- M1/M5が一時的に押す
- 直近谷で安値更新失敗
- その後、M1の直近高値上抜けまたはEMA再上抜け

### 2. 高値/安値刈り取り後の反転

直近山/谷を一度抜けた後、すぐに戻る形を狙う。

売り条件例:

- 直近高値を一瞬上抜け
- 終値で高値下に戻る
- 上ヒゲが大きい
- 次足で安値割れ

買い条件例:

- 直近安値を一瞬下抜け
- 終値で安値上に戻る
- 下ヒゲが大きい
- 次足で高値上抜け

### 3. ブレイク後のリテスト

山/谷を抜けた後、同じラインへの戻りで反発する形を狙う。

売り条件例:

- 重要安値を下抜け
- 抜けた安値ラインまで戻す
- そのラインで上げ止まり
- M1で反落確認

買い条件例:

- 重要高値を上抜け
- 抜けた高値ラインまで押す
- そのラインで下げ止まり
- M1で反発確認

## SL/TP設計

基本単位をRとする。

- 売りSL: 直近山の外側 + spread + buffer
- 買いSL: 直近谷の外側 - spread - buffer
- buffer: `0.2-0.5 * ATR14`
- TP: 原則 `5R`

候補を採用する前に、TPまでの空間を確認する。

見送り条件:

- TPまでに強いM5/M15の山/谷がある
- SL幅がスプレッドに対して狭すぎる
- SL幅がM1 ATR未満でノイズに近い
- 価格がM15/M30の強い抵抗/支持に近すぎる
- ロールオーバーや極端な低流動性時間

## RR探索と可変RR戦略

初期仮説は1:5だが、1:2、1:3、1:4、1:5を同じ候補生成ロジックで横比較する。固定RRごとの損益分岐勝率は以下。

```text
1:2 breakeven_win_rate = 33.3%
1:3 breakeven_win_rate = 25.0%
1:4 breakeven_win_rate = 20.0%
1:5 breakeven_win_rate = 16.7%
```

実運用ではスプレッド、滑り、約定遅延、途中撤退を含めるため、上記より数ポイント高い勝率が必要になる。

比較方針:

- 1:2: TP到達率の上限確認用。勝率は上がるがPFが伸びるかを見る
- 1:3: TP到達率を上げ、勝ち癖と短時間決済を狙う
- 1:4: 到達率と期待Rのバランスを見る
- 1:5: 本命仮説。勝率は低くてもPFと総Rが伸びるかを見る

可変RR戦略は、候補ごとにTP倍率を変える。ただしRRを上げた結果scoreが上がる循環を避けるため、RR成分を除いたセットアップ品質とTPまでの空間を使って決める。

初期可変RR方針:

- `setup_ladder`: セットアップ品質が強ければ5R、中程度なら4R、それ以外は3R
- `space_ladder`: 品質に加え、TPまでのM1/M5/M15確定山谷障害物が少ない時だけ5Rまたは4R、それ以外は3R

採用条件:

- 固定1:2/1:3/1:4/1:5より平均R、PF、最大DDのバランスが良い
- score閾値別で成績が単調に悪化していない
- 片側の売買方向だけに過剰適合していない
- buy/sell別の平均Rがマイナスではない
- プラス総Rのうち片側だけが85%超を占めない
- 1週間だけでなく、別期間でも同じ傾向が出る

## 評価関数

評価関数は成功確率そのものではなく、期待Rを高くする方向に設計する。

1:5の損益分岐勝率:

```text
breakeven_win_rate = 1 / (1 + 5) = 16.7%
```

実運用ではスプレッド、滑り、建値差、早期撤退を考え、20-25%以上の勝率が必要になる。

初期評価関数:

```text
score =
  trend_score
+ structure_score
+ entry_trigger_score
+ risk_reward_score
- cost_penalty
- chop_penalty
```

100点満点の初期配点:

```text
trend_score         0-25
structure_score     0-20
entry_trigger_score 0-20
risk_reward_score   0-20
cost_penalty       -15-0
chop_penalty       -20-0
```

初期採用目安:

```text
score < 60  見送り
60-70       観察候補
70-80       検証上の採用候補
80以上      強い候補
```

最終判断は固定点数ではなく、スコア帯ごとの実績で決める。

例:

```text
score 50-60: 平均R -0.20
score 60-70: 平均R +0.05
score 70-80: 平均R +0.35
score 80-90: 平均R +0.80
```

このように、スコアが上がるほど平均RとPFが改善する形が確認できた場合に評価関数として採用する。

## 特徴量

### トレンド特徴量

- M30 EMA fast/slow関係
- M15 EMA fast/slow関係
- M15/M30 RSI14
- M15/M30の直近高値/安値の切り上げ/切り下げ
- M5の短期方向

### 構造特徴量

- 直近山/谷の明確さ
- 前回山/谷からの距離
- 山/谷と現在価格の距離
- M5確定山/谷と現在価格の距離
- 上位足の支持抵抗までの距離
- 高値更新失敗/安値更新失敗

### トリガー特徴量

- M1の直近高値/安値ブレイク
- EMA再上抜け/再下抜け
- 包み足
- ヒゲ比率
- 反転後の実体方向
- RSIの再加速/再失速

### リスク特徴量

- SL幅
- TP幅
- risk_reward
- spread / SL幅
- ATRに対するSL幅
- TPまでの障害物数
- TPまでのM5/M15確定山/谷障害物数
- M15/M30確定山/谷支持抵抗までの距離

### 除外特徴量

- スプレッド過大
- ロールオーバー付近
- M15/M30とM1/M5の方向不一致
- EMA絡みのレンジ
- ヒゲ連発
- 値幅が小さすぎる時間帯

## バックテスト仕様

候補生成時点から未来足を順に見て、TP/SLのどちらが先に到達したかを判定する。

判定ルール:

- buy: highがTP以上なら勝ち、lowがSL以下なら負け
- sell: lowがTP以下なら勝ち、highがSL以上なら負け
- 同一足でTP/SL両方に触れた場合は保守的に負け扱い
- 最大保有時間を超えた場合は時間切れ決済扱い

初期値:

- risk_reward: 5.0
- 最大保有時間: 30分、60分、120分を比較
- コスト: スプレッド + 追加滑り幅
- 同一方向の連続エントリーは一定時間禁止

## 出力指標

全体:

- 候補数
- 採用数
- 勝率
- 平均R
- PF
- 最大連敗
- 最大ドローダウン
- 期待R

スコア帯別:

- 50-60
- 60-70
- 70-80
- 80-90
- 90-100

方向別:

- 買い
- 売り

時間帯別:

- 東京時間
- 欧州時間
- NY時間
- ロールオーバー付近

パターン別:

- pullback_continuation
- liquidity_sweep_reversal
- breakout_retest

## プログラム構成

最初はPythonで検証エンジンを作る。

想定ファイル:

```text
analysis/
  swing_points.py
  features.py
  scoring.py
  candidate_generator.py
  backtest.py
  reports.py
  diagnostics.py
  deal_context.py
  rr_experiment.py
  weight_search.py
  signal.py
  dry_run_command.py
  risk_gate.py
  position_sizing.py
  economic_calendar.py
  time_filters.py
  history_status.py
  forward_test.py
  forward_status_watch.py
  forward_test_watch.py
  mt5_forward_report.py
  mt5_forward_collect.py
  mt5_tester_optimization_report.py
  mt5_optimization_recommend.py
  mt5_compile_status.py
  mt5_compile.py
  mt5_tester_run.py
  dry_run_audit.py
  promotion_gate.py
```

### `swing_points.py`

役割:

- M1/M5の山/谷検出
- ATR基準のノイズ除去
- 山/谷の強さを計算

主要関数:

```python
detect_swings(bars, left=3, right=3, min_atr_distance=0.5)
```

### `features.py`

役割:

- 各候補時点の特徴量を作る
- M1/M5/M15/M30を横断して環境認識を数値化する

主要関数:

```python
build_features(candidate, market_context)
```

### `scoring.py`

役割:

- 特徴量からscoreを計算
- scoreの内訳を返す

主要関数:

```python
score_candidate(features, weights)
```

出力例:

```json
{
  "score": 76.5,
  "trend_score": 22.0,
  "structure_score": 16.0,
  "entry_trigger_score": 15.5,
  "risk_reward_score": 18.0,
  "cost_penalty": -3.0,
  "chop_penalty": -2.0
}
```

### `candidate_generator.py`

役割:

- 買い/売り候補を生成
- SL/TPを仮置き
- TPまでの障害物を確認
- 候補を `pullback_continuation` / `liquidity_sweep_reversal` / `breakout_retest` の3パターンへ分類する

分類順:

1. 直近の同方向ブレイク済み山/谷を再テストし、エントリー足で再度ラインを回復/下抜けしていれば `breakout_retest`
2. M15/M30のEMA方向がエントリー方向に揃っていれば `pullback_continuation`
3. それ以外は `liquidity_sweep_reversal`

`breakout_retest` では、`retest_level_kind`、`retest_level_time`、`retest_level_price`、`retest_broken_time`、`retest_distance_atr` を特徴量に残す。

主要関数:

```python
generate_candidates(market_context)
```

候補出力:

```json
{
  "time": "2026.07.07 09:40",
  "symbol": "XAUUSD-m",
  "side": "sell",
  "pattern": "pullback_continuation",
  "entry": 4127.30,
  "sl": 4129.00,
  "tp": 4118.80,
  "risk_reward": 5.0
}
```

### `backtest.py`

役割:

- 候補ごとにTP/SL到達を検証
- R損益を計算
- 最大保有時間を適用

主要関数:

```python
run_backtest(candidates, bars, max_hold_minutes=60)
```

結果出力:

```json
{
  "candidate_id": "...",
  "result": "win",
  "r_multiple": 5.0,
  "exit_time": "2026.07.07 10:12",
  "exit_reason": "tp"
}
```

### `reports.py`

役割:

- Excel/CSV/Markdown出力
- スコア帯別の統計を作る
- 売り/買い/時間帯/パターン別に集計する

### `diagnostics.py`

役割:

- 勝ち候補と負け候補の特徴量差分を出す
- score閾値別に平均R/PF/DDを比較する
- score構成要素の重み探索を行う

### `deal_context.py`

役割:

- `latest_deal_history.json` の決済履歴と `latest_history_168h.json` のM1足を時刻で突合する
- 決済前後のM1足をCSV/XLSXで出力する
- 決済足、前後の値動き、窓内高値/安値、決済価格からの距離を確認できるようにする

### `rr_experiment.py`

役割:

- 固定1:2、1:3、1:4、1:5の横比較を行う
- 可変RR方針を固定RRと同じ条件で比較する

### `weight_search.py`

役割:

- `trend/structure/entry/risk/cost/chop` の重み倍率を探索する
- 高スコア帯で平均RとPFが改善する配点候補を出す
- Excelに加えてJSON/Markdownを出力し、上位候補、baseline閾値別成績、探索条件、walk-forward aggregate、regime別不足をPromotion Gateや後続自動処理から参照・目視確認できる形で残す
- walk-forwardでは各foldのtrainで重み/閾値を選び、testで同じ重み/閾値をbaseline score閾値と比較する。全期間fitの上位候補だけでは採用しない
- `--regime-search entry_hour,m30_m15_trend,m30_trend,m15_trend,htf_alignment` で、時間帯や上位足レジーム別に同じ重み探索とwalk-forwardを行い、全体fitでは崩れるが一部レジームだけ候補が残るケースを切り分ける
- Promotion Gateは `runtime/latest_score_weight_search.json` を読み、score calibration / score quality未達時のnext actionとMarkdownに上位重み候補、baseline比較、平均R/PF/DD差分、walk-forward結果を表示する
- `weight_search.py` の上位候補は「採用」ではなく「次に検証する候補」とする。baselineより平均R/PFが改善しても、walk-forward、MT5 Optimization、年次検証を通るまでは実運用配点へ反映しない

### `score_weight_set.py`

役割:

- `weight_search.py` のside別JSONを読み、`trend/structure/entry/risk/cost/chop` の倍率候補をMT5の `InpScore...` 入力へ変換する
- SELLは `Swing_Evaluation_Trader_sell_regime_entry_refit.set` をテンプレートに `Swing_Evaluation_Trader_sell_score_weight_refit.set`、BUYは `Swing_Evaluation_Trader_buy_refit.set` をテンプレートに `Swing_Evaluation_Trader_buy_score_weight_refit.set` を生成する
- walk-forward aggregateが `walk_forward_candidate_passed` でない限り、既定では `.set` を書かず、`runtime/latest_score_weight_set_168h_<side>_rr4.json` / `.md` に `skip_reason=walk_forward_not_passed` を残す
- Promotion Gateは `runtime/latest_score_weight_set_168h_<side>_rr4.json` も読み、set未生成の理由をnext action直下へ表示する。全体walk-forward不合格やレジーム別 `walk_forward_sample_shortage` の場合は、同じset変換を繰り返すのではなく、`failure_mode`、平均R/PF、baseline比delta、fold数、不足fold、レジーム別sample shortageを表示し、`history_status.py` による履歴確認と `Swing_Evaluation_Trader_sample_collection.set` を使った診断サンプル収集計画を出す。自動Runnerのsample collection成果物は `runtime/latest_mt5_tester_sample_collection_<side>_run.json` / `runtime/latest_mt5_sample_collection_<side>_report.json` に分け、BUY/SELLの証跡を上書きしない。実行計画には `--sync-expert-parameters-set` を含め、MT5起動前に対象sample collection `.set` だけをprofileへ同期する
- 生成setはMT5検証用であり、MT5 Optimization、年次/out-of-year検証、Promotion Gateを通るまでは実運用配点として採用しない

### `winrate_fit.py`

役割:

- 買い/売り/RR別に、勝率を上げるための追加フィルタを探索する
- 単純なtrain/testだけでなく、時系列ウォークフォワードで検証する
- 168h履歴のような候補数が薄い窓では、既定でwalk-forwardをtrain 40件/test 12件の4 foldにし、1 foldだけの見かけの採用を避ける
- 絶対価格水準に依存する特徴量はfit対象から外す
- fitでtrain勝率だけが上がり、未来testで崩れるルールは採用しない
- Promotion Gateでは `adoption_decision.adopted=true` に加え、`walk_rows` のaggregateでfitted test件数が最低件数以上、かつ `mean_test_fitted_pf` が最低PF以上であることも要求する

### `signal.py`

役割:

- 最新履歴から直近の採用候補を選ぶ
- 固定RRまたは可変RR方針でTP倍率を決める
- `runtime/latest_signal.json` に手動確認用シグナルを出す
- 自動発注は行わず、`mode = manual_review` として出力する

### `dry_run_command.py`

役割:

- `runtime/latest_signal.json` をEA向け `runtime/trade_command.json` に変換する
- `dry_run = true` のみを出力する
- hold、不正SL/TP、score不足、期限切れ相当のシグナルは拒否する
- `generated_at + valid_for_seconds` を過ぎたsignalは期限切れとして拒否する
- rejected commandでも `source_signal` にscore、RR、`generated_at`、`valid_for_seconds`、candidate time、latest bar time、history server timeを残し、`lot_policy` に0.1 lot基準と0.3 lot合計上限を残す。EAへ送らなかった判断、signal有効期限、ロットルールの元データを監査できるようにする
- 既存pending commandは明示的な `--replace` がない限り上書きしない
- 既定ロットは既存運用に合わせて `0.1`
- risk sizingを使う場合も、ロットを大きく下げるのではなく `0.1` 未満なら拒否する

### `risk_gate.py`

役割:

- dry-run command作成前に建玉数、日次損失、連敗を確認する
- `latest_account.json` と `latest_deal_history.json` を入力にする
- 拒否理由とmetricsをcommand JSONへ保存する
- live化前の安全条件をdry-run段階から検証する
- 現行ロット運用として、`0.1` を基本単位、ナンピン/追加時も合計 `0.3` lot上限を確認する。加えて新規dry-run注文後の `projected_open_positions` を計算し、既に建玉上限に達している状態で追加注文候補を出さない
- 連敗停止は既定20連敗、120分クールダウン。連敗数だけで永久停止せず、クールダウン経過後は再開を許可する

### `position_sizing.py`

役割:

- signalのentry/SLと口座equityから許容リスクに対するロットを計算する
- `latest_deal_history.json` からXAUUSD-mの価格1.00変動あたりのJPY損益価値を推定する
- 既存運用に合わせ、標準は1回 `0.1` lotを基本上限とする
- 計算上0.1未満が妥当な場合、自動的に大幅縮小せず拒否してリスク過大を明示する

### `economic_calendar.py`

役割:

- JSON/CSVの経済指標カレンダーを読み込む
- `time`, `server_time`, `datetime`, または `date + time` 形式を受け付ける
- `currency`, `impact`, `title/event/name` を読み、指定通貨・重要度でフィルタする
- ISO時刻にtimezoneが付いている場合は、必要に応じてMT5サーバーUTC offsetへ変換できる
- timezoneなしのJST/UTC等のカレンダーは、`--calendar-input-utc-offset` と `--calendar-server-utc-offset` でMT5サーバー時刻へ変換する

JSON例:

```json
{
  "events": [
    {
      "time": "2026.07.07 15:30:00",
      "currency": "USD",
      "impact": "high",
      "title": "CPI"
    }
  ]
}
```

CSV例:

```csv
date,time,currency,impact,event
2026-07-07,15:30,USD,high,CPI
```

JSTカレンダーをMT5サーバーUTC+3へ変換する例:

```bash
--calendar-input-utc-offset 9 \
--calendar-server-utc-offset 3
```

UTC ISO時刻をMT5サーバーUTC+3へ変換する例:

```json
{"time": "2026-07-07T12:30:00Z", "currency": "USD", "impact": "high", "title": "CPI"}
```

### `time_filters.py`

役割:

- 日跨ぎ/ロールオーバーと指標proxy時間の新規エントリーを除外する
- MT5サーバー時刻で `23:45-00:15` をロールオーバー除外時間にする
- 米国指標proxyとして `15:20-15:40`, `16:50-17:10`, `20:50-21:10` を初期除外する
- `runtime/economic_calendar.json` が存在する場合は、実イベント前後もno-entryにする
- 正確なカレンダーがない段階では、保守的なproxy時刻窓も併用する

### `history_status.py`

役割:

- `latest_history_168h.json` のM1/M5/M15/M30本数を検証する
- top-level `bars` はコンパクトなプレビューであり、分析には `timeframes.M1.bars` を使うことを明示する
- `history_request.done.json` の本数と照合し、取得不備や誤読を早期に検出する
- `runtime/latest_history_status.json` と `.md` に診断結果を保存する

### `bridge_status.py`

役割:

- MT5 AI Bridgeの `/health` / `/config` 応答、`mt5_ai_bridge.py` プロセス、`latest_snapshot.json` 鮮度を確認する
- `history_request.json` と `history_request.done.json` のID照合、pending経過秒数、stale pendingを診断する
- `bridge.log` の `POST /snapshot`、history chunk、deal history chunkの最終時刻を読み、監視プロセス由来の `GET /config` とEA由来のPOST停止を分ける
- `bridge_log_activity` と `ea_attention` には `ea_liveness_signal`、`config_get_recent`、`ea_post_recent`、`config_get_recent_but_ea_post_stale` を保存し、`GET /config` だけが新しくてもEA稼働証跡として扱わない
- Bridge自体が停止している状態と、Bridgeは生きているがMT5側EAがsnapshot/historyをPOSTしていない状態を分ける
- MT5 terminalプロセスの有無と `ea_attention.required/reason` を出し、terminalは開いているがEA POSTが止まっている状態を、MT5/EA未起動と分ける
- `runtime/latest_bridge_status.json` と `.md` に診断結果を保存する

### `bridge_recovery_plan.py`

役割:

- `runtime/latest_bridge_status.json` と `runtime/latest_history_status.json` を読み、Bridge/EA/履歴pendingの復旧状態を `ready`、`needs_bridge_http`、`needs_bridge_process`、`needs_ea_restart`、`needs_history_wait`、`needs_history_status_refresh` に分類する
- `GET /config` ではなくEA由来の `POST /snapshot` / history chunk鮮度を優先し、MT5 terminalは起動しているがEAがPOSTしていない状態を手動復旧対象として出す
- stale pending中は同じ履歴要求を繰り返さず、EA POST復旧後に `history_request.done.json` のID一致を待つ手順を表示する
- `blocking_reasons` と `next_action` を出し、`snapshot_not_fresh`、`history_request_stale_pending`、`bridge_process_not_running` などの機械可読な停止理由と、次に実行すべき復旧操作を他のRunnerと同じ形式で扱えるようにする
- JSONには `operation_cards` を持たせ、`needs_ea_restart` では `AI_Bridge_Advisor` をライブ `XAUUSD-m` チャートへ付け直す次操作、検証条件としてfreshな `POST /snapshot`、履歴pendingのrequest/done ID、復旧後に実行する `verification_commands` を構造化して保存する。Markdownにも `Bridge Recovery Operation Cards` と確認コマンドを出し、coverageやwatcher heartbeatから次のBridge復旧操作と確認手順だけを読めるようにする
- JSONには操作者向けの `operator_summary` も保存する。ここにはstatus、ready判定、blocking reasons、次操作、対象領域、対象EA、手動手順、確認条件、確認コマンド、MT5 terminal起動有無、直近EA POST経過秒、snapshot鮮度、履歴request/done ID照合を集約し、MarkdownやCoverageへ転記してMT5画面で次に行う復旧操作を1か所で読めるようにする
- JSON直下と `operator_summary` には `bridge_required_for_standalone_tester=false`、`standalone_strategy_tester_allowed=true`、`standalone_strategy_tester_note` を出し、Bridge/GPT/履歴更新の未ready状態と、Bridge非依存の `Swing_Evaluation_Trader` Strategy Tester Back/Forwardを進めてよい状態を機械的に分けられるようにする
- `ready_for_mt5_validation=true` の時だけ、Bridge/履歴依存のMT5検証へ進むコマンドを表示する。ただしStandalone Strategy Testerの手動Back/Forward導線は、runner側で `--require-bridge-ready` を明示しない限りBridge未readyでも消さない
- `runtime/latest_bridge_recovery_plan.json` と `.md` に復旧手順と再確認コマンドを保存する

### `bridge_status_watch.py`

役割:

- `bridge_status.py` を定期実行し、Bridge/EA接続状態をheartbeatへ転記する
- `bridge_recovery_plan.py` も同じ周期で実行し、Bridge/EA復旧手順とMT5検証へ進めるかを `runtime/latest_bridge_recovery_plan.json` / `.md` に更新する
- heartbeatに直近実行時刻、epoch、elapsed秒数、returncode、次回実行間隔、`watcher_pid`、`pid_file`、`pid_file_enabled`、`pid_file_written`、`heartbeat_enabled`、`run_index`、`max_runs`、`continuous`、`implementation_version`、`snapshot_required_keys`、Bridge HTTP/config、snapshot鮮度、履歴request/done照合、Bridge log上のEA POST活動、`ea_liveness_signal`、`config_get_recent_but_ea_post_stale`、MT5 terminal起動有無、EA attention理由、復旧プランのstatus、`ready_for_mt5_validation`、`bridge_required_for_standalone_tester`、`standalone_strategy_tester_allowed`、`standalone_strategy_tester_note`、復旧プラン出力先、復旧 `operation_cards`、次カード要約、次カードの `verification_commands`、`operator_summary` とその次操作/確認条件/履歴ID/EA POST鮮度/Standalone Strategy Tester可否を残す。`operator_summary` 系keyも必須snapshot keyに含め、古いwatcherがBridge復旧の操作者向け要約やEA liveness判定を転記できない状態を `running_heartbeat_incompatible` で検出できるようにする
- `--max-runs 1` などの1回実行は、明示的に `--heartbeat` / `--pid-file` を指定しない限り共有daemon heartbeat/PIDを上書きしない。常駐watcherは `--max-runs 0` の時だけ既定の共有pathを使う。明示pathを使う診断では `--skip-pid-file-write` も指定でき、heartbeatの `pid_file_written=false` で常駐監視ではない更新と分かるようにする

### `dry_run_audit.py`

役割:

- signal、trade command、EA dry-run resultを突合する
- command id一致、dry_run維持、EA受理/拒否/未取得を分類する
- command/resultの鮮度を確認し、古いdry-run結果を昇格根拠にしない
- HOLDやrisk gateなどでcommandがEA送信前に `rejected` / `expired` になった場合はEA resultを要求せず、command自体の鮮度を確認する。古い無関係な `latest_trade_result.json` でHOLDの監査をstale扱いにしない
- 最新signalとcommandのaction/symbol/candidate_timeが整合するか確認する
- `runtime/latest_dry_run_audit.json` と `.md` に監査結果を保存する

### `forward_test.py`

役割:

- `runtime/latest_signal.json` をフォワードテスト台帳へ記録する
- 記録後に増えたM1足だけを使い、TP/SL/時間切れを評価する
- バックテストと混同しないよう、`runtime/forward_tests.jsonl` を独立台帳にする
- closed/open/ignored、勝率、平均R、PF、最大連敗、最大DD、期待Rを集計する

### `forward_status_watch.py`

役割:

- `forward_test.py status` を一定間隔で実行する
- `runtime/latest_forward_test_status.json` と `.md` を継続更新する
- heartbeatに直近実行時刻、epoch、elapsed秒数、returncode、次回実行間隔、`watcher_pid`、`pid_file`、`pid_file_enabled`、`pid_file_written`、`heartbeat_enabled`、`run_index`、`max_runs`、`continuous`、`implementation_version`、`snapshot_required_keys`、status要約を残す
- `--max-runs 1` などの1回実行は、明示的に `--heartbeat` / `--pid-file` を指定しない限り共有daemon heartbeat/PIDを上書きしない。常駐watcherは `--max-runs 0` の時だけ既定の共有pathを使う
- signalがHOLDの間も台帳を汚さず、稼働状態だけを確認できるようにする

### `forward_test_watch.py`

役割:

- `runtime/latest_signal.json` を一定間隔で確認し、BUY/SELLだけを `runtime/forward_tests.jsonl` へ記録する
- 同じsignal IDは二重記録しない
- HOLDや不完全なsignalは台帳に書かず、status/heartbeatに理由を残す
- `runtime/latest_history_168h.json` のM1足でopen recordを評価し、TP/SL/時間切れをclosedへ更新する
- `runtime/latest_forward_test.json` / `.md` と `runtime/latest_forward_test_status.json` / `.md` をまとめて更新する
- `runtime/forward_test_watch_heartbeat.json` に直近実行結果、記録結果、評価結果、件数、`schema_version`、`implementation_version`、`snapshot_required_keys`、`returncode`、`started_epoch`、`finished_epoch`、`elapsed_seconds`、`watcher_pid`、`pid_file`、`pid_file_enabled`、`pid_file_written`、`heartbeat_enabled`、`run_index`、`max_runs`、`continuous` を残し、`record_result`、`evaluation_result`、`paths`、`counts`、`signal`、`summary` も必須snapshot keyとして互換性判定する。これにより、1回実行の更新と常駐監視、ファイル鮮度、古いwatcher世代、記録/評価結果を転記できない古いwatcherを区別できるようにする
- `--max-runs 1` などの1回実行は、明示的に `--heartbeat` / `--pid-file` を指定しない限り共有daemon heartbeat/PIDを上書きしない。常駐watcherは `--max-runs 0` の時だけ既定の共有pathを使う

### `runtime_watchers.py`

役割:

- Bridge、MT5 tester status、MT5 manual auto collect、forward test、forward status の各watcherをまとめて確認し、PIDファイル上のプロセスが動いていないwatcherだけを起動する
- `--restart` 指定時は既存watcherを停止してから同じ設定で起動し直し、古いGate/Next Actionを見ているwatcherを復旧できるようにする
- PIDが生きていてもheartbeatが `interval_seconds * 3` または `--max-heartbeat-age-seconds` を超えて古い場合は `running_heartbeat_stale`、heartbeatがない場合は `running_heartbeat_missing` として `ok=false` にし、PIDファイルだけ残った監視停止を見落とさないようにする
- heartbeatがfreshでも、heartbeat内の `watcher_pid` がPIDファイルのPIDと一致しない、`continuous=false`、または `pid_file_written=false` の場合は `running_heartbeat_not_daemon` として `ok=false` にする。一回実行の `--skip-pid-file-write` heartbeatで常駐watcherが健全に見える誤判定を避ける
- MT5 tester status watcher、Bridge status watcher、forward test watcher、forward status watcherは、freshでdaemon状態でも `implementation_version` が現行値と一致しない、または現行statusが要求する必須snapshot keyが欠ける場合に `running_heartbeat_incompatible` として `ok=false` にし、古い常駐watcherがMT5手動テストキュー、Back/Forward preflight、Bridge Recovery Operation Cards、Python forward ledger/statusを転記できない状態を再起動対象にする
- `--dry-run` では起動/停止せず、実行予定コマンドとPID/heartbeat状態だけを確認する。PIDファイル上のプロセスが動いていない場合は `stale_pid_would_start` として `action_required_watcher_count` に数え、dry-runの `ok=false` にする。これにより、dry-run成果物だけを見て停止中watcherを正常稼働と誤読しないようにする
- `runtime/latest_runtime_watchers.json` / `.md` にwatcher名、状態、PID、heartbeat鮮度、heartbeat側PID、PID一致、`pid_file_written`、`continuous`、`implementation_version`、期待implementation version、schema ok、必須key欠落数、`status_refresh_phase`、log、起動/再起動コマンドを保存し、個別watcherの起動状況とheartbeat停止/互換性をファイルだけで確認できるようにする。JSONの各watcher行には `heartbeat_status`、`heartbeat_fresh`、`heartbeat_age_seconds`、`heartbeat_watcher_pid`、`heartbeat_pid_matches`、`schema_ok`、`missing_required_field_count`、`missing_required_fields` もトップレベルaliasとして置き、Markdownやネスト構造を読まなくても外部監視・手元スクリプトから状態を判定できるようにする
- MT5手動Strategy Tester後の自動取り込みは既定OFFにする。`runtime_watchers.py --only mt5_manual_auto_collect --restart --mt5-manual-auto-collect-execute-ready` を明示した場合だけ、常駐 `mt5_manual_auto_collect` に `--execute-ready` を付け、readyなcollect-onlyを実行してPromotion Gate、Strategy Tester Analysis、Spec Coverageまで更新する。既存daemonのheartbeat上の `execute_ready` が要求モードと違う場合は `running_heartbeat_mode_mismatch` として `ok=false` にし、検知専用daemonを自動取り込みdaemonとして誤読しない

### `mt5_forward_report.py`

役割:

- `Swing_Evaluation_Trader.mq5` がStrategy Tester/Forward Testで出すCSVログを読む
- `close` 行だけを実績として集計し、PF、勝率、net profit、最大連敗、価格Rベース最大DD、期待価格Rを出す
- `deal_price`、計画entry/SL、`spread_points`、`latency_seconds` から価格ベースR、滑り、平均/最大スプレッド、約定遅延を出す
- `button` 行からチャートEntryボタンのdry-run/ignored件数を出す
- `signal` / `reject` 行からBUY/SELL/HOLD数、平均score、主なHOLD/reject理由を出す
- `Risk Exposure` で実際に観測された最大単発lot、同時保有lot、同時建玉数、日次損失停止後open、連敗停止後open、risk系reject数を出す
- 売買別、RR別、score帯別に集計する
- `m30_trend` / `m15_trend` / `m5_trend` / `m30_slope` / `m15_slope` / `trend_alignment` で上位足トレンド別のPFと平均価格Rを集計する
- `opened_at` / `entry_server_hour` がある場合は、決済時刻ベースの時間帯だけでなくentry hour別にも集計する
- Forward CSVでも `Weak Time Segments` と `Weak Trend Segments` を出し、Forwardで崩れる時間帯/上位足レジームをside別再fitの材料にする
- Forward CSVのschemaを診断し、`opened_at`、`entry_server_hour`、M30/M15/M5 trend、M30/M15 slope、`trend_alignment` が欠ける古いCSVではentry-hour/trend診断を採用しないよう警告する
- score累積閾値をbuy/sell別に集計し、買いはcandidate gate、売りはscore inversionなどのside別score診断を出す
- closedサンプル数、PF、最大連敗のForward採用条件を機械判定する
- Analyzer/GPT/Bridgeを使わないMT5単体EAの検証結果を、プロジェクト側の昇格判断材料に戻す

### `mt5_forward_collect.py`

役割:

- MT5の `MQL5/Files` と `Tester/.../MQL5/Files` から最新の `swing_evaluation_trades.csv` を探す
- 見つかったCSVを `runtime/mt5_forward/swing_evaluation_trades.csv` へコピーする
- `mt5_forward_report.py` と同じ集計JSON/Markdownを自動生成する
- 見つからない場合も `runtime/latest_mt5_forward_collect.json` に探索状況を残す

### `mt5_tester_optimization_report.py`

役割:

- MT5 Strategy TesterのOptimizationでAgentごとに分かれた `swing_evaluation_trades.csv` を統合集計する
- RR、売買方向、SL幅、TP幅、RR×SL幅、RR×TP幅でPF、平均価格R、価格Rベース最大DD、期待価格R、TP/SL/早期損失を比較する
- `Weak SL/TP Segments` で崩れているSL/TP帯を診断する
- `Best Segments` で次に重点探索する候補帯を出す
- `Temporal Diagnostics` で四半期、月、曜日、サーバー時間帯、RR×月のPF/平均Rを比較する
- `Weak Time Segments` で短期では良く見えた設定が通年のどの時間レジームで崩れるかを診断する
- `Trend Regime Diagnostics` でM30/M15/M5トレンド、M30/M15 slope、トレンド整合、売買方向×トレンド整合のPF/平均Rを比較する
- `Weak Trend Segments` で、買い/売りの評価関数が上位足トレンドと逆行して崩れていないかを診断する
- Tester本体が出すOptimization XMLとForward XMLを読み、back/forwardの上位パスを同じレポートに含める
- `--set-file` を指定した場合は、`.set` の全探索候補pass数と、MT5 genetic optimizationで実際にXMLへ出たrows数を並べて表示する。JSONでは `optimization_pass_budget.executed_tester_xml_rows.back/forward` として構造化し、Markdown表示と後続ゲートが同じ証跡を参照できるようにする
- `--modified-after` / `--modified-before` でAgent CSVのmtime範囲を絞れる。通常の短期Optimization再集計planでは、latest tester runの `terminal_run.finished_at` を `--modified-before` として付け、Tester後に別setで上書きされたAgent CSVを混ぜない
- Agent CSVのclose行から `source_time_coverage.first_server_time` / `last_server_time` を出し、`--expected-from-date` / `--expected-to-date` が指定された場合は `source_time_diagnostics.matches_expected_range` でTester期間と実CSV期間の整合性を判定する。年次検証を再集計する時に、残っている短期Agent CSVを拾って別期間のレポートを上書きしないための証跡にする
- `--fail-on-source-time-mismatch` を指定した場合、期待期間とCSV期間が一致しない時は出力JSON/Markdownを書き換えずに終了する。これにより、年次/out-of-yearレポートを別期間CSVで上書きする事故を防ぐ
- 既存Agent CSVから年次/out-of-yearレポートを復旧する場合は、`--drop-source-time-mismatch-files` を指定できる。この場合、期待期間外のAgent CSVだけをファイル単位で除外し、`source_time_file_filter` に入力件数、採用件数、除外ファイル、各ファイルのfirst/last、除外理由を残す。通常のTester起動直後の検証では混入自体を検知するため、必要な時だけ明示的に使う
- Promotion Gateのsource-time mismatch next actionには `source_time_gap` と `source_time_warnings` を表示し、期待From/To、実際のAgent CSV close `server_time` first/last、server_time付き/なし行数、期間不一致の理由を実行計画の近くで確認できるようにする
- 補助CLI `mt5_strategy_tester_analysis.py` は、Promotion Gate、spec coverage、Back/Forward runner、tester status、BUY/SELLの主要Optimizationレポートを読み、MT5上で回したBacktest/Forward/Optimization証跡を横断表にする。候補、参考、閾値未満、不採用、未実行を分類し、SELLだけが候補でBUYに安定passがない状態や、Back/Forwardがまだ `plan_only` の状態を採用ブロッカーとして明示する

### `mt5_optimization_recommend.py`

役割:

- `latest_mt5_optimization_report.json` を読み、次のOptimization探索範囲をBUY/SELL別に整理する
- BUY/SELL別にPFと平均価格Rを確認し、再fitが必要なsideを明示する
- 一定件数以上の `Best Segments` だけを主候補にし、少数サンプルの高PF帯は参考扱いにする
- `Weak SL/TP Segments` を除外候補として整理する
- `Time Regime Diagnostics` を推薦レポートに含め、月別/時間帯別に崩れた条件を再fit候補として扱う
- `Trend Regime Diagnostics` を推薦レポートに含め、M30/M15の方向とslope別に崩れた条件を再fit候補として扱う
- forwardだけ良くbackが悪いTesterパスを過剰適合候補として不採用理由に含める
- 推薦されたside/RR/SL帯から、次回Optimization用 `.set` を生成できる
- `score_inversion` などで診断用setになる場合は、既存のfocused `.set` を既定では上書きしない。診断用setを明示的に保存する時だけ `--allow-diagnostic-output-set` を付ける
- 推薦が不採用でもstable back/forward pass周辺を追加探索する場合は、通常の `next_optimization.set` ではなく `Swing_Evaluation_Trader_stable_candidate_next.set` のような別名setへ `--allow-non-adoptable-output-set` 付きで明示保存する。このsetは探索用で、Promotion Gateでは採用済み候補として扱わない

### `mt5_compile.py`

役割:

- Mac版MT5/Wine環境のMetaEditorを起動し、EA/IndicatorのCompileを試行する
- MetaEditorの終了コードだけではなく、`.ex5` が最新 `.mq5` より新しいかを `mt5_compile_status.py` と同じ基準で再確認する
- Compile実行コマンド、stdout/stderr末尾、MetaEditorログ候補、前後の `.ex5` 更新時刻を `runtime/latest_mt5_compile_run.json` に残す
- `ok=false` の場合はStrategy Tester Optimizationを走らせる前のブロッカーとして扱う

### `mt5_tester_run.py`

役割:

- MT5 `terminal64.exe /config:<ini>` を使ってStrategy TesterのOptimizationを起動する
- 実行用 `.ini` は `C:\mt5cfg` にコピーし、`ShutdownTerminal=1` と `ReplaceReport=1` を明示する
- 起動前にMT5配置済み `.ex5` の鮮度を確認し、古い場合は既定で実行を止める
- 既存の `terminal64.exe` が起動中の場合、`/config` が既存プロセスへ吸われてStrategy Testerが走らないことがあるため既定で実行を止める。診断目的で強制する場合だけ `--allow-running-terminal` を使う
- 手動Strategy Testerキューの `direct_config` 起動は `--detached` を指定できる。MT5端末がテスト中に開き続けてもCLIを待たせず、JSON/Markdownに `status=launched`、PID、次アクション `wait_for_mt5_strategy_tester_report_then_collect` を残す
- 起動前に参照 `.set` のrisk presetを確認し、通常のForward/Optimizationでは日次損失停止ON、連敗停止ON、連敗limit 20以上、cooldown 120分以上、`InpChartButtonDryRunOnly=true`、`InpAllowChartButtonTrading=false` を満たさない場合は既定で実行を止める。`sample_collection.set` だけはサンプル収集用として日次損失停止/連敗停止OFFを許容するが、チャートボタン実発注は禁止のまま確認する
- 起動前に対象configの `ExpertParameters` `.set` がMT5側 `MQL5/Profiles/Tester` に同期済みか確認する。compile statusの一覧に出ない一時的な `.set` でも、workspace側とMT5側profileの実ファイルを直接比較する。対象`.set`が `set_not_synced` / `missing_mt5_set` の場合は `tester_set_not_synced` として起動前にブロックし、`--sync-expert-parameters-set` 付き再実行または手動コピーで復旧する。全`.set`のどれかではなく、そのrunが参照する対象`.set`だけを起動ブロッカーにする
- compileまたはrisk presetで起動前にブロックした場合は、既存のTester XML/CSVを収集せず、`report_paths.source=blocked_not_collected` を残して古い最適化結果を最新runとして誤読しないようにする
- `--archive-agent-csvs-before-run` を指定した場合、MT5起動前に既存のTester Agent CSVを `runtime/mt5_agent_csv_archive/<timestamp>/...` へ退避する。EAはCSVを末尾追記するため、年次/短期など期間の違う実行を混ぜないための標準手順として使う。退避時のrun JSON/Markdownには、退避したCSVのclose `server_time` first/last、close件数、欠落件数も残す
- `--agent-csv-archive-run-id` を指定すると、`mt5_agent_csv_archive.py --run-id` で事前previewした退避先と同じディレクトリへ退避できる。Promotion Gateのsource-time mismatch復旧planでは、previewと本実行に同じrun-idを含める
- collect-only/dry-run以外の通常起動でCSV退避が未指定なら、run JSON/Markdownに `agent_csv_archive_missing=true` とwarningを残し、source-time mismatchの原因候補を明示する
- run JSON/Markdownにはterminal開始時刻、timeout秒数、deadline、elapsed秒数を残し、長時間Optimizationの最大待機期限を後から確認できるようにする
- run JSON/Markdownには `compile_status` の `all_tester_sets_synced` / `all_tester_configs_synced` と、対象 `ExpertParameters` `.set` の `target_tester_set_sync` を表示し、単体runの証跡だけでMT5側 `MQL5/Profiles/Tester` の `.set` / `.ini` 配置状態と起動ブロック理由を確認できるようにする
- terminalがtimeoutまたは非0終了した場合は `terminal_failed=true` とし、古いTester XML/CSVへのfallback収集や推薦生成は行わない
- 通常起動で指定Report XMLが生成されずfallback XMLを検出した場合は `report_fallback_blocked=true` とし、古いXML/CSVからの収集や推薦 `.set` 更新は行わない。collect-onlyでは既存XMLの再集計用途としてfallbackを許容する
- `Optimization=0` の単発Strategy Testを `--no-recommendation` で実行する場合は、MT5がXMLではなくHTMLレポートだけを出すことがある。この場合は指定ReportのHTMLが生成され、新規Agent CSVが見つかることを条件に、`report_paths.source=requested_single_test_html_report` としてCSV集計を許容する。Optimization実行ではこの例外を使わず、古いXML pairへのfallbackを引き続きブロックする
- 集計や推薦生成を止めた場合は、親run JSON/Markdownを根拠にしつつ、子の `latest_mt5_optimization_report` / `latest_mt5_optimization_recommendation` も `ok=false` の停止マーカーで上書きし、古い子レポートを最新証跡として誤読しないようにする。停止マーカーのMarkdownにもterminal開始時刻、deadline、timeout秒数、elapsed秒数、compile状態、risk preset、Agent CSV退避状況を残す。期間不一致で集計自体はできた場合はOptimization子レポートに実測summaryを残し、推薦子レポートだけを停止マーカーにする
- 実行後にAgent別 `swing_evaluation_trades.csv` とTester XML/Forward XMLを統合集計する
- 集計結果から `mt5_optimization_recommend.py` 相当の推薦と次回Optimization用 `.set` を更新する
- 推薦が不採用の場合、または診断用score refitの場合は、既存の次回focused `.set` を保持し、`next_set.skipped_write=true` を実行レポートに残す。不採用は `skip_reason=not_adoptable`、score refit診断は `skip_reason=diagnostic_only` とする。まとめ実行で診断用setを明示保存する時だけ `--allow-diagnostic-output-set` を付ける。不採用だがstable pass周辺を探索したい場合は `--allow-non-adoptable-output-set` を使い、採用setとは別名のstable candidate setに限って保存する

### `mt5_back_forward_run.py`

役割:

- Backtest用 `Swing_Evaluation_Trader_backtest.ini` とForward用 `Swing_Evaluation_Trader_forward_test.ini` をまとめてdry-run / execute / collect-onlyできる
- `Manual Strategy Tester Checklist` にMT5画面で選ぶExpert、Symbol、Period、Model、Dates、Forward、Inputs、Report名、推奨collect-onlyコマンドを出す
- `Manual Collect Readiness` に、手動Strategy Tester実行後の指定Report HTML/XMLと新しいAgent CSVが `--csv-modified-after` 以降に揃ったかを表示し、collect-onlyを実行してよい状態か判定できるようにする。readyでない場合は `blocking_reasons` と `next_action` に、step別Report待ち、Agent CSV待ち、時刻指定ミスを機械判定できる形で残す
- `Manual Strategy Tester Prerequisites` に `runtime/latest_mt5_compile_status.json` 由来のEA `.ex5` 鮮度、対象Tester `.ini`、対象 `ExpertParameters` `.set`、config参照setの同期状態をBacktest/Forward対象だけに絞って出す
- `Back/Forward Plan Validation` に、Backtest/Forwardが同じEA、Symbol、Period、Model、ExecutionMode、From/Toで比較できること、Backtestは `ForwardMode=0`、Forwardは非0、Optimizationは無効、Report名/`.set`/出力JSONが別名で上書きされないことを表示する。`--forward-mode` はForward Test側の分割指定として扱い、`mode=both` のBacktest stepには渡さず、純バックテストを維持する。`mode=both` の `--execute` または `--collect-only` では、この検証がreadyでない場合に `back_forward_plan_validation_not_ready` でstep実行を止める。`mt5_tester_status.py`、status watcher、`spec_coverage.py` へready/status/reasonsを転記し、MT5画面で回す前に計画自体の不整合をファイルだけで検出できるようにする
- `mt5_tester_status.py` と `mt5_tester_status_watch.py` に `manual_prerequisites_ready` / reasons / compile status pathを転記し、`latest_mt5_back_forward_run.md` を開かなくてもstatus Markdown、`latest_mt5_tester_status.json` 直下のalias、またはheartbeatから手動Strategy Tester前の前提条件を確認できる。status JSON直下には `manual_prerequisites_ready`、`back_forward_plan_validation_ready`、`back_forward_run_manual_prerequisites_ready`、`back_forward_run_plan_validation_ready` を置き、ネストを読まない監視でもMT5実行前の前提条件とBack/Forward計画検証を判定できるようにする
- `spec_coverage.py` は `manual_prerequisites_ready=false` を `mt5_back_forward_manual_prerequisites_not_ready` として未完了理由にし、`refresh_mt5_back_forward_prerequisites` のNext Actionでcompile status更新とBack/Forward plan再生成を促す
- `spec_coverage.py` はPromotion Gateがcompile status、MT5 tester status、統合手動キュー、手動collect dry-run、Back/Forward runner、履歴status、BUY/SELL score weight探索/setなどの判断証跡より古い場合も `promotion_gate_stale_vs_dependencies` として未完了理由にし、Gate再生成のNext Actionを出す。ただし統合手動キューと手動collect dry-runはGate生成後に作る派生handoffなので、entryの `promotion_generated_at` / `current_promotion_generated_at` が現行Gateと一致し、`stale_entry_count=0` かつ queue refresh が成功している場合は、同じGate世代から派生したcurrent artifactとして扱い、stale dependencyにはしない
- `spec_coverage.py` は `latest_mt5_tester_status.json` のNext Action Runnerが現在のPromotion Gateと一致しない場合も `mt5_next_action_runner_not_current` として未完了理由にし、MT5起動前に `latest_mt5_next_action_run.*` の再生成を促す
- `spec_coverage.py` はNext Action Runnerに未処理の高優先度Actionが残っている場合も `mt5_next_action_runner_blocked_by_prior_actions` として未完了理由にし、選択中runnerを飛ばしてMT5を起動しないようにする。この時、blocking prior actionのpriority/area/action/reason/commandと `P1 bridge:...` 形式のsummaryもNext Actionに表示し、`command_text` がある先行Actionは `run_blocking_prior_action_N` としてcommands欄にも出すことで、どの先行Actionをどの順で解消すべきかをcoverageだけで確認・実行できるようにする。`MT5 Operator Handoff` が手動Strategy Testerを推奨している場合は、このblockerが選択中Next Action Runnerだけに適用され、Standaloneの手動Strategy Testerキューは `run_mt5_manual_test_queue` から並行して進められることも同じNext Actionに表示する
- `spec_coverage.py` は保存JSON、Markdown、標準出力のすべてに `not_complete_reason_count` と `next_action_count` を出し、監視スクリプトが `not_complete_reasons` / `next_actions` 配列を展開しなくても未完了理由数と未処理Action件数を確認できるようにする。保存JSON、Markdown、標準出力には `blocked_phase_count`、`first_blocked_phase`、`first_blocked_phase_primary_reason`、`first_blocked_phase_primary_next_action` も出し、短縮JSONだけで最初に詰まっているPhaseと実行入口を読めるようにする
- `spec_coverage.py` は `phase_statuses` に加えて `blocked_phase_count` と `phase_current_blockers` をJSONへ出し、Phase別の主要ブロッカー、主要 `next_action`、関連 `next_action` ID、該当理由を構造化する。各blockerには `primary_next_action_id` / priority / area / summary と `primary_next_action` を持たせる。Markdownの `Phase Current Blockers` も主要Actionと関連Action IDを表示し、履歴/Bridge、Back/Forward、BUY診断、score weightなど複数領域の未完了理由がある時に、どのPhaseからどのActionで進めるかを短く確認できるようにする
- `spec_coverage.py` はBridge/EA未readyまたはEA POST/snapshot停滞を検出した場合、履歴更新より先に `refresh_bridge_status` を上位Next Actionとして出す。`latest_bridge_recovery_plan.json` がある場合はBridge Recoveryのstatus、blocking reasons、next action、operator summary、operation card、verification commandsもNext Action手順へ転記し、coverage MarkdownだけでEA再起動待ち、snapshot stale、履歴pending stale、復旧後に実行する確認コマンドを確認できるようにする。Bridge activity manual stepsには `ea_liveness_signal` と `config_get_recent_but_ea_post_stale` も表示し、`GET /config` だけが新しい状態をEA稼働証跡として誤読しない。履歴pendingがstaleの時は `refresh_history` Actionにも同じBridge Recovery要約を出し、Bridge statusとRecovery planの再生成コマンドもcommands欄に含め、履歴取得要求の再送ではなくEA POST復旧待ちであることを履歴Action単体でも判断できるようにする。一方で `Swing_Evaluation_Trader` はBridge/GPT非依存の単体EAなので、`ready_for_mt5_validation=false` の間もMT5 Strategy TesterのBack/Forward手順、手動キュー、collect-only導線は表示する。Bridge未readyは注意としてmanual stepsへ残すが、Standalone Testerの実行コマンドは消さない。Bridge readyを必須にしたい診断時だけ、runner側で `--require-bridge-ready` を明示する
- `spec_coverage.py` のMQL5 artifact確認はBack/Forward用だけでなく、Optimization、stable candidate、BUY/SELL refit、hour/time/trend/calendar validation用の `.ini` / `.set` も監視対象にし、仕様に列挙したMT5検証ファイルの欠落を未完了理由にする
- `spec_coverage.py` は各Tester `.ini` の `Expert` / `ExpertParameters` / `Symbol` / `Period` / `Model` / `Optimization` / `ForwardMode` と、各 `.set` のsignal/live/risk/button安全入力をmarkerとして確認し、存在するだけで誤ったset参照やForward設定を通さない。`.set` では `InpDailyLossLimit=5000.0`、`InpConsecutiveLossLimit=20`、`InpConsecutiveLossCooldownMinutes=120`、`InpRequireStrategyTester=true`、`InpChartButtonDryRunOnly=true`、`InpAllowChartButtonTrading=false` も確認し、古い3連敗停止、Tester限定漏れ、ボタン発注許可の混入を検出する
- MQL5 artifactの欠落、テスト参照不足、marker gapがある場合は `fix_mql5_artifact_coverage` のNext Actionを出し、MT5 Strategy Testerへ進む前に対象ファイル修正、`mt5_compile_status.py`、`spec_coverage.py` の再確認へ戻す
- `runtime/latest_mt5_compile_status.json` がMQL5 artifact更新より古い場合、またはsources/binaries/Tester `.ini`/`.set` の同期・参照readyフラグがfalseの場合は `refresh_mt5_compile_status` のNext Actionを出し、MT5 Strategy Tester起動前にcompile/status更新へ戻す
- BacktestとForwardの両レポートが揃った場合、closed件数、PF、平均R、期待R、価格R DD、損益差分を比較し、`executed_consistent` / `executed_degraded` / `executed_below_break_even` / `executed_sample_shortage` に分類する

### `mt5_manual_test_queue.py`

役割:

- `latest_mt5_back_forward_run.json`、SELL用 `latest_mt5_next_action_run.json`、BUY用 `latest_mt5_next_action_run_buy.json` の `manual_strategy_tester` と `manual_collect_readiness` を読み、MT5画面で順に回す手動Strategy Testerキューを `runtime/latest_mt5_manual_test_queue.json` / `.md` に集約する
- キューにはBacktest、Forward、SELL score sample collection、BUY score sample collectionのstep表、各Report名、Inputs、Forward設定、runner生成時刻、参照Promotion Gate生成時刻、Gate decision、手動実行開始下限時刻、collect-onlyコマンドをまとめる。上部には `strategy_tester_targets` を置き、MT5上で今回回す目的、queue/step、Report、Inputs、start after、collect after、collect状態、自動起動種別、`run_type`、`expected_report_artifact`、`report_expectation_note` をMarkdown上でも先に確認できるようにする。`Optimization=0` のBacktest/Forward/sample collectionは単発Strategy Testなので、Forward指定があっても期待成果物はHTML ReportとAgent CSVであり、Optimization ForwardのXML/forward XML pairとは区別する。Back/Forward Runnerのように `runner_generated_at` を持たないartifactでは、計画JSONの `generated_at` をrunner生成時刻として表示する
- `--include-optimization-configs` を指定した場合は `Swing_Evaluation_Trader_optimization.ini` と `Swing_Evaluation_Trader_next_optimization.ini` を静的Strategy Tester entryとしてBack/Forward/SELL/BUYの後ろに追加する。任意の診断 `.ini` は `--include-static-config` で繰り返し追加できる。年次候補や短期 `.ini` とは別のReport名/FromDate/ToDate/ForwardModeで再実行すべき候補は `--include-static-candidate-label` で追加し、`static_candidate_labels` として保持する。たとえば `sell_hour12_m30m15_2025` / `sell_hour12_m30m15_calendar_2025` は `2025.01.01` から `2025.12.31`、ForwardMode `3`、年次Report名へ上書きした `runner_execute` stepとして表示し、短期 `.ini` の `2026.06.30` から `2026.07.08` を年次証跡として誤用しない。標準の別名artifactは `runtime/latest_mt5_manual_test_queue_with_optimization.json` / `.md` とし、通常キューを壊さずMT5 Optimization Forwardを同じ手順で回せるようにする。静的config/candidate entryも `strategy_tester_targets`、Operation Cards、Manual Execution Checklist、Auto Launch Commands、collect-onlyコマンドに出し、`Optimization=2` かつForward有効のstepは `run_type=optimization_forward`、`expected_report_artifact=XML + forward XML + Agent CSV` として扱う。静的config/candidate entryは `static_strategy_config_state` に `manual_run_start_after` を保持し、`mt5_manual_collect.py` のqueue refresh後も `--csv-modified-after` が手動実行前の時刻から動かないようにする
- キューJSONには `execution_checklist`、`operation_cards`、`operator_handoff.quick_input` を持たせ、MarkdownにはMT5 Strategy Tester画面で順に実行するBacktest、Forward、SELL sample、BUY sampleを `[ ]` 付きチェックリストと操作カード表として表示する。`quick_input` には次に実行する1stepのPurpose、Expert、Symbol、Period、Model、From/To、Forward、ForwardMode、Optimization、Inputs、Report、Expected output、start after、launch kindを入れ、`latest_mt5_manual_test_queue.md` と `latest_mt5_tester_status.md` の上部だけでMT5画面へ入力する値を確認できるようにする。`operator_handoff` には `next_queue_step`、`next_quick_input`、`next_step_operator_summary` と同内容の `next_mt5_step_summary`、および `dry_run_command_text` / `execute_command_text` と同内容の `collect_dry_run_command_text` / `collect_execute_command_text` / `collect_execute_and_refresh_analysis_command_text` / `collect_execute_and_refresh_all_command_text` も持たせ、Markdownを開かない監視やstatus/coverage転記がcollect操作名として同じ値を読めるようにする。さらに `latest_mt5_manual_test_queue.json` と `latest_mt5_manual_test_queue_with_optimization.json` のトップレベルにも `next_queue_step`、`next_mt5_step`、`quick_input`、`next_quick_input`、`next_step_operator_summary`、`next_step_summary`、`next_step_collect_filter_summary`、`collect_*_command_text` aliasを出し、status/watchを経由しなくてもキュー単体から次のMT5 Backtest/Forward操作と回収コマンドを読めるようにする。`operation_cards` には `is_next`、`action`、purpose、queue/step、Symbol、Period、Dates、Forward、Optimization、Inputs、Report、collect statusを入れ、Markdownを開かない監視やstatus/coverage転記でも次にMT5で実行する1手を同じ形で読めるようにする。各行にはqueue/step、Symbol、Period、Model、Dates、Forward、Optimization、`run_type`、`expected_report_artifact`、Inputs、Report、start afterを含め、手動入力時に通常のstep表と同じ内容を順番に確認できるようにする。`Optimization=0` の単発Strategy Testは `Disabled`、Optimization Forwardの静的configは `Fast genetic algorithm` と表示し、MT5画面上でOptimizationを有効にすべきstepを明示する
- Markdownには `Auto Launch Commands` も表示し、各stepのworkspace `.ini`、MT5側 `MQL5/Profiles/Tester` `.ini`、起動コマンドを出す。固定 `.ini` のReport/Dates/Forwardがstepと一致する場合はWine経由の `terminal64.exe /config:` 直起動を出し、Report名などのruntime上書きが必要な場合はrunner executeコマンドへフォールバックする。既存terminalが開いている場合は手動チェックリストを使い、terminalを閉じてから自動起動する場合だけこのコマンドを使う
- SELL/BUY side runnerが `current_for_execution=false` または `gate_stale_reason` を持つ場合は `stale_runner_artifacts` として扱い、Manual Execution Checklist、Auto Launch Commands、collect対象から外す。Markdownには `Stale Runner Refresh` を表示し、side別 `mt5_next_action_run.py --target score_weight_sample_collection --focus-side ...` の再生成コマンドを出して、古いGate世代のReport名や出力先でMT5 Strategy Testerを回さないようにする
- `ready_to_collect_count`、`waiting_count`、`all_collect_ready`、`blocking_reasons`、`next_action` を出し、MT5上で手動実行した後にどのcollect-onlyを実行できるか、まだReport/Agent CSV待ちなのかをファイル単体で確認できるようにする
- `mt5_tester_status.py` はこのキューを `manual_test_queue` として読み、`latest_mt5_tester_status.md` の `MT5 Manual Test Queue` 欄にentry/total/stale/step/waiting/ready件数、blocking reasons、runner生成時刻、参照Promotion Gate生成時刻、current Gate生成時刻、Gate decision、current Gate decision、selected action current、stale理由、Back/Forward/SELL/BUYのReport/Inputs表、MT5 Operation Cards、Manual Execution Checklist、Auto Launch Commands、`Stale Runner Refresh` を出す。`runtime/latest_mt5_manual_test_queue_with_optimization.json` / `latest_mt5_manual_queue_launch_with_optimization.json` / `latest_mt5_manual_collect_with_optimization.json` がある場合は、`MT5 Manual Test Queue With Optimization` / `MT5 Manual Queue Launch With Optimization` / `MT5 Manual Collect With Optimization` 欄にも追加表示し、標準キューと別名でOptimization Forward待ちを併読できるようにする。`mt5_manual_test_queue.py` は通常運用では最新 `latest_promotion_gate.json` を読み、SELL/BUY side runnerについて現在のGateでも同じaction/side/出力先が選ばれているか再照合する。同じactionならrunner作成時Gateが古くても `current_for_execution=true` のまま `current_promotion_generated_at` を最新Gateへ更新し、不一致ならstale runnerとして手動実行対象から外す。標準出力JSONにも `manual_test_queue_status`、`manual_test_queue_next_action`、`manual_test_queue_entry_count`、`manual_test_queue_total_entry_count`、`manual_test_queue_stale_entry_count`、`manual_test_queue_step_count`、`manual_test_queue_waiting_count` を含め、operator summaryには `manual_test_queue_with_optimization_*` / `manual_queue_launch_with_optimization_*` / `manual_collect_with_optimization_*` の主要状態も追加する
- `mt5_tester_status.py` は `mt5_operator_handoff` として、MT5上で次に実行するStrategy Tester step、Inputs、Report、Forward、実行後のcollect dry-run/executeコマンド、collect後に `mt5_strategy_tester_analysis.py` 相当の横断採用判定まで更新する `manual_collect_execute_and_refresh_analysis_command_text`、Promotion Gate / Strategy Tester Analysis / Spec Coverage まで一括更新する `manual_collect_execute_and_refresh_all_command_text`、自動 `/config` 起動が端末起動中で止まっているか、Bridge Recoveryが単体EAのStrategy Testerを止めないことを `latest_mt5_tester_status.json` / `.md` の上部へ集約する。これによりMT5を開いたままBacktest/Forwardを行う場合も、statusファイルだけで次の手動操作と回収・分析コマンドを確認できる
- `mt5_tester_status_watch.py` は `mt5_operator_handoff_*` と `manual_test_queue_*` をheartbeatへ転記し、Operator Handoffのstate/recommended path/next MT5 step/collect command/Bridge非依存注記/一括更新commandと、`manual_test_queue_exists/status/next_action/entry_count/total_entry_count/stale_entry_count/step_count/ready_to_collect_count/waiting_count/all_collect_ready/blocking_reasons/entries/strategy_tester_targets/operation_cards/execution_checklist` を現行watcher schemaの必須snapshot keyにする。古いwatcherがこの統合キューとTarget要約、MT5 Operation Cards、Manual Execution Checklist、古いrunner混入を示すstale件数、Operator Handoffを転記できない場合は `incompatible` として再起動を促す。最適化込みキューは `manual_test_queue_with_optimization_*` / `manual_queue_launch_with_optimization_*` / `manual_collect_with_optimization_*` としてsnapshotに追加し、`manual_test_queue_with_optimization_next_step_summary`、`manual_queue_launch_with_optimization_queue_operator_handoff_next_step_summary`、`manual_queue_launch_with_optimization_queue_operator_handoff_collect_execute_and_refresh_full_analysis_command_text`、`manual_operator_packet_with_optimization_next_step_summary` を必須snapshot keyに含める。これによりOptimization Forwardの待ち状態、次step、取り込み候補、full analysis更新付きcollect入口をheartbeatから確認できるようにする
- `spec_coverage.py` は `runtime/latest_mt5_manual_test_queue.json` に加えて、SELL用 `runtime/latest_mt5_next_action_run.json` とBUY用 `runtime/latest_mt5_next_action_run_buy.json` も主要runtime artifactとして監視し、古い手動手順を見てMT5 Strategy Testerを回さないようにする。存在する場合は `runtime/latest_mt5_manual_test_queue_with_optimization.json` もoptional runtime artifactとしてRuntime Artifacts表に表示し、static config数、Optimization/Next OptimizationのTarget、次step、`XML + forward XML + Agent CSV` 期待成果物を確認できるようにする。Back/Forward未実行またはBUY/SELL score weight sample不足が残っていて、統合キューが `waiting_for_manual_strategy_tester_results` / `ready_to_collect_all` の場合は `run_mt5_manual_test_queue` のNext Actionを出し、`latest_mt5_tester_status.json.operator_summary` 由来の次のMT5 Strategy Tester step、launch blocker、collect executeコマンドを先頭付近に表示する。さらにentry/total/stale/step/waiting/ready件数、blocking reasons、current Gate上で実行可能なentry数、selected action一致/不一致件数、current Gate生成時刻、current decision、stale理由、Manual Execution Checklist、Auto Launch Commands相当のworkspace `.ini` / MT5 `.ini` / launch kind / launch command、entry別collect status、start after、collect after、runner生成時刻、Gate生成時刻、current Gate生成時刻、decision、`latest_mt5_manual_queue_launch.json` のstatus / next_action / selected queue/step / launch kind / blocked / blocked reasons / running terminal count、`latest_mt5_manual_collect_run.json` のstatus / next_action / selected / waiting / invalid / queue_refresh / blocking_reasonsをCoverage Markdownだけで確認できるようにする。手動実行待ちの場合は `mt5_manual_queue_launch.py` のdry-runコマンドもNext Actionに出し、terminalを閉じた後に次の1ステップだけを安全に起動できるようにする。同じNext Actionに `refresh_manual_test_queue_with_optimization`、`dry_run_manual_queue_launch_next_with_optimization`、`dry_run_manual_queue_collect_ready_with_optimization` も出し、通常キューとは別名でBack/Forward/SELL/BUY後のOptimization ForwardをMT上で回せるようにする。`refresh_mt5_tester_status` 系コマンドには通常キューと最適化込みキュー、launch dry-run、collect dry-runの各artifact pathを明示し、coverageからstatusを再生成してもOptimization Forward待ちの表示が落ちないようにする。全entryがcollect可能な場合は、entry別collect-onlyコマンドも同じNext Actionに表示する。SELL/canonicalまたはBUY runner artifactが欠落・staleの場合、または統合キュー自体が `stale_runner_artifacts` / `stale_entry_count>0` の場合は `refresh_mt5_next_action_runner_artifacts` のNext Actionを出し、stale entry別refreshコマンド、runner再生成、統合キュー再生成、MT5 tester status再生成のコマンドをまとめて表示する
- `mt5_strategy_tester_analysis.py` の採用候補に `candidate_source_time_missing:*`、`candidate_source_time_mismatch:*`、`candidate_source_time_files_stale:*`、または `candidate_source_time_files_missing:*` が残る場合、`spec_coverage.py` は `mt5_strategy_candidate_source_time_missing:*` / `mt5_strategy_candidate_source_time_mismatch:*` / `mt5_strategy_candidate_source_time_files_stale:*` / `mt5_strategy_candidate_source_time_files_missing:*` を未完了理由にし、`refresh_mt5_strategy_source_time_evidence` のNext Actionを出す。このActionは `refresh_manual_test_queue_with_optimization`、最適化込みqueue launch dry-run、collect dry-run、`--refresh-post-collect-analysis` 付きcollect execute、横断分析再生成、coverage再生成をcommands欄にまとめ、年次候補やout-of-year候補をsource-time証跡なし、または参照Agent CSVが再現できない状態で採用しないようにする。Runtime Artifacts表には `strategy_tester_analysis_source_artifacts` とlabel別の生成時刻/状態/pathも表示し、横断分析が読んだPromotion Gate、Back/Forward run、手動キュー世代をCoverageだけで照合できるようにする。さらにPromotion GateまたはBack/Forward runの `generated_at` が横断分析内のsource artifact世代と一致しない場合は `mt5_strategy_tester_analysis_stale_vs_dependencies:*` を未完了理由にし、`refresh_mt5_strategy_tester_analysis` のNext Actionで横断分析とCoverageの再生成を促す。循環を避けるため、この鮮度判定は `spec_coverage` や手動キューのような派生handoffではなく、安定証跡のPromotion GateとBack/Forward runに限定する
- `mt5_strategy_tester_analysis.py` のBUY candidate gap planが `needs_buy_diagnostic` の場合、adoption blockerにも `buy_candidate_gap:needs_buy_diagnostic[:labels]` を表示し、`spec_coverage.py` は `mt5_strategy_buy_candidate_gap:*` を未完了理由にし、`refresh_mt5_buy_candidate_gap_evidence` のNext Actionを出す。このActionはBUY診断候補ラベル、最適化込みキュー再生成、operator packet再生成、queue launch dry-run、collect dry-run、auto collect watch、`--refresh-post-collect-analysis` 付きcollect execute、横断分析再生成、coverage再生成をcommands欄にまとめる。SELL側候補だけで採用判断が進まないよう、BUY診断の不足をsource-time問題やPromotion Gate不合格に埋もれさせず、Phase 4/7のblockerとして独立表示する
- `spec_coverage.py` は `latest_mt5_back_forward_run.json` の `performance_comparison` を読み、`run_or_collect_mt5_back_forward` Next ActionにBack/Forward比較status、backtest/forwardのclosed、PF、平均R、delta、`--min-closed` 判定を表示する。`forward_sample_shortage` / `backtest_sample_shortage` / `back_forward_sample_shortage` の場合は候補拒否ではなく、同じ実行条件を引き継いで `2025.01.01` から `2025.12.31` へ期間拡張したBack/Forward再実行コマンドを出す。既存のfrom/toが180日以上ならその拡張済み窓を再利用し、短期窓の件数不足をForward劣化と誤読しないようにする
- `spec_coverage.py` はBUY/SELLの `score_weight_follow_up_*` Next Actionに、score weight探索のtop候補、walk-forward status、test件数/必要件数、不足fold、mean PF/平均R、baseline比delta、レジーム別候補のsample shortage、`score_weight_set.py` の `can_write` / `written` / `skip_reason` / `walk_forward_status` / `failure_mode` を表示する。これにより、MT5 Strategy Testerでsample collectionを回す前に、PFが高く見える候補でもwalk-forwardで採用不可なのか、全体性能劣化なのか、レジーム別候補だけ追加サンプル待ちなのか、`.set` 書き出しがなぜ止まったのかをCoverageだけで確認できるようにする
- Runtime Artifacts表にも各artifactの `status`、`next_action`、`blocking_reasons`、manual collectのready/selected/waiting/invalid件数、queue status/next action/refresh状態を表示し、Next Action表まで横スクロールしなくても現状の停止理由を確認できるようにする

### `mt5_manual_queue_launch.py`

役割:

- `runtime/latest_mt5_manual_test_queue.json` の `execution_checklist` から次に起動すべき1ステップを選び、既定はdry-runで `runtime/latest_mt5_manual_queue_launch.json` / `.md` に選択step、起動種別、コマンド、既存terminal検出、ブロック理由、次アクションを残す
- キュー側の `operator_handoff` を `latest_mt5_manual_queue_launch.json` / `.md` に転記し、launch artifact単体でもhandoff state、次のMT5 step、selected stepとの一致、待機中entry、手動実行後のcollect dry-run/executeコマンドを確認できるようにする
- launch artifactには `queue_entry_count`、`queue_total_entry_count`、`queue_step_count`、`queue_waiting_count`、`queue_step_report_ready_count`、`queue_step_waiting_report_count`、`queue_step_launch_needed_count` も残し、`queue_refresh_source_count` が再確認したrunnerソース数であり、MT5上で回す実行キュー件数とは別であることをMarkdown/CLI/status/coverageから確認できるようにする
- `direct_config` のstepはJSON内の `launch_command` 配列を使い、shell文字列をそのまま実行しない。`runner_execute` のstepは `launch_command_text` を `shlex.split` して実行し、SELL/BUY sample collectionのようにReport名のruntime上書きが必要なstepを既存runner経由で起動できるようにする
- `--execute` が明示された場合だけ選択stepを起動する。既定では既存 `terminal64.exe` が起動中の `direct_config` は `running_terminal_blocks_direct_config` で止め、既存MT5へ `/config` が吸われてStrategy Testerが走らない状態を避ける。承知して実行する診断時だけ `--allow-running-terminal` を使う
- `--step-order`、`--queue-id`、`--step-label` で対象stepを明示できる。指定がない場合はキュー上の最初の起動可能stepを選ぶ。手動キューがstale runnerを除外しているため、このランチャーも古いGate世代のBUY/SELL runnerを起動対象にしない
- `mt5_tester_status.py` は `runtime/latest_mt5_manual_queue_launch.json` を読み、status Markdownに `MT5 Manual Queue Launch` として選択step、起動種別、command、既存terminal検出、blocked reasonsを表示する。これにより、`latest_mt5_manual_test_queue.md` を開かなくても、次に自動起動されるstepと止まっている理由をstatusだけで確認できる
- `spec_coverage.py` は `runtime/latest_mt5_manual_queue_launch.json` もRuntime Artifactsとして監視し、選択queue/step、launch kind、blocked、blocked reasons、running terminal countに加えて、launch handoffのstate、selected stepとの一致、次のMT5 step、待機entry、collect executeコマンドをRuntime Artifacts表と `run_mt5_manual_test_queue` のNext Actionに出す。これにより、MT5を閉じる前に自動起動が止まっている理由と、手動実行後の回収入口をcoverageだけで確認できる
- manual queue/operator handoffは `next_step_operator_summary` と同じ値を `next_step_summary` aliasにも出し、full analysis付きcollectコマンドも `collect_execute_and_refresh_full_analysis_command_text` aliasで残す。これにより、MT5操作UI、status watcher、coverageが同じ短い次step説明と回収コマンド名を読めるようにする

### `mt5_manual_collect.py`

役割:

- `runtime/latest_mt5_manual_test_queue.json` を読み、`collect_ready=true` のentryだけを安全なcollect-only対象として選ぶ
- 既定はdry-runで、元runnerの `manual_collect_readiness` と統合キューを再評価してから `runtime/latest_mt5_manual_collect_run.json` / `.md` にselected/waiting/invalid件数、`next_action`、`blocking_reasons` を残す
- `--execute` を明示した時だけ、許可済みの `analysis/mt5_back_forward_run.py --collect-only` または `analysis/mt5_tester_run.py --collect-only` コマンドを順番に実行する。`--execute` を含むcollect commandや許可外scriptはinvalidとして拒否する。既定のsource runner再評価が失敗した場合は `blocked_queue_refresh_failed` としてcollect実行を止め、保存済みqueueを意図的にそのまま使う時だけ `--no-refresh-queue` を明示する
- `queue_refresh.status`、refreshed source別ready/status、planned/skipped/invalid/executions、`next_action`、`blocking_reasons` を出し、MT5上で手動Strategy Testerを回した後に、collectへ進めるか、まだReport/Agent CSV待ちか、runner再評価を直すべきかをこのファイルだけで確認できるようにする。planned/skipped/invalidにはrunner生成時刻、Gate生成時刻、Gate decisionも残し、MT5で実行した手順とcollector対象の世代を照合できるようにする
- collect run JSON/Markdownには統合キュー由来の `queue_step_count`、`queue_step_report_ready_count`、`queue_step_waiting_report_count`、`queue_step_launch_needed_count` も残し、MT5上でBacktest/Forward/sampleをどこまで実行済みか、collect前に次のStrategy Tester stepを回すべきかをcollector単体で確認できるようにする
- `--refresh-strategy-tester-analysis` を指定した場合、collectが `collect_executed` になった後に `mt5_strategy_tester_analysis.py` 相当の横断分析を再生成し、Back/Forwardと複数Optimization結果の採用状態、BUY/SELL候補、ブロッカーを `runtime/latest_mt5_strategy_tester_analysis.json` / `.md` に更新する。collect未readyやcollect失敗では横断分析を実行せず、collect run JSON/Markdownの `strategy_tester_analysis_refresh` にskip理由を残す
- `--refresh-post-collect-analysis` を指定した場合、collectが `collect_executed` になった後に Promotion Gate、Strategy Tester Analysis、Spec Coverage をこの順で再生成する。collect未readyやcollect失敗では各refresh結果にskip理由を残す。個別に `--refresh-promotion-gate`、`--refresh-spec-coverage` も指定できるが、手動MT5実行後の採用可否確認では一括更新を優先する
- `mt5_tester_status.py` は `manual_collect_run` を読み、status Markdownと標準出力JSONにstatus、selected/waiting/invalid、queue refresh、next action、runner/Gate世代、`Collect execute + analysis command` と `Collect execute + full analysis command` を表示する
- `mt5_tester_status_watch.py` は各runの先頭で `mt5_manual_collect.py` をdry-run実行し、`manual_collect_refresh_*` と最新 `manual_collect_run_*` をheartbeatへ転記する。最適化込みキューについても `manual_collect_with_optimization_refresh_*` と `manual_queue_launch_with_optimization_refresh_*` を追加で更新し、`latest_mt5_manual_test_queue_with_optimization.json` からOptimization/Next Optimizationの手動実行待ち、collect待ち、端末起動中ブロックを同じheartbeatで追えるようにする。さらにauto collect watcherのoperator packetから、source-time分析再生成コマンドとBUY診断collectコマンド、その利用可否、source-time status/issue labels、BUY gap status/reason/diagnostic labelsを `manual_auto_collect_watch_operator_packet_strategy_*` としてheartbeat必須snapshot keyに転記する。これにより、MT5画面で手動テストを実行した後、常駐watcherだけでcollect可能状態への遷移、次の分析更新入口、再実行すべき候補ラベルを検出できる。実際の取り込み実行は自動では行わず、`selected_count > 0` を確認してから `mt5_manual_collect.py --execute` を明示する
- `mt5_tester_status_watch.py` は `manual_queue_launch_selected_matches_queue_handoff`、`manual_queue_launch_queue_operator_handoff_state`、`manual_queue_launch_queue_operator_handoff_next_mt5_step`、`manual_queue_launch_queue_operator_handoff_next_step_summary`、`manual_queue_launch_queue_operator_handoff_collect_ready`、`manual_queue_launch_queue_operator_handoff_waiting_entry_ids`、collect dry-run/execute/full-analysisコマンドも必須snapshot keyとしてheartbeatへ転記し、古いwatcherがlaunch handoffを出せない場合は `incompatible` として再起動対象にする
- `promotion_gate.py` は `latest_mt5_tester_status.json.operator_summary` を `MT5 Operator Summary` として表示し、Promotion Gate Markdown上段だけで次にMT5 Strategy Testerで回すqueue/step、queue/launch/collect状態、自動 `/config` 起動blocker、手動実行後のcollect dry-run/executeコマンドを確認できるようにする。詳細欄の `MT5 Manual Queue From Watcher` も、status watcher heartbeatからmanual queue handoffとmanual queue launch handoffを表示し、Forward/Inputs/Report、選択stepとキュー推奨stepの一致、手動チェックリストを確認できるようにする
- `mt5_tester_status_watch.py` は `mt5_tester_status.py` を起動する前に、現行 `implementation_version` と必須snapshot keyを持つpre heartbeatを書き、statusが古い常駐watcherのheartbeatを読んで `incompatible` になる状態を避ける。status生成後は最新snapshot入りheartbeatを書き、さらにstatusをもう一度同期生成して、`latest_mt5_tester_status.json` / `.md` 内の `status_watch_heartbeat` も最終heartbeatを読んだ状態にする。最終heartbeatには `status_refresh_phase=synced_status_refresh` を残し、初回statusのreturncodeは `initial_status_returncode` に保存する。heartbeatには `manual_queue_launch_status`、`manual_queue_launch_selected_item`、`manual_queue_launch_launch_command_kind`、`manual_queue_launch_command_text`、`manual_queue_launch_blocked_reasons`、`manual_queue_launch_running_terminal_count` も残し、status watcherだけで次に自動起動されるStrategy Tester stepと `/config` 起動が止まっている理由を確認できるようにする
- `runtime_watchers.py` のMT5 tester status watcher起動コマンドには `--manual-test-queue`、`--manual-queue-launch`、`--manual-collect-run` と、最適化込み用の `--manual-test-queue-with-optimization`、`--manual-queue-launch-with-optimization`、`--manual-collect-with-optimization`、`--manual-operator-packet-with-optimization` を含める。古いwatcherが統合キュー、次の自動起動候補、Manual Execution Checklist、collector状態、operator packet由来の次操作を転記できない場合はheartbeat incompatibleまたは任意フィールド欠落として再起動対象にする

### `mt5_manual_auto_collect_watch.py`

役割:

- `runtime/latest_mt5_manual_test_queue_with_optimization.json` を既定の監視対象にし、`mt5_manual_collect.py` のdry-runを定期実行して `runtime/latest_mt5_manual_auto_collect_watch.json` / `.md` にready/waiting/invalid件数、次アクション、実行可否を残す
- dry-runでキューを再評価した後、`runtime/latest_mt5_manual_queue_launch_with_optimization.json` / `.md` と `runtime/latest_mt5_manual_operator_packet_with_optimization.json` / `.md` も再生成し、常駐監視だけで「次にMT5 Strategy Testerで回す1手」、`/config` 自動起動可否、running terminal blocker、Bridge Recovery、Bridge検証コマンド、Strategy Evidence、source-time分析再生成、BUY診断collect、collect手順を最新キューから確認できるようにする。operator packetは `next_operator_action` として `manual_strategy_tester_input` / `auto_launch_selected_step` / `collect_ready_results` / `wait_for_mt5_report` などの正規化action、mode、instruction、command、follow-up collect command、`quick_input` をJSON/Markdownに表示し、長いキューを読まなくても次に人間がMT5で行う操作と入力値を判定できるようにする。さらに `next_operator_action_name`、`next_operator_mode`、`next_operator_quick_input`、`next_operator_launch_state`、`next_operator_instruction`、`next_operator_command_text`、`next_operator_follow_up_command_text`、`auto_launch_command_text`、`auto_launch_blocked`、`manual_run_start_effective_after` をトップレベルaliasとして残し、ネストしたpacketを展開しない監視スクリプトや手元確認でも次操作、MT5入力値、回収下限時刻を読めるようにする
- `runtime/latest_bridge_recovery_plan.json` と `runtime/latest_mt5_strategy_tester_analysis.json` をoperator packet更新へ渡し、auto collect watcher経由の再生成でもBridge status、Bridge検証コマンド、Back/Forward証跡、source-time刷新計画、source-time分析再生成コマンド、BUY診断キュー、BUY診断collectコマンドが落ちないようにする
- 既定は監視のみで、`--execute-ready` を明示した時だけ `ready_for_collect_execute` かつ `selected_count>0` かつ `invalid_count=0` のcollect-onlyを実行する。実行時は `--refresh-post-collect-analysis` を付け、Promotion Gate、Strategy Tester Analysis、Spec Coverageまで更新する
- `returncode=2` のdry-runは「まだreadyなcollect対象がない」状態として扱い、watcher自体の失敗とは区別する。MT5でBacktest/Forward/Optimizationを手動実行した後、操作者はこのwatcherのMarkdownだけで「まだ待ち」「取り込み可能」「取り込み済み」を確認できる。JSON/Markdown/heartbeatには `collect_dry_run_command_text` と `collect_execute_command_text` を残し、ready検知後に同じ条件で確認または `--execute --refresh-post-collect-analysis` 付き取り込みを再実行できるようにする
- JSON/Markdown/heartbeatのトップレベルに `ready_for_collect_execute`、`selected_count`、`ready_entry_count`、`waiting_count`、`invalid_count` を残し、nested `dry_run` を展開しなくてもMT5実行後にcollectへ進めるか、まだ何件待ちかをruntime watcher/coverageから直接読めるようにする
- `--max-runs 1` の手動one-shot実行では、明示的に `--heartbeat` / `--pid-file` を渡さない限り、常駐監視用の共有heartbeat/PIDを上書きしない。常駐化は `runtime_watchers.py` から `--max-runs 0`、明示heartbeat/PID付きで起動し、heartbeatには `heartbeat_enabled`、`pid_file_enabled` も残す。これにより手動確認でdaemon heartbeatが `continuous=false` やPID不一致になり、監視がstale扱いになる事故を避ける
- `spec_coverage.py` はこのwatcherをoptional runtime artifactとして表示し、`run_mt5_manual_test_queue` と `refresh_mt5_strategy_source_time_evidence` のNext Actionに監視のみの1回実行コマンドと `--execute-ready` 付きの取り込みコマンドを出す。Runtime Artifacts要約には、operator packet由来のsource-time status/issue labelsとBUY gap status/reason/diagnostic labelsも展開し、MT5上でBacktest/Forward Testを実行すべき理由と再検証すべき候補ラベルをcoverageだけで確認できるようにする
- `runtime_watchers.py` はこのwatcherを `mt5_manual_auto_collect` として起動・監視できるようにし、通常は `--execute-ready` を付けずにready検知だけを常駐化する。heartbeatには `watcher_pid`、pid file、continuous、run index、ready状態、collect dry-run/executeコマンド、dry-run/実行結果、operator packet更新結果、MT5 Start直前の `--mark-manual-run-start` コマンド、Bridge検証コマンド、source-time分析再生成コマンド有無、BUY診断collectコマンド有無をトップレベル項目として残し、古いwatcher、単発実行heartbeat、またはoperator packet更新結果を転記できないwatcherをruntime watcher管理で検出できるようにする

### `mt5_agent_csv_archive.py`

役割:

- MT5 Tester Agent配下に残っている `swing_evaluation_trades.csv` を一覧する
- 既定ではドライランとして、退避予定先を `runtime/latest_mt5_agent_csv_archive.json` / `.md` に出す
- Promotion GateがMT5実行計画用に作るpreviewは、複数計画の上書きを避けるため `runtime/latest_mt5_agent_csv_archive_<run_id>.json` / `.md` に出す
- `--execute` を指定した時だけ、既存CSVを `runtime/mt5_agent_csv_archive/<timestamp>/...` に移動する
- `--run-id` を指定すると、プレビューと実行で同じ退避先ディレクトリを使える。`/` や `..` を含むrun-idは拒否する
- `--include-source-time` を指定すると、各Agent CSVのclose `server_time` first/last、close件数、server_time欠落件数をプレビューに含める。`source_time_diagnostics.matches_expected_range=false` の復旧planではこのフラグ付きpreviewを使い、どの期間のCSVが残っているかを退避前に確認する
- 手動でMT5 Strategy Testerを回す前、または `source_time_diagnostics.matches_expected_range=false` の調査時に、どのAgent CSVが残っているかを確認する

### `mt5_compile_status.py`

役割:

- ワークスペース側 `.mq5` とMT5配置済み `.mq5` のhash一致を確認する
- MT5配置済み `.ex5` が最新 `.mq5` より新しいか確認する
- ワークスペース側 `mt5/TesterSets/*.set` とMT5側 `MQL5/Profiles/Tester/*.set` のhash一致を確認する
- ワークスペース側 `mt5/TesterConfigs/*.ini` とMT5側 `MQL5/Profiles/Tester/*.ini` のhash一致を確認する
- 各 `mt5/TesterConfigs/*.ini` の `ExpertParameters` が参照する `.set` の存在とMT5側同期状態を `tester_config_references` として表示する。score-weight refit用 `.set` はwalk-forward合格後に生成されるため、生成前は `generated_set_missing` として表示し、通常の必須 `.set` 欠落とは区別する
- EA/インジケータの再コンパイル漏れを `stale_binary` として検出する
- Tester `.set` の配置漏れや古い配置を `missing_mt5_set` / `set_not_synced` として検出する
- Tester `.ini` の配置漏れや古い配置を `missing_mt5_config` / `config_not_synced` として検出する
- 昇格ゲートでMT5実行ファイルの鮮度を必須条件にできる

### `promotion_gate.py`

役割:

- 自動売買への昇格条件を機械判定する
- バックテスト、買い/売り別成績、dry-run監査、フォワードテスト成績をまとめて判定する
- `runtime/latest_bridge_status.json` を読み、Bridge/EA接続が `ready` でない場合は履歴再取得やbacktest再実行より前にBridge/EA復旧next actionを出す
- Bridge Status欄と `bridge_status_ready` check valueには `ea_liveness_signal`、`config_get_recent`、`ea_post_recent`、`config_get_recent_but_ea_post_stale`、last config GETを表示し、`GET /config` だけが新しい状態をEA稼働証跡として扱わない
- score上位閾値の平均R/PFと、score閾値を上げた時の平均R劣化を判定する
- score上位閾値のサンプル不足と、サンプルはあるが平均R/PFが悪い状態をnext actionで分ける
- MT5単体EAのForward Test CSV集計を任意で必須条件にできる
- MT5 Forwardの `Risk Exposure` を確認し、単発lot、同時保有lot、同時建玉数、日次損失停止後open、連敗停止後openが安全条件を超えた場合は昇格不可にする
- MT5 Forwardのchart button行はdry-runまたはignoredだけを許可する。unsafe button rowが1件でもある場合は `mt5_forward_button` のnext actionを出し、`InpChartButtonDryRunOnly=true`、`InpAllowChartButtonTrading=false` のrisk preset確認、compile、Forward再実行計画を表示する
- MT5 Forwardの `signal` / `reject` 診断をPromotion Gate Markdownにも表示し、トレード0件または途中停止時にHOLD過多、BUY/SELL候補不足、reject理由をGate側だけで確認できるようにする
- MT5 Forwardのrisk exposureがlot上限、合計lot、同時建玉、日次/連敗停止後openで失敗した場合は、`mt5_forward_risk` のnext actionでcompile確認とForward再実行を指示する
- MT5 Forwardの `diagnostic_warnings` と検出された連敗停止limitをPromotion Gate Markdownにも表示し、警告が1件でも残るForwardは昇格不可にして、古い連敗停止設定やrisk設定の混入を修正/再実行するnext actionへ戻す。このnext actionには再実行前の `mt5_compile.py` 計画も含める。検出された連敗limitが20未満の場合は `Swing_Evaluation_Trader_forward_test.set` のrisk preset確認planも含め、Markdownに検出limit、現在値、エラー、`InpConsecutiveLossLimit >= 20`、`InpConsecutiveLossCooldownMinutes >= 120`、`InpRequireStrategyTester = true`、`InpChartButtonDryRunOnly = true`、`InpAllowChartButtonTrading = false` を明示する
- MT5 Forwardの `csv_schema` をPromotion Gateのcheckにし、entry-time/trend診断が使えない古いCSVでは `mt5_forward_schema` のnext actionで現行EAのcompile確認とForward再実行を指示する
- MT5 Forwardの `SL/TP Diagnostics` をPromotion Gateのcheckにし、`by_stop_points`、`by_take_profit_points`、`by_risk_reward_stop_points`、`by_risk_reward_take_profit_points`、`weak_sl_tp_segments` が欠ける古いForwardレポートでは `mt5_forward_sl_tp_diagnostics` をFAILにする。`By Risk Reward And TP Points` がない場合はRR×TP帯の崩れを判断できないため、`mt5_forward_collect.py` で最新CSVから再集計するnext actionへ戻す
- MT5 Forwardの `side_score_diagnostics` を確認し、`score_inversion` が出たsideは評価関数の再fit対象として昇格不可にし、next actionでside別score関数の再fitを指示する
- MT5 Optimizationの `Chronological Split Diagnostics` を確認し、後半/quarterでPF < 1.0または平均R < 0のsplitがあれば昇格不可にする
- 短期Optimizationとは別に、年次/out-of-year Optimizationレポートを `mt5_yearly_optimization` として確認できる。必須化した場合は年次PF、平均R、positive forward/back pass、年次chronological splitを昇格条件にする
- `Backtest Vs Forward Drift` でbacktestを基準にPython forward、MT5 forward、MT5 Optimization、Yearly OptimizationのPF、平均R/価格R、期待R、最大DDの差分を表示し、実運用ログやTester結果がバックテストからどれだけ劣化しているかを評価できる。`latest_mt5_back_forward_run.json` がある場合は `MT5 Back/Forward Runner Drift` を別枠で表示し、MT5上で手動実行したbacktest/forwardのclosed、PF、平均R、期待R、価格R DD、損益差分もPromotion Gate本文から確認できる。dry-runの `plan_only` は昇格証跡としてFAILにし、Runner復旧planは直近dry-runの `run_id_prefix`、timeout、since、min closed、期間/ForwardMode上書き、ready status最大鮮度を実行コマンドへ引き継ぎ、Markdownの `mt5_back_forward_conditions` に表示する
- backtest / Python forward / MT5 forward / MT5 optimization / yearly optimizationの最大DDと期待Rを表示し、`--max-*-drawdown-*` や `--min-*-expectancy-*` が指定された場合は昇格条件として判定する
- DD/期待Rゲートが失敗した場合は `risk_shape` のnext actionを出し、DD集中の低減または期待R再fitへ戻す。このnext actionには `risk_shape_backtest_168h_min40.xlsx` と `risk_shape_weight_search_168h_both_rr4.xlsx` を出す専用backtest/weight_search計画を含める。weight_searchはwalk-forward付きで実行し、train内で良く見えるだけのDD/期待R改善を採用候補にしない。`--risk-shape-weight-search-report` が存在する場合は上位候補、baseline差分、walk-forward結果を実行計画直下に表示する。実行計画直下には `risk_shape_gap` も表示し、backtest / Python forward / MT5 forward / MT5 optimization / yearly optimization別に最大DDと期待Rの未達値を確認できるようにする
- `spec_coverage.py` は `runtime/latest_winrate_fit.json` と `runtime/latest_risk_shape_weight_search.json` も主要runtime artifactとして監視する。Runtime Artifacts表にはwinrate fitの採用有無、rule、walk-forward fold数、fitted件数、平均PF/平均Rと、risk shape weight searchのwalk-forward aggregate statusを表示し、勝率fitやDD/期待R再fit証跡の欠落・staleを完了監査から漏らさない。欠落またはstaleの場合は `refresh_fit_quality_artifacts` をNext Actionに出し、winrate fit、risk shape backtest診断、risk shape weight_search、Promotion Gate再生成のコマンドを表示する
- `spec_coverage.py` の `promotion_gate_stale_vs_dependencies` は、履歴、compile、Back/Forward、score weight探索/setに加えて `latest_winrate_fit.json` と `latest_risk_shape_weight_search.json` も依存証跡として扱う。fit証跡を更新した後は、古いPromotion Gateではなく再生成したGateで昇格可否を判断する
- 年次/out-of-year Optimizationレポートを読み込んだ場合は、`--require-mt5-yearly-optimization` の有無にかかわらず、そのレポート内のTester forward XML証跡とchronological splitは欠落不可とする。年次PFだけ良く、forward/back安定passや後半splitが欠ける設定は採用しない
- 年次/out-of-yearが落ちたnext actionは、年次検証の再実行planに加えてside別の再fit/診断planを含める。BUYは直近の年次失敗分析で残った `Swing_Evaluation_Trader_buy_hour03_wide_stop_calendar_validation.set` の432 pass診断へ進み、SELLは `Swing_Evaluation_Trader_sell_regime_entry_refit.set` でentry品質とtrend/time regimeを再fitする。失敗したchronological splitはevidenceに残す
- MT5単体EA/Indicatorの配置済み `.ex5` が最新ソースからCompile済みかを任意で必須条件にできる
- dry-run commandに埋め込まれた `risk_gate.allowed` を確認し、建玉/lot/日次損失/連敗停止でブロックされたdry-runを昇格根拠にしない
- dry-runのrisk gate証跡が欠落している場合と、risk gateが明示的にブロックした場合をnext actionで分ける
- dry-runは `ea_dry_run_passed` だけでなく、鮮度とsignal/command整合性も要求する
- 最新signalがHOLDでcommandがEA送信前に正しく `rejected` された場合、dry-run鮮度/整合/risk gateはPASSできるが `dry_run_passed` はFAILのままにする。この場合のnext actionは再refreshではなく、BUY/SELLのtradable signalを待ってからEA dry-runを実行することにする。Promotion Gate Markdownの実行計画には `dry_run_wait` を表示し、outcome、signal action、command status、signal/command整合理由、risk gate許可状態、失敗check名を確認できるようにする。鮮度で落ちている場合は `dry_run_freshness` にcommand/resultの経過秒数、許容秒数、fresh判定を表示し、HOLD待ち中でも古いdry-run証跡の程度を確認できるようにする。HOLD待ちで通常refreshを抑制する場合でも、`lot_policy` などdry-run command安全証跡の欠落は `dry_run_command_safety` として同じ実行計画に表示する
- MT5系next actionには、次に実行する `mt5_tester_run.py` のconfig、set、report名、出力先、コマンドをevidenceとして含める。MT5 Testerを起動する実行計画には、事前確認用の `mt5_compile.py` plan も `compile` evidenceとして含める。`execution` / `follow_up_execution` / `refit_execution` / `validation_execution` がAgent CSV退避付きMT5実行であれば、同じ `agent_csv_archive_run_id` の `archive_preview` / `follow_up_archive_preview` / `refit_archive_preview` / `validation_archive_preview` も含め、previewは `--include-source-time` 付きで残存CSVのclose `server_time` 範囲を確認する。自動生成previewの出力はrun-id別ファイルにして、BUY/SELLや年次計画のpreview証跡を上書きしない。Promotion Gate Markdownのplan行にも `include_source_time=True` を表示し、フラグ付きpreviewかどうかをコマンド本文以外からも確認できるようにする
- 時系列split失敗で年次検証へ戻すMT5 next actionでは、Promotion Gate Markdownに `chronological_failure` を表示し、崩れたsplitのPF、平均R、期間、診断文を実行計画の近くで確認できるようにする。forward-only上位passを避けてstable pass周辺へ絞るnext actionでは、`forward_only_top` と `stable_pass_hint` を表示し、除外すべきforward-only passと次に制約するstable pass候補を同じ場所で確認できるようにする
- stable candidateをMT5 Strategy Testerで検証済みの場合は、Promotion Gate Markdownの `mt5_optimization_recommendation` 実行計画に `stable_candidate_result`、`stable_candidate_chronological_failure`、`stable_candidate_weak_time`、`stable_candidate_weak_trend`、`stable_candidate_weak_sl_tp` を表示し、探索用setが採用不可のままなのか、どのsplit/時間帯/trend/SLTP帯で崩れているのかを実行計画の近くで確認できるようにする。弱いtrend/timeが主因なら `stable_candidate_refit` としてside別のregime/entry refit Tester計画を出し、SL/TPだけが主因ならentry/SLTP再fit計画を出す。同じstable candidate探索setを繰り返す前に、崩れた条件の再fitへ進める。SELL refitの推薦ファイル、特に `latest_mt5_sell_regime_entry_refit_recommendation.json` がすでに完了済みで `score_refit_required` / `diagnostic_only` の場合は、同じ `sell_regime_entry_refit` を再度MT5へ投げず、`stable_candidate_refit_completed` を表示して `sell_score_refit` のscore weight探索/評価関数再fitへ進める。短期Optimizationのchronological rejectionがすでにRecommendation不採用理由として確定し、完了済みSELL refitからscore sample収集へ進む場合は、`reject_chronologically_unstable_optimization` を別P1 actionとして残さず、`sell_score_refit` の `upstream_chronological_rejection` に失敗split、弱い時間帯、trend、SL/TP帯を統合する
- `mt5_next_action_run.py` はPromotion Gate JSONからMT5実行計画を選び、既定ではdry-runでconfig/set/output set/archive preview/primary commandを `runtime/latest_mt5_next_action_run.json` / `.md` に書き出す。Forward系のarea targetでは `follow_up_execution` や収集コマンドをprimaryとして誤選択せず、Strategy Tester本体の `execution` をprimary、`mt5_forward_collect.py` をfollow-upとして分けて表示する。実際にMT5を起動する時だけ `--execute` を要求し、shell文字列ではなくJSON内のcommand配列を実行する。`--run-archive-preview` 付きdry-runでは、MT5 primaryを起動せずAgent CSV退避previewだけを実行し、手動Strategy Tester前にsource timeとpreview validationを確認できるようにする。`--execute` は既定でprimaryが `analysis/mt5_tester_run.py` の場合だけ許可し、Gateが `mt5_optimization_recommend.py` などのローカルrefreshへ戻している場合は `non_tester_primary` で起動前ブロックする。MT5 Tester primaryの実行時は `latest_mt5_tester_status.json` の `next_action_execution.ready=true`、同じtarget/config/command、primary/archive preview/follow-upの予定出力先、ready status鮮度、選択中runnerより高優先度のGate action、または同じ優先度で選択中runnerより前に並ぶGate actionが残っていないことを必須にし、古いstatus、別targetのdry-run、出力先がずれたrunner、または未処理の推薦refreshやchronological rejectionを飛ばしてMT5を起動しない。`Swing_Evaluation_Trader` はBridge非依存の単体EAなので、`latest_bridge_recovery_plan.json` が未readyでも既定ではMT5 Tester primaryを止めない。Bridge readyも必須にしたい診断時だけ `--require-bridge-ready` を付け、その場合は `bridge_recovery_not_ready` で停止し、MT5起動ヒントと手動Strategy Tester checklistをRunner Markdownから隠す。通常の実行コマンドには `--refresh-ready-status` を付け、MT5起動直前に `latest_mt5_tester_status.json` / `.md` を再生成してからpreflightを判定する。診断目的で外す場合だけ `--skip-ready-status-check` を要求する。ローカルrefreshを意図的に実行する時だけ `--allow-non-tester-primary` を要求する。`mt5_optimization_recommend.py` は推薦JSONを正常生成しても `adoptable=false` なら終了コード2を返すため、runnerは予定 `--output-json` の推薦artifactが `ok=true` でdecisionを含む場合に限り、`accepted_returncode=true` / `recommendation_refresh_completed_not_adoptable` として処理完了扱いにする。Agent CSV退避previewはprimary起動前の必須ガードとして扱い、preview commandのreturncode、予定 `--output-json` の存在、JSON内の `ok=true`、`execute=false` を確認する。preview commandが失敗した場合は古いpreview artifactが残っていても `archive_preview_command_failed` を検証理由に含める。失敗または出力欠落なら `archive_preview_failed` / `archive_preview_artifact_not_ok` でMT5 Tester primaryを起動しない。follow-up側にも `follow_up_archive_preview` がある場合は同じ検証を行い、不備があればfollow-up収集を起動しない。既定targetは `first_mt5` とし、特定計画を診断するときだけ `--target stable_candidate_refit` などを明示する。compile planは明示的に `--run-compile` を付けた時だけ実行する。primary成功後にfollow-up収集まで続ける場合だけ `--run-follow-up` を要求する。dry-run時点でarchive preview、primary、follow-up commandの `--output-json`、`--optimization-output-json`、`--recommendation-output-json` を `planned_outputs` として保持し、status/heartbeatにも転記する。実行後は同じ出力先を読み、runner JSON/Markdownの `post_execution_artifacts` に証跡種別、Agent CSV previewの `ok/execute/count/source_time`、Tester runの `ok/blocked/source_time_blocked/report_fallback_blocked/elapsed`、Optimizationのclosed/PF/XML rows、Recommendationの採用可否と次setを要約する。`score_weight_sample_collection` は `evidence_role=diagnostic_sample_collection`、`diagnostic_only=true`、`promotion_evidence=false` を付け、score再fit用サンプルを昇格判定用成績として扱わない。MT5 Tester primaryの成功判定はsubprocess returncodeだけにせず、予定 `output_json` の存在、Tester run JSONの `ok=true`、blocked/source-time/fallback/terminal失敗なしを `post_execution_validation` で確認し、不備があれば `blocked_after_primary=primary_tester_artifact_not_ok` としてfollow-upへ進まない。`mt5_forward_collect.py` follow-upの成功判定もreturncodeだけにせず、予定 `output_json` のForward reportが存在し、`ok=false` でなく、`summary.overall.closed` が読めることを確認し、不備があれば `blocked_after_follow_up=follow_up_artifact_not_ok` にする。`mt5_tester_status.py` と `mt5_tester_status_watch.py` は `latest_mt5_next_action_run.json` も読み、target、kind、primary execution class、config、set、output set、archive run ID、dry-run/実行済み、archive preview/primary/follow-up実行結果、予定出力先、実行後artifact要約をstatus/heartbeatへ転記する。さらにrunnerが現在のPromotion Gateと同じ `promotion_generated_at` / `promotion_decision` / selected action / primary内容から作られているかを `promotion_gate_current`、`selected_action_current`、`current_for_execution`、`gate_stale_reason` として表示し、Gate更新後の古いrunnerをMT5へ渡さない。選択中runnerより高優先度のGate action、または同じ優先度で選択中runnerより前に並ぶGate actionが残っている場合は `Blocking prior actions` と `higher_priority_actions_pending` を出し、各先行Actionの `runner_execute_hint` とprimary `command_text` を表示する。ただしMT5 Tester primaryがBridge readyを要求していない通常運用では、Bridge復旧系の先行Actionだけは `advisory_prior_actions` / `next_action_run_advisory_prior_action_*` に分離し、`blocking_prior_action_count` と `higher_priority_actions_pending` ではMT5 Strategy Tester Back/Forwardを止めない。前段actionがない場合も `blocking_prior_action_count=0` と `advisory_prior_action_count=0` をstatus JSON/heartbeatへ残し、MT5起動前の順序ガードが空であること、またはBridge警告だけが残っていることを確認できるようにする。`runner_execute_hint` はMT5 Tester primaryなら `mt5_next_action_run.py --target ... --execute --refresh-ready-status ...`、ローカルrefresh primaryなら `--allow-non-tester-primary` 付きにし、先行Actionもstatus preflight経由で処理する。`next_action_execution.ready/status/reasons` では、現在terminal、compile鮮度、Promotion Gate/compile/next action runのfresh判定、primaryがMT5 Tester起動かどうか、未処理の高優先度actionまたは同順位の前段action有無をまとめて判定する。status/heartbeatには `mt5_next_action_run.py --target ... --execute --refresh-ready-status ...` のrunner実行ヒントも出す。primaryがローカルrefreshの場合は別枠の `next_action_local_execution.ready/status/reasons` を出し、Promotion Gate、Optimization report、Next Action dry-runのfresh判定と `--allow-non-tester-primary` 必要性を確認できるようにする。stable candidateの崩れからrefitへ進む場合は `stable_candidate_refit` をstatus/heartbeatに転記し、すでに同refitが完了済みで `stable_candidate_refit_completed` がある場合はkind/side/status/PF/平均R/理由/skip reasonも転記する。これによりMT5上でバックテスト/forward testを起動する前後の状態と、MT5起動前に済ませるべきローカル推薦refresh、Bridge復旧は別作業として残しながら単体Strategy Testerを進められる理由、同じstable candidate検証を繰り返さず次段のscore refitへ進む理由を同じ監視ファイルで追える
- runner/status/watchに転記するMT5 primary planには、`timeout_seconds` / `timeout_minutes` / `timeout_note`、runner生成時点またはstatus更新時点から見た `timeout_deadline_if_started_now`、`optimization_mode`、`optimized_input_count`、`estimated_full_factorial_passes`、直近Optimization由来の `latest_executed_tester_xml_rows` も含める。これによりMT5起動前のdry-run単体、起動中の監視、実行後の確認で、最長待機時間、今開始した場合の最大待機期限、理論pass上限、実際にTester XMLへ出たback/forward行数を同じファイルから確認できる。MarkdownではPython dictではなく `back=185, forward=185 (ratio_vs_full_factorial=..., source=...)` のようなcompact表示にする
- `mt5_next_action_run.py` の `Manual Collect Readiness` には、手動Strategy Tester実行後の指定Report HTML/XMLと新しいAgent CSVが揃ったか、ready/status/reason/blocking reasons/next actionを出す。score weight sample collectionなど診断サンプル収集でも、Report待ち、Agent CSV待ち、collect-only実行可をrunner/status/watch/coverageから確認できるようにする
- `latest_mt5_next_action_run.json` はMT上の実行前確認とstatus/watchの機械判定で直接読めるよう、`primary` 配下だけでなくトップレベルにも `kind`、`focus_side`、`optimization_mode`、`config`、`set`、`output_set`、`agent_csv_archive_run_id`、timeout、pass見積もり、直近Tester XML行数、4分類をまとめた `planned_outputs`、primary/archive preview/follow-up planned outputs、`action_context_keys`、`related_execution_keys` を出す。dry-run、`--execute --refresh-ready-status` のpreflight plan、ready status refresh失敗時のブロックレポートでも同じキーを保持する
- `latest_mt5_next_action_run.json` の `generated_at` は後方互換のためPromotion Gate生成時刻として残す。Runner artifact自体の生成時刻は `runner_generated_at`、参照Gateの一致判定は `promotion_generated_at` / `promotion_decision` を使う。CLI短縮出力とstatus/watch/coverageもこの3項目を出し、手動Strategy Tester後の `--csv-modified-after` には `runner_generated_at` を、Gate世代の照合には `promotion_generated_at` を使う
- runner JSON/Markdown自身にも `runner_promotion_generated_at`、`current_promotion_generated_at`、`runner_promotion_decision`、`current_promotion_decision`、`selected_action_current`、`current_for_execution`、`gate_stale_reason` をトップレベルで残す。これにより `mt5_manual_test_queue.py` やstatus/watchがrunnerを開くだけで、MT5へ渡してよい現行runnerか、再生成が必要なstale runnerかを判断できる
- `mt5_next_action_run.py` の既定targetは固定の `stable_candidate_refit` ではなく `first_mt5` とする。無指定または `--target auto` / `--target first_mt5` の場合は、現在のPromotion Gate内で最初に見つかる `analysis/mt5_tester_run.py` primaryを選び、runner JSONの `target` には `score_weight_sample_collection` などの具体ラベルを保存する。これによりGate更新後に存在しない古いtargetでdry-runが失敗し、`latest_mt5_tester_status` が不整合になることを防ぐ。特定計画の診断では従来通り `--target stable_candidate_refit` などを明示する
- `mt5_next_action_run.py --execute --allow-non-tester-primary` でローカルrefreshを実行する場合も、既定では `latest_mt5_tester_status.json` の `next_action_local_execution.ready=true`、同じtarget/command/planned outputs、ready status鮮度を必須にする。`--execute --refresh-ready-status` では、status更新前に選択済みtargetのdry-runを `latest_mt5_next_action_run.json` / `.md` へ書き、status preflightが古いrunnerではなく今選んだrunnerを比較できるようにする。`next_action_local_execution.ready=false` の場合や予定出力先がstatusとrunnerでずれる場合は `ready_status_not_ready` / `ready_status_plan_mismatch` でprimary実行前に止め、古いOptimization report、古いPromotion Gate、または別出力先のrunnerから推薦refreshを作らない。診断目的でこのガードを外す場合だけ `--skip-ready-status-check` を使う
- `next_action_local_execution` はOptimization reportのmtimeだけでなく、latest tester run内の `optimization_summary` との一致も確認する。mtimeがstaleでも、generated_at、closed、PF、平均R、net profit、source-time整合が一致し、latest tester runが `ok=true` かつblocked/source-time/fallbackなしなら `optimization_report_evidence.current=true` として、既存の最新Tester証跡から推薦refreshを実行可能にする。一致しない場合は `required_artifact_stale_or_missing:optimization_report` で止める
- Promotion Gateは `latest_mt5_tester_run.json` の `ok`、`blocked_components`、risk preset要約、`agent_csv_archive_missing`、`agent_csv_archive.ok`、退避済みCSVの `source_time_coverage`、`source_time_blocked`、`terminal_run`、`report_paths`、`report_fallback_blocked` も確認する。`ok=false` なら `mt5_tester_run_ok`、通常起動で退避なし/退避失敗/退避件数があるのにsource_time証跡欠落なら `mt5_tester_run_agent_csv_archive`、runnerが期間不一致で推薦生成を止めた場合は `mt5_tester_run_source_time`、terminalがtimeoutまたは非0終了した場合は `mt5_tester_run_terminal`、通常起動で指定Reportではなくfallback XMLを読んだ場合または `report_fallback_blocked=true` の場合は `mt5_tester_run_report_paths` をFAILにし、同じrun-idでarchive previewと再実行/再集計planを出す。通常起動で `ok=true` なのにrisk preset要約が `InpUseDailyLossStop`、`InpDailyLossLimit`、`InpUseConsecutiveLossStop`、`InpConsecutiveLossLimit`、`InpConsecutiveLossCooldownMinutes`、`InpRequireStrategyTester`、`InpChartButtonDryRunOnly`、`InpAllowChartButtonTrading` を含まない場合は `mt5_tester_run_risk_preset_schema` をFAILにし、現在のrunnerで再実行する。`mt5_tester_run_agent_csv_archive` のarchive previewは `--include-source-time` 付きにして、残存Agent CSVのclose `server_time` 範囲を確認してから再実行する。`mt5_tester_run_ok` のnext actionは、`compile_stale` なら `compile`、`risk_preset_invalid` なら `risk_preset_fix`、`agent_csv_archive_failed` なら `archive_failure` を分けてevidenceに残す
- MT5系next actionには、対象 `.set` のOptimization対象入力数と全組み合わせ換算pass数を含める。`Optimization=2` のgenetic optimizationでは実行pass数がこの理論値より少なく終わることを明示する
- MT5 Optimization未達のfocused `next_optimization` 実行計画直下には `mt5_optimization_gap` と `mt5_optimization_side_gap` を表示し、全体PFとBUY/SELL別のclosed件数、PF、平均Rの不足を同じコマンドの近くで確認できるようにする
- 直近Optimization/年次Optimizationレポートに `optimization_pass_budget.executed_tester_xml_rows` がある場合は、MT5系next actionの実行計画にも `recent_xml_rows` として併記し、理論pass上限と実際にTester XMLへ出たback/forward行数を同じ場所で確認できるようにする。未来の出力先を持つgenetic系refitやvalidation計画には、source付きで直近Optimization行数をfallback表示する。ただし単発のStrategy Forward Testなど `optimization_mode=single` の計画にはOptimization行数を混ぜない
- MT5系next actionには、`timeout_seconds` / `timeout_minutes` とtimeout noteを含める。実際の終了時刻は起動時刻次第なので、Promotion Gate Markdownでは最長待機時間として表示する
- MT5 Forward未達のnext actionには、`Swing_Evaluation_Trader_forward_test.ini` を使う `mt5_tester_run.py --no-recommendation` の実行計画と、続けて `mt5_forward_collect.py` でCSVを `latest_mt5_forward_report` へ集計するfollow-upコマンドを含める。Strategy Tester forward実行計画の直下には `mt5_forward_gap`、`mt5_forward_side_gap`、`mt5_forward_signal_flow`、`mt5_forward_reject_flow`、`mt5_forward_reject_top`、`mt5_forward_risk_exposure`、`mt5_forward_sl_tp`、`mt5_forward_weak_sl_tp`、`mt5_forward_warning`、`mt5_forward_detected_loss_limits`、`mt5_forward_schema_gap`、`mt5_forward_sl_tp_gap` を表示し、PF、最大連敗、side別PF/平均R、signal/reject件数、上位reject理由、risk exposure、SL/TP診断件数と弱いセグメント、古い連敗停止limit、entry-time/trend診断フィールド不足、SL/TP診断キー不足を再実行/再集計前に確認できるようにする。Promotion Gate本文にも `MT5 Forward SL/TP Diagnostics` を表示し、`latest_mt5_forward_report.md` を開かなくてもSL/TP診断キーの有無と弱い帯の概要を確認できるようにする
- Python forward未達のnext actionには、`forward_test_watch.py --max-runs 1` で台帳記録/評価/status更新を1回行う実行計画を含める。`latest_forward_test_status` が `waiting_for_tradable_signal` の場合は、台帳記録を急がせるのではなくBUY/SELLのtradable signal待ちとしてnext actionを出し、Promotion Gate Markdownには `forward_wait` としてoperational status、signal action、recordability、closed/open件数、HOLD理由を表示する。`forward_test_watch_heartbeat.json` がある場合は `forward_watch` として常駐状態、pidファイル書き込み有無、heartbeat鮮度、PID、run index、直近record/evaluate結果も表示し、BUY/SELL待ちが監視停止ではないこと、一回更新で常駐pidを上書きしていないことをGate側で確認できるようにする。`forward_status_watch_heartbeat.json` がある場合は `forward_status_watch` としてstatus-only監視の鮮度、pidファイル書き込み有無、PID、run index、operational status、signal action、closed/open、PFを表示する。dry-run未達またはrisk gate証跡欠落のnext actionには、`dry_run_command.py` と `dry_run_audit.py` の実行計画を含める
- score calibration / score quality未達のnext actionには、低め閾値を含む `backtest.py --min-score 40` の診断レポートと `weight_search.py --walk-forward` のfollow-up実行計画を含める。`weight_search.py` はExcelだけでなく `runtime/latest_score_weight_search.json` も出し、上位重み候補、baseline閾値別成績、探索条件、walk-forward aggregateを機械可読な証跡として残す。Promotion GateはこのJSONを読み、実行計画直下の `weight_search_top`、`weight_search_delta`、`Score Weight Search` セクションに上位候補、baseline比較、walk-forward結果を表示する。walk-forward表示には平均R/PF、countに加えて、候補とbaselineの `total_r`、`delta_total_r`、`min_count`、`missing_test_weight_count`、`folds_with_weight_trades`、`missing_folds_with_weight_trades`、最薄foldを含め、平均値だけで採用判断せず、sample shortage時に何件・何fold足りないかを確認できるようにする。実行計画直下には `score_gap`、`highest_sampled`、`highest_sufficient`、`calibration_recommendation`、`score_quality_gap` を表示し、高scoreサンプル不足、平均R/PF未達、score上昇時の平均R劣化を同じコマンドの近くで確認できるようにする。MT5 Optimization / 年次 / Forwardのside別score診断で `score_inversion` が出た場合は、MT5 Testerのside別再fit実行計画に加え、`score_weight_search` として `weight_search.py --side buy` または `--side sell` のwalk-forward付き計画を出し、`runtime/latest_score_weight_search_168h_<side>_rr4.json` にside別配点探索証跡を残す。既存のside別JSONがある場合は、`side_weight_search_top`、`side_weight_search_delta`、`side_weight_search_walk`、`side_weight_regime_top` をMT5再fit実行計画の近くに表示し、本文の `Side Score Weight Search` セクションにもBUY/SELL別の上位候補、baseline比較、walk-forward結果、レジーム別上位候補を表示する。さらに `score_weight_set` 計画を表示し、walk-forward合格済み候補だけ `score_weight_set.py` でMT5検証用setへ変換する。candidate数不足のnext actionには、`candidate_gap` と `history_check` を表示し、候補数の不足件数と168h履歴条件の成否を実行計画の近くで確認できるようにする。さらに168h履歴再取得要求、`history_status.py` による `history_request.done.json` / M1本数確認、履歴更新後に同じbacktest診断を走らせるfollow-upを含める。`spec_coverage.py` はside別sample collection runnerのGate生成時刻やdecisionが現在のPromotion Gateと一致しない場合、古いBUY/SELL runnerを実行せず、side別 `mt5_next_action_run.py --target score_weight_sample_collection --focus-side ...` の再生成Actionへ戻す
- MT5 compile未達のnext actionには `mt5_compile.py` の実行計画を含める。`chronological_splits` 欠落時は `mt5_tester_optimization_report.py` と `mt5_optimization_recommend.py` の再集計/follow-up計画を含め、時系列split失敗時は2025年などの年次検証 `mt5_tester_run.py --from-date ... --to-date ...` の実行計画を含める。短期Optimization推薦だけが不採用、診断用、または未書き込みの場合は、Agent CSVを再集計せず、既存の `runtime/latest_mt5_optimization_report.json` に対して `mt5_optimization_recommend.py` を実行する `mt5_optimization_recommendation_refresh` を主計画にする。Strategy Test後に再集計すると直近Forward CSVをOptimization証跡として誤読するため、Optimization report自体が欠落、古い、期間不一致、またはschema不足の場合だけ `mt5_tester_optimization_report.py` で再集計する。stable hintがある不採用推薦では、`mt5_stable_candidate_set` 計画で `Swing_Evaluation_Trader_stable_candidate_next.set` を `--allow-non-adoptable-output-set` 付きで生成し、続く `stable_candidate` Tester計画では `Swing_Evaluation_Trader_stable_candidate.ini` と `--sync-expert-parameters-set` を使ってMT5 profile側へsetを同期してから検証する。SELL refit推薦ファイルもPromotion Gate入力に含め、完了済みの `sell_regime_entry_refit` / `sell_entry_refit` が採用不可なら同じMT5 refit実行計画を抑制し、score refitやside別weight searchへ進める。年次/out-of-yearレポートでsource-time、chronological split、time/trend診断、pass budget証跡が欠けている場合は、`mt5_yearly_validation` のnext actionに年次出力先 (`runtime/latest_mt5_2025_optimization_report.json` / `runtime/latest_mt5_2025_recommendation.json`) へ再集計する `collect_refresh` も含め、期待期間 `2025.01.01` から `2025.12.31`、`--drop-source-time-mismatch-files`、`--fail-on-source-time-mismatch`、年次Tester XML `Swing_Evaluation_Trader_next_optimization_2025.xml` / `.forward.xml` を明示する。ただし短期Optimization推薦が不採用または未書き込みの場合は、年次XMLの再集計へ進まず短期の `mt5_optimization_recommendation_refresh` へ戻す。年次/out-of-yearの実行計画直下には `yearly_overall`、`yearly_metric_gap`、`yearly_source_time_file_filter`、`yearly_source_time_dropped`、`yearly_missing_evidence`、`yearly_chronological_failure` を表示し、PF/平均R/positive forward-backの未達、期間外CSV除外、source-timeやchronological splitの欠落、time/trend診断の不足を実行前に確認できるようにする。通常Optimizationの再集計planも、短期Report XML `Swing_Evaluation_Trader_next_optimization.xml` / `.forward.xml` を明示して、既定XML名への誤読を防ぐ。winrate fit未採用時はpurge/embargo付き `winrate_fit.py` の実行計画を含め、実行計画直下に `winrate_adoption` と `winrate_walk_gap` を表示し、採用理由、walk-forward fold数、fitted test件数不足、平均R/PFの閾値差を確認できるようにする
- `--require-mt5-optimization` では `Temporal Diagnostics` と `Trend Regime Diagnostics` の存在を必須にする。古いOptimizationレポートで `by_entry_server_hour` / `by_m5_trend` / `by_m30_slope` / `by_m15_slope` / `weak_time_segments` / `weak_trend_segments` などが欠ける場合は昇格不可にし、再集計next actionを出す。positive forward/back pass不足時は、弱いtime/trend regimeをevidenceに含め、SELLなら `sell_regime_entry_refit`、BUYなら `buy_entry_refit` へ進む実行計画を出す
- `--require-mt5-optimization` と年次/out-of-year検証では `SL/TP Diagnostics` も必須にする。`by_stop_points`、`by_take_profit_points`、`by_risk_reward_stop_points`、`by_risk_reward_take_profit_points`、`best_segments`、`weak_segments` が欠ける古いレポートは、RR×TP帯の崩れを判断できないため `mt5_optimization_sl_tp_diagnostics` / `mt5_yearly_optimization_sl_tp_diagnostics` をFAILにし、Agent CSVから再集計するnext actionへ戻す
- `sell_sl_tp` のnext actionでは、focused `next_optimization` を主実行計画にし、SL/TP帯を絞っても損失が残る場合のfollow-upとして `Swing_Evaluation_Trader_sell_entry_refit` の実行計画を含める。focused `next_optimization` の実行計画直下にはfocus sideで絞った `sl_tp_best` と `sl_tp_weak` を表示し、次に探索範囲を寄せるRR/SL/TP帯と除外候補の崩れた帯をPF、平均R、損益、診断文付きで確認できるようにする。focus sideの帯が欠ける場合は、BUY帯などをSELL候補として誤表示せず、`sl_tp_segment_gap` にside別件数と再実行/再生成が必要なことを表示する
- CLI標準出力は失敗件数と主要next actionのコンパクト要約にする。完全な判定JSONは `runtime/latest_promotion_gate.json`、Markdown要約は `runtime/latest_promotion_gate.md` へ保存し、端末へ全JSONを出す必要がある場合だけ `--print-full-report` を使う。完全JSONのトップレベルにも `check_count`、`failed`、`failed_checks`、`failed_check_names` を保存し、MT5のBack/Forward実行後にどのGate checkで止まっているかを機械的に読めるようにする
- 条件未達なら `live_ready = false` と失格理由を出す
- live commandは生成しない。判定レポートのみ出力する

### MT5表示/実行レイヤー

Python側のAnalyzerとは別に、MT5単体で動くMQL5実装を置く。

```text
mt5/
  Experts/
    Swing_Evaluation_Trader.mq5
  Indicators/
    Swing_Evaluation_Predictor.mq5
  TesterSets/
    Swing_Evaluation_Trader_backtest.set
    Swing_Evaluation_Trader_forward_test.set
    Swing_Evaluation_Trader_sample_collection.set
    Swing_Evaluation_Trader_optimization.set
    Swing_Evaluation_Trader_next_optimization.set
    Swing_Evaluation_Trader_stable_candidate_next.set
    Swing_Evaluation_Trader_buy_refit.set
    Swing_Evaluation_Trader_buy_entry_refit.set
    Swing_Evaluation_Trader_buy_hour03_validation.set
    Swing_Evaluation_Trader_buy_strong_hours_validation.set
    Swing_Evaluation_Trader_buy_strong_hours_m30m15_validation.set
    Swing_Evaluation_Trader_buy_wide_stop_validation.set
    Swing_Evaluation_Trader_buy_hour03_wide_stop_validation.set
    Swing_Evaluation_Trader_buy_hour03_wide_stop_calendar_validation.set
    Swing_Evaluation_Trader_sell_entry_refit.set
    Swing_Evaluation_Trader_sell_regime_entry_refit.set
    Swing_Evaluation_Trader_sell_hour12_validation.set
    Swing_Evaluation_Trader_sell_hour12_m30m15_validation.set
    Swing_Evaluation_Trader_sell_hour12_m30m15_calendar_validation.set
  TesterConfigs/
    Swing_Evaluation_Trader_backtest.ini
    Swing_Evaluation_Trader_forward_test.ini
    Swing_Evaluation_Trader_strategy_test.ini
    Swing_Evaluation_Trader_sample_collection.ini
    Swing_Evaluation_Trader_optimization.ini
    Swing_Evaluation_Trader_next_optimization.ini
    Swing_Evaluation_Trader_stable_candidate.ini
    Swing_Evaluation_Trader_buy_refit.ini
    Swing_Evaluation_Trader_buy_entry_refit.ini
    Swing_Evaluation_Trader_buy_hour03_validation.ini
    Swing_Evaluation_Trader_buy_strong_hours_validation.ini
    Swing_Evaluation_Trader_buy_strong_hours_m30m15_validation.ini
    Swing_Evaluation_Trader_buy_wide_stop_validation.ini
    Swing_Evaluation_Trader_buy_hour03_wide_stop_validation.ini
    Swing_Evaluation_Trader_buy_hour03_wide_stop_calendar_validation.ini
    Swing_Evaluation_Trader_sell_entry_refit.ini
    Swing_Evaluation_Trader_sell_regime_entry_refit.ini
    Swing_Evaluation_Trader_sell_hour12_validation.ini
    Swing_Evaluation_Trader_sell_hour12_m30m15_validation.ini
    Swing_Evaluation_Trader_sell_hour12_m30m15_calendar_validation.ini
```

`Swing_Evaluation_Predictor.mq5`:

- カスタムインジケータとしてチャートに常駐する
- Analyzer/GPT/Bridge/WebRequestを使わず、MT5内の足とEMA/RSI/ATRだけで評価する
- 予測パネルに action、score、buy/sell score、理由、RR、SL幅を表示する
- scoreが採用条件を満たした時だけ `DRY-RUN ENTRY` / `DRY-RUN SL` / `DRY-RUN TP` の水平線を出す
- 発注コードを持たない。`CTrade`、`OrderSend`、trade command生成は行わない
- hold時は既定で古い注文ラインを消し、 stale なラインを見て入る事故を避ける

`Swing_Evaluation_Trader.mq5`:

- Strategy Tester/Forward Test用のEA
- 初期状態はsignal-onlyで、明示的に3つのliveフラグを切り替えるまで発注しない
- `InpEnableBuy` / `InpEnableSell` でBUY/SELLを片側ずつ検証できる
- 基本確認は自動売買ロジックをStrategy Tester/Forward Testで回す
- チャートEntryボタンは補助機能として任意表示できる。既定では非表示で、表示した場合もdry-runログだけで発注しない
- ボタン発注にはliveフラグに加えて `InpAllowChartButtonTrading = true` を要求する
- Forward Test CSVを出力し、`mt5_forward_report.py` でPF、平均R、滑り、約定遅延、保有時間を評価する
- Backtest用 `.set` とForward Test用 `.set` を分け、MT5のInputs画面でもForwardなし/Forward 1/4の目的を取り違えないようにする
- Forward Test用 `.set` ではsignal診断行を出し、トレード0件でもHOLD理由、BUY/SELL候補数、reject理由を追えるようにする
- `sample_collection.set` は評価関数のサンプル収集専用。`InpUseDailyLossStop=false`、`InpUseConsecutiveLossStop=false` とし、連敗で早期終了させない。デモForward判定や実運用寄りの安全確認には使わない

`mt5/TesterConfigs/*.ini`:

- MT5の `/config` 起動でStrategy Testerを自動実行するための設定
- `Swing_Evaluation_Trader_backtest.ini` はForwardなしの単発バックテスト用
- `Swing_Evaluation_Trader_forward_test.ini` はForward 1/4の単発検証用
- `Swing_Evaluation_Trader_strategy_test.ini` は従来互換のForward 1/4単発テスト用
- `Swing_Evaluation_Trader_sample_collection.ini` はsample collection用
- `Swing_Evaluation_Trader_optimization.ini` はgenetic optimization用
- `Swing_Evaluation_Trader_next_optimization.ini` は推薦結果から生成したfocused optimization用
- `Swing_Evaluation_Trader_stable_candidate.ini` は不採用推薦のstable pass周辺を別名setで追加検証する探索用。採用済みsetとは扱わない
- `Swing_Evaluation_Trader_buy_refit.ini` はBUY側がpromotionで未達になった時のBUY only refit optimization用
  - 初回は `SwingDepth * SwingAtrBand * MinScore * BuyRiskReward * BuyBreakFilter = 288` 通り相当に絞る
  - RSI上下限とSL幅は固定し、BUY方向判定とRRの相性を先に検証する
  - 初回でPF/Forwardが残る範囲が出たら、次段でRSI帯またはSL/TP帯を追加探索する
- `Swing_Evaluation_Trader_buy_entry_refit.ini` は初回BUY refitが崩れた後のentry品質再fit用
  - `InpUseFittedBuyEntryFilter=true` 固定で、BUYだけを対象に `InpBuyRequireBreakConfirm`、`InpBuyMinM1ClosePosition`、`InpBuyMinM1BodyAtr`、`InpBuyMinM5CloseSlowAtr` を探索する
  - 全探索上限は864通り。SELL entry refitと対称に、BUYの反発確認が悪いのか、上位方向評価が悪いのかを分けて検証する
- `Swing_Evaluation_Trader_buy_hour03_validation.ini` はBUY entry refit後に強かった03:00-04:00サーバー時間だけを切り出す診断用
  - `InpUseBuyAllowedServerHours=true`、`InpBuyAllowedServerHours=3` 固定
  - 時間帯集計だけでは採用せず、専用setでback/forwardと年次検証を通す
- `Swing_Evaluation_Trader_buy_strong_hours_validation.ini` はhour03単独でサンプルが薄い時に、03/05/06/10時台へ広げる診断用
  - `InpUseBuyAllowedServerHours=true`、`InpBuyAllowedServerHours=3,5,6,10` 固定
  - 取引数を増やした状態で、BUY時間帯edgeがforward/backでも残るかを確認する
- `Swing_Evaluation_Trader_buy_strong_hours_m30m15_validation.ini` はBUY強時間帯に加えてM30/M15 upを必須にする診断用
  - `InpUseBuyM30M15UpGate=true` 固定
  - BUYが下落/混合レジームを拾って崩れるかどうかを切り分ける
- `Swing_Evaluation_Trader_buy_wide_stop_validation.ini` はBUY強時間帯/M30-M15 upでも年次で崩れた後のSL幅診断用
  - `InpMinStopPoints=300`、`InpMaxStopPoints=350` 固定
  - 年次で唯一残った広めSL帯がback/forwardでも残るかを確認する
- `Swing_Evaluation_Trader_buy_hour03_wide_stop_validation.ini` はwide-stop短期診断で残ったentry 03:00-04:00だけを切り出す診断用
  - `InpUseBuyAllowedServerHours=true`、`InpBuyAllowedServerHours=3` 固定
  - `InpUseBuyM30M15UpGate=true`、SL 300-350ptも固定し、entry hour splitでforward/backが残るかを確認する
- `Swing_Evaluation_Trader_buy_hour03_wide_stop_calendar_validation.ini` はhour03/wide-stop年次診断で残った弱い月/曜日をcalendar filterで切り分ける診断用
  - `InpUseBuyAllowedServerHours=true`、`InpBuyAllowedServerHours=3`、`InpUseBuyM30M15UpGate=true` 固定
  - `InpUseFittedBuyCalendarFilter` のON/OFFを探索し、`InpBuyBlockedMonths=6,8,10`、`InpBuyBlockedWeekdays=3,5` を減点候補にする
  - 全探索上限は432通り。年次PF >= 1.2、平均R > 0、positive forward/back passが出るまで採用しない
- `Swing_Evaluation_Trader_buy_score_weight_refit.ini` は `score_weight_set.py` が生成したBUY評価関数候補setをMT5で検証する用
- `Swing_Evaluation_Trader_sell_entry_refit.ini` はSELL entry品質の再fit用
- `Swing_Evaluation_Trader_sell_regime_entry_refit.ini` はSELL entry品質とtrend/time regimeの複合refit用
- `Swing_Evaluation_Trader_sell_score_weight_refit.ini` は `score_weight_set.py` が生成したSELL評価関数候補setをMT5で検証する用
- `Swing_Evaluation_Trader_sell_hour12_validation.ini` は12時台SELLだけの切り出し検証用
- `Swing_Evaluation_Trader_sell_hour12_m30m15_validation.ini` は12時台SELLかつM30/M15 down固定の次段階検証用
- `Swing_Evaluation_Trader_sell_hour12_m30m15_calendar_validation.ini` は12時台/M30-M15 downに加えて弱い月/曜日を減点する次段階検証用
- 初期条件は `XAUUSD-m`, `M1`, real ticks, Forward 1/4, `2026.06.30` から `2026.07.08`
- `ExpertParameters` は `MQL5/Profiles/Tester` に配置した `.set` を参照する

出力ファイル例:

```text
reports/signal_score_backtest_YYYYMMDD.xlsx
reports/signal_score_backtest_YYYYMMDD.csv
reports/signal_score_summary_YYYYMMDD.md
reports/swing_points_YYYYMMDD.xlsx
reports/swing_points_YYYYMMDD.csv
```

## CLI仕様

山/谷一覧出力:

```bash
python3 analysis/swing_points.py \
  --history runtime/latest_history_168h.json \
  --timeframes M1,M5 \
  --min-atr-distance 0.5 \
  --output reports/swing_points_168h.xlsx
```

出力には、実際の山/谷の中央足時刻 `swing_time` と、右側確認本数が経過してリアル運用で確定する `confirmed_time` を分けて保存する。M1は既定で左右3本、M5は既定で左右2本を使う。

初期CLI:

```bash
python3 analysis/backtest.py \
  --history runtime/latest_history_24h.json \
  --deals runtime/latest_deal_history.json \
  --rr 5 \
  --min-score 70 \
  --max-hold-minutes 60 \
  --calendar runtime/economic_calendar.json \
  --output reports/signal_score_backtest.xlsx \
  --deal-context-output reports/signal_score_backtest_deal_context.xlsx
```

168h取得後:

```bash
python3 analysis/backtest.py \
  --history runtime/latest_history_168h.json \
  --rr 5 \
  --min-score 70 \
  --max-hold-minutes 60 \
  --output reports/signal_score_backtest_168h.xlsx
```

Markdownサマリー:

```bash
python3 analysis/backtest.py \
  --history runtime/latest_history_168h.json \
  --rr 5 \
  --min-score 50 \
  --max-hold-minutes 60 \
  --output reports/signal_score_summary_168h_min50.md
```

決済周辺M1足:

```bash
python3 analysis/deal_context.py \
  --history runtime/latest_history_168h.json \
  --deal-history runtime/latest_deal_history.json \
  --symbol XAUUSD-m \
  --entry out \
  --before-minutes 10 \
  --after-minutes 10 \
  --output reports/deal_m1_context.xlsx
```

履歴取得ステータス:

```bash
python3 analysis/history_status.py \
  --history runtime/latest_history_168h.json \
  --done runtime/history_request.done.json \
  --output-json runtime/latest_history_status.json \
  --output-md runtime/latest_history_status.md
```

`latest_history_168h.json` のtop-level `bars` はコンパクトなプレビューで、分析本体は `timeframes.M1.bars` を使う。168hなら目安はM1 10080本、M5 2016本、M15 672本、M30 336本。

RR比較:

```bash
python3 analysis/rr_experiment.py \
  --history runtime/latest_history_168h.json \
  --rr-values 2,3,4,5 \
  --min-score 50 \
  --side sell \
  --max-hold-minutes 60 \
  --calendar runtime/economic_calendar.json \
  --output reports/rr_strategy_experiment_168h_sell_min50.xlsx
```

score重み探索:

```bash
python3 analysis/weight_search.py \
  --history runtime/latest_history_168h.json \
  --rr 5 \
  --side sell \
  --min-count 30 \
  --calendar runtime/economic_calendar.json \
  --output reports/score_weight_search_168h_sell.xlsx
```

勝率fit:

```bash
python3 analysis/winrate_fit.py \
  --history runtime/latest_history_168h.json \
  --rr 4 \
  --side buy \
  --min-score 50 \
  --validation-folds 3 \
  --wf-folds 4 \
  --purge-records 1 \
  --embargo-records 1 \
  --embargo-minutes 60 \
  --min-test-count 5 \
  --min-test-avg-r 0 \
  --min-test-pf 1.0 \
  --calendar runtime/economic_calendar.json \
  --output reports/winrate_fit_168h_buy_rr4.xlsx \
  --output-json runtime/latest_winrate_fit.json
```

手動確認シグナル生成:

```bash
python3 analysis/signal.py \
  --history runtime/latest_history_168h.json \
  --snapshot runtime/latest_snapshot.json \
  --strategy side_ladder \
  --min-score 50 \
  --max-candidate-age-minutes 30 \
  --calendar runtime/economic_calendar.json \
  --calendar-input-utc-offset 9 \
  --calendar-server-utc-offset 3 \
  --news-before-minutes 10 \
  --news-after-minutes 10 \
  --news-min-impact high \
  --news-currencies USD,XAU,ALL \
  --output runtime/latest_signal.json
```

EA dry-run command生成:

```bash
python3 analysis/dry_run_command.py \
  --signal runtime/latest_signal.json \
  --output runtime/trade_command.json \
  --volume 0.1 \
  --expires-in-seconds 30 \
  --account runtime/latest_account.json \
  --deal-history runtime/latest_deal_history.json \
  --calendar runtime/economic_calendar.json \
  --calendar-input-utc-offset 9 \
  --calendar-server-utc-offset 3 \
  --max-open-positions 3 \
  --max-total-volume 0.3 \
  --daily-loss-limit 5000 \
  --consecutive-loss-limit 20 \
  --consecutive-loss-cooldown-minutes 120
```

SL幅からロット妥当性を確認する場合:

```bash
python3 analysis/dry_run_command.py \
  --signal runtime/latest_signal.json \
  --output runtime/trade_command.json \
  --risk-percent 0.5 \
  --min-volume 0.1 \
  --max-volume 0.1 \
  --max-total-volume 0.3 \
  --account runtime/latest_account.json \
  --deal-history runtime/latest_deal_history.json
```

dry-run監査:

```bash
python3 analysis/dry_run_audit.py \
  --signal runtime/latest_signal.json \
  --command runtime/trade_command.json \
  --trade-result runtime/latest_trade_result.json \
  --max-age-seconds 3600 \
  --output-json runtime/latest_dry_run_audit.json \
  --output-md runtime/latest_dry_run_audit.md
```

フォワードテスト記録:

```bash
python3 analysis/forward_test.py record \
  --signal runtime/latest_signal.json \
  --ledger runtime/forward_tests.jsonl
```

フォワードテスト稼働状況:

```bash
python3 analysis/forward_test.py status \
  --signal runtime/latest_signal.json \
  --ledger runtime/forward_tests.jsonl \
  --output-json runtime/latest_forward_test_status.json \
  --output-md runtime/latest_forward_test_status.md
```

フォワードテスト稼働状況の定期更新:

```bash
python3 analysis/forward_status_watch.py \
  --signal runtime/latest_signal.json \
  --ledger runtime/forward_tests.jsonl \
  --output-json runtime/latest_forward_test_status.json \
  --output-md runtime/latest_forward_test_status.md \
  --interval-seconds 60
```

フォワードテスト記録・評価・稼働状況の定期更新:

```bash
python3 analysis/forward_test_watch.py \
  --signal runtime/latest_signal.json \
  --ledger runtime/forward_tests.jsonl \
  --history runtime/latest_history_168h.json \
  --summary-json runtime/latest_forward_test.json \
  --summary-md runtime/latest_forward_test.md \
  --status-json runtime/latest_forward_test_status.json \
  --status-md runtime/latest_forward_test_status.md \
  --heartbeat runtime/forward_test_watch_heartbeat.json \
  --interval-seconds 60
```

フォワードテスト評価:

```bash
python3 analysis/forward_test.py evaluate \
  --ledger runtime/forward_tests.jsonl \
  --history runtime/latest_history_168h.json \
  --max-hold-minutes 60 \
  --summary-json runtime/latest_forward_test.json \
  --summary-md runtime/latest_forward_test.md
```

MT5単体EAのForward Test CSV集計:

```bash
python3 analysis/mt5_forward_report.py \
  --input runtime/mt5_forward/swing_evaluation_trades.csv \
  --min-closed 30 \
  --min-pf 1.2 \
  --max-losing-streak 20 \
  --output-json runtime/latest_mt5_forward_report.json \
  --output-md runtime/latest_mt5_forward_report.md
```

`mt5_forward_report.py` の標準出力は、監視やGate連携で扱えるように `closed`、`pf`、`avg_price_r`、警告数、失敗check名、出力先だけを含む小さいJSONにする。詳細な集計本体は必ず `--output-json` / `--output-md` に保存し、必要時のみ `--print-full-summary` で全summaryをstdoutへ出す。

MT5 Strategy Tester後の最新CSV収集と集計:

MT5配置/コンパイル状態の確認:

```bash
python3 analysis/mt5_compile_status.py \
  --output-json runtime/latest_mt5_compile_status.json \
  --output-md runtime/latest_mt5_compile_status.md
```

`all_sources_synced=false` はMT5側への `.mq5` 配置漏れ、`all_compiled_fresh=false` はMetaEditorでのCompile漏れ、`all_tester_sets_synced=false` はMT5側 `MQL5/Profiles/Tester` の `.set` 配置漏れまたは古い配置、`all_tester_configs_synced=false` はMT5側 `MQL5/Profiles/Tester` の `.ini` 配置漏れまたは古い配置として扱う。`all_required_tester_config_references_ready=false` は、`.ini` 自体は同期済みでも、その `ExpertParameters` が参照する必須 `.set` が欠落または未同期であることを示す。score-weight refit用 `.set` の生成待ちは `generated_set_missing` として表示し、この必須参照ready判定では許容する。`Swing_Evaluation_Trader.mq5`、`Swing_Evaluation_Predictor.mq5`、`mt5/TesterSets/*.set`、または `mt5/TesterConfigs/*.ini` を編集した後は、Strategy Tester/Forward Test前にこの確認を行う。

MetaEditor起動を含めたCompile確認:

```bash
python3 analysis/mt5_compile.py \
  --output-json runtime/latest_mt5_compile_run.json \
  --output-md runtime/latest_mt5_compile_run.md
```

このコマンドも最終判定は `.ex5` の鮮度で行う。MetaEditorが終了コード0を返しても `.ex5` が更新されていなければ失敗として扱う。

```bash
python3 analysis/mt5_forward_collect.py \
  --destination runtime/mt5_forward/swing_evaluation_trades.csv \
  --output-json runtime/latest_mt5_forward_report.json \
  --output-md runtime/latest_mt5_forward_report.md \
  --collect-status-json runtime/latest_mt5_forward_collect.json \
  --min-closed 30 \
  --min-pf 1.2 \
  --max-losing-streak 20
```

テスターで少数しか約定しない時は、まず `reject.top_messages` / Markdownのreject診断を見る。`consecutive loss cooldown active 20 >= 20` なら、20連敗で `InpUseConsecutiveLossStop` が発動し、120分だけ新規エントリーを止めている。これはドライランではなく安全停止。評価関数の候補数を集める時だけ `Swing_Evaluation_Trader_sample_collection.set` を使い、Forward判定は安全停止ありの `Swing_Evaluation_Trader_forward_test.set` で行う。

Strategy Tester結果の評価では、`By SL Points`、`By TP Points`、`By Risk Reward And SL Points`、`By Risk Reward And TP Points`、`Weak SL/TP Segments`、`Score Thresholds`、`Side Score Diagnostics` を必ず見る。`Weak SL/TP Segments` では、どのSL/TP設定ラインでPFが崩れているか、TP到達率が低すぎるか、SL/早期損失が支配的かを確認する。`candidate_gate` は一時的な採用候補、`score_inversion` は高scoreほど悪化しているため、そのsideの評価関数を別fitする対象とする。

MT5 Tester Optimizationでは、短期窓で良かった設定でも年次検証で崩れることがある。`Temporal Diagnostics`、`Best Time Segments`、`Weak Time Segments` を必ず確認し、四半期/月/曜日/サーバー時間/RR×月のどこでPFと平均価格Rが崩れるかを見る。年次検証で `Weak Time Segments` が支配的で、positive forward/back passが0なら、その設定は採用せず、時間レジーム別の再fit対象に戻す。

EAのCSVには `m30_trend`, `m15_trend`, `m5_trend`, `m30_slope`, `m15_slope`, `trend_alignment` を出力する。Optimization/Forward集計では、M30/M15の向き、トレンド整合、売買方向×トレンド整合でPFと平均価格Rを比較する。これにより「上昇トレンド中の売り」「下落トレンド中の買い」など、方向評価のずれを検出し、BUY/SELL評価関数を別fitする材料にする。EA CSVには `opened_at` と `entry_server_hour` も出力し、エントリー時間帯の検証は決済時刻ベースの `by_server_hour` ではなく `by_entry_server_hour` を優先する。

SELLで `M30 down M15 up` や `m30_m15_up` などの弱いトレンドレジームが出た場合は、`InpUseFittedSellTrendFilter` をOptimization対象にして、部分的な上向きレジームを除外した時にPF/平均R/back-forward安定性が改善するか確認する。このフィルタは既定OFFで、採用は必ずStrategy Testerのback/forwardと年次検証を通した後にする。年次診断で `M30 down M15 down` だけが明確に強い場合は、減点ではなく `InpUseSellM30M15DownGate` を使ってSELLをM30/M15両方downへ厳格に絞る診断も行う。

時間帯でPFが大きく崩れる場合は、`InpUseFittedSellTimeFilter` と `InpSellBlockedServerHours` を使って、弱いサーバー時間帯のSELLを減点する候補を検証する。初期値は短期診断で崩れた `1,9,10,13,14,16,20` 時台を対象にするが、これは固定ルールではなくOptimization/年次検証で棄却可能な仮説として扱う。特定時間帯だけを切り出して検証する場合は、減点ではなく `InpUseSellAllowedServerHours` と `InpSellAllowedServerHours` を使う。これは指定サーバー時間外のSELLスコアを0に落とし、その時間帯だけがback/forwardと年次検証で残るかを見るための診断ゲートで、本番採用は単独検証を通った場合だけにする。

時間フィルタやトレンドフィルタを通しても年次でSLヒット過多が残る場合は、SELLのentry trigger自体を別fitする。`InpUseFittedSellEntryFilter` は既定OFFで、`InpSellRequireBreakConfirm`、`InpSellMaxM1ClosePosition`、`InpSellMinM1BodyAtr`、`InpSellMaxM5CloseSlowAtr` をOptimization対象にする。狙いは「直近安値割れ」「M1終値が足の下側」「M1陰線実体がATR比で十分」「M5終値がslow EMAより上に戻りすぎていない」を満たすSELLだけに絞り、planned SL hit too oftenを減らせるか確認すること。

このentry filterは `Swing_Evaluation_Trader_sell_entry_refit.set` で検証する。通常の `next_optimization.set` には混ぜず、SELL only、RR 1:2-1:5、SL 250-350pt、全探索上限864通りに分離する。短期back/forwardでPF、平均R、positive forward/back passが改善しても、2025年などの年次検証に通るまでは本番用の固定ルールにしない。

entry filter単独でpositive forward/back passが出ない場合は、`Swing_Evaluation_Trader_sell_regime_entry_refit.set` でentry品質とtrend/time regimeを同時に検証する。このセットはSELL only、RR 1:3-1:5、SL 250-300pt、`InpUseFittedSellEntryFilter=true` 固定、`InpUseFittedSellTrendFilter` と `InpUseFittedSellTimeFilter` をOptimization対象にする。時間帯の初期仮説はentry refitで弱かった `1,7,9,10,12,13,14,16,19,20` サーバー時台とし、全探索上限は2592通りに抑える。

年次検証で全体PFは崩れるが、特定サーバー時間帯だけPFが残る場合は `Swing_Evaluation_Trader_sell_hour12_validation.set` のような時間帯切り出しセットを使う。このセットは `InpUseSellAllowedServerHours=true`、`InpSellAllowedServerHours=12` で12:00-13:00のSELLだけを残し、RR 1:3-1:5、MinScore、entry条件、trend filterを再探索する。全探索上限は1296通り。時間帯診断でPFが高いだけでは採用せず、その時間帯専用のTester XMLでpositive forward/back passが出て、2025年などの年次CSVでもPF >= 1.2、平均R > 0が維持されることを条件にする。MT5 Tester集計の `by_server_hour` は決済/Deal時刻ベースなので、時間帯切り出しの妥当性は `entry_server_hour` を出力したCSVで再検証する。hour12単独の年次PFが1.2未満だがM30/M15 downサブレジームだけPFが残る場合は、次段階として `Swing_Evaluation_Trader_sell_hour12_m30m15_validation.set` を使い、`InpUseSellM30M15DownGate=true` 固定で再検証する。このセットは648通りに絞り、採用条件は同じく年次PF >= 1.2、平均R > 0、positive forward/back passありとする。

2025年の `Swing_Evaluation_Trader_sell_hour12_m30m15_validation.set` 検証では、SELL単体の数値基準は初めて通過した。結果は closed 39,315、PF 1.3786、平均R 0.2914、positive forward/back pass 30、positive forward/negative back pass 0。RR別では1:5がPF 1.4782で最も強く、1:4もPF 1.3792、1:3もPF 1.2909だった。ただしこの結果はSELL-only診断であり、BUY側が欠落しているためシステム全体の昇格条件は満たさない。さらに12月、3月、6月、水曜日が弱く、カレンダーレジームの分割または追加フィルタと、2026年/out-of-year forward検証を通すまではデモ/ライブ用ルールにしない。`Swing_Evaluation_Trader_sell_hour12_m30m15_calendar_validation.set` では `InpUseFittedSellCalendarFilter` のON/OFFをOptimization対象にし、弱月 `InpSellBlockedMonths=3,6,12`、弱曜日 `InpSellBlockedWeekdays=3` を検証した。曜日はMT5 `MqlDateTime.day_of_week` 基準で、日曜0、水曜3。結果はclosed 36,115、PF 1.3667、平均R 0.2834、positive forward/back pass 68、positive forward/negative back pass 0。stable passは増えたが、年間aggregateは非calendar版より低下し、3月/6月/水曜の弱さも残ったため、このフィルタは診断止まりとする。

MT5 TesterのOptimizationを使った場合は、ローカルAgentごとにCSVが分かれるため、最新1ファイルだけで判断しない。以下で直近Agent CSVを統合集計し、Tester XMLのback/forward上位パスも同時に確認する。

```bash
python3 analysis/mt5_tester_optimization_report.py \
  --since-minutes 30 \
  --min-closed 100 \
  --weak-pf 1.0 \
  --set-file mt5/TesterSets/Swing_Evaluation_Trader_next_optimization.set \
  --output-json runtime/latest_mt5_optimization_report.json \
  --output-md runtime/latest_mt5_optimization_report.md
```

Tester実行後に別setを回した可能性がある場合は、latest tester runの `terminal_run.finished_at` を `--modified-before "YYYY.MM.DD HH:MM"` として付け、後から上書きされたAgent CSVを除外する。Promotion Gateが出す短期Optimization再集計planでは、この値をlatest tester runから自動付与する。

次の探索範囲の整理:

```bash
python3 analysis/mt5_optimization_recommend.py \
  --input runtime/latest_mt5_optimization_report.json \
  --min-segment-closed 500 \
  --min-segment-pf 1.2 \
  --output-json runtime/latest_mt5_optimization_recommendation.json \
  --output-md runtime/latest_mt5_optimization_recommendation.md \
  --output-set mt5/TesterSets/Swing_Evaluation_Trader_next_optimization.set
```

`score_inversion` が出ているsideを明示的に `--focus-side` へ指定した場合、生成されるsetはscore refit用の診断setになる。この場合、通常の `next_optimization.set` を壊さないため、`--output-set` は既定で書き込みをスキップし、JSON/Markdown出力の `set_metadata.skipped_write=true` に証跡を残す。`mt5_tester_run.py` でOptimization実行から推薦生成までまとめる場合も、子の推薦JSON/Markdownへ同じ `set_metadata` を残す。診断setを別ファイルへ保存したい時だけ、`--output-set runtime/..._diagnostic.set --allow-diagnostic-output-set` を使う。

MT5 TesterのOptimization起動、集計、推薦生成をまとめて行う場合:

```bash
python3 analysis/mt5_tester_run.py \
  --config mt5/TesterConfigs/Swing_Evaluation_Trader_next_optimization.ini \
  --timeout-seconds 7200 \
  --since-minutes 240 \
  --archive-agent-csvs-before-run \
  --agent-csv-archive-run-id before_next_optimization \
  --min-closed 100 \
  --min-segment-closed 500 \
  --min-segment-pf 1.2 \
  --output-json runtime/latest_mt5_tester_run.json \
  --output-md runtime/latest_mt5_tester_run.md
```

BUY側がpromotionで `refit_required` になった場合は、SELL探索とは分けてBUY onlyの再fitを走らせる。
この初回refitはMT5 TesterのOptimization対象を288通り相当に制限し、終了目安を立てられるサイズにしてから実行する。

```bash
python3 analysis/mt5_tester_run.py \
  --config mt5/TesterConfigs/Swing_Evaluation_Trader_buy_refit.ini \
  --report-name Tester\\Swing_Evaluation_Trader_buy_refit \
  --timeout-seconds 7200 \
  --since-minutes 240 \
  --min-closed 100 \
  --min-segment-closed 500 \
  --min-segment-pf 1.2 \
  --output-json runtime/latest_mt5_tester_buy_refit_run.json \
  --output-md runtime/latest_mt5_tester_buy_refit_run.md \
  --optimization-output-json runtime/latest_mt5_buy_refit_optimization_report.json \
  --optimization-output-md runtime/latest_mt5_buy_refit_optimization_report.md \
  --recommendation-output-json runtime/latest_mt5_buy_refit_recommendation.json \
  --recommendation-output-md runtime/latest_mt5_buy_refit_recommendation.md \
  --output-set runtime/Swing_Evaluation_Trader_buy_refit_next.set
```

初回BUY refitでPF/Forwardが残らない場合は、BUYのentry確認だけを再fitする。これは `InpUseFittedBuyEntryFilter=true` 固定で、反発後の高値更新確認、M1終値位置、M1陽線実体、M5 slow EMAからの距離を探索する。上限は864通りで、BUY側の評価関数をSELL側とは分けて検証する。

```bash
python3 analysis/mt5_tester_run.py \
  --config mt5/TesterConfigs/Swing_Evaluation_Trader_buy_entry_refit.ini \
  --report-name Tester\\Swing_Evaluation_Trader_buy_entry_refit \
  --timeout-seconds 7200 \
  --since-minutes 240 \
  --min-closed 100 \
  --min-segment-closed 500 \
  --min-segment-pf 1.2 \
  --focus-side buy \
  --output-json runtime/latest_mt5_tester_buy_entry_refit_run.json \
  --output-md runtime/latest_mt5_tester_buy_entry_refit_run.md \
  --optimization-output-json runtime/latest_mt5_buy_entry_refit_optimization_report.json \
  --optimization-output-md runtime/latest_mt5_buy_entry_refit_optimization_report.md \
  --recommendation-output-json runtime/latest_mt5_buy_entry_refit_recommendation.json \
  --recommendation-output-md runtime/latest_mt5_buy_entry_refit_recommendation.md \
  --template-set mt5/TesterSets/Swing_Evaluation_Trader_buy_entry_refit.set \
  --output-set runtime/Swing_Evaluation_Trader_buy_entry_refit_next.set
```

BUY entry refitでも全体PFが崩れるが、特定サーバー時間だけPFが残る場合は時間帯切り出し診断を行う。今回の短期窓では03:00-04:00 entry hourが最も強かったため、まず `Swing_Evaluation_Trader_buy_hour03_validation.set` を使う。これは `InpUseBuyAllowedServerHours=true`、`InpBuyAllowedServerHours=3` 固定で、BUYだけを対象にentry条件とRRを再検証する。

```bash
python3 analysis/mt5_tester_run.py \
  --config mt5/TesterConfigs/Swing_Evaluation_Trader_buy_hour03_validation.ini \
  --report-name Tester\\Swing_Evaluation_Trader_buy_hour03_validation \
  --timeout-seconds 7200 \
  --since-minutes 240 \
  --min-closed 100 \
  --min-segment-closed 500 \
  --min-segment-pf 1.2 \
  --focus-side buy \
  --output-json runtime/latest_mt5_tester_buy_hour03_validation_run.json \
  --output-md runtime/latest_mt5_tester_buy_hour03_validation_run.md \
  --optimization-output-json runtime/latest_mt5_buy_hour03_validation_optimization_report.json \
  --optimization-output-md runtime/latest_mt5_buy_hour03_validation_optimization_report.md \
  --recommendation-output-json runtime/latest_mt5_buy_hour03_validation_recommendation.json \
  --recommendation-output-md runtime/latest_mt5_buy_hour03_validation_recommendation.md \
  --template-set mt5/TesterSets/Swing_Evaluation_Trader_buy_hour03_validation.set \
  --output-set runtime/Swing_Evaluation_Trader_buy_hour03_validation_next.set
```

hour03単独でaggregateは強いがpass単位の取引数が薄い場合は、BUY entry refitで相対的に良かった03/05/06/10時台へ広げる。`Swing_Evaluation_Trader_buy_strong_hours_validation.set` は `InpBuyAllowedServerHours=3,5,6,10` 固定で、同じentry条件探索をサンプル増加後に再評価する。

```bash
python3 analysis/mt5_tester_run.py \
  --config mt5/TesterConfigs/Swing_Evaluation_Trader_buy_strong_hours_validation.ini \
  --report-name Tester\\Swing_Evaluation_Trader_buy_strong_hours_validation \
  --timeout-seconds 7200 \
  --since-minutes 240 \
  --min-closed 100 \
  --min-segment-closed 500 \
  --min-segment-pf 1.2 \
  --focus-side buy \
  --output-json runtime/latest_mt5_tester_buy_strong_hours_validation_run.json \
  --output-md runtime/latest_mt5_tester_buy_strong_hours_validation_run.md \
  --optimization-output-json runtime/latest_mt5_buy_strong_hours_validation_optimization_report.json \
  --optimization-output-md runtime/latest_mt5_buy_strong_hours_validation_optimization_report.md \
  --recommendation-output-json runtime/latest_mt5_buy_strong_hours_validation_recommendation.json \
  --recommendation-output-md runtime/latest_mt5_buy_strong_hours_validation_recommendation.md \
  --template-set mt5/TesterSets/Swing_Evaluation_Trader_buy_strong_hours_validation.set \
  --output-set runtime/Swing_Evaluation_Trader_buy_strong_hours_validation_next.set
```

BUY strong-hoursでもM15 downやM30/M15 downが崩れる場合は、`Swing_Evaluation_Trader_buy_strong_hours_m30m15_validation.set` で上位足方向をBUYに揃える。これは `InpUseBuyM30M15UpGate=true`、`InpBuyAllowedServerHours=3,5,6,10` 固定で、BUY候補をM30/M15が両方upの時だけに制限する。

```bash
python3 analysis/mt5_tester_run.py \
  --config mt5/TesterConfigs/Swing_Evaluation_Trader_buy_strong_hours_m30m15_validation.ini \
  --report-name Tester\\Swing_Evaluation_Trader_buy_strong_hours_m30m15_validation \
  --timeout-seconds 7200 \
  --since-minutes 240 \
  --min-closed 100 \
  --min-segment-closed 500 \
  --min-segment-pf 1.2 \
  --focus-side buy \
  --output-json runtime/latest_mt5_tester_buy_strong_hours_m30m15_validation_run.json \
  --output-md runtime/latest_mt5_tester_buy_strong_hours_m30m15_validation_run.md \
  --optimization-output-json runtime/latest_mt5_buy_strong_hours_m30m15_validation_optimization_report.json \
  --optimization-output-md runtime/latest_mt5_buy_strong_hours_m30m15_validation_optimization_report.md \
  --recommendation-output-json runtime/latest_mt5_buy_strong_hours_m30m15_validation_recommendation.json \
  --recommendation-output-md runtime/latest_mt5_buy_strong_hours_m30m15_validation_recommendation.md \
  --template-set mt5/TesterSets/Swing_Evaluation_Trader_buy_strong_hours_m30m15_validation.set \
  --output-set runtime/Swing_Evaluation_Trader_buy_strong_hours_m30m15_validation_next.set
```

2025年通期でBUY strong-hours + M30/M15-upがPF 0.8980、平均R -0.1906、positive forward/back 0まで崩れた場合は、採用せず `Swing_Evaluation_Trader_buy_wide_stop_validation.set` でSL幅だけを切り分ける。これは同じ時間帯/上位足ゲートを固定し、`InpMinStopPoints=300`、`InpMaxStopPoints=350` の広めSLだけを検証する。年次aggregateではこのSL帯だけがPF 1.9573だったが、XML back/forwardが通っていないため診断専用とする。

```bash
python3 analysis/mt5_tester_run.py \
  --config mt5/TesterConfigs/Swing_Evaluation_Trader_buy_wide_stop_validation.ini \
  --report-name Tester\\Swing_Evaluation_Trader_buy_wide_stop_validation \
  --timeout-seconds 7200 \
  --since-minutes 240 \
  --min-closed 100 \
  --min-segment-closed 500 \
  --min-segment-pf 1.2 \
  --focus-side buy \
  --output-json runtime/latest_mt5_tester_buy_wide_stop_validation_run.json \
  --output-md runtime/latest_mt5_tester_buy_wide_stop_validation_run.md \
  --optimization-output-json runtime/latest_mt5_buy_wide_stop_validation_optimization_report.json \
  --optimization-output-md runtime/latest_mt5_buy_wide_stop_validation_optimization_report.md \
  --recommendation-output-json runtime/latest_mt5_buy_wide_stop_validation_recommendation.json \
  --recommendation-output-md runtime/latest_mt5_buy_wide_stop_validation_recommendation.md \
  --template-set mt5/TesterSets/Swing_Evaluation_Trader_buy_wide_stop_validation.set \
  --output-set runtime/Swing_Evaluation_Trader_buy_wide_stop_validation_next.set
```

`Swing_Evaluation_Trader_buy_wide_stop_validation.set` の短期窓結果はPF 1.4914、平均R 0.3299、closed 7,267まで改善したが、positive forward/back passは0だった。RR 1:2がPF 1.8406で最も強く、RR 1:5もPF 1.3366でプラスだったが、安定passがないため採用しない。entry 03:00-04:00はPF 6.1193と強い一方、entry 10:00-11:00、6月、火曜が大きく崩れるため、次にBUYを続ける場合はSL幅ではなくentry hour/calendar splitまたはBUY評価関数の再設計を優先する。

entry 03:00-04:00だけに切る診断は `Swing_Evaluation_Trader_buy_hour03_wide_stop_validation.set` を使う。これはwide-stopとM30/M15 upを維持しつつ、`InpBuyAllowedServerHours=3` だけに狭める。短期で良くても年次/out-of-yearでPF >= 1.2、平均R > 0、positive forward/back passが出るまでは採用しない。

```bash
python3 analysis/mt5_tester_run.py \
  --config mt5/TesterConfigs/Swing_Evaluation_Trader_buy_hour03_wide_stop_validation.ini \
  --report-name Tester\\Swing_Evaluation_Trader_buy_hour03_wide_stop_validation \
  --timeout-seconds 7200 \
  --since-minutes 240 \
  --min-closed 100 \
  --min-segment-closed 500 \
  --min-segment-pf 1.2 \
  --focus-side buy \
  --output-json runtime/latest_mt5_tester_buy_hour03_wide_stop_validation_run.json \
  --output-md runtime/latest_mt5_tester_buy_hour03_wide_stop_validation_run.md \
  --optimization-output-json runtime/latest_mt5_buy_hour03_wide_stop_validation_optimization_report.json \
  --optimization-output-md runtime/latest_mt5_buy_hour03_wide_stop_validation_optimization_report.md \
  --recommendation-output-json runtime/latest_mt5_buy_hour03_wide_stop_validation_recommendation.json \
  --recommendation-output-md runtime/latest_mt5_buy_hour03_wide_stop_validation_recommendation.md \
  --template-set mt5/TesterSets/Swing_Evaluation_Trader_buy_hour03_wide_stop_validation.set \
  --output-set runtime/Swing_Evaluation_Trader_buy_hour03_wide_stop_validation_next.set
```

`Swing_Evaluation_Trader_buy_hour03_wide_stop_validation.set` の短期窓結果はPF 5.7400、平均R 1.6671、closed 1,732と大きく改善したが、positive forward/back passは0だった。2025年通期ではclosed 60,491、PF 1.1593、平均R 0.1157、純益23,322.99で、利益は残ったものの昇格閾値PF 1.2に届かず、positive forward/back passも0だった。RR別では1:3がPF 1.2385で最も近く、弱い月は6月/8月/10月、弱い曜日は水曜/金曜だった。

このため次の診断は `Swing_Evaluation_Trader_buy_hour03_wide_stop_calendar_validation.set` を使う。これはhour03、M30/M15 up、広めSLを維持しつつ、`InpUseFittedBuyCalendarFilter` をON/OFFし、`InpBuyBlockedMonths=6,8,10` と `InpBuyBlockedWeekdays=3,5` を適用するかを検証する。RRは年次で最も近かった1:3に固定し、SL幅は300-400ptへ少し広げる。短期で良くても年次/out-of-yearでPF >= 1.2、平均R > 0、positive forward/back passが出るまでは採用しない。

```bash
python3 analysis/mt5_tester_run.py \
  --config mt5/TesterConfigs/Swing_Evaluation_Trader_buy_hour03_wide_stop_calendar_validation.ini \
  --report-name Tester\\Swing_Evaluation_Trader_buy_hour03_wide_stop_calendar_validation \
  --timeout-seconds 7200 \
  --since-minutes 240 \
  --min-closed 100 \
  --min-segment-closed 500 \
  --min-segment-pf 1.2 \
  --focus-side buy \
  --output-json runtime/latest_mt5_tester_buy_hour03_wide_stop_calendar_validation_run.json \
  --output-md runtime/latest_mt5_tester_buy_hour03_wide_stop_calendar_validation_run.md \
  --optimization-output-json runtime/latest_mt5_buy_hour03_wide_stop_calendar_validation_optimization_report.json \
  --optimization-output-md runtime/latest_mt5_buy_hour03_wide_stop_calendar_validation_optimization_report.md \
  --recommendation-output-json runtime/latest_mt5_buy_hour03_wide_stop_calendar_validation_recommendation.json \
  --recommendation-output-md runtime/latest_mt5_buy_hour03_wide_stop_calendar_validation_recommendation.md \
  --template-set mt5/TesterSets/Swing_Evaluation_Trader_buy_hour03_wide_stop_calendar_validation.set \
  --output-set runtime/Swing_Evaluation_Trader_buy_hour03_wide_stop_calendar_validation_next.set
```

`Swing_Evaluation_Trader_buy_hour03_wide_stop_calendar_validation.set` の短期窓結果はclosed 1,609、PF 6.2140、平均R 1.7013まで改善したが、positive forward/back passは0だった。2025年通期ではclosed 47,303、PF 1.1215、平均R 0.0886、純益14,682.68で、元のhour03 wide-stop年次PF 1.1593より悪化した。Tester XMLではcalendar ONのback passは平均PF 1.4936でcalendar OFFの1.2712より良かった一方、forward passはON/OFFとも全てマイナスで、calendar ON平均PF 0.9131、OFF平均PF 0.9166だった。Chronological splitでも前半PF 1.2615に対して後半PF 0.9951、q2 PF 0.7124、q3 PF 0.9317まで崩れた。したがってcalendar filterはback側のfitには効くがforwardと時系列後半には残らず、採用しない。

SELL time-filterの年次検証が崩れ、entry品質を再fitする場合は、SELL entry専用セットを使う。

```bash
python3 analysis/mt5_tester_run.py \
  --config mt5/TesterConfigs/Swing_Evaluation_Trader_sell_entry_refit.ini \
  --report-name Tester\\Swing_Evaluation_Trader_sell_entry_refit \
  --timeout-seconds 7200 \
  --since-minutes 240 \
  --min-closed 100 \
  --min-segment-closed 500 \
  --min-segment-pf 1.2 \
  --output-json runtime/latest_mt5_tester_sell_entry_refit_run.json \
  --output-md runtime/latest_mt5_tester_sell_entry_refit_run.md \
  --optimization-output-json runtime/latest_mt5_sell_entry_refit_optimization_report.json \
  --optimization-output-md runtime/latest_mt5_sell_entry_refit_optimization_report.md \
  --recommendation-output-json runtime/latest_mt5_sell_entry_refit_recommendation.json \
  --recommendation-output-md runtime/latest_mt5_sell_entry_refit_recommendation.md \
  --template-set mt5/TesterSets/Swing_Evaluation_Trader_sell_entry_refit.set \
  --output-set runtime/Swing_Evaluation_Trader_sell_entry_refit_next.set
```

entry専用セットでpositive forward/back passが0のままなら、trend/time regimeも同時に振る。

```bash
python3 analysis/mt5_tester_run.py \
  --config mt5/TesterConfigs/Swing_Evaluation_Trader_sell_regime_entry_refit.ini \
  --report-name Tester\\Swing_Evaluation_Trader_sell_regime_entry_refit \
  --timeout-seconds 7200 \
  --since-minutes 240 \
  --min-closed 100 \
  --min-segment-closed 500 \
  --min-segment-pf 1.2 \
  --output-json runtime/latest_mt5_tester_sell_regime_entry_refit_run.json \
  --output-md runtime/latest_mt5_tester_sell_regime_entry_refit_run.md \
  --optimization-output-json runtime/latest_mt5_sell_regime_entry_refit_optimization_report.json \
  --optimization-output-md runtime/latest_mt5_sell_regime_entry_refit_optimization_report.md \
  --recommendation-output-json runtime/latest_mt5_sell_regime_entry_refit_recommendation.json \
  --recommendation-output-md runtime/latest_mt5_sell_regime_entry_refit_recommendation.md \
  --template-set mt5/TesterSets/Swing_Evaluation_Trader_sell_regime_entry_refit.set \
  --output-set runtime/Swing_Evaluation_Trader_sell_regime_entry_refit_next.set
```

`mt5_tester_run.py` は実行前にCompile鮮度を確認する。`all_compiled_fresh=false` の時は既定でOptimizationを起動しない。既存のTester出力だけ再集計する場合は `--collect-only`、診断目的で古い `.ex5` を許容する場合は `--allow-stale-compile` を明示する。既存の `terminal64.exe` が起動中の場合も既定で止める。これは `/config` 起動が既存MT5へ吸われ、return code 0でもTesterが走らないことを避けるためで、診断時だけ `--allow-running-terminal` を使う。起動前に止めた理由は `blocked_components.compile_stale` / `risk_preset_invalid` / `terminal_already_running` / `agent_csv_archive_failed` と個別booleanに残し、親run JSON、子停止マーカー、Promotion Gate check valueから機械判定できるようにする。親run Markdownにも `Running Terminal Detection` として検出ON/OFF、ブロック有無、起動中terminalのPID/commandを表示する。

`mt5_tester_status.py` はTesterを起動せず、`latest_mt5_tester_run.json`、`latest_promotion_gate.json`、`latest_mt5_compile_status.json`、任意の `latest_mt5_optimization_report.json`、`latest_mt5_next_action_run.json`、`latest_mt5_back_forward_run.json`、`latest_mt5_manual_test_queue.json`、`latest_mt5_manual_operator_packet_with_optimization.json`、`latest_bridge_recovery_plan.json`、stable candidateの最適化レポート/推薦/runner JSON、現在の `terminal64.exe` プロセスを読んで、`runtime/latest_mt5_tester_status.json` / `.md` を更新する。`operational_status` は `blocked_running_terminal`、`ready_to_rerun_after_terminal_closed`、`blocked_compile_stale`、`blocked_risk_preset`、`blocked_risk_preset_schema`、`blocked_agent_csv_archive`、`terminal_failed`、`source_time_blocked`、`report_fallback_blocked`、`latest_run_ok` などに正規化し、Markdownには次アクション、起動中terminalのPID/command、Bridge Recoveryのstatus/ready/EA POST鮮度/blocking reasons/next action、入力artifactの存在/更新時刻/経過秒数/fresh判定、最新runnerのブロック理由、terminal開始時刻/deadline/elapsed、risk preset要約のスキーマ必須/状態/鮮度/欠落入力、compile鮮度、Optimization pass予算、MT5 Manual Test Queue、MT5 Back/Forward Runnerのdry-run計画と実行ready状態、stable candidateのclosed/PF/採用不可理由、stable candidate検証後のrefit side/driver/kind/config/set/output set/archive run ID、Promotion GateのP1 action、Promotion Gateのfailed check名、Back/Forward Gate checkのpass/value/requirementを表示する。冒頭の `MT5 Next Operator Action` にはoperator packet由来のaction/mode/instruction/queue step/follow-up collectコマンドに加えて、packet内 `next_step.quick_input`、next step summary、collect filterも表示し、operator packet単体またはstatus JSONだけでMT5画面へ入力する値、手動実行前の下限時刻、回収対象Report/Agent CSVを読めるようにする。標準出力JSONと `runtime/latest_mt5_tester_status.json` の `operator_summary` にも `manual_strategy_tester_available`、`manual_strategy_tester_recommended`、`manual_strategy_tester_collect_only_command_text`、`manual_strategy_tester_collect_status`、`manual_strategy_tester_collect_next_action`、`manual_test_queue_status`、`manual_test_queue_next_action`、`manual_test_queue_entry_count`、`manual_test_queue_total_entry_count`、`manual_test_queue_stale_entry_count`、`manual_test_queue_step_count`、`manual_test_queue_waiting_count`、`manual_operator_packet_with_optimization_next_operator_action/mode/instruction/follow_up`、`manual_operator_packet_with_optimization_next_step_quick_input`、`manual_operator_packet_with_optimization_next_step_operator_summary`、`manual_operator_packet_with_optimization_next_step_collect_filter_summary` を含め、既存terminalで `/config` 起動がブロックされている時も、MT5画面でBacktest/Forward/SELL/BUY sample collectionを手動実行してからcollect-onlyで取り込む入口をJSONだけで確認できるようにする。`mt5_tester_status_watch.py` はBridge Recovery要約と統合手動キュー要約をheartbeatへ転記し、operator packet要約として `manual_operator_packet_with_optimization_next_operator_*` に加え、`manual_operator_packet_with_optimization_next_step_quick_input`、`manual_operator_packet_with_optimization_next_step_operator_summary`、`manual_operator_packet_with_optimization_next_step_collect_filter_summary` も必須snapshot keyとして残す。古いwatcherがpacket内のMT5入力値やcollect filterを転記できない場合はheartbeat incompatibleとして再起動対象にする。`bridge_recovery_plan_status`、`bridge_recovery_plan_ready_for_mt5_validation`、`bridge_recovery_plan_output_json`、`bridge_recovery_plan_blocking_reasons`、`bridge_recovery_plan_next_action`、`manual_test_queue_status`、`manual_test_queue_entry_count`、`manual_test_queue_total_entry_count`、`manual_test_queue_stale_entry_count`、`manual_test_queue_waiting_count`、`manual_test_queue_execution_checklist` なども必須snapshot keyとして扱う。Promotion Gate Markdownもstatus watcher heartbeatの統合手動キューを `MT5 Manual Queue From Watcher` として短く表示し、Manual Execution Checklistに加えてworkspace `.ini`、MT5 `.ini`、launch kind、launch command、stale runner refreshを確認できるようにする。`mt5_manual_operator_packet.py` と `mt5_manual_auto_collect_watch.py` も `latest_bridge_recovery_plan.json` を読み、短いMT5作業packetにBridge status、EA POST鮮度、履歴pending/stale、Bridge検証コマンド、`Standalone Strategy Tester allowed` を表示する。`mt5_manual_operator_packet.py` はさらに `latest_mt5_strategy_tester_analysis.json` を読み、Strategy EvidenceとしてBack/Forward証跡、source-time刷新計画、BUY候補不足の診断キューを同じpacketに表示し、`next_operator_action` で手動入力、自動起動、collect ready、report待ちを正規化する。`mt5_manual_auto_collect_watch.py` はoperator packet更新結果から `next_operator_action/mode/instruction/command/follow_up` も転記する。これによりBridgeが `needs_ea_restart` でも、Bridge非依存のBacktest/Forward TestをMT5 Strategy Tester上で進めてよい状態、Bridge復旧後に確認するコマンド、次にOptimization/source-time/BUY診断を回す理由を操作者が同じファイルで判断できる。

status watcher heartbeatのoperator packet契約では、`manual_operator_packet_with_optimization_next_operator_before_mt5_command_text` を必須snapshot keyにする。これはMT5 Strategy Testerを手動Startする直前に `--mark-manual-run-start` で回収下限時刻を更新するためのコマンドで、古いwatcherがこのbefore-MT5 mark commandを転記できない場合はheartbeat incompatibleとして再起動対象にする。

`MT5 Operator Handoff` が `manual_strategy_tester` を推奨している場合、stdout/Markdownの `next_action` は既存terminalを閉じる指示ではなく、次にMT5画面で実行するstepを表示する。`operational_status` 自体は `/config` 自動起動不可を表すため `blocked_running_terminal` のまま残すが、Coverageの完了判定ではこの状態だけを `mt5_tester_status_not_ready:blocked_running_terminal` として二重に扱わない。未完了理由は `mt5_back_forward_not_executed`、手動キュー、Report/Agent CSV待ち、score weightサンプル不足など実際の次アクションへ寄せる。

Manual Strategy Tester欄の `auto_launch_blockers` は、統合手動キューがBack/Forward stepを選択済みなら `latest_mt5_manual_queue_launch.json` の選択stepのblockerを優先して表示する。これにより、古いBack/Forward runner単体の鮮度診断を操作者向けの次アクションと混同せず、`running_terminal_blocks_direct_config` の場合はMT5を閉じるのではなく手動Strategy Testerで進める判断を同じstatusファイル内で確認できる。

`latest_mt5_back_forward_run.json` / `.md` には `Execution Hints` を保存する。ここには、同じ `run_id_prefix`、timeout、since、min closed、期間、ForwardMode、同期/許可フラグを引き継いだMT5起動コマンドと、MT5画面で手動Strategy Testerを回した後に既存XML/Agent CSVだけを取り込む `--collect-only` コマンドを出す。さらに `manual_strategy_tester` / `Manual Strategy Tester Checklist` として、MT5画面で選ぶExpert、Symbol、Period、Model、Dates、Forward、Inputs、Report名、生成時刻を下限にした推奨 `--csv-modified-after` 付きcollect-onlyコマンドを保存し、既存terminalが開いていて `/config` 起動できない時も同じBack/Forward計画を手動で再現できるようにする。`MT5 Strategy Tester Quick Start` には `MT5 mode`、`run_type`、`report_note` を表示し、`Optimization=0` の単発Forward profileで期待するHTML report + Agent CSVと、Optimization Forwardで期待するXML + forward XML + Agent CSVを混同しないようにする。`latest_bridge_recovery_plan.json` を明示して未readyでも、既定ではBridge非依存のStandalone Strategy TesterとしてMT5起動ヒント、step command、手動Strategy Tester checklistを残す。Bridge readyも必須にしたい診断時だけ `--require-bridge-ready` を付け、その場合は `bridge_recovery_not_ready` でstep実行前に止まり、MT5起動ヒントと手動Strategy Tester checklistをMarkdownから隠す。`Manual Collect Readiness` は `ready/status/reason/blocking_reasons/next_action` とstep別 `blocking_reason` を保存し、Report未生成、Agent CSV未生成/古い、`--csv-modified-after` 不正をファイルだけで判断できるようにする。Runner Markdown本文にも `Skip archive preview` を表示し、MT5起動ヒントとcollect-onlyヒントの両方に `--skip-archive-preview` を保持する。`latest_mt5_tester_status.md` のBack/Forward Runner欄はこの `manual_strategy_tester` を再表示し、statusファイルだけでもMT5上でBacktest/Forward Testを手動実行してからcollect-onlyで取り込む手順を確認できる。Back/Forward実行ヒントも同じ条件に加えて `max_ready_status_age_seconds` と `skip_archive_preview` を保持し、step commandが省略されたrunnerでも `execution_conditions` からtimeout、since、min closed、期間、ForwardMode、同期/許可フラグを復元して、status側のヒントから実行してもpreflight条件が落ちないようにする。これによりstatus Markdownを開かなくても、runner証跡ファイル単体から次に実行するBack/Forward手順を確認できる。

Back/Forward Runnerのsample shortage系statusは候補拒否ではなく評価不能として扱う。Promotion Gateは `collect_more_mt5_back_forward_samples_before_promotion` を出し、min_closed、backtest/forward closed件数、各stepが閾値を満たしたかをnext action直下に表示する。あわせて `sample_shortage_recovery` に、同じBack/Forward Runnerを `--from-date 2025.01.01 --to-date 2025.12.31` の拡張期間で再実行するコマンドを表示し、短期窓の件数不足を成績劣化と誤読しないようにする。現在のfrom/toが180日未満なら短期窓を引き継がず2025年通年へ上書きし、180日以上の既存窓だけを再利用する。

手動でMT5 Strategy Testerを開く前にAgent CSVの残存期間だけ確認したい場合は、`mt5_back_forward_run.py --run-archive-preview` を使う。このモードはdry-runのままMT5を起動せず、Back/Forward各stepのarchive previewだけを実行し、source time coverageとvalidation結果を `latest_mt5_back_forward_run.json` / `.md` とstatus watcherに残す。previewコマンド自体が失敗した場合は、同じrun-idの古いpreview artifactが存在しても `archive_preview_command_failed` として失敗扱いにし、古いCSV確認結果で実行可否を誤判定しない。

`latest_mt5_tester_status.md` の `MT5 Status Watcher` 欄にも、heartbeatが保持しているNext Action Runnerのprimary/archive preview/follow-up/follow-up archive previewのplanned outputs、4分類をまとめた `next_action_run_planned_outputs`、action context key、関連実行件数/キー、Blocking prior actionsの件数/一覧/summary、Manual Collect Readinessを表示し、常駐watcherが実行前preflightで比較する出力先と前段証跡、MT5手動実行後の取り込み可否をファイルだけで確認できるようにする。統合手動キューについてもstatus、next action、entry/total/stale/step/waiting/ready件数、blocking reasons、Manual Execution Checklistを表示し、Back/ForwardとBUY/SELL sample collectionのどれがReport/Agent CSV待ちか、次にMT5画面でどの順番に実行するか、古いrunner由来のentryが混ざっていないかをwatcherだけで確認できるようにする。Promotion Gateは `mt5_status_watch_heartbeat` check valueとMarkdownの `MT5 Manual Queue From Watcher` に `mt5_next_operator_action`、`mt5_next_queue_step`、`mt5_next_manual_run_start_effective_after`、`mt5_auto_launch_blocked`、`mt5_strategy_operator_decision_verdict`、`mt5_strategy_operator_decision_primary_blocker`、`mt5_collect_execute_command_text` などのwatcher aliasも表示し、Gateだけを見てもMT5上で次に手動入力するstep、自動起動blocker、collect入口、Back/Forward未実行blockerを確認できるようにする。Promotion Gateは `mt5_status_watch_next_action_current` で、heartbeatのNext Action Runner target/config/set/archive run ID/Gate世代/planned outputsが最新statusの `next_action_runner` と一致するかを確認し、watcher自体が `ok` でも古い出力先や古いGate世代を見ていればFAILにする。Back/Forward Runnerについてもheartbeat上の `run_id_prefix`、手動Strategy Tester後のcollect-onlyコマンド、手動開始下限時刻、Manual Collect Readiness、手動step数、per-step timeout、since minutes、min closed、ForwardMode上書き、同期/許可フラグ、Ready Status ok/reasons/mismatches、checked step keys/options/flags、checked/expected/status execution conditions、archive preview出力先/step別preview mapを同じ欄に表示し、常駐watcherがどのBack/Forward条件と手動取り込み入口を監視しているかをstatusファイルだけで確認できるようにする。Promotion Gateは `mt5_status_watch_back_forward_current` で、heartbeatのBack/Forward `run_id_prefix` と `execution_conditions` が最新 `latest_mt5_back_forward_run.json` と一致するかも確認し、watcher自体が `ok` でも古いrun-id、ForwardMode、timeout、期間、許可フラグを見ていればFAILにする。

Optimization込みの手動オペレータpacketは、ネストした `next_operator_action` に加えて、`next_operator_action_name`、`next_operator_mode`、`next_operator_queue_step`、`next_operator_quick_input`、`next_operator_launch_state`、`next_operator_instruction`、`next_operator_command_text`、`next_operator_follow_up_command_text`、`next_operator_verification`、`auto_launch_command_text`、`auto_launch_command_available`、`auto_launch_blocked`、`auto_launch_blocked_reasons`、`manual_run_start_effective_after` をトップレベルaliasとして持つ。`mt5_tester_status.py` と `mt5_tester_status_watch.py` はこれらを `manual_operator_packet_with_optimization_*` としてheartbeatへ転記し、MT5が起動中で `/config` 自動起動がブロックされている場合でも、次にStrategy Tester画面で入力するstep、Inputs/Report/Forwardなどのquick input、手動開始下限時刻、実行後のcollect-only入口をファイルだけで確認できるようにする。古いwatcherが `manual_operator_packet_with_optimization_next_operator_quick_input`、`manual_operator_packet_with_optimization_auto_launch_command_available`、または `manual_operator_packet_with_optimization_manual_run_start_effective_after` を転記できない場合は `running_heartbeat_incompatible` として再起動対象にする。

`latest_mt5_tester_status.json` は、詳細な `operator_summary` を残した上で、手元スクリプトや外部監視が1階層だけ読めばよいように `mt5_next_operator_action`、`mt5_next_operator_mode`、`mt5_next_operator_launch_state`、`mt5_next_queue_step`、`mt5_next_quick_input`、`mt5_next_step_operator_summary`、`mt5_next_step_summary`、`mt5_next_step_collect_filter_summary`、`mt5_next_manual_run_start_effective_after`、`mt5_auto_launch_command_available`、`mt5_auto_launch_blocked`、`mt5_auto_launch_command_text`、`mt5_back_forward_quick_start_quick_inputs`、`mt5_back_forward_quick_start_current_quick_input`、`mt5_collect_dry_run_command_text`、`mt5_collect_execute_command_text`、`mt5_collect_execute_and_refresh_analysis_command_text`、`mt5_collect_execute_and_refresh_full_analysis_command_text`、`mt5_strategy_operator_decision_verdict`、`mt5_strategy_operator_decision_primary_blocker`、`mt5_strategy_operator_decision_command_text` をトップレベルaliasとして出す。加えて `MT5 Operator Handoff` 本体も `mt5_operator_handoff_state`、`mt5_operator_handoff_recommended_path`、`mt5_operator_handoff_next_mt5_step`、`mt5_operator_handoff_quick_input`、`mt5_operator_handoff_next_step_summary`、`mt5_operator_handoff_manual_collect_execute_command_text`、`mt5_operator_handoff_manual_collect_execute_and_refresh_full_analysis_command_text`、`mt5_operator_handoff_bridge_status` などのトップレベルaliasへ展開し、Markdownやネストした `operator_summary` を読まない監視でもMT5画面の次step、手動入力値、collect入口、Bridge非依存注記を確認できるようにする。`manual_test_queue_next_queue_step`、`manual_test_queue_next_quick_input`、`manual_test_queue_with_optimization_next_queue_step`、`manual_test_queue_with_optimization_next_quick_input`、`manual_operator_packet_with_optimization_next_operator_quick_input`、`manual_operator_packet_with_optimization_back_forward_quick_start_quick_inputs` もトップレベルaliasへ出し、通常キューとOptimization込みキューのどちらでも次にMT5 Strategy Testerへ入力する値、Backtest/Forward Testペア両方の入力値、回収コマンドを1階層で読めるようにする。`mt5_tester_status_watch.py` も同じ `mt5_next_*`、`mt5_auto_launch_*`、`mt5_back_forward_quick_start_*`、`mt5_collect_*`、`mt5_strategy_operator_decision_*`、`mt5_operator_handoff_*`、`mt5_manual_queue_*`、`manual_test_queue_*`、`manual_test_queue_with_optimization_*`、`manual_operator_packet_with_optimization_*`、`manual_prerequisites_*`、`back_forward_plan_validation_*` aliasをheartbeat implementation version 89の必須snapshot keyとして出し、常駐watcherが古いimplementationのままなら `running_heartbeat_incompatible` で再起動対象にする。これにより、MT5画面でBacktest/Forward Testを手動実行する前後に、JSONの深い構造を知らない確認スクリプトでも次step、入力値、回収コマンド、採用判定ブロッカーを読めるようにする。

`spec_coverage.py` は `latest_mt5_tester_status.json.operator_summary` を優先しつつ、`operator_summary` が欠落、古い、または空値だけの場合でもトップレベルの `mt5_next_*`、`mt5_auto_launch_*`、`mt5_collect_*`、`mt5_strategy_operator_decision_*` aliasから同じ `mt5_operator_summary_*` を復元する。Coverage Markdownの `run_mt5_manual_test_queue` Next Actionでは、詳細構造の有無にかかわらず、次のStrategy Tester step、quick input、manual start after、collect dry-run/execute、Back/Forward未実行ブロッカーを表示する。

Coverage Markdownの `run_mt5_manual_test_queue` 手順には、`MT5 operator next action` としてaction/mode/launch state/manual start after、`MT5 operator auto launch` として `/config` 起動可否・blocked状態・blocker、`MT5 operator strategy decision` としてRUN_BACK_FORWARDなどのverdictとprimary blocker、必要なcollect-onlyコマンドを独立行で表示する。これにより、MT5画面上で手動入力すべき状態なのか、MT5を閉じて `/config` 自動起動できる状態なのか、実行後にどのcollectコマンドへ進むかをCoverageだけで判断できる。

`MT5 Status Watcher` 診断では、現行スキーマ用の `runtime/mt5_tester_status_watch_heartbeat_current.json` を読み、heartbeatを `ok`、`stale`、`incompatible`、`missing` に分類する。`incompatible` はheartbeatファイル自体は新しいが、現行statusが要求する `compile_all_tester_configs_synced`、`manual_test_queue_exists/status/next_action/entry_count/total_entry_count/stale_entry_count/current_for_execution_count/selected_action_current_count/current Gate generated_at/decision/gate_stale_reasons/step_count/ready_to_collect_count/waiting_count/all_collect_ready/blocking_reasons/entries/execution_checklist`、`back_forward_run_evidence_state`、`back_forward_run_run_id_prefix`、Back/Forward Runnerの手動collect-onlyコマンド / 手動開始下限時刻 / Manual Collect Readiness ready/status/csv_count/modified_after/reason/blocking/next_action / 手動step数 / 手動step一覧 / `back_forward_run_plan_validation_ready/status/reasons` / `back_forward_run_execution_conditions` / per-step timeout / since minutes / min closed / 期間上書き / ForwardMode上書き / 同期・許可フラグ / Ready Status ok/reasons/mismatches / checked step keys/options/flags / checked/expected/status execution conditions / `back_forward_run_archive_preview_output_json` / step別preview map、`promotion_failed_check_names`、`promotion_mt5_back_forward_run_check_value`、`next_action_run_current_for_execution`、runner/current Gate generated_at、Next Action RunnerのManual Collect Readiness、Next Action Runnerの集約/primary/archive preview/follow-up planned outputs、`next_action_run_action_context_keys` / `next_action_run_related_execution_count` / `next_action_run_related_execution_keys` / `next_action_run_blocking_prior_action_count/actions/summary`、`next_action_run_evidence_role` / `next_action_run_diagnostic_only` / `next_action_run_promotion_evidence`、score weight follow-up status / sample shortage / walk-forward status / set skip reason などのsnapshot keyが欠けているか、heartbeatの `implementation_version` が現行statusの期待値と一致しない状態であり、古い常駐watcherが動いている可能性が高い。この場合はstatus MarkdownとJSONの `restart_hint` に `mt5_tester_status_watch.py --manual-test-queue runtime/latest_mt5_manual_test_queue.json --manual-queue-launch runtime/latest_mt5_manual_queue_launch.json --manual-collect-run runtime/latest_mt5_manual_collect_run.json` を含む再起動コマンドを表示し、監視が動いているように見えるが新しいGate/Back-Forward判定、Tester `.ini` 同期状態、統合手動キュー、現行Gate上で実行できるqueue entry、次の自動起動候補、Manual Execution Checklist、Back/Forward実行条件、Back/Forward計画検証、Back/Forward手動取り込み入口とreadiness、Back/Forward preflightのok/reasons/mismatches、checked step/options/flags、checked/expected/status conditions、Back/Forward実行前preview、RunnerのGate世代、run-id別archive preview出力先、MT5起動前preflightで比較するplanned outputs、Next Action手動取り込みreadiness、前段action一覧/summary、診断用サンプル収集と昇格判定用成績の区分、score weight候補がwalk-forward不合格でサンプル収集へ戻っている理由を転記できていない状態を見落とさないようにする。Promotion Gateも `latest_mt5_tester_status.json` の `status_watch_heartbeat` を読み、`status != ok` の場合は `mt5_status_watch_heartbeat` checkをFAILにし、check valueへ `implementation_version`、expected implementation version、version mismatch、Next Action Runnerのplanned outputsとarchive preview出力先、Back/Forward Runnerの実行条件、Back/Forward計画検証、Ready Statusのok/reasons/mismatches、checked step keys/options/flags、checked/expected/status execution conditions、archive preview出力先/step別preview map、統合手動キューstatus/entry/total/stale/waiting/current Gate要約、`next_action_run_current_for_execution`、runner/current Gate generated_at、`gate_stale_reason`、前段action件数/一覧/summaryを残す。`restart_mt5_status_watch_with_current_schema` のnext actionとrestart commandにも同じ情報を表示し、どのwatcher世代がどのGate世代・出力先・preflight比較条件・手動キューを転記できていないかをGate Markdownだけで確認できるようにする。

現行watcherはstatus更新前に `mt5_manual_collect.py` をdry-run実行し、`manual_collect_refresh_enabled/returncode/status/queue_refresh_status/queue_refresh_ok/queue_refresh_source_count/selected_count/waiting_count/invalid_count` と、更新後の `manual_collect_run_*` をheartbeatへ残す。`manual_collect_run_queue_step_count/queue_step_report_ready_count/queue_step_waiting_report_count/queue_step_launch_needed_count` も必須snapshot keyとして扱い、MT5手動実行後に「レポートだけ進んだ」「まだ次step起動が必要」「collect可能」のどこで止まっているかをwatcherだけで読めるようにする。Optimization込みの手動キューも通常キューと同じ粒度で `manual_test_queue_with_optimization_progress_state`、step ready/collect/waiting/launch-needed件数、step ID一覧、collect確認コマンドをheartbeatとstatus Markdownへ転記し、Back/Forward、BUY/SELL sample collection、年次/Optimization候補のどこで止まっているかを同じ監視ファイルで読めるようにする。`returncode=2` は「readyなcollect対象がまだない」状態として扱い、watcher自体の失敗とは区別する。古いwatcherがこのdry-run refresh結果やstep進捗を出していない場合も `incompatible` にし、MT5手動実行後のcollect可能状態を監視ファイルだけで検出できない状態を避ける。watcher自身のstatus生成は `pre_status_refresh`、`post_status_refresh`、`synced_status_refresh` の順に進み、最終heartbeatとStatus内の埋め込みwatcher要約が同じ現行schemaを参照していることを `status_refresh_phase=synced_status_refresh` と `status_watch_heartbeat.status=ok` で確認する。

Promotion Gateが生成するAgent CSV archive run IDは、Gate自身の再生成時刻ではなく、MT5最適化/推薦、score weight、refit、年次検証などの入力証跡の最新生成時刻をseedにする。`mt5_tester_status` やwatcherの更新時刻だけではrun IDを変えず、同じ入力状態でGateだけを再生成してもNext Action Runnerのplanned outputsが即staleにならないようにする。Status側の `current_for_execution` もGateの `generated_at` 完全一致だけでは落とさず、decision、target、config、set、archive run ID、timeout、primary/archive/follow-up planned outputsが現Gateの選択actionと一致する場合は実行可能とする。一方、同じtargetでもrun IDや出力先が変わった場合は `selected_action_mismatch` としてMT5起動前に止める。Next Action Runnerの `generated_at` は互換用のGate時刻、`runner_generated_at` はRunner artifact生成時刻、`promotion_generated_at` / `promotion_decision` は明示的なGate参照として扱う。Promotion Gateの `mt5_status_watch_next_action_current` も同じ方針に合わせ、watcherが転記した `runner_promotion_generated_at` の差だけではFAILにせず、target/config/set/archive run ID/planned outputsなど実行計画の差だけをmismatchとして扱う。

年次検証などでは `--from-date` / `--to-date` / `--forward-mode` でTester期間を実行時に上書きできる。`.ini` を複製せず、同じ `.set` と同じ集計処理で短期/長期を比較する。指定した `FromDate` / `ToDate` は子のOptimizationレポートへ `expected_from_date` / `expected_to_date` として渡し、Agent CSVの実際の `server_time` 範囲がその期間内かを `source_time_diagnostics` で検査する。

2025年の1年分で同じSELL focused optimizationを確認する例:

```bash
python3 analysis/mt5_tester_run.py \
  --config mt5/TesterConfigs/Swing_Evaluation_Trader_next_optimization.ini \
  --report-name Tester\\Swing_Evaluation_Trader_next_optimization_2025 \
  --from-date 2025.01.01 \
  --to-date 2025.12.31 \
  --forward-mode 3 \
  --timeout-seconds 10800 \
  --since-minutes 240 \
  --archive-agent-csvs-before-run \
  --min-closed 100 \
  --min-segment-closed 500 \
  --min-segment-pf 1.2 \
  --focus-side sell \
  --output-json runtime/latest_mt5_tester_2025_run.json \
  --output-md runtime/latest_mt5_tester_2025_run.md \
  --optimization-output-json runtime/latest_mt5_2025_optimization_report.json \
  --optimization-output-md runtime/latest_mt5_2025_optimization_report.md \
  --recommendation-output-json runtime/latest_mt5_2025_recommendation.json \
  --recommendation-output-md runtime/latest_mt5_2025_recommendation.md \
  --output-set runtime/Swing_Evaluation_Trader_2025_next.set
```

指定した `Report` 名のTester XMLが存在しない場合は、MT5 Tester直下または `runtime/mt5_optimization` の最新 `Swing_Evaluation_Trader*.xml` / `.forward.xml` ペアへfallbackする。使用したXMLと要求されたXMLは `runtime/latest_mt5_tester_run.json.report_paths` に残し、誤ってforward XMLなしとして判定しない。ただしcollect-onlyではない通常起動でfallbackした場合は、指定Reportが生成されていない可能性があるため `report_fallback_blocked=true` とし、収集・推薦生成・`.set` 更新は行わない。

Optimization採用の判断順:

1. `By Action And Risk Reward` でBUY/SELL別にPFと平均Rを見る。
2. `Weak SL/TP Segments` でSL 0-50ptなど明確に崩れる帯を除外候補にする。
3. `Temporal Diagnostics` と `Weak Time Segments` で、短期候補が年次/月別/時間帯別に崩れていないか確認する。
4. `Chronological Split Diagnostics` でclose行を `server_time` 順に並べた前半/後半と四分割のPF/平均Rを確認する。後半や後半側quarterでPF < 1.0または平均R < 0なら、短期または前半だけのfitとして扱う。
5. `Trend Regime Diagnostics` と `Weak Trend Segments` で、M30/M15トレンドに対する買い/売り評価のずれを確認する。
6. `Best Segments` と `MT5 Optimization Recommendation` でPFが残るRR/SL/TP帯を次の探索範囲にする。RR×SL幅帯だけでなくRR×TP幅帯も確認し、遠すぎる利確ラインで崩れる設定を候補から外す。
7. `Tester Optimization XML` でforwardだけ良くbackが悪いパスを過剰適合候補として落とす。
8. backとforwardの両方が基準を満たすまで、live/デモ昇格はしない。

`Tester Optimization XML` には `Back Parameter Diagnostics` と `Forward Parameter Diagnostics` を出す。これはTester XMLの全passを `Inp...` 入力値ごとに集計し、pass数、positive result数、平均/最大Result、平均/最大PF、平均Tradesを比較するための表である。back側では良いがforward側ではpositive resultが0、または平均PFが1.0未満になる入力値はback-fit artifactとして扱い、次のsetへ固定採用しない。forward上位passがpositive forward / negative backの場合でも、`stable_top` にpositive forward / positive backのpassがある場合は、promotion gateのnext actionでstable候補を明示し、次setはstable passのパラメータへ制約する。今回のBUY calendar診断では `InpUseFittedBuyCalendarFilter=true` がback平均PF 1.4936を出した一方、forwardではpositive result 0、平均PF 0.9131だったため、calendar filterを採用しない根拠にした。

`mt5_optimization_recommend.py` が生成する `Swing_Evaluation_Trader_next_optimization.set` は、stable back/forward passから得た `stable_parameter_hints` をRRだけでなく、`InpMinScore`、`InpSwingDepth`、`InpSwingAtrBand`、`InpStopBufferPoints`、side別entry/filter閾値にも反映する。複数値が残る数値/真偽値は狭いOptimization範囲として残し、単一値だけの真偽値や文字列は固定する。`Next Set` には `Stable hint coverage` を出し、各hintが `.set` に反映されたか、back-fit artifactとして除外されたか、未対応でスキップされたかを確認できるようにする。Promotion Gateの `Next Action Execution Plans` には `recommendation_set_passes` と `recommendation_stable_hints` を表示し、既存 `.set` のpass数と、推薦されたが未書き込みの `.set` のpass数を混同しないようにする。これによりforward-only上位passの広い探索へ戻らず、stable pass群の周辺だけを次に検証する。

`Chronological Split Diagnostics` は、Agent CSVを統合した後のclose行を時系列順に並べ、`first_half` / `second_half` と `q1` - `q4` に分けて同じPF/平均R指標を出す。これはTester XMLのforward分割とは別に、実際に集計した取引CSVが年内のどこで崩れているかを見る粗いwalk-forward診断である。特定の月/時間帯の表だけでなく、時系列後半でedgeが消える場合は採用しない。失敗splitがある場合、`MT5 Optimization Recommendation` は `Chronological Failure Context` として失敗期間に重なる弱時間帯、弱trend regime、弱SL/TP帯を同じMarkdownに出し、次に時間帯切り出し、M30/M15 gate、SL/TP再探索のどれを優先するかを判断できるようにする。

年次/out-of-yearレポートでは、`source_time_diagnostics.expected_from_date` / `expected_to_date` と `actual_first_server_time` / `actual_last_server_time` を確認する。`matches_expected_range=false` の場合は、指定した年次Tester出力ではなく別期間のAgent CSVを集計している可能性が高いため、そのレポートは採用しない。`mt5_tester_run.py --from-date ... --to-date ...` 経由ではこの期待期間が自動で埋まる。`mt5_tester_optimization_report.py` を単体実行する場合は `--expected-from-date` / `--expected-to-date` を付け、既存レポート保護が必要な場合は `--fail-on-source-time-mismatch` も付ける。`mt5_tester_run.py` は期間不一致の集計では推薦生成と `.set` 更新を行わず、`source_time_blocked=true` / `ok=false` として扱う。

MT5 EAのCSV出力は追記式なので、同じAgentの `swing_evaluation_trades.csv` を残したまま別期間のTesterを走らせると、`server_time` の異なる行が同じファイルに混在する。`mt5_tester_run.py` で新しい検証を起動する時は `--archive-agent-csvs-before-run` を付け、既存CSVを退避してから実行する。退避先は `agent_csv_archive` としてrun JSON/Markdownに残す。

score品質ゲートでは、`score_upper_threshold_sample` がFAILの場合は、評価関数が70点以上の候補を十分に出せていないため、score配点/正規化を見直すか高score候補を十分に集める。promotion reportの `Score Calibration` には、要求閾値、要求count、最高到達score帯、countを満たす最高score帯、要求閾値までの点差、要求閾値で不足しているサンプル数を出す。`Next Action Execution Plans` の `score_calibration` でも同じ証跡を `score_gap`、`highest_sampled`、`highest_sufficient`、`calibration_recommendation` として実行コマンドの直下に表示し、再fit/追加収集の理由をコマンド近くで確認できるようにする。Optimization推薦が不採用、またはscore inversionで診断用setになる場合は、該当するMT5実行計画の直下に `recommendation_block`、`recommendation_reason`、`side_score_issue` を表示し、`adoptable=false`、`skipped_write=true`、`skip_reason=not_adoptable` または `diagnostic_only=true` / `skip_reason=diagnostic_only`、`score_refit_sides`、side別のbase/high PFを実行前に確認できるようにする。`skipped_write=true` の `mt5_optimization_recommendation` next actionは、古い `next_optimization.set` でTesterを再実行せず、既存の `runtime/latest_mt5_optimization_report.json` から `mt5_optimization_recommend.py` で推薦と `.set` だけを更新する。stable hintがある場合は、別名のstable candidate setを生成し、`stable_candidate` Tester計画で検証する。ただしこのsetは探索用であり、Promotion Gateの採用set条件は通過しない。検証済みstable candidateがある場合は、同じ実行計画に `stable_candidate_result` と失敗split/弱いtime/trend/SLTP帯を出し、再度同じ探索setを走らせるのではなく崩れた条件の再fitへ進む。stable pass、focused `next_optimization`、SELL score refit、regime/yearly refit、年次validation、MT5 runner失敗復旧のnext actionも、未更新の `.set` を直接実行せず、同じ推薦refresh planまたはstable candidate検証へ戻してから再評価する。70点以上のサンプルはあるが `score_upper_threshold_avg_r`、`score_upper_threshold_pf`、`score_threshold_avg_r_not_degrading` がFAILの場合は、scoreを上げても期待R/PFが改善していないため、評価関数そのものを再fitする。

昇格ゲート:

```bash
python3 analysis/promotion_gate.py \
  --history runtime/latest_history_168h.json \
  --calendar runtime/economic_calendar.json \
  --calendar-input-utc-offset 9 \
  --calendar-server-utc-offset 3 \
  --signal runtime/latest_signal.json \
  --command runtime/trade_command.json \
  --trade-result runtime/latest_trade_result.json \
  --forward-ledger runtime/forward_tests.jsonl \
  --forward-status runtime/latest_forward_test_status.json \
  --mt5-forward-report runtime/latest_mt5_forward_report.json \
  --mt5-optimization-report runtime/latest_mt5_optimization_report.json \
  --mt5-buy-refit-recommendation runtime/latest_mt5_buy_refit_recommendation.json \
  --mt5-buy-entry-refit-recommendation runtime/latest_mt5_buy_entry_refit_recommendation.json \
  --mt5-sell-entry-refit-recommendation runtime/latest_mt5_sell_entry_refit_recommendation.json \
  --mt5-sell-regime-entry-refit-recommendation runtime/latest_mt5_sell_regime_entry_refit_recommendation.json \
  --mt5-buy-hour03-validation-recommendation runtime/latest_mt5_buy_hour03_validation_recommendation.json \
  --mt5-buy-hour03-wide-stop-validation-recommendation runtime/latest_mt5_buy_hour03_wide_stop_validation_recommendation.json \
  --mt5-buy-hour03-wide-stop-calendar-validation-recommendation runtime/latest_mt5_buy_hour03_wide_stop_calendar_validation_recommendation.json \
  --mt5-yearly-optimization-report runtime/latest_mt5_2025_optimization_report.json \
  --mt5-compile-status runtime/latest_mt5_compile_status.json \
  --winrate-fit-report runtime/latest_winrate_fit.json \
  --risk-shape-weight-search-report runtime/latest_risk_shape_weight_search.json \
  --require-mt5-forward \
  --require-mt5-optimization \
  --require-mt5-yearly-optimization \
  --require-mt5-compile \
  --require-winrate-fit \
  --min-candidates 100 \
  --min-pf 1.2 \
  --max-drawdown-r 0 \
  --min-expectancy-r 0 \
  --min-side-avg-r 0.0 \
  --max-side-total-r-share 0.85 \
  --min-score-quality-threshold 70 \
  --min-score-quality-count 20 \
  --min-score-quality-avg-r 0.0 \
  --min-score-quality-pf 1.2 \
  --max-score-quality-avg-r-drop 0.25 \
  --max-dry-run-age-seconds 3600 \
  --min-forward-closed 30 \
  --min-forward-pf 1.2 \
  --max-forward-drawdown-r 0 \
  --min-forward-expectancy-r 0 \
  --min-forward-side-closed 10 \
  --min-forward-side-pf 1.0 \
  --min-forward-side-avg-r 0.0 \
  --min-mt5-forward-closed 30 \
  --min-mt5-forward-pf 1.2 \
  --max-mt5-forward-losing-streak 20 \
  --max-mt5-forward-drawdown-price-r 0 \
  --min-mt5-forward-expectancy-price-r 0 \
  --min-mt5-forward-side-closed 10 \
  --min-mt5-forward-side-pf 1.0 \
  --min-mt5-forward-side-avg-price-r 0.0 \
  --min-mt5-optimization-closed 100 \
  --min-mt5-optimization-pf 1.2 \
  --max-mt5-optimization-drawdown-price-r 0 \
  --min-mt5-optimization-expectancy-price-r 0 \
  --min-mt5-optimization-side-closed 30 \
  --min-mt5-optimization-side-pf 1.0 \
  --min-mt5-optimization-side-avg-price-r 0.0 \
  --min-mt5-optimization-forward-pf 1.2 \
  --min-mt5-optimization-forward-trades 30 \
  --min-mt5-optimization-positive-forward-back 1 \
  --min-mt5-yearly-optimization-closed 100 \
  --min-mt5-yearly-optimization-pf 1.2 \
  --min-mt5-yearly-optimization-avg-price-r 0.0 \
  --max-mt5-yearly-optimization-drawdown-price-r 0 \
  --min-mt5-yearly-optimization-expectancy-price-r 0 \
  --min-mt5-yearly-optimization-positive-forward-back 1 \
  --output-json runtime/latest_promotion_gate.json \
  --output-md runtime/latest_promotion_gate.md
```

`--max-*-drawdown-*` は `0` 以下で無効。`--min-*-expectancy-*` は未指定なら無効で、指定した場合は該当レポートの期待Rが閾値以上であることを要求する。どちらも値が存在しない古いレポートに対して明示的に有効化した場合はFAILにする。

`--require-mt5-optimization` を指定する場合、`latest_mt5_optimization_report.json` には `chronological_splits` が必要である。`chronological_splits` が欠落している場合は `mt5_optimization_chronological_splits` がFAILになり、`regenerate_mt5_optimization_report_with_chronological_splits` がnext actionに出る。この再集計planでは `mt5_tester_optimization_report.py --set-file mt5/TesterSets/Swing_Evaluation_Trader_next_optimization.set` を必ず渡し、chronological splitと同時にpass予算証跡も再生成する。失敗splitが1件でもある場合も同じcheckがFAILになり、こちらは原則として `reject_chronologically_unstable_optimization` がnext actionに出る。これはTester XMLのforward/backが良くても、年次CSVの後半またはquarterでedgeが消えた設定を昇格させないためのゲートである。このnext actionには `chronological_failure` に加えて `chronological_weak_time`、`chronological_weak_trend`、`chronological_weak_sl_tp` を出し、失敗期間を再fitする前に弱い時間帯/トレンド/SLTPをコマンド近くで確認できるようにする。ただしRecommendation refreshが不採用を確定し、SELL regime-entry refitも完了済みで、次にscore weight sample collectionを走らせる状態では、chronological rejectionを別P1 actionとして二重に残さず `sell_score_refit.upstream_chronological_rejection` へ統合する。この例外は昇格許可ではなく、失敗理由を保持したまま評価関数再fit用の診断サンプル収集へ進むための導線である。chronological split欠落、未処理のRecommendation refresh、またはscore sample収集へ進めない状態では従来通り先行ActionとしてMT5起動を止める。この年次検証planにも、実行と同じ `agent_csv_archive_run_id` の `mt5_agent_csv_archive.py --include-source-time` previewを含める。`mt5_yearly_optimization` を読み込んだ場合は、年次PF/平均Rだけでなく、positive forward/back passと年次chronological splitの欠落もFAILにし、`mt5_yearly_validation` のnext actionへ戻す。この年次validation actionにも `yearly_weak_time`、`yearly_weak_trend`、`yearly_weak_sl_tp` を表示し、年次の崩れを時間帯、trend gate、SL/TP再探索のどれで直すかを同じ実行計画上で確認する。短期Optimization推薦が不採用または未書き込みの間は、MT5 ForwardのPF/連敗/side別PFなどの性能不足actionも候補set検証として扱わず、`mt5_optimization_recommendation_refresh` へ戻す。ただしForward CSV schema、entry-time/trend診断、古い連敗停止limit、SL/TP診断キー不足は現行EA/forward_test診断として残し、`forward_test.set` の再実行または再集計計画を出す。

`--require-mt5-optimization` では、time/trend診断キーが存在しても `by_entry_server_hour` やM30/M15/M5 trend/slope系のgroupが `unknown` だけなら診断不可としてFAILにする。これは古いCSVを新しい集計器で再集計しただけで昇格ゲートを通してしまうのを防ぐためで、現行EAでStrategy Tester/Optimizationを再実行してから再集計する。

年次/out-of-year Optimizationレポートを読み込んだ場合も、`mt5_yearly_optimization_time_regime_diagnostics` と `mt5_yearly_optimization_trend_regime_diagnostics` を必須証跡として扱う。年次PFやforward/back passが良くても、entry hourやtrend/slope診断が欠落または `unknown` だけなら、古いCSV由来の検証として再実行/再集計へ戻す。

train/test方針:

- 時系列順を崩さない
- train内でさらに未来validation窓を作り、validationで残るルールだけを見る
- 最終testはルール選択に使わない
- 最大保有時間分の近接候補は、`--purge-records` / `--embargo-records` / `--embargo-minutes` でtrain/test境界から除外する
- 最終testで件数、平均R、PFが基準未満またはtest baselineより悪化したfitルールは `adoption_decision` で不採用にする
- Promotion Gateは `winrate_fit_walk_forward` でwalk-forward aggregateも確認する。最終testが通っても、`total_test_fitted_count` が最低件数未満、または `mean_test_fitted_pf` が最低PF未満なら採用しない
- 1週間だけで有効なルールは仮説扱いにし、別期間で再検証する
- live化前にフォワードテスト台帳で実時間順の検証を行う

## シグナル仕様

検証で有効な評価関数が得られたら、リアルタイム判定は次のJSONを出す。

```json
{
  "action": "sell",
  "symbol": "XAUUSD-m",
  "entry_low": 4107.80,
  "entry_high": 4108.40,
  "stop_loss": 4109.20,
  "take_profit": 4101.20,
  "risk_reward": 5.0,
  "score": 78.5,
  "pattern": "pullback_continuation",
  "valid_for_seconds": 120,
  "reason": "M15/M30 downtrend, M1 rebound failed below prior swing high",
  "risk_notes": [
    "spread is 37 points",
    "avoid if price reclaims M5 EMA slow"
  ]
}
```

## 自動売買への昇格条件

自動発注は以下を満たすまで行わない。

- 最低1週間以上のM1履歴で検証済み
- 100件以上の候補がある
- score上位帯で平均Rがプラス
- score上位帯でPFが1.2以上
- score閾値を上げた時に平均Rが大きく崩れていない
- 最大連敗が許容範囲内
- 買い/売り別で片側だけ大きく悪化していない
- 買い/売り別の平均Rが0以上
- プラス総Rのうち片側だけが85%超を占めない
- スプレッド込みでプラス
- デモまたはドライランで想定通りのシグナルが出る
- フォワードテストで十分なclosedサンプルがある
- フォワードテストでも平均RとPFが基準以上
- MT5 Forwardのside別score診断で `score_inversion` が出ていない。出た場合は `mt5_forward_{side}_score_not_inverted` を失格にし、side別score関数の再fitを次アクションにする
- MT5 Optimization、年次Optimization、MT5 ForwardでもBUY/SELL別のプラスprice-Rが片側だけに集中していない。`avg_price_r * price_r_count` でside別の総price-Rを近似し、プラス総price-Rの片側shareが85%を超える場合は `mt5_optimization_side_total_price_r_balance` / `mt5_yearly_optimization_side_total_price_r_balance` / `mt5_forward_side_total_price_r_balance` を失格にする
- dry-run結果が新しく、最新signalと一致している
- 最新signalがHOLDの場合はEA dry-run passedを昇格根拠にせず、BUY/SELLのtradable signalが出るまで待つ
- dry-run commandの `risk_gate.allowed = true`。証跡が無い場合はrisk gate付きdry-runを作り直し、`allowed=false` の場合は建玉/lot/日次損失/連敗停止のブロック解消を先に行う
- BUY/SELLのdry-run commandは、EAへ渡す前にSL/TP、source signal score下限、`max_spread_points` をPromotion Gateで再確認する。HOLDなど非tradable signalが正しくrejectedされた場合は、EA発注安全フィールドとしては要求しない

自動売買時の安全条件:

- MT5単体EAでは `InpSignalOnly = false`、`InpEnableTrading = true`、`InpAllowLiveTrading = true` は最終段階のみ。Strategy Tester用presetでは `InpRequireStrategyTester = true` とし、通常チャートで実発注する最終段階だけ `InpRequireStrategyTester = false` に戻す
- チャートボタンでの実発注は `InpChartButtonDryRunOnly = false`、`InpAllowChartButtonTrading = true` も最終段階のみ
- Bridge EA経由のlive commandでは `InpEnableTrading = true`、`InpAllowCodexTrading = true` は最終段階のみ
- 最大建玉数と合計lot上限は必須
- 現行運用では1回 `0.1` lotを基本とし、追加/ナンピンを許可する場合も合計 `0.3` lotまで
- SL/TP必須
- score下限必須
- spread上限必須
- 連敗停止ルール必須。MT5単体EAでは既定 `InpConsecutiveLossLimit = 20`、`InpConsecutiveLossCooldownMinutes = 120`
- 日次損失停止ルール必須。MT5単体EAでは既定 `InpDailyLossLimit = 5000.0`

## 段階的な進め方

### Phase 1: データ基盤

- 24h履歴取得を安定化
- 168h履歴取得を安定化
- 決済履歴とM1足を結合できるようにする
- 決済周辺のM1足レポートを出す

完了条件:

- `latest_history_168h.json` が取得できる
- M1が約10080本入っている
- 取引履歴と足時刻を突合できる
- Promotion Gateは `history_timeframes_complete` で `timeframes.M1/M5/M15/M30.bars` が168h期待本数の98%以上あるか確認し、top-level `bars` のコンパクトプレビューだけでは検証済み扱いにしない

### Phase 2: 山/谷検出

- M1/M5の山/谷を抽出
- ATR基準でノイズ除去
- チャート上で妥当か目視確認

完了条件:

- 山/谷の一覧CSV/Excelが出る
- 過剰検出が少ない
- リペイントしない確定方法になっている

### Phase 3: 候補生成

- 3パターンの候補を生成
- SL/TPを仮置き
- RRが5に満たない候補を除外

完了条件:

- 買い/売り候補が時系列で出る
- 各候補にSL/TP/score内訳が付く

### Phase 4: バックテスト

- TP/SL到達を検証
- スコア帯別に集計
- 時間帯別、方向別、パターン別に比較

完了条件:

- scoreが高いほど平均Rが上がるか判断できる
- 採用スコア下限の初期値を決められる

### Phase 5: シグナル化

- リアルタイムの最新スナップショットからscoreを算出
- `trade_signal.json` 形式で出力
- まずは通知/手動確認だけにする

完了条件:

- リアルタイムで候補が出る
- 理由とscore内訳が読める
- 手動トレード判断に使える

### Phase 5.5: MT5インジケータ表示

- `Swing_Evaluation_Predictor.mq5` を `MQL5/Indicators` に入れる
- XAUUSD M1チャートに適用する
- 左0%、縦80%付近の5行コンパクトな背景Boxとdry-run注文ラインだけを確認する
- `HOLD: 49.0` / `BUY: 61.0` / `SELL: 58.0` のように推奨とscoreを表示する
- HOLDは黄色、BUYは緑、SELLは赤で表示する
- HOLD時は `WAIT: SCORE LOW` / `WAIT: NO DOMINANCE` / `WAIT: SPREAD` などの短い理由を表示する
- Updated、spread、有効期限、BUY/SELL score、M30/M15トレンドを簡潔に表示する
- ENTRY、SL推奨値、TP推奨値を表示する。HOLD時は `WAIT: SCORE LOW` など短い理由を明示する
- 詳細根拠や注意書きは減らし、裁量判断に使う主情報だけを優先する
- ENTRY/SL/TP線が現在の裁量判断と大きくずれていないか見る
- 発注はしない。必要なら手動でラインを見て判断する

完了条件:

- buy/sell/holdの表示がチャート上で更新される
- Updated、score、BUY/SELL score、M30/M15トレンド、ENTRY/SL/TP推奨値が読める
- 採用条件を満たす時だけ `DRY-RUN ENTRY` / `DRY-RUN SL` / `DRY-RUN TP` 線が出る
- hold時に古い線が残り続けない

### Phase 6: ドライラン自動売買

- EAへtrade commandを出す
- ただしライブ発注せず、検証ログのみ
- SL/TP/score/理由を保存
- 日跨ぎ/指標proxy時間のsignalは拒否する
- 0.1 lot基準、合計0.3 lot上限のロットルールを監査ログに残す
- EA resultとcommand idを突合してdry-runが維持されたか確認する
- 古いEA resultや、現在のsignalと一致しないcommand resultは昇格判定に使わない
- signalをフォワードテスト台帳へ記録し、後続M1足でTP/SL/時間切れを評価する

完了条件:

- EAが期待通りに注文候補を拒否/受理する
- 誤発注リスクがない
- signal、command、EA resultの監査JSON/Markdownが出る
- フォワードテスト台帳と集計JSON/Markdownが出る
- 昇格ゲートが未達条件を具体的に出す

### Phase 7: 小ロット自動売買

- デモまたは最小ロットで開始
- 日次停止ルールを必須化
- 連敗停止を必須化

完了条件:

- 実運用ログとバックテストの差を評価できる
- MT5 CSVから滑り、スプレッド、価格ベースRを評価できる
- MT5 CSVからsignal/openの時刻差を約定遅延として評価できる

## 最初に作るもの

最初の実装対象は以下。

1. `analysis/swing_points.py`
2. `analysis/candidate_generator.py`
3. `analysis/scoring.py`
4. `analysis/backtest.py`
5. `reports/signal_score_backtest_*.xlsx`

最初のゴール:

```text
latest_history_24h.json を読み、
山/谷を検出し、
1:5候補を作り、
score帯別に平均Rと勝率を出す。
```

168h取得が安定したら同じ処理を1週間分に拡張する。
