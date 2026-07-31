# Entry EV Uncompensated Loss Head

日時: 2026-07-02 15:41 JST
更新日時: 2026-07-02 15:41 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00303の次アクションどおり、`is_large_loss` ではなく `large_loss_uncompensated_by_context` を教師候補にしたchronological OOF headを追加した。
- `scripts/experiments/entry_ev_selected_trade_uncompensated_loss_head.py` を追加し、00303のpath compensation rowsから「同context-month内で補償されない大損」を予測できるか診断した。
- feature setは `base`, `base_prior`, `base_risk`, `base_prior_risk`。`base_risk` は00302 large-loss headのOOF `pred_large_loss_prob` を補助featureとして入れる。
- 結果は否定的。best APは `pnl / source base / base` の `0.1463` で、00302 large-loss headのbest AP `0.2146` より低い。
- threshold除去は160本すべて悪化。positive block deltaは0本、最小悪化でも flagged PnL `+5.6900`。
- 判断: uncompensated path target生成とchronological head infrastructureはaccepted。現feature/headはdirect gateとしてreject。次はtargetを使うなら、pointwise classifierではなくcandidate-level / stateful path featureへ接続する。

## Artifacts

- New script:
  - `scripts/experiments/entry_ev_selected_trade_uncompensated_loss_head.py`
- New test:
  - `tests/test_entry_ev_selected_trade_uncompensated_loss_head.py`
- Main run:
  - `data/reports/backtests/20260702_064017_20260702_entry_ev_uncompensated_loss_head_s1/`

## Input

```text
data/reports/backtests/20260702_062720_20260702_entry_ev_path_compensation_large_loss_s1/selected_trade_path_compensation_rows.csv
```

Run setting:

```text
target:
  large_loss_uncompensated_by_context

target modes:
  factor,pnl

source large-loss feature sets:
  base,base_prior

feature sets:
  base
  base_prior
  base_risk
  base_prior_risk

fold:
  train = selected rows with month < target month
```

Leakage note:

- `large_loss_uncompensated_by_context` は教師ラベルなので、同月の実現context-month PnLを使って作る。
- featuresには `context_month_total_pnl` などの実現context集計を入れていない。
- 実行時に使う場合は、prior-only context、candidate-level state、entry/exit featuresで代理する必要がある。

## Score Summary

| mode | source risk set | feature set | target count | AUC | AP | Brier | pred mean |
|---|---|---|---:|---:|---:|---:|---:|
| pnl | base | base | `22` | `0.6465` | `0.1463` | `0.0933` | `0.0552` |
| pnl | base_prior | base | `22` | `0.6465` | `0.1463` | `0.0933` | `0.0552` |
| pnl | base_prior | base_risk | `22` | `0.6469` | `0.1447` | `0.0916` | `0.0536` |
| pnl | base | base_risk | `22` | `0.6416` | `0.1425` | `0.0921` | `0.0538` |
| factor | base | base | `22` | `0.6537` | `0.1416` | `0.0925` | `0.0536` |
| factor | base_prior | base_risk | `22` | `0.6502` | `0.1395` | `0.0913` | `0.0544` |

Reading:

- `uncompensated` targetはpositive countが22件で、00302のlarge-loss 23件より1件少ない。
- APはbestでも `0.1463`。large-loss headのbest AP `0.2146` から悪化した。
- `pred_large_loss_prob` を入れる `base_risk` / `base_prior_risk` はBrierを少し縮める場合があるが、APやgate品質は改善しない。
- target rowの予測平均はbest `0.0774`、non-target平均 `0.0529` 程度で分離が弱い。

## Threshold Diagnostics

Top rows sorted by least-bad block delta:

| mode | source risk set | feature set | threshold | flagged trades | flagged PnL | delta if removed | flagged target | target recall | flagged large losses |
|---|---|---|---|---:|---:|---:|---:|---:|---:|
| pnl | base_prior | base_prior_risk | `prob_ge_0.4` | `1` | `+5.6900` | `-5.6900` | `0` | `0.0000` | `0` |
| factor | base | base_prior | `prob_ge_0.4` | `2` | `+15.0000` | `-15.0000` | `0` | `0.0000` | `0` |
| factor | base | base_prior_risk | `prob_ge_0.4` | `2` | `+15.0000` | `-15.0000` | `0` | `0.0000` | `0` |
| factor | base_prior | base_prior | `prob_ge_0.4` | `2` | `+15.0000` | `-15.0000` | `0` | `0.0000` | `0` |
| factor | base_prior | base_risk | `prob_ge_0.4` | `2` | `+15.0000` | `-15.0000` | `0` | `0.0000` | `0` |
| factor | base_prior | base_prior_risk | `prob_ge_0.3` | `7` | `+16.5424` | `-16.5424` | `1` | `0.0455` | `1` |

Reading:

- 160 threshold rowsのうち、positive block deltaは `0`。
- 最小悪化でもtargetを1件も拾わず、winnerだけを削る。
- target recallが出るthresholdでも、flagged PnLはプラスで除去すると悪化する。

## Failure Pattern

Top predicted rows still include the compensated/non-target 2025-11 path:

| mode | source risk set | feature set | month | context | PnL | target | pred uncomp prob | pred large-loss prob | context total |
|---|---|---|---|---|---:|---:|---:|---:|---:|
| pnl | base | base | `2025-11` | `short|down_normal_vol|london` | `-7.9800` | false | `0.6541` | `0.6541` | `+54.1000` |
| pnl | base | base | `2025-11` | `short|down_normal_vol|london` | `+62.0800` | false | `0.6359` | `0.6359` | `+54.1000` |
| pnl | base | base_risk | `2025-11` | `short|down_normal_vol|london` | `-7.9800` | false | `0.5509` | `0.6541` | `+54.1000` |
| pnl | base | base_risk | `2025-11` | `short|down_normal_vol|london` | `+62.0800` | false | `0.5316` | `0.6359` | `+54.1000` |

Actual target rows are not strongly lifted:

| metric | best value |
|---|---:|
| target pred mean | `0.0774` |
| target pred median | `0.0233` |
| non-target pred mean | `0.0529` |
| non-target pred median | `0.0117` |

Reading:

- Labelをpath-awareにしても、現featureでは補償済みpathとuncompensated pathを分けきれない。
- 大損確率を補助featureに入れても、最上位は依然としてpositive contextを拾う。
- これは「ラベルだけ直せば解ける」問題ではなく、candidate replacement / stateful sequence / exit timing contextが必要。

## Decision

Accepted:

- `large_loss_uncompensated_by_context` target generation
- chronological uncompensated-loss head infrastructure
- `pred_large_loss_prob` を補助featureとして比較する診断経路

Rejected:

- uncompensated-loss probabilityのdirect hard gate
- current feature setでのpointwise target head標準化
- risk probabilityを足しただけでpositive pathを分離できる、という仮説

Standard policy remains NoTrade.

## Next

1. Pointwise classifierを増やすより、candidate-level selector / stateful replayへ戻す。
2. `large_loss_uncompensated_by_context` は教師候補として残し、entry/exit sequence featuresやreplacement stateと組み合わせる。
3. 2025-11の補償済みpairを明示的なnegative exampleとして、同context内のwinner availability / replacement cost / exit timingをfeature化できるか検討する。
4. NoTrade-first selector、role/month floor、support-aware diagnosticsを維持する。

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_selected_trade_uncompensated_loss_head.py tests/test_entry_ev_selected_trade_uncompensated_loss_head.py`: OK
- `uv run python -m unittest tests.test_entry_ev_selected_trade_uncompensated_loss_head`: OK
- `uv run python -m unittest tests.test_entry_ev_selected_trade_uncompensated_loss_head tests.test_entry_ev_selected_trade_path_compensation_diagnostics tests.test_docs_reports`: OK
- `git diff --check`: OK
- uncompensated-loss head run: OK
