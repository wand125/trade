# Entry EV Support-Sufficient Loss Risk Prior

日時: 2026-07-03 15:39 JST
更新日時: 2026-07-03 15:39 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00363の次アクションとして、support-sufficient negative monthの既存tradeを、実行時点で見えている特徴と時系列priorだけでloss-risk診断できるか確認した。
- `entry_ev_support_sufficient_loss_risk_prior_diagnostics.py` を追加し、selected trade features、trade timestamp以前だけのcontext prior、feature/prior rule hits、rule summaryを出力した。
- 対象は引き続き `refit2025_validation 2025-03`。9 trades / loss 4本 / month PnL `-0.4730`。
- 対象月だけなら `lossfirst_ge0p40_or_ev_ge5_lossfirst_lt0p30` が4/4 lossを捕捉し、flagged PnL `-1.5900`、skip delta `+1.5900`。
- ただし同ruleは全240 selected tradesでは176 tradesをflagし、flagged PnL `+332.3394`。勝ちtradeを大きく巻き込むため、block policyとしてはreject。
- `ev_ge5_lossfirst_lt0p30` と `side_gap_ge0p15_lossfirst_lt0p30` は対象月のshort損失2本をcleanに拾うが、全体ではそれぞれ flagged PnL `+284.9458` / `+210.1174` で、やはりglobal hard gateにできない。
- 判断: loss-risk prior diagnosticsはaccepted infrastructure。次はdirect blockではなく、loss-riskをreplacement selector / horizon abstention / expected PnL calibrationの補助featureに使う。

## Artifacts

Added script:

- `scripts/experiments/entry_ev_support_sufficient_loss_risk_prior_diagnostics.py`

Added tests:

- `tests/test_entry_ev_support_sufficient_loss_risk_prior_diagnostics.py`

Run:

- `data/reports/backtests/20260703_063906_20260703_entry_ev_00364_support_sufficient_loss_risk_prior/`

Outputs:

- `support_sufficient_loss_risk_target_trades.csv`
- `support_sufficient_loss_risk_month_summary.csv`
- `support_sufficient_loss_risk_prior_context.csv`
- `support_sufficient_loss_risk_prior_context_all_trades.csv`
- `support_sufficient_loss_risk_rule_hits.csv`
- `support_sufficient_loss_risk_rule_summary.csv`
- `support_sufficient_loss_risk_all_trade_features.csv`
- `support_sufficient_loss_risk_meta.json`

## Method

Target:

```text
refit2025_validation:2025-03:short
```

Input config:

```text
data/reports/backtests/20260702_111114_20260702_entry_ev_00318_thin_month_opposite_candidates_00314_w5_s2/config.json
```

Observable selected-trade features:

- `selected_loss_first_prob`
- `pred_taken_ev`
- `pred_side_confidence_gap`
- `pred_taken_entry_local_rank`
- predicted fixed 60/240/720m argmax and predicted value
- direction / combined regime / session / entry hour

Chronological prior:

- For each evaluated trade, use only selected trades with `entry_decision_timestamp` earlier than that trade.
- Context specs:
  - `direction`
  - `direction,session_regime`
  - `direction,combined_regime`
  - `direction,combined_regime,session_regime`
  - `direction,combined_regime,session_regime,entry_hour`
- Prior metrics include count, month count, loss count/rate, large-loss count/rate, PnL sum/mean.

Important:

- Actual PnL is used only for outcome summary.
- Feature/prior rules are diagnostic screens, not accepted block rules.
- This run has only one support-sufficient negative target month, so it is target discovery, not a trained classifier.

## Month Result

| metric | value |
|---|---:|
| month PnL | `-0.4730` |
| trades | `9` |
| loss trades | `4` |
| large loss trades <= -1.0 | `1` |
| winner PnL sum | `+3.0070` |
| loss PnL sum | `-3.4800` |

## Rule Findings

Top target-loss recall rules:

| rule | target loss recall | target flagged PnL | all flagged trades | all flagged PnL | reading |
|---|---:|---:|---:|---:|---|
| `lossfirst_ge0p40_or_ev_ge5_lossfirst_lt0p30` | `1.00` | `-1.5900` | `176` | `+332.3394` | target lossは全部拾うが、全体では勝ちを大量に消す |
| `prior_count_ge5_lossrate_ge0p50` / `direction,combined_regime` | `0.75` | `-0.3570` | `76` | `+70.4174` | targetでは効くが全体ではpositive |
| `ev_ge5_lossfirst_lt0p30` | `0.50` | `-2.6724` | `92` | `+284.9458` | short損失2本を拾うが、全体では強い勝ちも多い |
| `side_gap_ge0p15_lossfirst_lt0p30` | `0.50` | `-2.6724` | `69` | `+210.1174` | 大きいshort loss向けの診断signal |
| `loss_first_ge0p40` | `0.50` | `+1.0824` | `84` | `+47.3936` | long損失2本も拾うがtarget内でも勝ち削除が上回る |

Interpretation:

- 対象月内のloss-risk signは存在する。
- しかし、全体では同じsignが利益の大きいtradeにも強く出る。
- よって「対象月で当たったrule」をそのままentry blockにするのは過学習。

## Target Trade Findings

Key losses:

| trade | pnl | feature/prior read |
|---|---:|---|
| `2025-03-20 00:38 long` | `-0.6360` | `loss_first=0.4533`, pred horizon 720m、prior `long/up_low_vol` mean `-0.1321`。loss-first系で拾う。 |
| `2025-03-20 09:53 long` | `-0.1716` | `loss_first=0.4000`, `long/range_low_vol/london` prior loss rate `0.7778`。loss-first + context priorで拾う。 |
| `2025-03-21 14:00 short` | `-2.3400` | `loss_first=0.1777` で低いが `taken_ev=5.4153`, `side_gap=0.3790`, fixed-best pred `7.1611`。EV過大評価型として拾う。 |
| `2025-03-21 14:29 short` | `-0.3324` | `loss_first=0.2933`, `taken_ev=5.8397`, `side_gap=0.1684`。同じEV過大評価型として拾う。 |

Winner damage:

- `2025-03-31 03:40 short +1.3800` は多くのprior/context risk ruleにflagされる。
- 00363でも同tradeはpredicted fixed 720m actual `-15.5400` で危険に見えるが、実際のcurrent exitではwinner。
- したがってrisk signは「exit/horizon abstentionの警告」には使えても、「entryを消す」にはまだ粗い。

## Decision

- 00364 loss-risk prior diagnosticsはaccepted infrastructure。
- Direct block / hard gateとしてはreject:
  - target月のloss recallは高いが、全期間でflagged PnLが大きくpositive。
  - target-awareに見えるruleをglobal化するとwinner damageが大きい。
- 次の使い方:
  - replacement selectorのrisk feature
  - fixed-horizon exit extensionのabstention feature
  - expected PnL calibrationのoverconfidence feature
  - loss-risk classifierのteacher候補。ただし教師は複数periodに広げる。
- 標準policyはNoTrade。

## Next

1. Build a target-aware replacement selector using loss-risk feature hits as candidate priority, not as a global block.
2. Add horizon abstention: high predicted fixed PnL + low loss-first confidence + bad prior context should reduce trust in horizon argmax.
3. Extend the teacher set beyond one target month before training a loss-risk classifier.
4. Keep rule summaries split into target-month benefit and all-trade winner damage.

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_support_sufficient_loss_risk_prior_diagnostics.py tests/test_entry_ev_support_sufficient_loss_risk_prior_diagnostics.py`: OK
- `uv run python -m unittest tests.test_entry_ev_support_sufficient_loss_risk_prior_diagnostics`: OK
- 00364 support-sufficient loss-risk prior diagnostic run: OK
