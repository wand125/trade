# Entry EV Pre-Block Prior Context Guard

日時: 2026-07-02 03:24 JST
更新日時: 2026-07-02 03:24 JST

採番メモ: 通し番号、最新判断、再採番はファイルシステムの更新時刻(mtime)や `更新日時` ではなく、本文内の作成時刻 `日時` を参照する。ここでいうファイル内の時刻は作成時刻の `日時` であり、編集履歴用の `更新日時` ではない。

## Summary

- 00265の次アクションとして、pre-block side-gapで新たに入ったrefit2025 only-candidate rowsを、前月までの同context損失だけで止められるか診断した。
- `scripts/experiments/entry_ev_delta_prior_context_guard_diagnostics.py` を追加した。
- 診断はstateful replayではなく、trade-delta rows上の no-replacement estimate。ブロック後に別tradeが入る効果はまだ含まない。
- `context_id = direction/combined_regime/session_regime` は細かすぎてprior supportが薄く、改善しない。
- `direction_regime = direction/combined_regime` は `short/down_normal_vol` を前月損失から拾い、候補行合計では `min_prior_count=1`, `prior_loss_threshold=60` が flagged 14 rows / `-134.1100` を止める見込み。
- 候補別では q99/floor5 が最も反応し、`min_prior_count=1`, `threshold=20` で flagged 6 rows / `-110.6212`, kept pnl `+19.6780`。q95/floor5は `threshold=60` で flagged 9 rows / `-44.5200`, kept `-105.0980` に留まる。
- 判断: prior context guard診断インフラはaccepted。q99向けの二段階guard候補として有望だが、stateful replay前なので標準policyにはしない。

## Artifacts

- Added script:
  - `scripts/experiments/entry_ev_delta_prior_context_guard_diagnostics.py`
- Added test:
  - `tests/test_entry_ev_delta_prior_context_guard_diagnostics.py`
- Input:
  - `data/reports/backtests/20260701_181417_20260702_entry_ev_replguard_preblockgap_refit_delta_context_s1/enriched_trade_delta_rows.csv`
- Diagnostic artifact:
  - `data/reports/backtests/20260701_182358_20260702_entry_ev_preblock_prior_context_guard_diag_s2/`

## What Was Tested

For each only-candidate row:

```text
same candidate + same context scope の過去月only-candidate PnLを集計
prior_trade_count >= min_prior_count
prior_month_count >= min_prior_months
prior_pnl_sum <= -prior_loss_threshold
ならflag
```

Important leakage rule:

- 同じ月の先行rowは使わない。
- current monthより前のmonthだけをpriorにする。

Scopes:

- `direction_regime`: `direction/combined_regime`
- `context_id`: `direction/combined_regime/session_regime`

Threshold grid:

- `min_prior_count`: `1,2,3`
- `min_prior_months`: `1`
- `prior_loss_threshold`: `20,40,60,100`

## Overall Result

All only-candidate rows across q99/q95:

| scope | min prior count | threshold | flagged rows | flagged pnl | kept pnl | no-replacement delta | first flagged month |
|---|---:|---:|---:|---:|---:|---:|---|
| direction_regime | `1` | `60` | `14` | `-134.1100` | `-106.4512` | `+134.1100` | 2025-05 |
| direction_regime | `1` | `20` | `20` | `-132.4884` | `-108.0728` | `+132.4884` | 2025-05 |
| direction_regime | `1` | `40` | `15` | `-96.5100` | `-144.0512` | `+96.5100` | 2025-05 |
| context_id | `1` | `100` | `0` | `0.0000` | `-240.5612` | `0.0000` | |
| context_id | `3` | `60` | `3` | `+4.8230` | `-245.3842` | `-4.8230` | 2025-11 |
| context_id | `2` | `60` | `6` | `+11.8000` | `-252.3612` | `-11.8000` | 2025-10 |

Reading:

- `direction_regime` は粗いがprior supportがあり、2025-04 lossから2025-05 `short/down_normal_vol` tailを拾える。
- `context_id` はsessionまで細かくしたことで、priorが薄くなるか、勝ちrowをflagして悪化する。

## Candidate Breakdown

Best candidate-level direction_regime settings:

| candidate | min prior count | threshold | flagged rows | flagged pnl | kept pnl | no-replacement delta | first flagged |
|---|---:|---:|---:|---:|---:|---:|---|
| q99/floor5 | `1` | `20` | `6` | `-110.6212` | `+19.6780` | `+110.6212` | 2025-05 |
| q99/floor5 | `1` | `40` | `5` | `-89.5900` | `-1.3532` | `+89.5900` | 2025-05 |
| q99/floor5 | `1` | `60` | `5` | `-89.5900` | `-1.3532` | `+89.5900` | 2025-05 |
| q95/floor5 | `1` | `60` | `9` | `-44.5200` | `-105.0980` | `+44.5200` | 2025-05 |
| q95/floor5 | `2` | `60` | `9` | `-44.5200` | `-105.0980` | `+44.5200` | 2025-05 |

Flagged context for the overall best `direction_regime / min_count1 / threshold60`:

| candidate | direction_regime | flagged rows | flagged pnl | positive pnl | negative pnl | first | last |
|---|---|---:|---:|---:|---:|---|---|
| q99/floor5 | `short/down_normal_vol` | `5` | `-89.5900` | `+56.2100` | `-145.8000` | 2025-05 | 2025-11 |
| q95/floor5 | `short/down_normal_vol` | `9` | `-44.5200` | `+101.2800` | `-145.8000` | 2025-05 | 2025-12 |

Month detail under `direction_regime / min_count1 / threshold60`:

| month | candidate | rows | pnl | prior pnl |
|---|---|---:|---:|---:|
| 2025-05 | q95/floor5 | `3` | `-145.8000` | `-72.4680` |
| 2025-05 | q99/floor5 | `3` | `-145.8000` | `-70.1280` |
| 2025-10 | q95/floor5 | `1` | `+1.5000` | `-218.2680` |
| 2025-11 | q95/floor5 | `3` | `+97.4270` | `-216.7680` |
| 2025-11 | q99/floor5 | `2` | `+56.2100` | `-215.9280` |
| 2025-12 | q95/floor5 | `2` | `+2.3530` | `-119.3410` |

The same guard catches the 2025-05 large loss but later also blocks profitable 2025-11 rows. That is the main caution.

## Interpretation

This supports the 00265 split:

```text
pre-block side-gap = support normalization
prior context downside = candidate admission signal
```

But it is not yet a policy result:

- It assumes flagged rows are simply removed.
- It does not re-run one-position replacement.
- It evaluates thresholds on the same refit delta rows.
- It does not yet show whether q99/floor5 should be chosen over q95/floor5 in an external window.

The most useful signal is not session-level context. It is coarse `direction_regime`, especially `short/down_normal_vol`, with at least one prior losing month.

## Decision

Accepted:

- prior-context guard diagnostic infrastructure
- evidence that coarse prior downside can catch the 2025-05 pre-block tail
- q99/floor5 as the better next diagnostic candidate than q95/floor5

Not accepted:

- any standard policy promotion
- static `short/down_normal_vol` blacklist
- threshold selection from this same refit window
- no-replacement estimate as stateful evidence

Standard policy remains NoTrade.

## Next

1. Convert the best q99 diagnostic setting into a true stateful replay:
   - pre-block side-gap support normalization
   - prior-month `direction_regime` downside guard
   - start with q99/floor5, `min_prior_count=1`, threshold band `20..60`
2. In replay, measure replacement path:
   - removed bad candidate rows
   - removed good candidate rows
   - newly admitted replacement rows
   - role/month floor and side balance
3. Keep q95 as a stress comparison, not primary. Its no-replacement kept pnl remains negative.

## Verification

- `python3 -m unittest tests.test_entry_ev_delta_prior_context_guard_diagnostics`: OK
- `python3 -m py_compile scripts/experiments/entry_ev_delta_prior_context_guard_diagnostics.py tests/test_entry_ev_delta_prior_context_guard_diagnostics.py`: OK
- prior-context diagnostic run: OK
