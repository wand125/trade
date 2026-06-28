# Candidate Selection Jackknife

日時: 2026-06-29 07:10 JST
更新日時: 2026-06-29 07:10 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻である `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## 目的

`00107` ではfold間PnL標準偏差をcandidate rankingへ追加したが、top候補は変わらなかった。次に確認すべきことは、候補選定がvalidation内の特定月に依存していないかである。

今回は未使用holdoutへ後付け最適化せず、validation foldだけでleave-one-fold-out診断を追加する。各月を1つ抜いて候補を選び直し、その抜いた月で選定候補が壊れないかを見る。

## 実装

`model-candidate-selection-jackknife` を追加した。

入力は保存済み `model-candidate-selection` の `config.json` またはrun directory。base/cost sweep pathと選定条件をconfigから読み直すため、長いoption listを再入力しない。

処理:

```text
1. full selection configを読む
2. validation fold labelを period_start の YYYY-MM から取得
3. 各foldを1つ除外
4. 残りfoldだけで同じcandidate selectionを再実行
5. 選ばれた候補を、除外したfoldのbase/cost sweepで評価
6. full topと一致するか、除外foldでpassするかを保存
```

4fold selectionを3foldで再実行するため、`min_base_folds` / `min_cost_folds` は残りfold数に合わせて下げる。その他の `min_trades`, `max_drawdown`, PnL threshold, ranking weightは元configを維持する。

## Validation

`00107` の以下2configで実行した。

- stability weight 0: `data/reports/backtests/pnl_stability_candidate_ranking_w0/20260628_220328_model_candidate_selection/`
- stability weight 1.0: `data/reports/backtests/pnl_stability_candidate_ranking_w1/20260628_220328_model_candidate_selection/`

両者のjackknife結果は同じだった。

| left out | selected rule set | full top match | train cost min | train PnL stability | held-out base min | held-out cost min | held-out min | pass |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| 2024-07 | `down5,up10` | yes | `96.8776` | `17.3036` | `198.1782` | `155.0210` | `155.0210` | yes |
| 2024-09 | `down5,up10` | yes | `118.6468` | `31.7335` | `138.0338` | `96.8776` | `96.8776` | yes |
| 2024-11 | `down5,range5` | no | `128.7538` | `16.3270` | `94.6622` | `86.0172` | `86.0172` | yes |
| 2025-01 | `down5,up10` | yes | `96.8776` | `33.4269` | `143.6102` | `118.6468` | `118.6468` | yes |

集計:

- rows: `4`
- pass: `4/4`
- full top match: `3/4`
- held-out min minimum: `86.0172`
- held-out min sum: `456.5626`

## 判断

`model-candidate-selection-jackknife` は採用する。候補選定のfold依存を、未使用holdoutを見る前に確認できるため。

今回の結果では、4fold内で強い単月依存は見えない。2024-11を抜いたときだけfull topと違う候補が選ばれたが、その候補も抜いた2024-11でbase/cost両方を通過した。

ただし、これは標準policy採用の根拠ではない。理由:

- validation内部のjackknifeであり、未知regimeの代替ではない。
- 既存holdoutではすでに2025-04などの崩れを見ている。
- 今回の診断は「validation内で明らかな単月依存がある候補を殺す」ためのもので、未来性能を保証しない。

次は、このjackknifeを事前診断として残したうえで、追加walk-forward foldまたは未使用月へ同じ事前条件を固定適用する。

## Artifacts

- jackknife w0: `data/reports/backtests/jackknife_candidate_ranking_w0/20260628_221031_model_candidate_selection_jackknife/metrics.csv`
- jackknife w1: `data/reports/backtests/jackknife_candidate_ranking_w1/20260628_221031_model_candidate_selection_jackknife/metrics.csv`

## Verification

- `python3 -W ignore -m unittest tests.test_backtest.BacktestTests.test_candidate_selection_jackknife_evaluates_left_out_fold`: OK
- `python3 -m trade_data.backtest model-candidate-selection-jackknife --help`: OK
- `python3 -m trade_data.backtest model-candidate-selection-jackknife`: OK for w0 and w1 configs
- `python3 -W ignore -m unittest tests.test_backtest tests.test_docs_reports`: OK, 67 tests
- `python3 -W ignore -m unittest discover tests`: OK, 153 tests
- `git diff --check`: OK
