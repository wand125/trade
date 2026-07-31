# Quality Secondary Tiebreak Validation

日時: 2026-06-29 15:17 JST
更新日時: 2026-06-29 15:17 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻である `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## 目的

`00146` では failure probability入り trade quality を `min_trade_quality` hard filterへ使うと、2025-05で悪化した。

今回は hard filterを避け、既存の `secondary_score_tie_margin` を使って near-tie のside選択だけに quality scoreを使う。entry threshold、raw EV、stateful risk5、MLP holding guardは維持し、side gapが小さい局面だけ `pred_trade_quality_*_adjusted_pnl` でlong/shortを選び直す。

## 設定

対象は highcost risk5 の2024-11..2025-04 OOF validation。predictionは `00146` の failure-prob quality列を stateful risk OOF predictionへ結合した。

固定条件:

- profit `1.0` / loss `1.20`
- spread `0.2`, slippage `0.1`, execution delay `1`
- policy `timed_ev`
- entry threshold `12`
- short entry offset `6`
- side margin `5`
- stateful `session_floor_lowered mean_match risk=5`
- MLP holding guard `30..480m`
- side EV penalty `short:down_low_vol=5`, `short:up_low_vol=10`

比較した `secondary_score_tie_margin` は `5`, `10`, `20`。

## Validation Results

| run | total PnL | trades | min month | max DD |
|---|---:|---:|---:|---:|
| baseline | `407.8172` | 502 | `-16.9006` | `224.7524` |
| margin 5 | `407.8172` | 502 | `-16.9006` | `224.7524` |
| margin 10 | `154.2024` | 544 | `-156.0008` | `198.3294` |
| margin 20 | `-84.8690` | 519 | `-212.8968` | `254.9618` |

月別では、margin 10は2025-04を `14.3072 -> 105.1364` に改善する一方、2025-03を `27.1660 -> -156.0008` へ壊す。margin 20は2024-11を `129.9968 -> -212.8968` へ大きく壊す。

margin 5は完全にbaselineと同じ結果だった。これは実質的にside gapが5以内でqualityがside選択を変える局面が、実行trade集合では効かなかったことを示す。

## 判断

1. failure-prob qualityをnear-tie secondary scoreへ使う今回の設定は採用しない。
2. margin 5は無効に近く、margin 10/20はvalidation内で大きな月別破綻を作る。
3. 2025-05固定適用は行わない。validationで採用条件を満たしていないため、最終test側へ進めるとpost-hoc探索になる。
4. quality scoreをside反転に使うより、同一side内のentry優先順位、EV overestimate residual、またはtail-risk targetの説明変数に回す。
5. 次は `pred_taken_ev - adjusted_pnl` の連続targetまたは上側分位targetを作り、quality/failure/exit特徴で過大評価幅を直接学習する。

## Artifacts

- merged validation predictions: `data/reports/modeling/20260629_1509_failure_quality_stateful_validation/`
- validation backtests: `data/reports/backtests/20260629_quality_secondary_tiebreak_validation/`

## 検証

- `python3 -m unittest tests.test_docs_reports`: 実施予定
- `git diff --check`: 実施予定

## 次の作業

1. `ev_overestimate_amount = max(pred_taken_ev - adjusted_pnl, 0)` の連続targetを作る。
2. mean targetだけでなく上側分位またはtail-risk targetを作る。
3. その予測を直接filterにせず、raw EVからのsoft residual penaltyまたはcandidate rankingに限定して検証する。
