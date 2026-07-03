# Entry EV Surface Support Gap Diagnostics

日時: 2026-07-03 22:44 JST
更新日時: 2026-07-03 22:44 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00382で残ったcandidate gapを、candidate pool / prior count / prior month / prior actual meanのどこで落ちたかに分解する後処理診断を追加した。
- `scripts/experiments/entry_ev_surface_support_gap_diagnostics.py` を追加し、既存surface artifactのchoicesとcandidatesを照合する。
- 同じrisk tradeを複数risk selectorが共有する場合、candidate artifactは最初のselector名でだけpoolを書き出すため、診断側ではrisk selector完全一致がない場合にfamily/month/risk_trade/calibration単位でfallback照合する。
- 00382 artifactを診断した結果、残るcandidate gapは `prior_count_gap` ではなく `prior_month_and_actual_gap` だった。
- 重要: `hgb2024_0306 2024-03` と `fresh2024 2024-03` はcandidate poolとpositive actual candidate自体はあるが、max prior month countが1、max prior actual meanが負なのでsupport候補にならない。
- 判断: support gap診断はaccepted infrastructure。early-month targetは「候補生成なし」ではなく「薄くて負のpriorしかない候補をどう扱うか」の問題として次へ進む。標準policyはNoTrade。

## Artifacts

Run:

- `data/reports/backtests/20260703_134354_20260703_entry_ev_00383_surface_support_gap_00382/`

Inputs:

- `data/reports/backtests/20260703_133252_20260703_entry_ev_00382_all_family_shrunk_prior_surface_00378/`

Code:

- `scripts/experiments/entry_ev_surface_support_gap_diagnostics.py`
- `tests/test_entry_ev_surface_support_gap_diagnostics.py`

## Method

For each choice row in the selector surface:

```text
exact pool key:
  family, month, risk_selector, risk_trade_id, calibration_min_context_count

fallback pool key:
  family, month, risk_trade_id, calibration_min_context_count
```

Then apply the same support floors used by the surface:

```text
candidate_min_prior_count
candidate_min_prior_month_count
candidate_min_prior_actual_mean
```

Support stage categories:

| stage | meaning |
|---|---|
| `no_risk_trade` | observable risk selector did not select a current trade |
| `risk_trade_winner` | selected trade was not a loss |
| `no_candidate_pool` | no statefully available replacement pool |
| `prior_count_gap` | pool exists but prior count floor removes all rows |
| `prior_month_gap` | prior count passes, prior month floor removes all rows |
| `prior_month_and_actual_gap` | prior month floor fails and even max prior actual mean is below floor |
| `prior_actual_gap` | count/month pass but prior actual floor removes all rows |
| `supported_repaired` | supported candidate repairs the month to non-negative |
| `supported_replacement_gap` | supported candidate exists but chosen replacement fails |

## Result

Top rows:

| risk selector | score | prior count | success | candidate gap | prior month+actual gap | risk gap | mean after | support stages |
|---|---|---:|---:|---:|---:|---:|---:|---|
| `oracle:worst_loss` | `side_score` | 20 | 3 | 2 | 2 | 0 | `+10.8766` | `prior_month_and_actual_gap:2; supported_repaired:3` |
| `oracle:worst_loss` | `shrunk_prior_actual_mean` | 20 | 3 | 2 | 2 | 0 | `+1.8132` | `prior_month_and_actual_gap:2; supported_repaired:3` |
| `combined:any_lossrisk` | `side_score` | 20 | 2 | 1 | 1 | 2 | `+10.1326` | `prior_month_and_actual_gap:1; risk_trade_winner:2; supported_repaired:2` |
| `feature:side_gap_ge0p15_lossfirst_lt0p30` | `side_score` | 20 | 2 | 1 | 1 | 2 | `+5.7560` | `no_risk_trade:1; prior_month_and_actual_gap:1; risk_trade_winner:1; supported_repaired:2` |
| `feature:ev_ge5_lossfirst_lt0p30` | `side_score` | 20 | 2 | 2 | 2 | 1 | `+5.3544` | `no_risk_trade:1; prior_month_and_actual_gap:2; supported_repaired:2` |
| `feature:ev_ge5_lossfirst_lt0p30` | `shrunk_prior_actual_mean` | 20 | 2 | 2 | 2 | 1 | `-0.0384` | `no_risk_trade:1; prior_month_and_actual_gap:2; supported_repaired:2` |

The strict read:

- There are no `prior_count_gap` rows in the top surface rows.
- There are no pure `prior_actual_gap` rows in the top surface rows.
- Candidate gaps come from early-month prior evidence being both too short and negative.

## Representative Detail

Nonoracle row:

```text
risk_selector = feature:ev_ge5_lossfirst_lt0p30
replacement_score_mode = shrunk_prior_actual_mean
candidate_min_prior_count = 20
candidate_min_prior_month_count = 2
candidate_min_prior_actual_mean = 0
```

| target | outcome | support stage | candidate rows | prior count pass | prior month pass | positive actual candidates | best any actual | max prior months | max prior actual mean |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| `hgb2024_0306 2024-03` | candidate gap | `prior_month_and_actual_gap` | 117 | 117 | 0 | 29 | `+18.2800` | 1 | `-1.3401` |
| `fresh2024 2024-03` | candidate gap | `prior_month_and_actual_gap` | 20 | 20 | 0 | 5 | `+8.0770` | 1 | `-1.3401` |
| `fresh2024 2024-11` | repaired | `supported_repaired` | 27 | 27 | 27 | 16 | `+58.2400` | 7 | `+10.2969` |
| `refit2025 2025-03` | repaired | `supported_repaired` | 422 | 422 | 422 | 347 | `+36.3900` | 12 | `+22.3745` |
| `hybrid2025_0912 2025-11` | risk gap | `no_risk_trade` | 0 | 0 | 0 | 0 | n/a | 0 | n/a |

Oracle row:

```text
risk_selector = oracle:worst_loss
replacement_score_mode = shrunk_prior_actual_mean
candidate_min_prior_count = 20
```

| target | outcome | support stage | candidate rows | prior count pass | prior month pass | positive actual candidates | best any actual | max prior months | max prior actual mean |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| `hgb2024_0306 2024-03` | candidate gap | `prior_month_and_actual_gap` | 126 | 126 | 0 | 38 | `+18.2800` | 1 | `-1.3401` |
| `fresh2024 2024-03` | candidate gap | `prior_month_and_actual_gap` | 20 | 20 | 0 | 5 | `+8.0770` | 1 | `-1.3401` |
| `fresh2024 2024-11` | repaired | `supported_repaired` | 27 | 27 | 27 | 16 | `+58.2400` | 7 | `+10.2969` |
| `refit2025 2025-03` | repaired | `supported_repaired` | 422 | 422 | 422 | 347 | `+36.3900` | 12 | `+22.3745` |
| `hybrid2025_0912 2025-11` | repaired | `supported_repaired` | 46 | 46 | 46 | 20 | `+28.6700` | 20 | `+6.6193` |

## Interpretation

00382では「all-family priorでcandidate gapが少し減った」と読んだが、00383で内訳が分かった。

- `hgb2024_0306 2024-03` と `fresh2024 2024-03` はcandidate poolがないわけではない。
- positive actual candidateも存在する。
- ただし、そのpositive candidateを実行時に信じるためのpriorが1ヶ月しかなく、historical actual meanも負。
- よって、単純に `candidate_min_prior_month_count=1` へ下げるだけでは不十分。`candidate_min_prior_actual_mean=0` も同時に崩す必要があり、これは00379で見えたcross-family calibration不安定性を再開する。

## Decision

Accepted:

- support gap decomposition as infrastructure
- risk-selector fallback matching for shared risk trade candidate pools
- `prior_month_and_actual_gap` as a first-class diagnostic stage

Rejected:

- treating hgb/fresh03 as raw candidate-generation absence
- lowering prior month floor alone as the next main fix
- using positive actual candidate existence as executable evidence

Standard policy remains NoTrade.

## Next

1. For early-month targets, build a diagnostic lane that evaluates `prior_month_count=1` candidates separately, but requires an additional confidence signal before using them.
2. Test a support-limited candidate scoring report, not a policy replay:
   - positive actual candidates with negative prior mean
   - horizon / side / session buckets
   - family-source diversity
   - whether a coarse context has a non-negative prior while fine context is negative
3. Keep support-sufficient replacement calibration separate for targets already at prior month >=2.

## Verification

- `uv run python -m py_compile scripts/experiments/entry_ev_surface_support_gap_diagnostics.py tests/test_entry_ev_surface_support_gap_diagnostics.py`: OK
- `uv run python -m unittest tests.test_entry_ev_surface_support_gap_diagnostics`: OK
- 00383 surface support gap diagnostics run: OK
